"""PLAT-27: read-only data diagnostics, intended for cron/systemd or operator use."""
import json

from django.core.management.base import BaseCommand

from config.data_health_services import scan


class Command(BaseCommand):
    help = "Run registered non-destructive data-health checks and deduplicated triage."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")

    def handle(self, *args, **options):
        report = scan(actor=None)
        self.stdout.write(json.dumps(report, sort_keys=True) if options["json"] else
                          f"Data Health: {report['findings']} findings, {report['new']} new")
