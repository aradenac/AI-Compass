# Desktop UX acceptance matrix — UX-R07 (#126)

> **Status:** Living traceability matrix for the normative [role-based UX](role-based-user-experience-and-guided-navigation.md#13-recommended-ux-validation-journeys) §13 journeys and the modal requirements NFR-UX-001/002. It records **what was actually executed in a real desktop Chromium session** and, just as importantly, what is **not** proven.
> **Scope:** Desktop web only — reference viewport 1366×900, standalone fictional Demo **and** isolated authenticated Server. Mobile/tablet are out of scope by product-owner decision (2026-10-11).
> **Last executed run:** 2026-10-12, local disposable stack (`docker compose` Server + static Demo): 16/16 checks PASS, 15 VERIFIED / 5 PARTIAL / 4 BLOCKED requirements. A green run is **not** a production GO: [release readiness](release-readiness.md) stays **NO-GO**.

## How to read this matrix

| Status | Meaning |
| --- | --- |
| **VERIFIED** | Every mapped check ran in the same real-browser run and passed, with inspectable artifacts. Not a code-reading claim. |
| **PARTIAL** | The mapped checks ran and passed, but a named part of the scenario still needs data or UI owned by another issue. The gap is stated, never implied away. |
| **BLOCKED** | The owning implementation is not on this base (UX-R05 [#124](https://github.com/aradenac/AI-Compass/issues/124) / UX-R06 [#125](https://github.com/aradenac/AI-Compass/issues/125)). No proxy assertion was substituted and no pass is claimed. |
| **UNMAPPED / FAILED** | The registry references a check that did not run, or a mapped check failed. The gate exits non-zero and the PR must not merge. |

The registry that produces this table lives in [`scripts/uxqa/coverage.py`](../scripts/uxqa/coverage.py). Deleting or renaming a mapped check breaks the run, so a scenario can never silently become "verified".

## Reproduce

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r scripts/requirements-ui-qa.txt
python -m playwright install chromium

python3 scripts/init-env.py
docker compose up -d --build --wait
docker compose exec -T api python manage.py migrate --noinput
python3 -m http.server 8090 --bind 127.0.0.1 --directory . &

python3 scripts/ux_qa.py provision --output /tmp/uxqa-credentials.json
python3 scripts/ux_qa.py test \
  --base-url http://127.0.0.1:8080 \
  --demo-url http://127.0.0.1:8090/prototype.html \
  --credentials /tmp/uxqa-credentials.json --artifacts /tmp/ux-qa
```

`provision` creates disposable randomized accounts only (never run it against production). The run writes `report.json`, `report.md`, screenshots and Chromium traces next to each other. The CI check keeps the exact name **`ui-qa`**.

## §13 scenario traceability

| # | Scenario (abridged) | Persona | Fixture | Mode | Positive check | Negative probe | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Task-first Engineer, By Task/By Tool, solution detail, contextual return | Engineer (`user`) | Fictional Demo seed; empty authenticated Server catalog | Demo + Server | `Standalone Demo engineer 1366`, `Authenticated Server engineer 1366` | Mutation probe *broken breadcrumb/return* | `demo-engineer-1366.png`, `demo-engineer-origin-1366.png`, `server-engineer-1366.png` | VERIFIED |
| 2 | Windows-only ordering, Linux-only alternative stays discoverable | Engineer | Demo OS metadata | Demo + Server | Only the honest `not_configured` / `unknown OS` state is asserted | — | `server-engineer-1366.png` | **PARTIAL** — OS relevance ordering needs seeded multi-OS published configurations (UX-R06 #125) |
| 3 | Engineer without a complete profile sees an explicit unconfigured state | Engineer | Empty Server; Demo simulation-only profile | Demo + Server | `Standalone Demo engineer 1366`, `Authenticated Server engineer 1366` | — | `server-engineer-1366.png` ("Profile: not_configured", "No personal Task profile assigned") | VERIFIED |
| 4 | Authentic usage feedback linked to a measured solution | Engineer | Demo measured Runs | Demo + Server | Demo feedback/interest path exercised; Server write refusal asserted (`POST /api/v1/guides` → 403) | `Authenticated Server authorization fail-closed` | `demo-engineer-1366.png` | **PARTIAL** — a positive Server linkage needs a seeded published Run (UX-R06 #125) |
| 5 | Deployment-eligible Engineer without access expresses interest, DAP-linked | Engineer | Requires DAP data | Server | — | — | — | **BLOCKED** (#125) |
| 6 | Engineer proposes a new use from Task context | Engineer | Requires the idea flow | Server | — | — | — | **BLOCKED** (#125) |
| 7 | Reader sees published knowledge only, never internal drafts or privileged events | Engineer vs Contributor | Demo draft Guide `g5` + internal event `e1`; internal Server Watch entry | Demo + Server | `Standalone Demo publication boundary`, `Authenticated Server publication boundary` | Contributor-side positive visibility inside the same check | `server-watch-internal-1366.png` | VERIFIED |
| 8 | Multi-role switching only when permitted, no logout, no URL-based escalation | Multi-role (`contributor`,`user-admin`,`deployment-planner`) and maintainer | Combined-grant and single-grant fixtures | Server | `Authenticated Server multi-role workspace switching`, `Authenticated Server authorization fail-closed` | Refused routes (management/planning, users, `/maintenance`) and refused APIs (403) | `server-multi_role-switch-*.png`; report `api_denials` | VERIFIED |
| 9 | Workgroup five-zone map, core emphasis, semantic links, opportunity gap | Contributor | Demo seed; empty Server catalog | Demo + Server | `Standalone Demo workgroup 1366` (5 zones, `section=opportunities` deep link), `Authenticated Server workgroup 1366` | — | `demo-workgroup-map-1366.png`, `server-workgroup-1366.png` | VERIFIED |
| 10 | One resolvable count; no artificial pending count | Contributor | Demo under-review Campaign + Watch fixtures | Demo | `Standalone Demo workgroup 1366` | The Watch block must expose **no** attention badge | `demo-workgroup-map-1366.png` ("1 requiring review") | VERIFIED |
| 11 | Diagram → Benchmark → Campaign → Run with breadcrumbs/Back | Contributor, Engineer | Demo Campaign/Run fixtures | Demo + Server | `Standalone Demo workgroup 1366` (record deep link, reload, Back, Forward, return link), `Standalone Demo engineer 1366` (measured Run + Back) | Mutation probe *broken breadcrumb/return* | `demo-workgroup-return-1366.png`, `demo-engineer-origin-1366.png` | **PARTIAL** — the Campaign → Run stepper deep link is delivered by UX-R05 #124 |
| 12 | Run stepper with local draft resume and no phantom Runs | Contributor | — | Server | — | — | — | **BLOCKED** (#124) |
| 13 | Incompatible local draft invalidated, authoritative records untouched | Contributor | Injected stale-revision, expired and foreign-scope drafts | Demo + Server | `Demo/Server draft isolation contract` (real `shared-drafts.js`) | Draft engine refuses a stale schema/revision and omits password/secret fields | `demo-draft-contract-1366.png`; report `checks` | VERIFIED |
| 14 | Concurrent edit: stale save 409, draft kept, no overwrite | Two independent contributors | Real persisted Setup Guide, two Chromium sessions | Server | `Authenticated Server revision conflict 409` (409 observed, banner, draft in `localStorage`, authoritative revision kept) | Mutation probe *silent revision conflict* | `server-revision-conflict-1366.png` | VERIFIED |
| 15 | Run edit ownership: hijack refused, separate Run allowed | Contributor | — | Server | — | — | — | **BLOCKED** (#124) — backend ownership rules exist; the browser journey does not |
| 16 | Editorial recommendations linked to evidence; a failed Run never auto-positive | Contributor, Engineer | Demo recommendations including a failed Run | Demo + Server | `Standalone Demo workgroup 1366`, `Standalone Demo engineer 1366` | — | `demo-engineer-1366.png` | **PARTIAL** — the recommendation/failed-Run editorial rule needs seeded Server data (#125) |
| 17 | Management lands on authorized aggregates and opens sourced results | Planner | Demo heatmap; empty Server planning data | Demo + Server | `Standalone Demo management 1366` (as-of Inspector), `Authenticated Server management 1366`, `Authenticated Server authorization fail-closed` | Non-planner roles refused (`planning_view` 403, no management screen) | `demo-management-inspector-1366.png`, `server-management-planning-1366.png` | **PARTIAL** — a populated DAP drill-down needs seeded Server opportunity data (#125) |
| 18 | Maintenance-only identity: authorized health only | Maintainer | Maintenance fixture plus a reader on the same route | Server | `Authenticated Server maintenance 1366` (audit + health), reader denied | `assert_location_fail_closed` for `/?…section=guides` and `/maintenance` | `server-maintenance-health-1366.png` | VERIFIED |
| 19 | Demo/Server isolation: no shared cache, no outage fallback | Contributor, Engineer | Offline Demo seed, real session, aborted API traffic | Demo + Server | Zero Demo API calls; `Authenticated Server offline isolation`; draft mode/account isolation | An offline Server must render no business record and no Demo fixture text | `server-offline-1366.png`, `demo-draft-contract-1366.png` | VERIFIED |
| 20 | Keyboard/AT traversal of nodes, counts, steppers, breadcrumbs | All fixtures | Real Chromium desktop sessions | Demo + Server | `assert_accessible` on every rendered view; `assert_dialog_focus` (trap, Escape, focus return) | Mutation probes *overflow*, *stacked workspaces*, *focus containment* | `mutation-fixtures.png`, per-view screenshots | VERIFIED (desktop keyboard/AT semantics; **not** a screen-reader narration session) |

## Modal and cross-cutting requirements

| ID | Requirement | Checks | Evidence | Status |
| --- | --- | --- | --- | --- |
| NFR-UX-001 | A form dialog stays open on backdrop click and Escape and never loses unsaved fields | Mutation probe *backdrop discards draft*; Demo and Server editor journeys | `demo-shared-guide-form-1366.png`, `server-shared-guide-form-1366.png` | VERIFIED |
| NFR-UX-002 | Every dialog exposes an accessible close control and returns focus to its invoker | Mutation probes *missing modal*, *focus containment*, *focus is not returned*; Server Guide editor | `server-shared-guide-form-1366.png` | VERIFIED |
| NFR-A11Y-01 | Semantic headings, labelled controls, one main landmark and exactly one current location per view | `assert_accessible` across all four workspaces and both modes | report `accessibility_findings` | VERIFIED |
| NFR-ERR-01 | No uncaught JavaScript exception and no unexpected HTTP failure during a journey | `PageWatch` on every journey | report `checks[].details` | VERIFIED |

## Negative controls (the gate must be able to fail)

`Mutation probes (deliberate UI defects rejected)` injects representative regressions and requires the matching assertion to fail: stacked workspaces, an unauthorized surface rendered for the wrong role, a missing modal, a backdrop that discards a draft, an untrapped dialog, a lost focus return, a broken return path, page-level horizontal overflow, a silently swallowed 409 and an uncaptured JavaScript exception.

The same check names are reused by the coverage registry, so a weakened assertion fails the scenario it was supposed to prove.

## Defects found and fixed by this gate

| Finding | Evidence before the fix | Fix |
| --- | --- | --- |
| The workspace switcher claimed `aria-current="page"` while the sidebar also did, so a view announced **two** current pages | `assert_accessible` counted 2 current entries on every Server landing | `shared-runtime.js` uses `aria-current="true"` for the switcher; `shared-shell.css` keeps the same highlight |
| An unpermitted route stayed in the breadcrumb while another view was rendered (Engineer + `section=planning`) | `assert_location_fail_closed` | `server-mode.js` normalises the announced location to the screen actually rendered |
| Server workspaces had no page-level heading (Engineer/Management/Maintenance started at `h2`) | Accessibility audit `no_h1` | the shell exposes the current location as the single `h1` in Server mode, with the topbar look unchanged |
| 21 Demo filter controls plus the resource-meters field had no accessible name (placeholder-only inputs, unlabelled selects) | Accessibility audit `controls_without_name` | explicit `aria-label` on every Demo filter and on the budget meters field |
| The Demo sidebar exposed no current-location state | Audit counted 0 `aria-current` | the active Demo navigation entry now carries `aria-current="page"` |
| The Demo workspace switcher was a bare link instead of the shared pill switcher | Screenshot comparison Demo vs Server | `shared-shell.css` styles the Demo switcher with the shared tokens |
| `server-discussions.js` requested `/api/v1/auth/account`, which does not exist, so the Server Feedback view failed with 404 while the unit test mocked the wrong path | `NFR-ERR-01` network capture | switched to `/api/v1/auth/me`; the test now asserts the real path |
| `shared-pricing.js` requested `/api/v1/catalog/model`, which the catalog router rejects (`/api/v1/models` is the real collection) | `NFR-ERR-01` network capture | the shared adapter maps `model` → `/api/v1/models`; the pricing test asserts both paths |
| The 409 conflict banner was unreachable: controllers built errors without the HTTP status, so the draft engine's text match never fired | `Authenticated Server revision conflict 409` | `AICompassRuntime.requestError` keeps the status taxonomy; Guides/Watch/Forecasts/Test Cases attach the status and test `error.status === 409` |

## Handed over, not fixed here

| Finding | Why it is not fixed in #126 |
| --- | --- |
| `server-sessions.js` still calls `/api/v1/catalog/model` (404), so the tariff trio cannot load | The Run/session stepper is the UX-R05 [#124](https://github.com/aradenac/AI-Compass/issues/124) deliverable; changing it here would collide with that rewrite. Same one-line pattern as the `shared-pricing.js` fix. |
| Every Server domain controller keeps its own `fetch` wrapper (duplicated CSRF/status/error handling) | Registered as **TD-10**; consolidating it belongs to shared-runtime work, not to a verification gate. |
| Heading-level skips in legacy Demo card lists (Campaigns, Results, Guides, Feedback) and Demo details without an `h1` | Recorded per run in `report.md` → `accessibility_findings`; correcting legacy Demo typography belongs to the converging business layer (#123/#125). |

## Open risks / what would change this table

- **#123–#125 are still in flight.** Scenarios 2, 4, 5, 6, 11, 12, 15, 16 and 17 stay PARTIAL/BLOCKED until their owning implementation lands *and* is exercised here. A merged implementation is not a verified journey.
- **Seeded Server domain data.** Positive Server journeys (measured Run, feedback linkage, DAP drill-down, editorial recommendation rule) need isolated synthetic published records. This gate creates only Guides, Watch entries, Tasks and Test Cases; inventing measured evidence was deliberately avoided.
- **Not covered by automation.** Contrast ratios, screen-reader narration quality, human visual approval of screenshots, and real staging/operator acceptance.
- **Steppers.** §13-12 and part of §13-20 concern steppers; stepper traversal is asserted by #124, while the keyboard/AT semantics of the shared shell are asserted here.
