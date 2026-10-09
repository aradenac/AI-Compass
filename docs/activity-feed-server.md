# Activity Feed — Server audit read model (PLAT-24)

The authenticated **Server mode** Activity Feed projects already-committed
append-only source rows without copying, rewriting or guessing historical data.
Demo mode remains an independent local browser prototype and requires no Server.

## Sources and semantics

- `CatalogAuditEvent` — versioned Model, Provider, Harness, Framework and Task
  creations, revisions and task reorganizations. Each event has a durable UUID,
  actor FK, timestamp, object public ID, and immutable `CatalogRevision` FK.
  Publishing a component by changing `properties.publication` from any other
  state to `published` emits `published`; reversing that state emits
  `unpublished`; other edits emit `revised`.
- `UserAccessAuditEvent` — account creation, role and activation changes
  recorded by PLAT-28. Only `users_manage` operators can view these events.
  Sensitive audit `details` are **never** included in lists/exports; the
  privileged detail view exposes only allow-listed role/status/session-count
  information. No emails, password resets' credentials or arbitrary JSON.
- Fields: event UUID, timestamp, actor username, operation, object type, public
  catalog ID or `user:<pk>`, original revision number and UUID (when present),
  committed success status. Historical actor role and BU were **not captured**
  by existing rows and are represented by null, not inferred from current state.
  A rejected request creates no success audit event.

New domain producers should write append-only source events **inside the same
transaction** as the revision, using `record_catalog_event(...)` when the
domain has a `CatalogItem` + `CatalogRevision`. New sources can join the
permission-scoped projection without replacing existing immutable rows.
Future campaign, recommendation, feedback and actual publication lifecycles
will add their own genuinely committed events; no placeholder activity is seeded.

## Permissions and endpoints

| Path | Permission | Contract |
| --- | --- | --- |
| `GET /api/v1/activity` | `business_read` and/or `users_manage` | Newest-first, 50/page, max 20 pages; optional filters |
| `GET /api/v1/activity/{event_uuid}` | appropriate source permission | Source-specific event detail; unauthorized source → 404 |
| `GET /api/v1/activity/export?format=json` | same | Filtered JSON up to 1,000 events |
| `GET /api/v1/activity/export?format=csv` | same | Filtered CSV up to 1,000 events; spreadsheet-formula escaped |

Supported query filters: `type` = all/model/provider/harness/framework/task/access,
`actor` = exact username, `action` = operation, `from` / `to` = offset-aware
ISO-8601 timestamp, `page` = 1–20 for feed, `format` on export only.

Both list and export combine the visible sources in a deterministic descending
`(created_at, event_uuid)` order. An over-limit export returns HTTP 422 and
asks to narrow the filters: it never silently produces a partial archive.

`business_read` alone cannot request account audit (`type=access`), including
direct calls, exports or event UUID detail. `users_manage` alone cannot inspect
business audit. Unauthenticated requests return 401; authenticated users
without either permission return 403. No token or historical record properties
are included in exported rows. All responses use `Cache-Control: no-store`.

## Reproducible validation

```bash
docker compose exec -T api python manage.py test config.test_activity -v 2
docker compose exec -T api python manage.py makemigrations --check --dry-run
node --check server-activity.js
node scripts/test-server-activity.js
bash scripts/smoke-platform.sh
```

Operator smoke: sign into `?mode=server` as contributor; create a draft Model,
edit it, publish it, inspect event revision IDs in the Activity Feed; filter by
actor/type and download CSV/JSON. Sign into a user-admin-only account, create and
deactivate another account, verify only these account events are visible. Sign
into a data-maintainer-only account and confirm the feed is hidden and direct
API/export reads are denied. Sign out and confirm activity disappears. Reload
the Server page: historical events must persist. Open Demo without backend:
seeded local Activity Feed must still run with no Server API calls.

**Migration impact:** None. The feed is a read-only projection of existing
immutable, protected source audit tables. No migration or data conversion is
applied in this issue.
