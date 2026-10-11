# AI Compass — Technology Accessibility & Pricing Management

> **Reference:** Product/domain specification maintained with the implemented application. The delivery tracker and outstanding UX acceptance work are maintained in the [implementation plan](future-evolutions/implementation-plan.md).

> **Status (2026-10-10):** Owner-approved specification, first implementation via [FUT-05 #79](https://github.com/aradenac/AI-Compass/issues/79). The actual usage-meter and automatic cost calculator remain FUT-09; this specification describes both and must not be read as a claim that FUT-09 is delivered.  
> **Discussion date:** 2026-10-10  
> **Areas:** Technology Catalog, Benchmark Workspace, Test Runs, Results Explorer, economic analyses.  
> **Related:** [Product Definition](product-definition.md) · [Technology Catalog Server](technology-catalog-server.md) · [Individual Benchmark Runs](individual-benchmark-runs-server.md) · [Benchmark Workflow](benchmark-workflow.md) · [Platform Architecture & Data Governance](platform-architecture-and-data-governance.md) · [Campaign Evaluation Matrix](campaign-evaluation-matrix.md)

## 1. Purpose and fixed decisions

Track the **enterprise-wide accessibility** and **commercial pricing** of every technology component — **Models, Providers, Harnesses and Frameworks** — and use explicit, versioned pricing selections to automatically calculate the variable cost of the tested AI configurations.

Separate these three concerns:

1. **Availability/accessibility:** whether the technology is actually accessible to enterprise users; public availability is not the same as enterprise authorization.
2. **Pricing:** what alternatives and cumulative charges a supplier makes available.
3. **Run cost attribution:** which offers the workgroup actually selected for a campaign configuration and what the measured consumption costs under those rules.

### Decisions confirmed in the discussion

| Topic | Agreed rule |
| --- | --- |
| Catalog coverage | Models, Providers, Harnesses, Frameworks; offer-level applicability may span combinations. |
| Accessibility | **One enterprise-wide status**, not per-BU statuses. |
| Free vs paid | Support free-only, paid-only, mixed free/paid, and unknown pricing as distinct catalog presentations. |
| Commercial diversity | Multiple alternative pricing offers per component; each offer can contain **multiple cumulative charges**. |
| Charging models | Free, token, provider-specific credit, other usage units, subscription, per-seat, tiered, hybrid, negotiated/unknown where applicable. |
| Campaign choice | **Manual, mandatory offer selection by a workgroup member** for each configuration's applicable billable elements. |
| Cost of a Test Run | **Calculated automatically from usage units and the selected tariffs**; no manual final cost as the normal route for new runs. |
| Missing/incomplete tariff | **Block Test Run start** until required tariff data and offer selections are complete. A draft campaign/configuration can still exist. |
| Subscriptions | Display fixed subscriptions **separately**; do **not** allocate them to individual runs or include them in marginal profitability calculations. |
| Shared free quotas/credits | **Do not track enterprise-wide consumption or allocate shared quota across campaigns**; price usage using selected **reference tariffs** without discounting global shared allowances. |
| Catalog maintenance | **Manual pricing entry**, with cited source, effective date, verification date and immutable history. |
| Price evolution | Updating a rate does **not** invalidate or silently recalculate prior Runs/results/dependencies. |
| AI Solution identity | A pricing selection is **not** part of the technical identity/fingerprint of the AI Solution if its effective technical configuration is otherwise unchanged. |

The remaining operational edge cases in section 11 are **open**, not silently resolved requirements.

## 2. Enterprise accessibility

Maintain a common, enterprise-wide component accessibility indicator, **independent of whether it is free or paid**:

| Suggested status | Meaning |
| --- | --- |
| `accessible` | Available for authorized enterprise use. |
| `restricted` | Requires specific approval, provisioning, contractual or technical conditions. |
| `not_accessible` | Known technology but currently unavailable for enterprise use. |
| `unknown` | Enterprise access has not been established. |

An inaccessible component remains discoverable in the catalog and technology watch. A commercially available/free product is not necessarily accessible to the enterprise. A complete assembled solution may have further access/integration constraints, even if its individual components are accessible.

Do not introduce Business Unit-specific accessibility in this increment.

## 3. Commercial pricing model: offers vs billable components

**Do not store one flat price or a single `is_free` flag as the authoritative pricing model.** A Provider or component can simultaneously offer a free tier, PAYG billing and several subscriptions.

Proposed conceptual entities (physical schema remains an implementation choice):

| Entity | Purpose |
| --- | --- |
| **PricingOffer** | Stable, versioned commercial plan attached to a component, provider, or an explicit applicable combination. Captures source, validity, currency, terms, and coverage. |
| **PricingComponent** | One billable rule within an offer: price, native unit, meter, conditions, billing period, fixed/variable classification, and possible tiers. |
| **CampaignPricingSelection** | Manual selection of applicable offer revisions for a **specific campaign configuration** or Framework participant/workflow, distinguishing alternative and cumulative charges. |
| **RunCostSnapshot** | Exact selected rate revisions, observed quantities, calculation policy/version, breakdown and computed marginal cost for that Run. |

An **offer** may contain multiple **cumulative components** (e.g., monthly fee + usage above threshold). Multiple **alternative offers** (e.g., PAYG vs subscription) should not be added together by accident. Additional charges may still be additive when genuinely cumulative.

Plans may apply to a particular Model served through a Provider, an independent Harness license, a Framework service, or a relevant combination. Do not imply that a Model's API price and its Provider's price are **two separate billable charges** if they describe the same single invoice line. Store the billing owner / charge identity needed to prevent double counting.

### Fields worth supporting

- Offer public ID, descriptive name, linked catalog object(s), provider/billing owner, offer status.
- Currency and unambiguous pricing unit (e.g. EUR per million input tokens).
- Pricing lines, unit quantities, fixed vs variable, applicable model/configuration/region and other conditions.
- Effective-from/to dates, manually registered source URL/reference, date last checked, optional explanatory terms.
- Optional tax inclusion/exclusion context and contract confidentiality classification.
- Explicitly separate **free**, **zero marginal usage under a flat-rate plan**, **unknown**, and **not applicable**.

Free-only, paid-only, mixed, and unknown labels can be *derived from cataloged offers*, avoiding a contradictory second pricing flag.

## 4. Supported pricing families

| Family | Example | Marginal Run cost |
| --- | --- | --- |
| Free / free software license | Open-source Harness with no license charge | Zero **license** marginal cost, not necessarily zero infrastructure/provider cost |
| Token PAYG | Separate input/output tokens, potentially cached tokens | Computed from metered units and applicable rates |
| Provider-specific credits | Provider A credits vs Provider B credits | Convert **using that offer's rules**, not a universal credit definition |
| Other per-usage | Request, minute, GPU hour, job, execution | Rate × corresponding measured units |
| Fixed subscription | Monthly or annual subscription | **Excluded** from run-level profitability; shown separately |
| Per-seat license | Seat/month | **Excluded** from run-level profitability; shown separately |
| Tiered/volume pricing | Unit-price brackets | Charge by explicit tier rules, without guessing missing thresholds |
| Hybrid | Subscription plus usage over included allowance | Fixed part separate; **billable variable excess** included when calculable |
| Negotiated / bespoke | Private contract | Supported as an offer, but cannot be used to start a new Run until required computation parameters have been completed |

Credit **purchase**, credit **balance**, and credit **spending** are different notions. Never charge both the price of purchased credits and their converted consumption for the same Run. Credit units are namespaced to the provider/offer.

**Shared allowances** are deliberately not tracked or allocated across campaigns. For comparable benchmarks, usage is valued at the selected reference unit rates without deductions for shared free quotas or prepaid pooled credits. Fixed subscriptions remain a separately reported commercial commitment. The resulting computed variable amount is a **reference cost** and may differ from the incremental amount actually appearing on a shared enterprise invoice.

For genuinely per-execution free tiers or thresholds that are fully determinable from the selected offer and the current Run alone, implementation may support them without global quota accounting; do not infer remaining shared entitlement.

## 5. Campaign setup and mandatory manual choice

A workgroup member selects the **actual pricing offer(s)** used for each evaluated configuration in the Campaign Benchmark Workspace.

1. Compose or choose the Model + Provider + Harness technical setup, optionally with a Framework and multiple participants.
2. Display eligible commercial offers for each **distinct billable component/charge**, with source and applicability.
3. Require the workgroup to select all applicable offers **manually**; the system can suggest compatible plans but must not silently select an offer in place of the member.
4. Validate that the chosen offers, meter types, currencies, required rates, tiers and conditions are complete **before the Test Run starts**. The **Run's consumption-input form is then generated from the chosen offer's actual metering rules** — credits only where billed in credits; input/output/reasoning/cache tokens only where relevant; calls/time/other units only if required; no irrelevant consumption field for a flat-rate-only offer.
5. Pin exact offer revisions and economic assumptions to the intended run/configuration. A later catalog price edit must not retroactively switch the selection.
6. Execute the Run, capture relevant usage, then calculate and store the result with a transparent per-line breakdown.

Different solutions within the same campaign may use different plans. The same technical AI Solution can be tested under different economic offers without creating artificial separate technical solution identities.

This selection should occur **before the first Run requiring the configuration**, not necessarily during the initial campaign draft creation. A campaign draft and Test Case planning are allowed while the pricing setup is unfinished; **starting the Run is blocked**.

The pricing completeness gate is independent of the later **Setup Guide publication gate** and the Campaign Evaluation Matrix's evaluation/waiver completion gate.

## 6. Cost calculation and profitability conventions

For chargeable usage components, calculate:

```text
marginal_reference_run_cost = SUM(measured_billable_quantity_i × applicable_unit_rate_i)
                              + applicable variable tier/overage adjustments
```

The full calculation must know the **unit and its conversion factor** (e.g. price per million tokens, rather than price per token). Native currencies and conversion assumptions must be explicit. Preserve precision and the applied calculation-rule version.

### Distinct economic quantities

| Measure | Treatment |
| --- | --- |
| Variable reference usage cost | Included in run-level economic/profitability analyses. |
| Fixed subscription, annual contract or per-seat fee | **Displayed separately**; **not amortized across Runs** for marginal profitability. |
| Valued human time | Remains a separate part of existing economic/value analyses. |
| Shared free quota or pooled prepaid credits | **No global utilization tracking and no campaign-level allocation/deduction.** |
| Unknown usage/missing metering | **Preserve the incomplete Run/session as pending**, not as a zero-cost finalized result. Its evidence is retained but **not eligible for publication** until the selected offer's required measured units become available. Independent complete Runs can be published in a partial Campaign release. |
| Historical bill/invoice actuals | Do not conflate with a price-derived reference amount. |

Examples: an API model charged per million **input** tokens and per million **output** tokens needs separate usage quantities. A single total-token count is not sufficient to reproduce this split. Some tariffs additionally need cached/reasoning tokens, requests, minutes or other counters.

Where a plan has a subscription and an overage rate, display the fixed subscription separately and compute independently billable excess according to the explicit rules; **do not allocate the subscription to the individual benchmark**.

For comparative analytics, label the metric **variable reference cost** to avoid presenting it as the literal amount charged on a real invoice.

## 7. Frameworks and collaborative executions

A Framework is a cataloged orchestration/workflow **distinct from** an individually measured Model/Provider/Harness trio. A collaborative Run may involve several individually configured participants.

- Allow manual offer selection for each participant's actual billable Model/Provider/Harness use, and any Framework/orchestrator-specific costs.
- Calculate variable usage cost for every billable source, then aggregate to **one composite Run cost**.
- Do not double-count shared gateway/Provider charges or the same invocation represented on multiple component records.
- Do not attribute an overall composite economic result as an individually measured score for a single participant.
- Show fixed framework or participant subscriptions separately from marginal variable costs.

## 8. Price lifecycle, sources and historical behavior

Price information is **entered and updated manually** by workgroup members, with the source, date of applicability and date checked. A pricing update creates a new **immutable revision** of the offer/line.

Historical Run costs and their selected tariff revisions remain readable and **do not change automatically** after a rate update. No automatic run invalidation, dependency invalidation, new campaign review, or republishing is triggered merely because a vendor rate or component changes.

A later hypothetical *what would this prior Run cost at today's prices?* calculation is a **distinct simulation**, not an overwrite of the originally recorded cost.

If an original tariff was entered incorrectly, correct it with a new revision and preserve the earlier record. Any permitted correction of a derived cost should be explicit and independently traceable; do not rewrite the original Run's frozen experimental measurements or evidence.

Accessibility, offer availability, and component lifecycle also evolve independently of historical measured results.

## 9. Preliminary architecture and migration impact

| Area | Impact | Expected changes |
| --- | --- | --- |
| **Technology Catalog / UI** | High | Versioned pricing offers, per-element access status, manual source-backed price entry, offer alternatives and charge composition. |
| **Schema/type registry** | Medium–high | New pricing types, native unit definitions, rate constraints and extensible applicability; preserve old catalog schema revisions. |
| **Campaign Workspace** | Medium | Explicit pricing-offer picker for each selected configuration, including Framework participants, with complete pre-run validation. |
| **Test Runs / sessions** | **High** | Pin offer revisions, add variable usage counters, computation and immutable pricing/cost provenance. |
| **Calculation engine** | **High** | Declarative meters/rates, currency/unit handling, tiers, credit conversion and anti-double-counting logic. |
| **Results Explorer / profitability** | High | Expose marginal reference cost separately from fixed fees and human-valued time; compare compatible samples/metrics. |
| **Accessibility filters** | Medium | Enterprise-wide accessible/restricted/not accessible/unknown filtering independent of catalog free/paid labels. |
| **Versioning and audit** | Low–medium | Reuse catalog immutability/attribution for pricing records and run economic snapshots. |
| **Existing data migration** | Medium | Preserve original free-text pricing, `cost_mode=amount|flat_rate|unknown`, `cost_eur`, and total-token semantics; do not fabricate detailed metering or new calculated costs for legacy Runs. |

**Present baseline:** The catalog currently supports descriptive `pricing` information but not full pricing-plan entities. Individual Runs currently accept `cost_mode=amount|flat_rate|unknown` with a supplied EUR amount or unknown, and may record a **single total token count**. This future proposal changes new Run workflows and requires backward-compatible handling for historical records.

**Implementation strategy:** start with declarative, unit-based PAYG, credits, fixed subscriptions and simple hybrid lines, but design versioned types extensibly for tiers or later billing forms. Avoid constructing a complex enterprise contract/invoice/credit-accounting system.

**Separate pricing from AI Solution identity:** an identical effective technical configuration remains the same measured solution when only the commercial plan changes. If the plan causes a materially different **technical service/configuration**, that change is reflected independently in the technical setup fingerprint.

## 10. Acceptance criteria

1. Each Model, Provider, Harness and Framework can exist without a pricing offer; its availability/pricing state is explicit rather than fabricated.
2. A component can offer multiple mutually exclusive pricing plans; each can hold multiple genuinely cumulative billable rules.
3. Access status is common to the enterprise and independent of free/paid status.
4. Each offer/rate has a currency, source, verification date, effective period where known, and immutable revisions.
5. Credit units belonging to two Providers remain distinguishable and are converted using the matching offer rules.
6. A workgroup member **manually selects** all relevant offer revisions for a campaign configuration before any new Test Run begins.
7. Attempting to start a Run with missing selected offers or incomplete tariff parameters is **rejected**; planning a draft campaign is not blocked.
8. For a correctly measured per-token Run, the backend computes the cost using the correct input/output (and other applicable) meters, pricing units and selected revisions — without manually entering the resulting EUR cost.
9. Flat subscriptions are displayed distinctly and **excluded** from marginal profitability, while separately chargeable variable usage is included.
10. Shared free allowances / credit balances are **not tracked or allocated**; reference-cost calculations do not deduct pooled entitlements.
11. Model and Provider charges for the same underlying service invocation cannot be added twice; mutually exclusive plans are not cumulatively selected.
12. Composite Framework Runs include all billable participant/orchestrator variable costs once, but do not impute the overall cost to an individual measured solution.
13. Revising a tariff does not alter the previous Runs' prices, observed data, calculations, identities, campaign publication, or historical relationships.
14. The same technically identical AI Solution can be evaluated under different offers without generating an extra measured AI Solution identity.
15. Historical Runs and existing Demo/Server records remain readable with their original cost semantics, without invented backfilled usage.

## 11. Open edge cases and implementation questions

These were **not** finally decided in the discussion:

- **Missing consumption after the Run has started — now resolved at product level:** preserve all entered setup, interactions, artifacts and measurements as an **incomplete/pending execution**; do not finalize or publish **that Run** without the required billable meter data. Allow **partial Campaign publication** of other complete, adequately documented Runs. A **failed-DoD but complete** experiment remains valid publishable negative evidence. Exact resumed-session/Run status mapping remains implementation design. See [Publication & Information Lifecycle](publication-and-information-lifecycle.md).
- **Currency handling:** reporting base currency, FX rate source, rate timestamp, and tax-inclusive/exclusive presentation.
- **Tier/overage policy:** which per-Run thresholds are deterministic without tracking globally shared quotas, and how should unavailable overage data be represented?
- **Meter acquisition:** manually entered usage quantities vs provider usage metadata/imports; how to handle cache categories, reasoning tokens and non-token usage without forcing unsupported fields.
- **Alternative/composite offer constraints:** practical rules for selecting a plan once and avoiding multiple charges for the same measured invocation.
- **Accessibility granularity:** any extra restrictions for a specific assembled solution beyond the common enterprise-wide component status.
- **Exact plan applicability:** provider region, negotiated contract visibility, version validity, and how selection reacts to commercial offer expiry after a campaign is prepared.

Do not invent defaults that contradict the decisions above.

## 12. Scope boundaries

This feature does **not** implement corporate invoicing, prepaid credit-wallet reconciliation, shared free-quota consumption tracking, per-business-unit access plans, automatic pricing scraping, automatic selection of the cheapest plan, or automatic re-rating/invalidation of old results.

It remains separate from the future [Composable Setup Guides](composable-setup-guides.md) and [Data Governance Audit Explorer](data-governance-audit-explorer.md), while reusing shared versioning and business permission foundations.

**This document captures the agreed future feature and impact assessment. It is not a claim that the APIs, pricing calculation engine, or publication/readiness UI already exist.**

## 13. Harmonized integration contract — selected offer drives the Run

**This is the authoritative home for pricing offers and meter declarations**, distinct from the Campaign/Run lifecycle. At preparation, the Workgroup **manually selects** applicable offer revisions for actual billable sources, while the application automatically derives the Run's required consumption inputs and resulting reference variable cost. Do not ask a user to reselect a commercial mode or manually type a final EUR cost already determined by selected tariff × observed consumption. Flat-rate license/subscription remains reported separately; a genuinely fully fixed offer requires no irrelevant per-Run variable field. Hybrid offers may expose only their applicable variable meter lines.

Required meters unknown **after execution** leave that Run **pending**, preserve all work and original data, and do **not** block a versioned [partial Campaign publication](publication-and-information-lifecycle.md) containing other finalized Runs. Retain exact recorded costs and offer revisions for historical Runs; current hypothetical revaluation at newer tariffs is a separate projection. This page does not own the publish/revoke/delete state machine or the physical purge policy.
