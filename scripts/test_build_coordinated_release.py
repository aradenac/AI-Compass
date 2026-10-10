"""FUT-01: fully offline positive/negative coordinated release tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_coordinated_release as release

COMMIT = "a" * 40
IMAGE = "sha256:" + "b" * 64
REPO = "engineering/ai-compass"
RUN = "12345"


class CoordinatedReleaseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "source"
        self.root.mkdir()
        self.out = Path(tmp.name) / "artifacts"
        self.root.joinpath("release").mkdir()
        (self.root / "release/versions.json").write_text(json.dumps({
            "schema": release.VERSION_SCHEMA, "release": "0.1.0",
            "frontend": "0.1.0", "backend": "0.1.0",
            "api_major": 1, "api_min_major": 1, "api_max_major": 1
        }))
        (self.root / "backend/config").mkdir(parents=True)
        (self.root / "backend/Dockerfile").write_text("FROM python:3.12-slim\n")
        (self.root / "backend/requirements.txt").write_text("Django==5.2.18\n")
        (self.root / "backend/config/release_contract.py").write_text(
            "API_MAJOR = 1\nAPI_MIN_MAJOR = 1\nAPI_MAX_MAJOR = 1\n")
        assets = ["prototype.html", "server-mode.js", "model-catalog.js"] + [
            "server-module-%s.js" % n for n in range(15)]
        for name in assets:
            (self.root / name).write_text("/*%s*/\n" % name)
        (self.root / "compose.yaml").write_text(
            "services:\n  web:\n    volumes:\n" +
            "".join("      - ./%s:/srv/frontend/%s:ro\n" % (n, n) for n in assets))
        self.packages = Path(tmp.name) / "packages.txt"
        self.packages.write_text("Django==5.2.18\npsycopg==3.2.12\n")
        self.evidence = Path(tmp.name) / "report.json"
        self.report = {
            "schema": "ai-compass/release-acceptance@1",
            "source": {"commit": COMMIT, "repository": REPO,
                       "workflow_run": "https://github.com/%s/actions/runs/%s" % (REPO, RUN)},
            "automated": {
                "status": "passed",
                "checks": {"check%d" % n: {"status": "passed"} for n in range(10)},
                "recovery": {"drill_report_sha256": "c" * 64,
                             "authenticated_original_download": "passed"},
                "staging_rejections": {"migration_key": "model-v1-to-v2@1"},
            },
            "manual_release_gates": {
                "real_browser_staging_inspection_and_signed_acceptance": "not_evidenced",
                "accepted_candidate_production_replay_with_new_recovery_point": "not_evidenced",
                "operator_release_signoff": "not_evidenced",
            },
            "decision": "NO_GO"
        }
        self.save()

    def save(self):
        self.evidence.write_text(json.dumps(self.report))

    def build(self, image=IMAGE):
        return release.build(self.root, self.out, self.evidence, COMMIT,
                             REPO, RUN, image, self.packages)

    def test_deterministic_reproducible_artifacts_and_verification(self):
        m1 = self.build()
        b1 = (self.out / "frontend.zip").read_bytes()
        j1 = (self.out / "manifest.json").read_bytes()
        m2 = self.build()
        self.assertEqual(m1, m2)
        self.assertEqual(b1, (self.out / "frontend.zip").read_bytes())
        self.assertEqual(j1, (self.out / "manifest.json").read_bytes())
        self.assertEqual(m1["decision"], "NO_GO")
        self.assertEqual(m1["components"]["backend"]["image_id"], IMAGE)
        self.assertEqual(release.verify(self.root, self.out)["release_id"], "r0.1.0+" + COMMIT[:12])

    def test_acceptance_evidence_required_and_exact_commit(self):
        self.report["source"]["commit"] = "f" * 40
        self.save()
        with self.assertRaisesRegex(release.ReleaseError, "different commit"):
            self.build()
        self.report["source"]["commit"] = COMMIT
        self.report["automated"]["checks"]["check1"]["status"] = "skipped"
        self.save()
        with self.assertRaisesRegex(release.ReleaseError, "Missing/failed"):
            self.build()

    def test_manual_go_claim_refused_and_image_must_be_digest(self):
        with self.assertRaisesRegex(release.ReleaseError, "content-addressed"):
            self.build("ai-compass:latest")
        self.report["decision"] = "GO"
        self.save()
        with self.assertRaisesRegex(release.ReleaseError, "Do not fabricate"):
            self.build()

    def test_tampered_bundle_missing_manifest_and_backend_drift_fail_closed(self):
        self.build()
        (self.out / "frontend.zip").write_bytes(b"tampered")
        with self.assertRaisesRegex(release.ReleaseError, "bundle was modified"):
            release.verify(self.root, self.out)
        self.build()
        (self.root / "backend/config/release_contract.py").write_text(
            "API_MAJOR = 99\nAPI_MIN_MAJOR = 1\nAPI_MAX_MAJOR = 1\n")
        with self.assertRaisesRegex(release.ReleaseError, "Backend source drift"):
            release.verify(self.root, self.out)
        (self.out / "manifest.json").unlink()
        with self.assertRaisesRegex(release.ReleaseError, "Missing/unsafe"):
            release.verify(self.root, self.out)

    def test_no_unrecorded_client_files(self):
        (self.root / "server-unknown.js").write_text("new feature\n")
        self.build()
        self.assertNotIn("server-unknown.js", self.build()["components"]["frontend"]["files"])
        # FUT-01 makes compose mounts the explicit deployment source: once
        # deployed, the new source must appear in the tested bundle.
        with (self.root / "compose.yaml").open("a") as f:
            f.write("      - ./server-unknown.js:/srv/frontend/server-unknown.js:ro\n")
        with self.assertRaisesRegex(release.ReleaseError, "Frontend sources"):
            release.verify(self.root, self.out)


if __name__ == "__main__":
    unittest.main()
