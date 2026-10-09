#!/usr/bin/env bash
# Compatibility entrypoint: atomic verified backup with isolated recovery rehearsal.
# Never backs up browser-only Demo fixtures.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
exec python3 scripts/recovery.py backup "$@"
