#!/usr/bin/env bash
# Local PostgreSQL logical backup; does not touch the browser-only Demo dataset.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
target_dir="${AI_COMPASS_BACKUP_DIR:-.local/backups}"
mkdir -p "$target_dir"
tmp="$(mktemp "$target_dir/ai-compass-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXXXX.dump.partial")"
trap 'rm -f "$tmp"' EXIT

docker compose exec -T db sh -ec 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$tmp"
test -s "$tmp"
file="${tmp%.partial}"
mv "$tmp" "$file"
trap - EXIT
sha256sum "$file" > "$file.sha256"
echo "$file"
