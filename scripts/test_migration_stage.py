#!/usr/bin/env python3
"""PLAT-35 offline safety tests: no live Docker instance or backup data needed."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import migration_stage as s
import recovery as db


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        patcher = patch.object(s, "STATE_ROOT", self.base / ".local" / "staging")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_candidate_whitelist_never_allows_production(self):
        for name in ("ai-compass", "main", "../ai-compass", "x" * 16, "0000000000000000/../"):
            with self.assertRaises(db.RecoveryError):
                s.candidate_dir(name)
        self.assertEqual(s.project_for("0123456789abcdef"), "ai-compass-stage-0123456789abcdef")
        with self.assertRaisesRegex(db.RecoveryError, "non-production"):
            s.staging_environment(self.base, "0123456789abcdef", 8080)

    def test_compose_target_has_pinned_file_project_and_own_env(self):
        folder = s.candidate_dir("0123456789abcdef")
        folder.mkdir(parents=True)
        with patch.object(s, "command", return_value="ok") as invoke:
            self.assertEqual(s.compose(folder, ["ps", "-q", "db"]), "ok")
        argv = invoke.call_args.args[0]
        self.assertEqual(argv[0:2], ["docker", "compose"])
        self.assertEqual(argv[argv.index("-p") + 1], "ai-compass-stage-0123456789abcdef")
        self.assertEqual(argv[argv.index("--env-file") + 1], str(folder / "runtime.env"))
        self.assertEqual(argv[argv.index("-f") + 1], str(s.COMPOSE_FILE))
        self.assertNotIn("ai-compass", argv)

    def test_unknown_volume_owner_refused_before_delete(self):
        with patch.object(s, "docker_volume_label", side_effect=["ai-compass", None]):
            with self.assertRaisesRegex(db.RecoveryError, "not owned"):
                s.assert_owned("0123456789abcdef")
        with patch.object(s, "docker_volume_label", side_effect=[None, None]):
            s.assert_owned("0123456789abcdef", absent=True)

    def test_append_only_checks_detect_identity_history_and_count_loss(self):
        before = {"item_count": 1, "model_count": 1, "schema_versions": ["model:1", "model:2"],
                  "schema_hashes": ["h"], "hrid_digest": "stable",
                  "evidence_db_references": {"blob_count": 1, "sha256": ["hash"], "link_count": 2},
                  "revision_count": 1, "audit_count": 1,
                  "invalid_ids": 0, "invalid_revision_links": 0, "orphan_revisions": 0}
        after = {**before, "revision_count": 2, "audit_count": 2}
        old = {"identities": [["uuid", "mdl-simple-tree-lake", "model"]],
               "history": [["rev-original", "digest"]]}
        new = copy.deepcopy(old)
        new["history"].append(["rev-new", "another"])
        s.check_migrated(before, after, old, new, {"status": "passed", "changed": 1})
        bad = copy.deepcopy(new)
        bad["history"][0][1] = "tampered"
        with self.assertRaisesRegex(db.RecoveryError, "historical"):
            s.check_migrated(before, after, old, bad, {"status": "passed", "changed": 1})
        tampered = {**after, "evidence_db_references": {"blob_count": 0}}
        with self.assertRaisesRegex(db.RecoveryError, "evidence"):
            s.check_migrated(before, tampered, old, new, {"status": "passed", "changed": 1})
        with self.assertRaisesRegex(db.RecoveryError, "delta"):
            s.check_migrated(before, before, old, new, {"status": "passed", "changed": 1})

    def fixture(self):
        candidate = "0123456789abcdef"
        folder = s.candidate_dir(candidate)
        folder.mkdir(parents=True)
        (folder / "runtime.env").write_text("STAGING_DB_PASSWORD=unique\n")
        manifest = self.base / "ai-compass-20261009T220000Z-012345abcdef.dump.full.json"
        manifest.write_text('{"status":"verified"}')
        source = self.base / "ai-compass-20261009T220000Z-012345abcdef.dump"
        source.write_bytes(b"PGDMP")
        report = {"candidate_id": candidate, "project": s.project_for(candidate),
                  "migration": s.MIGRATION, "migration_sha256": db.hash_file(s.MIGRATION_FILE),
                  "runtime_sha256": db.hash_file(folder / "runtime.env"),
                  "status": "awaiting-frontend-review",
                  "application_commit": "f" * 40, "snapshot": str(source),
                  "snapshot_id": "20261009T220000Z-012345abcdef",
                  "snapshot_manifest_sha256": db.hash_file(manifest),
                  "port": 18081, "verdict": None,
                  "url": "http://127.0.0.1:18081/?mode=server",
                  "baseline_inspection": {"evidence_db_references": {"link_count": 0}},
                  "automated_checks": "passed",
                  "migrated": {"status": "passed", "changed": 1,
                               "public_ids": ["mdl-verified-blue-beacon"]}}
        s.save_report(folder, report)
        return candidate, folder, report

    def test_verdict_coupled_to_exact_candidate_and_frontend(self):
        cid, folder, report = self.fixture()
        with self.assertRaisesRegex(db.RecoveryError, "frontend"):
            s.verdict(cid, "accepted", "reviewed old/new records")
        with self.assertRaisesRegex(db.RecoveryError, "review"):
            s.verdict(cid, "accepted", "Flag alone must not pass", True)
        template = s.review_template(cid)
        self.assertFalse(template["checks"]["new_model_v2_revision_visible"])
        self.assertEqual(template["record_id"], "mdl-verified-blue-beacon")
        template["reviewer"] = "Staging QA reviewer"
        template["reviewed_at"] = "2026-10-10T12:00:00+00:00"
        for name in s.REVIEW_CHECKS:
            if template["checks"][name] is not None:
                template["checks"][name] = True
            template["observations"][name] = (
                "Inspected real staging page and compared the original source record"
                if template["checks"][name] is not None else
                "No source evidence links exist in the verified snapshot")
        review_file = folder / "browser-observations.json"
        review_file.write_text(json.dumps(template), encoding="utf-8")
        with patch.object(s, "build_identity", return_value="f" * 40), \
             patch.object(s, "snapshot_for", return_value=(Path(report["snapshot"]),
                                                              {"backup_id": report["snapshot_id"]})):
            saved = s.verdict(cid, "accepted", "Old and new revision inspected", True, str(review_file))
            self.assertEqual(saved["verdict"]["snapshot_manifest_sha256"],
                             report["snapshot_manifest_sha256"])
            self.assertTrue((folder / "verdict.json").exists())
            self.assertEqual(saved["verdict"]["review_sha256"], db.hash_file(folder / "review.json"))
            self.assertEqual(json.loads((folder / "review.json").read_text()), template)
            with self.assertRaises(db.RecoveryError):
                s.verdict(cid, "rejected", "changed my mind")

    def test_manual_review_missing_checks_foreign_candidate_and_time_refused(self):
        cid, folder, report = self.fixture()
        sample = s.review_template_for(report)
        sample["reviewer"] = "Human reviewer"
        sample["reviewed_at"] = "2026-10-10T12:00:00+00:00"
        for key in s.REVIEW_CHECKS:
            if sample["checks"][key] is not None:
                sample["checks"][key] = True
            sample["observations"][key] = "Reviewed old and new Server frontend model revisions"
        path = folder / "candidate-review.json"
        def check(doc):
            path.write_text(json.dumps(doc), encoding="utf-8")
            return s.verify_manual_review(cid, path, report)
        review, data = check(sample)
        self.assertEqual(review["candidate_id"], cid)
        corrupt = copy.deepcopy(sample)
        corrupt["candidate_id"] = "fedcba9876543210"
        with self.assertRaisesRegex(db.RecoveryError, "candidate"):
            check(corrupt)
        corrupt = copy.deepcopy(sample)
        corrupt["checks"]["new_model_v2_revision_visible"] = False
        with self.assertRaisesRegex(db.RecoveryError, "Incomplete"):
            check(corrupt)
        corrupt = copy.deepcopy(sample)
        corrupt["observations"]["original_model_v1_revision_visible"] = "ok"
        with self.assertRaisesRegex(db.RecoveryError, "Specific"):
            check(corrupt)
        corrupt = copy.deepcopy(sample)
        corrupt["reviewed_at"] = "2099-01-01T00:00:00Z"
        with self.assertRaisesRegex(db.RecoveryError, "future"):
            check(corrupt)
        corrupt = copy.deepcopy(sample)
        corrupt["reviewer"] = ""
        with self.assertRaisesRegex(db.RecoveryError, "named"):
            check(corrupt)
        report["baseline_inspection"]["evidence_db_references"]["link_count"] = 2
        with self.assertRaisesRegex(db.RecoveryError, "candidate"):
            check(sample)
        new = s.review_template_for(report)
        self.assertFalse(new["checks"]["original_linked_evidence_download_verified"])

    def test_unmigrated_stage_cannot_be_accepted(self):
        cid, _, report = self.fixture()
        report["migrated"] = {"status": "passed", "changed": 0, "public_ids": []}
        with self.assertRaisesRegex(db.RecoveryError, "No verified migrated"):
            s.review_template_for(report)

    def test_discard_preserves_report_and_never_calls_production_compose(self):
        cid, folder, report = self.fixture()
        with patch.object(s, "assert_owned") as ownership, \
             patch.object(s, "compose", return_value="") as actions, \
             patch.object(s, "docker_volume_label", return_value=s.project_for(cid)), \
             patch.object(s, "command", return_value=""):
            result = s.discard(cid)
        self.assertEqual(actions.call_args.args[0], folder)
        self.assertEqual(actions.call_args.args[1], ["down", "--remove-orphans"])
        self.assertEqual(result["status"], "discarded")
        self.assertEqual(result["snapshot"], report["snapshot"])
        self.assertTrue((folder / "report.json").is_file())
        self.assertFalse((folder / "runtime.env").exists())
        self.assertEqual(ownership.call_args.kwargs, {"absent": True})

    def test_recreate_uses_identical_source_but_new_attempt(self):
        cid, folder, report = self.fixture()
        with patch.object(s, "discard", return_value={}) as remove, \
             patch.object(s, "create", return_value={"candidate_id": "fedcba9876543210"}) as start:
            result = s.recreate(cid)
        remove.assert_called_once_with(cid)
        start.assert_called_once_with(report["snapshot"], port=report["port"])
        self.assertNotEqual(result["candidate_id"], cid)


if __name__ == "__main__":
    unittest.main()
