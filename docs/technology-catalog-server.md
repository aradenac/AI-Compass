# Technology Catalog Server extension — PLAT-06

The **Models, Providers, Harnesses and Frameworks** lanes share the browser renderer
(`model-catalog.js`) and the `list/get/create/revise/revisions` data-provider
contract. The original seeded Demo remains a self-contained `localStorage`
dataset and **is never read, imported or synchronized** into PostgreSQL.

## Authoritative Server API

Models retain the existing `/api/v1/models` endpoints. The three additional
technology types use exactly the same API contract under
`/api/v1/catalog/{type}`, where `type` is one of
`provider`, `harness`, `framework` (singular):

| Operation | Method and endpoint |
|---|---|
| List | `GET /api/v1/catalog/{type}` |
| Create | `POST /api/v1/catalog/{type}` |
| Current revision | `GET /api/v1/catalog/{type}/{public_id}` |
| Full history | `GET /api/v1/catalog/{type}/{public_id}/revisions` |
| Append revision | `POST /api/v1/catalog/{type}/{public_id}/revisions` |
| Pinned revision | `GET /api/v1/catalog/{type}/{public_id}/revisions/{number}` |
| Immutable schema | `GET /api/v1/catalog/schemas/{type}?version=1` |

A create payload is `{"name":"Provider X","properties":{"hosting":"cloud", "pricing":"PAYG","custom":{"region":null}}}`.
Appending a revision requires `{"expected_revision":"r001","name":"Provider X v2"}`;
missing `properties` retains original JSON without default insertion. Explicit
`properties` must be a JSON object and is validated against the immutable
registry. Unknown extensions are preserved. A stale edit returns 409, invalid
data 400, and a wrong-type ID 404. Reads and mutations require Django
`business_read` and `business_write` respectively; POST requires session CSRF.

All items use UUIDv7 technical IDs and permanent `mdl-*`, `prv-*`,
`hrn-*`, `frm-*` public IDs; history and audit rows are append-only.
The new Provider/Harness/Framework schema v1 records are registered through
migration `0003_technology_catalog_schemas` (Model v1/v2 untouched).
The #25 compatibility metadata remains available on reads and prevents
writes to unsupported historical schemas.

## Semantic distinction

- **Provider** captures hosting, access, pricing, endpoint and optional regions.
- **Harness** captures CLI/IDE/web/agent interface, tool integrations and
  optional capabilities.
- **Framework** captures methodology/process, orchestration, stages and
  participant roles. It represents a process **only**; creating a Framework
  cannot create a scored AI Solution, an execution, or a benchmark result.

Server starts with **zero** business catalog records. In the browser, visit
`/prototype.html?mode=server`, sign in as Contributor, use the appropriate
lane's **+ Add**, save, refresh or sign in from another browser, edit and inspect
history. Readers can inspect but not edit; no fallback to fictional Demo
data occurs on API failure.

## Reproducible checks

```bash
docker compose up -d --wait --build
docker compose run --rm api python manage.py migrate --noinput
docker compose exec -T api python manage.py test config --verbosity 1
node scripts/test-model-catalog.js
node scripts/test-catalog-types.js
# With a real CI contributor bootstrapped as described in docs/local-installation.md:
AI_COMPASS_TEST_PASSWORD=... python3 scripts/smoke_catalog.py ci-contributor
```

The required pull-request workflow runs Django tests, the real two-session
HTTP smoke for all three types, both JavaScript tests, and the existing
Demo/Model/backup/restore regressions. Neither framework execution nor
campaign-scoped participant Model/Provider/Harness trios are implemented here;
those belong to #13 and #16.
