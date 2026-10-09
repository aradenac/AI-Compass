"""Registered PLAT-35 staging-only example: append validated Model v2 revisions.

Never update a historical CatalogRevision or ObjectTypeVersion in place.
No default or conversion of unknown keys: an invalid v1 extension aborts atomically.
"""
import json
import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from config.catalog_schemas import validate_model, InvalidModel
from config.models import CatalogItem, CatalogRevision, CatalogAuditEvent, ObjectTypeVersion

CANDIDATE_PATTERN = re.compile(r"^[0-9a-f]{16}$")


def assert_disposable_target():
    if (os.environ.get("AI_COMPASS_STAGING") != "1"
            or not CANDIDATE_PATTERN.fullmatch(os.environ.get("AI_COMPASS_STAGING_CANDIDATE", ""))
            or os.environ.get("DB_NAME") != "ai_compass_restore_verify"
            or os.environ.get("DB_USER") != "ai_compass_restore"
            or os.environ.get("DB_HOST") != "db"):
        raise CommandError("Staging-only migration refuses non-disposable database configuration")


def upgrade():
    with transaction.atomic():
        target = ObjectTypeVersion.objects.get(type_slug="model", version=2)
        items = list(CatalogItem.objects.select_for_update(of=("self",)).filter(type_slug="model")
                     .select_related("current_revision__schema_version").order_by("pk"))
        changed = []
        for item in items:
            old = item.current_revision
            if old is None:
                raise CommandError("Catalog identity missing current revision")
            if old.schema_version.type_slug != "model":
                raise CommandError("Cross-type schema link")
            if old.schema_version.version != 1:
                continue
            try:
                validate_model(old.display_name, old.properties, target.json_schema)
            except InvalidModel as error:
                raise CommandError("Cannot upgrade " + item.public_id + ": " + str(error)) from error
            revision = CatalogRevision.objects.create(
                item=item, number=old.number + 1, schema_version=target,
                display_name=old.display_name, properties=old.properties,
                created_by=old.created_by,
            )
            item.current_revision = revision
            item.save(update_fields=["current_revision"])
            CatalogAuditEvent.objects.create(
                item=item, revision=revision, actor=old.created_by, action="schema_migrated")
            changed.append(item.public_id)
        return changed


class Command(BaseCommand):
    help = "Upgrade v1 Model current revisions to v2 on an isolated staging DB only."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        assert_disposable_target()
        try:
            upgraded = upgrade()
        except ObjectTypeVersion.DoesNotExist as error:
            raise CommandError("Registered Model v2 schema unavailable") from error
        result = {"status": "passed", "migration": "model-v1-to-v2@1",
                  "changed": len(upgraded), "public_ids": upgraded}
        self.stdout.write(json.dumps(result, sort_keys=True) if options["json"]
                          else "Upgraded " + str(len(upgraded)) + " v1 Model records")
