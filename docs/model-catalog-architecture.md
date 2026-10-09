# AI Compass — Model Catalog API and Immutable Identity (PLAT-03)

> **Status:** Implemented backend slice · **Scope:** Model type only · **Related:** [Platform Architecture](platform-architecture-and-data-governance.md) · [Local Installation](local-installation.md) · [Roadmap](platform-implementation-roadmap.md)

## Scope and responsibility

PLAT-03 is the first persistent, audited business object in **Server mode**. A user with `business_read` can list/get Models and past revisions; one with `business_write` can create a Model and append new revisions. Authentication is the real Django session from PLAT-02 (cookie + CSRF header on POST).

The exact same `prototype.html` supports standalone **Demo mode**, using seeded fake `localStorage` records. [PLAT-05](https://github.com/aradenac/AI-Compass/issues/5) binds the graphical Models lane to this API in Server mode while keeping the independent Demo data adapter. **PLAT-03 does not synchronize, import or overwrite Demo records.**

## Physical model

```text
ObjectTypeVersion(type_slug, version, json_schema, UUIDv7)
             |                         [never UPDATE/DELETE]
             v
CatalogItem(UUIDv7 id, public_id UNIQUE, immutable type_slug,
            current_revision -> CatalogRevision)
   | 1:N                          |
   v                              v
CatalogRevision(UUIDv7 id, item FK, number, schema_version FK,
                display_name, properties JSONB, author FK, timestamp)
   | 1:N
   v
CatalogAuditEvent(UUIDv7 id, item FK, revision FK, actor FK, action, timestamp)
```

- Every CatalogItem receives a **UUIDv7** technical primary key and a public HRID `mdl-word-word-word`; names are editable but **both IDs and type are permanent**. Public IDs are never recycled. Word lists are curated/versioned in `backend/config/catalog_ids.py`; PostgreSQL enforces global `UNIQUE(public_id)` and collisions cause bounded atomic retries.
- `CatalogRevision` and `CatalogAuditEvent` are append-only. The `current_revision` pointer is advanced in the **same transaction** as creation of the revision and audit event. Database triggers reject UPDATE/DELETE of revisions, schema versions and audit events; catalog identity changes and hard-delete are also rejected.
- `(item, number)` is unique; human revision labels are `r001`, `r002`, etc. Historical revision URLs do not change. Each revision has an immutable link to its schema definition version and author.
- The baseline `ObjectTypeVersion("model", 1)` JSON Schema is installed by migration `config.0001_initial`, whose source freezes that schema. Its documented properties include positive integer `context_window`, boolean `supports_tools`, `accessible`, string `model_identifier`, array of `modalities` and enumerated `reasoning_effort`. Arbitrary additional JSON keys are **accepted and preserved** to support future evolution. Invalid *known* fields are rejected, not silently coerced.
- Historical data and schema rows remain available even if future versions become available. Schema migrations/compatibility adapters are a later issue. No deletion or rename endpoints are offered.

**Concurrency:** each revision uses a PostgreSQL row lock on the CatalogItem and requires `expected_revision`. A stale update returns HTTP 409 without creating a revision. HRID collisions are retried inside independent atomic transactions, then fail explicitly if repeatedly occupied.

## API contract

All endpoints are relative to `http://127.0.0.1:8080`; all require `business_read` except POST operations, which require `business_write` and a CSRF header.

| Verb | Path | Result |
| --- | --- | --- |
| GET | `/api/v1/models` | `{"results":[...]}`, Model current revisions |
| POST | `/api/v1/models` | Create, HTTP 201 + `Location` |
| GET | `/api/v1/models/schema` | Registered `model` schema version 1 |
| GET | `/api/v1/models/{public_id}` | Current revision |
| GET | `/api/v1/models/{public_id}/revisions` | Complete historical revisions |
| POST | `/api/v1/models/{public_id}/revisions` | Append a validated revision, HTTP 201 |
| GET | `/api/v1/models/{public_id}/revisions/{number}` | Exact historical revision (number e.g. 1) |

Example POST payload:

```json
{
  "name": "GLM-5.2",
  "properties": {
    "context_window": 262144,
    "supports_tools": true,
    "reasoning_effort": "max",
    "provider_notes": {"status": "unverified"}
  }
}
```

Example append-only edit:

```json
{"expected_revision": "r001", "name": "GLM-5.2 (corrected)"}
```

Omitting `properties` on edit preserves all previous attributes, including unrecognized vendor-specific fields. Providing `properties` replaces the **new** snapshot properties; the old snapshot never changes.

Response contains `id` (HRID), `uuid` (UUIDv7), `type`, `name`, `properties`, `revision`, `schema_version`, `created_at`, and `created_by`. No unknown metrics are invented. Invalid input is HTTP 400 (`invalid_model`); stale edit HTTP 409 (`revision_conflict`); missing item HTTP 404; unauthenticated HTTP 401; insufficient privilege HTTP 403; CSRF failures HTTP 403.

**Security/deployment:** this is a same-origin, cookie-authenticated API, not a public bearer-token API. No cross-origin CORS, unauthenticated writes, or fake-identity fallbacks. The local HTTP Docker setup binds to loopback only and is not production-ready without HTTPS, secure cookies and request throttling.

## Reproduction and smoke tests

After installing the stack and running migrations as in [Local Installation](local-installation.md), create a contributor account:

```bash
docker compose exec -T api python manage.py bootstrap_identity
docker compose exec api python manage.py bootstrap_identity \
  --username model-editor --role contributor
```

Get the real CSRF cookie from `/api/v1/auth/csrf`, login using `/api/v1/auth/login`, then POST to `/api/v1/models` with `X-CSRFToken`; after login, **refresh** the cookie (Django rotates CSRF upon login). Use `/api/v1/models/{id}/revisions` to append with the current `expected_revision`.

To run the concise automated suite:

```bash
docker compose exec -T api python manage.py test config --verbosity 1
docker compose exec -T api python manage.py makemigrations --check --dry-run
bash scripts/smoke-platform.sh
```

The CI pipeline also provisions a throwaway contributor and runs `scripts/smoke-models.py` through Caddy: login, fetch schema, create, list, revise, read old revision, reject stale/invalid edits, log out and reject an anonymous request. Existing Demo/offline, role-separation and backup/restore smoke checks remain enabled.

**PLAT-05 browser contract:** `model-catalog.js` defines the common `LocalStorageDataProvider` and `ApiDataProvider` shape (list/get/create/revise/revisions) and the single shared Models card renderer. Demo uses its existing browser localStorage callbacks. Server uses authenticated same-origin Django fetch, preserves unrecognized JSON properties, sends `expected_revision` on edit and exposes full read-only revision history. An HTTP 401/403/409 or backend outage is shown as a failure, never as a fake local fallback. The Server page deliberately exposes only Models among the four technology catalog types.

**Explicitly deferred:** generic type registry UI, all non-Model Server catalog types, legacy export/import, external storage and advanced migration tooling; these belong to later increments.
