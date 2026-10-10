#!/usr/bin/env python3
"""PLAT-32: derive a fail-closed release acceptance dossier from *executed* CI.

Only run collect as the FINAL success-gated step of the platform smoke job.
All prerequisite command failures must have halted that job already. A green
CI proves the automated campaign only: it never fabricates human staging
frontend acceptance or an approved, recoverable production replay.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

REQUIRED_STEPS = (
    "fresh_server_zero_business",
    "cross_role_workflow_with_evidence",
    "session_and_run_permissions",
    "native_export_restore",
    "coordinated_db_blob_drill",
    "staging_reject_recreate_twice",
    "original_schema_and_evidence_unchanged",
    "server_frontend_adapter_no_demo_fallback",
    "standalone_demo_regression",
    "migration_promotion_negative_gates",
)
SCHEMA = "ai-compass/release-acceptance@1"


class AcceptanceError(ValueError):
    pass


def check(condition, message):
    if not condition:
        raise AcceptanceError(message)


def read_json(path):
    file = Path(path)
    check(file.is_file() and not file.is_symlink(), "Missing/unsafe CI artifact: " + str(path))
    try:
        result = json.loads(file.read_text("utf-8"))
    except (ValueError, UnicodeError, OSError) as exc:
        raise AcceptanceError("Invalid CI JSON artifact: " + str(path)) from exc
    check(isinstance(result, dict), "Non-object CI artifact: " + str(path))
    return result


def sha_file(path):
    hash_value = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hash_value.update(chunk)
    return hash_value.hexdigest()


def collect(temp, commit, run_id, repository, *, ci_environment):
    check(ci_environment.get("CI") == "true"
          and ci_environment.get("GITHUB_ACTIONS") == "true",
          "Only a completed GitHub CI smoke job may attest automated acceptance")
    check(re.fullmatch(r"[0-9a-f]{40}", commit) is not None, "Invalid tested commit")
    check(re.fullmatch(r"[0-9]+", str(run_id)) is not None, "Missing workflow run ID")
    check(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None,
          "Invalid source repository")
    check(ci_environment.get("GITHUB_SHA") == commit
          and ci_environment.get("GITHUB_RUN_ID") == str(run_id)
          and ci_environment.get("GITHUB_REPOSITORY") == repository,
          "Workflow/commit identity does not match live GitHub CI environment")
    # These files are emitted from the actual disposable recovery and staging
    # commands in the same job, NOT re-created from example/dummy fixtures.
    root = Path(temp)
    restore_file = root / "full-restore-report.json"
    status_file = root / "full-status.json"
    restored = read_json(restore_file)
    status = read_json(status_file)
    stages = [read_json(root / ("stage%d.json" % n)) for n in (1, 2, 3)]
    check(restored.get("status") == "passed"
          and isinstance(restored.get("restored"), dict), "DB+blob drill did not pass")
    inspection = restored["restored"].get("inspection", {})
    evidence = inspection.get("evidence_db_references", {})
    check(restored["restored"].get("api_download") == "passed"
          and isinstance(evidence.get("link_count"), int)
          and evidence["link_count"] > 0
          and isinstance(evidence.get("sha256"), list)
          and len(evidence["sha256"]) > 0
          and all(re.fullmatch(r"[0-9a-f]{64}", x) for x in evidence["sha256"]),
          "Isolated DB/blob recovery lacks original bytes and authenticated read")
    check(status.get("status") == "ok"
          and status.get("last_successful_restore", {}).get("status") == "passed",
          "Full recovery status does not attest successful verified restore")
    ids = []
    for stage in stages:
        cid = stage.get("candidate_id")
        check(isinstance(cid, str) and re.fullmatch(r"[0-9a-f]{16}", cid),
              "Missing isolated staging candidate ID")
        ids.append(cid)
        check(stage.get("automated_checks") == "passed"
              and stage.get("migrated", {}).get("changed") == 1,
              "Staging migration/retry validation failed")
        check(stage.get("migration") == "model-v1-to-v2@1"
              and isinstance(stage.get("snapshot_id"), str)
              and stage.get("snapshot_id")
              and re.fullmatch(r"[0-9a-f]{64}",
                               stage.get("snapshot_manifest_sha256", "")),
              "Staging artifact/source recovery fingerprint missing")
    check(len(set(ids)) == 3, "Staging recreation reused a disposable candidate")
    check(len({x["snapshot_id"] for x in stages}) == 1
          and len({x["snapshot_manifest_sha256"] for x in stages}) == 1,
          "Staging retries did not restore the same original coordinated snapshot")

    results = {
        name: {"status": "passed", "basis": "Same success-gated platform-smoke job"}
        for name in REQUIRED_STEPS
    }
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "repository": repository, "commit": commit,
            "workflow_run": "https://github.com/%s/actions/runs/%s" % (repository, run_id),
            "kind": "CI automated campaign", "environment": "ephemeral_disposable",
        },
        "automated": {
            "status": "passed", "checks": results,
            "recovery": {
                "drill_report_sha256": sha_file(restore_file),
                "source_objects": inspection.get("item_count"),
                "source_revisions": inspection.get("revision_count"),
                "original_evidence_link_count": evidence["link_count"],
                "original_evidence_sha256": sorted(evidence["sha256"]),
                "authenticated_original_download": "passed",
            },
            "staging_rejections": {
                "candidates": ids,
                "recovery_id": stages[0]["snapshot_id"],
                "recovery_manifest_sha256": stages[0]["snapshot_manifest_sha256"],
                "migration_key": stages[0]["migration"],
                "migration_sha256": stages[0].get("migration_sha256"),
                "automated_checks": "passed",
                "manual_frontend_accepted": False,
            },
        },
        "manual_release_gates": {
            "real_browser_staging_inspection_and_signed_acceptance": "not_evidenced",
            "accepted_candidate_production_replay_with_new_recovery_point": "not_evidenced",
            "operator_release_signoff": "not_evidenced",
        },
        "decision": "NO_GO",
        "blockers": [
            {"issue": 35, "reason": "Staged migration requires real human Server-frontend inspection and accepted candidate evidence"},
            {"issue": 26, "reason": "Accepted migration must be replayed on separate approved dataset with original verified recovery point and immutable receipts"},
            {"issue": 32, "reason": "Release owner must review all operational evidence and record an explicit go/no-go signoff"},
        ],
        "limits": [
            "CI DOM/JS adapters and HTTP requests are not equivalent to a human browser inspection",
            "CI staging rejection never proves acceptance or authorized production replay",
            "No external real-data import or operational production migration was attempted",
        ],
    }


def render_markdown(report):
    meta = report["source"]
    lines = [
        "# AI Compass · PLAT-32 release acceptance",
        "",
        "**Decision: NO-GO** — automated tests passing is insufficient for production release.",
        "",
        "| Field | Value |",
        "| --- | --- |",
        "| Commit under test | \`" + meta["commit"] + "\` |",
        "| GitHub Actions | " + meta["workflow_run"] + " |",
        "| CI campaign | " + report["automated"]["status"] + " |",
        "| Browser/manual production gates | not evidenced |",
        "",
        "## Executed automatic regression",
        "",
    ]
    lines.extend("- **%s:** passed" % name.replace("_", " ") for name in REQUIRED_STEPS)
    checks = report["automated"]
    lines += [
        "",
        "## Recovery and migration evidence",
        "",
        "- Isolated DB+blob report SHA-256: \`%s\`" % checks["recovery"]["drill_report_sha256"],
        "- Original evidence links: %s" % checks["recovery"]["original_evidence_link_count"],
        "- Original evidence SHA-256: " + ", ".join("\`" + x + "\`"
                                                    for x in checks["recovery"]["original_evidence_sha256"]),
        "- Coordinated recovery point: \`%s\`" % checks["staging_rejections"]["recovery_id"],
        "- Source recovery manifest SHA-256: \`%s\`" % checks["staging_rejections"]["recovery_manifest_sha256"],
        "- Staging create/recreate candidates: " + ", ".join(
            "\`" + x + "\`" for x in checks["staging_rejections"]["candidates"]),
        "- Stage mutation: one v1→v2 revision, twice recreated from the unchanged source; each rejected/discarded",
        "",
        "## Blocking operational acceptance",
        "",
    ]
    lines.extend("- [#%s](https://github.com/%s/issues/%s): %s" % (
        item["issue"], meta["repository"], item["issue"], item["reason"])
                 for item in report["blockers"])
    lines += [
        "",
        "## Operator action and recovery",
        "",
        "1. See \`docs/migration-staging.md\`: inspect historical/current records and original evidence through the **real staging Server frontend**; explicitly record a pinned manual acceptance or rejection.",
        "2. See \`docs/migration-production.md\`: after accepted staging, preview approved migration and use the controlled signed promotion with a **new independent verified DB+blob recovery point**, never replacing production from staging.",
        "3. Verify the resulting immutable receipts, hashes, baseline counts and rollback drill on an appropriate separate approved target; retain operator identity, timestamps, candidate, recovery ID, build and migration SHA.",
        "4. Have the accountable release operator separately sign off all criteria. Until then release remains **NO-GO**. If replay fails, freeze writes and restore **both DB and evidence bytes** from the independently verified recovery point; do not assume inverse SQL.",
        "",
        "Demo is permanently independent localStorage without Docker; Server uses authenticated PostgreSQL and starts with zero business records. CI exercises both, but manual GUI validation remains outstanding.",
        "",
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--temp", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--destination", required=True)
    args = parser.parse_args(argv)
    try:
        report = collect(args.temp, args.commit, args.run_id, args.repository,
                         ci_environment=os.environ)
        directory = Path(args.destination)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True)
                                               + "\n", encoding="utf-8")
        (directory / "report.md").write_text(render_markdown(report), encoding="utf-8")
        print(json.dumps({"report": str(directory / "report.md"),
                          "automated": report["automated"]["status"],
                          "decision": report["decision"]}))
    except (AcceptanceError, OSError, KeyError, TypeError) as exc:
        print("READINESS EVIDENCE INCOMPLETE: " + str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
