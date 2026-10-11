# FUT-09 — Tariff-driven measured Runs (Server and standalone Demo)

## Experimental and commercial boundaries

A **Run** is an immutable measured attempt at exactly one campaign-revision and Test Case revision, using exact component/participant/Framework and Setup Guide revisions. A failed Definition of Done (DoD) is valid **negative** evidence when the measurement is complete; it never becomes a successful solution. Multiple Run attempts retain distinct identities, checkpoint history and immutable evidence. Campaign Matrix selection/waivers and publication membership are independent of completion; FUT-10 owns eligibility to publish a selected completed subset.

Existing `legacy_unclassified` Server sessions and old Demo records continue to accept their original `cost_mode=amount|flat_rate|unknown` and original total-token fields. **No historical Run is backfilled with invented split tokens, supplier rates or cost.**

New `offer_revisions_v1` sessions instead use the explicitly selected and immutable `PricingOffer` revisions:

1. Choose Model/Provider/Harness and, where applicable, Framework participant/source tariffs. Before starting the affected Session, a missing, unknown, expired/invalid or unsupported conditional selected offer **blocks only this Run** (not drafting the Campaign or publication of independently eligible completed Runs). The tariff's effective-date check is recorded against the Session start date, not a later closure date.
2. The Session's `metering.schema.required_meters` derives all and only required meter inputs from the actual selected offer line(s): input/output/cached/reasoning tokens, provider-namespaced credits, requests, time, executions, GPU-hours, etc. No irrelevant consumption forms for wholly fixed/free plans. Multiple cumulative charges consuming the *same* source and meter reference the same observation; they each price their genuine independent charge. Source-specific invoice/charge identities are checked at offer selection to prevent duplicate Model/Provider gateway billing.
3. Record Test Case setup, original rendered guide, actual environment/deviations, chronological human and agent interaction durations, evidence and produced artifacts. **Save meter observations and preliminary result/DoD independently** through the two new checkpoint endpoints. Empty means **missing**, explicitly recorded `0` means **measured zero**. An incomplete set of required meter values returns 409 on close but does not delete the saved partial work.
4. Once every required meter is known, closing uses server-side `Decimal` calculations and the **original offer revisions**. It persists a cost breakdown, the exact source/charge/revision/meter values, rate unit sizes and currency subtotals in `metrics.reference_cost`, alongside legacy numeric metrics for compatible old consumers. Fixed subscriptions/seats are listed separately but never allocated to a variable Run. Shared quotas, prepaid wallets and credits **do not** reduce reference usage cost. The result is labeled *variable reference cost*, **not an invoice**.
5. A composite Framework Session sums separately chargeable participant and orchestrator sources into **one global workflow cost**. Individual participant information and per-interaction actor IDs remain pinned and auditable; neither the composite cost nor its DoD/quality is automatically credited to an individual measured AI Solution. Sessions involving a single Framework participant use the existing individual-Run semantics.

### Cost calculation

For a flat variable line:

```
observed_meter_quantity / native_unit_size × unit_rate
```

For a progressive tier, split the **current Run's** native observed quantity into its explicitly declared brackets; multiply each bracket's consumed units by its unit rate divided by `unit_size`. Do not use global supplier quota, enterprise aggregation or assumed remaining prepaid balance to choose a tier. A quantity exceeding all declared tiers remains pending rather than silently assuming a missing rate.

Calculations preserve exact decimal string amounts in their immutable source/currency breakdown. The existing `cost_eur` compatibility field is automatically populated **only when the total variable reference cost is denominated unambiguously in EUR**. Mixed or non-EUR amounts remain native currency totals in `reference_cost.variable_reference_by_currency` with `cost_eur=null`, and must not be mistaken for EUR zero. No automatic FX conversion. Any subscription or framework license is separate from Run-level usage.

## Authenticated Server API

| Path | Action | Contract |
| --- | --- | --- |
| `GET /api/v1/sessions/<id>` | Read | Includes frozen `pricing_selections`, original source, required meters and `metering.{ready,missing,quote}` |
| `PATCH /api/v1/sessions/<id>/metering` | Save observed counters | `{"expected_revision":"rNNN","consumption":{"root:model":{"input_tokens":"1000000"}}}`; permits partial saves and clearing a meter using explicit `null` |
| `PATCH /api/v1/sessions/<id>/results` | Save incomplete DoD/outcome, scores, output/evidence | Validates bounded drafts, independent of consumption completeness |
| `POST /api/v1/sessions/<id>/close` | Finalize immutable Run | `{"expected_revision":"rNNN"}` uses last saved results and metering for tariff-priced sessions; optionally supplies the remaining result fields. Manual amount override is forbidden |
| `GET /api/v1/runs/<id>` | Read | Historical immutable Run, `metrics.reference_cost`, exact provenance and frozen checkpoint |

Changes use CSRF, `business_write`, session ownership and optimistic revision checks. 403 means insufficient permission; 409 means concurrent checkpoint or missing required metering; malformed quantities/sources and attempts to override computed costs are rejected. Only selected matrix evaluation IDs can start matrix Runs; the matrix's original pinned technical trio/participants and Test Case revision are not silently replaced. Repeated attempts are distinct Sessions.

## Standalone Demo

The browser-local fake environment has a **fictional reference offer** embedded at initial Trial setup (`rNNN`, ISO currency and declared `lines`) that the operator may adapt or omit to preserve old manual-cost behavior. Once the Trial starts, its offer and guide are copied into the mock Session. The Step 5 result form derives consumption fields from that pinned fictional offer, computes free/fixed/variable/tier charges and persists unresolved meters and preliminary results without finalizing. Composite trials carry the overall workflow price only; no conversion to an individual measured Solution. This is **not** live vendor pricing and never imports business data from Server.

## Migration, rollout and recovery

No new relational schema/migration is necessary: optional `metering`, `results_draft` and `reference_cost` reside in existing immutable SessionCheckpoint / BenchmarkRun / CompositeBenchmarkRun JSON. Pre-existing DB constraints and revision/restore protections remain; rollout is additive. Reverting the application will keep the prior persisted JSON bytes intact but older code will not interpret them: do not complete partially metered Sessions using a legacy server binary; restore the compatible coordinated application version and recovery artifacts before continuation. Original snapshots are never overwritten or republished by tariff updates.

**CI:** PostgreSQL integration: `python manage.py test config.test_run_cost config.test_pricing config.test_campaign_matrix config.test_sessions config.test_runs config.test_composite_runs`. Offline Demo/UI: `node scripts/test-run-cost.js`, plus existing `test-server-composite-runs.js` and the release readiness suite. Production remains **NO-GO** until human deployment/recovery gates and explicit operator approval, regardless of CI outcome.
