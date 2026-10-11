# FUT-07 — Composable Setup Guides (Demo and Server)

## Principle and scope

A Setup Guide `gui-*` remains an immutable, revisioned knowledge-base record. It may contain standalone **text**, an external **HTTP(S) URL**, or both; these legacy forms remain intact. New guides can carry an optional `properties.recipe` which references other guide versions as reusable **modules**. The recipe itself is another `gui-*` revision, not a second mutable knowledge database.

This introduces **declared applicability and completeness checks**, not certification. A future publication gate (FUT-10) validates adequate instructions for the evaluated exact setup. Do not use `ready` as evidence that an installation has actually succeeded.

### Recipe example

```json
{
  "name": "Cline + provider + model setup on Ubuntu",
  "properties": {
    "text": "Overview and end-to-end verification procedure",
    "recipe": {
      "required": ["os", "model", "provider", "harness", "runtime"],
      "applies_to": {"os": "ubuntu-22.04", "harness": "har-cline"},
      "required_groups": ["installation"],
      "modules": [
        {
          "id": "gui-common-install",
          "revision": "r001",
          "group": "installation",
          "applies_to": {"os": "ubuntu-22.04"},
          "requires": []
        },
        {
          "id": "gui-integration",
          "revision": "r003",
          "requires": [{"id": "gui-common-install", "revision": "r001"}]
        }
      ]
    }
  }
}
```

Create the referenced modules first. The UI can append selected existing immutable guide revisions into a recipe, and exposes a JSON editor for applicability, dependency edges and variants. `required_groups` selects named alternative groups. At most one applicable module per group is accepted, and a missing required group is an explicit incomplete state. Compatible OS variants use the same group with mutually exclusive `applies_to` values. Reuse keeps the same original module version, even when its current documentation is subsequently revised.

### Frameworks and collaborative workflows

The session renderer obtains a list of **actual selected, revision-pinned participants** from the campaign snapshot. It requires one module group `participant:<participant-public-id>` for **each** selected participant, plus `framework_wiring` for coordination, routing, handoffs and end-to-end verification. Missing or ambiguous groups are incomplete and cannot silently be called reproducible. Modules may additionally constrain their own `applies_to` using exact component/version/environment values.

## Server endpoints and integration

| Endpoint | Capability | Purpose |
| --- | --- | --- |
| `GET/POST /api/v1/guides` | business_read / business_write | Existing reusable guide catalog, now supporting recipe properties |
| `PATCH /api/v1/guides/<id>` | business_write | Append immutable recipe/document revision, optimistic concurrency |
| `POST /api/v1/guides/render` | business_read | Preflight an explicitly pinned guide `{guide_id,revision,configuration}`; no external URL fetch |
| `GET /api/v1/sessions/<id>/guide` | business_read | Read original guide revision rendered against the *actual pinned* test setup, stored OS/runtime environment and recorded deviations |

Workgroup **Guides & Charter** offers the editor, history and explicit render preview. The **Campaign** editor links a reusable guide and previews proposed configuration/environment before saving; **Test Run** creation can select any existing guide, and the session installation step can read its original rendered version. Existing Campaign, Session and Run FKs preserve exact original guide revisions; session checkpoints preserve actual installation environment, human notes and deviations. Component ID/version fields in the session guide API are loaded from frozen relational pins, never trusted from a submitted client claim.

Legacy standalone guides remain readable and are marked **unverified** for composed exact-configuration coverage. No invalid published benchmark claims are introduced by these preflight tools.

## Standalone fictional Demo

The single-file `prototype.html` stays offline, browser-local and has **no Server API fallback**. Demo guide forms accept optional recipe JSON, guide details display deduplicated pinned module snapshots, and simulated runs store the original guide and deep copies of referenced module versions. Later document edits cannot rewrite those original run snapshots. Unpublished module copies are filtered from public run projections. Demo records are never imported into PostgreSQL.

## Safety, rollout and verification

There is **no database schema migration**: `recipe` is an additive optional field of the existing permissive guide JSON schema. All existing guide records and immutable revisions are unchanged. A rollback to the previous application version ignores unknown recipe properties while preserving JSON history. Existing verified platform backup/restore and production migration approvals remain separate.

Recommended checks on a disposable Server with PostgreSQL:

```bash
docker compose exec -T api python manage.py test config.test_setup_guides config.test_setup_composition config.test_setup_recipe_views config.test_sessions -v 2
node --check server-guides.js
node --check server-campaigns.js
node --check server-sessions.js
node scripts/test-server-guides.js
node scripts/test-server-campaigns.js
node scripts/test-server-sessions.js
bash scripts/smoke-platform.sh
```

Verify: shared module reuse, exact pinned history before/after revision, Linux/Windows variants and ambiguous groups, nonexistent pins, Framework participants/wiring gaps, read-only/maintenance access restrictions, Demo isolation, session checkpoint and deviation preservation. Browser acceptance, real-world environment setup, archival recovery, Internet exposure and human production sign-off remain explicit operational gates.
