# FUT-16 — Pilot, rollout and active-capacity resource budgets

## Purpose and entrypoints

The separate **Budget & Resource Planning** panel in Demo and the Server planning workspace is *decision support*. It neither provisions external entitlements nor purchases licenses, rotates credentials, renews subscriptions or debits a wallet. All Server writes require `planning_manage`; reads, frozen revisions and JSON request-summary exports require `planning_view`. No individual names, per-person rates or access-event references are exported. No-cache headers and CSRF apply.

Server endpoints:
- `GET /api/v1/planning/budgets/options`: authorized populations, published measured/Forecast candidates, deliberately selected measured targets and selectable pricing offer revisions.
- `POST /api/v1/planning/budgets/preview`: no-write estimate, including gaps.
- `GET, POST /api/v1/planning/budgets`: bounded list, new immutable budget.
- `GET, PATCH /api/v1/planning/budgets/<id>`: original projection and read-time current projection; optimistic `expected_revision`.
- `GET /api/v1/planning/budgets/<id>/revisions[/<number>]`: frozen, attributable versions.
- `GET /api/v1/planning/budgets/<id>/export`: aggregate, source-referenced JSON for review.

## Minimal request

```json
{
  "profile_id": "wlp-your-existing-profile",
  "plan": {
    "name": "Q4 pilot capacity",
    "start_date": "2026-10-11",
    "period_months": 3,
    "margin_pct": "10",
    "include_active": false,
    "items": [
      {
        "purpose": "pilot",
        "task_id": "tsk-existing-task",
        "candidate_id": "fct-published-forecast",
        "pilot_headcount": 2,
        "offer_pins": [],
        "meter_overrides": {}
      }
    ]
  }
}
```

Rollout items instead use `{"purpose":"rollout","target_id":"dpt-existing-selected-target"}`. The pilot requires a published theoretical Forecast; rollout requires an explicitly selected measured DeploymentTarget. Pricing is pinned by offer ID and immutable revision UUID with `source_key` (e.g. `root:provider`). All other applicable billable elements must have an explicit offer, including the free alternative; missing offers produce an **incomplete estimate**, never an implicit zero. Optional source/meter-specific assumptions are qualified inputs, not observed usage, and are checked against selected tariff meters.

## Calculation and evidence rules

1. Resolve DAP-01 effective, versioned annual Task workload; never add inherited overrides twice or automatically aggregate parent+child Task occurrences. The period uses stated **uniform monthly distribution assumption** and an explicit nonnegative capacity margin. Same Task cannot be selected twice.
2. Pilot scales the selected Forecast cohort; a money-saving estimate or total token count **cannot** be silently split into provider-specific input/output/credit meters. The optional qualified meter fields are used only if matched to a pinned offer. Otherwise the budget marks exact meter quantities **unknown**.
3. Rollout is for currently **not external-access-ready** people. Optional active capacity separately serves those with **verified entitlements, setup and confirmed first use**; people already access-ready but not yet first-used are excluded from both until clarified. These current eligibility quantities are recalculated when the budget is read; historical requests are never rewritten.
4. Meter rates and progressive tiers reuse the FUT-09 pricing contract (`run_cost_services._tiers`); the measured source is actual source-keyed observations from accepted published comparable Runs and **original exact selected tariff revisions**. Incomparable Run methodologies/offers are rejected, not averaged. Provider credit namespaces are kept distinct. No new FX rates, pooled-wallet allowances, token ratio or quota units are invented.
5. Variable quantities for the same owner, offer revision and charge line aggregate across distinct Tasks *before* applying volume tiers. Fixed monthly, annual or one-off charges are displayed independently; seats are deduplicated for the same Task across disjoint rollout and active populations, and pooled by maximum required seat count between Tasks under the same population. If two different source revisions claim the same vendor invoice, an explicit ambiguity gap appears. **No inferred overlap of separate organizations**: each plan is for one WorkloadProfile.
6. Frozen `BudgetRevision` captures the request inputs, pinned source/version IDs, original approximate measured units, effective population and projected native-currency totals. New current sources produce a separate read-time comparison and a new explicit revision only on planner PATCH.
7. Missing pricing, obsolete tariffs, unmeasured required meters and qualified assumptions are visible as gaps; `ready_for_request=false` means no complete monetary commitment can be claimed. No personal hourly valuation rate is exported, and no employee-level entitlement event is included.

## Operation and rollback

Migration `0028_resource_budgets` is additive: permanent `bdg-*` IDs, protected FKs, append-only historical revisions and PostgreSQL triggers disallow update/delete. Standard coordinated backup/restore and staged migration NO-GO procedures remain authoritative. Roll back application code first using the staged release procedure, retaining data; reverting the schema migration destroys budget records and is **not a normal rollback strategy**. Run `python manage.py test config.test_budgets` (within disposable Server) and `node scripts/test-shared-budgets.js`. Demo stores only fictional `db.demoResourceBudgets` in its separate local DB; it never reads/writes Server business records.

**Limits:** reference forecasts are not actual invoice rates or spend; commercially conditional or negotiated lines remain unresolved instead of being guessed. Do not promote a release without the repository's independent platform release and restoration gates.
