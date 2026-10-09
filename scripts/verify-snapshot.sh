#!/usr/bin/env bash
# Offline snapshot verification (PLAT-34): recompute the checksum and validate
# the manifest WITHOUT restoring. Use this before a restore drill, or to detect
# tampering/deletion by comparing against an off-host copy of the manifest.
set -euo pipefail
if [[ $# -ne 1 || ! -f "$1" ]]; then
  echo "Usage: bash scripts/verify-snapshot.sh BACKUP.dump" >&2
  exit 2
fi
backup="$(realpath "$1")"
cd "$(dirname "$0")/.."
python3 scripts/snapshot_manifest.py verify "$backup"
