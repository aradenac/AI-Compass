# Future evolutions — Secure remote archives, capacity governance and Internet readiness

> **Status:** Pending FUT-19 [#93](https://github.com/aradenac/AI-Compass/issues/93) and FUT-20 [#94](https://github.com/aradenac/AI-Compass/issues/94), with release integration FUT-21 [#95](https://github.com/aradenac/AI-Compass/issues/95). Resume after [UX-R07 #126](https://github.com/aradenac/AI-Compass/issues/126); UX-R03 #116 is already merged/closed.
> **Delivered foundation:** [Development/LAN operational profile](../secure-operations-baseline.md), [archive permissions](../deployment-profiles-and-archive-permissions.md) and [release contracts](../shared-frontend-and-release-lifecycle.md).

## Internet / inter-BU deployment profile

A trusted domain and controlled public ingress/VPN must provide HTTPS, secure cookies, trusted hosts/origins, login throttling, reverse-proxy/CSP/security headers, least privilege, abuse limits, observability and explicit acceptance. Never permit the public Internet to inherit loopback-only HTTP defaults.

## 2. Retain two different archive purposes

| Artifact | Meaning and guarantee | Restore boundary |
| --- | --- | --- |
| **Native logical archive** | Portable business objects, immutable historical revisions, type definitions, provenance, referenced original evidence and manifest; excludes password hashes/sessions and some operator bootstrap state. | Portable logical import under explicit compatibility, currently implemented as isolated-staging-only. Not a substitute for disaster recovery. |
| **Coordinated complete recovery point** | Verified PostgreSQL backup plus original evidence bytes, hashes, manifest and restore drill, with consistent source boundary. | Actual platform disaster recovery; operational production restore remains separately controlled. |

**Decision:** both artifacts should be obtainable remotely from one secured HTTP transfer mechanism. Do **not** remove the native archive endpoint capability merely because an archive can grow to many GiB. The *current synchronous* GET implementation is insufficient at that scale; evolve its behavior safely. Never mistake downloading a logical native ZIP for a complete reconstruction of user passwords, platform identity and runtime state.

## 3. Secure remote archive and recovery transfer

Implement the simplest safe two-stage flow, using existing Django/Caddy and persistent filesystem storage:

1. An authenticated **authorized platform export operator** explicitly requests an export/recovery artifact. Separate inventory/status privileges, archive creation and **full confidential download** rights; generic platform read-only health permission is insufficient. Full archives may contain confidential engineering or workforce data. Maintain attributable action logs without recording secrets.
2. A server-side management process produces the **immutable** artifact and manifest independently of HTTP request lifetime; it verifies completeness, checksum, source boundary and storage capacity before publication. Persist job state/reason for failure. No arbitrary shell/SQL execution endpoint and no mandatory Redis/Celery/message bus.
3. After creation, an authorized operator receives a **short-lived, revocable, cryptographically random, artifact-scoped bearer token**. Store only a token digest on the server; include expiry, intended scope, issuer and revocation state. The token is revealed only through an authorized session/CSRF-protected operation, never placed in a URL/query string, browser analytics, logs, repository, GitHub artifact or permanent localStorage.
4. Serve the already-created immutable bytes over **HTTPS** with Authorization header, download-safe content type/Content-Disposition and cache disabled. Loopback development may use HTTP only locally. Enforce authorization at every Range request; permit byte-range/resumable transfers (206/Content-Range) without opening a user-controlled filesystem path, with appropriate throttling/limits and secure token expiry. Reuse the same scoped token across resumed requests until expiry; support renewal by an authorized operator, never require a globally reusable long-lived key.
5. Supply a small maintained Python HTTP client which works identically against loopback or remote HTTPS, supports resume and SHA-256/manifest verification, and fails closed on truncated, changed or corrupted bytes. An ordinary browser download may be provided as a convenience for small archives but is **not** the dependable multi-GiB transfer path.
6. Support private retention/cleanup policies only after verifying that protected recovery points and transfers are not silently lost. Never expose archive contents through publicly cached CDN/static paths or put archive bytes into the public repository.

**Operational UX:** the interface can show export jobs, progress, sizes, source date, integrity, download authorization and expiration. A platform-only user lacking archive authorization must not see confidential artifact content or acquire a download token. A Maintenance/Data Health account gains no extra archive rights by default. Treat backup encryption and secure off-host storage as independent responsibilities; TLS protects transport, not files after arrival.

## 4. Capacity management and safe configurability

Provide a **small versioned operations-policy store**, administered only by explicit platform operations permission; no generic rule engine. Settings apply to *future operations* and do not rewrite, delete or revalidate historical records into noncompliance.

| Parameter | Administrable? | Safety constraint |
| --- | --- | --- |
| Maximum incoming evidence size / per-user or tenant upload quota | Yes within tested technical limits | Enforce before/during streaming; do not accept incomplete blobs or metadata. |
| Warning thresholds for DB, disk, evidence growth and available headroom | Yes | Warnings and trends are distinct from hard physical capacity. |
| Export job concurrency, retention, space reservation and soft limits | Yes within safe envelope | Never disable archive integrity, pending-transfer protection or last verified recovery protection. |
| Native export record/byte/entry ceilings | Raise through a separately tested versioned exporter/format and resource policy | Current 200,000-record / 2-GiB / 10,000-member restrictions are **format/export guards, not global DB capacity**; do not simply raise a constant past verifier support. |
| Physical free disk, DB integrity, HTTP upload parser and archive decompression guards | **No arbitrary override** | Detect and explain real resource limits; require infrastructure capacity expansion or reviewed hard-limit change. |

The dashboard should provide counts, historical trend/forecast with clear uncertainty, storage free/used, export queue and failures, latest verified backup/restore, integrity scan freshness, configurable warning levels and practical suggested actions. Trigger notices **before** reaching a hard limit; on refusal return precise machine-readable reason and safe administrator remedy. If user operations are temporarily blocked by a configurable quota, an authorized administrator must have a supported path to raise it where physically possible. All policy changes require who/when/old/new audit and validated bounds.

Do not confuse this operational overview with the [Data Governance Audit Explorer](../data-governance-audit-explorer.md), which owns historical business-change inspection, or with [Publication & Information Lifecycle](../publication-and-information-lifecycle.md), which owns logical deletion/retention of domain evidence. Technical backup retention cannot erase required historical evidence.

## 5. Security and quality acceptance

- Verify permission separation: read-only platform users cannot generate/download a full archive; maintainer-only and unauthorized users cannot create token or stream any byte; revocation/expiration and account deactivation take effect. No credential appears in logs/URLs.
- Verify resume after interrupted multi-chunk download, range validation (including out-of-range and wrong archive), hash mismatch rejection and bounded bandwidth/space use without loading a multi-GiB archive into API memory.
- Verify consistent complete recovery point transfer on a clean isolated machine and prove native import's staged scope is not misrepresented as production restoration.
- Verify profile-specific cookie/CSRF/TLS behavior, login abuse controls and no inadvertent network exposure. Internet-specific full validation can be deferred until infrastructure exists; deployment defaults must already prevent unsafe exposure.
- Verify dynamic policy edits affect only new requests; stored evidence remains intact. Show warnings as capacity approaches configured thresholds and distinguish hard physical vs configurable blockers.
- Keep infrastructure minimal: Django/PostgreSQL, existing filesystem evidence/backups, Caddy and a managed host job for archive generation are preferred over new services until actual load justifies them.


## Issue boundaries and implementation order

- [#93](https://github.com/aradenac/AI-Compass/issues/93) owns immutable archive jobs and resumable confidential transfer.
- [#94](https://github.com/aradenac/AI-Compass/issues/94) owns operator-configurable bounded capacity and hardened Internet profile, after #93.
- [#95](https://github.com/aradenac/AI-Compass/issues/95) owns guided compatible/incompatible release and recovery operations, after #93.

These are the **remaining** technical evolutions, not the already delivered development/LAN protection or existing coordinated manifest. All original data integrity and operational GO/NO-GO gates remain binding.
