# FUT-03 — First shared Demo/Server workspace and persona bootstrap

> Implements [#77](https://github.com/aradenac/AI-Compass/issues/77). Other module migration/Workgroup knowledge map is scheduled in [#78](https://github.com/aradenac/AI-Compass/issues/78). Operational release acceptance stays **NO-GO**.

## What is shared

`shared-runtime.js` detects Demo/Server once at bootstrap, selects **exactly one** domain provider, defines versioned same-origin HTTP requests (CSRF/session, JSON/validation, standardized 401/403/409/422/offline status) and renders four permission-aware persona entry links: Engineer/My AI Workspace, Workgroup Studio, Management Insights and independent Maintenance & Governance. These are navigation/entry foundations, not the final task suitability/management analytics features planned later.

`shared-catalog.js` owns **one Catalog list/editor/history controller and its markup** for Models, Providers, Harnesses and Frameworks. It consumes `model-catalog.js` existing identical, safely escaped cards and interchangeable `catalog[type].list/create/revise/revisions` providers. Server uses real Django APIs; Demo uses browser `db.components`, its original fictional seeded data and persistent revision log. Edits submit exact `expected_revision`; 409 conflicts show rejection/reload guidance. Unknown JSON properties are preserved via the raw object editor. The existing Server 'Inspect original catalog record' and evidence panels remain available for uncommon or unsupported historical records, not copied into a separate business UI.

`server-tasks.js` now provides the **same Task tree/editor/history/reorder presentation** to both modes. It accepts an injected fictional `tasks.request` provider or uses the real versioned Task API. Demo updates its own `db.tasks` with local version history and parent/sibling checks; Server continues to use permanent `tsk-*` IDs, exact revisions, CSRF and its own tested database structure. Demo's existing attached Test Case, inherited DoD and solution-evidence detail section remains accessible below the shared Task tree; it is **not imported to Server**.

## Modes and roles

Run Demo by opening `prototype.html` with the accompanying static JS files (no Docker/PostgreSQL, no Server API call or real credentials). Login is to fictional local accounts; their simulated role controls edit visibility. The Demo provider persists only in its existing localStorage key. Run Server with Compose, open `/?mode=server` and sign in with an actual account. The Server provider fetches exclusively `/api/v1` and **never** uses Demo data or changes mode on failure. A new Server database remains empty.

Persona entry uses `?mode=demo&workspace=engineer|workgroup|management` or `?mode=server&workspace=engineer|workgroup|management`, with independent Maintenance on `/maintenance?mode=server`. Only capabilities returned by the server can produce role links. The backend's own access checks remain mandatory, even if a user deep-links manually. Role-specific discovery UI will be refined by later FUT issues; no mock management financial data is passed into Server.

## Tests and safety

CI runs `node scripts/test-shared-frontend.js` alongside existing Demo/Server JS checks and all backend/restore tests. It validates the same Catalog/Task rendering for both providers, absence of persisted cross-mode fallbacks, denied/unauthorized/conflicting status and CSRF handling, invalid server JSON, and startup/route wiring. The frontend build and manifest pin the two new static modules, component versions and tested source. **No database schema or business API changes** are required.

Rollback means deploying the **previous coordinated frontend artifact** as one unit, never mixing old/new missing JS files; Server data revisions are not deleted. The previous Server panel remains temporarily for advanced inspection and older module compatibility. Removing its redundant elements belongs to the #78 migration, not to the creation of a third enduring frontend.
