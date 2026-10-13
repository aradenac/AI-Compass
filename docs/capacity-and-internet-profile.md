# Capacity governance and Internet deployment profile — FUT-20

Two coordinated capabilities: a small **versioned, auditable capacity policy**
with a health/headroom view, and an explicit **Internet / inter-BU exposure
profile** that fails closed. Neither introduces a generic rule engine, Redis,
Celery or a microservice.

## Bounded capacity policy

Administered only by `platform_manage` (platform-admin). `platform_view` may read
the health/headroom view and the current policy; nothing here is visible to a
`maintenance_view` (Data Health) or ordinary account. Every change writes an
append-only `CapacityPolicyEvent` (who / when / old / new) and **supersedes** the
previous version — a policy change never rewrites pinned historical data and only
affects future operations.

| Setting | Meaning | Bounds |
| --- | --- | --- |
| `evidence_warn_bytes` | Warn when stored evidence exceeds this | 0 – 2^50 |
| `disk_warn_percent` | Warn when the evidence volume is this full | 1 – 99 |
| `archive_concurrency_warn` | Warn when queued/running archive jobs exceed this | 0 – 64 |
| `upload_quota_warn_bytes` | Soft upload-quota warning | 0 – 2^50 |

**Physical technical hard limits are never administrable.** The health view
reports them separately and marks them `administrable: false`: the 16 MiB
evidence-upload technical bound, the 200,000-record / 2 GiB uncompressed native
export guards. These can only be raised by a separately tested format/resource
change, never by editing a setting.

### API

```
GET   /api/v1/platform/capacity/health            platform_view   -> metrics{value,warn_at,state}
GET   /api/v1/platform/capacity/policy            platform_view
GET   /api/v1/platform/capacity/policy/history    platform_view
PATCH /api/v1/platform/capacity/policy/edit       platform_manage
```

Each metric carries `{value, warn_at, state}` with `state ∈ {ok, warning, hard,
unknown}`. A warning is informational — it never deletes or blocks existing
records by itself.

## Internet / inter-BU profile

Set `AI_COMPASS_PROFILE=internet`. The profile is validated at Django startup
(fail-closed) and additionally by the host-side preflight:

```bash
python3 scripts/check_deployment_profile.py --env .env
```

It **refuses** unsafe exposure:

- a missing TLS-terminating trusted proxy (`AI_COMPASS_TLS_PROXY=1` required);
- no public DNS host in `DJANGO_ALLOWED_HOSTS` (loopback, internal-only and
  private-IP hosts are rejected as the sole host);
- non-HTTPS or wrong-host CSRF trusted origins;
- weak `DJANGO_SECRET_KEY` / `DB_PASSWORD`;
- again, wildcard / CIDR hosts.

When accepted, it enables secure cookies, HTTPS redirect, `Referrer-Policy:
same-origin` and a **short** HSTS (`SECURE_HSTS_SECONDS=600`, no includeSubDomains
/ preload) so a mistaken subdomain stays recoverable. Public ingress must not
inherit the loopback-only HTTP defaults. Loopback development and the private LAN
profile are unchanged.

### Login throttling

A durable, DB-backed `AccessThrottle` (keyed by a one-way digest of
identifier+client IP; no plaintext) locks an identifier after 5 failed logins for
15 minutes; the login endpoint returns **429** while locked, even for a correct
password. It survives process/worker restarts and needs no broker. The client IP
is honoured only from a trusted proxy's `X-Forwarded-For`.

## Human operational acceptance checklist (not performed by automated tests)

Local tests prove the profile logic and throttle; they do **not** authorize a
production Internet GO. Before public ingress, an operator must sign off:

- [ ] Public DNS name resolves; certificate chains to a trusted CA and covers the
      host; renewal is automated and monitored.
- [ ] Reverse proxy sets `X-Forwarded-Proto`; HSTS length agreed; no mixed
      content; `check_deployment_profile.py --env .env` passes on the real host.
- [ ] Cookie/CSRF behaviour verified through the real proxy for both a valid and
      a cross-origin request.
- [ ] Login throttling verified against the real client-IP header path; lockout
      alerts wired to an operator.
- [ ] Permission matrix reviewed: which accounts hold `platform_manage`,
      `archive_export`, `purge_manage`; no role was auto-granted.
- [ ] Representative volumes: a real native archive built, transferred with the
      resumable client over HTTPS, and verified offline.
- [ ] Incident practice: revocation of a leaked archive grant, disabling an
      account, and reading the append-only capacity/archive audit.
- [ ] Capacity warnings observed against real evidence/disk growth; hard limits
      understood as non-administrable.

Heavy live ingress, soak and TLS-infrastructure validation remain explicit
rollout gates beyond this issue.

## Migration and rollback

- Migration `0031_capacity_policy_and_throttle` is additive (three tables + an
  append-only trigger). Rollback: `python manage.py migrate config 0030_archive_jobs_and_grants`.
- The `internet` profile is configuration only; reverting `AI_COMPASS_PROFILE`
  and the HSTS/redirect flags restores the previous posture. HSTS is sticky in a
  browser for its duration — keep it short while validating.

## Verification

```bash
docker compose -p <proj> exec -T api python manage.py test config.test_capacity
python3 -m unittest discover -s scripts -p 'test_deployment_profile.py' -v
```

Covers: RBAC (only `platform_manage` revises; `maintenance_view` sees nothing);
versioned audited changes and immutability of the event log; bounds enforcement;
health distinguishing configurable warnings from hard limits; a synthetic
archive-concurrency pressure warning; the Internet profile refusing cleartext,
loopback/private hosts, non-HTTPS origins and weak secrets while preserving
development and LAN; and the throttle locking after repeated failures (429 on
replay).
