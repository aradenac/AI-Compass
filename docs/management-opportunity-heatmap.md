# FUT-14 — Task × AI configuration opportunity heatmap and Management Insights

**Implementation:** shared `shared-opportunity-heatmap.js` in both authenticated
Server Management and independent fictional Demo Management. One
`opportunity_insights_services.py` projection wraps the **existing FUT-13
`opportunity_services.project`** source of economic truth; **no new DB model,
new financial formula, silent personnel assumption or migration**.

## Primary Task × AI configuration heatmap

- **Rows:** versioned Task taxonomy, depth-first ordered; hierarchy navigation
  with collapsible descendants. Task parents and children are **not summed**.
- **Columns:** measured `sol-*` solutions and theoretical `fct-*` Forecast
  candidates. Population (role, specialty, person, cohort) is an authorized
  **scope selector**, not a column or a synthetic organizational hierarchy.
- **Window:** server-side pagination of up to **16 taxonomy rows × 12 candidate
  columns** (UI defaults to **8 × 8**) with bounded candidate/source selection,
  explicit next/previous controls, sticky Task column and horizontal scrolling.
  No mega-DOM for unrelated combinations; no unbounded per-request full-grid
  rendering. Items with no actual Task→candidate evidence have **empty cells**.
- **Cell numeric background:** same fixed EUR/year bands across every page,
  never relative to the current viewport: [0–999], [1,000–9,999],
  [10,000–99,999], [100,000+]. Color is **only** a positive monetary
  opportunity. Zero and negative figures remain **unshaded**, with numeric
  label; unknown/inapplicable is **unshaded and marked ?**. Single evidence
  maturity character denotes **B** accepted measured, **F** published
  theoretical, **?** insufficient evidence. A chosen scenario cell is visually
  outlined; this does **not** alter its evidence maturity.
- **Unselected alternatives:** each cell is calculated with the same FUT-13
  formula as a one-choice *hypothetical comparison*, never summed into the
  active portfolio and never treated as selected/deployed/approved. Its
  benchmark weight is immaterial unless a linked Forecast is **explicitly**
  chosen in a saved scenario. No numeric "quality rating" is invented.
- **Period:** authoritative annual EUR. Monthly/quarterly/seasonal values
  are *not inferred* without explicit distribution sources.
- **Selection:** only an immutable saved FUT-13 scenario revision contributes
  to the portfolio and its three mutually exclusive slices. To change the
  population or selected candidate and create a new dated revision, use the
  existing Annual Opportunity Scenarios editor.

## Management entry and common projections

`?mode=server&workspace=management` mounts Management Insights before the
existing protected workload/scenario planning panel. It is **not a duplicate
stored financial truth**. All live values are delivered by
`/api/v1/planning/insights` and `/api/v1/planning/heatmap`, both explicitly
scoped to the same `profile_id` and optionally `scenario_id`. The three
FUT-13 slices and total are identical to the scenario's
`GET /planning/opportunities/{id}` current projection. The cumulative bar
and percentages apply only to the chosen portfolio, not all comparative
cells. Until trusted FUT-15 entitlement and first-use evidence exists,
**Activated Potential is zero**; no click in Management provisions access.

Each stored `OpportunitySnapshot` contributes one *immutable, dated point*
to the scenario historical series. Points show annualized total, all three
stacked portions, difference to the previous saved point and **possible**
change categories (scenario choice/weight, workload revision, source Run
correction/withdrawal, Forecast source availability, modeled distribution
change). Historical plotting supports stacked columns or individual SVG
curves with an accessible date/value table. A click on a date selects its
actual original revision and narrows the matrix to originally selected
candidates only: it must never reassign today's Forecast/Run to a past cell.

Current projections are explicitly labelled fresh read-time values and
compared to saved values using FUT-13 `source_changed`; they do not
secretly append historical records. **Snapshot cadence = explicit scenario
save/revise**. No arbitrary daily automatic snapshot or backdating is
performed. This is auditable, and avoids manufacturing historical events.

