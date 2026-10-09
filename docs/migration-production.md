# PLAT-26 — Controlled production migration replay

**Status:** implementation can be merged and tested without granting production
approval. The production replay remains **blocked until PLAT-35 has been manually
accepted using the real staging frontend** for the *same clean application
commit and registered transformation checksum*. These instructions do not claim
that operator acceptance has happened.

## Separation of authorities and safety boundaries

This feature registers only `model-v1-to-v2@1`. No arbitrary SQL, Python,
user-supplied patches or Demo data are accepted. The staging migration
(`stage_model_v1_to_v2.py`) is executed only on the isolated disposable Server
from PLAT-35. The production executor is a **different** Django management
command (`promote_model_schema`), bound to a signed approval envelope generated
by a trusted host-only CLI. It refuses an unauthorized operator, an altered
transformation, mismatching original schema/evidence data, a stale recovery
fingerprint, unknown extensions that are invalid in v2, or a live Server API.

The operator must be an active user with **`auth.maintenance_triage`**, e.g.
the independent `data-maintainer` role; this does not imply business_write,
users_manage, platform_manage or superuser. Docker + the host recovery mount
remain privileged operational capabilities: limit machine access accordingly.

The host script (`scripts/migration_promote.py`) **first verifies**:
- the original complete four-part PLAT-29 staging-source archive and every
  original evidence blob hash;
- the exact PLAT-35 report and separately retained **accepted** verdict file,
  including acknowledgement of inspection through the actual Server frontend,
  non-empty review notes, passed automated checks and unchanged candidate ID;
- currently checked out clean Git commit matches the accepted staging build,
  and the registered transformation SHA-256 is unchanged.

It then queries the current Server with a read-only preview. On explicit apply
only, it creates and independently verifies a **new** full DB+blobs restoration
point on a pre-existing, separate mounted filesystem, checks the current schema
against accepted staging, persists a signed copy of the recovery/preflight
fingerprint, and freezes the production API before mutation.

Each promotion invocation writes **at most 100 items** in one atomic PostgreSQL
transaction. For every item, the old revision is retained, a new v2 revision
preserves unknown JSON properties and is attributed to the migration operator,
a transactional `schema_migrated` audit event is created, and an append-only,
DB-trigger-protected `ProductionMigrationReceipt` records the old/new revision
FKs, candidate, exact artifact/build, operator and full recovery point.

An interruption does not erase committed batches. The retry uses the **same**
verified signed recovery point saved in `.local/promotions` and reconstructs
the original fingerprint by excluding that candidate's already-receipted
revisions/events. Any unrelated change after the recovery point is refused.
A failed operation leaves the Server API stopped for investigation: do **not**
start/restore it blindly. Recover only from the coordinated recovery point
with DB + evidence integrity validation, never by promoting a staging database.

## Commands

First complete PLAT-35 with a **real human browser inspection**, for example:

```bash
python3 scripts/migration_stage.py create --snapshot /mnt/backup/ai-compass-<snapshot>.dump
# Inspect old/new records, evidence and unknown fields in ?mode=server on staging.
python3 scripts/migration_stage.py verdict <candidate> accepted --frontend-checked \
  --notes "Inspected old and new records and original evidence through the staging Server frontend"
python3 scripts/migration_stage.py discard <candidate>
```

On the machine with the real operational Server and independent recovery mount:

```bash
python3 scripts/migration_promote.py preview --candidate <candidate> --operator maintainer
# Review affected count, blocked fields and the exact approved snapshot/build.
python3 scripts/migration_promote.py apply --candidate <candidate> \
  --confirm-candidate <candidate> --operator maintainer \
  --destination /mnt/independent-recovery
```

`--confirm-candidate` is mandatory and must exactly match. This is not a
browser-side migration operation. If a batch fails, inspect the saved recovery
reference in `.local/promotions/<candidate>.approval.recovery`. A repeat
`apply` uses the original signed proof (not a snapshot of partly migrated
records). A mismatched source, forged acceptance or missing recovery data
stops the operation without silent promotion.

## Verification

```bash
python3 -m unittest discover -s scripts -p test_migration_promote.py -v
docker compose exec -T api python manage.py test config.test_schema_promotion -v 2
docker compose exec -T api python manage.py makemigrations --check --dry-run
bash scripts/smoke-platform.sh
```

Full platform CI confirms Demo and Server separation, staging discard/recreate,
coordinated recovery and permission checks. The operational production replay
is **not** executed in CI and must not be claimed as manually approved before
the frontend acceptance of PLAT-35. The database migration
`0007_production_migration_receipt` only adds an immutable ledger; it does not
convert any object data. Never downgrade/drop this table on production as a
rollback strategy.
