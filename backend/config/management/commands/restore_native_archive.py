"""Explicit test-only command for native archive preview and controlled replay."""
import json

from django.core.management.base import BaseCommand, CommandError

from config.native_restore import inspect, RestoreError


class Command(BaseCommand):
    help = "Preview/import a verified native archive into an EMPTY disposable staging Server only."

    def add_arguments(self, parser):
        parser.add_argument("archive")
        parser.add_argument("--operator", required=True, help="Active privileged local account")
        choice = parser.add_mutually_exclusive_group(required=True)
        choice.add_argument("--preview", action="store_true")
        choice.add_argument("--apply", action="store_true")
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        try:
            outcome = inspect(options["archive"], options["operator"],
                              apply=options["apply"])
        except (RestoreError, OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(outcome, sort_keys=True) if options["json"]
                          else "%s: %d rows, %d original blobs" % (
                              outcome["status"], outcome["records"], outcome["blobs"]))