The suggestions pane orders *currently published source-supported
alternatives* using the descriptive policy
`descriptive_evidence_maturity_then_annual_economic_potential_v1`.
There is **no validated global performance-ranking method** in v1.
Theoretical predictions, unquantifiable and negative alternatives are
labelled distinctly. Suggestions do not create Campaigns, deployment
targets, access requests, rankings, AI-approved suitability or purchased
licenses.

## Progressive Evidence & Calculation Explorer

A matrix cell click shows a summary, not a dense graph. A selected portfolio
cell opens branches one by one:
1. Original FUT-13 algorithm, formula, blend assumptions and annual money.
2. DAP-01 versioned effective workload source, role/specialty/override lineage.
3. Original measured Test Case/Run IDs, correction revisions and method pins.
4. Published theoretical Forecast ID and exact revision (including its
   public source eligibility checks inherited from FUT-13).
5. Recorded marginal EUR cost as an **historical reference**, explicitly not
   a current live supplier quotation.
6. Activation/entitlement boundary (unverified until FUT-15).

The individual branch expands on demand, with breadcrumbs and a Back action.
Historical links resolve the **stored original source revision references**;
withdrawal affects *current* values immediately but never edits prior
snapshots. An unselected comparison cannot claim to have historical
provenance in the saved scenario, so its inspector guides the planner to
the scenario editor instead of exposing guessed source ancestry.

## Privacy and operational controls

Every Management API requires the Django `auth.planning_view` grant and an
explicit authorized DAP-01 population ID. The frontend persona is **not**
a security boundary. Permission failure or Server outage never falls back to
Demo data. Unexpected query parameters, unsupported periods, invalid
pagination, mismatched profile/scenario and inaccessible source revision
are rejected before any private data are returned.

Management projection, history and provenance payloads redact valuation
rates, individual frequencies, baseline/assisted time, private workforce
profile attributes, individual headcount and linked account identifiers
from tooltips, chart data and inspector exports. They retain exact source
revision IDs and an explicit restricted-input marker. The underlying
**separate protected DAP-01 planning API** still owns detailed authorized
auditing of its workforce input records. This release does not expose
planning values through public Engineer, Workgroup, Technology Watch or
catalog search routes. API responses are no-store.

A request computes only its requested bounded matrix window; no persistent
read-model cache to become stale or leak across populations, no tracked
navigation analytics. Scaling beyond the explicit candidate bounds requires
a future versioned precomputed read model with invalidation and privacy
controls; the implementation fails explicitly rather than returning
partial, falsely complete rankings.

## API

All requests are **GET**, authenticated, cache-disabled and scoped:
- `/api/v1/planning/heatmap?profile_id=wlp-...&scenario_id=opp-...&row_page=0&column_page=0&row_size=8&column_size=8&period=annual`
- `/api/v1/planning/insights?profile_id=wlp-...&scenario_id=opp-...`
- `/api/v1/planning/insights?profile_id=wlp-...&scenario_id=opp-...&revision=r001`
- `/api/v1/planning/insights/explain?profile_id=wlp-...&scenario_id=opp-...&task_id=tsk-...&kind=benchmark&candidate_id=sol-...&revision=r001`
- `/api/v1/planning/insights/suggestions?profile_id=wlp-...&limit=40`

There are no write endpoints, additional databases or new migrations for
FUT-14. Historical records remain protected by the FUT-13 PostgreSQL
immutable triggers and native backup/restore pipeline. Rollback consists of
removing read-only API/frontend mounts; it does not touch the scenario
histories or existing evidence.

## Acceptance and deployment

Focused commands, on disposable PostgreSQL and Node:

```sh
docker compose exec -T api python manage.py test config.test_opportunity_insights -v 2
node scripts/test-shared-opportunity-heatmap.js
```

The existing FUT-13, FUT-12, FUT-11 and full PLAT-32 pipeline must remain
green, including independent Demo/Server behavior, authorized user models,
migration check, isolated archive restore, staged reversible migration and
release manifest production. Production GO still requires the usual
independent operator readiness gates. No external input from the user is
required; synthetic values belong only to Demo and test fixtures.
