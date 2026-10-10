# PLAT-31 — Verified native archive restore (staging only)

The PLAT-31 importer verifies native v1 archives, offers a strictly read-only
preview and restores into a **new empty isolated staging Server**. Original
archive remains untouched. The importer is never a production restore, never
loads Demo localStorage fixtures or external business data, and never imports
authentication passwords, email addresses, roles or sessions.

## Independent validation

    python3 scripts/verify_export.py ai-compass-native-v1.zip

The offline verifier checks format, completeness, SHA-256 for every member,
all declared original evidence files, unique PKs, valid foreign keys and
record counts. Invalid data blocks preview and apply.

## Provision a disposable Server

Use the existing staging/compose.yaml, as described in
docs/migration-staging.md, with a new isolated Compose project, different
PostgreSQL and evidence volumes, fresh random secrets and an explicitly
STAGING-labelled frontend copy. Example:

    export STAGING_CANDIDATE="$(python3 -c 'import secrets;print(secrets.token_hex(8))')"
    export STAGING_DB_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
    export STAGING_DJANGO_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
    export STAGING_PORT=18081
    export STAGING_PAGE="/absolute/path/to/labeled/staging-prototype.html"
    export RESTORE_PROJECT="ai-compass-native-$STAGING_CANDIDATE"
    docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" up -d --wait --build
    docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" exec -T api python manage.py migrate --noinput
    docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" exec -T api python manage.py bootstrap_identity
    docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" exec api python manage.py bootstrap_identity --username native-import-operator --role data-maintainer
    docker cp ai-compass-native-v1.zip "$(docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" ps -q api):/tmp/native-source.zip"

Preview with an active account that holds maintenance_triage or
platform_manage; preview changes neither catalog nor import journal:

    docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" exec -T -e AI_COMPASS_NATIVE_RESTORE_TEST=1 api python manage.py restore_native_archive /tmp/native-source.zip --operator native-import-operator --preview --json

After human review, explicitly apply:

    docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" exec -T -e AI_COMPASS_NATIVE_RESTORE_TEST=1 api python manage.py restore_native_archive /tmp/native-source.zip --operator native-import-operator --apply --json

The extra opt-in alone is insufficient; the CLI also verifies exact staging
DB name/user/host, staging candidate and staging marker. **Never share** a
production DB/volume with this project.

## Semantics and limitations

- Business UUIDs, permanent HRIDs, original revision UUIDs, all history,
  timestamp, unknown JSON fields, relational links, audit records and original
  SHA-256 evidence blobs are preserved without rewriting old objects.
- Immutable *technical* ObjectTypeVersion UUIDs are mapped to local
  preseeded schema UUIDs **only if type, version and JSON schema match
  exactly**. The explicit identity map is retained in the staging receipt.
  Unknown or incompatible types/schema layouts are refused, not guessed.
- Source users are recreated as **inactive attribution accounts** with
  unusable passwords and the original usernames, with source→local numeric
  IDs recorded in the receipt. No privileges are imported. Existing target
  username collisions fail rather than silently reassign history. Create
  the separate staging operator with a distinct username.
- Restore rejects any pre-existing target business object and a different
  archive on an already-restored target. Repeat of the identical archive
  checks retained histories and original blobs, returning already_imported,
  never duplicating objects.
- SQL insertion batches of 100 are enclosed in a **single atomic whole-archive
  transaction**. Original evidence files are SHA-verified, fsynced, and
  exclusively hardlinked to their content-addressed names before DB commit.
  Failed transactions roll back; any orphan bytes are safe and revalidated.
  Dedicated non-exported restore_tracking tables retain start/failure/commit
  events. A retry after an interruption starts from a verified clean state.
- This is a version-1 logical portability mechanism, not a physical/WAL
  backup, not an arbitrary archive importer, and not production onboarding.
  A revised schema or source field contract needs a separately reviewed
  adapter. No browser uploads or production account access are granted.

## Acceptance commands

    docker compose exec -T api python manage.py makemigrations --check --dry-run
    docker compose exec -T api python manage.py test config.test_native_restore -v 2
    python3 -m unittest discover -s scripts -p 'test_verify_export.py' -v

CI additionally performs real Server→portable archive→offline verification→
isolated disposable PostgreSQL Server preview/apply→idempotent replay, and
tests corruption/collisions. Inspect old/new revisions and original evidence
through the existing staging frontend in explicit Server mode; Demo remains
independent and offline. Use only the exact disposable Compose project name
when eventually discarding the test stack with down -v.
