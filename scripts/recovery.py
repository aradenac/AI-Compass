#!/usr/bin/env python3
"""PLAT-34: durable, independently verified PostgreSQL recovery points.

Python standard library only; invokes Docker explicitly and never targets the
running PostgreSQL service for writes. Demo localStorage is not involved.
"""
import argparse
import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
FORMAT = "ai-compass-postgres-v1"
PG_IMAGE = "postgres:17-alpine"
DUMP_PATTERN = re.compile(r"^ai-compass-\d{8}T\d{6}Z-[0-9a-f]{12}\.dump$")
RESTORE_DB = "ai_compass_restore_verify"
RESTORE_USER = "ai_compass_restore"
# Pin the exact repository Compose project instead of trusting caller cwd/env flags.
COMPOSE = ["docker", "compose", "--project-directory", str(ROOT),
           "-f", str(ROOT / "compose.yaml"), "-p", "ai-compass"]
INSPECT_SQL = """
SELECT json_build_object(
 'model_count', (SELECT count(*) FROM config_catalogitem WHERE type_slug='model'),
 'item_count', (SELECT count(*) FROM config_catalogitem),
 'revision_count', (SELECT count(*) FROM config_catalogrevision),
 'audit_count', (SELECT count(*) FROM config_catalogauditevent),
 'schema_versions', (SELECT coalesce(json_agg(type_slug || ':' || version ORDER BY type_slug, version), '[]'::json) FROM config_objecttypeversion),
 'schema_definitions', (SELECT coalesce(json_agg(json_build_object(
   'type', type_slug, 'version', version, 'schema', json_schema)
   ORDER BY type_slug, version), '[]'::json) FROM config_objecttypeversion),
 'migration_count', (SELECT count(*) FROM django_migrations),
 'hrid_digest', (SELECT md5(coalesce(string_agg(public_id, '|' ORDER BY public_id), '')) FROM config_catalogitem),
 'revision_digest', (SELECT md5(coalesce(string_agg(r.id::text || ':' || r.number::text || ':' || r.schema_version_id::text || ':' || r.display_name || ':' || r.properties::text, '|' ORDER BY r.id::text), '')) FROM config_catalogrevision r),
 'invalid_ids', (SELECT count(*) FROM config_catalogitem WHERE type_slug='model' AND public_id !~ '^mdl-[a-z]+(-[a-z]+){2}$'),
 'invalid_revision_links', (SELECT count(*) FROM config_catalogitem i WHERE i.current_revision_id IS NULL OR NOT EXISTS
     (SELECT 1 FROM config_catalogrevision r WHERE r.id=i.current_revision_id AND r.item_id=i.id
       AND r.number=(SELECT max(rr.number) FROM config_catalogrevision rr WHERE rr.item_id=i.id))),
 'orphan_revisions', (SELECT count(*) FROM config_catalogrevision r WHERE NOT EXISTS (SELECT 1 FROM config_catalogitem i WHERE i.id=r.item_id))
)::text;
"""


