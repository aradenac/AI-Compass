# Users & Access — Server mode (PLAT-28)

Users & Access is a **Server-only** maintenance workspace. It is available
independently of Data Health (#27) and of any business-catalog grants.
Demo mode remains a separate seeded browser runtime; no Demo user is promoted,
imported, synchronized or used for authorization.

## Operators and guardrails

Install the baseline roles and create the first operator from the container
using a securely provided password on stdin (never as a command argument):

```bash
docker compose exec -T api python manage.py bootstrap_identity
printf '%s\n' "$ADMIN_TEMP_PASSWORD" | docker compose exec -T api \
  python manage.py bootstrap_identity --username accounts-admin \
  --role user-admin --password-stdin
```

Sign into `http://127.0.0.1:8080/?mode=server`. The **Users & Access**
section appears only when the authenticated account holds `auth.users_manage`.
The standalone workspace supports searching and filtering users, account creation
with an administrator-set initial password, role assignments, activation/
deactivation, password reset and reading recent audit events. Provision initial
credentials to the intended recipient via a separate secure channel. Passwords
are never returned or written to audit events. Email delivery, SSO and password
self-service are not included.

Every read/write of `/api/v1/admin/users` requires `users_manage` at
the Django API boundary, not only the frontend. Mutations additionally require
a valid CSRF token and active Django session. User admins cannot change their
own role/status/credential through this interface, modify Django staff/superusers,
or edit accounts with direct Django permission grants. Adding/removing the
`platform-admin` role or managing an existing platform operator additionally
requires `platform_manage`. To grant both capabilities explicitly to an operator,
create it with both roles at bootstrap time; neither role implies the other.

Only the six baseline roles may be assigned through this workspace. The final
active `user-admin` role-holder cannot be disabled/demoted. Changes serialize
under a PostgreSQL advisory transaction lock, with target-account row locking.
Existing sessions observe role changes on the next authenticated request;
deactivated accounts lose authentication. Reactivating an account does not
restore its prior session.

## API contract

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/admin/users?search=&status=all&page=1` | 50 users per page, plus total and available roles |
| POST | `/api/v1/admin/users` | Create: username, optional email, required password, roles |
| PATCH | `/api/v1/admin/users/{integer_id}` | Update: active, roles, optional new password |
| GET | `/api/v1/admin/users/audit` | Latest 100 immutable attribution events |

POST returns 201; successful PATCH returns `changed`. Invalid payloads,
permissions, CSRF, duplicates and concurrency-sensitive self-lockout are
rejected with appropriate status codes. No endpoint returns password hashes.
Access audit events use UUIDv7, preserve actor and subject using protected
foreign keys, and reject UPDATE/DELETE via a PostgreSQL trigger.

## Validation and rollback

```bash
docker compose exec -T api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_user_admin -v 2
node --check server-users.js && node scripts/test-server-users.js
bash scripts/smoke-platform.sh
```

Operator smoke: use a user-admin without contributor/maintainer grants; create
an ordinary user, grant `data-maintainer`, confirm access to the authorized
maintenance API and denial on the catalog, revoke and confirm denial on the
*next request*, then disable and confirm their active session no longer works.
Use a data-maintainer-only account to verify the Users & Access UI is hidden
and direct list/create/update/audit API calls are forbidden.

The migration only **adds** the access-audit table and append-only trigger;
it does not migrate catalog or evidence records. Reverting the migration would
discard access-audit history and is **not** a supported production rollback.
Preserve the DB and its coordinated backups instead.
