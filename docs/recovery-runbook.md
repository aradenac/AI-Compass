# AI Compass — Recovery Runbook (PLAT-34)

> **Scope:** scheduled PostgreSQL snapshots, offline verification, and isolated restore drills. · **Status:** implemented · **Related:** [Local Installation §7](local-installation.md) · [Architecture §10](platform-architecture-and-data-governance.md) · [Roadmap #34](platform-implementation-roadmap.md)
>
> **Principle:** a backup that has never been restored is an assumption, not a recovery point. Every snapshot produces a verified triplet and the drill proves a real restore reproduces Model IDs, revision counts and schema versions into an isolated database, without ever touching the active Server database or the seeded Demo `localStorage`.

## Snapshot artefacts

A "good" snapshot is a complete triplet, written atomically in this order:

| File | Contents |
| --- | --- |
| `ai-compass-<utc-ts>-<pid>.dump` | custom-format `pg_dump` (PostgreSQL-aware, logical) |
| `…dump.sha256` | SHA-256 of the dump bytes |
| `…dump.manifest.json` | status, timestamp, checksum, DB/pg_dump version, app git SHA, catalog summary (item + revision counts, public IDs, schema-version hashes, FK-orphan count), retention hint |

A partial or failed dump produces **no** manifest and **no** renamed dump, so it can never be mistaken for a last-good recovery point. A dump lacking its `.sha256` or `.manifest.json` is treated as **incomplete** and refused by verify/restore.

The manifest carries `manifest_version` and a reserved `evidence_store` field (currently `null`). This is the **recovery-point contract for the future evidence store (#17)**: when blob storage lands, a coordinated snapshot will record blob hashes and storage generations there so DB + files can be reconciled together. Coordinated DB+blob backups, PITR/WAL, a dedicated health UI and off-host automation remain **#29 — explicitly out of scope here.**

## 1. Manual one-off snapshot

```bash
bash scripts/backup-db.sh
# stdout: the dump path (capture it); progress goes to stderr.
# .local/backups/ai-compass-….dump + .sha256 + .manifest.json
```

## 2. Offline verification (no restore)

```bash
bash scripts/verify-snapshot.sh .local/backups/ACTUAL.dump
# recomputes the checksum and validates the manifest triplet; exits non-zero on
# corruption, absence or a status != success.
```

Compare the `.manifest.json` + `.sha256` pair against an **off-host copy** to detect tampering or deletion of the source snapshot.

## 3. Isolated restore drill

```bash
# default: restore into a unique disposable DB, assert >=1 table
bash scripts/restore-db-smoke.sh .local/backups/ACTUAL.dump

# --strict: also verify the dump triplet, then assert restored catalog counts,
# public IDs, schema-version hashes and FK integrity match the manifest
bash scripts/restore-db-smoke.sh --strict .local/backups/ACTUAL.dump
# stdout: the disposable database name; a .restore-manifest.json is written.
```

The full deterministic drill (point-in-time before/after data, live-DB unchanged, reproducible twice, corrupted-dump rejection, retention safety):

```bash
bash scripts/smoke-recovery.sh
```

**Isolation guarantees:** the restore target is always a name starting with `ai_compass_restore_drill_`; it is refused if empty, un-prefixed, or equal to the active `POSTGRES_DB` (fail-closed). The drill drops **only** `ai_compass_restore_drill_*` databases and never the active database. No restore script issues `docker compose down -v` or volume removal.

## 4. Scheduled invocation

`scripts/schedule-backup.sh` runs a backup + offline verify and appends a `timestamp status dump-path` line to `AI_COMPASS_BACKUP_DIR/backup.log`. It does **not** install a scheduler. Wire it into cron or a systemd timer:

```cron
# daily at 03:17 local (off-minute to avoid synchronised load across hosts)
17 3 * * * AI_COMPASS_BACKUP_DIR=/mnt/ai-compass-backups \
            AI_COMPASS_BACKUP_REQUIRE_MOUNT=1 \
            /path/to/AI-Compass/scripts/schedule-backup.sh >> /var/log/ai-compass-backup.log 2>&1
```

```ini
# /etc/systemd/system/ai-compass-backup.service
[Service]
Type=oneshot
Environment=AI_COMPASS_BACKUP_DIR=/mnt/ai-compass-backups
Environment=AI_COMPASS_BACKUP_REQUIRE_MOUNT=1
WorkingDirectory=/path/to/AI-Compass
ExecStart=/path/to/AI-Compass/scripts/schedule-backup.sh
# /etc/systemd/system/ai-compass-backup.timer
[Timer]
OnCalendar=*-*-* 03:17:00
Persistent=true
[Install]
WantedBy=timers.target
```

## 5. Destination independence

The default `AI_COMPASS_BACKUP_DIR=.local/backups` is on the **same host** as the database — it is **not** disaster-recovery protection. A disk or host failure takes the database and its backups together. Point `AI_COMPASS_BACKUP_DIR` at a different physical disk or an off-host mount and set `AI_COMPASS_BACKUP_REQUIRE_MOUNT=1` so backups **fail loudly** if that destination is not actually mounted (verified by device id). Off-host automated copies and coordinated DB+blob recovery are #29.

## 6. Retention

`AI_COMPASS_BACKUP_RETENTION` (default 14 days) prunes complete triplets older than the window, **always keeping the single newest good snapshot**. Orphaned `.partial` files from a crashed run are cleaned up; a manifest-less dump is never treated as last-good.

## 7. Failure handling

| Symptom | Action |
| --- | --- |
| `FAIL: source dump not found` | The snapshot was deleted or moved; restore from an off-host copy. Code cannot prevent deletion, only detect it. |
| `FAIL: checksum mismatch` | The dump is corrupted/tampered; do not restore. Discard and use a prior good triplet. |
| `FAIL: incomplete triplet` | A crash left a dump without its checksum/manifest; treat as failed, re-run the backup. |
| `AI_COMPASS_BACKUP_REQUIRE_MOUNT=1 but … same device` | The independent destination is not mounted; mount it or back up to the correct off-host path. |
| Restore target equals `POSTGRES_DB` | Impossible by construction — refused with exit 2. |

## 8. Destructive operations — never

- **Never** run `docker compose down -v` when you want to preserve data — it deletes the named database volume.
- The recovery scripts (`backup-db.sh`, `restore-db-smoke.sh`, `smoke-recovery.sh`, `schedule-backup.sh`) never invoke `down -v`, `volume rm`, or `dropdb` against `POSTGRES_DB`.
- Restores always target a derived `ai_compass_restore_drill_*` name; the active Server DB is never a restore target.

## 9. Out of scope (#29 and later)

Continuous WAL/PITR, HA clusters, automated production rollback, coordinated DB+blob backup, off-host automation, a dedicated recovery health UI, and large-scale retention dashboards. This increment establishes the verified-recovery baseline that those later capabilities build on.
