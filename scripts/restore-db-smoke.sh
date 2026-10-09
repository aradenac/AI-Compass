#!/usr/bin/env bash
# Restoration test into a throwaway DB inside the same PostgreSQL instance.
# Never selects, drops or writes the production DB.
set -euo pipefail
if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "Usage: bash scripts/restore-db-smoke.sh BACKUP.dump" >&2
  exit 2
fi
backup="$(realpath "$1")"
cd "$(dirname "$0")/.."
restore_name="ai_compass_restore_smoke"

docker compose exec -T db sh -ec '
  test "$POSTGRES_DB" != "ai_compass_restore_smoke" || { echo "Unsafe restore DB name" >&2; exit 2; }
  dropdb --if-exists -U "$POSTGRES_USER" ai_compass_restore_smoke
  createdb -U "$POSTGRES_USER" ai_compass_restore_smoke
'
docker compose exec -T db sh -ec 'exec pg_restore --exit-on-error --no-owner --no-privileges -U "$POSTGRES_USER" -d ai_compass_restore_smoke' < "$backup"
table_count="$(docker compose exec -T db sh -ec 'psql -U "$POSTGRES_USER" -d ai_compass_restore_smoke -Atqc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '\''public'\''"' | tr -d '\r\n')"
if [[ ! "$table_count" =~ ^[0-9]+$ || "$table_count" -lt 1 ]]; then
  echo "Restore failed: no SQL tables in restored database" >&2
  exit 1
fi
echo "Restore check PASSED: $table_count tables in disposable database $restore_name"
