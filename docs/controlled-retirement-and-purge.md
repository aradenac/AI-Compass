# Controlled retirement, orphan inventory and privileged purge — FUT-18

Implements the maintenance half of the
[retirement/retention/purge specification](../future-evolutions/controlled-retirement-and-purge.md):
**logical retirement**, a read-only **orphan inventory** and **dry-run preview**,
a separately privileged **idempotent physical purge**, and a **disabled-by-default,
versioned retention policy**. The business-lifecycle half (publication
membership, Run correction/recall) is delivered by the existing
[partial publication and Run corrections](publication-and-information-lifecycle.md)
features and is not duplicated here.

## Model and guarantees

| Concern | Implementation |
| --- | --- |
| Logical retirement | `RetirementRecord` (OneToOne on `CatalogItem`, `PROTECT`) hides an object from current views while preserving its stable public id, immutable revisions and historical references. It never cascades a physical delete. |
| Tombstone trail | `RetirementEvent` — append-only, DB-trigger-protected. Records `retired`/`restored` in order, so the trail survives a restore. |
| Retention policy | `PurgePolicy` — single active versioned row; `enabled` defaults to **false**. Grace duration and eligible classes are administrative decisions; **30 days is illustrative**, never a universal rule. |
| Candidates | `PurgeCandidate` — durable dry-run snapshot. Idempotent per `(subject, kind)`; `first_seen_at` is the **durable orphan-since journal** used for grace. |
| Receipt | `PurgeReceipt` — append-only, DB-trigger-protected result: actor, reclaimed bytes, purged/blocked counts and per-subject detail. |

### What never qualifies as an orphan
- Any evidence blob with **one or more live `EvidenceLink`s** — including a shared
  deduplicated blob owned by another object. A zero link count is never assumed;
  a still-referenced subject is reported `re_referenced` and left untouched.
- Any standalone Catalog object that merely lacks an incoming link. Only an
  **explicitly retired** record is a managed-record candidate, and managed-record
  rows are **deferred** to their own domain policy — this feature never physically
  removes them (`record_purge_deferred`).
- Any digest whose bytes are missing or inconsistent — reported
  `disk_inconsistent`, a diagnostic, and purge **fails closed**.

### Grace window
Grace is counted from the durable candidate journal (`first_seen_at`), i.e. the
later of first verified orphan eligibility and last-reference removal — never
from upload alone. Before any inventory observation the fallback is the upload
time, so a blob can never be treated as older than it is.

## Privileged physical purge and the immutability exception

Evidence tables are append-only by database trigger. The specification (§5)
requires that ordinary deletion is *not* physical erasure, while (§6.3.4) permits
removing eligible physical bytes and their metadata *only when safe*. The purge
therefore opens a **transaction-local, DELETE-only** guard window
(`SET LOCAL ai_compass.purge_blob = 'on'`) that the evidence-blob trigger honours
for a verified, unreferenced row:

- **UPDATE stays forbidden everywhere**; the exception is DELETE-only on
  `config_evidenceblob`.
- It is **opt-in per transaction** and unreachable from ordinary request paths —
  only `retirement_services.purge`, behind the `purge_manage` capability, sets it,
  and only after a row lock plus an advisory transaction lock prove the subject
  is still unreferenced.
- The window closes automatically at transaction end (`SET LOCAL`).

## Authorization (separate grants)

| Capability | Endpoints |
| --- | --- |
| `maintenance_view` | inventory, preview, policy read, receipts, retirement history |
| `retirement_manage` | retire, restore |
| `purge_manage` | policy edit, run purge |

`data-maintainer` gains `retirement_manage`. The new `purge-operator` role
(`maintenance_view`, `audit_view`, `retirement_manage`, `purge_manage`) holds the
destructive grant. A Data Maintainer's read-only ability never implies purge.

## HTTP contract

All under `/api/v1/maintenance/retirement`; every path enforces session RBAC,
CSRF on writes, and `Cache-Control: no-store`.

| Operation | Endpoint |
| --- | --- |
| Orphan inventory | `GET /inventory` |
| Dry-run preview | `GET /preview` |
| Read policy | `GET /policy` |
| Edit policy | `PATCH\|PUT /policy/edit` |
| Run purge | `POST /purge` (`{"subjects": [...], "confirm": "purge"}`) |
| Purge receipts | `GET /receipts` |
| Retirement history | `GET /{public_id}` |
| Retire / restore | `POST /{public_id}/retire`, `POST /{public_id}/restore` |

## Verification

```bash
COMPOSE_PROJECT_NAME=<proj> docker compose -p <proj> exec -T api \
  python manage.py test config.test_retirement
```

18 focused tests cover: retirement hides and preserves identity/history; restore
keeps the tombstone trail; a reader is refused; inventory excludes a referenced
blob and includes a true orphan; grace is enforced from the durable journal and
repeatable; zero grace marks eligible; purge removes only a true orphan and
reclaims bytes while reporting the protected subject `re_referenced`; the
confirmation token is required; a disk inconsistency fails closed; a shared
deduplicated blob is protected while any reference remains; a purged digest is
unreachable; the receipt is immutable; the policy is disabled by default and
versioned; and purge/policy HTTP paths enforce `purge_manage` + CSRF.

## Migration and rollback

- **Migration:** `0029_retirement_and_purge` — additive (five new tables plus
  append-only triggers). It redefines the shared
  `ai_compass_no_revision_mutation()` function to add the guarded DELETE case;
  the reverse restores the unconditional body and drops the new triggers.
- **Rollback:** `python manage.py migrate config 0028_resource_budgets`. The new
  tables are dropped and the immutability function returns to its unconditional
  form. No existing evidence/catalog data is altered by the migration itself;
  rollback after a purge only removes the purge bookkeeping, not the already
  deleted bytes.
- **Existing behaviour:** no existing test changed; the full `config` suite (275
  tests) stays green after the trigger exception.

## Boundaries (out of scope here)

Standalone/independent knowledge (Watch entries, external sources, Models,
Guides, Test Cases) is never auto-purged for lacking links; managed-record
physical removal is deferred to its own domain; automated scheduled GC execution
and the exceptional authorised-erasure path remain separately scoped; physical
deletion from active store does not claim deletion from immutable backups
(see [evidence-storage](evidence-storage.md) backup limitation).
