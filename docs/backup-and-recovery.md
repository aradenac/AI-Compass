# AI Compass — PostgreSQL backup and isolated recovery (PLAT-34)

> **Scope:** persistent Server PostgreSQL only. Browser Demo is independent. Evidence blobs are NOT covered by this issue (#17/#29). **Same-disk backups do not protect against host or disk loss.**

## One-off commands

Run from repository root, after Docker Compose and Django migrations:

    bash scripts/backup-db.sh
    python3 scripts/recovery.py status --json
    python3 scripts/recovery.py verify /ABS/PATH/ai-compass-YYYYMMDDTHHMMSSZ-ID.dump
    bash scripts/restore-db-smoke.sh /ABS/PATH/ai-compass-YYYYMMDDTHHMMSSZ-ID.dump
    python3 scripts/recovery.py drill /ABS/PATH/ai-compass-YYYYMMDDTHHMMSSZ-ID.dump --json

The backup prints the absolute dump filename. **Every backup is restored successfully into a fresh isolated container before it is marked valid.** The following files constitute one recovery point:

- **.dump**: PostgreSQL custom-format snapshot including stable Model IDs, revisions, audit history, schemas, user tables and JSONB.
- **.dump.json**: database, PostgreSQL and app Git revision, time, byte size, SHA-256, registered schema versions, restored object/revision counts and fingerprints, plus explicit evidence-file coverage.
- **.dump.complete**: checksum of the manifest, created atomically **last**. A partial/interrupted operation never becomes last-good.
- **reports/drill-*.json**: separate machine-readable validation pass/failure records for subsequent isolated restores.
- **ai-compass-DATE-ID.failed.json**: failed backup stage and error, without overwriting the last-good backup.

Offline verification checks all three files, the metadata and the full dump SHA-256 **without Docker**.

## Isolation contract

Each full restore drill creates a uniquely named temporary PostgreSQL container, using an independent random password, no Docker network, no published port and **no mounted volume**. It restores through standard input, validates row/revision counts, HRIDs, schema versions, relation consistency and digests, then removes the container. No API exists to specify a restore destination. **It never drops or writes to the operational database.**

Do not use destructive Docker Compose volume commands during recovery. **Production restoration** is a separate, deliberately gated future feature; this command only demonstrates recoverability.

## Independent destination and automatic scheduling

Provision an existing writable backup mount, then use, for example:

    python3 scripts/recovery.py --destination /mnt/ai-compass-backups --require-external backup --keep 14
    python3 scripts/recovery.py --destination /mnt/ai-compass-backups status --json
    python3 scripts/install-backup-timer.py --destination /mnt/ai-compass-backups --require-external --calendar daily --keep 14
    systemctl --user list-timers ai-compass-backup.timer
    journalctl --user -u ai-compass-backup.service -n 50

Inspect generated service/timer text first with the **--dry-run** installer option. The installed user-level systemd timer uses Persistent=true and calls the same verified backup operation. If the user-level timer must run while no one is logged in, the OS may require enabling user lingering.

A configured destination **must already exist**. An unavailable/unmounted directory fails instead of being silently recreated under another mount. **--require-external** requires a different filesystem from the repository. This check does not by itself guarantee independent off-host protection: prefer a protected external disk or remote share, backed by operational monitoring.

Without an explicit destination, backups are stored in .local/backups and a warning is printed if they share a filesystem with the application. Retention defaults to the newest **14 verified snapshots**, configured with --keep N (N >= 1); pruning occurs only after successful capture and validation, preserves the last-good point and does not remove unknown or incomplete snapshots. Advisory file locking serializes backups targeting the same directory.

## Failure recovery and verification

1. Inspect status --json and the latest .failed.json or reports/drill-*.json after an unsuccessful run. A missing .complete marker or failed restore is **not** a valid snapshot.
2. Repeat verify and drill on a protected backup copy. Never edit the original dump or replace the operational DB from this CLI.
3. To test corruption, copy the full .dump/.json/.complete triplet to a temporary directory, flip a byte in the copied dump and check that verify/drill fails while the original stays valid.
4. To test timing and non-interference, create test Model revisions, make backup A, add new synthetic data and drill A again: the original HRID/revision fingerprints must match A while post-backup production changes remain untouched.
5. Stop migrations or major data changes if no verified recovery point exists. Only apply a registered migration following the later staging acceptance and production governance gates (#35/#26).

### Tests

    python3 -m unittest discover -s scripts -p 'test_recovery.py' -v
    python3 scripts/install-backup-timer.py --destination "$PWD" --dry-run
    bash scripts/smoke-platform.sh

The live smoke checks DB recovery in isolation, data written after snapshot being excluded, corrupt-file refusal, missing destination refusal, wrong-target rejection and preservation of Model fingerprints. The existing Django/Models/Demo smoke checks remain in CI.

**Not included:** WAL/PITR, coordination with uploaded evidence files, automatic off-host replication, a web backup dashboard, HA, and automated production rollback. See #29 for coordinated DB+evidence backups.
