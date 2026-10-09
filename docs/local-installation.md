# AI Compass — Local Installation and Deployment

> **Target:** Ubuntu 22.04 / 24.04 LTS · **Scope:** PLAT-01 local infrastructure · **Date:** 2026-10-09
>
> **Two permanent choices:** Demo and Server use the **same frontend**. The browser-only Demo must never be removed. See [Architecture](platform-architecture-and-data-governance.md) and [Roadmap](platform-implementation-roadmap.md).

## 1. Choose the operating mode

| Capability | Demo mode | Server mode |
| --- | --- | --- |
| UI | `prototype.html` | The **same** `prototype.html` |
| Data source | Seeded fake records in browser `localStorage` | Django Ninja API + PostgreSQL, added by domain incrementally |
| Current PLAT-01 business screens | Demo works | **Still use Demo data**; only a server health API exists so far |
| Browser authentication | Simulated test accounts | Real server identity is planned in PLAT-02 |
| Docker / SQL DB | Not required | Required |
| Data sharing | Not shared across origins/browsers | Shared, **when the relevant business APIs are implemented** |

**No implicit fallback or synchronization.** When Server business data becomes available, a shared frontend `DataProvider` contract will route the same UI to either a `LocalStorageDataProvider` or `ApiDataProvider`. Failure to reach the backend must show an error, not fictitious records.

## 2. Demo mode: installation without Docker

Install Git and Python's standard-library static server:

```bash
sudo apt update
sudo apt install -y git python3
git clone https://github.com/aradenac/AI-Compass.git
cd AI-Compass
python3 -m http.server 8090 --bind 127.0.0.1
```

Open **http://127.0.0.1:8090/prototype.html**. Login with the explicitly simulated accounts, create demo records and refresh: `localStorage` retains them on the same browser/origin. Use the built-in **Export data JSON** before resetting demo data. End the server with Ctrl+C. **No Docker, database, npm or backend package installation is required.**

## 3. Server infrastructure: install prerequisites on Ubuntu

