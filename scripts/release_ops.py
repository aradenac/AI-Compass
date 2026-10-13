#!/usr/bin/env python3
"""FUT-21: guided release operations that orchestrate existing, already-verified tools.

A small operator entrypoint (`check`, `status`, `stage`, `deploy`, `recover`) that
composes the existing PLAT tools — the coordinated release manifest, migration
staging/promotion and the coordinated recovery point — instead of introducing a
second migration engine, Kubernetes, an event bus or a separate release database.

Guarantees:
- An unsafe frontend/backend pairing, API incompatibility or schema drift is
  refused *before* any live data changes.
- An incompatible change additionally requires an **independently verified**
  recovery point and an explicit privileged approval; a refusal, interruption or
  failed staging leaves production untouched.
- Deployment is never executed silently: it produces an ordered, recorded,
  idempotent plan whose apply stays with the existing, separately guarded tools.
  Staging is never promoted and production GO is never inferred from CI alone.
"""
import argparse
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import build_coordinated_release as coordinated

SEMVER = re.compile(r"\d+\.\d+\.\d+\Z")
STATE_SCHEMA = "ai-compass/release-state@1"
PLAN_SCHEMA = "ai-compass/release-plan@1"


class ReleaseOpsError(ValueError):
    pass


def demand(ok, message):
    if not ok:
        raise ReleaseOpsError(message)


