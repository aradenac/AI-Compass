# PLAT-10 — Persistent Test Cases and fork lineage

Test Cases are **experimental challenge instances**, not functional task-tree
categories. Server stores Test Cases independently in PostgreSQL. Demo remains
a standalone fake browser localStorage prototype: **no synchronization**.

## Data and immutable history

- A `CatalogItem` of type `test_case` provides stable UUIDv7 and human-readable
  permanent `tcs-*` public ID. Each edit appends an immutable `CatalogRevision`
  with a version-pinned JSON Schema; arbitrary unknown JSONB extension fields
  survive edits/forks. `CatalogAuditEvent` records created/revised/forked.
- The `TestCase` relational row pins a real `TaskNode` FK and
  `task_revision_at_creation`. Task renaming, moving or reordering does not
  change those links. The Test Case is **not** a child task.
- Each original Test Case is version `1.0` within its fork tree. A fork is a
  **new independent identity** with explicit `fork_parent` and immutable
  `fork_source_revision`; versions follow `1.0.1`, `1.0.2` and
  `1.0.1.1`. Version suffixes are allocated on save under a PostgreSQL
  transaction advisory lock, not by guessing a number in the browser.
  The lock also serializes revisions versus forks to pin exact source revisions.
- PostgreSQL rejects mutation/deletion of Test Case identity, version and
  task/parent/source pointers, and rejects inconsistent task or fork references.
  Historical content revisions and evidence links retain immutable FKs.
- No additional benchmark protocol object is invented. The challenge JSON
  contains objective, inputs, constraints, expected outputs and Definition of
  Done. Schema requires nonempty objective and DoD. Attached prompts, input
  documents and expected-output exemplars use the **existing #17 Evidence API**
  at `/api/v1/catalog/items/<tcs-id>/evidence`, including exact revision FKs.

## Server API

| Method | Path | Effect |
|---|---|---|
| GET | `/api/v1/test-cases[?task_id=tsk-...]` | List persisted challenges |
| POST | `/api/v1/test-cases` | Create root, task FK, version 1.0 |
| GET | `/api/v1/test-cases/<tcs-id>` | Current revision + lineage |
| PATCH | `/api/v1/test-cases/<tcs-id>` | Append revision; `expected_revision` required |
| POST | `/api/v1/test-cases/<tcs-id>/fork` | Copy pinned parent revision, allocate child version; `expected_parent_revision` required |
| GET | `/api/v1/test-cases/<tcs-id>/revisions` | Complete original revision history |
| GET | `/api/v1/test-cases/<tcs-id>/revisions/<number>` | Exact historical snapshot |

Reads require `business_read`; writes require `business_write`, same-origin
Django session and CSRF token. The backend validates real task IDs, optimistic
revision tokens, registered schema, and safe fork ancestry. No silent deletion
or parent reattachment is supported.

## Smoke checks

```bash
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_test_cases -v 2
node --check server-test-cases.js
node scripts/test-server-test-cases.js
```

Log in to `/?mode=server` as a contributor, create a real Task in **Task
management**, then create a Test Case in **Test Design**, set objective and DoD,
edit and reopen it, and fork it twice; inspect versions `1.0.1` and `1.0.2`,
then fork again to produce a nested `1.0.1.1`. Reload and verify the history
persists. Rename/move the Task and verify the Test Case still points to the
same permanent task ID. Inspect attached documents through the original
Evidence APIs. Sign into a maintenance-only role to confirm direct REST access
is denied, and open Demo without backend to confirm fake records remain local.

**Schema change:** additive `0009_test_case` (one empty business table, new
immutable Test Case schema row and append-only relationship guards); no
historical business data migrated. Avoid dropping this table in production,
which would discard fork lineage. No measured results, campaigns or benchmark
scores are implemented by this issue.
