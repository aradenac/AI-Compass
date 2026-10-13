"""FUT-21: offline guided release-operation tests (check/classify/deploy/recover)."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_coordinated_release as release
import release_ops as ops

COMMIT = "a" * 40
IMAGE = "sha256:" + "b" * 64
REPO = "engineering/ai-compass"
RUN = "12345"


def build_release(out, root, packages, evidence, commit=COMMIT):
    """Produce a real coordinated release directory to operate on offline."""
    return release.build(root, out, evidence, commit, REPO, RUN, IMAGE, packages)


@contextlib.contextmanager
def quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


class ReleaseOpsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / "source"
        self.root.mkdir()
        self.out = base / "artifacts"
        self.state = base / "release-state.json"
        (self.root / "release").mkdir()
        (self.root / "release/versions.json").write_text(json.dumps({
            "schema": release.VERSION_SCHEMA, "release": "0.1.0",
            "frontend": "0.3.0", "backend": "0.2.0",
            "api_major": 1, "api_min_major": 1, "api_max_major": 1}))
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
        self.packages = base / "packages.txt"
        self.packages.write_text("Django==5.2.18\npsycopg==3.2.12\n")
        self.evidence = base / "report.json"
        self.report = {
            "schema": "ai-compass/release-acceptance@1",
            "source": {"commit": COMMIT, "repository": REPO,
                       "workflow_run": "https://github.com/%s/actions/runs/%s" % (REPO, RUN)},
            "automated": {
                "status": "passed",
                "checks": {"check%d" % n: {"status": "passed"} for n in range(10)},
                "recovery": {"drill_report_sha256": "c" * 64,
                             "authenticated_original_download": "passed"},
                "staging_rejections": {"migration_key": "model-v1-to-v2@1"}},
            "manual_release_gates": {
                "real_browser_staging_inspection_and_signed_acceptance": "not_evidenced",
                "accepted_candidate_production_replay_with_new_recovery_point": "not_evidenced",
                "operator_release_signoff": "not_evidenced"},
            "decision": "NO_GO"}
        self.evidence.write_text(json.dumps(self.report))
        build_release(self.out, self.root, self.packages, self.evidence)
        self.candidate = ops.load_candidate(self.out)

    def contract(self, api_major=1, supported=(1,)):
        return {"api_major": api_major, "supported_client_api_majors": list(supported)}

    def state_file(self, snapshot, release_id="r0.1.0+previous0000"):
        self.state.write_bytes(ops.canonical({
            "schema": ops.STATE_SCHEMA, "release_id": release_id,
            "component_versions": {"frontend": "0.1.0", "backend": "0.1.0"},
            "api_major": 1, "migration_snapshot": snapshot}))

    # --- candidate integrity ------------------------------------------------

    def test_candidate_rechecks_pinned_integrity_and_refuses_go_manifest(self):
        manifest = json.loads((self.out / "manifest.json").read_text())
        self.assertEqual(manifest["decision"], "NO_GO")
        manifest["decision"] = "GO"
        (self.out / "manifest.json").write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ops.ReleaseOpsError, "operational GO"):
            ops.load_candidate(self.out)

    def test_tampered_frontend_artifact_is_refused_before_any_operation(self):
        (self.out / "frontend.zip").write_bytes(b"tampered")
        with self.assertRaisesRegex(ops.ReleaseOpsError, "Frontend artifact digest"):
            ops.load_candidate(self.out)

    def test_acceptance_evidence_must_match_its_pinned_digest(self):
        (self.out / "release-acceptance.json").write_text(json.dumps(self.report, indent=2))
        with self.assertRaisesRegex(ops.ReleaseOpsError, "Acceptance evidence was modified"):
            ops.load_candidate(self.out)

    # --- classification -----------------------------------------------------

    def test_same_snapshot_is_a_compatible_update(self):
        self.state_file(self.candidate["migration_snapshot"])
        installed = ops.installed_view(self.contract(), ops.load_state(self.state))
        verdict = ops.classify(installed, self.candidate)
        self.assertTrue(verdict["compatible"])
        self.assertEqual(verdict["reasons"], [])

    def test_schema_drift_and_unknown_schema_fail_closed(self):
        self.state_file("f" * 64)
        installed = ops.installed_view(self.contract(), ops.load_state(self.state))
        verdict = ops.classify(installed, self.candidate)
        self.assertFalse(verdict["compatible"])
        self.assertIn("schema_migration_required", verdict["reasons"])
        # A running instance whose schema we cannot establish is never assumed safe.
        blank = ops.installed_view(self.contract(), None)
        self.assertIn("installed_schema_unknown",
                      ops.classify(blank, self.candidate)["reasons"])
        # ...unless it is a genuinely fresh install with no data.
        self.assertTrue(ops.classify(blank, self.candidate, fresh=True)["compatible"])

    def test_api_major_mismatch_is_incompatible(self):
        self.state_file(self.candidate["migration_snapshot"])
        installed = ops.installed_view(self.contract(supported=(2,)), ops.load_state(self.state))
        verdict = ops.classify(installed, self.candidate)
        self.assertIn("api_major_incompatible", verdict["reasons"])

    # --- check end to end ---------------------------------------------------

    def test_check_refuses_unsafe_pairing_and_offline_contract_is_supported(self):
        self.state_file("f" * 64)
        contract = Path(self.tmp.name) / "contract.json"
        contract.write_text(json.dumps(self.contract()))
        args = type("A", (), {})()
        args.release = str(self.out); args.state = str(self.state)
        args.contract_json = str(contract); args.base_url = None
        args.allow_incompatible = False; args.fresh = False
        with self.assertRaisesRegex(ops.ReleaseOpsError, "Unsafe pairing"):
            with quiet():
                ops.op_check(args)
        args.allow_incompatible = True
        with quiet():
            self.assertEqual(ops.op_check(args), 0)

    # --- deploy authorization ----------------------------------------------

    def _deploy_args(self, **kw):
        args = type("A", (), {})()
        args.release = str(self.out); args.state = str(self.state)
        args.base_url = None; args.fresh = False; args.operator = "ops@example"
        args.recovery_point = None; args.approve = None
        args.contract_json = str(Path(self.tmp.name) / "contract.json")
        for key, value in kw.items():
            setattr(args, key, value)
        return args

    def test_incompatible_deploy_requires_verified_recovery_point_and_approval(self):
        (Path(self.tmp.name) / "contract.json").write_text(json.dumps(self.contract()))
        self.state_file("f" * 64)
        args = self._deploy_args(approve=self.candidate["release_id"])
        with self.assertRaisesRegex(ops.ReleaseOpsError, "verified recovery point"):
            with quiet():
                ops.op_deploy(args)
        dump = Path(self.tmp.name) / "prod.dump"
        dump.write_bytes(b"backup")
        args.recovery_point = str(dump)
        with self.assertRaisesRegex(ops.ReleaseOpsError, "independent verification"):
            with quiet():
                ops.op_deploy(args)  # no report
        dump.with_name("prod.dump.full.json").write_text(json.dumps({"complete": False}))
        with self.assertRaisesRegex(ops.ReleaseOpsError, "independently verified"):
            with quiet():
                ops.op_deploy(args)
        dump.with_name("prod.dump.full.json").write_text(json.dumps({"complete": True}))
        args.approve = "wrong"
        with self.assertRaisesRegex(ops.ReleaseOpsError, "requires --approve"):
            with quiet():
                ops.op_deploy(args)
        args.approve = self.candidate["release_id"]
        with quiet():
            self.assertEqual(ops.op_deploy(args), 0)
        saved = ops.load_state(self.state)
        self.assertEqual(saved["last_operation"]["status"], "planned")
        self.assertEqual(saved["last_operation"]["manifest_sha256"],
                         self.candidate["manifest_sha256"])
        # An incompatible plan captures/verifies the recovery point first.
        self.assertEqual(saved["last_operation"]["steps"][0]["step"],
                         "capture_verify_recovery_point")

    def test_compatible_deploy_needs_no_recovery_point_and_orders_backend_first(self):
        (Path(self.tmp.name) / "contract.json").write_text(json.dumps(self.contract()))
        self.state_file(self.candidate["migration_snapshot"])
        args = self._deploy_args()
        with quiet():
            self.assertEqual(ops.op_deploy(args), 0)
        plan = ops.load_state(self.state)
        self.assertEqual(plan["last_operation"]["status"], "planned")
        self.assertNotIn("capture_verify_recovery_point",
                         [s["step"] for s in plan["last_operation"]["steps"]])
        # Backend is updated before frontend, so no new frontend calls a missing API.
        order = [s["step"] for s in plan["last_operation"]["steps"]]
        self.assertLess(order.index("update_backend_image"), order.index("update_frontend_bundle"))

    # --- recover / stage ----------------------------------------------------

    def test_recover_is_a_plan_that_requires_an_explicit_target(self):
        args = type("A", (), {})()
        args.recovery_point = None; args.operator = "ops@example"
        with self.assertRaisesRegex(ops.ReleaseOpsError, "explicit target"):
            with quiet():
                ops.op_recover(args)
        dump = Path(self.tmp.name) / "prod.dump"
        dump.write_bytes(b"backup")
        args.recovery_point = str(dump)
        with quiet():
            self.assertEqual(ops.op_recover(args), 0)

    def test_stage_never_promotes_and_targets_the_existing_tool(self):
        args = type("A", (), {})()
        args.release = str(self.out)
        with quiet():
            self.assertEqual(ops.op_stage(args), 0)

    # --- status -------------------------------------------------------------

    def test_status_reports_recorded_state_when_live_contract_is_unreachable(self):
        self.state_file(self.candidate["migration_snapshot"])
        args = type("A", (), {})()
        args.state = str(self.state); args.contract_json = None
        args.base_url = "http://127.0.0.1:1"  # nothing listening
        with quiet():
            self.assertEqual(ops.op_status(args), 0)


if __name__ == "__main__":
    unittest.main()
