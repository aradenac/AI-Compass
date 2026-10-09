#!/usr/bin/env python3
"""PLAT-26: fail-closed host orchestration of accepted staging -> current production.

Never copies a staging database. Never applies without a real accepted verdict
on this trusted host, exact build+artifact hashes, and a freshly verified
independent full DB+evidence recovery point.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

import migration_stage as stage
import full_recovery as full
import recovery as db

REGISTRY = {stage.MIGRATION: stage.MIGRATION_FILE}
MAX_BATCHES = 10000


def fail(message):
    raise db.RecoveryError(message)


def file_sha(path):
    return db.hash_file(path)


def approval(candidate):
    """Read authenticated-host staging metadata; do not trust a browser payload."""
    folder = stage.candidate_dir(candidate)
    if folder.is_symlink():
        fail("Symlinked promotion candidate not allowed")
    report_file, verdict_file = folder / "report.json", folder / "verdict.json"
    if (not report_file.is_file() or not verdict_file.is_file()
            or report_file.is_symlink() or verdict_file.is_symlink()):
        fail("Missing durable staging report or manual verdict")
    report = json.loads(report_file.read_text("utf-8"))
    verdict = json.loads(verdict_file.read_text("utf-8"))
    if report.get("candidate_id") != candidate or report.get("project") != stage.project_for(candidate):
        fail("Wrong staging project identity")
    if not ((report.get("status") == "accepted") or
            (report.get("status") == "discarded" and report.get("prior_status") == "accepted")):
        fail("Stage has no accepted manual review")
    if report.get("verdict") != verdict or verdict.get("decision") != "accepted" or not verdict.get("frontend_checked"):
        fail("Missing matching human frontend acceptance")
    if not isinstance(verdict.get("notes"), str) or not verdict["notes"].strip():
        fail("A substantive manual acceptance note is required")
    for key in ("candidate_id", "migration", "migration_sha256",
                "application_commit", "snapshot_id", "snapshot_manifest_sha256"):
        if verdict.get(key) != report.get(key):
            fail("Approval identity mismatch: " + key)
    if report.get("automated_checks") != "passed" or report.get("migrated", {}).get("status") != "passed":
        fail("Isolated staging verification has not passed")
    migration = report.get("migration")
    if migration not in REGISTRY or report.get("migration_sha256") != file_sha(REGISTRY[migration]):
        fail("Unregistered or tampered transformation artifact")
    commit = stage.build_identity()
    if commit != report.get("application_commit"):
        fail("Approved application commit is not current clean build")
    source, manifest = stage.snapshot_for(report["snapshot"])
    if (manifest["backup_id"] != report.get("snapshot_id")
            or file_sha(full.sibling(source, ".full.json")) != report["snapshot_manifest_sha256"]):
        fail("Approved source recovery point modified/obsolete")
    if manifest.get("restored_inspection", {}).get("schema_versions") != report.get("source_schema_versions"):
        fail("Staging source schema metadata changed")
    return report, verdict, file_sha(verdict_file)


def production_secret():
    """The host-only .env contains Django's secret; do not log it."""
    env = db.ROOT / ".env"
    if not env.is_file() or env.is_symlink():
        fail("Production .env is missing or unsafe")
    secret = None
    for line in env.read_text("utf-8").splitlines():
        if line.startswith("DJANGO_SECRET_KEY="):
            secret = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not secret or len(secret) < 32 or secret.startswith("REPLACE_WITH_"):
        fail("Production Django signing secret missing")
    return secret


def docker_cmd(args, *, proof_file=None, timeout=600):
    return db.run(db.COMPOSE + args, input_file=proof_file, timeout=timeout)


def backend_preview(operator):
    output = docker_cmd(["exec", "-T", "api", "python", "manage.py",
                         "promote_model_schema", "--preview", "--operator", operator, "--json"])
    try:
        return json.loads(output.splitlines()[-1])
    except (IndexError, ValueError) as error:
        fail("Production preflight did not return a parseable record")


