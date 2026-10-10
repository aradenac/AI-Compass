# FUT-02 — Deployment profiles, archive privileges and evidence verification

> Implementation scope: [#76](https://github.com/aradenac/AI-Compass/issues/76).
> **Production deployment is still NO-GO** without manual staging, restore, operator approval and LAN certificate/browser verification. Internet exposure is explicitly NOT authorized (FUT-20).

## Development / local HTTP

Use `python3 scripts/init-env.py` once for unique local credentials, then:

```bash
python3 scripts/check_deployment_profile.py --env .env
docker compose up -d --build
```

The original Compose service stays bound to `127.0.0.1:8080`. The default profile is `AI_COMPASS_PROFILE=development`; Django refuses LAN/public hosts, remote trusted CSRF origins or proxy TLS trust. Standalone fictional Demo remains independent of any server or credentials.

## First secured LAN configuration

LAN is an **opt-in separate Compose overlay**, never a change to the default development listener. Provide a private static IPv4 assigned to the host, an internal-CA-signed certificate trusted by each user's browser with that IP present in SAN, and a matching protected key. No public domain is needed. Do not use an untrusted self-signed cert for real accounts.

Set in the private `.env` (example values, never check in real secrets):

```dotenv
AI_COMPASS_PROFILE=lan
AI_COMPASS_LAN_BIND=192.168.1.20
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,api,192.168.1.20
DJANGO_CSRF_TRUSTED_ORIGINS=https://192.168.1.20
AI_COMPASS_TLS_PROXY=1
AI_COMPASS_LAN_CERT=./secrets/lan.crt
AI_COMPASS_LAN_KEY=./secrets/lan.key
```

Protect the local private key with mode 0600 and its directory with mode 0700, do not commit it. The preflight verifies explicit private bind, internal hosts, strictly HTTPS allowed origins, proxy mode, readable real certificate and matching key, and forbids permissive filesystem permissions. The application independently validates the safe mode during Django startup and switches session/CSRF cookies to Secure, with a trusted HTTPS proxy protocol header. Caddy terminates HTTPS on **only the configured private address:443**, proxies API traffic over the isolated Compose network and serves static frontend. The development HTTP port stays loopback-only.

```bash
python3 scripts/check_deployment_profile.py --env .env
docker compose -f compose.yaml -f compose.lan.yaml config --quiet
docker compose -f compose.yaml -f compose.lan.yaml up -d --build
```

Do not start the LAN overlay if the preflight fails; do not forward ports to the Internet. Control firewall/VPN access, credential provisioning/rotation and private backups; do not assume the certificate is trusted until real browser verification. Startup validation also rejects accidentally placing LAN settings in development. Public ingress, brute-force protection, scale and operational acceptance remain FUT-20.

## Native archive security

`GET /api/v1/archives` exposes only the available export operation, its required permission and whether the current authenticated account has it; `platform_view` grants inventory only. Building/downloading the complete native archive at the legacy `GET /api/v1/archives/native` now requires **`archive_export`**. The explicit `archive-operator` role has it, alongside `platform_view`; `platform-admin` also retains export access to preserve existing operator workflows. A `platform_manage` user, read-only `platform_view` user, `data-maintainer` user, disabled user or unauthenticated client cannot obtain any complete archive bytes. This is not a new archive transfer protocol: FUT-19 provides asynchronous export and scoped tokens.

Successful export builds and integrity refusals emit a structured **actor ID and action only** to the server security log, without filenames, credentials or archive bytes. Keep these logs under restricted retention. Archive integrity failures continue to return HTTP 409 without streaming a partial ZIP. Logical native export remains distinct from PostgreSQL+evidence disaster recovery and has its original size/record safeguards.

## Evidence listing and verification

Evidence `GET .../evidence` lists immutable attribution and expected SHA-256 **without opening or hashing every blob**. Each row returns `integrity: not_checked`, `verification: {status: not_checked, last_verified_at: null}` because no durable per-blob verification timestamp has been recorded; it does not claim success or a fabricated scan date. The shared Server UI explicitly says "not checked in listing" while allowing a download.

Single-evidence detail requests (`.../evidence/<id>`), every authenticated original-byte download, native export, full recovery and `reconcile_evidence`/Data Health scans **still rehash** and fail closed on missing, tampered or unsafe bytes. Download returns HTTP 409 for corruption, never a success. Operators can run `docker compose exec -T api python manage.py reconcile_evidence --json` and use the Maintenance health scan for periodic independent detection. Existing immutable metadata, deduplication, per-revision permission filters and historical references remain unchanged.

## Verification and rollback

```bash
python3 -m unittest discover -s scripts -p 'test_deployment_profile.py' -v
docker compose exec -T api python manage.py test config.test_archive_permissions config.test_evidence_fast_listing config.test_native_archive config.test_evidence -v 2
```

GitHub's existing full Server/Demo CI additionally exercises migrations, original evidence preservation, integrity failure paths, native and coordinated backup/restore. This change contains **no database schema migration**. Rollback to the original loopback-only profile: stop LAN overlay, remove LAN-only `AI_COMPASS_*`/CSRF-origin settings, rerun preflight and start the base Compose file; restore archive privileges only via the controlled account-management process. Never downgrade security while the LAN listener remains exposed.
