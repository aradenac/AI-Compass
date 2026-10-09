#!/usr/bin/env python3
"""PLAT-26 offline tests: no Docker, operational recovery point or production mutation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import migration_promote as promote
import migration_stage as stage
import recovery as db


class PromotionHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        state = patch.object(promote, "PROMOTION_ROOT", self.root / "promotions")
        state.start()
        self.addCleanup(state.stop)
        p = patch.object(stage, "STATE_ROOT", self.root / "staging")
        p.start()
        self.addCleanup(p.stop)

    def fixture(self):
        cid = "0123456789abcdef"
        folder = stage.candidate_dir(cid)
        folder.mkdir(parents=True)
        artifact_hash = db.hash_file(stage.MIGRATION_FILE)
        report = {
            "candidate_id": cid, "project": stage.project_for(cid),
            "status":"accepted",
            "automated_checks":"passed",
            "migrated":{"status":"passed","changed":1},
            "migration":stage.MIGRATION, "migration_sha256":artifact_hash,
            "application_commit":"a"*40,
            "snapshot":str(self.root / "ai-compass-20261010T010101Z-012345abcdef.dump"),
            "snapshot_id":"20261010T010101Z-012345abcdef",
            "snapshot_manifest_sha256":"c"*64,
            "source_schema_versions":["model:1","model:2"],
        }
        verdict = {
            "candidate_id":cid,"decision":"accepted",
            "notes":"Inspected old and migrated historical revisions",
            "frontend_checked":True, "migration":stage.MIGRATION,
            "migration_sha256":artifact_hash,
            "application_commit":"a"*40,
            "snapshot_id":report["snapshot_id"],
            "snapshot_manifest_sha256":report["snapshot_manifest_sha256"],
        }
        report["verdict"] = verdict
        (folder / "report.json").write_text(json.dumps(report))
        (folder / "verdict.json").write_text(json.dumps(verdict))
        return cid, folder, report, verdict

    def test_refuses_missing_manual_acceptance_and_modified_reports(self):
        cid, folder, report, verdict = self.fixture()
        with patch.object(stage, "build_identity", return_value="a"*40), \
             patch.object(stage, "snapshot_for", return_value=(Path(report["snapshot"]), {
                 "backup_id":report["snapshot_id"],"restored_inspection":{
                     "schema_versions":report["source_schema_versions"]}})), \
             patch.object(promote, "file_sha", side_effect=lambda p:
                 report["snapshot_manifest_sha256"] if str(p).endswith(".full.json")
                 else db.hash_file(p)):
            checked, _, _ = promote.approval(cid)
            self.assertEqual(checked["candidate_id"], cid)
            report["status"] = "rejected"
            (folder / "report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(db.RecoveryError, "accepted"):
                promote.approval(cid)
            report["status"] = "accepted"
            report["migration_sha256"] = "0"*64
            (folder / "report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(db.RecoveryError, "mismatch"):
                promote.approval(cid)
            report["migration_sha256"] = verdict["migration_sha256"]
            verdict["frontend_checked"] = False
            (folder / "verdict.json").write_text(json.dumps(verdict))
            (folder / "report.json").write_text(json.dumps(report))
            with self.assertRaisesRegex(db.RecoveryError, "frontend"):
                promote.approval(cid)

    def test_no_production_stop_or_backup_on_missing_confirmation(self):
        cid, folder, report, verdict = self.fixture()
        with patch.object(promote, "approval") as approved, \
             patch.object(promote, "docker_cmd") as docker, \
             patch.object(promote.full, "full_backup") as backup:
            with self.assertRaisesRegex(db.RecoveryError, "confirm-candidate"):
                promote.apply(cid, "operator", "wrong", str(self.root))
            approved.assert_not_called()
            backup.assert_not_called()
            docker.assert_not_called()

    def test_preview_is_read_only_and_uses_pinned_prod_compose(self):
        cid, folder, report, verdict = self.fixture()
        with patch.object(promote, "approval", return_value=(report, verdict, "v"*64)), \
             patch.object(promote, "backend_preview", return_value={
                  "pending_count":2,"blocked_count":0}) as preview:
            result = promote.preview(cid, "maintainer")
        self.assertEqual(result["status"], "preview")
        self.assertEqual(result["production"]["pending_count"], 2)
        preview.assert_called_once_with("maintainer")

    def test_apply_blocks_ambiguous_preview_before_backup(self):
        cid, folder, report, verdict = self.fixture()
        with patch.object(promote, "approval", return_value=(report, verdict, "v"*64)), \
             patch.object(promote, "backend_preview", return_value={
                 "pending_count":1,"blocked_count":1}), \
             patch.object(promote.full, "full_backup") as backup:
            with self.assertRaisesRegex(db.RecoveryError, "Ambiguous"):
                promote.apply(cid, "maintainer", cid, str(self.root))
            backup.assert_not_called()

    def test_resume_reuses_first_signed_backup_without_recapturing_mutated_state(self):
        cid, folder, report, verdict = self.fixture()
        saved = promote.proof_path(cid)
        saved.write_text(json.dumps({"proof":{"candidate_id":cid,"recovery_id":"original-point"}, "signature":"saved"}))
        saved.with_suffix(".recovery").write_text("/unused/original.dump\n")
        calls = []
        def docker(argv, **kwargs):
            calls.append(argv)
            if "promote_model_schema" in argv:
                return json.dumps({"candidate_id":cid,"changed":0,"remaining":0})
            return ""
        with patch.object(promote, "approval", return_value=(report, verdict, "hash")), \
             patch.object(promote, "signed_recovery", return_value={
                 "backup_id":"original-point"}) as verified, \
             patch.object(promote, "backend_preview") as preview, \
             patch.object(promote.full, "full_backup") as backup, \
             patch.object(promote, "docker_cmd", side_effect=docker):
            result = promote.apply(cid, "maintainer", cid, str(self.root))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["batches"], 1)
        verified.assert_called_once()
        preview.assert_not_called()
        backup.assert_not_called()
        self.assertEqual(calls[0], ["stop","api"])
        self.assertEqual(calls[-1], ["start","api"])

    def test_proof_binds_fresh_recovery_and_operator_without_logging_secret(self):
        cid, folder, report, verdict = self.fixture()
        snapshot = {"backup_id":"backup1234","_dump_path":str(self.root/"snapshot.dump"),
            "restored_inspection":{
                "item_count":1,"revision_count":1,"revision_digest":"x",
                "hrid_digest":"y","audit_count":0,"schema_versions":["model:1","model:2"],
                "schema_hashes":[],"evidence_db_references":{
                    "blob_count":0,"link_count":0,"sha256":[]},
            }}
        with patch.object(promote, "file_sha", return_value="a"*64), \
             patch.object(promote, "production_secret", return_value="very-secret-test-only"):
            envelope = promote.prepare_proof(report, "b"*64, "maintainer",snapshot)
        self.assertEqual(envelope["proof"]["candidate_id"], cid)
        self.assertEqual(envelope["proof"]["recovery_id"], "backup1234")
        self.assertEqual(envelope["proof"]["operator"], "maintainer")
        self.assertEqual(len(envelope["signature"]), 64)
        self.assertNotIn("very-secret", json.dumps(envelope))


if __name__ == "__main__":
    unittest.main()
