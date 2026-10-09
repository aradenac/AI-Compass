"""PLAT-26: non-networked management entrypoint for one registered migration.

A production apply needs a signed, one-candidate approval envelope on stdin.
The *host promotion CLI*, not the user-facing web app, may construct it.
"""
import hashlib
import json
import os
from pathlib import Path
import sys

from django.core.management.base import BaseCommand, CommandError

from config import schema_promotion

ARTIFACT = Path(__file__).resolve().with_name("stage_model_v1_to_v2.py")


class Command(BaseCommand):
    help = "Dry-run or apply one registered Model schema migration; never edit historical revisions."

    def add_arguments(self, parser):
        parser.add_argument("--preview", action="store_true")
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--operator", required=True)
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **opts):
        if opts["preview"] == opts["apply"]:
            raise CommandError("Select exactly one of --preview or --apply")
        if os.getenv("AI_COMPASS_STAGING") == "1":
            raise CommandError("This production command is not a staging transform")
        from django.contrib.auth import get_user_model
        person = get_user_model().objects.filter(username=opts["operator"], is_active=True).first()
        if person is None or person.is_superuser or not person.has_perm("auth.maintenance_triage"):
            raise CommandError("Active maintenance_triage operator required")
        if opts["preview"]:
            result = schema_promotion.dry_run()
        else:
            if os.getenv("AI_COMPASS_PROMOTION_API_FROZEN") != "1":
                raise CommandError("Production API must be write-frozen by the trusted host orchestrator")
            raw = sys.stdin.read(16385)
            if len(raw) > 16384:
                raise CommandError("Approval proof exceeds 16 KiB")
            try:
                envelope = json.loads(raw)
            except ValueError as exc:
                raise CommandError("Expected signed approval envelope on stdin") from exc
            if not isinstance(envelope, dict) or not isinstance(envelope.get("proof"), dict) or (
                envelope["proof"].get("operator") != opts["operator"]
            ):
                raise CommandError("Approving operator mismatch")
            artifact_sha = hashlib.sha256(ARTIFACT.read_bytes()).hexdigest()
            result = schema_promotion.apply_batch(envelope, expected_migration_sha=artifact_sha)
        if opts["json"]:
            self.stdout.write(json.dumps(result, sort_keys=True))
        else:
            self.stdout.write(str(result))
