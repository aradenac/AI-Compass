# PLAT-27 — Server Data Health and maintenance-only triage

A dedicated `/maintenance` route serves the **same Server frontend** as
`/?mode=server`, never seeded browser Demo records. It is available only to
users granted `auth.maintenance_view`; updates and on-demand scans require
`auth.maintenance_triage`. The `data-maintainer` role has both, without
`business_read`, `business_write`, `users_manage` or evidence downloads.

## Registered checks

`data-health@1` scans the current **read-only** catalog state and:
- compares source schemas and current revision compatibility; flags invalid,
  unsupported, obsolete and missing required properties (unknown JSON
  extensions are left intact);
- checks current catalog→revision links, task-node structure→historical
  revision alignment, and evidence link→revision→item integrity;
- checks each content-addressed evidence blob's original bytes, size and
  SHA-256 using the existing read verifier, including missing or inaccessible
  files; source filenames, document contents and evidence hashes are never
  sent in maintenance API responses;
- verifies production migration receipt source/target version and item lineage;
  this catches inconsistent persisted receipts, not failures of external
  host-side migration processes without DB records.

Each issue has an immutable UUIDv7, a permanent readable `mnt-*` ID, a
deterministic private SHA-256 deduplication key, severity and origin-check
version, assignee, first/last detection and observation count. A scan reuses
an existing issue even after it was resolved. Resolved defects detected again
reopen with an attributed event. Absent defects auto-resolve **only after a
complete successful** scan. Explicit exceptions persist with rationale and
review date until that date, when a recurring defect reopens.

Status and assignment are mutable *projections*, with append-only immutable
`DataHealthEvent` history. PostgreSQL rejects modifications/deletions of
events. No scanner or triage action edits catalog/evidence data or executes
a production migration. The last scan does not delete resolved/exception
history. Scans serialize using a transaction-level PostgreSQL advisory lock.

## Endpoints

| Verb | Path | Permission |
| --- | --- | --- |
| GET | `/api/v1/maintenance/health` | maintenance_view |
| GET | `/api/v1/maintenance/issues?status=open&page=1` | maintenance_view |
| GET | `/api/v1/maintenance/issues/<mnt-id>` | maintenance_view |
| POST | `/api/v1/maintenance/scan` with `{}` | maintenance_triage + CSRF |
| PATCH | `/api/v1/maintenance/issues/<mnt-id>/triage` | maintenance_triage + CSRF |
| GET | `/api/v1/maintenance/migrations` | maintenance_view |

PATCH supports `status` (open, resolved, exception), `assigned_to`
(active maintenance operator username, or null to clear), and for exceptions
a nonempty `rationale` and **future** ISO date `review_after`. All successful
changes create an attributed, immutable event. Mutations are POST/PATCH only;
there are no delete/bulk-resolve or arbitrary user-submitted check scripts.
The migration overview explicitly does not have an apply endpoint: staging
manual acceptance (#35) and verified recovery are required (#26).

## On-demand and scheduled operation

Initialize roles and a separate operator:

```bash
docker compose exec -T api python manage.py bootstrap_identity
docker compose exec -T api python manage.py scan_data_health --json
```

The second command is suitable as an **idempotent daily scheduled action**
using the deployment host's systemd timer or cron (e.g. 03:00 each day):

```cron
0 3 * * * cd /path/to/AI-Compass && /usr/bin/docker compose exec -T api python manage.py scan_data_health --json >> /var/log/ai-compass-data-health.log 2>&1
```

Configure this schedule on a trusted host separately; it is **not enabled**
automatically by deploying the PR. Schedule only once per deployment. Failures
must be treated as alerts (an interrupted scan transaction rolls back).

Alternatively, sign into `http://127.0.0.1:8080/maintenance` as a
maintenance-only user, select **Run checks now**, and triage recorded issues.
The status filter and issue detail display check history and review dates.

## Test and operation acceptance

```bash
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_data_health -v 2
node --check server-data-health.js
node scripts/test-server-data-health.js
bash scripts/smoke-platform.sh
```

Smoke with two isolated accounts:
1. Upload or register a synthetic evidence reference and temporarily remove
   its test-only file. Run the scan twice; verify exactly one `mnt-*` issue
   with an increasing detection counter, without exposing original file bytes.
2. Restore the same original hash bytes; rescan and observe a resolved
   event. Remove the test-only bytes once more to see the same ID reopened.
3. Record an exception with substantive rationale, assignee and future review
   date. Confirm its immutable event history survives reloading the page.
4. With `data-maintainer` only, confirm dashboard/triage works but direct
   catalog writes, Users & Access and evidence downloads are forbidden.
   With business-only credentials, confirm the maintenance API denies
   GET, scan and PATCH even when invoked directly.
5. Open `/?mode=demo` without backend; seeded Demo remains independent.

This is an additive schema migration `0008_data_health`. It neither
converts business records nor runs an accepted staging transformation.
Dropping the new tables is not a safe production rollback because that would
destroy maintenance investigation/audit history. Keep coordinated full
DB+evidence recovery points. #35/#26 operational acceptance remains open.