class RecoveryError(RuntimeError):
    pass


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(cmd, *, input_file=None, timeout=600, capture=True):
    try:
        with (open(input_file, "rb") if input_file is not None else contextlib.nullcontext()) as stream:
            result = subprocess.run(
                cmd, stdin=stream, stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.PIPE, timeout=timeout, check=False, cwd=ROOT
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RecoveryError("Command unavailable or timed out: " + str(error)) from error
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace")[-1200:].strip()
        raise RecoveryError("Command failed (exit " + str(result.returncode) + "): " + message)
    return (result.stdout or b"").decode("utf-8", "replace").strip()


def hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def durable_write(path, data):
    """Atomic replace + fsync; no successful metadata for an incomplete file."""
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data if isinstance(data, bytes) else data.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        fsync_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def fsync_dir(directory):
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def json_bytes(data):
    return (json.dumps(data, sort_keys=True, indent=2) + "\n").encode("utf-8")


def destinations(args, *, for_backup=False):
    explicit = args.destination is not None or "AI_COMPASS_BACKUP_DIR" in os.environ
    value = args.destination or os.environ.get("AI_COMPASS_BACKUP_DIR") or str(ROOT / ".local/backups")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    if path.is_symlink():
        raise RecoveryError("Refusing symlink backup destination")
    if not path.exists() and not explicit and for_backup:
        path.mkdir(mode=0o700, parents=True)
    if not path.is_dir():
        raise RecoveryError("Backup destination does not exist or is unavailable: " + str(path))
    path = path.resolve()
    if for_backup:
        if args.require_external and path.stat().st_dev == ROOT.stat().st_dev:
            raise RecoveryError("Required independent destination is on the same filesystem as the application")
        if not os.access(path, os.W_OK):
            raise RecoveryError("Backup destination is not writable: " + str(path))
        if path.stat().st_dev == ROOT.stat().st_dev:
            print("WARNING: backup on the same filesystem is NOT protection against host/disk loss", file=sys.stderr)
    return path


def validate_dump_path(path):
    path = Path(path).expanduser().resolve()
    if not DUMP_PATTERN.fullmatch(path.name):
        raise RecoveryError("Only completed AI Compass .dump recovery-point filenames are accepted")
    return path


def verify(path):
    """Purely offline verification: no PostgreSQL, Docker or network needed."""
    path = validate_dump_path(path)
    manifest_path = Path(str(path) + ".json")
    marker_path = Path(str(path) + ".complete")
    if not path.is_file() or not manifest_path.is_file() or not marker_path.is_file():
        raise RecoveryError("Incomplete recovery point (dump, manifest or completion marker missing)")
    try:
        raw = manifest_path.read_bytes()
        manifest = json.loads(raw)
    except (ValueError, OSError) as error:
        raise RecoveryError("Unreadable recovery manifest: " + str(error)) from error
    if (manifest.get("format") != FORMAT or manifest.get("dump_file") != path.name
            or manifest.get("status") != "verified" or not manifest.get("restored_at")
            or manifest.get("evidence", {}).get("included") is not False):
        raise RecoveryError("Invalid or unsupported recovery-point metadata")
    if marker_path.read_text("ascii").strip() != hashlib.sha256(raw).hexdigest():
        raise RecoveryError("Recovery manifest checksum differs from completion marker")
    if path.stat().st_size != manifest.get("dump_bytes") or hash_file(path) != manifest.get("sha256"):
        raise RecoveryError("PostgreSQL dump checksum/size mismatch")
    return manifest


def database_metadata():
    name = run(COMPOSE + ["exec", "-T", "db", "sh", "-ec", 'printf %s "$POSTGRES_DB"'])
    version = run(COMPOSE + ["exec", "-T", "db", "sh", "-ec",
                   'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SHOW server_version"'])
    if not name or len(name) > 100:
        raise RecoveryError("Cannot identify source database")
    return name, version


def inspect_restored(container):
    query = run(["docker", "exec", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                 "-U", RESTORE_USER, "-d", RESTORE_DB, "-Atqc", INSPECT_SQL])
    try:
        info = json.loads(query)
    except ValueError as error:
        raise RecoveryError("Cannot parse isolated recovery integrity query") from error
    # Individual SHA-256 digests are derived from the *restored* point-in-time
    # database, never from a subsequent query against the live source. Thus an
    # active Model/schema change after pg_dump cannot skew the manifest.
    definitions = info.pop("schema_definitions", [])
    if not isinstance(definitions, list):
        raise RecoveryError("Invalid restored schema definition list")
    info["schema_hashes"] = [
        {"type": entry["type"], "version": entry["version"],
         "sha256": hashlib.sha256(json.dumps(
             entry["schema"], sort_keys=True, ensure_ascii=False,
             separators=(",", ":")
         ).encode("utf-8")).hexdigest()}
        for entry in definitions
    ]
    for check in ("invalid_ids", "invalid_revision_links", "orphan_revisions"):
        if info[check] != 0:
            raise RecoveryError("Restored catalog integrity failed: " + check + "=" + str(info[check]))
    marker_table = run(["docker", "exec", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                        "-U", RESTORE_USER, "-d", RESTORE_DB, "-Atqc",
                        "SELECT to_regclass('public.ai_compass_smoke_marker') IS NOT NULL"])
    info["smoke_marker"] = (run(["docker", "exec", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                                 "-U", RESTORE_USER, "-d", RESTORE_DB, "-Atqc",
                                 "SELECT marker FROM public.ai_compass_smoke_marker ORDER BY marker LIMIT 1"])
                            if marker_table == "t" else None)
    return info


def restore_isolated(dump, *, verifier=None):
    """No prod volumes/network; optional CI-only verifier sees disposable DB before cleanup."""
    container = "ai-compass-drill-" + secrets.token_hex(10)
    password = secrets.token_urlsafe(30)
    started = False
    try:
        run(["docker", "run", "--rm", "--detach", "--name", container,
             "--network", "none", "--security-opt", "no-new-privileges",
             "-e", "POSTGRES_DB=" + RESTORE_DB, "-e", "POSTGRES_USER=" + RESTORE_USER,
             "-e", "POSTGRES_PASSWORD=" + password, PG_IMAGE], timeout=90)
        started = True
        for _ in range(45):
            try:
                run(["docker", "exec", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                     "-U", RESTORE_USER, "-d", RESTORE_DB, "-Atqc", "SELECT 1"], timeout=8)
                break
            except RecoveryError:
                time.sleep(1)
        else:
            raise RecoveryError("Isolated PostgreSQL did not become ready")
        run(["docker", "exec", "-i", container, "pg_restore", "--exit-on-error",
             "--single-transaction", "--no-owner", "--no-privileges",
             "-U", RESTORE_USER, "-d", RESTORE_DB], input_file=dump)
        inspection = inspect_restored(container)
        if verifier is not None:
            verifier(container, inspection)  # errors still force-remove the temporary DB
        return inspection
    finally:
        if started:
            try:
                run(["docker", "rm", "--force", container], timeout=30)
            except RecoveryError as error:
                # Refuse to claim a clean drill if a disposable DB was left behind.
                raise RecoveryError("Could not remove isolated restore container: " + str(error)) from error


def report_file(directory, report):
    reports = directory / "reports"
    reports.mkdir(mode=0o700, exist_ok=True)
    name = "drill-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + secrets.token_hex(4) + ".json"
    durable_write(reports / name, json_bytes(report))
    return reports / name


def drill(path, *, record=True):
    started = utc_now()
    result = {"action": "restore-drill", "started_at": started,
              "dump_file": str(path), "status": "failed"}
    try:
        manifest = verify(path)
        result["backup_id"] = manifest["backup_id"]
        inspection = restore_isolated(path)
        # Prove each source snapshot remains identical on a repeated restoration.
        if inspection != manifest["restored_inspection"]:
            raise RecoveryError("Restored object/revision/schema fingerprint differs from verified baseline")
        result.update(status="passed", inspection=inspection, finished_at=utc_now())
    except (RecoveryError, OSError, KeyError, ValueError) as error:
        result.update(error=str(error), finished_at=utc_now())
    if record:
        result["report_path"] = str(report_file(Path(path).resolve().parent, result))
    return result


def backup(args):
    directory = destinations(args, for_backup=True)
    lockfile = directory / ".ai-compass-backup.lock"
    with open(lockfile, "a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(6)
        filename = "ai-compass-" + identifier + ".dump"
        target = directory / filename
        partial = directory / ("." + filename + ".partial")
        manifest_path = Path(str(target) + ".json")
        marker_path = Path(str(target) + ".complete")
        stage = "starting"
        try:
            source_name, pg_version = database_metadata()
            stage = "dumping"
            with open(partial, "xb") as output:
                output.flush()
                os.fchmod(output.fileno(), 0o600)
                command = COMPOSE + ["exec", "-T", "db", "sh", "-ec",
                           'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom']
                subprocess_run_dump(command, output)
                output.flush()
                os.fsync(output.fileno())
            if partial.stat().st_size < 100:
                raise RecoveryError("Truncated or empty PostgreSQL dump")
            # A pg_restore list check is useful but cannot replace a full restore drill.
            stage = "checking-archive"
            run(["docker", "run", "--rm", "--network", "none", "-i", PG_IMAGE,
                 "pg_restore", "--list"], input_file=partial)
            stage = "rehearsing-restore"
            inspection = restore_isolated(partial)
            stage = "committing"
            app_revision = run(["git", "rev-parse", "HEAD"])
            metadata = {
                "format": FORMAT, "status": "verified", "backup_id": identifier,
                "dump_file": filename, "sha256": hash_file(partial),
                "dump_bytes": partial.stat().st_size, "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "database": source_name, "postgres_version": pg_version,
                "app_git_sha": app_revision, "schema_versions": inspection["schema_versions"],
                "restored_at": utc_now(), "restored_inspection": inspection,
                "evidence": {"included": False, "generation": None, "blob_hashes": None,
                             "future_contract": "coordinated-db-evidence-v2 (#17/#29)"}
            }
            os.replace(partial, target)
            durable_write(manifest_path, json_bytes(metadata))
            durable_write(marker_path, hashlib.sha256(manifest_path.read_bytes()).hexdigest() + "\n")
            fsync_dir(directory)
            # A second independent offline read proves committed metadata and checksum.
            verify(target)
            retain(directory, args.keep)
            return target
        except (RecoveryError, OSError, ValueError, subprocess.SubprocessError) as error:
            # Never report a half-written dump as a good recovery point.
            for pending in (partial, marker_path, manifest_path, target):
                if pending.exists():
                    pending.unlink()
            failure = {"status": "failed", "backup_id": identifier, "stage": stage,
                       "failed_at": utc_now(), "error": str(error)}
            try:
                durable_write(directory / ("ai-compass-" + identifier + ".failed.json"), json_bytes(failure))
            except OSError:
                print(json.dumps(failure), file=sys.stderr)
            raise RecoveryError(stage + ": " + str(error)) from error


def subprocess_run_dump(cmd, output):
    try:
        p = subprocess.run(cmd, stdout=output, stderr=subprocess.PIPE, timeout=600, check=False, cwd=ROOT)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RecoveryError("pg_dump unavailable or timed out: " + str(error)) from error
    if p.returncode:
        raise RecoveryError("pg_dump failed: " + p.stderr.decode("utf-8", "replace")[-1000:])


def verified_entries(directory):
    """Use the verified manifest timestamp, never randomized filename order."""
    entries = []
    for path in directory.glob("ai-compass-*.dump"):
        try:
            metadata = verify(path)
            entries.append((metadata, path))
        except (RecoveryError, OSError, ValueError):
            continue
    entries.sort(key=lambda row: (row[0].get("created_at", ""), row[0]["backup_id"]), reverse=True)
    return entries


def retain(directory, keep):
    if keep < 1:
        raise RecoveryError("Retention must retain at least one last-good snapshot")
    old_snapshots = verified_entries(directory)[keep:]
    for _, old in old_snapshots:
        for file in (old, Path(str(old) + ".json"), Path(str(old) + ".complete")):
            file.unlink()
    if old_snapshots:
        fsync_dir(directory)


def status(directory):
    good = verified_entries(directory)
    failures = sorted(directory.glob("ai-compass-*.failed.json"), reverse=True)
    return {"status": "ok" if good else "no-verified-recovery-point",
            "last_good_backup": good[0][0] if good else None,
            "verified_count": len(good), "failed_backup_count": len(failures),
            "last_failure": json.loads(failures[0].read_text("utf-8")) if failures else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", help="Existing backup directory (absolute or relative to repository)")
    parser.add_argument("--require-external", action="store_true", help="Fail if destination shares the application filesystem")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("backup", help="Snapshot, restore to isolated Postgres, commit atomically, retain")
    p.add_argument("--keep", type=int, default=int(os.environ.get("AI_COMPASS_BACKUP_KEEP", "14")))
    for name in ("verify", "drill"):
        command = sub.add_parser(name)
        command.add_argument("dump")
        command.add_argument("--json", action="store_true")
    sub.add_parser("status").add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "backup":
            if args.keep < 1:
                raise RecoveryError("--keep must be >= 1")
            target = backup(args)
            print(target)
        elif args.action == "verify":
            result = verify(args.dump)
            print(json.dumps(result, sort_keys=True) if args.json else "Offline checksum PASSED: " + args.dump)
        elif args.action == "drill":
            result = drill(validate_dump_path(args.dump))
            print(json.dumps(result, sort_keys=True) if args.json else
                  "Isolated restore " + result["status"].upper() + ": " + result.get("report_path", result.get("error", "")))
            if result["status"] != "passed":
                raise RecoveryError(result.get("error", "Isolated restore failed"))
        elif args.action == "status":
            result = status(destinations(args))
            print(json.dumps(result, sort_keys=True) if args.json else
                  ("Last good snapshot: " + str(result["last_good_backup"]["dump_file"])
                   if result["last_good_backup"] else "No verified recovery point"))
            if result["status"] != "ok":
                raise RecoveryError("No verified backup is available")
    except (RecoveryError, OSError, ValueError, KeyError) as error:
        print("RECOVERY ERROR: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
