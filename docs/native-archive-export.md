# PLAT-30 — Native portable history and evidence archive (v1)

The export is an **authorized logical data archive**, not a substitute for the
coordinated operational DB + evidence recovery point (#29/#34). Native import
is reserved for #31. This endpoint does not mutate any business object.

## Export and independent verification

1. Start the Server stack, authenticate in a browser as a **platform-admin**
   user (permission: auth.platform_view). The endpoint is
   GET /api/v1/archives/native and requires that Django session. Never use a
   public/browser cache to distribute archives.
2. Download to private storage through an authenticated same-origin browser
   (navigation or an authenticated GET), saving the ZIP; it is intentionally
   not offered in standalone Demo.
3. On an **offline host without Docker or Django**, use:

       python3 scripts/verify_export.py ai-compass-native-v1.zip

   The verifier exits 0 and emits a JSON report with the archive SHA-256,
   model counts and original evidence count only after validating every
   manifest digest, every NDJSON record count, unique primary keys, exported
   foreign keys and each content-addressed SHA-256 blob. Exit 1 means invalid.
   Never use a failed or partially transferred archive for #31 import.

## Format, source-of-truth and privacy

ZIP (native format ai-compass-native v1):

- manifest.json is written **last**, declares completion, snapshot boundary,
  file sizes and SHA-256, total record and blob counts, and version.
- schema.json lists every current Django config model, exact named NDJSON
  member, per-model count, and FK target/field metadata.
- records/config.<model>.ndjson preserves every ORM row, primary key,
  typed FK, scalar field and JSONB property including unknown extensions,
  with historical catalog identities, original revisions, audit, evaluations,
  forecasts, Runs, migration receipts and other first-party data.
- subjects.json contains referenced auth user ID, username, active flag and
  group name only. **Passwords and hashes, email, sessions, CSRF credentials,
  user permission secrets and Demo/browser localStorage are not exported.**
  The #31 importer must explicitly map or provision accounts and permissions.
- evidence/blobs/<sha256> contains original unmodified binary evidence.
  Export aborts when any indexed original is missing, symlinked, mismatched
  in size or different from its content hash. Unreferenced filesystem orphans
  are excluded and do not become fabricated evidence.

The export is captured under a PostgreSQL **read-only REPEATABLE READ**
transaction. Evidence files are immutable content-addressed data. The ZIP
is fully assembled and verified for file integrity **before any response**;
no partial ZIP is returned on failure. Never edit native history while
archiving. This is a **logical** snapshot, not a WAL/recovery backup, and
archive consumers must treat JSON and filenames as untrusted.

Access is restricted at API level to authenticated platform administrators;
ordinary engineers, users and Data Maintainers without that role get 403.
The archive contains potentially sensitive engineering data and is therefore
confidential **even if the source code repository is public**. Store offline
in encrypted/access-controlled storage and transport only via trusted HTTPS,
or from an explicitly local loopback deployment. No built-in public share
link, arbitrary path parameter or server-side retention is created.

Limits: 200,000 config records and 2 GiB of uncompressed content per export,
plus 10,000 ZIP members at verifier. Oversized/corrupt exports are refused,
not truncated. For larger installations build a separately reviewed
streaming/snapshot extension rather than loosening integrity checks.

## Operator acceptance

    docker compose up -d --wait --build
    docker compose exec -T api python manage.py migrate --noinput
    docker compose exec -T api python manage.py makemigrations --check --dry-run
    docker compose exec -T api python manage.py test config.test_native_archive -v 2
    python3 -m unittest discover -s scripts -p 'test_verify_export.py' -v

In Server mode create Model -> edit -> attach original PDF; download,
verify offline, inspect manifest and confirm exact IDs, two revisions,
relations, original SHA-256 and byte-for-byte evidence. Repeat with corrupted
file storage: endpoint must return 409 and no downloadable partial archive.
Test anonymous and contributor access: 401/403. Open ?mode=demo without Docker
and confirm fake localStorage mode continues independently with no Server export.

**Not performed here:** external data onboarding, account credential migration,
native re-import into a new instance (#31), automatic production restore,
arbitrary custom export filters or modifying existing catalog metadata.
