#!/usr/bin/env bash
# Local PostgreSQL logical snapshot with an atomic completion marker (PLAT-34).
# Does not touch the browser-only Demo dataset.
#
# A "good" snapshot is the triplet  <dump> + <dump>.sha256 + <dump>.manifest.json,
# written in that order so a crash never leaves a successful-looking dump
# without its checksum/manifest. A partial/failed dump produces NO manifest and
# is therefore never last-good.
#
# stdout is the dump path (so smoke-platform.sh can capture it); progress goes
# to stderr. Keep it that way.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077

target_dir="${AI_COMPASS_BACKUP_DIR:-.local/backups}"
require_mount="${AI_COMPASS_BACKUP_REQUIRE_MOUNT:-0}"
retention_days="${AI_COMPASS_BACKUP_RETENTION:-14}"

if [[ ! -d "$target_dir" ]]; then
  if ! mkdir -p "$target_dir" 2>/dev/null; then
    echo "Backup destination is unavailable or not writable: $target_dir" >&2
    exit 2
  fi
fi
target_dir="$(cd "$target_dir" && pwd)"

if [[ "$require_mount" == "1" ]]; then
  # Fail loudly if the destination is not on its own device/mount. This is an
  # opt-in guard for operators who require an independent destination; it does
  # not hard-require off-host storage (that is #29).
  root_dev="$(stat -c %d "$target_dir" 2>/dev/null || echo "")"
  repo_dev="$(stat -c %d . 2>/dev/null || echo "")"
  if [[ -z "$root_dev" || -z "$repo_dev" || "$root_dev" == "$repo_dev" ]]; then
    echo "AI_COMPASS_BACKUP_REQUIRE_MOUNT=1 but '$target_dir' is on the same device as the repository" >&2
    echo "Configure an independent (different disk/off-host) destination before backing up." >&2
    exit 2
  fi
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp="$target_dir/ai-compass-$stamp-$$.dump.partial"
trap 'rm -f "$tmp" "$tmp.sha256" "$tmp.manifest.json"' EXIT

echo "Taking PostgreSQL snapshot into $target_dir ..." >&2
docker compose exec -T db sh -ec 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom' > "$tmp"
if [[ ! -s "$tmp" ]]; then
  echo "Backup FAILED: pg_dump produced an empty dump; no manifest written" >&2
  exit 1
fi

sha256sum "$tmp" > "$tmp.sha256"
python3 scripts/snapshot_manifest.py write "$tmp" >&2

# Atomic promotion: rename all three artefacts together once they are complete.
file="$target_dir/ai-compass-$stamp-$$.dump"
mv "$tmp" "$file"
mv "$tmp.sha256" "$file.sha256"
mv "$tmp.manifest.json" "$file.manifest.json"
trap - EXIT
chmod 600 "$file" "$file.sha256" "$file.manifest.json"

# Retention: prune complete triplets older than retention_days, but ALWAYS keep
# the single newest good snapshot. Never treat an orphan .partial or a
# manifest-less dump as valid/last-good.
newest=""
shopt -s nullglob
mapfile -t dumps < <(ls -1t "$target_dir"/ai-compass-*.dump 2>/dev/null || true)
for d in "${dumps[@]}"; do
  if [[ -f "$d.sha256" && -f "$d.manifest.json" ]]; then
    newest="${newest:-$d}"
  fi
done
if [[ -n "$newest" ]]; then
  find "$target_dir" -name 'ai-compass-*.dump' -type f -mtime +"$retention_days" -print \
    | while read -r old; do
        [[ "$old" == "$newest" ]] && continue
        rm -f "$old" "$old.sha256" "$old.manifest.json" "$old.restore-manifest.json"
        echo "Pruned (retention ${retention_days}d): $old" >&2
      done
  # Also clean orphaned .partial files left by any previous crashed run.
  find "$target_dir" -name 'ai-compass-*.dump.partial' -type f -delete 2>/dev/null || true
fi

echo "$file"
