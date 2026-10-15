# PLAT-11 — Versioned reusable Setup Guides (Server)

> **Approved UI target (2026-10-15):** [simplified Guides & Charter interface](guides-charter-workgroup-ui-spec.md) · [HTML](prototypes/guides-charter/index.html). The Workgroup view hides revision numbers and advanced composition, offers Publish/Unpublish and confirmed Delete, and does not show review or prepublication quality gates. **Existing Server revisions, concurrency checks and no-DELETE API remain unchanged.** A future deletion implementation must first resolve referenced-guide preservation and governance; the UI prototype does not authorize cascading historical erasure.


A guide is a shared **referenceable** source-of-truth, not an inline block
copied into another record. Guides use `CatalogItem` (UUIDv7, permanent
`gui-*` public ID) and immutable `CatalogRevision` snapshots, plus the
shared catalog audit emitter. No new mutable guide content store is introduced.

## Registered object schema and revision preservation

Migration `0010_setup_guide_schema` registers **setup_guide v1** through
`ObjectTypeVersion` without populating a single business guide. Its JSONB
properties support:
- `text` (procedure, ≤32,768 characters);
- `url` (absolute HTTP or HTTPS external guide, ≤2,048 characters);
- optional `description` (≤4,000 characters);
- other compatible, unknown JSON properties, retained across revisions.

At least one non-blank `text` or valid HTTP(S) `url` is required. URL-only,
text-only and combined guides are supported. Empty text/URL values in an edit
clear the optional property; old revisions keep their original value. URLs are
**metadata**; the API never downloads or follows them, and refuses embedded
credentials, malformed URLs, whitespace, scripts and non-HTTP schemes.

Edits require the exact current `expected_revision`; conflicting edits return
HTTP 409. A changed guide appends a new immutable revision, updates only the
current-revision pointer and appends an attributed audit event. A no-op edit
does not invent a new history entry. Original history, schema FK, unknown
properties and revision UUIDs remain available.

## API and authorization

| Method | Path | Contract |
| --- | --- | --- |
| GET | `/api/v1/guides[?q=title-or-id]` | Search existing shared guides; max 500 results, oversized lookups return 422 |
| POST | `/api/v1/guides` | Create permanent guide; `{name,properties:{text?,url?,description?}}` |
| GET | `/api/v1/guides/<gui-id>` | Latest guide including exact revision UUID |
| PATCH | `/api/v1/guides/<gui-id>` | Edit with `expected_revision`, append if changed |
| GET | `/api/v1/guides/<gui-id>/revisions` | Complete historical revisions |
| GET | `/api/v1/guides/<gui-id>/revisions/<number>` | Original pinned snapshot |

GET requires `business_read`; POST/PATCH require `business_write`, an
authenticated session and CSRF. Maintenance-only and user-admin-only accounts
do not receive business access. No delete, blind overwrites or external
URL fetching is offered.

## UI and campaign connection

In `/?mode=server`, **Knowledge & Collaboration / Guides & Charter** supports
listing, filtering, creating, editing and inspecting historical Setup Guides.
There is an embedded **Setup Guide selector**, which can find already
registered guides or create a new one and report its exact `gui-*` ID and
revision UUID to the consuming workflow.

`window.AICompassServerGuides.mountInline(root, csrfProvider, escapeHtml,
onSelected, {canWrite:true, heading:"..."})` is the reusable component for
campaign setup. The callback receives `{id, revision, revision_id, name}`.
**Actual persistent campaign linkage is added in #12**, when the Server
campaign object exists; no dummy campaign, automatic selection sync or
unversioned copy is created here. Running a benchmark will separately pin
the guide snapshot in #14/#15.

The standalone Demo continues its own fake browser localStorage state.
Guide creation in Server never reads, imports or propagates Demo fixtures.

## CI and operator acceptance

```bash
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_setup_guides -v 2
node --check server-guides.js
node scripts/test-server-guides.js
bash scripts/smoke-platform.sh
```

Manual repeatable walkthrough: start a clean Server and sign in as contributor.
Confirm **zero guides**. Create text-only, URL-only and combined guides. Edit
the URL and verify the original URL and unknown fields remain visible under
revisions; refresh and log in again to verify persistence. Filter the list,
select an existing guide from the inline selector, create another from the
selector, and verify both provide their stable ID and exact revision. As a
read-only user, confirm create/edit controls are unavailable and POST/PATCH
are denied; as a maintainer-only user, confirm direct GET is denied.
Open Demo with backend stopped and confirm its guide fixtures still work.

Migration only adds a technical schema definition. No existing business
records, historical schemas, evidence, production data or benchmark
measurements are transformed. No separate product release acceptance or
production migration (#26/#35) is claimed. Manual browser acceptance is not
equivalent to passing the automated CI suite.