def prepare_proof(report, verdict_hash, operator, backup):
    inspection = backup["restored_inspection"]
    proof = {
        "candidate_id": report["candidate_id"],
        "migration": report["migration"],
        "migration_sha256": report["migration_sha256"],
        "app_commit": report["application_commit"],
        "recovery_id": backup["backup_id"],
        "recovery_manifest_sha256": file_sha(full.sibling(
            Path(backup["_dump_path"]), ".full.json")),
        "approved_report_sha256": verdict_hash,
        "source_item_count": inspection["item_count"],
        "source_revision_count": inspection["revision_count"],
        "source_revision_digest": inspection["revision_digest"],
        "source_hrid_digest": inspection["hrid_digest"],
        "source_audit_count": inspection["audit_count"],
        "source_schema_versions": inspection["schema_versions"],
        "source_schema_hashes": inspection["schema_hashes"],
        "source_evidence_db_references": inspection["evidence_db_references"],
        "operator": operator,
    }
    # Same deterministic canonical HMAC as the Django management command.
    signature = __import__("hmac").new(
        production_secret().encode("utf-8"),
        json.dumps(proof, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8"), hashlib.sha256,
    ).hexdigest()
    return {"proof": proof, "signature": signature}


def preview(candidate, operator):
    report, _, verdict_hash = approval(candidate)
    info = backend_preview(operator)
    return {"status":"preview", "candidate_id": candidate,
            "application_commit": report["application_commit"],
            "migration_sha256": report["migration_sha256"],
            "verdict_sha256": verdict_hash,
            "production": info}


def apply(candidate, operator, confirm_candidate, destination, *, allow_ci=False):
    if confirm_candidate != candidate:
        fail("Explicit --confirm-candidate must equal the accepted candidate ID")
    report, _, verdict_hash = approval(candidate)
    before = backend_preview(operator)
    if before["blocked_count"]:
        fail("Ambiguous production records require human review; no mutation permitted")
    # Full backup requires an already-existing independently mounted filesystem.
    args = argparse.Namespace(destination=destination, allow_local_ci=allow_ci,
                              require_external=True, keep=14)
    dump = full.full_backup(args)  # verifies an independent restore and original hashes
    backup = full.verified_manifest(dump)
    backup["_dump_path"] = str(dump)
    if backup.get("restored_inspection", {}).get("schema_versions") != report.get("source_schema_versions"):
        fail("Production object schema differs from accepted staging source")
    envelope = prepare_proof(report, verdict_hash, operator, backup)
    result = {"status":"applying", "candidate_id":candidate,
              "recovery_id":backup["backup_id"], "changed":0, "batches":0}
    # The service stays frozen if an unknown error requires manual intervention.
    # A verified recovery point is already safely off-host before the freeze.
    docker_cmd(["stop", "api"], timeout=90)
    try:
        with tempfile.TemporaryDirectory(prefix="aic-promotion-") as temp:
            file = Path(temp) / "approval.json"
            file.write_text(json.dumps(envelope, sort_keys=True), "utf-8")
            file.chmod(0o600)
            for _ in range(MAX_BATCHES):
                output = docker_cmd([
                    "run", "--rm", "-T", "-e", "AI_COMPASS_PROMOTION_API_FROZEN=1",
                    "api", "python", "manage.py", "promote_model_schema", "--apply",
                    "--operator", operator, "--json"], proof_file=file, timeout=240)
                try:
                    data = json.loads(output.splitlines()[-1])
                except (IndexError, ValueError):
                    fail("Production promotion returned invalid batch receipt")
                if data.get("candidate_id") != candidate or not isinstance(data.get("remaining"), int):
                    fail("Batch identity or count mismatch")
                changed = data.get("changed")
                if not isinstance(changed, int) or changed < 0 or (changed == 0 and data["remaining"]):
                    fail("A promotion batch made no progress")
                result["changed"] += changed
                result["batches"] += 1
                if data["remaining"] == 0:
                    result["status"] = "passed"
                    break
            else:
                fail("Maximum registered migration batches exceeded")
        docker_cmd(["start", "api"], timeout=180)
        return result
    except Exception:
        # Intentionally do not resume a potentially inconsistent Server.
        # Investigate/retry against the SAME signed recovery proof or restore
        # verified DB+evidence snapshot, never a staging DB.
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("preview", "apply"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--candidate", required=True)
        cmd.add_argument("--operator", required=True)
        if name == "apply":
            cmd.add_argument("--confirm-candidate", required=True)
            cmd.add_argument("--destination", required=True,
                             help="Pre-existing separate mounted recovery destination")
    args = parser.parse_args(argv)
    try:
        if not stage.CANDIDATE.fullmatch(args.candidate):
            fail("Invalid promotion candidate")
        if args.action == "preview":
            print(json.dumps(preview(args.candidate, args.operator), sort_keys=True))
        else:
            print(json.dumps(apply(args.candidate, args.operator,
                                   args.confirm_candidate, args.destination), sort_keys=True))
    except (db.RecoveryError, OSError, ValueError, KeyError) as error:
        print("PROMOTION REFUSED: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
