#!/usr/bin/env bash
# PLAT-34 end-to-end infrastructure and independent PostgreSQL recovery check.
# Requires stack running. Mutates only synthetic markers in live source DB.
set -euo pipefail
cd "$(dirname "$0")/.."
port="8080"
if [[ -n "${AI_COMPASS_HTTP_PORT:-}" ]]; then port="$AI_COMPASS_HTTP_PORT"; fi
if [[ -f .env ]]; then
  configured="$(grep -E '^AI_COMPASS_HTTP_PORT=[0-9]+$' .env | tail -1 | cut -d= -f2 || true)"
  [[ -z "$configured" ]] || port="$configured"
fi

curl --fail --silent --show-error "http://127.0.0.1:$port/api/v1/health" | grep '"status": "ok"\|"status":"ok"' >/dev/null
curl --fail --silent --show-error "http://127.0.0.1:$port/prototype.html" | grep "AI Compass" >/dev/null
docker compose exec -T api python manage.py test config --verbosity 1
docker compose exec -T db sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
CREATE TABLE IF NOT EXISTS public.ai_compass_smoke_marker (marker text PRIMARY KEY);
INSERT INTO public.ai_compass_smoke_marker (marker) VALUES ('persistence-check') ON CONFLICT DO NOTHING;
DELETE FROM public.ai_compass_smoke_marker WHERE marker = 'post-backup-only';
SQL

source_summary="$(docker compose exec -T db sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' <<'SQL' | tr -d '\r\n'
SELECT (SELECT count(*) FROM config_catalogitem)::text || ':' ||
       (SELECT count(*) FROM config_catalogrevision)::text || ':' ||
       (SELECT md5(coalesce(string_agg(public_id, '|' ORDER BY public_id), '')) FROM config_catalogitem);
SQL
)"
backup="$(bash scripts/backup-db.sh)"
python3 scripts/recovery.py verify "$backup"
python3 scripts/recovery.py status --json | python3 -c \
  'import json,sys; d=json.load(sys.stdin); assert d["status"]=="ok" and d["last_good_backup"]["status"]=="verified"'
bash scripts/restore-db-smoke.sh "$backup"
python3 scripts/recovery.py drill "$backup" --json | python3 -c \
  'import json,sys; d=json.load(sys.stdin); assert d["status"]=="passed",d; i=d["inspection"]; assert i["smoke_marker"]=="persistence-check"; assert i["invalid_ids"]==i["invalid_revision_links"]==i["orphan_revisions"]==0; assert "model:1" in i["schema_versions"]'

# Data written AFTER the recovery point must never contaminate staged recovery.
docker compose exec -T db sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
INSERT INTO public.ai_compass_smoke_marker (marker) VALUES ('post-backup-only');
SQL
python3 scripts/recovery.py drill "$backup" --json | python3 -c \
  'import json,sys; d=json.load(sys.stdin); assert d["status"]=="passed"; assert d["inspection"]["smoke_marker"]=="persistence-check"'
live_count="$(docker compose exec -T db sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT COUNT(*) FROM public.ai_compass_smoke_marker"' | tr -d '\r\n')"
test "$live_count" = "2"

# Corrupted dump and missing mandatory destination must fail without losing last-good.
bad_dir="$(mktemp -d)"
trap 'rm -rf "$bad_dir"' EXIT
bad="$bad_dir/$(basename "$backup")"
cp "$backup" "$bad"
cp "$backup.json" "$bad.json"
cp "$backup.complete" "$bad.complete"
printf 'broken' | dd of="$bad" bs=1 seek=64 conv=notrunc status=none
if python3 scripts/recovery.py verify "$bad"; then
  echo "ERROR: corrupted backup accepted" >&2
  exit 1
fi
if python3 scripts/recovery.py --destination "$bad_dir/disconnected" backup; then
  echo "ERROR: unavailable mandatory destination silently created" >&2
  exit 1
fi
if python3 scripts/recovery.py drill "$backup" --target-db ai_compass; then
  echo "ERROR: a production restore target was accepted" >&2
  exit 1
fi
test -f "$backup.complete"
docker compose exec -T db sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
DELETE FROM public.ai_compass_smoke_marker WHERE marker = 'post-backup-only';
SQL
after_summary="$(docker compose exec -T db sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At' <<'SQL' | tr -d '\r\n'
SELECT (SELECT count(*) FROM config_catalogitem)::text || ':' ||
       (SELECT count(*) FROM config_catalogrevision)::text || ':' ||
       (SELECT md5(coalesce(string_agg(public_id, '|' ORDER BY public_id), '')) FROM config_catalogitem);
SQL
)"
test "$source_summary" = "$after_summary"
echo "Platform checks PASSED: Demo/API, independent restore, immutable Model history, corruption and unsafe-target refusal"
