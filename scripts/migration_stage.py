#!/usr/bin/env python3
"""PLAT-35: create, judge and safely discard an isolated migration test Server.

Accepts only PLAT-29 four-part verified full recovery points and exactly one
registered staging-only migration. Production Compose files/volumes are never
written to, started, stopped or passed to a destructive command.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

import recovery as db
import full_recovery as full

STATE_ROOT = db.ROOT / ".local" / "staging"
COMPOSE_FILE = db.ROOT / "staging" / "compose.yaml"
MIGRATION_FILE = db.ROOT / "backend/config/management/commands/stage_model_v1_to_v2.py"
MIGRATION = "model-v1-to-v2@1"
PROJECT_PREFIX = "ai-compass-stage-"
CANDIDATE = re.compile(r"^[0-9a-f]{16}$")
DB_USER, DB_NAME = db.RESTORE_USER, db.RESTORE_DB
SAFE_ENV = ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONFIG", "XDG_RUNTIME_DIR",
            "DOCKER_CERT_PATH", "DOCKER_TLS_VERIFY")


def fail(message):
    raise db.RecoveryError(message)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def protected_root():
    for path in (db.ROOT / ".local", STATE_ROOT):
        if path.is_symlink():
            fail("Unsafe staging state directory symlink")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.chmod(0o700)
    return STATE_ROOT


def candidate_dir(identifier):
    if not CANDIDATE.fullmatch(identifier or ""):
        fail("Invalid staging candidate identifier")
    return protected_root() / identifier


def project_for(identifier):
    return PROJECT_PREFIX + identifier


def command(argv, *, input_file=None, timeout=300):
    # Never inherit production Compose project/DB variables or env-file.
    environment = {key: os.environ[key] for key in SAFE_ENV if key in os.environ}
    try:
        with (open(input_file, "rb") if input_file else _nullcontext()) as stream:
            result = subprocess.run(argv, cwd=db.ROOT, stdin=stream, env=environment,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as error:
        fail("Command failed to run: " + str(error))
    output = result.stdout.decode("utf-8", "replace").strip()
    if result.returncode:
        fail("Command failed: " + " ".join(argv[:5]) + ": " +
             result.stderr.decode("utf-8", "replace")[-1200:])
    return output


class _nullcontext:
    def __enter__(self):
        return None

    def __exit__(self, *args):
        return False


def compose(folder, action, *, timeout=360):
    identifier = folder.name
    if not CANDIDATE.fullmatch(identifier) or not folder.is_dir() or folder.is_symlink():
        fail("Unsafe staging Compose target")
    return command(["docker", "compose", "--project-directory", str(db.ROOT / "staging"),
                    "-f", str(COMPOSE_FILE), "--env-file", str(folder / "runtime.env"),
                    "-p", project_for(identifier)] + action, timeout=timeout)


def runtime_checksum(folder):
    file = folder / "runtime.env"
    if not file.is_file() or file.is_symlink():
        fail("Missing or unsafe candidate credentials")
    return db.hash_file(file)


def check_state(identifier):
    folder = candidate_dir(identifier)
    path = folder / "report.json"
    if not path.is_file() or path.is_symlink():
        fail("Unknown staging candidate")
    report = json.loads(path.read_text("utf-8"))
    if (report.get("candidate_id") != identifier or
            report.get("project") != project_for(identifier) or
            report.get("migration") != MIGRATION or
            report.get("migration_sha256") != db.hash_file(MIGRATION_FILE) or
            report.get("runtime_sha256") != runtime_checksum(folder)):
        fail("Candidate identity, executable migration or staging credentials changed")
    return folder, report


def save_report(folder, report):
    if folder.is_symlink():
        fail("Unsafe staging report directory")
    db.durable_write(folder / "report.json", db.json_bytes(report))


def volume_name(identifier, kind):
    if kind not in ("evidence", "pgdata"):
        fail("Unexpected volume kind")
    return project_for(identifier) + "_" + kind


def docker_volume_label(volume):
    # None is allowed for absent volumes; every existing stage volume MUST be ours.
    environment = {key: os.environ[key] for key in SAFE_ENV if key in os.environ}
    result = subprocess.run(["docker", "volume", "inspect", volume, "--format",
                             '{{index .Labels "com.docker.compose.project"}}'],
                            cwd=db.ROOT, env=environment, capture_output=True,
                            timeout=20, check=False)
    if result.returncode:
        if b"no such volume" in result.stderr.lower():
            return None
        fail("Cannot inspect Docker volume: " + result.stderr.decode("utf-8", "replace")[-500:])
    return result.stdout.decode("utf-8", "replace").strip()


def assert_owned(identifier, *, absent=False):
    project = project_for(identifier)
    for kind in ("pgdata", "evidence"):
        label = docker_volume_label(volume_name(identifier, kind))
        if absent and label is not None:
            fail("Refusing to reuse existing staging volume")
        if label is not None and label != project:
            fail("Refusing volume not owned by exact staging project: " + kind)


def validate_environment(identifier):
    # Explicitly pin the disposable target. Do not trust COMPOSE_PROJECT_NAME
    # or arbitrary user --project/--volume values.
    if not CANDIDATE.fullmatch(identifier):
        fail("Invalid candidate")
    command(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=25)
    assert_owned(identifier, absent=True)
    occupied = command(["docker", "ps", "-aq", "--filter",
                        "label=com.docker.compose.project=" + project_for(identifier)])
    if occupied:
        fail("Another container already uses the candidate project")


def snapshot_for(path):
    source = Path(path).expanduser().resolve(strict=True)
    manifest = full.verified_manifest(source)  # checks *all* four artifacts + all blob hashes
    return source, manifest


def build_identity():
    revision = command(["git", "rev-parse", "HEAD"])
    if not re.fullmatch("[0-9a-f]{40}", revision):
        fail("Build commit could not be pinned")
    if command(["git", "status", "--porcelain", "--untracked-files=no"]):
        fail("Dirty tracked source: stage only a clean, reproducible build")
    return revision


def frontend_copy(folder, identifier):
    page = (db.ROOT / "prototype.html").read_text("utf-8")
    if "</body>" not in page or '<script src="server-mode.js"></script>' not in page:
        fail("Cannot identify shared Server frontend insertion point")
    page = page.replace("</body>", '<script src="/banner.js"></script>\n</body>', 1)
    target = folder / "prototype.html"
    db.durable_write(target, page)
    target.chmod(0o644)
    return target


def staging_environment(folder, identifier, port):
    if not 1024 <= port <= 65535 or port == 8080:
        fail("Stage port must be a dedicated non-production loopback port")
    page = frontend_copy(folder, identifier)
    lines = {
        "STAGING_DB_PASSWORD": secrets.token_urlsafe(36),
        "STAGING_DJANGO_SECRET": secrets.token_urlsafe(48),
        "STAGING_CANDIDATE": identifier,
        "STAGING_PORT": str(port),
        "STAGING_PAGE": str(page),
    }
    db.durable_write(folder / "runtime.env",
                     "\n".join(key + "=" + value for key, value in lines.items()) + "\n")
    return lines


def db_container(folder):
    identifier = folder.name
    assert_owned(identifier)
    result = compose(folder, ["ps", "-q", "db"])
    if not re.fullmatch(r"[0-9a-f]{12,64}", result):
        fail("Disposable Postgres container missing or ambiguous")
    labels = command(["docker", "inspect", result, "--format",
                      '{{index .Config.Labels "com.docker.compose.project"}}'])
    if labels != project_for(identifier):
        fail("Refusing to inspect an unowned DB container")
    return result


def pg_query(container, sql):
    return command(["docker", "exec", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                    "-U", DB_USER, "-d", DB_NAME, "-Atqc", sql], timeout=80)


def catalog_inventory(container):
    rows = pg_query(container, """SELECT json_build_object(
      'identities', (SELECT coalesce(json_agg(json_build_array(id,public_id,type_slug)
                                   ORDER BY id::text),'[]'::json) FROM config_catalogitem),
      'history', (SELECT coalesce(json_agg(json_build_array(id,md5(row_to_json(r)::text))
                                  ORDER BY id::text),'[]'::json) FROM config_catalogrevision r)
    )::text""")
    return json.loads(rows)


def check_migrated(before, after, original, previous, execution):
    changed = execution.get("changed")
    if execution.get("status") != "passed" or not isinstance(changed, int) or changed < 0:
        fail("Registered migration did not return a valid success record")
    for key in ("item_count", "model_count", "schema_versions", "schema_hashes",
                "hrid_digest", "evidence_db_references"):
        if before.get(key) != after.get(key):
            fail("Migration changed protected identity/schema/evidence field: " + key)
    if after.get("revision_count") != before.get("revision_count") + changed:
        fail("Migration revision count does not match append-only delta")
    if after.get("audit_count") != before.get("audit_count") + changed:
        fail("Migration audit count does not match append-only delta")
    for key in ("invalid_ids", "invalid_revision_links", "orphan_revisions"):
        if after.get(key) != 0:
            fail("Staging integrity failure: " + key)
    if original["identities"] != previous["identities"]:
        fail("Staging changed permanent catalog identities")
    old_revisions = {str(row[0]): row[1] for row in original["history"]}
    new_revisions = {str(row[0]): row[1] for row in previous["history"]}
    if any(new_revisions.get(key) != value for key, value in old_revisions.items()):
        fail("Staging modified historical immutable revisions")
    if len(new_revisions) != len(old_revisions) + changed:
        fail("Staging revision inventory has unexpected delta")


def create(snapshot, *, port=18081):
    dump, backup = snapshot_for(snapshot)
    commit = build_identity()
    identifier = secrets.token_hex(8)
    if not 1024 <= port <= 65535 or port == 8080:
        fail("Stage port must be a dedicated non-production loopback port")
    validate_environment(identifier)
    folder = candidate_dir(identifier)
    folder.mkdir(mode=0o700, exist_ok=False)
    credentials = staging_environment(folder, identifier, port)
    report = {
        "candidate_id": identifier, "project": project_for(identifier),
        "status": "preparing", "created_at": now(),
        "snapshot": str(dump), "snapshot_id": backup["backup_id"],
        "snapshot_manifest_sha256": db.hash_file(full.sibling(dump, ".full.json")),
        "snapshot_dump_sha256": backup["database"]["sha256"],
        "snapshot_evidence_sha256": backup["evidence_archive"]["sha256"],
        "baseline_inspection": backup["restored_inspection"],
        "migration": MIGRATION, "migration_sha256": db.hash_file(MIGRATION_FILE),
        "application_commit": commit, "source_schema_versions": backup["restored_inspection"]["schema_versions"],
        "port": port, "url": "http://127.0.0.1:" + str(port) + "/?mode=server",
        "runtime_sha256": runtime_checksum(folder), "verdict": None,
    }
    save_report(folder, report)
    try:
        compose(folder, ["up", "-d", "--wait", "db"], timeout=300)
        container = db_container(folder)
        command(["docker", "exec", "-i", container, "pg_restore", "--exit-on-error",
                 "--single-transaction", "--no-owner", "--no-privileges",
                 "-U", DB_USER, "-d", DB_NAME], input_file=dump, timeout=900)
        baseline = db.inspect_restored(container)
        if baseline != backup["restored_inspection"]:
            fail("Restored staging database fingerprint differs from verified source")
        blobs = full.database_evidence(container)
        if blobs != backup["blobs"]:
            fail("Evidence references differ from coordinated recovery snapshot")
        extracted = folder / "evidence-input"
        full.listing(full.sibling(dump, ".blobs.tar"), blobs, destination=extracted)
        name = volume_name(identifier, "evidence")
        assert_owned(identifier)
        command(["docker", "volume", "create",
                 "--label", "com.docker.compose.project=" + project_for(identifier),
                 "--label", "com.docker.compose.volume=evidence", name], timeout=30)
        assert_owned(identifier)
        command(["docker", "run", "--rm", "--network", "none",
                 "--mount", "type=volume,source=" + name + ",target=/evidence",
                 "--mount", "type=bind,source=" + str(extracted) + ",target=/input,readonly",
                 "busybox:1.36", "sh", "-ec",
                 "cp -a /input/. /evidence/ && chown -R 10001:10001 /evidence"], timeout=180)
        compose(folder, ["up", "-d", "--build", "--wait", "api"], timeout=600)
        original_history = catalog_inventory(container)
        raw = compose(folder, ["exec", "-T", "api", "python", "manage.py",
                               "stage_model_v1_to_v2", "--json"], timeout=180)
        execution = json.loads(raw.splitlines()[-1])
        after = db.inspect_restored(container)
        final_history = catalog_inventory(container)
        check_migrated(baseline, after, original_history, final_history, execution)
        # Validate actual protected Django download against the isolated copied bytes.
        if blobs:
            compose(folder, ["exec", "-T", "api", "python", "manage.py",
                             "shell", "-c", full.APP_TEST], timeout=180)
        compose(folder, ["up", "-d", "--wait", "web"], timeout=180)
        folder.joinpath("evidence-input").exists() and __import__("shutil").rmtree(extracted)
        report.update(status="awaiting-frontend-review", migrated=execution,
                      final_inspection=after, automated_checks="passed",
                      opened_at=now())
        save_report(folder, report)
        return report
    except Exception as error:
        report.update(status="failed", error=str(error), failed_at=now(),
                      automated_checks="failed")
        save_report(folder, report)
        # Failure leaves an explicitly FAILED candidate for safe investigation/discard.
        raise


def verdict(identifier, decision, notes, frontend_checked=False):
    folder, report = check_state(identifier)
    if decision not in ("accepted", "rejected") or not notes.strip():
        fail("Verdict and substantive notes are required")
    if report["status"] != "awaiting-frontend-review" or report.get("verdict") is not None:
        fail("Cannot judge a failed, discarded or previously judged candidate")
    if decision == "accepted" and not frontend_checked:
        fail("Acceptance requires explicit real-frontend inspection acknowledgement")
    if build_identity() != report["application_commit"]:
        fail("The application build changed since the stage was created")
    dump, source = snapshot_for(report["snapshot"])
    if (source["backup_id"] != report["snapshot_id"] or
            db.hash_file(full.sibling(dump, ".full.json")) != report["snapshot_manifest_sha256"]):
        fail("The verified source snapshot has changed")
    record = {"decision": decision, "notes": notes.strip(),
              "frontend_checked": bool(frontend_checked), "recorded_at": now(),
              "candidate_id": identifier, "application_commit": report["application_commit"],
              "migration": MIGRATION, "migration_sha256": report["migration_sha256"],
              "snapshot_id": report["snapshot_id"], "snapshot_manifest_sha256": report["snapshot_manifest_sha256"]}
    path = folder / "verdict.json"
    if path.exists():
        fail("Immutable verdict already exists")
    with open(path, "x", encoding="utf-8") as output:
        output.write(json.dumps(record, sort_keys=True, indent=2) + "\n")
        output.flush()
        os.fsync(output.fileno())
    report.update(verdict=record, status=decision)
    save_report(folder, report)
    return report


def discard(identifier):
    folder, report = check_state(identifier)
    assert_owned(identifier)
    # Avoid any caller-supplied project, db or volume; only this exact candidate.
    if (folder / "runtime.env").is_file():
        compose(folder, ["down", "--remove-orphans"], timeout=180)
    assert_owned(identifier)
    for kind in ("pgdata", "evidence"):
        name = volume_name(identifier, kind)
        if docker_volume_label(name) == project_for(identifier):
            command(["docker", "volume", "rm", name], timeout=60)
    assert_owned(identifier, absent=True)
    for name in ("runtime.env", "prototype.html"):
        (folder / name).unlink(missing_ok=True)
    extracted = folder / "evidence-input"
    if extracted.exists():
        __import__("shutil").rmtree(extracted)
    report.update(discarded_at=now(), status="discarded",
                  prior_status=report["status"])
    # Retain report and immutable verdict; never touch the original backup.
    report.pop("runtime_sha256", None)
    save_report(folder, report)
    return report


def recreate(identifier, *, port=None):
    folder, old = check_state(identifier)
    source = old["snapshot"]
    actual_port = port if port is not None else old["port"]
    discard(identifier)
    return create(source, port=actual_port)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    make = commands.add_parser("create")
    make.add_argument("--snapshot", required=True, help="Exact named FULL .dump recovery point")
    make.add_argument("--port", type=int, default=18081)
    for action in ("status", "discard", "recreate"):
        p = commands.add_parser(action)
        p.add_argument("candidate")
        if action == "recreate":
            p.add_argument("--port", type=int)
    judge = commands.add_parser("verdict")
    judge.add_argument("candidate")
    judge.add_argument("decision", choices=("accepted", "rejected"))
    judge.add_argument("--notes", required=True)
    judge.add_argument("--frontend-checked", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "create":
            result = create(args.snapshot, port=args.port)
        elif args.action == "status":
            folder = candidate_dir(args.candidate)
            report_file = folder / "report.json"
            if not report_file.is_file() or report_file.is_symlink():
                fail("Unknown candidate")
            result = json.loads(report_file.read_text("utf-8"))
        elif args.action == "discard":
            result = discard(args.candidate)
        elif args.action == "recreate":
            result = recreate(args.candidate, port=args.port)
        else:
            result = verdict(args.candidate, args.decision, args.notes, args.frontend_checked)
        print(json.dumps(result, sort_keys=True))
    except (db.RecoveryError, OSError, KeyError, ValueError, json.JSONDecodeError,
            subprocess.SubprocessError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, sort_keys=True), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