def canonical(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    p = Path(path)
    demand(p.is_file() and not p.is_symlink(), "Missing or unsafe file: " + str(p))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ReleaseOpsError("Invalid JSON: " + str(p)) from exc


# --- candidate and installed views -----------------------------------------

def load_candidate(release_dir):
    """Read one coordinated release directory, re-checking its pinned integrity.

    The operator typically has only the release directory, not the full source
    tree, so we re-verify the digests *inside* the directory (artifact,
    dependency inventory, acceptance evidence) rather than re-deriving them from
    sources. The manifest itself is only ever accepted as a NO-GO manifest.
    """
    root = Path(release_dir)
    manifest = read_json(root / "manifest.json")
    demand(manifest.get("schema") == coordinated.SCHEMA,
           "Not a coordinated release manifest")
    demand(manifest.get("decision") == "NO_GO",
           "Refusing a manifest that claims operational GO")
    source = manifest.get("source") or {}
    demand(coordinated.COMMIT.fullmatch(source.get("commit", "")) is not None,
           "Unverified source commit")
    frontend = (manifest.get("components") or {}).get("frontend") or {}
    backend = (manifest.get("components") or {}).get("backend") or {}
    compat = manifest.get("compatibility") or {}
    evidence = manifest.get("evidence") or {}
    demand(compat.get("api_major") in (compat.get("supported_client_api_majors") or []),
           "Candidate manifest declares an unsupported API major")
    for name, component in (("frontend", frontend), ("backend", backend)):
        demand(SEMVER.fullmatch(component.get("version", "")) is not None,
               "Missing component version: " + name)
    # Re-validate the CI acceptance evidence the manifest pins.
    acceptance = read_json(root / "release-acceptance.json")
    demand(digest((root / "release-acceptance.json").read_bytes())
           == evidence.get("acceptance_sha256"), "Acceptance evidence was modified")
    coordinated.validate_evidence(acceptance, source.get("commit"),
                                  source.get("repository"), str(source.get("ci_run_id")))
    # Re-validate each pinned artifact against its declared digest.
    demand(_artifact_matches(root, frontend.get("artifact"), frontend.get("artifact_sha256")),
           "Frontend artifact digest mismatch")
    demand(_artifact_matches(root, backend.get("pip_freeze_artifact"),
                            backend.get("pip_freeze_sha256")),
           "Backend dependency inventory digest mismatch")
    demand("**Production decision: NO-GO.**" in
           (root / "release-notes.md").read_text(encoding="utf-8"),
           "Release notes omit the operational approval blocker")
    return {
        "release_id": manifest.get("release_id"),
        "commit": source["commit"],
        "api_major": compat["api_major"],
        "supported_client_api_majors": compat["supported_client_api_majors"],
        "migration_snapshot": compat.get("django_migration_snapshot_sha256"),
        "component_versions": {name: component["version"]
                               for name, component in (("frontend", frontend), ("backend", backend))},
        "release_notes": (root / "release-notes.md").exists(),
        "manifest_sha256": digest(canonical(manifest)),
        "recovery_evidence": evidence.get("recovery_sha256"),
    }


def _artifact_matches(root, name, expected):
    if not name or not isinstance(expected, str):
        return False
    path = root / name
    return path.is_file() and not path.is_symlink() and digest(path.read_bytes()) == expected


def fetch_contract(base_url, timeout=10):
    """Read the live instance's version/capability handshake (safe, pre-auth)."""
    url = base_url.rstrip("/") + "/api/v1/contract"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # network/HTTP/JSON: refuse rather than guess
        raise ReleaseOpsError("Cannot read live contract from " + url) from exc


def installed_view(contract, state):
    """Combine the live handshake with the last recorded operation state."""
    demand(contract.get("api_major") is not None, "Live contract has no API major")
    return {
        "api_major": contract["api_major"],
        "supported_client_api_majors": contract.get("supported_client_api_majors", []),
        "component_versions": (state or {}).get("component_versions", {}),
        "release_id": (state or {}).get("release_id"),
        "migration_snapshot": (state or {}).get("migration_snapshot"),
    }


# --- classification ---------------------------------------------------------

def classify(installed, candidate, *, fresh=False):
    """Decide compatibility BEFORE touching live data.

    Incompatible when the candidate API major is not accepted by the running
    instance, when the migration snapshot differs (a schema/data migration), or —
    fail-closed — when a running instance's schema is unknown. A brand-new
    instance (`fresh=True`, no prior data to lose) needs no recovery point.
    """
    reasons = []
    if candidate["api_major"] not in installed["supported_client_api_majors"]:
        reasons.append("api_major_incompatible")
    if not fresh:
        known = installed.get("migration_snapshot")
        if not known:
            reasons.append("installed_schema_unknown")
        elif candidate.get("migration_snapshot") != known:
            reasons.append("schema_migration_required")
    return {"compatible": not reasons, "reasons": reasons}


# --- durable state ----------------------------------------------------------

def load_state(path):
    p = Path(path)
    if not p.exists():
        return None
    state = read_json(p)
    demand(state.get("schema") == STATE_SCHEMA, "Unknown release state schema")
    return state


def write_state(path, state):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["schema"] = STATE_SCHEMA
    state["updated_at"] = now()
    p.write_bytes(canonical(state))
    return state


# --- operations -------------------------------------------------------------

def _installed(args, state):
    contract = read_json(args.contract_json) if args.contract_json \
        else fetch_contract(args.base_url)
    return installed_view(contract, state)


def op_check(args):
    candidate = load_candidate(args.release)
    state = load_state(args.state) if args.state else None
    installed = _installed(args, state)
    verdict = classify(installed, candidate, fresh=args.fresh)
    report = {"action": "check", "candidate": candidate, "installed": installed,
              "compatibility": verdict, "at": now()}
    print(json.dumps(report, sort_keys=True, indent=2))
    if not verdict["compatible"] and not args.allow_incompatible:
        raise ReleaseOpsError("Unsafe pairing: " + ",".join(verdict["reasons"]))
    return 0


def op_status(args):
    state = load_state(args.state) if args.state else None
    try:
        contract = read_json(args.contract_json) if args.contract_json \
            else fetch_contract(args.base_url)
    except ReleaseOpsError:
        contract = None
    print(json.dumps({"action": "status", "recorded": state, "live": contract,
                      "at": now()}, sort_keys=True, indent=2))
    return 0


def _require_authorization(args, verdict, candidate):
    """Deploy preconditions: explicit approval, and an independently verified
    recovery point when the change is incompatible."""
    if verdict["compatible"]:
        return
    demand(args.recovery_point,
           "Incompatible change requires a verified recovery point (--recovery-point)")
    dump = Path(args.recovery_point)
    demand(dump.is_file() and not dump.is_symlink(),
           "Recovery point does not exist: " + str(dump))
    verification = dump.with_name(dump.name + ".full.json")
    demand(verification.is_file(),
           "Recovery point has no independent verification report")
    report = read_json(verification)
    demand(report.get("complete") is True,
           "Recovery point is not independently verified as complete")
    demand(args.approve == candidate["release_id"],
           "Incompatible change requires --approve " + str(candidate["release_id"]))


def op_deploy(args):
    candidate = load_candidate(args.release)
    state = load_state(args.state) if args.state else None
    installed = _installed(args, state)
    verdict = classify(installed, candidate, fresh=args.fresh)
    _require_authorization(args, verdict, candidate)
    # Never executes the change itself: produce an ordered, recorded plan whose
    # apply stays with the existing, separately guarded tools. Backend is updated
    # before frontend so a new frontend never calls an API it cannot reach.
    steps = []
    if not verdict["compatible"]:
        steps.append({"step": "capture_verify_recovery_point",
                      "argument": str(args.recovery_point)})
    steps += [
        {"step": "apply_migrations", "tool": "scripts/migration_promote.py",
         "note": "backend-first; that tool re-enforces its own promotion guards"},
        {"step": "update_backend_image", "version": candidate["component_versions"]["backend"]},
        {"step": "update_frontend_bundle", "version": candidate["component_versions"]["frontend"]},
    ]
    plan = {"schema": PLAN_SCHEMA, "action": "deploy", "release_id": candidate["release_id"],
            "manifest_sha256": candidate["manifest_sha256"],
            "compatible": verdict["compatible"], "reasons": verdict["reasons"],
            "approved_by": args.operator, "steps": steps, "at": now(),
            "note": "Plan only; no live data changed. Production decision remains NO-GO."}
    if args.state:
        write_state(args.state, {
            "release_id": candidate["release_id"],
            "component_versions": candidate["component_versions"],
            "api_major": candidate["api_major"],
            "migration_snapshot": candidate["migration_snapshot"],
            "last_operation": {"action": "deploy", "release_id": candidate["release_id"],
                               "status": "planned", "manifest_sha256": candidate["manifest_sha256"],
                               "steps": steps, "at": now()},
        })
    print(json.dumps(plan, sort_keys=True, indent=2))
    return 0


def op_recover(args):
    """Show a safe recovery plan; never overwrites production silently."""
    demand(args.recovery_point, "recover requires --recovery-point (an explicit target)")
    dump = Path(args.recovery_point)
    demand(dump.is_file() and not dump.is_symlink(),
           "Recovery point does not exist: " + str(dump))
    plan = {
        "action": "recover", "target": str(dump), "operator": args.operator, "at": now(),
        "note": "Code rollback is not database rollback: an image revert does not "
                "restore data. The restore target must be named explicitly and never "
                "default to the running production database.",
        "steps": [
            {"step": "stop_api_writes", "tool": "docker compose stop -t 30 api"},
            {"step": "verify_recovery_point", "tool": "scripts/full_recovery.py verify",
             "target": str(dump)},
            {"step": "restore_against_explicit_target",
             "note": "operator-named destination only; never production implicitly"},
            {"step": "reconcile_tombstones",
             "note": "reapply revisions/retirements after a point-in-time restore"},
            {"step": "start_api_and_verify"},
        ],
    }
    print(json.dumps(plan, sort_keys=True, indent=2))
    return 0


def op_stage(args):
    """Delegate isolated staging to the existing guarded tool; never auto-promote."""
    plan = {"action": "stage", "candidate": args.release, "at": now(),
            "delegate": {"tool": "scripts/migration_stage.py", "action": "create"},
            "note": "Restores an isolated copy from a coordinated recovery point and "
                    "rehearses the migration there. Production is untouched and "
                    "nothing is promoted automatically."}
    print(json.dumps(plan, sort_keys=True, indent=2))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check", "status", "stage", "deploy", "recover"])
    parser.add_argument("--release", help="Coordinated release directory (manifest.json)")
    parser.add_argument("--state", help="Durable release-state.json path")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080",
                        help="Running instance base URL for the live contract")
    parser.add_argument("--contract-json", help="Offline contract document (instead of --base-url)")
    parser.add_argument("--fresh", action="store_true",
                        help="The running instance is a brand-new install with no data")
    parser.add_argument("--allow-incompatible", action="store_true",
                        help="check: report an incompatible pairing without failing")
    parser.add_argument("--recovery-point", help="Verified .dump recovery point")
    parser.add_argument("--approve", help="Privileged approval token = candidate release_id")
    parser.add_argument("--operator", default="", help="Accountable operator identity")
    args = parser.parse_args(argv)
    try:
        if args.command in ("check", "deploy"):
            demand(args.release, "This command requires --release")
        if args.command == "check":
            return op_check(args)
        if args.command == "status":
            return op_status(args)
        if args.command == "stage":
            return op_stage(args)
        if args.command == "deploy":
            return op_deploy(args)
        return op_recover(args)
    except (ReleaseOpsError, coordinated.ReleaseError) as exc:
        print("release operation refused: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
