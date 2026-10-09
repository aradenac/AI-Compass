#!/usr/bin/env bash
# Compatibility entrypoint: restore ONLY into an isolated, networkless container.
# Neither mounts nor contacts the live PostgreSQL database.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/restore-db-smoke.sh RECOVERY_POINT.dump" >&2
  exit 2
fi
exec python3 scripts/recovery.py drill "$1"
