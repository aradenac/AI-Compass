#!/usr/bin/env bash
# Scheduled-snapshot helper (PLAT-34). Runs a backup, verifies it offline and
# appends a one-line result to the backup log. It does NOT install a scheduler
# itself — wire it into cron or a systemd timer as below.
#
# Sample cron (daily at 03:17 local, off-minute to avoid synchronised load):
#   17 3 * * * AI_COMPASS_BACKUP_DIR=/mnt/ai-compass-backups \
#              AI_COMPASS_BACKUP_REQUIRE_MOUNT=1 \
#              /path/to/AI-Compass/scripts/schedule-backup.sh >> /var/log/ai-compass-backup.log 2>&1
#
# Sample systemd timer (on-calendar, off-minute):
#   # /etc/systemd/system/ai-compass-backup.{service,timer}
#   [Service]
#   Type=oneshot
#   Environment=AI_COMPASS_BACKUP_DIR=/mnt/ai-compass-backups
#   Environment=AI_COMPASS_BACKUP_REQUIRE_MOUNT=1
#   WorkingDirectory=/path/to/AI-Compass
#   ExecStart=/path/to/AI-Compass/scripts/schedule-backup.sh
#   [Timer]
#   OnCalendar=*-*-* 03:17:00
#   Persistent=true
#   [Install]
#   WantedBy=timers.target
#
# This script never issues `docker compose down -v` or volume removal.
set -euo pipefail
cd "$(dirname "$0")/.."
log_dir="${AI_COMPASS_BACKUP_DIR:-.local/backups}"
mkdir -p "$log_dir"
log="$log_dir/backup.log"
status="failed"
dump=""
if dump="$(bash scripts/backup-db.sh)"; then
  if bash scripts/verify-snapshot.sh "$dump" >/dev/null 2>&1; then
    status="ok"
  fi
fi
printf '%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status" "${dump:-none}" >> "$log"
if [[ "$status" != "ok" ]]; then
  echo "Scheduled snapshot FAILED; see $log" >&2
  exit 1
fi
echo "Scheduled snapshot OK: $dump"
