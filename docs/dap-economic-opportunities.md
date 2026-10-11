# FUT-13 — Annual economic opportunity scenarios (DAP-02)

This extension uses the **existing** DAP-01 versioned WorkloadProfile (role,
specialty, person, cohort and inheritance). It adds versioned immutable
selection/calculation snapshots, NOT a second workforce/price profile.

## What the figures mean

For one selected Task × configuration alternative in one explicit population:

```
per_occurrence = (baseline_human_hours - expected_assisted_human_hours)
                 * labor_valuation_eur_per_hour - variable_AI_cost_eur
annual_potential = per_occurrence * annual_occurrences_per_person * headcount
```

All output is **estimated labor-value capacity / prospective annual potential,
not cash savings realized, profit, salaries, or a promise of operational
qualification**. A negative per-occurrence value is retained as a negative
reference gain, and excluded from the explicitly named
`positive_modeled_total_eur`. Unknown inputs are `null`/unquantifiable,
never zero. Period: 12-month annual projection; currency: EUR only, **no FX
conversion**.

A scenario must explicitly select **one alternative per Task**. Parent and
descendant Task workloads that overlap are blocked from numerical accumulation
without confirmed non-overlapping quantities. Role/specialty inheritance is
resolved by the existing DAP service; competing contradictory templates are
unquantifiable until explicitly overridden. An individual candidate's value
is only an alternative comparison, not independently additive enterprise gain.

The current experimental interpretation method remains
`descriptive_only`; **this economic opportunity calculation is not a new
performance ranking**. Only **current effective published individual Runs**
support measured opportunities. Failed-only/contradictory DoD, missing
human-time or marginal EUR cost, withdrawn and unpublished runs, mixed
experimental methods / non-identical Test Cases are ineligible. For
multiple comparable accepted published Runs of the same Test Case + frozen
method, v1 averages measured human time and declared marginal EUR cost,
exposing the entire exact input Run/revision set and sample size.
The Run's pinned **reference marginal cost** remains a historical price
assumption for prospective calculation, not an assertion that its tariff is
still today's active contract. A fixed subscription cannot silently be
turned into zero marginal usage: historical `cost_eur=null` is unquantifiable
without a validated applicable variable-cost reference. Fixed/seat/licensing
fees remain separate future budget inputs.

Forecasts are distinct **theoretical** candidates, not measured solutions.
Only the currently published version can contribute. Forecast quantification
requires a stated assisted `human_minutes`, predicted `ai_cost_eur`,
and `acceptance_probability`. When probability is less than 100%,
`assumptions.failure_recovery_human_minutes` is also required:
failed cases consume baseline time plus that declared recovery time, as well
as the stated reference usage cost. Without these inputs the money field is
unknown. Confidence, uncertainty and source revisions remain visible.

For an **explicitly linked** Forecast+Benchmark comparison, v1 weights the
average effort and marginal cost only if Task, pinned model/provider/harness
revisions and configuration settings match *exactly*, all selected measured
observations are accepted/comparable, and the theoretical estimate is complete.
A per-scenario **explicit** `benchmark_weight` between 0.5 and 1, exclusive,
is stored immutably; the remaining weight applies to Forecast. No hidden 80/20
default or optimistic theory overriding failed measured evidence.

## Three disjoint annual slices

- **Activated Potential:** only a subset of people with independently verified
  entitlement *and* confirmed first use.
- **Benchmarked Opportunity:** non-activated occurrences assigned to the
  selected measured candidate; an accepted comparable Forecast, if linked,
  may influence its estimate, **not** create an additional Forecast slice.
- **Forecast Opportunity:** non-activated occurrences assigned to the selected
  theoretical-only candidate, with no benchmark credit.

