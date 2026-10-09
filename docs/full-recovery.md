# Coordinated PostgreSQL + evidence disaster recovery — PLAT-29

This supersedes DB-only operations **for complete recoverability** without removing the
existing PLAT-34 commands. A valid full recovery point consists of four inseparable files:

- \`ai-compass-<UTC>-<ID>.dump\` (custom PostgreSQL snapshot);
- \`.dump.blobs.tar\` (private content-addressed evidence bytes);
- \`.dump.full.json\` (DB/bytes SHA-256, count, hashes, provenance-linked DB inspection, schema digests, restored API download result);
- \`.dump.full.complete\` (SHA-256 of the manifest, committed **last**).

All payloads are checked twice: during the initial completely independent restore
and during offline \`verify\`. The full manifest is immutable and links precisely one
DB capture to one evidence archive. No incomplete/failed/corrupt/missing set is a
valid full recovery point.

## Daily operator workflow

Prepare **an existing independently mounted, privately protected directory**.
A missing mount or destination on the application filesystem is refused; the
CLI will not manufacture a fallback. A different filesystem is necessary but
does **not** guarantee off-host redundancy: the operator must provision and
protect independent storage (e.g. protected NAS, separate backup disk).

\`\`\`bash
# From the AI Compass repository root with Docker and running services:
python3 scripts/full_recovery.py --destination /mnt/ai-compass-backups backup --keep 14
python3 scripts/full_recovery.py verify /mnt/ai-compass-backups/ai-compass-...dump
python3 scripts/full_recovery.py drill  /mnt/ai-compass-backups/ai-compass-...dump
python3 scripts/full_recovery.py --destination /mnt/ai-compass-backups status
# Default daily systemd --user timer now invokes full_recovery.py:
python3 scripts/install-backup-timer.py --destination /mnt/ai-compass-backups --require-external --dry-run
python3 scripts/install-backup-timer.py --destination /mnt/ai-compass-backups --require-external
systemctl --user list-timers ai-compass-backup.timer
journalctl --user -u ai-compass-backup.service -n 80
\`\`\`

\`status\` is compact machine-readable JSON: exact scope, backup ID, age, last
fully verified recovery point, failed attempts, and latest successful independent
restore. Default freshness window is 36 hours (\`status --fresh-hours N\`).
Separate JSON restoration reports in \`reports/\` contain the result and failure
stage. Pruning occurs only **after a new complete recovery point is verified**;
the newest N full points are retained separately from historical DB-only points.

For PLAT-34 DB-only compatibility, the existing
\`scripts/backup-db.sh\` and \`scripts/recovery.py backup|verify|drill\` remain
unchanged. \`install-backup-timer.py --db-only\` deliberately selects the old
DB-only scheduling mode. **Do not mistake a DB-only snapshot for a full point.**

## Consistency boundary and outage

1. Check the pinned Compose project, named \`ai-compass_evidence\` Docker
   volume, the existing independent destination, and required images.
2. Gracefully stop the **API service only** (\`docker compose stop -t 30 api\`),
   allowing in-flight application writes to terminate. PostgreSQL stays running.
   All supported business writes enter via this API. Direct DBA SQL writes
   outside the application are **not** protected by this boundary; do not make
   them concurrently.
3. Capture the PostgreSQL custom-format dump and the immutable \`blobs/\`
   directory using a *read-only* mount of the source evidence volume.
   Always restart the API service in a \`finally\` block, even after failure.
4. Once source services are back up, restore the DB in a **random, networkless,
   volume-free PostgreSQL container**, stage archive bytes in a fresh local
   private directory, compare every reference/hash/size with the recovered
   DB and check historical ID/revision/schema fingerprints. Start an additional
   ephemeral API container in that disposable Postgres network namespace,
   mount **only the staged evidence directory read-only**, authenticate with a
   recovered uploader and GET the original bytes through the actual Django
   download view. Both disposable containers and temporary evidence bytes
   are removed afterwards.
5. Only when every check passes atomically publish the dump, tar, manifest,
   and final \`.full.complete\` marker. Any failure records a
   \`*.full.failed.json\` stage and does **not** supersede last-good.

The unavoidable brief API interruption during capture is visible to users:
this is an explicit write freeze, **not** a transparent online PITR backup.
Do not schedule during critical interactive benchmark sessions.

## Safety and incident handling

- \`verify\` checks both complete files **offline** (dump/tar SHA-256 + size,
  manifest/marker coupling and *every contained* content-addressed blob).
- \`drill\` requires **no running source services or source volumes**. The
  production Postgres and evidence volume are not mounted, opened, dropped,
  replaced or overwritten during any drill.
- Missing, extra, duplicate, corrupt, wrongly-sized or unsafe/symlink tar
  contents fail before a successful recovery report.
- If a snapshot fails or looks stale, run \`status\`, inspect
  \`*.full.failed.json\` and last \`reports/drill-*.json\`; do not promote.
- Run \`docker compose exec -T api python manage.py reconcile_evidence --json\`
  periodically. Existing finalized **orphan blobs** require explicit triage;
  this strict full backup refuses unreferenced payloads rather than silently
  discarding them. Never remove source evidence volumes as a recovery
  experiment.
- Use separate encryption/access controls and operational off-host
  replication for the independent destination as appropriate. This feature
  does not implement key management, HA, PITR/WAL, an automated production
  restore button, or cross-cloud backup automation.

## Repeatable tests

\`\`\`bash
python3 -m unittest discover -s scripts -p 'test_full_recovery.py' -v
python3 -m unittest discover -s scripts -p 'test_recovery.py' -v
# CI runs real two-session evidence upload first, followed by:
# full backup -> stop source DB/API -> isolated full drill (including Django
# download) -> restart source -> verify status and corruption refusal.
\`\`\`

The CI-only switch \`--allow-local-ci\` requires both \`GITHUB_ACTIONS=true\`
and \`AI_COMPASS_FULL_RECOVERY_CI=1\` and is unavailable to operators; it is
used only because hosted test runners lack a separately mounted recovery
disk. This exception is not a deployment recommendation.

For recovery after a real incident, preserve the verified **four-file set**
on its independent destination and first perform the isolated drill.
Production cutover is deliberately a separately authorized process and is
not implemented by this tool.
