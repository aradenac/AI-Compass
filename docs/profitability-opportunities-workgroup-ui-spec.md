# Profitability & Opportunities — approved Workgroup UI contract

**Prototype:** [standalone interactive HTML](prototypes/profitability-opportunities/index.html) · [design/limitations](prototypes/profitability-opportunities/DESIGN.md).
**Related baseline:** [Deployment & Adoption Planning](deployment-and-adoption-planning.md), [FUT-13 economic opportunities](dap-economic-opportunities.md), [FUT-14 opportunity heatmap](management-opportunity-heatmap.md), [AI Solutions portfolio](ai-solutions-workgroup-ui-spec.md).

## Core questions and simplified navigation

The default page must directly answer:
1. What **annual prospective gain** is attributed to AI solutions **actually deployed and verified**?
2. How much **additional** gain could deploying accepted measured benchmarks bring, beyond current activation?
3. How much **further additional** gain might experiments on theoretical Forecast configurations bring, **beyond the best available activated/benchmarked alternative**?

The main screen is an **opportunity matrix with exactly three gain columns**: **Activated**, **+ Benchmarked to deploy**, **+ Forecast to experiment**. It does not display one column per AI Solution, and does not provide scenario/population simulators or repeated giant KPI cards in the main view. Advanced scenario authoring and confidential population configuration remain separate authorized planning tooling, not discarded data or APIs.

## Rows and category rollups

- Group activities by **project phase** (RFQ, architecture, software development, qualification, etc.) or **specialty/domain**, switchable in place. Show group rows **collapsed by default**, click to reveal Tasks/activities.
- Group row values must be sums of **distinct, non-overlapping eligible activity-level increments** in each column. Never add an aggregate parent Task to its constituent children; detect overlapping workload estimates or mark them unquantifiable.
- Each individual activity/Task can combine deployed, measured, theoretical, idea-only and missing inputs. Evidence maturity **belongs to each underlying Task × candidate association**, never to a whole solution column or whole phase.
- Idea-only/unquantified opportunities may appear in the relevant group/task row as an unquantified indicator, **not as EUR 0** or guessed benefit. Empty/uncovered cells must remain distinguishable.
- Restrict compared candidates to the published **minimal accepted/qualified measured AI Solutions portfolio**, plus only relevant published theoretical Forecast alternatives. Preserve the published-outside-minimal inventory policy from AI Solutions when context demands it; do not silently equate all measured catalog records with endorsed choices.

## Incremental, non-duplicative economic semantics

For each **same Task/activity and same eligible workload population**, compute a non-overlapping reference ladder, rather than summing different tool alternatives:

- **Activated**: modeled positive annual potential for verified first-use/entitled covered occurrences, using eligible selected actual usage alternative.
- **+ Benchmark**: positive additional annual capacity *not already captured as activated*. Include non-activated covered occurrences and, when justified by comparable alternatives, an explicitly defined incremental improvement over the effective activated baseline; do not assume double coverage or sum rivals.
- **+ Forecast**: positive increment over the **best effective activated/accepted measured alternative**, not an independent total. A Forecast candidate with lower projected performance adds **nothing** to the upside, but its comparison/evidence may remain inspectable. Forecasts require published, quantitatively complete sources with transparent uncertainty/recovery assumptions. They do not imply measured qualification.

**This is a new desired incremental-domain contract**, distinct from the currently implemented FUT-13 three disjoint population/evidence slices. The implementation must first specify the precise comparison, per-occurrence baseline, verified activation cohort and population overlap allocation, version the formula, and test edge cases (negative, unknown, contradictory measurements, source withdrawal, alternative costs, incomplete forecast, no eligible evidence) before calling outputs authoritative. Do not mislabel existing FUT-13 outputs as these deltas.

All displayed EUR amounts are annual **prospective labor-value capacity** from source-backed assumptions, not realized accounting savings/profit. Never turn missing costs/human times into zero or treat fixed subscription as free variable usage.

## Visual presentation

- Distinct color family for each of the three gain columns, with **intensity scaled to the monetary amount within that family**; maturity/deployment markings and unquantified ideas must not masquerade as gain colors.
- One compact **stacked cumulative total bar**, showing the **numeric amounts in all three segments**, and their additive total. No redundant separate metric strip.
- **Historical chart:** smooth/continuous **stacked area curves** for Activated, additional Benchmarked and additional Forecast potential. Plot real dated, immutable scenario/source snapshots, with date labels and inspectable provenance. Do not invent daily intermediate historical snapshots or imply continuous observed gains between discrete saved revisions; interpolation is visual only and marked as such.

## Actionable lists below the matrix

Provide **two visibly separate populated lists**, not a generic mixed ranking:
1. **Priority deployments — accepted Benchmarks:** the selected measured AI Solution/configuration for each activity or qualifying set of activities, its *additional* annual potential, and enterprise accessibility status (**Accessible / Restricted / Not accessible / Unknown**).
2. **Experiments to prioritize — Forecasts:** explicitly theoretical candidate configuration, prospective *additional* upside beyond the best activated/measured option, its accessibility state and source provenance.

The lists are actionable navigation/context, not automatic deployment requests, license purchasing, campaigns or authorized access provisioning. Avoid fake “selected solution” identities for unmeasured Forecasts. The approved demo must visibly populate both sections on initial load and retain the ability to filter/expand evidence.

## Evidence, permissions and boundaries

- Cell selection reveals **progressive calculation and evidence provenance**, including baseline workload, measured Run, forecast revision and historical pricing assumptions, without exposing private individual rates in Workgroup views.
- Actual deployed figures require independent **verified entitlement and first use** under FUT-15. As of the existing Server baseline, verification is pending and **Activated currently remains zero in Server**; positive activation in HTML is fictional demonstration data only.
- Preserve read-only behavior for this decision/exploration page, immutable evidence snapshots, differentiated theoretical/actual states, and authorization-gated workforce/salary scope. The full FUT-13 scenario editor and planning APIs remain available in the appropriate restricted workspace.
- Prototype is not a new economic service implementation. Visually and interactively test at 1366×900 and 1024px with collapsed groups, switchable grouping, dense matrix, accessible status, history and populated action lists.
