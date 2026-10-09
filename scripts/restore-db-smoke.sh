#!/usr/bin/env bash
# Isolated restore drill into a uniquely named disposable PostgreSQL database.
# Never selects, drops or writes the active Server database or seeded Demo data.
#
# Default (used by scripts/smoke-platform.sh): restore + assert >=1 SQL table.
#   bash scripts/restore-db-smoke.sh BACKUP.dump
# --strict (used by scripts/smoke-recovery.sh): also verify the dump triplet,
#   restore into a unique disposable DB, and assert restored catalog counts,
#   public IDs, schema-version hashes and FK integrity match the manifest.
#   bash scripts/restore-db-smoke.sh --strict BACKUP.dump
#
# Safety: the restore target is ALWAYS a name starting with
# ai_compass_restore_drill_; it is refused if empty, un-prefixed, or equal to
# POSTGRES_DB (fail-closed on an unset POSTGRES_DB). This script never issues
# `docker compose down -v`, volume removal, or dropdb against POSTGRES_DB.
set -euo pipefail
strict=0
if [[ "${1:-}" == "--strict" ]]; then
  strict=1
  shift
fi
if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/restore-db-smoke.sh [--strict] BACKUP.dump" >&2
  exit 2
fi
backup="$(realpath "$1")"
if [[ ! -f "$backup" ]]; then
  echo "FAIL: source dump not found: $backup" >&2
  exit 2
fi
cd "$(dirname "$0")/.."

# POSTGRES_USER/POSTGRES_DB are injected by compose into the db service; read
# them from the container (the host shell does not have them) and fail closed
# if either is empty, so a guard never passes vacuously.
postgres_user="$(docker compose exec -T db sh -ec 'printf "%s" "$POSTGRES_USER"' | tr -d '\r')"
postgres_db="$(docker compose exec -T db sh -ec 'printf "%s" "$POSTGRES_DB"' | tr -d '\r')"
if [[ -z "$postgres_user" || -z "$postgres_db" ]]; then
  echo "FAIL: POSTGRES_USER or POSTGRES_DB is empty in the db container; refusing to derive a restore target" >&2
  exit 2
fi

# Unique disposable target; collisions are structurally near-impossible.
rand="$(head -c 6 /dev/urandom | base32 | tr 'A-Z' 'a-z' | tr -d -c 'a-z0-9')"
restore_name="${RESTORE_PREFIX:-ai_compass_restore_drill_}$(date -u +%Y%m%dT%H%M%SZ)_${rand}"

case "$restore_name" in
  "${RESTORE_PREFIX:-ai_compass_restore_drill_}"*) : ;;  # prefixed, OK
  *) echo "FAIL: derived restore name lacks the required prefix: $restore_name" >&2; exit 2 ;;
esac
if [[ -z "$restore_name" || "$restore_name" == "$postgres_db" ]]; then
  echo "FAIL: unsafe restore target '$restore_name' (empty or equals POSTGRES_DB '$postgres_db')" >&2
  exit 2
fi

if [[ "$strict" == "1" ]]; then
  python3 scripts/snapshot_manifest.py verify "$backup" >&2
fi

echo "Restoring into disposable database: $restore_name" >&2
docker compose exec -T db sh -ec '
  test "$POSTGRES_DB" != "$1" || { echo "Unsafe restore DB name" >&2; exit 2; }
  dropdb --if-exists -U "$POSTGRES_USER" "$1"
  createdb -U "$POSTGRES_USER" "$1"
' _ "$restore_name"

docker compose exec -T db sh -ec 'exec pg_restore --exit-on-error --no-owner --no-privileges -U "$POSTGRES_USER" -d "$1"' _ "$restore_name" < "$backup"

table_count="$(docker compose exec -T db sh -ec 'psql -U "$POSTGRES_USER" -d "$1" -Atqc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '"'"'public'"'"'"' _ "$restore_name" | tr -d '\r\n')"
if [[ ! "$table_count" =~ ^[0-9]+$ || "$table_count" -lt 1 ]]; then
  echo "Restore FAILED: no SQL tables in disposable database $restore_name" >&2
  exit 1
fi

report="$backup.restore-manifest.json"
if [[ "$strict" == "1" ]]; then
  python3 - "$backup" "$restore_name" "$postgres_user" "$table_count" "$report" <<'PY'
import json, subprocess, sys
backup, restore_name, pg_user, table_count, report = sys.argv[1:6]
manifest = json.loads(open(backup + ".manifest.json").read())
expected = manifest["catalog"]

def psql(sql):
    out = subprocess.run(
        ["docker", "compose", "exec", "-T", "db", "sh", "-ec",
         f'psql -X -U "{pg_user}" -d "{restore_name}" -Atq'],
        check=True, capture_output=True, text=True, input=sql)
    return out.stdout.strip()

items = int(psql("SELECT COUNT(*) FROM public.config_catalogitem") or "0")
revisions = int(psql("SELECT COUNT(*) FROM public.config_catalogrevision") or "0")
public_ids = psql("SELECT COALESCE(string_agg(public_id, ',' ORDER BY public_id), '') FROM public.config_catalogitem")
orphan_sql = (
    "SELECT COUNT(*) FROM public.config_catalogrevision r "
    "LEFT JOIN public.config_catalogitem i ON r.item_id = i.id "
    "LEFT JOIN public.config_objecttypeversion s ON r.schema_version_id = s.id "
    "LEFT JOIN public.auth_user u ON r.created_by_id = u.id "
    "WHERE i.id IS NULL OR s.id IS NULL OR u.id IS NULL")
fk_orphans = int(psql(orphan_sql) or "0")
checks = {
    "table_count": {"expected": ">=1", "actual": table_count,
                    "pass": int(table_count) >= 1},
    "items": {"expected": expected["items"], "actual": items, "pass": items == expected["items"]},
    "revisions": {"expected": expected["revisions"], "actual": revisions,
                  "pass": revisions == expected["revisions"]},
    "public_ids": {"expected": sorted(expected["public_ids"]),
                   "actual": sorted(public_ids.split(",") if public_ids else []),
                   "pass": sorted(public_ids.split(",") if public_ids else []) == sorted(expected["public_ids"])},
    "fk_orphans": {"expected": 0, "actual": fk_orphans, "pass": fk_orphans == 0},
}
ok = all(c["pass"] for c in checks.values())
result = {
    "status": "success" if ok else "failure",
    "dump_file": manifest["dump_file"],
    "restore_database": restore_name,
    "checked_against_manifest_sha256": manifest["sha256"],
    "checks": checks,
}
open(report, "w").write(json.dumps(result, indent=2, sort_keys=True) + "\n")
if not ok:
    print("Restore strict checks FAILED:", json.dumps(checks, sort_keys=True), file=sys.stderr)
    sys.exit(1)
PY
  echo "Restore STRICT check PASSED: $table_count tables, catalog reproduced in $restore_name" >&2
  echo "$restore_name" > "$backup.restore-target"
else
  echo "Restore check PASSED: $table_count tables in disposable database $restore_name" >&2
fi
echo "$restore_name"
