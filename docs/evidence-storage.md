# Private immutable evidence store — PLAT-17

## Scope and architecture

The **Server** workspace now attaches immutable files to any registered
`CatalogItem` (Model, Provider, Harness, Framework) or a particular immutable
`CatalogRevision`. This is a single reusable **EvidenceBlob / EvidenceLink**
domain: the blob is deduplicated by SHA-256, but **every upload creates a new
attributed link** with its own UUIDv7, original basename, user, timestamp, source,
JSON provenance and optional pinned revision foreign key. Renaming an item and
appending subsequent revisions do not break the attachment. DB triggers forbid
changing or deleting historic blobs and links and independently reject
cross-item revision relationships. Future business object types can reuse the
same content-addressed storage/metadata API; they require an explicit FK-capable
target extension rather than a silently unvalidated generic text identifier.

The `evidence` Docker named volume is mounted **only** into the unprivileged
Django API at `/var/lib/ai-compass/evidence`; it is **never served directly by
Caddy**. Its permissions are private. No filesystem path appears in the API.
An uploaded file streams in 64-KiB chunks, is constrained to **16 MiB**, must
have a supported suffix and matching magic bytes (PDF, PNG, JPEG, WEBP, ZIP)
or valid UTF-8 (TXT, MD, CSV, JSON). JSON must parse. The private `.incoming`
file is fsynced, then atomically hard-linked to
`blobs/aa/bb/<64-lowercase-hex-sha256>`, checked for already-existing
content and published **before** the DB link transaction. Atomic link
creation never overwrites original bytes. A crash may leave a recoverable
orphaned disk blob; it cannot create a valid DB pointer to a partial upload.
Each download rehashes the original bytes and refuses missing/corrupt files
with HTTP 409; downloads are protected by Django session RBAC and use
`Content-Disposition: attachment`, `nosniff`, `private, no-store`.

## HTTP contract

Session authentication and CSRF use the existing `/api/v1/auth/*` endpoints;
`business_read` is required for list/metadata/download and
`business_write` + CSRF for multipart upload.

| Operation | Endpoint |
| --- | --- |
| List links, including verified integrity | `GET /api/v1/catalog/items/{public_id}/evidence` |
| Attach | `POST /api/v1/catalog/items/{public_id}/evidence/upload` |
| Inspect one immutable link | `GET /api/v1/evidence/{link_uuid}` |
| Download original bytes | `GET /api/v1/evidence/{link_uuid}/download` |

The multipart form contains `file` (required), `revision` (optional, exact
`r001`-style number belonging to the target item), `source` (optional up to
600 chars) and `provenance` (optional JSON object up to 8 KiB).
Missing revision explicitly links to the *item* rather than silently pinning
a revision. A fresh Server starts with no evidence or business records.
Unsupported/mismatched file types, missing targets, wrong-type revisions,
oversized files, missing CSRF or insufficient roles are rejected.

In Server mode, select **Evidence** on a catalog card. Contributors can
attach; readers see the list and can download but cannot mutate. If integrity
checks fail, the UI displays an explicit failure instead of offering a
fake/broken download. Standalone `?mode=demo` continues entirely from local
seeded examples and `localStorage`: it does not contact or import the
Server evidence store.

## Integrity, reconciliation and recovery

Execute:

```bash
docker compose exec -T api python manage.py reconcile_evidence --json
docker compose exec -T api python manage.py reconcile_evidence --json --prune-stale-incoming
```

The default command is **read-only** and reports missing/corrupt referenced
blobs, finalized orphan files left by interrupted transactions, DB blob rows
without contextual links, temporary interrupted uploads, and dangling or
wrong-target links (although normal FKs and triggers prevent them). It exits
nonzero for broken data. The optional switch removes **only** incoming
temporary files at least one hour old; finalized orphans are **never**
automatically deleted, to retain recovery evidence. Do not manually delete
the named volume or merge staging/production writable evidence mounts.

### Backup limitation — critical

PLAT-34 creates **database-only** recovery points. On backup, the existing
PostgreSQL manifest now inventories `evidence.blob_count`,
`evidence.link_count`, `evidence.blob_hashes` from its **restored snapshot**,
records `included=false`, and sets
`requires_coordinated_restore=true` if links exist. It explicitly warns
that the **file bytes are NOT in the archive**. Restoring only the DB can leave
broken evidence pointers; reconciliation must report these as broken.
The blob volume therefore requires separately secured independent media
and operator retention until coordinated DB + blob backup/restore is built
under **#29**. The DB-only checksum and restore are still valid for the DB,
not a guarantee of complete evidence recovery. Old pre-PLAT-17 recovery
points with no evidence tables remain restorable.

## Reproducible verification

```bash
docker compose up -d --wait --build
docker compose exec -T api python manage.py migrate --noinput
docker compose exec -T api python manage.py test config --verbosity 1
# CI contributor created by the existing identity bootstrap:
AI_COMPASS_TEST_PASSWORD=... python3 scripts/smoke_evidence.py ci-contributor
docker compose exec -T api python manage.py reconcile_evidence --json
```

CI exercises two independent Django sessions through Caddy, upload and exact
byte-for-byte download, distinct provenance links on the same content hash,
and a DB-only backup manifest reporting uncovered references. Focused
Django tests cover invalid/oversized formats, RBAC/CSRF, partial DB
transaction rollback, broken/missing bytes, read-only reconciliation,
target/revision DB constraints and append-only triggers. Existing catalog,
Demo, Docker volume and restore tests are retained.

**Deferred:** S3, external antivirus/secure file classification workflow,
multi-target non-catalog FK extension as new modules land, coordinated
off-host evidence backup/PITR (#29), and bulk evidence workflows.
