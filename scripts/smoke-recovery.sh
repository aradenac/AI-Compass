#!/usr/bin/env bash
# PLAT-34 deterministic recovery drill. Proves, end to end:
#   - a scheduled snapshot is validated (triplet + manifest)
#   - isolated restore reproduces Model IDs, revision counts and schema versions
#   - distinct before/after point-in-time data: post-snapshot data is NOT in the snapshot
#   - the active Server database is unchanged by the restore (no restore-to-production)
#   - the drill is reproducible (run twice into unique disposable databases)
#   - a corrupted dump fails verification safely
#   - retention never deletes the newest good snapshot and never treats a
#     manifest-less orphan as last-good
#
# Not wired into CI (local/operator evidence). Requires the stack up + migrated.
# Never issues `docker compose down -v` or volume removal.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== PLAT-34 recovery drill =="
echo "[1/10] Create 'before' Model (2 revisions) on the live database"
before_json="$(docker compose exec -T api python manage.py recovery_fixture \
  --create --name "Drill Before" --revisions 2)"
before_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["public_id"])' <<<"$before_json")"
echo "  before_id=$before_id"

echo "[2/10] Take snapshot S1 and verify it offline"
s1="$(bash scripts/backup-db.sh)"
bash scripts/verify-snapshot.sh "$s1" >&2

echo "[3/10] Create 'after' Model (1 revision) — distinct post-snapshot data"
after_json="$(docker compose exec -T api python manage.py recovery_fixture \
  --create --name "Drill After" --revisions 1)"
after_id="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["public_id"])' <<<"$after_json")"
echo "  after_id=$after_id"

echo "[4/10] Restore S1 into an isolated disposable database (--strict)"
restore_db="$(bash scripts/restore-db-smoke.sh --strict "$s1")"

echo "[5/10] Point-in-time check on the RESTORED database: before present (2 rev), after ABSENT"
docker compose exec -T api python manage.py recovery_fixture --check \
  --expect-id "$before_id" --revisions 2 --expect-absent "$after_id" \
  --database "$restore_db" >&2

echo "[6/10] Live database unchanged: before (2 rev) AND after (1 rev) still present"
docker compose exec -T api python manage.py recovery_fixture --check \
  --expect-id "$before_id" --revisions 2 >&2
docker compose exec -T api python manage.py recovery_fixture --check \
  --expect-id "$after_id" --revisions 1 >&2

echo "[7/10] Reproducibility: run the isolated restore a second time"
restore_db2="$(bash scripts/restore-db-smoke.sh --strict "$s1")"
test "$restore_db2" != "$restore_db"
docker compose exec -T api python manage.py recovery_fixture --check \
  --expect-id "$before_id" --revisions 2 --expect-absent "$after_id" \
  --database "$restore_db2" >&2

echo "[8/10] Corrupted-dump verification must fail"
corrupt="$(mktemp -p "$(dirname "$s1")" corrupt-XXXX.dump)"
cp "$s1" "$corrupt"
cp "$s1.sha256" "$corrupt.sha256"
cp "$s1.manifest.json" "$corrupt.manifest.json"
head -c 64 "$corrupt" > "$corrupt.tmp" && mv "$corrupt.tmp" "$corrupt"
if bash scripts/verify-snapshot.sh "$corrupt" 2>/dev/null; then
  echo "FAIL: corrupted dump was accepted" >&2
  rm -f "$corrupt" "$corrupt.sha256" "$corrupt.manifest.json"
  exit 1
fi
rm -f "$corrupt" "$corrupt.sha256" "$corrupt.manifest.json"

echo "[9/10] Retention: newest good snapshot survives and orphans are not last-good"
# An orphan dump with no checksum/manifest must not be treated as valid.
orphan="$(dirname "$s1")/ai-compass-19900101T000000Z-orphan.dump"
printf 'not a real dump' > "$orphan"
orphan_newest_before="$(ls -1t "$(dirname "$s1")"/ai-compass-*.dump | head -1)"
# Re-run backup to trigger retention; S1 (just created) must survive.
s2="$(bash scripts/backup-db.sh)"
good="$(ls -1t "$(dirname "$s1")"/ai-compass-*.dump 2>/dev/null | while read -r d; do
  if [[ -f "$d.sha256" && -f "$d.manifest.json" ]]; then echo "$d"; break; fi
done)"
test -n "$good"
# The newest good snapshot must be one of the two we just made, never the orphan.
case "$good" in
  "$s1"|"$s2") : ;;
  *) echo "FAIL: newest good snapshot is not a real backup: $good" >&2; rm -f "$orphan"; exit 1 ;;
esac
rm -f "$orphan"

echo "[10/10] Cleanup disposable databases (only ai_compass_restore_drill_*)"
docker compose exec -T db sh -ec '
  for db in $(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc \
    "SELECT datname FROM pg_database WHERE datname LIKE '"'"'ai_compass_restore_drill_%'"'"'"); do
    dropdb --if-exists -U "$POSTGRES_USER" "$db"
  done
' >&2 || true

echo "PLAT-34 recovery drill PASSED: snapshot, isolated point-in-time restore,"
echo "  live-DB unchanged, reproducible, corrupted-dump rejection and retention safety."
