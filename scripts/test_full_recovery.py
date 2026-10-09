#!/usr/bin/env python3
"""Offline PLAT-29 failure-path tests; never interact with production Docker."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import full_recovery as f
import recovery as db

CONTENT = b"%PDF-1.4\nprivate original evidence\n"
HASH = hashlib.sha256(CONTENT).hexdigest()
INSPECTION = {"item_count": 1, "revision_count": 2,
              "evidence_db_references": {"blob_count": 1, "link_count": 2, "sha256": [HASH]}}
BLOBS = [{"sha256": HASH, "size": len(CONTENT)}]


class FullRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.dump = self.root / "ai-compass-20261009T220000Z-012345abcdef.dump"
        self.dump.write_bytes(b"PGDMP" + b"\x00" * 300)
        self.archive = f.sibling(self.dump, ".blobs.tar")
        self.manifest_file = f.sibling(self.dump, ".full.json")
        self.marker = f.sibling(self.dump, ".full.complete")
        self.make_tar()
        self.record = {
            "format": f.FORMAT, "status": "verified",
            "backup_id": "20261009T220000Z-012345abcdef",
            "created_at": "2020-10-09T22:00:00+00:00",
            "dump_file": self.dump.name, "blobs_file": self.archive.name,
            "database": {"sha256": db.hash_file(self.dump), "bytes": self.dump.stat().st_size},
            "evidence_archive": {"sha256": db.hash_file(self.archive), "bytes": self.archive.stat().st_size},
            "restored_inspection": INSPECTION, "blobs": BLOBS, "link_count": 2,
        }
        self.commit()

    def make_tar(self, *, name=None, contents=CONTENT, symlink=False):
        with tarfile.open(self.archive, "w") as tar:
            item = tarfile.TarInfo(name or "blobs/" + HASH[:2] + "/" + HASH[2:4] + "/" + HASH)
            if symlink:
                item.type = tarfile.SYMTYPE
                item.linkname = "/etc/passwd"
                item.size = 0
                tar.addfile(item)
            else:
                item.size = len(contents)
                tar.addfile(item, io.BytesIO(contents))

    def commit(self):
        self.record["database"] = {
            "sha256": db.hash_file(self.dump), "bytes": self.dump.stat().st_size}
        self.record["evidence_archive"] = {
            "sha256": db.hash_file(self.archive), "bytes": self.archive.stat().st_size}
        db.durable_write(self.manifest_file, db.json_bytes(self.record))
        db.durable_write(self.marker, hashlib.sha256(self.manifest_file.read_bytes()).hexdigest() + "\n")

    def test_verified_atomic_point_and_stage_exact_bytes(self):
        self.assertEqual(f.verified_manifest(self.dump)["link_count"], 2)
        stage = self.root / "isolated"
        f.listing(self.archive, BLOBS, destination=stage)
        self.assertEqual((stage / "blobs" / HASH[:2] / HASH[2:4] / HASH).read_bytes(), CONTENT)
        self.assertEqual(f.full_entries(self.root)[0][0]["backup_id"], self.record["backup_id"])

    def test_partial_dump_or_mispaired_archive_never_success(self):
        self.archive.write_bytes(b"bad")
        with self.assertRaisesRegex(db.RecoveryError, "corrupt"):
            f.verified_manifest(self.dump)
        self.assertFalse(f.full_entries(self.root))
        self.make_tar()
        self.marker.unlink()
        with self.assertRaisesRegex(db.RecoveryError, "Incomplete"):
            f.verified_manifest(self.dump)
        self.commit()
        self.record["link_count"] = 18
        self.commit()
        with self.assertRaisesRegex(db.RecoveryError, "counts"):
            f.verified_manifest(self.dump)

    def test_corrupt_missing_or_unreferenced_blob_and_symlink_fail(self):
        self.make_tar(contents=b"fake original bytes")
        self.commit()
        with self.assertRaisesRegex(db.RecoveryError, "Corrupt"):
            f.verified_manifest(self.dump)
        self.make_tar(name="../../unsafe", contents=CONTENT)
        self.commit()
        with self.assertRaisesRegex(db.RecoveryError, "Unsafe"):
            f.verified_manifest(self.dump)
        self.make_tar(symlink=True)
        self.commit()
        with self.assertRaisesRegex(db.RecoveryError, "Unsafe/non-file"):
            f.verified_manifest(self.dump)
        self.make_tar()
        self.record["blobs"] = []
        self.record["restored_inspection"]["evidence_db_references"]["sha256"] = []
        self.record["restored_inspection"]["evidence_db_references"]["blob_count"] = 0
        self.commit()
        with self.assertRaisesRegex(db.RecoveryError, "Unreferenced"):
            f.verified_manifest(self.dump)

    def test_full_restore_failure_is_recorded_and_not_reported_as_success(self):
        with patch.object(f, "disposable_restore", side_effect=db.RecoveryError("restore corrupted")):
            report = f.full_drill(self.dump)
        self.assertEqual(report["status"], "failed")
        self.assertIn("restore corrupted", report["error"])
        self.assertTrue(Path(report["report_path"]).exists())
        with patch.object(f, "disposable_restore", return_value={
            "inspection": INSPECTION, "blobs": BLOBS, "api_download": "passed"}):
            report = f.full_drill(self.dump)
        self.assertEqual(report["status"], "passed")

    def test_independent_destination_rejects_absent_and_ci_bypass_outside_runner(self):
        args = SimpleNamespace(destination=str(self.root / "unmounted"),
                               allow_local_ci=False, require_external=True, keep=14)
        with self.assertRaisesRegex(db.RecoveryError, "unavailable"):
            f.full_backup(args)
        args.destination = str(self.root)
        args.allow_local_ci = True
        with patch.dict(os.environ, {"GITHUB_ACTIONS": ""}):
            with self.assertRaisesRegex(db.RecoveryError, "CI"):
                f.full_backup(args)

    def test_capture_restarts_api_on_archive_failure(self):
        commands = []
        def command(args, **kwargs):
            commands.append(args)
            return "ok"
        with patch.object(db, "run", side_effect=command), \
             patch.object(f, "_capture", side_effect=db.RecoveryError("blob failed")):
            with self.assertRaisesRegex(db.RecoveryError, "blob failed"):
                f.capture_db_and_evidence(self.root / "partial.dump",
                                          self.root / "partial.tar")
        self.assertTrue(any(x[-2:] == ["start", "api"] for x in commands))
        self.assertTrue(any(x[-4:] == ["stop", "-t", "30", "api"] for x in commands))

    def test_status_refuses_outdated_recovery_point(self):
        with patch.object(f, "full_entries", return_value=[(self.record, self.dump)]):
            d = f.full_status(self.root, fresh_hours=1)
        self.assertEqual(d["status"], "stale")
        self.assertEqual(d["verified_count"], 1)
        self.assertEqual(d["scope"], "postgresql+immutable-evidence")
        self.assertIsNone(d["last_successful_restore"])


if __name__ == "__main__":
    unittest.main()
