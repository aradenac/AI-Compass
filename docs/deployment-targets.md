# FUT-15 — Deliberate deployment targets, external access and verified use

Issue: [#89](https://github.com/aradenac/AI-Compass/issues/89). Depends on FUT-06 OS compatibility, FUT-07 pinned setup recipes, FUT-13 economic projections and FUT-14 Management Insights.

## Operator workflow (Server)

Open **Deployment Planning → Deployment & External Access** as a user with \`auth.planning_view\` and \`auth.planning_manage\` (the \`deployment-planner\` role). The repository's Demo remains a separate fictional local workspace; real targets **never** import or fall back to Demo data.

1. Select a real, existing population (role, specialty, person or cohort), a published Task/configuration candidate (a measured \`sol-*\` or theoretical \`fct-*\`) and one or more explicitly identified beneficiary seats. No matrix click or opportunity suggestion creates a target. Optionally supply an originating saved \`opp-*\` scenario, in which case the candidate must already be among the selected choices for that population.
2. Optionally select a real **immutable setup-guide revision UUID**. For an individual measured Run, the existing pinned guide is offered automatically. A missing/legacy/inapplicable recipe blocks readiness rather than being silently accepted.
3. Record the status **for each required technical component** (Model, Provider and Harness): \`requested → approved → provisioned → verified\`. \`rejected\` and \`revoked\` take access out of the verified set; a new request must restart the traceable sequence. Workflow states describe manually recorded **external-tool** rights, not AI Compass roles.
4. Once all component entitlements and enterprise accessibility, an applicable Windows/Linux environment, and the pinned setup recipe are valid, record **setup_verified** with a non-secret evidence reference. Only after this can **first_use** be confirmed. Requests, approval, provisioning or verified external access **alone do not prove an invocation**.
5. Revoking a component, disabling a linked account, changing current enterprise accessibility or revising a target immediately removes unsupported activation **on the next authorized live read**. All old revisions/events remain inspectable. The three current annual opportunity slices distinguish activated potential from benchmarked or forecast opportunity without retroactively changing the saved opportunity snapshot.

**Beneficiaries:** \`seat-key | optional person WorkloadProfile public ID | optional windows,linux\` is one line per explicitly intended person/seat. A person-target must select that person. A cohort can contain persons without AI Compass accounts. If a person has a linked account, its current **self-declared OS** supersedes a manually supplied OS; deactivation blocks readiness. A cohort without an exact roster cannot be counted as activated merely because one anonymous seat was confirmed. The per-target deliberately bounded first iteration permits **at most 100 individually traced seats**, and no more than the population's current headcount; larger cohorts require explicit further roster integration, never fabricated aggregate usage. Headcounts/person-roster membership are planning declarations: they are not employee monitoring, IAM grants or automatic eligibility approval.

### HTTP API (Server)

All responses are \`Cache-Control: no-store\`. All planner routes require \`auth.planning_view\`; mutating requests require **both** \`auth.planning_manage\` and CSRF. The Engineer endpoint requires \`auth.business_read\` and exposes **only the requesting authenticated user's currently linked person profiles**, without rates or colleague records.

| Endpoint | Semantics |
| --- | --- |
| \`GET /api/v1/planning/deployments?profile_id=wlp-...\` | Bounded summary list without person-level rows |
| \`POST /api/v1/planning/deployments\` | Deliberately create one unique Task × candidate × population target |
| \`GET/PATCH /api/v1/planning/deployments/{dpt-id}\` | Authorized current beneficiary status; append new immutable target revision via \`expected_revision\` |
| \`GET /api/v1/planning/deployments/{dpt-id}/revisions\` | Original frozen selection and actor/time history |
| \`POST /api/v1/planning/deployments/{dpt-id}/events\` | Attributable, append-only component/guide/use action; requires expected target revision |
| \`GET /api/v1/planning/deployments/export?profile_id=wlp-...\` | Authorized bounded non-personal request summary; does not issue rights |
| \`GET /api/v1/engineer/deployments\` | Self-only current readiness and blockers (no colleague identities) |

Creation:
\`\`\`json
{
  "profile_id": "wlp-EXISTING",
  "task_id": "tsk-EXISTING",
  "kind": "benchmark",
  "candidate_id": "sol-EXISTING",
  "scenario_id": "opp-OPTIONAL",
  "selection": {
    "status": "selected",
    "guide_revision_id": "UUID-OF-EXISTING-GUIDE-REVISION",
    "seats": [
      { "key": "pilot-01", "person_profile_id": null, "available_os": ["linux"] }
    ]
  }
}
\`\`\`
\`scenario_id\` and \`guide_revision_id\` are optional, but guide/readiness checks fail closed if the latter cannot be resolved. The exact current candidate **type** is checked against the published evidence corpus; individual measured and theoretical candidates remain distinct and are never fabricated from each other.

Event:
\`\`\`json
{
  "expected_revision": "r001",
  "seat_key": "pilot-01",
  "component_id": "pro-EXISTING-OR-NULL",
  "action": "requested",
  "evidence_reference": ""
}
\`\`\`
For \`verified\`, \`setup_verified\` and \`first_use\`, include a **non-secret, attributable evidence reference** of at least eight characters. For setup/first-use events, \`component_id\` must be \`null\`. A complete set of component rights is scoped to a target/seat and never silently grants broader rights. No password, API key, license secret or external account token is collected or stored; any historical evidence reference should point to a safe external ticket, not contain credentials.

## Versioning, security and recovery

- Schema migration **\`config.0027_deployment_targets\`** adds the target, revision and event tables and uniqueness constraints, with PostgreSQL no-UPDATE/no-DELETE triggers. It is additive: no historical business object, Run, guide, Catalog revision, external entitlement or archived evidence is migrated or rewritten.
- All technical components, initial guide and origin scenario snapshot are pinned to authoritative IDs/revisions. Target revisions and manual events are append-only, with actor/timestamp/seat and stable \`dpt-*\` public ID. Later changes to current authorization/OS/accessibility affect **live** readiness only; historical opportunity and target selections remain unchanged.
- \`opportunity_services.project()\` reuses the FUT-13 allocation function, injecting \`verified_count\` from the current external access and first-use journal only for **positive quantifiable** candidate cells; a negative/withdrawn/non-comparable measured source never gains fabricated activated value. Management maturity indicator \`D\` means usage verified; \`B\` / \`F\` retain measured/theoretical semantics.
- No endpoint provisions accounts, buys seats, rotates credentials, edits AI Compass groups, changes catalog pricing or mutates third-party systems. Merely exploring a scenario or Management cell is always read-only.
- **Operational gate:** apply \`0027\` only after the usual verified recovery point and isolated staging rehearsal under [migration-staging](migration-staging.md), [migration-production](migration-production.md), and [release-readiness](release-readiness.md). Never auto-promote staging or declare a production GO merely because CI passes. Old binaries should not be used with live newly written target data; rollback is the normal coordinated artifact and verified recovery procedure, **not** destructive table drops.

### Verification commands

\`\`\`sh
docker compose run --rm api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_deployments config.test_opportunities config.test_opportunity_insights config.test_workloads config.test_environment config.test_setup_composition -v 2
node --check server-deployments.js
node scripts/test-server-deployments.js
node scripts/test-server-planning.js
\`\`\`

All test identities, accounts, cohorts and entitlement states are synthetic. To exercise positive first-use conditions end-to-end, a staging environment needs valid **current** enterprise component accessibility, a Windows/Linux-compatible Harness, a pinned applicable Setup Guide, and complete manually recorded external grants. Changes to eligibility/access/OS can be verified by reading the same current DAP scenario before and after and checking that its frozen revision does not change. Authorization should be exercised using an ordinary Engineer, a planner, a disabled user and a maintenance-only account.
