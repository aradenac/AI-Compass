# PLAT-09 — Shared engineering task taxonomy

## Runtime separation

**Demo** remains the original seeded localStorage task organizer in
`prototype.html`, without Django or Docker. **Server** (`?mode=server`) has
a separate authenticated **Task management** section with an initially empty
PostgreSQL tree. It never imports Demo tasks, Test Cases or research data.

- A contributor (`business_write`) can create root and child tasks, edit the
  name/engineering metadata, reparent and reorder with Up/Down; a reader
  (`business_read`) can view the shared tree and immutable history.
- `tsk-<adjective>-<colour>-<noun>` is a permanent public ID backed by UUIDv7.
  Renames/reparenting do not change identity; descendant references remain stable.
  `TaskNode.parent` is a relational self-FK, with sibling `position`.
- Each content or placement change creates immutable `CatalogRevision` and
  `TaskStructureRevision` snapshots and a `CatalogAuditEvent`. Changed
  siblings each receive a revision. Original unknown JSON fields survive.
- PostgreSQL advisory transaction lock serializes tree writes across workers.
  Cycles, invalid anchors, stale revisions and malformed fields are refused.
  No delete endpoints.

## Authenticated API

| HTTP | Endpoint | Action |
|---|---|---|
| GET | `/api/v1/tasks` | Ordered tree (flat rows, parent IDs) |
| POST | `/api/v1/tasks` | Create: `name`, `properties`, `parent_id`, `before` |
| GET | `/api/v1/tasks/{tsk-id}` | Current node |
| PATCH | `/api/v1/tasks/{tsk-id}` | Optimistic edit using `expected_revision` |
| GET | `/api/v1/tasks/{tsk-id}/revisions` | Original content and placement snapshots |
| GET | `/api/v1/tasks/{tsk-id}/revisions/{n}` | Historical version |

`parent_id: null` denotes root. A `before` ID must be a distinct sibling
of the target parent. Omitting `parent_id` and `before` from PATCH preserves
placement; providing both with `before: null` appends to the destination.
The server returns 409 for a stale revision and 400 for invalid structure,
without partial writes. Patch `properties` merges unknown fields.

## Reproducible validation

```sh
python3 scripts/init-env.py
docker compose up -d --build --wait
docker compose run --rm api python manage.py migrate --noinput
docker compose exec -T api python manage.py bootstrap_identity
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_tasks -v 2
node --check server-tasks.js
node scripts/test-server-tasks.js
node scripts/test-model-catalog.js
```

**Manual:** sign in as contributor in Server; verify empty tree. Create a root
and two children, edit/move/reorder a child; sign in as a separate reader
in another browser and refresh. IDs, order and history must match in both.
Log out and run `?mode=demo` with Django stopped; original seeded tasks
must remain available, without Server records. Check that forbidden direct
writes, stale revisions, cycles and missing parents are refused.

## Migration / rollback

Migration `0005_task_taxonomy` only creates empty tables and schema v1.
It does not transform existing business records. Backups include new PostgreSQL
tables. Never reverse it destructively on a populated production database.
Make a verified #29 coordinated recovery point before future nontrivial
production schema transformations and follow #35/#26 acceptance. Test Cases,
score inheritance and task aggregation are out of scope.