If `docker --version` and `docker compose version` already work, reuse the installation. Otherwise follow the [official Docker Engine Ubuntu guide](https://docs.docker.com/engine/install/ubuntu/) and install the Compose plugin through Docker's apt repository:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git python3
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "$VERSION_CODENAME")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
```

Using the Docker socket usually requires `sudo`. Membership in the `docker` group grants root-equivalent privilege; **do not** grant it casually or make the socket world-writable. Commands in repository scripts use `docker compose`; configure legitimate access or adjust them for `sudo`.

## 4. Clone, create private credentials and launch

```bash
git clone https://github.com/aradenac/AI-Compass.git
cd AI-Compass
python3 scripts/init-env.py
docker compose up -d --build
docker compose run --rm api python manage.py migrate --noinput
docker compose ps
```

`scripts/init-env.py` generates strong random PostgreSQL and Django secrets in `.env` (mode 0600), refuses to overwrite existing credentials and never sends them anywhere. This file is ignored by Git. To change the local bind port, edit `AI_COMPASS_HTTP_PORT=8080` in `.env` before starting.

Open **http://127.0.0.1:8080/prototype.html**: the **same Demo frontend** is served by Caddy. For PLAT-01, catalog and campaign records in this UI are still fictitious and stored locally, **not** persisted in PostgreSQL.

Check real server/database connectivity:

```bash
curl --fail --show-error http://127.0.0.1:8080/api/v1/health
# {"status":"ok","database":"ok"}
```

The stack has three containers: `db` (PostgreSQL, persistent named volume `ai-compass_pgdata`, no host DB port), `api` (Django + Django Ninja + Gunicorn, private internal port) and `web` (Caddy static frontend and reverse proxy, bound to **127.0.0.1**). Django Python dependencies are installed **in the container** from `backend/requirements.txt`, not on the PC. Node.js and npm are not required for the current single-file frontend.

## 5. Create real Server identities and use the permission-gated workspace (PLAT-02)

Run this after the first `migrate`. The first command is idempotent and creates six **independent** Django groups and permissions; it does not grant every role to a platform operator.

```bash
docker compose exec -T api python manage.py bootstrap_identity
# Interactive account creation (do not place passwords in the command line):
docker compose exec api python manage.py bootstrap_identity --username operator --role platform-admin
docker compose exec api python manage.py bootstrap_identity --username maintainer --role data-maintainer
docker compose exec api python manage.py bootstrap_identity --username reviewer --role reviewer
docker compose exec api python manage.py bootstrap_identity --username contributor --role contributor
docker compose exec api python manage.py bootstrap_identity --username users-admin --role user-admin
```

Every `bootstrap_identity --username` command prompts for and validates a unique strong password, creates an **ordinary** user (not an implicit Django superuser) and **refuses to overwrite** an existing account. To add more than one role during initial creation, repeat `--role`, for example `--role data-maintainer --role user-admin`. To seed roles only, omit the username.

For controlled non-interactive provisioning, pipe a private secret into `--password-stdin`; never supply it as a command-line argument or log it. Provisioning or changing existing accounts remains an **operator CLI action** in this issue; a user-management web interface arrives in [PLAT-28](https://github.com/aradenac/AI-Compass/issues/28).

**Open the same frontend explicitly in Server mode:**

- **http://127.0.0.1:8080/prototype.html?mode=server** — real sign-in/out and role-gated landing.
- **http://127.0.0.1:8080/prototype.html?mode=demo** — fake, locally stored demo records and simulated identities.
- In Demo mode, the **Server sign-in** link switches explicitly to Server mode; the separate **Return to independent Demo mode** link switches back.

In Server mode, the original Demo initialization is **skipped**, so the browser does not read or modify the fake dataset. If Django is offline, Server mode shows an **unavailable** message; it never falls back to fake records.

After signing in, the Server page displays real account groups/capabilities and only the corresponding available functions. A Data Maintainer may access the Maintenance & Governance permission check, not protected business reads/writes or User Administration. A Contributor may read and update a **private session-only sandbox value**, not the future persistent catalog. A User Administrator may access the user-administration permission check, not maintenance. All permissions are rechecked by Django on direct HTTP access.

**CSRF/session contract:** first request `GET /api/v1/auth/csrf` to receive a same-origin CSRF cookie; include that cookie's token in `X-CSRFToken` on `POST /api/v1/auth/login`, `logout` and protected sandbox writes. Django creates an HttpOnly session cookie and rotates CSRF on login. The frontend handles these steps automatically. The endpoints are intentionally same-origin (not cross-origin public APIs).

**Security limitations:** local HTTP is bound to 127.0.0.1 only; do not expose the endpoint publicly until HTTPS, secure cookies and login rate limiting are configured. Current Server UI provides only identity and capability demonstrations; persistent Models, campaigns and evidence are **not** present yet.

## 6. Model Catalog API: first persistent business object (PLAT-03)

The database now contains a **versioned Model schema and immutable revisions**; see [Model Catalog Architecture](model-catalog-architecture.md) for the exact data model, HTTP endpoints and error conditions.

On an **existing installation**, take a logical backup first, then apply the new SQL/schema migration (never delete your database volume):

```bash
bash scripts/backup-db.sh
docker compose up -d --build
docker compose run --rm api python manage.py migrate --noinput
docker compose exec -T api python manage.py bootstrap_identity
```

Create a user authorized to **read and write Server Models**:

```bash
docker compose exec api python manage.py bootstrap_identity \
  --username model-editor --role contributor
```

The command prompts for a password; no fake demo login is accepted by this API. The Server interface at `?mode=server` provides real account login and access checks, but the graphical **Models screen is not yet API-connected** (planned in [PLAT-05](https://github.com/aradenac/AI-Compass/issues/5)).

For a minimal curl example, use cookies/CSRF and read the exact ID returned by the POST. Avoid putting the password on a persistent shell command line; the following reads it in a hidden terminal prompt:

```bash
BASE=http://127.0.0.1:8080
COOKIE_JAR=$(mktemp)
chmod 600 "$COOKIE_JAR"
curl -fsS -c "$COOKIE_JAR" "$BASE/api/v1/auth/csrf" >/dev/null
read -rsp 'Server account password: ' PW; echo
export PW
CSRF=$(awk '$6=="csrftoken"{print $7}' "$COOKIE_JAR")
python3 -c 'import json,os;print(json.dumps({"username":"model-editor","password":os.environ["PW"]}))' | \
  curl -fsS -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -H 'Content-Type: application/json' -H "X-CSRFToken: $CSRF" \
    --data-binary @- "$BASE/api/v1/auth/login"
unset PW
CSRF=$(awk '$6=="csrftoken"{print $7}' "$COOKIE_JAR")
curl -fsS -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -H 'Content-Type: application/json' -H "X-CSRFToken: $CSRF" \
  -d '{"name":"GLM-5.2","properties":{"context_window":262144,"supports_tools":true}}' \
  "$BASE/api/v1/models"
