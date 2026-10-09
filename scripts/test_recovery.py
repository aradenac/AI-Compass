#!/usr/bin/env python3
"""Deterministic PLAT-34 unit tests; never require Docker or production access."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("recovery", Path(__file__).with_name("recovery.py"))
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


INSPECTION = {
    "model_count": 1, "item_count": 1, "revision_count": 2, "audit_count": 2,
    "schema_versions": ["model:1"], "migration_count": 1, "hrid_digest": "test-hrids",
    "revision_digest": "test-revisions", "invalid_ids": 0, "invalid_revision_links": 0,
    "orphan_revisions": 0, "smoke_marker": "persistence-check"
}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "backups"
        self.directory.mkdir()
        self.args = SimpleNamespace(destination=str(self.directory), require_external=False, keep=14)
        self.fake_run = lambda *args, **kwargs: "f463ab3"

    def fake_dump(self, command, stream):
        self.assertIn("pg_dump", command[-1])
        stream.write(b"PGDMP" + b"\0" * 512 + b"known-safe-snapshot")

    def make_backup(self, *, inspection=None):
        with patch.object(recovery, "database_metadata", return_value=("ai_compass", "17.0")), \
             patch.object(recovery, "subprocess_run_dump", side_effect=self.fake_dump), \
             patch.object(recovery, "run", side_effect=self.fake_run), \
             patch.object(recovery, "restore_isolated", return_value=inspection or dict(INSPECTION)):
            return recovery.backup(self.args)

    def test_atomic_snapshot_manifest_checksum_last_good_and_retention(self):
        first = self.make_backup()
        manifest = recovery.verify(first)
        self.assertEqual(manifest["status"], "verified")
        self.assertEqual(manifest["schema_versions"], ["model:1"])
        self.assertEqual(manifest["restored_inspection"]["revision_count"], 2)
        self.assertFalse(manifest["evidence"]["included"], "future evidence generation is not covered")
        self.assertEqual(recovery.status(self.directory)["verified_count"], 1)
        second = self.make_backup()
        self.assertNotEqual(first, second)
        self.args.keep = 1
        third = self.make_backup()
        self.assertFalse(first.exists())
        self.assertFalse(second.exists())
        self.assertTrue(third.exists())
        self.assertEqual(recovery.status(self.directory)["verified_count"], 1)

    def test_corrupt_dump_and_tampered_metadata_fail_offline(self):
        dump = self.make_backup()
        data = bytearray(dump.read_bytes())
        data[32] ^= 1
        dump.write_bytes(data)
        with self.assertRaisesRegex(recovery.RecoveryError, "checksum"):
            recovery.verify(dump)
        self.assertEqual(recovery.status(self.directory)["status"], "no-verified-recovery-point")
        manifest = json.loads(Path(str(dump) + ".json").read_text())
        self.assertEqual(manifest["status"], "verified", "the failed verification is not a success")
        dump.unlink()
        with self.assertRaisesRegex(recovery.RecoveryError, "Incomplete"):
            recovery.verify(dump)

    def test_partial_or_failed_dump_is_never_a_successful_backup(self):
        original = self.make_backup()
        with patch.object(recovery, "database_metadata", return_value=("ai_compass", "17.0")), \
             patch.object(recovery, "subprocess_run_dump", side_effect=self.fake_dump), \
             patch.object(recovery, "run", side_effect=recovery.RecoveryError("invalid pg_restore archive")):
            with self.assertRaisesRegex(recovery.RecoveryError, "checking-archive"):
                recovery.backup(self.args)
        self.assertEqual(recovery.status(self.directory)["verified_count"], 1)
        self.assertEqual(recovery.status(self.directory)["failed_backup_count"], 1)
        self.assertTrue(original.exists())
        self.assertFalse(list(self.directory.glob(".*.partial")))
        self.assertEqual(len(list(self.directory.glob("*.complete"))), 1)

    def test_missing_external_destination_and_wrong_filesystem_fail_safely(self):
        self.args.destination = str(self.directory / "disconnected-mount")
        with self.assertRaisesRegex(recovery.RecoveryError, "unavailable"):
            recovery.destinations(self.args, for_backup=True)
        self.args.destination = str(self.directory)
        self.args.require_external = True
        with self.assertRaisesRegex(recovery.RecoveryError, "same filesystem"):
            recovery.destinations(self.args, for_backup=True)

    def test_wrong_target_is_not_a_supported_restore_parameter(self):
        import subprocess
        result = subprocess.run(
            ["python3", str(Path(__file__).with_name("recovery.py")),
             "drill", str(self.directory / "missing.dump"), "--target-db", "ai_compass"],
            capture_output=True, text=True
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unrecognized arguments", result.stderr)

    def test_drill_recreates_expected_inspection_and_records_failure(self):
        dump = self.make_backup()
        with patch.object(recovery, "restore_isolated", return_value=dict(INSPECTION)):
            result = recovery.drill(dump)
        self.assertEqual(result["status"], "passed")
        self.assertTrue(Path(result["report_path"]).exists())
        altered = dict(INSPECTION, revision_count=3)
        with patch.object(recovery, "restore_isolated", return_value=altered):
            failure = recovery.drill(dump)
        self.assertEqual(failure["status"], "failed")
        self.assertIn("fingerprint", failure["error"])
        self.assertTrue(dump.exists())
        self.assertEqual(recovery.verify(dump)["restored_inspection"], INSPECTION)

    def test_isolated_restore_does_not_mount_or_connect_to_prod(self):
        dump = self.make_backup()
        issued = []
        def fake_command(args, **kwargs):
            issued.append(args)
            return "ok"
        with patch.object(recovery, "run", side_effect=fake_command), \
             patch.object(recovery, "inspect_restored", return_value=dict(INSPECTION)):
            result = recovery.restore_isolated(dump)
        self.assertEqual(result["revision_count"], 2)
        container = issued[0]
        self.assertEqual(container[:3], ["docker", "run", "--rm"])
        self.assertIn("--network", container)
        self.assertEqual(container[container.index("--network") + 1], "none")
        self.assertNotIn("-v", container)
        self.assertNotIn("--mount", container)
        self.assertNotIn("-p", container)
        self.assertNotIn("ai_compass", " ".join(x for x in container if x.startswith("POSTGRES_PASSWORD=")))
        self.assertTrue(any(cmd[0:3] == ["docker", "rm", "--force"] for cmd in issued))
        self.assertTrue(any(cmd[:3] == ["docker", "exec", "-i"] for cmd in issued))

    def test_individual_schema_sha256_uses_restored_bytes(self):
        import hashlib
        schema = {"type": "object", "properties": {
            "context_window": {"minimum": 1, "type": "integer"}}}
        raw = dict(INSPECTION, schema_definitions=[
            {"type": "model", "version": 1, "schema": schema}
        ])
        def fake_run(args, **kwargs):
            if "SELECT to_regclass" in args[-1]:
                return "f"
            return json.dumps(raw)
        with patch.object(recovery, "run", side_effect=fake_run):
            result = recovery.inspect_restored("isolated-only")
        expected = hashlib.sha256(json.dumps(
            schema, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()).hexdigest()
        self.assertEqual(result["schema_hashes"], [
            {"type": "model", "version": 1, "sha256": expected}
        ])
        self.assertNotIn("schema_definitions", result)
        # Field order in JSON schema must not alter the digest.
        self.assertEqual(expected, hashlib.sha256(json.dumps(
            {"properties": schema["properties"], "type": "object"},
            sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()).hexdigest())

    def test_recovery_verifier_failure_also_disposes_separate_postgres(self):
        dump = self.make_backup()
        issued = []
        def fake_command(args, **kwargs):
            issued.append(args)
            return "ok"
        def fail_verification(container, inspection):
            raise AssertionError("Historical v1 Model does not match")
        with patch.object(recovery, "run", side_effect=fake_command), \
             patch.object(recovery, "inspect_restored", return_value=dict(INSPECTION)):
            with self.assertRaisesRegex(AssertionError, "does not match"):
                recovery.restore_isolated(dump, verifier=fail_verification)
        self.assertTrue(any(cmd[:3] == ["docker", "rm", "--force"] for cmd in issued))
        self.assertNotIn("-v", issued[0])
        self.assertEqual(issued[0][issued[0].index("--network") + 1], "none")

    def test_real_domain_drill_refuses_manual_or_production_invocation(self):
        import subprocess
        import os
        environment = dict(os.environ)
        environment.pop("AI_COMPASS_ISOLATED_FIXTURE_CI", None)
        result = subprocess.run(
            ["python3", str(Path(__file__).with_name("smoke_recovery_domain.py"))],
            env=environment, text=True, capture_output=True, check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CI-only", result.stderr)

    def test_restore_failure_still_force_removes_disposable_container(self):
        dump = self.make_backup()
        issued = []
        def fail_restore(args, **kwargs):
            issued.append(args)
            if "pg_restore" in args:
                raise recovery.RecoveryError("malformed dump")
            return "ok"
        with patch.object(recovery, "run", side_effect=fail_restore):
            with self.assertRaisesRegex(recovery.RecoveryError, "malformed dump"):
                recovery.restore_isolated(dump)
        self.assertTrue(any(cmd[:3] == ["docker", "rm", "--force"] for cmd in issued))


if __name__ == "__main__":
    unittest.main()
