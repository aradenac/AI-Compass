# FUT-10 — Versioned partial publication of benchmark Runs

## Authority and lifecycle

A Campaign plan/matrix is not a publication. In Server, **only** a specifically
selected immutable completed Run with an applicable pinned Setup Recipe may be
published. Runs with a valid failed DoD are publishable negative observations.
Missing required tariff meters leave the session pending and are never upgraded
to completed evidence. Waivers, pending sessions and unselected matrix rows do
not create measured results.

Publication is an immutable `publication_event` on a new Campaign
`CatalogRevision`: `kind: publish`, explicit replacement `runs` with
Run UUID, closing checkpoint, Test Case, experiment method, historical guide
and modules, pinned pricing-offer revision IDs and configuration source, plus
the *then-current* matrix coverage. These records are never re-pinned from
current Catalog or Guide heads. An explicit `revoke` event is separate from
`reopen`. Revision history and as-of publication pointers survive later edits.

**Effective publication** is the latest publication event of a Campaign,
provided it is `publish`. Reopening, in-progress sessions or a new draft
revision leave the last published subset untouched. An explicit republish
replaces the whole selection, and previously published IDs can be omitted
only with a written removal reason. The current publication uses exactly this
membership, not the current Campaign status or matrix coverage.

## API and workgroup usage

All routes require authenticated Server identities (no Demo data exchange):

| Operation | Method / route | Required permission |
| --- | --- | --- |
| Effective published selection | `GET /api/v1/campaigns/{id}/publication` | `business_read` |
| Private eligibility review and blockers | `GET /api/v1/campaigns/{id}/publication/review` | `business_write` or `publication_review` |
| Commit selection | `POST /api/v1/campaigns/{id}/publication/publish` | `publication_review` |
| Explicitly withdraw whole selection | `POST /api/v1/campaigns/{id}/publication/withdraw` | `publication_review` |

For publishing, Campaign must be in `under_review`. Send authenticated CSRF
and JSON `{"expected_revision":"r003","run_ids":["run-..."],"removal_reason":""}`.
One or more *already completed* eligible Run IDs are required; the selected
membership is validated server-side and written in the same transaction as
the Campaign lifecycle revision. Reviewer may be the original author;
there is no compulsory second reviewer. Existing
`POST /api/v1/campaigns/{id}/actions/publish` also accepts this exact
selection. A different Campaign Run, stale revision, absent/legacy-inadequate
guide, missing setup module, non-selected matrix attempt or loss of prior
published membership without a reason fails closed.

When the Campaign is `published`, the workgroup can `reopen` it and
continue work. To republish, `close` again for review and publish an explicit
replacement selection. Historical `/revisions/{number}` contain the
as-of effective publication pointer. `unpublish`/`withdraw` records an
explicit revocation, not a destructive delete.

In Server's Workgroup Campaign management, use **Published evidence** to
inspect the effective manifest and (when authorized) choose eligible Runs.
Disabled entries show missing guide or selection criteria; reviewers submit
a checked selection, with a removal reason if dropping historic members.
The permanent offline Demo remains independent and does not import real Runs.

## Read-side contracts, privacy and rollout

`GET /api/v1/results/explorer` defaults to `scope=published` and uses
the same membership authority. `scope=private` requires an editor/reviewer.
`GET /api/v1/runs` shows private data to those roles, otherwise only effective
published Runs; direct unpublished Run reads return 404 for read-only users.
Read-only responses omit raw session checkpoint data. Campaign evidence
attachments are downloadable to read-only users only if actually pinned by an
effective published Run; mere upload does not constitute publication.

The latest event is queried from existing immutable Campaign revisions;
**no new database migration or production data backfill** is required.
New records are append-only and historical as-of interpretation is preserved.
Rollback of application code retains the JSON revision history (do not delete
published artifacts). Reverting to a pre-FUT-10 build is **not** permission
safe without an operational gate: old Run/explorer endpoints expose draft
data and old publish actions do not enforce Run eligibility. No production
GO is implied by CI; operator-controlled release, permissions and archival
recovery checks remain mandatory.

## Testing

Django: `python manage.py test config.test_publication` against disposable
PostgreSQL. Existing campaigns/matrix, Runs, setup and security suites should
run as regressions. Shared Server frontend syntax: `node --check server-campaigns.js`.
Tests cover rejected legacy/inadequate guide, auth, failed-DoD inclusion,
reopen, replacement of published subset, removal reason and non-retroactive
guide corrections. Full Run correction/withdrawal effects are FUT-11 (#85),
not an implicit effect of FUT-10.
