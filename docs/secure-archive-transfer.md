# Secure asynchronous archive transfer — FUT-19

A **durable, server-managed job** produces one immutable, independently verified
artifact; an operator then transfers it over HTTPS with a short-lived,
artifact-scoped bearer token that supports resumed (Range) downloads. This
supersedes the *synchronous* `GET /api/v1/archives/native` path for large or
remote archives: the synchronous endpoint remains for small loopback exports and
its bytes are identical, but the job flow never serializes a confidential archive
in API memory.

## Two artifact meanings (unchanged)

| Kind | Meaning | HTTP job |
| --- | --- | --- |
| `native` | Portable logical business archive (see [native-archive-export](native-archive-export.md)). Restore is isolated-staging-only, not disaster recovery. | Built by the job; downloadable. |
| `full_recovery` | Coordinated PostgreSQL + evidence disaster-recovery point built by the operator CLI ([full-recovery](full-recovery.md)) under a proven consistency boundary. | **Refused** as an HTTP job (`full_recovery_requires_operational_gate`); never faked. |

## Authorization

All job/grant/download paths require `archive_export` (platform-admin or
archive-operator). A generic `platform_view` read-only observer, an unrelated
`data-maintainer`, or an ordinary user gets 403 and cannot create a job, mint a
grant, or stream a single byte. Creation, status/list and download are distinct
operations even though one grant covers them here.

## Flow

```bash
BASE=https://compass.example
# 1. Request a durable job (CSRF + session required)
POST   /api/v1/archives/jobs              {"kind":"native"}          -> 201 {job}
# 2. Run the build (child process; the response reports the terminal state)
POST   /api/v1/archives/jobs/{job}/run                               -> 201 complete | 502 failed
# 3. List / inspect
GET    /api/v1/archives/jobs                                         -> {results}
GET    /api/v1/archives/jobs/{job}                                   -> {job}
# 4. Mint a short-lived, artifact-scoped bearer token (revealed once)
POST   /api/v1/archives/jobs/{job}/grant  {"ttl_seconds":3600}       -> 201 {grant, token}
GET    /api/v1/archives/jobs/{job}/grants                            -> {results}  (no token)
POST   /api/v1/archives/jobs/{job}/grants/{grant}/revoke             -> 200 {grant}
# 5. Stream the bytes (Authorization header, never a query parameter)
GET    /api/v1/archives/download/{job}    Authorization: Bearer <token>
```

The token is a cryptographically random `secrets.token_urlsafe(48)`; only its
SHA-256 digest is stored. It is **never** placed in a URL, log line, audit entry
or repository, and is revealed exactly once in the `grant` response.

## Resumable download

`Content-Length`, `Accept-Ranges: bytes`, `Content-Range` on 206, an `ETag`
equal to the artifact SHA-256 and `Cache-Control: private, no-store` are set on
every response. Authorization is enforced on **every** request including a
resume, so a Range can never return bytes the token is not entitled to. Only a
single well-formed byte range is accepted; a malformed, multi-range or
out-of-bounds range yields **416** with `Content-Range: bytes */<size>`.
Truncated, changed or corrupt bytes fail closed at the client.

Use the maintained client (token from the environment, never an argument):

```bash
export AI_COMPASS_ARCHIVE_TOKEN=...        # from the grant response
python3 scripts/archive_download.py \
    --base-url "$BASE" --job "$JOB" --output ./native.zip
# Interrupt it (Ctrl-C), truncate the partial file, re-run: it resumes via Range
# and verifies the SHA-256 against the ETag; a mismatch exits non-zero.
```

## Immutability and failure handling

- The build command writes a staging file inside the private archive store,
  verifies it with the shared native verifier, then **hard-links** it to its
  final content-addressed name (atomic, never overwrites). A crash leaves a
  `failed` job with a machine-readable reason and **no published artifact**.
- Failures surface a fixed reason (`verification_failed`, `storage_unavailable`,
  `invalid_kind`, …); an errno/path is never written into job state or logs.
- The private archive store is a Docker named volume mounted only into the
  unprivileged API; it is never served by Caddy nor placed in the repository.

## Audit

`ArchiveAccessEvent` is append-only (DB-trigger protected) and records
`requested`, `grant_issued`, `grant_revoked`, `built`, `downloaded`, `denied`
with actor and artifact. Its detail never carries a raw token or confidential
bytes. `security_audit` log lines carry actor id, job and grant public ids only.

## Limits and boundaries

- Native format guards are unchanged: 200,000 records, 2 GiB uncompressed and
  10,000 ZIP members; oversized/corrupt exports are refused, not truncated.
- `full_recovery` transfer over HTTP is out of scope and refused; it stays with
  the operator CLI and its separately controlled GO/NO-GO gate. No path here
  performs a live restore or promotion.
- Backup encryption and off-host retention remain independent responsibilities;
  TLS protects transport, not files after arrival.

## Migration and rollback

- **Migration:** `0030_archive_jobs_and_grants` — additive (`ArchiveJob`,
  `ArchiveGrant`, `ArchiveAccessEvent` plus an append-only trigger). No existing
  data is altered.
- **Rollback:** `python manage.py migrate config 0029_retirement_and_purge`.
  Tables are dropped; previously generated artifacts in the archive volume
  remain on disk and can be removed manually by an operator.

## Verification

```bash
docker compose -p <proj> exec -T api python manage.py test config.test_archive_jobs
```

Covers: RBAC refusal for observers/maintainers/ordinary users; job creation and
unknown-kind rejection; grant token revealed once and never stored raw or
re-listed; audit entries free of the raw token; expired, revoked and
wrong-archive grants refused; full round-trip digest; interrupted download
resuming via Range and reassembling exact bytes; 416 for an unsatisfiable range;
download denied without/with a wrong token; an artifact outside the private
store refused; malformed/multi-range refused; and the `full_recovery` build
refused rather than faked.
