"""PLAT-32: release decision never implies an unperformed human acceptance."""
import json
from pathlib import Path
import tempfile
import unittest

import release_acceptance as release

COMMIT = "a" * 40
RUN = "123456"
REPO = "engineering/compass"
ENV = {"CI": "true", "GITHUB_ACTIONS": "true", "GITHUB_SHA": COMMIT,
       "GITHUB_RUN_ID": RUN, "GITHUB_REPOSITORY": REPO}
RECOVERY = "b" * 64
ORIGINAL = "c" * 64


class ReleaseAcceptanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.write("full-restore-report.json", {
            "status": "passed",
            "restored": {"api_download": "passed", "inspection": {
                "item_count": 10, "revision_count": 16,
                "evidence_db_references": {"link_count": 2, "sha256": [ORIGINAL]}}}})
        self.write("full-status.json", {
            "status": "ok", "last_successful_restore": {"status": "passed"}})
        for n in (1, 2, 3):
            self.write("stage%d.json" % n, {
                "candidate_id": "%016x" % n, "automated_checks": "passed",
                "migrated": {"changed": 1}, "migration": "model-v1-to-v2@1",
                "migration_sha256": "d" * 64,
                "snapshot_id": "20261010T120000Z-source",
                "snapshot_manifest_sha256": RECOVERY,
                "status": "awaiting-frontend-review",
            })

    def write(self, name, payload):
        (self.root / name).write_text(json.dumps(payload))

    def collect(self, environ=None):
        return release.collect(self.root, COMMIT, RUN, REPO,
                               ci_environment=ENV if environ is None else environ)

    def test_automatic_success_never_claims_manual_or_production_go(self):
        dossier = self.collect()
        self.assertEqual(dossier["decision"], "NO_GO")
        self.assertEqual(len(dossier["automated"]["checks"]), len(release.REQUIRED_STEPS))
        self.assertTrue(all(c["status"] == "passed" for c in
                            dossier["automated"]["checks"].values()))
        self.assertEqual(dossier["automated"]["recovery"]["original_evidence_sha256"],
                         [ORIGINAL])
        self.assertEqual(dossier["automated"]["staging_rejections"]["recovery_id"],
                         "20261010T120000Z-source")
        self.assertFalse(dossier["automated"]["staging_rejections"]["manual_frontend_accepted"])
        self.assertEqual({b["issue"] for b in dossier["blockers"]}, {26, 32, 35})
        narrative = release.render_markdown(dossier)
        self.assertIn("**Decision: NO-GO**", narrative)
        self.assertIn("independently verified recovery point", narrative)
        self.assertNotIn("**Decision: GO**", narrative)

    def test_run_cannot_be_forged_outside_ci(self):
        for key, value in (("GITHUB_ACTIONS", "false"), ("CI", "false"),
                           ("GITHUB_SHA", "b" * 40),
                           ("GITHUB_RUN_ID", "different"),
                           ("GITHUB_REPOSITORY", "other/project")):
            with self.subTest(key=key):
                invalid = dict(ENV, **{key: value})
                with self.assertRaises(release.AcceptanceError):
                    self.collect(invalid)

    def test_missing_or_corrupted_evidence_never_passes(self):
        (self.root / "stage2.json").unlink()
        with self.assertRaisesRegex(release.AcceptanceError, "Missing"):
            self.collect()
        self.write("stage2.json", {
            "candidate_id": "%016x" % 2, "automated_checks": "failed",
            "migrated": {"changed": 1}, "migration": "model-v1-to-v2@1",
            "snapshot_id": "20261010T120000Z-source",
            "snapshot_manifest_sha256": RECOVERY,
        })
        with self.assertRaisesRegex(release.AcceptanceError, "Staging"):
            self.collect()

    def test_recreate_must_be_distinct_and_same_source(self):
        s2 = json.loads((self.root / "stage2.json").read_text())
        s2["candidate_id"] = "%016x" % 1
        self.write("stage2.json", s2)
        with self.assertRaisesRegex(release.AcceptanceError, "reused"):
            self.collect()
        s2["candidate_id"] = "%016x" % 2
        s2["snapshot_manifest_sha256"] = "e" * 64
        self.write("stage2.json", s2)
        with self.assertRaisesRegex(release.AcceptanceError, "same original"):
            self.collect()

    def test_invalid_or_missing_db_blob_evidence_blocks(self):
        r = json.loads((self.root / "full-restore-report.json").read_text())
        r["restored"]["inspection"]["evidence_db_references"]["sha256"] = []
        self.write("full-restore-report.json", r)
        with self.assertRaisesRegex(release.AcceptanceError, "original bytes"):
            self.collect()


if __name__ == "__main__":
    unittest.main()
