"""Read-only evidence reconciliation and explicitly gated stale-temp cleanup.

Never removes orphaned finalized payloads: they may be recoverable artifacts
from an interrupted metadata transaction or evidence backup.
"""
import json
from pathlib import Path
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from config.evidence_store import BrokenEvidence, EvidenceError, blob_path, store_root, verify_bytes
from config.models import EvidenceBlob, EvidenceLink


def inspect(*, prune_stale_incoming=False, stale_seconds=3600):
    root = store_root()
    expected = {row["sha256"]: row["size"] for row in EvidenceBlob.objects.values("sha256", "size")}
    missing_or_corrupt = []
    for digest, size in expected.items():
        try:
            verify_bytes(digest, size=size)
        except (BrokenEvidence, EvidenceError):
            missing_or_corrupt.append(digest)
    on_disk = set()
    blob_dir = root / "blobs"
    if blob_dir.exists():
        for path in blob_dir.rglob("*"):
            if path.is_file() or path.is_symlink():
                on_disk.add(path.name)
    orphan_files = sorted(on_disk - expected.keys())
    temp_files = []
    removed = []
    incoming = root / ".incoming"
    if incoming.exists():
        for path in incoming.iterdir():
            if not path.is_file() or path.is_symlink():
                temp_files.append(path.name)
                continue
            temp_files.append(path.name)
            if prune_stale_incoming and time.time() - path.stat().st_mtime >= stale_seconds:
                path.unlink()
                removed.append(path.name)
    # FK restrictions reject ordinary invalid writes; the diagnostic also
    # detects dangling refs from accidental manual DB corruption/imports.
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT count(*) FROM config_evidencelink l
            LEFT JOIN config_evidenceblob b ON b.sha256=l.blob_id
            LEFT JOIN config_catalogitem i ON i.id=l.item_id
            LEFT JOIN config_catalogrevision r ON r.id=l.revision_id
            WHERE b.sha256 IS NULL OR i.id IS NULL
               OR (l.revision_id IS NOT NULL AND
                   (r.id IS NULL OR r.item_id<>l.item_id))
        """)
        dangling = cursor.fetchone()[0]
    without_links = list(EvidenceBlob.objects.exclude(
        sha256__in=EvidenceLink.objects.values("blob_id")
    ).values_list("sha256", flat=True))
    return {
        "status": "broken" if missing_or_corrupt or dangling else
                  "attention" if orphan_files or temp_files or without_links else "ok",
        "blob_rows": len(expected), "link_rows": EvidenceLink.objects.count(),
        "missing_or_corrupt_blobs": sorted(missing_or_corrupt),
        "orphan_files": orphan_files,
        "unlinked_blob_rows": sorted(without_links),
        "incoming_files": sorted(temp_files),
        "pruned_stale_incoming": sorted(removed),
        "dangling_links": dangling,
        "evidence_is_in_db_backup": False,
    }


class Command(BaseCommand):
    help = "Inspect evidence integrity; optionally remove OLD interrupted temp uploads only"

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--prune-stale-incoming", action="store_true")
        parser.add_argument("--stale-seconds", type=int, default=3600)

    def handle(self, *args, **options):
        if options["stale_seconds"] < 3600:
            raise CommandError("Minimum stale interval is one hour")
        result = inspect(prune_stale_incoming=options["prune_stale_incoming"],
                         stale_seconds=options["stale_seconds"])
        self.stdout.write(json.dumps(result, sort_keys=True) if options["json"]
                          else "Evidence reconciliation: " + result["status"])
        if result["status"] == "broken":
            raise CommandError("Missing/corrupt blobs or dangling evidence links detected")
