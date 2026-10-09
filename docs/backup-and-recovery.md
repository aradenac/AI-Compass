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

## Additional evidence from the competing PR #40

The selected #38 implementation remains the sole production recovery engine. A focused
follow-up integrates two useful ideas from the rejected #40 **without inheriting its
restore-to-live-cluster risks**:

- Each completed recovery manifest now includes `restored_inspection.schema_hashes`:
  one **SHA-256** digest for each registered type/version's canonical JSON Schema.
  These are calculated from the **restored snapshot itself**, not from a query
  executed later against a source database that may have changed. Repeat drills
  recompute and compare the hashes alongside revision/identity fingerprints.
- CI runs `scripts/smoke_recovery_domain.py` in a **new random Docker Compose
  project**, with independent DB, network, data volume and credentials. It invokes
  the real Django `create_model` and `revise_model` services, snapshots r001/r002,
  then creates r003 and a second Model **only in this CI fixture DB**. Two fully
  independent networkless PostgreSQL restores prove that r001/r002 (including
  the exact JSON properties and pinned schema version) survived, while r003
  and the post-snapshot Model are absent. The temporary source project and both
  restored databases are destroyed even when checks fail.

**Safety:** this domain fixture is refused outside GitHub Actions with its
explicit `AI_COMPASS_ISOLATED_FIXTURE_CI=1` opt-in. It never uses the running
`ai-compass` Compose project for fixture creation or performs production
`dropdb`/`down --volumes`. The operator backup/restore CLI is unchanged.
The CI workflow runs the new check alongside the original isolated-recovery,
Django and independent Demo regressions. The work does **not** add a Model
fixture command intended for operators.

## Failure recovery and verification

1. Inspect status --json and the latest .failed.json or reports/drill-*.json after an unsuccessful run. A missing .complete marker or failed restore is **not** a valid snapshot.
2. Repeat verify and drill on a protected backup copy. Never edit the original dump or replace the operational DB from this CLI.
3. To test corruption, copy the full .dump/.json/.complete triplet to a temporary directory, flip a byte in the copied dump and check that verify/drill fails while the original stays valid.
4. To test timing and non-interference **with real Models**, use the automated CI fixture described above. **Do not manually create fake Models on an operational database** to test backups. The existing operator smoke uses an independent synthetic SQL marker, and the recovery drill itself never mutates the source database.
5. Stop migrations or major data changes if no verified recovery point exists. Only apply a registered migration following the later staging acceptance and production governance gates (#35/#26).

### Tests

    python3 -m unittest discover -s scripts -p 'test_recovery.py' -v
    python3 scripts/install-backup-timer.py --destination "$PWD" --dry-run
    bash scripts/smoke-platform.sh

The live smoke checks DB recovery in isolation, data written after snapshot being excluded, corrupt-file refusal, missing destination refusal, wrong-target rejection and preservation of Model fingerprints. The existing Django/Models/Demo smoke checks remain in CI.

**Not included:** WAL/PITR, coordination with uploaded evidence files, automatic off-host replication, a web backup dashboard, HA, and automated production rollback. See #29 for coordinated DB+evidence backups.
