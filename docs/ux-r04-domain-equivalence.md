# UX-R04 — Demo/Server business presentation convergence evidence

**Scope:** desktop browser only (1366×900 reference). **Status:** partial, open under [issue #123](https://github.com/aradenac/AI-Compass/issues/123). This document distinguishes source-level reuse from proven end-to-end behavioral equivalence. **Do not close or merge issue #123 solely from this matrix.**

## Live domain and permission inventory

| Domain | Shared browser presentation | Demo data/actions | Server data/actions | Remaining divergence / acceptance |
| --- | --- | --- | --- | --- |
| Navigation & modal frame | `shared-shell.js`, `shared-context.js`, CSS | Local Demo persona and draft | Real Django identity, CSRF, RBAC | Existing real-browser smoke is not a complete role/negative matrix |
| Technology Catalog | `shared-catalog.js` full Catalog presenter | Local synthetic catalog; immutable Demo revisions | Versioned Server API; permission-checked edits | Validate source parity and historical errors across both modes |
| Tasks | `server-tasks.js` mounted in both, distinct domain providers | Offline fake tasks + local revisions | Authorized API + optimistic revision | Validate drag/drop parity vs Server move, stale-revision and missing grant |
| Test Cases | `AICompassWorkgroup.renderCases`, `renderCaseFields`, `renderCaseDetail` | All six challenge fields with local persistence, custom modal save/fork; fictional Demo runs | All six fields, authorized edit/fork, revision/evidence API | Form actions/validation still separate; browser create/inspect exercised in both modes, but fork/evidence and denial round trips not exhaustive |
| Campaigns and Matrix | `renderRecords` for authorized Campaign lists | Demo campaign lifecycle, matrix and run workflows | Server campaign workflow, pinned real methods, publication | Matrix/Run editor and session controllers remain mode-specific, not unified; compare lifecycle and action parity |
| Results and evaluations | `renderRecords` for measured Run/evaluation lists | Offline published Run card + comparison matrix | Authorized measured/theoretical matrix, revisions, correction | Comparison components and detail UX still divergent; no fabricated scores allowed |
| Guides and Charter | `renderRecords` for lists | Demo articles, modals and publication | Reusable revisioned Setup Guide and recipe editor | Guide title, text, URL, description and current-detail use shared components. Demo local save and Server authorized persisted save/reload are covered in Chromium; recipe editing, publication and pinned historical access still mode-specific. |
| Watch, research sources, forecasts | `renderRecords` for Watch and theoretical forecast lists | Fictional Watch/forecast/source workflows | Authenticated sources, Watch entries, forecasts + reviews | Watch/source/Forecast current summaries now reuse a text-only provenance-aware detail component. Chromium exercises Demo Watch/Forecast and real Server Watch create/reload/history; research sources and all specialized editor/review actions remain mode-specific. Forecasts never become measured Runs. |
| Feedback & discussions | `renderRecords` for thread lists | Local contribution/thread workflow | Real messages and visibility/revision APIs | Thread detail/reply/visibility actions remain distinct; negative role tests incomplete |
| Recommendations | `renderRecords` for list and historical flags | Demo solution guidance and local review | Run-grounded controlled recommendations, publication and review freshness | Business semantics and revision editors still divergent; do not infer evidence |
| Engineer | `shared-engineer.js` mode-provider + common DOM | Published fictional solutions and feedback | Published authorized Server records | Validate Task-first/By-Tool and unsupported/empty histories |
| Management | `shared-opportunity-heatmap.js` mode-provider + common DOM | Synthetic economics | Authenticated planning/heatmap | Validate scoped source evidence and impact factors |
| Users/maintenance/governance | Intentionally Server-only controlled workspaces | No privileged local equivalent | Separate authenticated permissions and audit | Not a Demo business duplicate; verify denied actions, original evidence and isolation |

## Shared record component contract

`AICompassWorkgroup.renderRecords(records, {domain, mode})` provides one escaped card/metadata/action/link DOM across Demo and Server. Callers **must** pass explicitly authorized rows, labels, untrusted values as plain text, and only action attributes delegated by their original permission-aware controller. Links are restricted to relative same-origin routes; never silently convert an API failure into Demo content. The component deliberately knows nothing about source data or write authorization.

This converges **record-list presentation, not full business forms or lifecycle controllers**. No unsupported Server action is mocked. Specialized matrix, Run, historical-evidence and maintenance panels remain independently implemented until actual behavior and source parity are proven.

## Verification crosswalk

- JavaScript unit checks: `node scripts/test-shared-case-tree.js`, `node scripts/test-workgroup-studio.js`, existing Server controller suites, `node scripts/test-shared-frontend.js`. Shared component tests assert hostile-text escaping, wrong mode, non-privileged actions, fork cycles and same-origin link rejection.
- Real browser: `python scripts/ux_qa.py provision --output /tmp/ux-qa-credentials.json` on a disposable composed Server, followed by `python scripts/ux_qa.py test --base-url http://127.0.0.1:8080 --demo-url http://127.0.0.1:8090/prototype.html --credentials /tmp/ux-qa-credentials.json --artifacts /tmp/ux-qa`. The suite now checks shared Demo domain cards, complete Test Case field persistence, real empty Server domain presentations and a real authorized Server Task → Test Case creation/reload, plus previously covered modal/role/context journeys.
- **Not yet proof:** equivalent writable flows/negative API cases in every domain, historical revision pin errors, exact modal focus restoration and 1366×900 screenshot approval by reviewer. Until those are demonstrated, no claim of complete UX-R04 acceptance, TD-01 closure, production staging GO or safe resumption of P7.

Existing Django integrity, revision, CSRF/RBAC, migration and recovery CI are independent mandatory gates. Mobile/tablet acceptance and enforcing branch-rule TD-UI-01 remain deliberately out of scope.
