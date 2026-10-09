#!/usr/bin/env python3
"""PLAT-29: verified, coordinated PostgreSQL + immutable evidence recovery.

Only the *running API process* is stopped for the DB+blob capture boundary.
Every drill uses a new networkless PostgreSQL container and an independent
staged evidence directory; never mounts or modifies any live source volume.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

import recovery as db

FORMAT = "ai-compass-full-v1"
VOLUME = "ai-compass_evidence"
MAX_BLOB = 64 * 1024 * 1024
MAX_AGE_HOURS = 36
APP_TEST = r"""
import hashlib
from config.models import EvidenceLink
from django.test import Client
links = EvidenceLink.objects.select_related("uploaded_by").order_by("created_at")
if links.exists():
    link = links.first()
    client = Client()
    client.force_login(link.uploaded_by)
    response = client.get("/api/v1/evidence/%s/download" % link.id)
    assert response.status_code == 200, "Restored authenticated download failed"
    payload = b"".join(response.streaming_content)
    assert hashlib.sha256(payload).hexdigest() == link.blob_id
    assert len(payload) == link.blob.size
    assert "attachment" in response["Content-Disposition"]
print("Restored isolated Django API original-byte download PASS")
"""


def fail(message):
    raise db.RecoveryError(message)


def sibling(dump, suffix):
    return Path(str(dump) + suffix)


def paths(dump):
    dump = db.validate_dump_path(dump)
    return dump, sibling(dump, ".blobs.tar"), sibling(dump, ".full.json"), sibling(dump, ".full.complete")


def digest_stream(stream):
    h = hashlib.sha256()
    count = 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        h.update(block)
        count += len(block)
    return h.hexdigest(), count


def listing(archive, expected, *, destination=None):
    """Reject path traversal, symlinks, unexpected/duplicate bytes and missing data."""
    expected = {x["sha256"]: x["size"] for x in expected}
    seen = set()
    if destination:
        destination.mkdir(mode=0o755, parents=True, exist_ok=False)
    with tarfile.open(archive, "r:*") as tar:
        for member in tar:
            if member.isdir() and (member.name.rstrip("/") in (".", "blobs") or
                re.fullmatch(r"blobs/[0-9a-f]{2}(/[0-9a-f]{2})?", member.name.rstrip("/"))):
                continue
            if not member.isfile():
                fail("Unsafe/non-file evidence archive member: " + member.name)
            match = re.fullmatch(r"blobs/([0-9a-f]{2})/([0-9a-f]{2})/([0-9a-f]{64})", member.name)
            if not match:
                fail("Unsafe or unexpected evidence archive path: " + member.name)
            sha = match.group(3)
            if sha[:2] != match.group(1) or sha[2:4] != match.group(2):
                fail("Wrong evidence hash namespace")
            if sha not in expected or sha in seen:
                fail("Unreferenced or duplicate blob in full recovery archive")
            if member.size != expected[sha] or member.size > MAX_BLOB or member.size < 1:
                fail("Evidence file size differs from restored DB metadata")
            source = tar.extractfile(member)
            if source is None:
                fail("Cannot stream tar member")
            destination_file = None
            if destination:
                directory = destination / "blobs" / sha[:2] / sha[2:4]
                directory.mkdir(parents=True, mode=0o755, exist_ok=True)
                (destination / "blobs").chmod(0o755)
                (destination / "blobs" / sha[:2]).chmod(0o755)
                directory.chmod(0o755)
                destination_file = open(directory / sha, "xb")
            digest = hashlib.sha256()
            size = 0
            try:
                with source:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(block)
                        size += len(block)
                        if destination_file:
                            destination_file.write(block)
                if destination_file:
                    destination_file.flush()
                    os.fsync(destination_file.fileno())
                    os.fchmod(destination_file.fileno(), 0o644)
            finally:
                if destination_file:
                    destination_file.close()
            if size != expected[sha] or digest.hexdigest() != sha:
                fail("Corrupt/mismatched blob content: " + sha)
            seen.add(sha)
    if seen != set(expected):
        fail("Missing referenced evidence blobs in coordinated recovery point")
    return sorted(seen)


def verified_manifest(path):
    dump, archive, manifest_file, marker = paths(path)
    if not all(p.is_file() and not p.is_symlink() for p in (dump, archive, manifest_file, marker)):
        fail("Incomplete coordinated recovery point (dump, blobs, manifest, completion)")
    raw = manifest_file.read_bytes()
    try:
        manifest = json.loads(raw)
    except (ValueError, UnicodeError):
        fail("Invalid coordinated recovery metadata")
    if (manifest.get("format") != FORMAT or manifest.get("status") != "verified"
            or manifest.get("dump_file") != dump.name or
            manifest.get("blobs_file") != archive.name or
            manifest.get("backup_id") != dump.name.removeprefix("ai-compass-").removesuffix(".dump")
            or not manifest.get("created_at")):
        fail("Mismatched coordinated recovery manifest")
    if marker.read_text("ascii").strip() != hashlib.sha256(raw).hexdigest():
        fail("Coordinated completion marker checksum mismatch")
    for key, file in (("database", dump), ("evidence_archive", archive)):
        record = manifest.get(key, {})
        if file.stat().st_size != record.get("bytes") or db.hash_file(file) != record.get("sha256"):
            fail("Missing, stale or corrupt " + key + " archive")
    blobs = manifest.get("blobs", [])
    if not isinstance(blobs, list) or len({b.get("sha256") for b in blobs}) != len(blobs):
        fail("Invalid/duplicate blob manifest")
    inspection = manifest.get("restored_inspection", {}).get("evidence_db_references", {})
    if set(inspection.get("sha256", [])) != {b.get("sha256") for b in blobs}:
        fail("Evidence inventory differs from restored DB references")
    if len(blobs) != inspection.get("blob_count") or manifest.get("link_count") != inspection.get("link_count"):
        fail("Evidence counts differ from recovered snapshot")
    listing(archive, blobs)
    return manifest


def database_evidence(container):
    sql = """SELECT json_build_object(
     'blobs', (SELECT coalesce(json_agg(json_build_object('sha256',sha256,'size',size)
                        ORDER BY sha256), '[]'::json) FROM config_evidenceblob),
     'bad_links', (SELECT count(*) FROM config_evidencelink l LEFT JOIN
                        config_catalogrevision r ON r.id=l.revision_id
                   WHERE l.revision_id IS NOT NULL AND
                       (r.id IS NULL OR r.item_id <> l.item_id))
    )::text;"""
    payload = db.run(["docker", "exec", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                      "-U", db.RESTORE_USER, "-d", db.RESTORE_DB, "-Atqc", sql])
    parsed = json.loads(payload)
    if parsed["bad_links"]:
        fail("Restored evidence revision links are mismatched")
    return parsed["blobs"]


def disposable_restore(dump, blobs_archive, *, expected=None, use_api=True):
    """Full restore in a container namespace with no prod network/volume mounts."""
    container = "ai-compass-full-drill-" + secrets.token_hex(9)
    password = secrets.token_urlsafe(30)
    started = False
    with tempfile.TemporaryDirectory(prefix="ai-compass-recovered-") as folder:
        restored_root = Path(folder) / "evidence"
        try:
            db.run(["docker", "run", "--rm", "--detach", "--name", container,
                    "--network", "none", "--security-opt", "no-new-privileges",
                    "-e", "POSTGRES_DB=" + db.RESTORE_DB,
                    "-e", "POSTGRES_USER=" + db.RESTORE_USER,
                    "-e", "POSTGRES_PASSWORD=" + password, db.PG_IMAGE], timeout=90)
            started = True
            for _ in range(45):
                try:
                    db.run(["docker", "exec", container, "psql", "-X", "-v", "ON_ERROR_STOP=1",
                            "-U", db.RESTORE_USER, "-d", db.RESTORE_DB, "-Atqc", "SELECT 1"], timeout=8)
                    break
                except db.RecoveryError:
                    time.sleep(1)
            else:
                fail("Disposable recovery PostgreSQL did not start")
            db.run(["docker", "exec", "-i", container, "pg_restore", "--exit-on-error",
                    "--single-transaction", "--no-owner", "--no-privileges",
                    "-U", db.RESTORE_USER, "-d", db.RESTORE_DB], input_file=dump)
            inspection = db.inspect_restored(container)
            if "evidence_db_references" not in inspection:
                fail("This database schema has no evidence registry; full recovery is unsupported")
            blobs = database_evidence(container)
            if expected and (expected["restored_inspection"] != inspection or expected["blobs"] != blobs):
                fail("Restored IDs/revisions/schema/evidence differ from recovery manifest")
            listing(blobs_archive, blobs, destination=restored_root)
            if use_api and blobs:
                image = db.run(db.COMPOSE + ["images", "-q", "api"]).splitlines()
                if len(image) != 1 or not image[0].strip():
                    fail("No built API image available for isolated download acceptance")
                output = db.run(["docker", "run", "--rm", "--network", "container:" + container,
                         "--security-opt", "no-new-privileges",
                         "--mount", "type=bind,source=" + str(restored_root) +
                            ",target=/var/lib/ai-compass/evidence,readonly",
                         "-e", "DB_HOST=127.0.0.1", "-e", "DB_NAME=" + db.RESTORE_DB,
                         "-e", "DB_USER=" + db.RESTORE_USER, "-e", "DB_PASSWORD=" + password,
                         "-e", "DJANGO_SECRET_KEY=" + secrets.token_urlsafe(36),
                         "-e", "DJANGO_ALLOWED_HOSTS=testserver,localhost,127.0.0.1",
                         "-e", "AI_COMPASS_EVIDENCE_ROOT=/var/lib/ai-compass/evidence",
                         image[0], "python", "manage.py", "shell", "-c", APP_TEST], timeout=120)
                if "original-byte download PASS" not in output:
                    fail("Authenticated isolated API did not validate restored download")
            return {"inspection": inspection, "blobs": blobs,
                    "api_download": "passed" if use_api and blobs else "no-linked-files" if not blobs else "skipped"}
        finally:
            if started:
                db.run(["docker", "rm", "--force", container], timeout=40)


def _capture(source_command, target):
    with open(target, "xb") as out:
        os.fchmod(out.fileno(), 0o600)
        try:
            completed = subprocess.run(source_command, stdout=out, stderr=subprocess.PIPE,
                                       cwd=db.ROOT, check=False, timeout=900)
        except (OSError, subprocess.TimeoutExpired) as error:
            fail("Snapshot process interrupted: " + str(error))
        if completed.returncode:
            fail("Snapshot subprocess failed: " + completed.stderr.decode("utf-8", "replace")[-900:])
        out.flush()
        os.fsync(out.fileno())


def evidence_source():
    # Volume creation MUST be prohibited during backup: name and Compose project verified first.
    label = db.run(["docker", "volume", "inspect", VOLUME, "--format",
                    '{{index .Labels "com.docker.compose.project"}}'])
    if label != "ai-compass":
        fail("Operational evidence volume is missing or not owned by the expected Compose project")
    # Ensure the immutable blob directory exists on the actual mounted API volume.
    db.run(db.COMPOSE + ["exec", "-T", "api", "python", "-c",
                        "from config.evidence_store import store_root; "
                        "(store_root()/'blobs').mkdir(mode=0o700,exist_ok=True)"])


def capture_db_and_evidence(dump_tmp, blobs_tmp):
    db.run(db.COMPOSE + ["stop", "-t", "30", "api"], timeout=75)
    capture_error = None
    try:
        _capture(db.COMPOSE + ["exec", "-T", "db", "sh", "-ec",
                 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom'], dump_tmp)
        _capture(["docker", "run", "--rm", "--network", "none",
                  "--mount", "type=volume,source=" + VOLUME + ",target=/evidence,readonly",
                  db.PG_IMAGE, "tar", "-C", "/evidence", "-cf", "-", "blobs"], blobs_tmp)
    except Exception as error:
        capture_error = error
        raise
    finally:
        try:
            db.run(db.COMPOSE + ["start", "api"], timeout=120)
        except Exception as restore_error:
            # Fail closed even if the files were captured: service not resumed.
            fail("Source API did not restart after coordinated capture: " + str(restore_error))


def _new_id():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(6)


def full_entries(directory):
    result = []
    for dump in directory.glob("ai-compass-*.dump"):
        try:
            meta = verified_manifest(dump)
        except (db.RecoveryError, ValueError, OSError, tarfile.TarError):
            continue
        result.append((meta, dump))
    result.sort(key=lambda row: (row[0]["created_at"], row[0]["backup_id"]), reverse=True)
    return result


def full_backup(args):
    if not args.destination:
        fail("A pre-existing independent --destination is required for full recovery")
    ci_exception = (args.allow_local_ci and os.environ.get("GITHUB_ACTIONS") == "true"
                    and os.environ.get("AI_COMPASS_FULL_RECOVERY_CI") == "1")
    if args.allow_local_ci and not ci_exception:
        fail("Local-filesystem exception is permitted only for isolated CI")
    args.require_external = not ci_exception
    directory = db.destinations(args, for_backup=True)
    if directory.stat().st_dev == db.ROOT.stat().st_dev and not ci_exception:
        fail("Coordinated backups require an independent mounted filesystem")
    with open(directory / ".ai-compass-full.lock", "a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        recovery_id = _new_id()
        dump = directory / ("ai-compass-" + recovery_id + ".dump")
        archive = sibling(dump, ".blobs.tar")
        manifest_file = sibling(dump, ".full.json")
        marker = sibling(dump, ".full.complete")
        dump_partial = directory / ("." + dump.name + ".partial")
        blob_partial = directory / ("." + archive.name + ".partial")
        stage = "preflight"
        try:
            # Fail BEFORE pausing production when destinations/volume/image are unavailable.
            evidence_source()
            db.run(db.COMPOSE + ["images", "-q", "api"])
            stage = "capturing-locked-boundary"
            capture_db_and_evidence(dump_partial, blob_partial)
            stage = "rehearsing-independent-restoration"
            if dump_partial.stat().st_size < 100:
                fail("Truncated PostgreSQL dump")
            db.run(["docker", "run", "--rm", "--network", "none", "-i",
                    db.PG_IMAGE, "pg_restore", "--list"], input_file=dump_partial)
            restored = disposable_restore(dump_partial, blob_partial)
            stage = "committing"
            metadata = {
                "format": FORMAT, "status": "verified", "backup_id": recovery_id,
                "created_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                "restored_at": db.utc_now(), "app_git_sha": db.run(["git", "rev-parse", "HEAD"]),
                "scope": "postgresql+immutable-evidence",
                "dump_file": dump.name, "blobs_file": archive.name,
                "database": {"sha256": db.hash_file(dump_partial), "bytes": dump_partial.stat().st_size},
                "evidence_archive": {"sha256": db.hash_file(blob_partial), "bytes": blob_partial.stat().st_size},
                "restored_inspection": restored["inspection"], "blobs": restored["blobs"],
                "link_count": restored["inspection"]["evidence_db_references"]["link_count"],
                "api_download": restored["api_download"],
            }
            os.replace(dump_partial, dump)
            os.replace(blob_partial, archive)
            db.durable_write(manifest_file, db.json_bytes(metadata))
            db.durable_write(marker, hashlib.sha256(manifest_file.read_bytes()).hexdigest() + "\n")
            db.fsync_dir(directory)
            verified_manifest(dump)
            # Full points and legacy DB-only points have separate retention namespaces.
            for _, old in full_entries(directory)[args.keep:]:
                for piece in paths(old):
                    piece.unlink()
            db.fsync_dir(directory)
            return dump
        except Exception as error:
            for piece in (dump_partial, blob_partial, dump, archive, manifest_file, marker):
                piece.unlink(missing_ok=True)
            db.durable_write(directory / ("ai-compass-" + recovery_id + ".full.failed.json"),
                             db.json_bytes({"backup_id": recovery_id, "stage": stage,
                                            "status": "failed", "at": db.utc_now(),
                                            "error": str(error)}))
            if isinstance(error, db.RecoveryError):
                raise
            raise db.RecoveryError(stage + ": " + str(error)) from error


def full_drill(path):
    path = db.validate_dump_path(path)
    report = {"status": "failed", "started_at": db.utc_now(), "action": "full-restore"}
    try:
        metadata = verified_manifest(path)
        report["backup_id"] = metadata["backup_id"]
        restored = disposable_restore(path, sibling(path, ".blobs.tar"), expected=metadata)
        report.update(status="passed", restored=restored, finished_at=db.utc_now())
    except Exception as error:
        report.update(error=str(error), finished_at=db.utc_now())
    report["report_path"] = str(db.report_file(Path(path).resolve().parent, report))
    return report


def full_status(directory, fresh_hours=MAX_AGE_HOURS):
    entries = full_entries(directory)
    failures = sorted(directory.glob("ai-compass-*.full.failed.json"), reverse=True)
    reports = sorted((directory / "reports").glob("drill-*.json"), reverse=True) if (directory / "reports").exists() else []
    last = entries[0][0] if entries else None
    age = ((datetime.now(timezone.utc) - datetime.fromisoformat(last["created_at"])).total_seconds() / 3600
           if last else None)
    last_restore = None
    for path in reports:
        try:
            item = json.loads(path.read_text("utf-8"))
            if item.get("action") == "full-restore" and item.get("status") == "passed":
                last_restore = item
                break
        except (ValueError, OSError):
            continue
    return {"status": "ok" if last and age <= fresh_hours else
                      "stale" if last else "no-full-recovery-point",
            "scope": "postgresql+immutable-evidence",
            "last_good_backup": last, "last_good_age_hours": round(age, 2) if age is not None else None,
            "freshness_limit_hours": fresh_hours,
            "verified_count": len(entries), "failed_backup_count": len(failures),
            "last_failure": json.loads(failures[0].read_text("utf-8")) if failures else None,
            "last_successful_restore": last_restore}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", help="Pre-existing independently mounted backup directory")
    parser.add_argument("--require-external", action="store_true", default=True)
    parser.add_argument("--allow-local-ci", action="store_true",
                        help="Only for hosted CI validation, never for operational backups")
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("backup")
    p.add_argument("--keep", type=int, default=14)
    for action in ("verify", "drill"):
        sub.add_parser(action).add_argument("dump")
    sub.add_parser("status").add_argument("--fresh-hours", type=int, default=MAX_AGE_HOURS)
    args = parser.parse_args(argv)
    try:
        if args.action == "backup":
            if not 1 <= args.keep <= 365:
                fail("Retention must keep 1–365 complete snapshots")
            print(full_backup(args))
        elif args.action == "verify":
            metadata = verified_manifest(args.dump)
            print(json.dumps({"status": "verified", "backup_id": metadata["backup_id"],
                              "scope": metadata["scope"], "blob_count": len(metadata["blobs"])},
                             sort_keys=True))
        elif args.action == "drill":
            result = full_drill(Path(args.dump))
            print(json.dumps(result, sort_keys=True))
            if result["status"] != "passed":
                return 1
        elif args.action == "status":
            if args.fresh_hours < 1:
                fail("Freshness window must be >= 1 hour")
            if not args.destination:
                fail("--destination is required")
            result = full_status(db.destinations(args), args.fresh_hours)
            print(json.dumps(result, sort_keys=True))
            if result["status"] != "ok":
                return 1
    except (db.RecoveryError, OSError, ValueError, KeyError, tarfile.TarError) as error:
        print("FULL RECOVERY ERROR: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
