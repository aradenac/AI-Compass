# PLAT-35: isolated migration staging and human acceptance

The CLI tests a registered data-migration artifact on a **disposable copy of an
existing Server database**. It is not a production migration engine. Never use
staging acceptance as permission to replace production with the staging DB.
Production changes will be governed separately by issue #26.

## Prerequisites

- Git, Python 3, Docker and Compose; a clean tracked checkout.
- A named, verified **full** PLAT-29 recovery point, not a DB-only snapshot.
  The dump, evidence tar, full manifest and completion marker must all exist.
- A free private host loopback port (default 18081; production 8080 refused).
- A trusted machine. The restored source backup may contain real account data.

## Operational commands

From the AI Compass repository root:

    python3 scripts/full_recovery.py verify /mnt/backup/ai-compass-<id>.dump
    python3 scripts/migration_stage.py create --snapshot /mnt/backup/ai-compass-<id>.dump --port 18081

The command returns JSON with a candidate_id and local URL.
Open http://127.0.0.1:18081/?mode=server in a browser on the host.
A red STAGING banner should be prominently visible.

    python3 scripts/migration_stage.py status <candidate_id>
    python3 scripts/migration_stage.py verdict <candidate_id> rejected --notes "Historical incompatibility"
    python3 scripts/migration_stage.py discard <candidate_id>

Once a candidate has been discarded, its private credentials are destroyed.
For a fresh isolated attempt from the same source snapshot, call create with
the same snapshot path. While a candidate remains active, use:

    python3 scripts/migration_stage.py recreate <candidate_id> --port 18081

Recreate discards the old stage and returns a **new** candidate ID.
It always restores the same unmodified recovery point rather than preserving
any staging-only edits. Reject/discard/recreate as many times as required.

After inspecting the real Server frontend, and **only after** doing so:

    python3 scripts/migration_stage.py verdict <candidate_id> accepted --frontend-checked --notes "Checked original and migrated revisions, preserved extensions and downloaded evidence"
    python3 scripts/migration_stage.py discard <candidate_id>

An acceptance without --frontend-checked is refused. This flag records a human
attestation; it is not a claim that automated tests inspected a browser.

## Registered migration and automated controls

The only registered example is model-v1-to-v2@1, implemented in
backend/config/management/commands/stage_model_v1_to_v2.py.
Its exact SHA-256 and current application Git commit are pinned to the report.
The command refuses any database except the marked disposable staging target.

Compatible historical Model v1 records gain a new Model v2 revision. Original
revisions, identifiers, timestamps and all unknown JSON properties remain
unchanged; no default values are invented. An incompatible extension blocks
the whole migration transaction and reports the failing identifier. It never
rewrites or removes historical revision or schema rows.

The CLI verifies the four-file source and every evidence hash before loading
the archive; restores the DB to a fresh, separately credentialed PostgreSQL
volume; verifies its original ID/revision/schema fingerprint; restores each
evidence byte to a dedicated evidence volume; checks all historical revision
digests and FK integrity after migration; validates append-only revision and
audit counts; and invokes an authenticated original-byte Django download
against the staged evidence volume. Failed checks cannot lead to acceptance.

The new Compose project is named ai-compass-stage-<candidate_id>, with its
own private Docker network, staging volumes and credentials. The network is
internal and Caddy binds only to 127.0.0.1 on the dedicated port. The existing
Server frontend and Django code are served unchanged apart from the clearly
labelled staging banner. There is no import from, export to or fallback to
seeded browser Demo localStorage.

## Manual acceptance checklist

In the staged Server page, confirm the red staging label and authenticated
Django login. Check a historical Model v1 record now has an additional v2
revision, that old revisions and unknown/null extensions remain inspectable,
and that current non-migrated records are unchanged. Download evidence from
an existing linked record. Optionally edit a test copy and refresh; such
staging-only edits must not appear in production. Record concrete findings
in the --notes field; choose accepted or rejected explicitly.

Each candidate report records the recovery-point identifier and manifest
checksum, app commit, migration name/sha256, schema inventory, integrity
checks and outcome. The verdict is also written once as verdict.json.
A report survives discard; only named, ownership-labelled staging volumes,
containers and ignored candidate credentials are removed. The CLI refuses
unknown or production-like volume ownership before destroying anything.
Source recovery files and production volumes are never removed.

## Tests

    python3 -m unittest discover -s scripts -p test_migration_stage.py -v
    python3 -m unittest discover -s scripts -p test_full_recovery.py -v
    docker compose exec -T api python manage.py test config.test_migration_staging -v 1
    node scripts/test-model-catalog.js
    node scripts/test-catalog-types.js

The CI includes a real staged full restore, serving the common frontend and
repeated reject/recreate/discard without changing the original Server record.
A manual frontend verdict is still required before any future production
migration approval. Staging does not automate production rollout, user
masking or production rollback.
