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

## 5. Verify persistence, backups and safe recovery

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

## 6. Stop, update, inspect

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

## 7. Troubleshooting

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

## 8. Boundaries and security

PLAT-01 is a **local development** stack, not a public production deployment. HTTP listens on loopback; server login, domain API persistence, document upload, production HTTPS, user-management permissions and independent backups are **not implemented yet**. Do **not** expose the current app to untrusted networks or upload confidential evidence. The Demo mode remains intentionally unauthenticated and uses fictional content.

The directory layout is `prototype.html` + `compose.yaml` + `Caddyfile` + `backend/` + `scripts/` + `.env.example`; generated secrets in `.env`, local backups under `.local/backups/`, and server PostgreSQL data in the Docker named volume. Browser Demo `localStorage` is separate and not automatically imported or synchronized.

**Official references:** [Docker Engine Ubuntu](https://docs.docker.com/engine/install/ubuntu/) · [Docker Compose](https://docs.docker.com/compose/install/linux/) · [Django 5.2](https://docs.djangoproject.com/en/5.2/) · [AI Compass architecture](platform-architecture-and-data-governance.md).
