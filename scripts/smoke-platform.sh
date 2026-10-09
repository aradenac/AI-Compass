#!/usr/bin/env bash
# End-to-end local infrastructure check. Requires the stack already started.
set -euo pipefail
cd "$(dirname "$0")/.."
port="${AI_COMPASS_HTTP_PORT:-8080}"
if [[ -f .env ]]; then
  # Read only the numeric port; never execute arbitrary .env as shell code.
  configured="$(grep -E '^AI_COMPASS_HTTP_PORT=[0-9]+$' .env | tail -1 | cut -d= -f2 || true)"
  [[ -z "$configured" ]] || port="$configured"
fi

curl --fail --silent --show-error "http://127.0.0.1:$port/api/v1/health" | grep '"status": "ok"\|"status":"ok"' > /dev/null
curl --fail --silent --show-error "http://127.0.0.1:$port/prototype.html" | grep "AI Compass" > /dev/null
docker compose exec -T api python manage.py test config --verbosity 1
docker compose exec -T db sh -ec 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
CREATE TABLE IF NOT EXISTS public.ai_compass_smoke_marker (marker text PRIMARY KEY);
INSERT INTO public.ai_compass_smoke_marker (marker) VALUES ('persistence-check') ON CONFLICT DO NOTHING;
SQL

backup="$(bash scripts/backup-db.sh)"
bash scripts/restore-db-smoke.sh "$backup"
marker="$(docker compose exec -T db sh -ec 'psql -U "$POSTGRES_USER" -d ai_compass_restore_smoke -Atqc "SELECT marker FROM public.ai_compass_smoke_marker LIMIT 1"' | tr -d '\r\n')"
test "$marker" = "persistence-check"
echo "Platform checks PASSED: HTTP/UI, Django tests, PostgreSQL dump/restore and marker integrity"
