# UX-R06 — persona journey coverage evidence

**Scope:** desktop browser only (Chromium reference 1366×900). **Status:** partial, open under
[issue #125](https://github.com/aradenac/AI-Compass/issues/125). This document distinguishes a
*delivered and exercised* journey from a *linked screen*, and states what remains missing or
blocked. **Do not close issue #125 solely from this matrix.**

Normative reference: [role-based UX specification §§3–7, §13](role-based-user-experience-and-guided-navigation.md).
Related: [UI acceptance contract](ux-acceptance-contract.md), [UX-R04 convergence](ux-r04-domain-equivalence.md),
[publication lifecycle](publication-and-information-lifecycle.md), [Workgroup Studio](workgroup-studio.md).

An existing navigation link is **not** counted as a passing journey: every "implemented" row below
names the deterministic fixture and the executable check that exercises the behavior.

## 1. §13 scenario-to-component-to-data-source coverage

| # | §13 journey | Delivered component (data source) | Status | Concrete evidence |
| --- | --- | --- | --- | --- |
| 1 | Engineer with a defined job/specialty: relevant Tasks, few measured options, By Task/By Tool, Solution Detail with contextual guide, return preserving the branch | `shared-engineer.js` over `/api/v1/engineer/workspace` (Server) and the fictional Demo projection; `ID_COLLAPSED` route state | **Implemented** | Chromium `Standalone Demo engineer 1366` (By Tool → By Task → detail → `#ux-engineer-setup` → measured Run → browser Back keeps the exact URL); `config.test_engineer` (real profile, published evidence, precise setup); `related Results / Guide / Feedback / access interest` sections in the detail view |
| 2 | Engineer Windows-only: Windows-capable first, a Linux-only tool still discoverable as **Requires Linux**, OS change re-evaluates without deleting history | `shared-environment.js#compose` reused by `shared-engineer.js` (Demo synthetic classification) and `config.engineer_services._by_solution` (Server `compose_os`) | **Implemented** | Chromium `Standalone Demo multi-role persona journeys 1366` (declare Windows only → `Requires Linux` chip, explicit reason, alternative still listed); `scripts/test-shared-engineer.js` (Windows/Linux/unknown/unconfigured matrix); `config.test_engineer.test_person_scoped_relevance_os_alternative...` |
| 3 | Engineer without a complete workload profile: explicit profile-not-configured plus a way to explore published solutions without invented Task membership | `shared-engineer.js` (header state + `No verified suitable configuration…Alternatives below state their exact Unknown / unavailable state` + `Explore all Tasks and solutions`), `config.engineer_services.workspace` (`profile.status = not_configured`) | **Implemented** | Chromium same journey (unknown profile state before the OS declaration); `config.test_engineer.test_no_profile_no_private_runs_no_fake_ranking_or_access` |
| 4 | Engineer with access: authentic usage feedback linked to the measured Solution/Task, Public/Internal preserved | `shared-engineer.js` feedback form → `/api/v1/engineer/feedback` → ordinary discussion threads (`discussion_services`) | **Implemented** | Chromium `Authenticated Server Engineer feedback and Management drill-down 1366` submits real feedback against a seeded published measured Solution/Task, asserts the "no entitlement or provisioning was granted" status, and reads the recorded thread back through the authorized discussions API where `context_id === solution_id`, `kind === feedback` and `scope === ["public"]`; context-preserving return (`all_tasks=true`); `config.test_engineer.test_csrf_feedback_context_and_permanent_demo_server_separation` |
| 5 | Engineer deployment-eligible but lacking access: express interest, discussion/DAP request properly linked, not a ticket | Engineer detail "Express interest in access" → public discussion, explicitly not a grant; entitlement state shown from `/api/v1/engineer/deployments` | **Delivered in part; `structured DAP access request` = owner decision (not implemented, not transferred to #126)** | Delivered and exercised: the interest/discussion path, the "no entitlement, approval or provisioning implied" wording, and the person-scoped deployment/first-use panel. **Owner decision pending — spec dependency:** a *structured access-request object with a resolvable approval status* does not exist in the repository (verified: no `access_request`/approval state in `deployment_services.py`/`models.py`); the discussion path is explicitly **not equivalent** to such an object. Adding it is an owner/product decision (§6.3 Deployment row) and is **not** part of #126's acceptance either |
| 6 | Engineer proposes a new use from Task context, with no mandatory Watch/Forecast/Task or workgroup To-Do | Engineer detail "Suggest an unmet need for this Task" → discussion with `kind=idea` | **Implemented** | `config.test_engineer` idea path; `test-engineer.js` unit coverage of accepted/rejected contexts |
| 7 | Engineer follows Workgroup Updates: published platform knowledge only, never internal drafts or the Activity Feed | **New** `shared-updates.js` + `GET /api/v1/updates` (`config.updates_services`) and the fictional Demo projection | **Implemented** | Chromium `Authenticated Server published persona journeys 1366` (reader sees published items; a Workgroup-only source is rendered as provenance text, not a live link) and `Standalone Demo multi-role persona journeys 1366` (draft guide `g5` and internal Watch `w2` absent; exclusion disclosure states "never included"); `config.test_updates` (real auth/APIs, published-only, drafts/internal/forecast excluded, withdrawn evidence leaves the view); `scripts/test-shared-updates.js` |
| 8 | Multi-role user switches Engineer → Workgroup → Management → Maintenance without logout, only where granted; unavailable APIs not obtainable by URL | `shared-runtime.js` (explicitly granted personas, never inherited), persona menu in `shared-shell.js`, Server routing fail-closed in `server-mode.js` | **Implemented** | Chromium `Standalone Demo multi-role persona journeys` (exactly 3 granted personas for the multi-role Demo account; no Maintenance) and `Authenticated Server published persona journeys` (maintenance-only account keeps Audit & Changes, gets **no** updates/Workgroup screen even when the URL asks for it; a contributor cannot reach Users & Access by URL) |
| 9 | Workgroup Studio: five themed zones, core emphasis, accurate semantic links, no mandatory sequence, **Profitability → Technology Catalog** gap link | `shared-workgroup.js#renderMap` + `coverageGapNotice`, `shared-opportunity-heatmap.js` per-Task gap link | **Implemented** | Chromium same Demo journey (5 zones, ≥5 core-class blocks, accessible names, `[data-studio-gap]`, `[data-heat-gap]` → catalog gap notice naming the Task and denying automatic creation); `scripts/test-workgroup-studio.js` |
| 10 | Counters: one Under-review Campaign count that can filter; no artificial Watch/Feedback pending count; not personalized | `AICompassWorkgroup.attention` (only `benchmark`/`forecasts`/`recommendations`), `status=awaiting_publication` filter in `server-campaigns.js`, Demo stage filter | **Implemented** | Chromium Demo journey (keyboard-activated badge → one filtered campaign → "Show all stages") and Server journey (badge → `awaiting a review decision` filter listing only the unresolved campaign); `test-workgroup-studio.js` asserts `attention("watch", …) === null` and `attention("feedback", …) === null`; a campaign with an effective publication is excluded from the count (`server-mode.js`) |
| 11 | Direct path Studio → Benchmark Workspace → Campaign → Run with breadcrumbs/browser Back retaining context | `shared-context.js` (`route`/`breadcrumb`/`returnTo`) + every domain controller | **Implemented** | Chromium `Authenticated Server workgroup 1366` and `Standalone Demo multi-role persona journeys` (updates source link → exact Run + requested revision → Back restores the updates surface); existing UX-R03 context journeys |
| 16 | Published editorial Recommendation pinned to Task/Solution/Run, contextual on Solution Detail, no duplicate catalog; a failed published Run never becomes a positive recommendation | `server-results.js` (measured ↔ editorial links from the published Recommendations API), Engineer detail editorial block, Demo Results notices | **Implemented** | `config.test_updates.test_editorial_recommendation_keeps_its_pinned_task_solution_and_runs` and `..._failed_published_run_is_negative_evidence_not_a_recommendation`; Chromium Results rows show the failed-DoD notice and the editorial-context action (writers) / editorial notice (readers); `scripts/test-server-results.js` asserts the authorized Recommendation read |
| 17 | Management lands on authorized DAP metrics and opens a sourced result without exposing restricted individual rates | `shared-opportunity-heatmap.js` + `/api/v1/planning/heatmap|insights|explain` | **Implemented (unchanged engine) + new gap link** | Chromium `Standalone Demo management 1366` (as-of inspector, factors, no raw JSON by default), the new gap link, **and** `Authenticated Server Engineer feedback and Management drill-down 1366`: seeds a real cohort population + saved annual scenario, selects the authorized population/scenario, drills into the exact Task × configuration cell, asserts the pinned source revision (`.ux-source-ref`), keeps the raw JSON behind a disclosure, and asserts no restricted field (`hourly_rate_eur`/`baseline_human_hours`/`linked_user`) reaches the view. Server planning exposure remains owned by `config.test_opportunity_insights` / `test_budgets` (rate fields never returned by the management views) |
| 18 | Maintenance-only entry keeps `/maintenance` and authorized health views while lacking Workgroup business editing or accounts administration | `server-mode.js` maintenance routing, `AICompassShell.serverNav` | **Implemented** | Chromium `Authenticated Server maintenance 1366` and the new URL-based fail-closed probes |
| 19 | Demo/Server: shared structure, separately scoped records, no draft-cache or Demo fallback across modes | One shell + explicit mode providers; `shared-updates.js` has **no** storage access | **Implemented** | Chromium Demo journeys assert zero `/api/v1/` traffic in Demo; Server journeys assert real authenticated data; `scripts/test-shared-updates.js` asserts the presenter never touches `localStorage`, and both providers refuse an unknown mode/scope |

## 2. Deterministic synthetic fixtures

| Mode | Fixture | Purpose |
| --- | --- | --- |
| Demo (fictional, offline) | seeded campaigns `planned` / `review` / `published`; guides `g1–g4 published` + `g5 draft`; Watch `w1 published` / `w2 internal`; `db.uxR06FixturesInitialized` OS classification (`Claude Code + CCR` → Windows+Linux, `OpenCode` → Linux only, unclassified harnesses stay Unknown); user `u6` with explicit `roles: [engineer, workgroup, management]` | published-vs-private knowledge, resolved counter, Windows-only variant with a Linux alternative, granted multi-persona switching |
| Server (disposable DB, real auth + real API) | `scripts/ux_qa.py seed_server_evidence`: harness with `supported_os=["linux"]`, model, provider, Task, Test Case, published Setup Guide + recipe, **draft** guide, **internal** Watch entry, campaign → session → interaction → close (accepted), campaign close → `under_review`, then explicit publish of the selected Run | completed/published and restricted/unavailable cases for the Workgroup, Engineer and Maintenance personas without vendor access or production records |

`ROLES["multi_role"]` includes `reviewer` so one disposable combined account can *author* and
*review* real synthetic evidence; the grants stay independent and nothing is inherited.

## 3. Verification commands actually run

```
node scripts/test-shared-updates.js            # PASS: published-only presenter/providers/boundaries (no restricted-record counts)
node scripts/test-shared-engineer.js           # PASS: OS variants, unknown states, no invented score
node scripts/test-workgroup-studio.js          # PASS: five zones, role filters, honest badges
node scripts/test-server-results.js            # PASS: authorized Recommendation read + isolation
# every scripts/test-*.js suite                 # 39/39 PASS
docker compose -p <project> exec -T api python manage.py test config --verbosity 1 --parallel 2
                                               # Ran 264 tests — OK (incl. config.test_updates, 17 real tests)
python3 scripts/verify_frontend_assets.py      # PASS: 36 assets mounted in Server + staging
python3 scripts/ux_qa.py test --base-url … --demo-url … --credentials … --artifacts …
                                               # 18/18 Chromium journeys PASS (disposable DB, clean volume)
```

Reviewed artifacts (not only green labels): `demo-attention-filter-1366.png`,
`demo-updates-source-1366.png`, `demo-coverage-gap-1366.png`, `demo-engineer-os-1366.png`,
`server-counter-filter-1366.png`, `server-updates-{workgroup,engineer,maintenance}-1366.png`,
`server-engineer-feedback-1366.png`, `server-management-drilldown-1366.png`, plus one Chromium
trace per journey. Visual inspection found and fixed a real defect: a business record with many actions
squeezed its title into a one-character column (`shared-workgroup.css`), now wrapping the action
group to its own line (`campaign-list-fixed.png`).

## 4. Still missing, blocked or intentionally out of this issue

- **Structured DAP access request** (scenario 5): requires a modeled request object with a
  resolvable approval status that does not exist today — an explicit **owner/product decision**
  with clear dependencies, **not** implemented here and **not** transferred to
  [#126](https://github.com/aradenac/AI-Compass/issues/126) (whose acceptance does not include it).
  The delivered interest/discussion path is **not equivalent** to such an object: it records
  intent in a discussion thread and grants nothing (no entitlement, approval, provisioning or
  ticket state). No invented object or status was added
  ([§6.3, §15](role-based-user-experience-and-guided-navigation.md)).
- **Automated rankings**: the primary shortlist stays descriptive (`descriptive_only_v1`,
  `score: null`, `rank: null`). No scoring formula was invented for presentation
  ([§4.2, §14](role-based-user-experience-and-guided-navigation.md)).
- **Cross-Task editable recommendation catalog**: not created; the existing Task-pinned editorial
  Recommendation lifecycle is reused.
- **Full 20-scenario certification, approved visual references** and enumeration of every
  domain's negative/revision cases remain [UX-R07 #126](https://github.com/aradenac/AI-Compass/issues/126).
- **TD-UI-01 remains open** (deferred at product-owner request): branch protection does not yet
  require the `ui-qa` status. **TD-01 is resolved by UX-R04 #123** (`docs/technical-debt.md`).
  Production release stays **NO-GO** under [release readiness](release-readiness.md). This matrix
  does not certify mobile/tablet behavior, real staging data or operator gates.
