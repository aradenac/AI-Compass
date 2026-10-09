#!/usr/bin/env python3
"""Snapshot manifest + checksum helper for PLAT-34.

Run from the repository root. It coordinates three artefacts per backup:

    <dump>.dump            custom-format pg_dump
    <dump>.dump.sha256      checksum of the dump bytes
    <dump>.dump.manifest.json   timestamp, checksum, DB/schema/app revision, catalog summary

A dump is only "good" when the complete triplet exists and the manifest
``status`` is ``success``. A partial/failed backup never produces a manifest,
so it can never be mistaken for a last-good recovery point.

Subcommands:
    write <dump>            gather metadata and write <dump>.manifest.json
    verify <dump>           offline: recompute checksum + validate the triplet
    read <dump> --field F   print one manifest field for restore drills
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

MANIFEST_VERSION = 1
RESTORE_PREFIX = "ai_compass_restore_drill_"

# SQL run inside the db container to summarise catalog state. Values are read
# from the database the dump was taken from, so the manifest records exactly
# what a restore must reproduce. public_ids prove identity-level reproduction,
# not just counts; fk_orphans must be 0 (referential integrity). json_schema
# rows are fetched raw and hashed in Python so we never depend on pgcrypto.
CATALOG_SQL = r"""
SELECT jsonb_build_object(
  'items', (SELECT COUNT(*) FROM public.config_catalogitem),
  'revisions', (SELECT COUNT(*) FROM public.config_catalogrevision),
  'audit_events', (SELECT COUNT(*) FROM public.config_catalogauditevent),
  'public_ids', COALESCE(
    (SELECT jsonb_agg(public_id ORDER BY public_id) FROM public.config_catalogitem), '[]'::jsonb),
  'schema_rows', COALESCE((
    SELECT jsonb_agg(jsonb_build_object(
      'type_slug', type_slug, 'version', version,
      'json_schema', json_schema,
      'created_at', to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'))
      ORDER BY type_slug, version)
    FROM public.config_objecttypeversion), '[]'::jsonb),
  'fk_orphans', (
    SELECT COUNT(*) FROM public.config_catalogrevision r
    LEFT JOIN public.config_catalogitem i ON r.item_id = i.id
    LEFT JOIN public.config_objecttypeversion s ON r.schema_version_id = s.id
    LEFT JOIN public.auth_user u ON r.created_by_id = u.id
    WHERE i.id IS NULL OR s.id IS NULL OR u.id IS NULL),
  'latest_revision_at', (SELECT to_char(MAX(created_at) AT TIME ZONE 'UTC',
        'YYYY-MM-DD"T"HH24:MI:SS"Z"') FROM public.config_catalogrevision)
)::text;
"""


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _env_file() -> dict[str, str]:
    env: dict[str, str] = {}
    path = _repo_root() / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def _compose_exec(args: list[str], *, capturebytes: bool = False,
                  stdin: str | None = None) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "exec", "-T", *args]
    return subprocess.run(cmd, check=True, text=not capturebytes,
                          capture_output=True, cwd=str(_repo_root()),
                          input=stdin)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_sha() -> str | None:
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                check=True, capture_output=True, text=True,
                                cwd=str(_repo_root()))
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _gather_catalog(db_name: str, db_user: str) -> dict:
    # Pass SQL via stdin to avoid fragile shell quoting; -X disables .psqlrc.
    proc = _compose_exec(
        ["db", "sh", "-ec", f'psql -v ON_ERROR_STOP=1 -X -U "{db_user}" -d "{db_name}" -Atq'],
        stdin=CATALOG_SQL,
    )
    raw = proc.stdout.strip()
    if not raw:
        raise SystemExit("catalog summary query returned no rows; has migrate run?")
    summary = json.loads(raw)
    # Hash each schema row's json_schema in Python (no pgcrypto dependency).
    schema_versions = []
    for row in summary.get("schema_rows", []):
        schema_versions.append({
            "type_slug": row["type_slug"],
            "version": row["version"],
            "json_schema_sha256": hashlib.sha256(
                json.dumps(row["json_schema"], sort_keys=True).encode("utf-8")).hexdigest(),
            "created_at": row["created_at"],
        })
    summary.pop("schema_rows", None)
    summary["schema_versions"] = schema_versions
    return summary


def _pg_dump_version(db_user: str) -> str:
    proc = _compose_exec(["db", "sh", "-ec", f'pg_dump --version'])
    return proc.stdout.strip()


def write_manifest(dump_path: str) -> int:
    dump = Path(dump_path).resolve()
    if not dump.is_file() or not dump.stat().st_size:
        raise SystemExit(f"dump is missing or empty: {dump}")
    sha_file = dump.with_suffix(dump.suffix + ".sha256")
    if not sha_file.is_file():
        raise SystemExit(f"missing checksum file: {sha_file}")
    recorded = sha_file.read_text(encoding="utf-8").split()[0]
    actual = _sha256_file(dump)
    if recorded != actual:
        raise SystemExit(f"checksum mismatch for {dump}: manifest not written")

    env = _env_file()
    db_name = os.environ.get("DB_NAME") or env.get("DB_NAME") or "ai_compass"
    db_user = os.environ.get("DB_USER") or env.get("DB_USER") or "ai_compass"
    keep_days = int(os.environ.get("AI_COMPASS_BACKUP_RETENTION")
                    or env.get("AI_COMPASS_BACKUP_RETENTION") or "14")

    # Record the final (post-rename) filename, stripping a trailing .partial.
    dump_filename = dump.name
    if dump_filename.endswith(".partial"):
        dump_filename = dump_filename[: -len(".partial")]

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "status": "success",
        "dump_file": dump_filename,
        "sha256": actual,
        "byte_size": dump.stat().st_size,
        "created_at": _utc_now(),
        "database": {
            "name": db_name,
            "pg_dump_version": _pg_dump_version(db_user),
        },
        "app_revision": {"git_sha": _git_sha(), "note": "best-effort host git revision"},
        "catalog": _gather_catalog(db_name, db_user),
        "retention": {
            "keep_days": keep_days,
            "note": "same-host dir is NOT disaster protection; off-host is #29",
        },
        # Reserved for the future evidence store (#17): blob hashes and storage
        # generations so a coordinated DB+blob snapshot can be reconciled later.
        "evidence_store": None,
    }
    manifest_path = dump.with_suffix(dump.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(manifest_path, 0o600)
    print(f"manifest written: {manifest_path}", file=sys.stderr)
    return 0


def verify_manifest(dump_path: str) -> int:
    dump = Path(dump_path).resolve()
    if not dump.is_file():
        print(f"FAIL: source dump not found: {dump}", file=sys.stderr)
        return 2
    sha_file = dump.with_suffix(dump.suffix + ".sha256")
    manifest_file = dump.with_suffix(dump.suffix + ".manifest.json")
    if not sha_file.is_file() or not manifest_file.is_file():
        print(f"FAIL: incomplete triplet for {dump} "
              f"(sha256={'yes' if sha_file.is_file() else 'no'}, "
              f"manifest={'yes' if manifest_file.is_file() else 'no'})", file=sys.stderr)
        return 2
    expected = sha_file.read_text(encoding="utf-8").split()[0]
    actual = _sha256_file(dump)
    if expected != actual:
        print(f"FAIL: checksum mismatch for {dump}: expected {expected}, got {actual}",
              file=sys.stderr)
        return 1
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        print(f"FAIL: manifest is not valid JSON: {error}", file=sys.stderr)
        return 1
    if manifest.get("status") != "success":
        print(f"FAIL: manifest status is {manifest.get('status')!r}, not 'success'",
              file=sys.stderr)
        return 1
    if manifest.get("sha256") != actual:
        print("FAIL: manifest sha256 does not match the dump", file=sys.stderr)
        return 1
    if manifest.get("byte_size") != dump.stat().st_size:
        print(f"FAIL: manifest byte_size {manifest.get('byte_size')} != {dump.stat().st_size}",
              file=sys.stderr)
        return 1
    print(f"OK: {dump} ({manifest.get('byte_size')} bytes, "
          f"{manifest.get('created_at')}, {manifest['catalog']['items']} items, "
          f"{manifest['catalog']['revisions']} revisions)", file=sys.stderr)
    return 0


def read_field(dump_path: str, field: str) -> int:
    dump = Path(dump_path).resolve()
    manifest_file = dump.with_suffix(dump.suffix + ".manifest.json")
    if not manifest_file.is_file():
        print(f"no manifest for {dump}", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    parts = field.split(".")
    value: object = manifest
    for part in parts:
        if not isinstance(value, dict) or part not in value:
            print(f"field {field!r} not found", file=sys.stderr)
            return 2
        value = value[part]
    print(json.dumps(value, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p_write = sub.add_parser("write", help="write <dump>.manifest.json")
    p_write.add_argument("dump")
    p_verify = sub.add_parser("verify", help="offline checksum + manifest validation")
    p_verify.add_argument("dump")
    p_read = sub.add_parser("read", help="print a manifest field as JSON")
    p_read.add_argument("dump")
    p_read.add_argument("--field", required=True)
    args = parser.parse_args()
    if args.command == "write":
        return write_manifest(args.dump)
    if args.command == "verify":
        return verify_manifest(args.dump)
    if args.command == "read":
        return read_field(args.dump, args.field)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