curl -fsS -b "$COOKIE_JAR" "$BASE/api/v1/models"
rm -f "$COOKIE_JAR"
```

**Shell detail:** the temporary password is exported only for the JSON-building subprocess, streamed through stdin rather than placed on the curl command line, and immediately cleared. Avoid shell tracing (`set -x`) or sharing the shell environment while using this example. A simpler alternative is to sign in through the Server-mode UI and use a same-origin authenticated browser client.

Each POST yields `mdl-word-word-word` plus revision `r001`. To append a revision, POST a JSON object with `expected_revision` and modified fields to `/api/v1/models/{id}/revisions`. Old revisions remain available at `/revisions/1`. The API enforces authenticated roles and CSRF, not the demo identities.

For the automated smoke and non-regression checks:

```bash
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config --verbosity 1
bash scripts/smoke-platform.sh
```

## 7. Verify persistence, backups and safe recovery

```bash
bash scripts/smoke-platform.sh
```

The script checks HTTP/HTML, the Django API/tests, writes a harmless SQL persistence marker, takes a custom-format `pg_dump`, and restores it into a **disposable database** (`ai_compass_restore_smoke`). It verifies the marker was recovered; it never drops the real DB.

Independent manual operations:

```bash
bash scripts/backup-db.sh
# Note the printed .local/backups/ai-compass-....dump path
bash scripts/restore-db-smoke.sh .local/backups/ACTUAL_FILENAME.dump
```

Use the actual filename output by the backup command. The backup is excluded from Git but is **on the same PC**, so it is **not** a disaster-recovery backup. Copy it to a physically independent, protected location. Automated off-host and coordinated document recovery is planned in [PLAT-29](https://github.com/aradenac/AI-Compass/issues/29).

Verify container recreation without wiping volumes:

```bash
docker compose down
docker compose up -d
docker compose exec -T db sh -ec \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atqc "SELECT marker FROM ai_compass_smoke_marker LIMIT 1"'
# persistence-check
```

**Never execute `docker compose down -v` when you want to preserve real data.** That command deletes the named database volume.

## 8. Stop, update, inspect

```bash
docker compose logs -f api
docker compose ps
docker compose stop
docker compose start
docker compose down             # Containers only; preserve DB volume
docker compose up -d --build
```

When updating:

```bash
git pull --ff-only
bash scripts/backup-db.sh
docker compose up -d --build
# Review migration requirements before applying on valuable data:
docker compose run --rm api python manage.py migrate --noinput
bash scripts/smoke-platform.sh
```

Do not blindly run irreversible migrations after every restart. For a production upgrade, first take a **restorable** backup and read the release/migration notes.

## 9. Troubleshooting

| Problem | Solution |
| --- | --- |
| Docker permission denied | Use `sudo docker compose` intentionally or configure authorized access; avoid `chmod 666`. |
| Docker Compose not found | Install the official `docker-compose-plugin`. |
| 8080 already in use | Change `AI_COMPASS_HTTP_PORT` in `.env` and recreate `web`. |
| HTTP 502/503 | `docker compose ps` and `docker compose logs api db`; verify DB health. |
| Django DisallowedHost | Check `DJANGO_ALLOWED_HOSTS` in `.env`; loopback names are configured by default. |
| Browser changes not shared | Expected **Demo mode**: different origins have independent `localStorage`. |
| Existing `.env` rejects initialization | Safety feature: do not overwrite established DB credentials; inspect/rotate deliberately. |
| Restore smoke test fails | Ensure migrations have run and the dump is nonempty; do not attempt to overwrite the real DB. |

## 10. Boundaries and security

PLAT-01 is a **local development** stack, not a public production deployment. HTTP listens on loopback; server login and role separation **are implemented**, but most domain APIs (except the versioned Model REST API), document upload, production HTTPS, the user-management web UI and independent backups are **not implemented yet**. Do **not** expose the current app to untrusted networks or upload confidential evidence. The Demo mode remains intentionally unauthenticated and uses fictional content.

The directory layout is `prototype.html` + `compose.yaml` + `Caddyfile` + `backend/` + `scripts/` + `.env.example`; generated secrets in `.env`, local backups under `.local/backups/`, and server PostgreSQL data in the Docker named volume. Browser Demo `localStorage` is separate and not automatically imported or synchronized.

**Official references:** [Docker Engine Ubuntu](https://docs.docker.com/engine/install/ubuntu/) · [Docker Compose](https://docs.docker.com/compose/install/linux/) · [Django 5.2](https://docs.djangoproject.com/en/5.2/) · [AI Compass architecture](platform-architecture-and-data-governance.md).
