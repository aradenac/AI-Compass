# PLAT-18 — Research Sources + Technology Watch (persistent Server)

## Architecture and security

This increment gives Technology Watch two independent, **versioned** Server entities, both backed by the existing `CatalogItem`, `CatalogRevision`, `ObjectTypeVersion` and audit ledger:

- **Research Source**: permanent `src-*` and UUIDv7, title, claim, citation, optional HTTP(S) URL, source type, confidence, limitations, publication and retrieval dates (explicit null = unknown), attributed revisions and arbitrary preserved additional JSON.
- **Watch Entry**: permanent `wat-*` and UUIDv7, hypothesis, assumptions, notes, internal/published visibility, draft → under review → reviewed lifecycle and optional version-pinned supporting sources.
- **WatchSourcePin**: append-only many-to-many FK from an exact Watch **CatalogRevision** to an exact canonical Research Source **CatalogRevision**. Unlinking from one entry is a new entry revision, not deletion of source, the old link, or its associated original evidence. Revising the source never updates previously pinned citations.

Only registered, validated schema versions can be edited. The additive migration `0016_research_sources_watch` registers two empty schema types and their immutable relational link table, with PostgreSQL FK/type/revision checks and no Demo seed or data backfill.

**Access:** a signed-in user with `auth.business_read` can list/read *published* Source and Watch snapshots only. A Watch Entry is not readable if any of its linked source revisions (or that source's current revision) is private. A reader cannot fetch internal historical versions by ID. Contributors with `auth.business_write` can create/edit private research; reviewers with `auth.publication_review` can publish/unpublish sources and move Watch Entries through review. Each transition is an immutable audited revision with optimistic concurrency; direct PATCH cannot silently bypass approval. No role hierarchy is implied.

Evidence uses the **existing `EvidenceBlob/EvidenceLink` #17 store** and exact Source/Watch catalog revision. PDF, text, JSON and other allowlisted originals are uploaded through the existing protected endpoint and verified on read using their original SHA-256. For Source/Watch evidence, uploads MUST pin a revision. Direct evidence metadata, list and download endpoints enforce the same public/private policy; files linked to an earlier internal revision do not become visible merely because a subsequent source revision was published. Uploaded bytes are never silently transformed or overwritten. The shared raw catalog-inspection endpoint enforces those same restrictions; generic Model/Provider/Harness behavior is unchanged.

The shared prototype has distinct permanent modes:
- `?mode=demo` stays a browser-local, seeded-fake Demo and works without Server, Django or Docker.
- `?mode=server` loads only the empty-at-first authenticated PostgreSQL-backed Sources and Watch Entries. The same static frontend is mounted in operational Docker and isolated staging; there is no import, sync or fallback between these data universes.

## API

| Verb | Path | Result |
| --- | --- | --- |
| GET/POST | `/api/v1/sources` | Filter `q`; create canonical source (workgroup contributor) |
| GET/PATCH | `/api/v1/sources/<src-id>` | Latest public/privileged revision; append revision with `expected_revision` |
| GET | `/api/v1/sources/<src-id>/revisions` | Original history, readers get only visible snapshots |
| GET | `/api/v1/sources/<src-id>/revisions/<number>` | Exact historical source revision |
| POST | `/api/v1/sources/<src-id>/actions/publish|unpublish` | Reviewer-only audited transition |
| GET/POST | `/api/v1/watch-entries` | Filter `q`; create entry with pinned source links |
| GET/PATCH | `/api/v1/watch-entries/<wat-id>` | Latest/updated hypothesis and pinned links |
| GET | `/api/v1/watch-entries/<wat-id>/revisions[/<number>]` | Immutable source/Watch history |
| POST | `/api/v1/watch-entries/<wat-id>/actions/submit|approve|publish|unpublish` | Explicit reviewer-only lifecycle |
| POST | `/api/v1/catalog/items/<src|wat-id>/evidence/upload` | Original file and explicit `revision=r001` |
| GET | `/api/v1/evidence/<link-UUID>[/download]` | Auth/visibility-protected, content-verified original |

Create one source:

```json
{"name":"Provider model release report","properties":{
  "claim":"Observed change in published benchmark",
  "citation":"Technical report, October 2026",
  "url":"https://example.org/report",
  "source_type":"benchmark","confidence":"medium",
  "limitations":"Third-party result, not internal reproduction",
  "published_on":null,"retrieved_on":"2026-10-10",
  "extensions":{"unknown":null}
}}
```

Create one Watch Entry referring to an **exact** source revision:

```json
{"name":"SPI driver coding performance",
 "properties":{"hypothesis":"New model may improve Zephyr driver debugging",
  "assumptions":"Comparable CI and tools","notes":"Not an observed in-house Run"},
 "sources":[{"id":"src-actual-permanent-id","revision":"r001"}]}
```

To revise without losing unknown JSON properties, PATCH with `expected_revision` and only changed properties. If `sources` is omitted, original pins are preserved; if an array is supplied, it completely defines the next revision's linked sources (so unlinking is explicit). Historical links remain queryable via the older Watch revision. A watch publication is rejected until all linked exact source revisions and their current sources have been published. Even after Source publication, a link pinned to the *earlier internal revision* must be explicitly revised before the Watch Entry can be published — never silently re-pin.

## Reproducible verification / manual walkthrough

```bash
docker compose up -d --wait --build
docker compose exec -T api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_watch -v 2
node scripts/test-server-watch.js
```

1. Sign in to Server as a contributor. Confirm both lists empty on a new real Server (Demo records are not present). Create **one** canonical source and **two** separate Watch Entries referencing source `r001`; close/reopen browser, verify records and revision FK identities persist.
2. Upload a real PDF/text file to the source through the original evidence uploader with `revision=r001`, filename, provenance and SHA-256. Verify original bytes and file hash through the protected Server evidence URL; do not copy them to any Watch-specific path.
3. Revise the Source claim to `r002`. Both Watch Entries still pin the original `r001`. Unlink the source from one Watch Entry by saving its new revision; the other Watch link, canonical Source and every original evidence link remain available. Read original `r001` revision after source edit.
4. As an ordinary reader, verify both private Source and Watch are absent/404, including guessed generic catalog ID, historical revision, evidence list/detail and direct file-download URLs.
5. As a reviewer, publish the source; explicitly link the Watch Entries to its **published** revision, then `submit → approve → publish` each. Log back in as reader: now see only correctly published material. Check that an attachment tied to `r001` when internal remains private; attach to published `r002` for authorized public access.
6. Try invalid URLs, duplicate or nonexistent sources, stale `expected_revision`, an unauthorized role, a missing CSRF token, wrong evidence hash and source hiding after publication. Verify no partial database revision/link and no sensitive content leaks.
7. Open the same prototype as `?mode=demo` with the Django stack stopped; its original seeded Technology Watch workflow must remain fully functional. Reopening Server should not copy Demo data. The CI suite also verifies isolated staging, backup/restore and server mounts.

The new schemas only add tables/registry rows; the existing #29 backup includes all DB relationships and original evidence. #35 staging and #26 governed production conversion gates remain distinct; no migration candidate is accepted or production transformed merely because this feature was merged.
