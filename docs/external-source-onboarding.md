# PLAT-33 — External onboarding, with isolated mock adapter

**Implementation status:** mock-contract backend is implemented and CI-tested.
**Operational status:** NO-GO for ingesting real data. The real origin,
data-sharing permission, source format, mapping and production release are
still unselected/unapproved. The simulated connector is NEVER a substitute
for approving/ingesting a real source, and it cannot run on the normal Server.

## Safe prototype contract

The first target type is **Model**, using an isolated source identifier
\`mock-model-catalog-v1\` and a stable \`source_key\` supplied by a *synthetic*
test provider. This is **not** the browser Demo/localStorage dataset.

The backend reuses existing versioned \`CatalogItem\`, \`CatalogRevision\`,
\`CatalogAuditEvent\`, active \`ObjectTypeVersion\` and immutable
\`EvidenceBlob\`/\`EvidenceLink\`. Additive tables keep:
- \`ExternalImportBinding\`: durable source-system + source-key → Model
  identity and latest source-controlled revision, with conflict detection.
- \`ExternalImportBatch\`: immutable digest-keyed run, operator and timestamp.
- \`ExternalImportEvent\`: immutable per-row action, original row hash,
  referenced revision and evidence link.

A Model is created only for a previously unseen source key. Subsequent
**different** content creates a new immutable revision. Identical content
does not revise an object; an exact previously applied batch returns the
same batch ID without new objects, events or evidence. If someone edits the
target Model outside import, the next import reports a **conflict** and
refuses to silently overwrite their changes. All rows apply within one
atomic PostgreSQL transaction and serialize through an advisory lock.

Each changed row is attached to its resulting revision as a content-addressed
immutable **canonical mock JSON row**. This is explicitly labeled synthetic
mock evidence; no real document or original external bytes are claimed.
The existing evidence download path independently verifies the SHA-256 and
original bytes. Ordinary users are not given import permissions.

## Deliberately gated disposable staging

The import endpoints are **disabled in production**, not merely hidden.
They are enabled only if *all* conditions are met:

- \`AI_COMPASS_MOCK_IMPORT_ENABLED=1\` explicitly;
- \`AI_COMPASS_STAGING=1\`;
- \`AI_COMPASS_STAGING_CANDIDATE\` is exactly 16 lowercase hexadecimal digits;
- PostgreSQL database/user/host are exactly
  \`ai_compass_restore_verify\` / \`ai_compass_restore\` / \`db\`.

The default is disabled; configuring an ordinary Server as a staging target
must never share its original DB, evidence directory or credentials.

For a disposable, explicitly named staging instance use
[staging/compose.yaml](../staging/compose.yaml) and the
[staging isolation runbook](migration-staging.md). Before starting it,
set \`AI_COMPASS_MOCK_IMPORT_ENABLED=1\` (in the operator's *staging-only*
shell, not a production \`.env\`). After verified provisioning, run:

    docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" \
      exec -T api python manage.py migrate --noinput
    docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" \
      exec -T api python manage.py bootstrap_identity
    docker compose -f staging/compose.yaml -p "$RESTORE_PROJECT" \
      exec api python manage.py bootstrap_identity \
      --username test-import-operator --role import-operator

Use the real Django CSRF cookie/token plus the operator's authenticated
session; there is NO anonymous/admin bypass. An import operator is not
implicitly a business writer, maintenance operator or user administrator.

## Authenticated mock API

| Endpoint | Method | Rights | Result |
|---|---|---|---|
| \`/api/v1/imports/mock-models/preview\` | POST | \`import_preview\` | Schema-aware planned actions and short-lived, actor-bound signed token |
| \`/api/v1/imports/mock-models/apply\` | POST | \`import_apply\` | Atomic explicitly reviewed application with audit receipt |
| \`/api/v1/imports/mock-models/batches/<UUID>\` | GET | \`import_preview\` | Immutable batch-level result and source hashes |

To exercise from an authenticated client in *disposable staging only*,
POST [scripts/fixtures/mock_model_catalog_v1.json](../scripts/fixtures/mock_model_catalog_v1.json)
to \`preview\` (Content-Type application/json, CSRF header and session).
It must yield actions \`created\` for both records on an empty staging
Server, no data mutation and a \`preview_token\`. POST the **same object**
plus \`preview_token\` to \`apply\`. Never fabricate a token or bypass the
review. Repeat preview+apply identically: the second response returns
\`already_imported:true\` and the same batch ID.

Changing Model Alpha's \`context_window\` to 16384 in the fixture
(not in a real system) yields \`revised\` for Alpha and \`unchanged\`
for Beta. Its first revision stays byte-exact. The signed preview expires
after 15 minutes, is bound to the operator, exact request SHA-256, each
row checksum and current target revision. New source data, a concurrent
manual change or a different operator require another preview.
Invalid/unsupported source rows produce explicit \`invalid\` or
\`conflict\` results with no authorization to apply.

The batch's original evidence is **synthetic** and only present in this
isolated stack. The independent seeded Demo browser runtime remains
unchanged; its localStorage is never imported or synced.

## Separate local preflight for actual source discovery

The existing \`scripts/external_source_preflight.py\` checks a bounded real
CSV or JSONL export in a read-only manner. It requires source ownership,
permission basis and explicit human attestation and produces only a
checksum/field inventory, with \`approved_for_apply=false\`. It does not
connect to the DB or call the synthetic adapter.

## Next step when a real source exists

Before a genuine import, obtain the first real source's origin, owner,
representative examples, permissible fields, source key, expected Model
mapping and exact original evidence contract. Separately implement/review
an **explicit real-source adapter**, not a renamed mock source ID or a
turning on of the mock API. Its deployment is subject to the still deferred
real staging, controlled production migration and GO/NO-GO release gates.

## Checks

    docker compose exec -T api python manage.py makemigrations --check --dry-run
    docker compose exec -T api python manage.py test config.test_external_mock_import -v 2
    python3 -m unittest discover -s scripts -p test_external_source_preflight.py -v

CI runs these checks plus the cross-role real Server journey, immutable
history/native archive, full DB+evidence restore and standalone Demo.

**Ticket completion policy:** when this mock implementation is merged,
the owner may close #33 as a **mocked development milestone**, leaving
real source selection, human operational release and future defects
explicitly deferred. A green simulated test is not a real-source
onboarding certification.