The allocation formula is tested for partial populations (6 activated / 4
unactivated out of 10), always totals each occurrence **once**, and never
transfers negative value into a positive opportunity. **Important actual
deployment boundary:** FUT-15 (#89) owns verification of real component
entitlements and first use. It is not implemented yet. Therefore FUT-13
currently passes **zero verified activations** to this partitioner and the
live Activated Potential is always zero, not a manually togglable badge.
The pure allocation function accepts future trusted, source-backed
activation counts for independently tested partial deployments. No current
scenario request can supply a fictional count or claim production access.
Deployed scenarios become possible after FUT-15's verified source is
integrated; the contract and missing capability are intentionally explicit.

## Privileged API

All routes below require `auth.planning_view`; mutations also require
`auth.planning_manage` and CSRF. A normal Engineer, Workgroup contributor,
Data Maintainer or User Administrator does not inherit these rights.

- `GET /api/v1/planning/opportunities/candidates` — current published
  Task/measured and Task/theoretical candidates, not a ranking or grant.
- `POST /api/v1/planning/opportunities/preview` — current what-if
  calculation, no records written.
- `GET|POST /api/v1/planning/opportunities` — list/create immutable scenario.
- `GET|PATCH /api/v1/planning/opportunities/{opp-id}` — load stored snapshot,
  live source-recomputed projection and `source_changed`; revise a scenario
  with exact `expected_revision` for optimistic concurrency.
- `GET /api/v1/planning/opportunities/{opp-id}/revisions` and
  `/revisions/{number}` — immutable original values and source provenance.

Sample preview body:

```json
{
  "profile_id": "wlp-<existing-public-id>",
  "scenario": {
    "name": "Embedded role — illustrative annual opportunity",
    "benchmark_weight": "0.8",
    "choices": [
      {"task_id": "tsk-<existing>", "kind": "benchmark",
       "candidate_id": "sol-<published-measured>"},
      {"task_id": "tsk-<different-existing>", "kind": "forecast",
       "candidate_id": "fct-<published-theoretical>"}
    ]
  }
}
```

The id placeholders are **not actual Server IDs**. A measured choice can
include `forecast_id` only when intentionally requesting a strictly
comparable blended estimate. Choosing one alternative per Task prevents
summing competitors as separate gains. Privacy is enforced by API permission,
never inferred from a frontend persona switch. Protected outputs including
cohort headcount, specific rates, effective workload source and historical
source assumptions must not be cached or passed to public activity/Engineer
dashboards.

## History, source invalidation and safety

The additive `OpportunityScenario` table stores permanent `opp-` identity
and a protected FK to the selected existing DAP profile. Each
`OpportunitySnapshot` stores the full selected assumptions, algorithm
identifier `dap-opportunity-v1`, frozen per-cell economic source refs +
values, actor and timestamp; PostgreSQL triggers reject UPDATE/DELETE.
All scenario writes append a new snapshot, with stale expected-revision
rejected. The current read recomputes directly from the authoritative
latest effective published membership and Run corrections; withdrawal removes
a source immediately (fail-closed, `unquantifiable`). Original snapshots
and the original Run/pricing assumptions are never rewritten.

**Data migration:** `0026_dap_opportunity.py` adds the two tables and
immutability triggers; rollback drops only the new scenario/snapshot tables
when intentionally rolling back *before* any real scenarios exist.
Database backups/restore and staging migration tests must run against
the new schema. Existing DAP-01 histories and benchmark evidence are
unchanged.

**Frontend:** `shared-opportunities.js` renders both server planning
and the **separate clearly fictional** Demo management example. The
Demo adapter uses synthetic fixed assumptions and fake local results;
the Server adapter uses only authenticated JSON endpoints and never
falls back to Demo. Neither mode copies data to the other.

## Verification and deferred ownership

Run `python manage.py test config.test_opportunities -v 2` on disposable
PostgreSQL and `node scripts/test-shared-opportunities.js`.
The regression suite must cover role boundaries, CSRF, one-candidate
allocation, negative/missing inputs, mathematical partial deployment,
Forecast and comparable blends, Run correction/withdrawal, pinned snapshots
and reproducible restore/release. Full GitHub CI is required before merging;
production readiness remains separately NO-GO until operational sign-off.

**Explicitly deferred to its already-open FUT-15 #89:** sourced verification
of user entitlements, first use, full configuration readiness, active usage
allocation, and replacement/upgrade incremental benefits. Until then,
Activated Potential is zero rather than an unsupported simulated count.
**Explicitly deferred to FUT-14 #88:** scalable profitability heatmap,
historical trend curves and Management Insights filtering; FUT-13 supplies
current/source-pinned values but does not pretend the full heatmap exists.
**Deferred FUT-16 #90:** exact forward active commercial tariffs, fixed
license commitments, metered capacity and resourcing budgets. This issue
does not auto-approve product purchase or treat a previous tariff as
guaranteed current supplier pricing.
