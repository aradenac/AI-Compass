# FUT-06 — Windows/Linux user environments and composed OS compatibility

Implements [#80](https://github.com/aradenac/AI-Compass/issues/80) from the [approved specification](os-compatibility-and-user-environment.md). FUT-07 (setup recipes), FUT-12 (evidence-backed engineer matching) and FUT-15 (deployment entitlement) are **not** delivered by this feature.

## Two distinct truths

1. **Self-declared available OS** belongs to each authenticated `business_read` user. The same browser UI with Windows and Linux checkboxes is used in Demo and Server. Server persists an append-only `UserEnvironmentRevision` history; `GET /api/v1/profile/environment` exposes `available_os:null`, `configured:false`, `revision:null` for an existing user who has never declared an environment. `PATCH` with exact `expected_revision` (null on initial write) and nonempty Windows/Linux list appends a revision (409 on stale write). Only the *signed-in person* can write their record, protected by session + CSRF, never another user's. `GET /api/v1/profile/environment/revisions` reads the account's own historical declarations. Deliberate removal of the last OS is invalid, not synonymous with 'no computer.' Browser User-Agent and hosting OS are never used to infer availability.
2. **Harness/Framework supported OS** lives in each immutable catalog revision's `properties.supported_os` array (Windows/Linux only). Its read projection `os_compatibility` is `classified` or `unknown`. Editors show two explicit checkboxes; saving a classified tool requires at least one. The backend prevents any newly published or asserted `active|usable|enabled|supported` Harness or Framework without valid nonempty classification. Older unclassified drafts/revisions stay readable without backfill, and an incomplete draft can be created before classification; it cannot be marked usable without the OS assertion. Model/Provider are not OS-scoped. Narrowing declared OS appends a new catalog revision and leaves historical guides, Runs, price pins, and setups unchanged.

A change of environment **does not** issue an enterprise technology access grant, confirm an individual subscription/license, establish a working Setup Guide, validate infrastructure or prove first use.

## Composite OS projection and discovery

`POST /api/v1/environment/compatibility` accepts 1–65 explicit *Harness or Framework* catalog source references `{type,id,revision_id}`, plus optional `topology:shared_os|distributed_unknown`; it requires a real authenticated `business_read` session and CSRF. Every referenced revision must belong to the same real Server item. `shared_os` means a single common OS across the Framework and **all** relevant participant Harnesses. Result statuses are:

| Result | Interpretation |
| --- | --- |
| `compatible` | Intersection includes Windows/Linux actually self-declared for this user; no license, quality or guide implied |
| `other_os` | Candidate is still visible and interesting, but requires an additional Windows/Linux environment |
| `unconfigured_user` | Candidate known but user's OS profile unknown; prompt **Set your OS** |
| `unknown` | Missing/invalid legacy Harness/Framework OS classification; never assume both |
| `unsupported_combination` | Known Harness/Framework sets have an empty common intersection; not a viable shared-OS setup |
| `unknown_topology` | A distributed/multi-machine execution cannot be verified by the current simple intersection model |

Unknown essential components are *not* silently considered compatible; a definitively empty intersection remains unsupported even if another component is unclassified. All rows remain visible in discoverable primary-compatible, secondary other-OS and unclassified lists; the full Technology Catalog keeps explicit Windows/Linux/Both/Unknown filtering as an optional UI query, not a destructive catalog query. This is a **coarse OS facet**, not a benchmark-quality ranking or entitlement gate.

API returns exact source revision numbers/UUIDs and explicitly marks entitlement, guide and measured quality as separate/unverified. Both modes use the same client-side presentation and normalization; the standalone **Demo uses only fictional local fixtures and the browser-local profile history**. No Demo data is sent to or substituted for Server.

## Migration, rollback and test scope

Migration `0024_user_environments` adds one append-only table and a revision-immutability trigger. There is **no migration or mutation of existing catalog items, OS profile defaults, benchmark Runs or evidence**. Missing OS remains null. A previous coordinated frontend/backend release can be restored with the matching verified recovery manifest; never modify/delete protected existing revisions. Database recovery must account for the additive table; do not use a downmigration as a way to discard users' OS changes.

CI runs `python manage.py test config.test_environment` against PostgreSQL and `node scripts/test-environment-frontend.js` against browser-free independent Demo/Server fixtures. They cover Windows-only, Linux-only, both, unknown/unconfigured, OS intersection, disjoint Framework sets, multi-participant Harness intersections, independent real user profiles, reader/editor/maintenance/unauthenticated permissions, CSRF, optimistic conflict, immutability and historical revision pinning.

**Production**: a green CI or local Demo is not the manually approved signed staging/recovery deployment; the PLAT release gate remains **NO-GO**.
