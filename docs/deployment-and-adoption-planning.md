# AI Compass — Deployment & Adoption Planning

> **Reference:** Product/domain specification maintained with the implemented application. The delivery tracker and outstanding UX acceptance work are maintained in the [implementation plan](future-evolutions/implementation-plan.md).

> **Contract:** Workload profiles; versioned Task × configuration economic projections and history; deployment access targeting; resource and rollout budgets.
> **Decision context:** Discussions through 2026-10-10.  
> **Scope:** Enterprise workload profiles; Task × AI configuration opportunity matrix; profitability simulations and historical trends; exploratory provenance; deployment/access tracking; experimental and rollout resource budgets.  
> **Related baseline:** [Product Definition](product-definition.md) · [Platform Architecture & Data Governance](platform-architecture-and-data-governance.md) · [Benchmark Workflow](benchmark-workflow.md) · [Users & Access](users-and-access.md) · [Campaign Evaluation Matrix](campaign-evaluation-matrix.md) · [Technology Accessibility & Pricing Management](technology-accessibility-and-pricing.md) · [Data Governance Audit Explorer](data-governance-audit-explorer.md) · [Composable Setup Guides](composable-setup-guides.md)

## 1. Purpose and fundamental product separation

**Objective:** turn AI Compass's evolving hypotheses, Technology Watch, Forecasts, measured Benchmarks, pricing, Task hierarchy and population workloads into **explainable prospective economic opportunities**, then identify who should have which AI capabilities, track their verified deployment, and justify the tokens/credits/licenses needed.

This is **decision support and resource planning**, not a claim that projected savings have been realized or an automated IAM/billing system.

**Three distinct, connected business views:**

| View | Question answered | Owns |
| --- | --- | --- |
| **1. Profitability & Opportunities** | Which Task × AI configuration combinations have the greatest potential for a selected population, how mature is the evidence, and what is already deployed? | Central heatmap, simulations, candidate suggestions, three economic slices, historical evolution, idea visibility. |
| **2. Deployment & Access** | Which selected people have the necessary AI components/accounts/permissions, were these verified, and did they actually use the solution? | Targets, explicit access requests/approvals, provisioning status, verification and first-use confirmation. |
| **3. Budget & Resource Planning** | Which licenses, tokens, provider-specific credits or other metered capacity must be requested, for pilots or for targeted deployment, over what period? | Automatically derived, explainable resource needs, pilot envelopes, rollout budgets and optional already-active capacity. |

**Do not merge these views into one giant operational screen.** They share population, Task, configuration, tariff and deployment references. The profitability view *displays* deployment state but is **not** where credentials, requests or provisioning are managed. The budget view calculates/justifies needs; it does **not** issue credentials.

One additional **cross-cutting interactive Evidence & Calculation Explorer** is available on every relevant matrix cell, metric, chart point and budget amount, without rendering all evidence at once.

## 2. Decisions agreed; distinguish from remaining open design points

- Profiles represent **Job Roles**, **Specialties**, people and their effective Task workloads (estimated annual frequencies and engineer-only baselines), with **inheritance plus individual overrides** and job-based hourly valuation rates, optionally overridden for an individual.
- The central explorer is a **Task-tree × AI configuration matrix**: collapsible hierarchy on the **left**, configurations/solutions on the **horizontal axis**. Do not substitute an employee × Task matrix for this primary view. Population is a **filter/scope**, not the column dimension.
- **Cell background intensity conveys potential economic gain only. A single overlay icon conveys the maturity/deployment status only.** Background color must not encode maturity, and the icon must not encode profitability. An uncovered combination has **no icon and no economic fill**.
- Explicit categories: **deployed/used**, **benchmark evidence**, **Forecast evidence only**, **intuition/idea only**, **uncovered**. Their underlying evidence types remain separately inspectable; partial deployment is shown as coverage detail.
- Every potentially meaningful cell can be explored **progressively by clicking**; no mandatory all-at-once provenance graph.
- Forecasts contribute to projected gains **even when measured Benchmarks exist**, at a **smaller configurable weight** when the two can be meaningfully compared. Benchmarks take precedence. The previously illustrated 80%/20% weighting is **illustrative, not a final mandated coefficient**.
- Three **mutually exclusive** annual opportunity metrics: **Activated Potential** (estimated gains for deployed/used scope), **Benchmarked Opportunity** (remaining benchmark-backed potential), **Forecast Opportunity** (remaining forecast-only potential). Display a **cumulative bar** and **time-series history**. They are *prospective annualized valuations*, **not actual recognized profit**.
- **Ideas/intuitions without quantitative Forecast or Benchmark** appear in the grid, but **never generate numerical profit by guesswork**, nor automatically create a To-Do or other compulsory workflow.
- Current simulations **recompute as relevant source data evolve**; historical estimate snapshots remain unchanged, traceable and comparable.
- The user may inspect **automated recommendations** and create **freely configurable what-if scenarios**. A candidate's selection for deployment is intentional; exploring a cell does not perform any write.
- **Deployment & Access** tracks requests, decisions, access readiness, functional verification, and **first confirmed use**. No automated external provisioning initially; integrations may follow.
- **Quota/Budget Planning** is derived as far as possible from workload frequency, benchmark metering, usable Forecast consumption estimates, provider-specific tariffs and already-known entitlements; **minimal manual input**.
- **Experimental budget:** a promising Forecast can be explicitly selected for a pilot, principally by specifying **how many pilot users**; derive capacity from available assumptions and the selected pilot horizon/defaults. Separate this demand in the budget summary.
- **Rollout budget:** for benchmark-backed solutions chosen for not-yet-covered eligible people, derive eligible roles/people and amount of capacity needed; show licenses for flat-rate products, usage units for metered products, or both for hybrids.
- **Existing users:** optionally include continuing **capacity needs** as a separate budget category. **Do not manage credential renewal**, token rotation, subscriptions' renewal workflow, or enterprise shared credit-wallet balance.
- Enterprise-wide *technology accessibility* from the Pricing proposal remains **one common catalog property**. **User-specific external-tool entitlement and confirmed access** are separate data, without changing AI Compass login permissions.
- Preserve source identity, original evidence, immutable historical revisions and privacy constraints. Never fabricate missing measurements, quota sizes or actual usage.

## 3. Workload & organizational reference data

The workload reference data is distinct from the Task taxonomy and AI Compass account management:

| Concept | Role |
| --- | --- |
| **JobRole** | Reusable métier classification, e.g. embedded developer, software validator, system engineer. |
| **Specialty** | Domain/subdiscipline, e.g. MCU, hardware, safety, verification; people may have several. |
| **Person / PlanningProfile** | A collaborator relevant to planning, optionally linked to an authenticated AI Compass account. People need not have accounts merely to be included in deployment planning. |
| **OrganizationMembership** | Company/team/BU scope, effective periods for aggregation and visibility. |
| **WorkloadProfile** | Typical set of existing Task IDs, annual frequencies and optional time/period distribution for a métier/specialty. |
| **WorkloadOverride** | Specific person's replacement value or explicit exclusion, with source/inheritance context. |
| **LaborRate** | Hourly valuation/cost reference for role (and optionally person), scoped and versioned with effective period and confidentiality. |
| **PlanningPopulation** | Individually identified collaborators and, where exact roster is unavailable, aggregated role/team cohorts with headcount. |

**Reuse stable Tasks and their hierarchy.** Test Cases remain separate concrete evaluation instances; do not turn TC1/TC2 or implementation/robustness criteria into taxonomy branches. Profiles reference Tasks, not ad hoc strings.

**Effective workload:** role/specialty defaults supply tasks and frequencies; person-level overrides **replace, rather than add to**, inherited values. Different source profiles may overlap: define deterministic precedence/conflict handling, never silently add duplicate task occurrences. Distinguish **unknown/not supplied**, **explicit zero/excluded**, **inherited**, **manually overridden**. A worker may do Tasks outside their primary job.

**Taxonomy aggregation:** avoid summing both a parent Task and a descendant if the parent frequency already includes descendant occurrences. Make distinct executable task quantities explicit, support rollups without double-counting, and flag unrealistic total annual workloads for review rather than inventing capacities.

The selected viewer's **population scope** (enterprise, BU, team, role, specialty, cohort or authorized individual) drives frequency, rate, access coverage and annual gain. Support aggregated pilot headcounts and hypothetical populations without requiring creation of dozens of user accounts.

Annual frequency is the **baseline**; period-based resource needs may assume uniform monthly/quarterly distribution unless explicit seasonality is known. Do not represent uniform distribution as an observed fact. Full seasonality and per-person manual period grids are not required initially.

Hourly rates are **labor valuation assumptions**, not necessarily actual private salaries. Individual details are restricted; authorized aggregate views should remain available without exposing protected personal rates.

## 4. Evidence maturity: ideas, forecasts, benchmarks and deployed usage

The matrix merges several evidence states **without conflating their meaning**:

| Underlying evidence | Meaning | Numerical economic estimate? |
| --- | --- | --- |
| **No coverage** | No relevant submitted idea, forecast, benchmark or verified deployment information for this Task × configuration. | No — blank/transparent cell. |
| **Intuition / Idea** | A user submitted an initial belief that AI could improve this Task, optionally suggesting technologies or an approach. | **No**, even if narrative optimism is strong. |
| **Forecast-only** | A reasoned, task-linked theoretical configuration with quantitative projections and Technology Watch sources where applicable. | Yes, **theoretical**, only if required metrics can be computed. |
| **Benchmark evidence** | A related measured AI Solution/Framework workflow and completed Test Case/Run evidence, potentially complemented by Forecast. | Yes when comparable measured metrics suffice; clearly qualify evidence quality. |
| **Deployed / first use confirmed** | Actual population members have been equipped, access verified, and use confirmed. | Potential for that deployed population when a **quantified source** exists; deployment alone never fabricates profit. |

**Important identity distinction:** Forecasts may describe **theoretical configurations** before any Run exists. Only a controlled measured Run creates a measured AI Solution identity under the current product definition. Do not fabricate an existing measured-solution ID just to populate the matrix. Link candidate configuration identities/fingerprints and measured solution references appropriately.

A **Framework** with collaborative participants is a distinct candidate configuration, and its composite benchmark is **not** treated as an individual solution's score.

A plausible, **non-mandatory** knowledge path is:

1. **Submit an idea/opportunity intuition** — Task, optional target population/configuration, concise intended benefit and optional rationale. Reuse existing Feedback & Ideas where possible; link any structured opportunity hypothesis rather than duplicating commentary.
2. **Technology Watch and Forecast(s)** — exploratory research and quantified predictions tied to relevant Tasks/configurations. A Watch Entry alone is **not automatically a numeric Forecast**.
3. **Benchmark Campaign / Test Cases / Runs** — real measurements can support, revise or reject Forecast claims.
4. **Select deployment candidates and verify use** — people receive needed capabilities, and their first real use is confirmed.

These are **information maturity stages, not a compulsory state machine**. Teams may benchmark directly, keep theoretical work theoretical, or record a deployed tool whose usage is known without backfilling evidence. **No automatic task assignment, To-Do list, new Campaign or access request merely because a grid cell shows an intuition or an attractive Forecast.**

## 5. Primary UI: Task-tree × AI configuration profitability heatmap

The **central representation** is a large, scalable two-axis matrix:

- **Left fixed/sticky column:** full editable/reusable Task taxonomy *projected as an expandable, collapsible hierarchy*; browse groups to leaves, scroll, search and filter. Editing Tasks remains in the normal Task Management area.
- **Horizontal columns:** actual measured AI Solutions **and** distinct theoretical candidate configurations, plus labeled composite Framework workflows when applicable; group/filter by model/provider/harness/framework, evidence maturity or solution. Do not imply all candidates are benchmarked.
- **Cell:** one Task × configuration under the **selected population and scenario**, containing a rentability-intensity background and a **single status icon**, not multiple stacked blocks of explanatory data.
- **Population/scope controls:** choose company/team/role/specialty/cohort/individual when authorized; annual period and scenario/revision filters; grouped Task and solution views. Same value and legend thresholds across all columns in one comparison.
- **Interaction:** click any covered cell for a small summary and drill-down into assumptions, alternative estimates, source records and versions through the **progressive Evidence Explorer**. Clicking **does not initiate a workflow**.
- **Usability at scale:** sticky headers, horizontal/vertical virtualization, accessible keyboard navigation, search, server-side paging/aggregation and efficient hover detail for large Task × solution grids.

### The two orthogonal encodings — fixed requirement

**Background intensity is ONLY about economic potential.** Use a consistent quantitative color scale across the matrix: low positive savings to high positive savings. This is **not** a colored state badge or an arbitrary color-per-status scheme. Expose actual value/units in tooltip/details. Zero, **negative**, unavailable and incomparable values must be visually distinguishable rather than conflated with unknown; use an explicit legend and accessible numeric alternative. A cell with only intuition has no numerical intensity, but can show its idea icon.

**The centrally displayed icon is ONLY about evidence/deployment status:**

| Icon meaning (visual suggestion) | Condition and interpretation |
| --- | --- |
| Check-circle / deployed | At least the applicable deployment scope is verified as having used the configuration; show proportion/count when partially deployed. |
| Flask / benchmark | Measured evidence exists, and this cohort is not confirmed deployed for the relevant portion. |
| Telescope / forecast | Task-linked Forecast exists, but no applicable measurement for this configuration/cohort. |
| Lightbulb / intuition | Submitted intuition only; no applicable quantitative Forecast or measured evidence. |
| **No icon** | Uncovered combination: nothing known. |

Icon shapes and exact color palette can be finalized by UI design; **the semantic separation cannot be changed**.

A benchmark **planned or in progress** is not a completed positive result. Such progress may be explained in detail or marked by a subtle state variant, without granting the cell a measured-gain estimate prematurely. Measured failure also does **not** imply a positive gain.

**Priority of the single primary icon, conditional on available data:** deployed/used > benchmark evidence > forecast-only > intuition > unknown. A deployed cell can still have both Forecast and Benchmark sources; preserve and expose **all** underlying categories in details. If adoption is **partial**, do not hide the benchmark/forecast potential of the remaining users: show coverage (e.g. 6/20 verified) and compute all three economic slices per individual/cohort segment.

**Uncovered cell:** absolutely **no economic fill and no icon** (neutral default table surface). No speculative zero or invented evidence. **Idea-only cell:** lightbulb with no economic fill unless and until an independently valid numeric Forecast/Benchmark exists.

**Hierarchy and aggregation:** collapsed parent rows may show a non-duplicative summary, not a naive sum of parent plus descendant tasks. At a Task with multiple alternatives, displayed gains are **candidate comparisons**, not simultaneously additive enterprise savings.

## 6. Economic projection: keep it simple, explainable, prospective

For one person/cohort, Task and selected configuration, a simple planning-level estimate is:

    annual_reference_gain = annual_occurrences ×
                            [(baseline_human_hours - expected_AI_assisted_human_hours)
                              × labor_valuation_rate
                             - variable_reference_AI_cost_per_occurrence]

- Baseline hours: Task/workload estimate without AI; avoid counting both a global baseline and a TC-specific one twice.
- AI-assisted human hours: measured/forecast preparation, steering, review, correction and recovery where known; agent waiting time is not automatically labor time.
- Consumption cost: the **selected applicable Pricing Offer's variable reference usage cost**; separate from fixed subscription and seat/license fees.
- The projection remains a **capacity value / potential labor-value gain**, not verified cash savings or actual profits.
- Failed runs, recovery effort, sample size, variance, quality/DoD, Test Case coverage and task applicability should affect reliability/eligibility. **Do not** simply multiply gain by a success probability while ignoring failure costs.
- If required time, rate, price or usage quantities are unknown, label the estimate **unquantifiable/partial**, never silently set to zero.

### Forecast + Benchmark blending

Provide three evidence cases:

1. **Forecast only:** quantify from theoretically predicted performance, **clearly theoretical**.
2. **Benchmark only:** use applicable empirical measurements and their reliability/coverage, **measured-based projection**.
3. **Both:** retain each estimate separately; compute a weighted **blended projection** when same Task, comparable configuration/scope, units and assumptions permit it. Benchmark **must carry more weight** than Forecast. Keep weight **configurable and visible**, and store calculation version. Previously discussed **80% benchmark / 20% Forecast is an example, not a finalized default**.

A rejected/failed DoD or a clearly inapplicable benchmark **cannot be offset by a rosy Forecast to claim deployable value**. Record ineligibility and quality caveats; do not force an unsupported blended estimate. Forecasts are neither retroactively turned into measured Runs nor used to rewrite original measurements.

### Scenarios and suggested candidates

- **Automated suggestions** rank candidate solutions for selected Tasks/profiles **using applicable, currently active, published measured evidence and the versioned experimental methodology as the source of qualification**; theoretical candidates remain clearly distinct. Economic gain, representativeness/confidence, evidence maturity, compatibility/access gaps may be reported transparently, without turning unreviewed theories into measured results. **Editorial Recommendations are descriptions/limitations, not manual overrides of methodology-derived rankings.** Explain each suggestion; never use a hidden unversioned AI ranking.
- **Freely configurable saved what-if scenarios** can choose populations, candidate solutions per Task, relevant assumptions and weighting; compare scenarios. Simulations are not Benchmark Campaigns or new Test Runs.
- Avoid double-counting the same person's occurrence across **multiple alternative AI solutions**. The chosen scenario determines the applicable candidate for aggregate totals; multiple candidates can still appear side by side for comparative inspection.
- If a person already uses an AI solution for the same work, any proposed **replacement/upgrade** must distinguish **incremental improvement over current state** from a full baseline gain. Do not sum both. Exact replacement policy is an implementation question.
- Tied-to-source forecasts, recommendations and measured results may change over time. **An individual grid cell's displayed potential is not automatically an additive part of the company-wide headline total.**

## 7. Three complementary, non-overlapping annual opportunity metrics

Present these as a **single cumulative distribution bar**, total and percentages, with links into filtered portions of the matrix:

| Slice | Interpretation | Classification |
| --- | --- | --- |
| **Activated Potential** | Estimated annual value associated with eligible Task occurrences where the selected AI configuration has **verified access and confirmed actual first use** for the applicable persons. | First in classification priority, **not** actual measured savings. |
| **Benchmarked Opportunity** | Additional **not-yet-activated** annual potential backed by applicable measured benchmark evidence (optionally blended with linked Forecast). | Remaining benchmark-backed portion. |
| **Forecast Opportunity** | Additional **not-yet-activated** annual potential supported by **Forecast only**, with no applicable benchmark for that candidate. | Remaining theoretical portion. |

For each **unique person/cohort segment × Task occurrence × chosen configuration** in a scenario, assign its modeled value **once and only once** to the appropriate slice, respecting partial deployment. A solution with measured + theoretical inputs is in the **Benchmarked** slice until activated, not in both benchmark and forecast slices. Intuition-only and unknown combinations contribute **no fabricated monetary values**.

    modeled_total_annual_potential =
        activated_annual_potential +
        benchmarked_remaining_annual_opportunity +
        forecast_only_remaining_annual_opportunity

The three slices describe annualized estimates **at a point in time**, not money actually saved to date. Even the **Activated** slice is a modeled projection, not a measured realization of profits; a first-use confirmation does not prove the projected value was achieved.

A separate **count of unquantified ideas**, coverage gaps and potentially unquantifiable forecast/benchmark cases should appear **outside** the three monetary slices and outside the total, rather than disappearing.

For negative or zero potential, preserve the information and disclose the total aggregation convention; do not interpret negative gains as positive opportunity. An initially simple headline may sum positive eligible candidate gains only **if explicitly labeled**, while retaining negative values independently. Do not silently drop unfavorable experiment results.

## 8. Live recomputation and immutable historical trends

**Current projection:** automatically recalculate affected derived opportunity cells/aggregates when material dependencies change:

- New/updated/published Forecasts, Technology Watch references or source applicability;
- New published benchmark results, **authorized corrections and revocations of published Runs**, versioned interpretations, changes in quality or sample coverage; consume only [currently effective published evidence](publication-and-information-lifecycle.md), never include pending/incomplete or withdrawn Runs in live quantified totals;
- Task taxonomy, workload frequency, population composition, job/specialty profile, rate and baseline assumptions;
- Pricing Offer/rate updates relevant to prospective costs (without changing historical Run costs);
- Eligibility, selected candidate/scenario, access verification, first confirmed use, deactivation/revocation.

Respect publication/visibility and permission rules; **don't assume that every draft Run or forecast is fit for public-facing simulations**. Default eligibility for unpublished/preliminary evidence is an open implementation choice, not implicit publication.

**Historical chart:** display total and three separately distinguishable trends, with annualized value on the Y-axis and snapshot date on the X-axis. Support a **cumulative/stacked view** and individual curves; see how total opportunity and its distribution change over time.

Store **immutable, dated snapshots** of the derived aggregate and enough per-source/per-scope calculation references to reconstruct the meaning **as known on that date** (algorithm, weighting, population, effective task/rate inputs, underlying Forecast/Run/recommendation/pricing revisions, deployment status). Today's changes never rewrite last month's historical plotted point.

Be able to drill down a chart point into its inputs, and **explain the delta** between two dates (e.g., new forecast, new benchmark lower than predicted, workload revision, candidate promoted to deployed, population growth). Conversions between the three slices can occur **without increasing total gain**.

Choose snapshot cadence/trigger strategy (material-change, daily/monthly or hybrid), backfill policy and efficient aggregation during implementation. Recompute forward-looking estimates without continuously re-opening or modifying immutable historical experiments. Re-evaluation should create new **derived projections**, not mutate source evidence.

## 9. Exploratory provenance — progressive disclosure, not an evidence dump

**Every displayed number or stage must be explainable, through navigation.** Do **not** flatten every input, URL, run, formula and document into the same matrix cell or one gigantic static graph.

User experience:

1. **Click a matrix cell, summary slice, budget line or historical chart point** -> compact side panel or inspector: number, unit, stage, coverage, and a short plain-language reason.
2. Choose **"Why this result?"** -> factor breakdown: population, effective annual task frequency, human-hour baseline, source-specific performance, tariff, forecast/benchmark weight, calculation method.
3. Click one factor -> **navigate into that source**: inherited workload/override, Task/TC, Forecast, Technology Watch Entry, reference URL, benchmark campaign/run/revisions, metered consumption, Setup Guide, selected Pricing Offer, or deployment verification.
4. Continue along **one branch at a time** via drill-down, back-navigation and breadcrumbs to the immutable original record/evidence, subject to permissions. Where a derivation has several parents, let the user choose the branch.
5. A historical point must navigate to the **revisions actually used then**, not silently substitute the latest revisions.

A read projection / provenance graph of **typed IDs, version references, dependency edges and calculation-step explanations** is appropriate. Use shared reusable UI and API contracts (lazy/deferred detail loading), not copied strings or universal exposure of sensitive original payloads. Provenance is **also valid for non-numeric stages**: why marked deployed? who verified first use? why an idea is linked to a Task?

A deeper dependency graph is optional, **never the mandatory first view**. Preserve fine-grained authorization throughout traversal: a user who can see an authorized aggregate is **not automatically entitled** to individual payroll rates, private account details, underlying confidential evidence or other teams' identities. Offer suitably redacted aggregation-level explanations. A revoked source must be removed from **current** economic projections and the previous aggregate explicitly invalidated until corrected; an earlier frozen projection is still inspectable under appropriate historical permissions and labeled with subsequent withdrawal/correction.

This exploration is **distinct from** the separate governance **Audit Explorer**. Governance audit answers *who changed what and when*; calculation provenance answers *why this business result has this value*. Reuse common revisions/events without conflating their UI or permissions.

## 10. Deployment & Access — selected users, verified actual use

From the opportunity analysis, an authorized actor can **explicitly select a candidate configuration and intended beneficiaries** (individuals or an eligible role/cohort). This creates a traceable deployment target; it does **not** automatically approve purchases, grant privileges or issue an access request just because a high-value cell was viewed.

Deployment tracking is separate from AI Compass users-and-roles management:

| Concern | Meaning |
| --- | --- |
| **Enterprise Technology Accessibility** | Company-wide catalog-level status of Model/Provider/Harness/Framework from the separate Pricing/Accessibility proposal. |
| **External Tool Entitlement** | Person's right/account/license/API or model permission needed to run a component in the chosen solution. |
| **Solution Readiness** | All required components, permissions, environment and setup verified together; an accessible component alone doesn't make the assembled solution usable. |
| **Confirmed First Use** | A real invocation/use has been explicitly confirmed, initially by an authorized person, potentially via future integration. This is the milestone for **deployed** classification in the opportunity simulation. |

Track requests/approvals and execution-oriented statuses, e.g. **proposed/eligible, requested, approved or rejected, provisioning pending, provisioned, access verified, first use confirmed**, plus suspended/revoked/expired where relevant. Exact state machine/approver permissions remain detailed design questions; don't add burdensome approval flows not yet selected.

A **flat-rate license** or **metered Provider access** is an entitlement to a **billable component/service**, not a unique license per every possible Model/Provider/Harness combination. Derive assembled solution readiness from all required component entitlements. Do not double-count shared accounts across configurations.

**Partial population deployment:** 6 of 20 beneficiaries with verified first use implies 6 potentially activated beneficiaries and 14 remaining, subject to evidence/eligibility. Update the **same opportunity view** automatically when this status changes, while preserving history. Requests, approvals, provisioning and verified access **alone** do not prove first use.

**Explicitly excluded now:** credential rotation/renewal, secret storage, license renewal workflow, automated purchasing, automatic creation of external accounts, and automatic provisioning. Design connector interfaces for **possible future** integrations, while keeping manual status updates usable.

## 11. Budget & Resource Planning — three separate purposes

The budget view derives needed **capability and quota** from existing data with as little form filling as possible. It is a **decision and request summary**, not a credit-wallet ledger or IAM credential controller.

| Budget section | What it represents | Population / main parameters |
| --- | --- | --- |
| **Experimental Budget** | Small pilot of a theoretically promising **Forecast candidate** before, or to support, real benchmarking. | User explicitly chooses candidate and **pilot headcount**; use sensible common pilot duration/defaults, allow essential overrides. |
| **Rollout / Deployment Budget** | Enable **benchmark-backed, selected but not yet access-covered** people to perform their workload using relevant configurations. | Derive role/person eligibility, annual Task frequencies, metered consumption, pre-existing rights and applicable licenses. |
| **Existing Usage Capacity (optional)** | Anticipated continued variable capacity / seats for people **already active**. | Include as separate planning segment when requested; **not a credential or license-renewal process**. |

**Experimental vs rollout** must be **explicitly distinguished** in summaries/exports/budget requests; they have different levels of evidence and intended use. Selecting a strong Forecast may require merely entering a **number of pilot users**; do not demand full per-person profiles, 36 separate form fields, or artificial mandatory manual tokens if known or derivable.

### Derivation

For a person or cohort, Task, configured solution, billable meter and selected planning period:

    required_meter_units_per_period =
        SUM(annual_task_frequency × estimated_meter_units_per_task
            × period_distribution_share)
        × (1 + optional_capacity_margin)

- Prefer actual **Benchmark metering** for the correct configuration/Task, and Forecast *usage predictions* when measured data are unavailable. A Forecast of **money savings alone is not a token/credit estimate**.
- Distinguish input, output, cached/reasoning tokens or other meter types **when the Pricing Offer demands them**. Never infer a token split from aggregate total tokens without a disclosed, qualified assumption.
- Convert to **provider- and offer-specific credit quantities**, not one interchangeable global credit. Do not mix incompatible currencies/credit units in a raw numerical total.
- Flat-rate/per-seat offerings: express **license or access required (yes/no per eligible person; aggregated seat count)** rather than inventing token usage. Hybrid: seat/subscription and metered capacity both.
- Aggregate across non-overlapping Tasks **for the same billing owner/offer** and deduplicate reused licenses/accounts; separately list other Providers/offers. Composite Framework calls require per-participant and orchestrator meters without double billing.
- Annual frequency is available; monthly/quarterly may start as **uniform distribution** clearly marked as assumption; known seasonal peaks may be supplied when relevant. An optional common **capacity margin** can be changed per scenario, without mandatory per-person setup.
- Show **estimate, unit, period, source maturity (Forecast vs Benchmark), assumptions and confidence/known gaps**. Never fake an unmeasured amount. If a required meter is unavailable, mark the budget line incomplete and ask only for the essential missing datum/qualified assumption at the point of need.
- Show optionally **reference monetary cost** using source-backed Pricing Offer and separate fixed/subscription charges; the planning budget is not identical to a Run's marginal profitability calculation.
- Respect the previous pricing decision: **do not allocate or track globally pooled/free-credit entitlements across campaigns**. Budget plans may sum requested capacities, but must not claim to know real shared Provider account balances or actual invoiced usage.

### Minimal user entry contract

**Automatically derive** job/specialty, person or cohort, role frequency, task baseline, configuration/solution, benchmark/forecast consumption, rates, license conditions, eligible/not-yet-covered beneficiaries and current readiness wherever records permit.

User input should normally be limited to: **explicit pilot candidate + number of trial users**, an optional change to pilot horizon/capacity margin, or an explicit rollout target/scenario. Exceptional custom inputs are optional and transparent. Do not require a separate form submission for every matrix cell, Task, employee and meter.

The budget view can pass an **explicitly approved** target and expected allocations to the Access view, and retrieve entitlement coverage from it, without auto-fulfilling requests.

## 12. Derived current state vs frozen historical decisions

**Current live projections** update when their effective inputs change; **historical simulations, selected deployments and issued budget requests** retain their own immutable revision/context.

Conceptually distinguish:

- **Workload & pricing inputs:** versioned authoritative source records;
- **OpportunityScenario:** scope, candidate choices, weighting and assumptions, with frozen revisions when saved;
- **OpportunityCalculationSnapshot:** one result/slice or aggregate with exact source version refs, rates, formulas, algorithms, outcomes and date;
- **DeploymentTarget:** deliberate selected configuration + population + purpose linked to an originating opportunity/scenario where appropriate;
- **ExternalEntitlement / AccessRequest / Verification:** person or cohort allocation/request, allowed transitions, actor/time and separate first-use evidence;
- **ResourceRequirement:** specific offer/meter/license, period, beneficiary cohort, estimate, Forecast/Benchmark provenance and a calculated version;
- **BudgetPlan / BudgetLine:** grouped experimental, rollout and optionally active-capacity lines, with exact assumptions and dated snapshots;
- **OpportunityHypothesis:** optional structured link to existing user Feedback/Ideas, Tasks and possible candidate configuration; idea submission alone is not measured value.

These are **conceptual responsibilities, not mandated table names**. Use stable typed identities, typed relations/FKs for core links, append-only revisions and explicit derived-model versions in accordance with the platform baseline. Computation provenance is a reusable domain service, not duplicated frontend-only calculation code.

When new data produce a different suggested plan, **do not silently edit previously selected candidate targets, approvals or resource requests**. Offer a new comparison/revision while retaining who approved/selected which original version.

## 13. Privacy, rights and organizational boundaries

- Display enterprise-wide knowledge and published evidence according to existing roles, but scope **employee-level workloads, hourly rates, entitlements, contact and access-request details** to authorized roles.
- A typical collaborator may inspect authorized opportunities and their own appropriate access status; managers/planners may see appropriately permissioned team/company aggregates. Sensitive individual rates and private records must **not leak via chart hover, source explorer, search, CSV export or cached aggregates**.
- Do not require access to the regular business workspace for maintenance-only operators. Keep this business planning module distinct from **Users & Access** (AI Compass account administration) and the governance **Audit Explorer**.
- Identity-linked workload and first-use statements are **planning/operational records**, not a requirement for detailed employee productivity surveillance. No passive reading/navigation tracking. Store verification attribution only as necessary; apply retention, correction, deletion and privacy policies.
- Future external integrations should be least-privilege, connector-specific and optional. Never store exposed credentials or grant real service permissions merely by updating a dashboard checkbox.
- Keep **Server vs Demo** separation and shared frontend/data-provider contracts: Demo uses independent clearly fake local data; Server accesses controlled persisted data. No automatic fake-to-real import.

## 14. Preliminary architecture and impact assessment

**Preferred approach:** extend the current modular Django/PostgreSQL architecture and shared frontend/data-provider design; don't add microservices merely for this feature. Suggested logical domains: **organization**, **workload**, **opportunity analytics**, **deployment/entitlements**, **resource planning**, with a cross-cutting **calculation provenance** projection/service.

| Area | Impact | Implications / dependencies |
| --- | --- | --- |
| **Organization / profiles** | **High** | JobRole, Specialty, cohorts/people, membership periods, rates, inheritance, individual overrides, confidentiality. |
| **Task taxonomy** | Medium | Stable Task joins, group rollups, avoidance of parent/descendant double-counting. |
| **Technology Watch / Forecasts** | **High** | Task-linked theoretical configuration/metrics including optional usable consumption estimates; publication/scope controls. |
| **Benchmark results / recommendations** | **High** | Match measured Task/TC/configuration evidence, representativeness/quality, failure handling, labor effort and per-meter usage. |
| **Pricing catalog (separate proposal)** | **High dependency** | Versioned offers, provider-specific credit conversions, fixed vs variable charges, no double billing. |
| **Opportunity engine / history** | **High** | Per-population task × candidate projections, provenance, blending, de-duplication, snapshots and delta attribution. |
| **Opportunity matrix frontend** | **High** | Two-dimensional virtualized Task tree × solution grid, intensity-only heatmap, single status icons, population filtering, expandable details. |
| **Deployment & external access** | **High** | Selected targets, person/component entitlement state, manual requests/approvals, verified access and first-use confirmation; future connectors. |
| **Budget/quota engine** | **High** | Pilot/rollout/active segmentation, unit conversion, allocation-by-period, metering estimates, minimal-entry UX. |
| **Cross-cutting provenance explorer** | **High** | Lazy traversal of versioned factor/source graph and calculation breakdown, privacy-aware API links. |
| **Security / privacy / audit** | **High** | Rights on rates and profiles, RBAC for approval/provisioning statuses, historical source transparency and redaction. |
| **Compatibility and migrations** | Medium–high | Additive schemas and empty Server records; preserve historical Runs with unknown / coarse token meters; never fabricate new observed values. |

For performance, compute large aggregates on the server, invalidate only affected derived projections, support asynchronous/incremental read-model updates **with explicit freshness timestamps and without falsely presenting stale data as current**. Read models can be cached or materialized without sacrificing immutable authoritative historical records.

**Dependencies on other future proposals:** Pricing/Accessibility supplies offers and enterprise access; Campaign Evaluation Matrix supplies improved Task/TC/evidence coverage; Composable Setup Guides helps operational rollout readiness; Data Governance Audit Explorer audits actual persistent modifications. They are **complementary, not duplicated**.

## 15. Recommended incremental delivery

Deliver a usable decision feature in increments while keeping the eventual architecture flexible:

1. **Foundations:** roles/specialties/person/cohort linkage, inherited workload frequencies, hourly valuation, stable Task mapping, permissions.
2. **Opportunity computation and core matrix:** Task × measured/theoretical configuration crosswalk, simple Forecast+Benchmark calculations, idea/unknown states, icon/heatmap separation, single-population scope.
3. **Three metric slices and historical snapshots:** mutually exclusive totals, graph, provenance-first drilldown and versioned computations.
4. **Candidate selection and deployment tracking:** explicit population/configuration targets, requests/approvals, verification and first-use confirmation, feedback to opportunity slices.
5. **Budget & Resource Planning:** Forecast-driven experimental pilot count, benchmark-driven rollout quantities, optional active-capacity view, source-backed quota/license requests.
6. **Refinement:** suggested portfolios/scenario comparisons, confidence/seasonality, more sophisticated economic assumptions, optional external integrations.

Stages are implementation guidance, **not extra user-facing mandatory approval phases**. Shared contracts should be designed early even if screens are introduced successively.

## 16. Acceptance criteria

1. Role and specialty workloads can be defined once, inherited by people, overridden individually, or explicitly excluded; missing ≠ zero; no duplicate addition from overlapping profiles.
2. Roles have versioned hourly rates, individual overrides are possible under appropriate access control, and aggregates do not expose restricted individual rate details.
3. Planning can include aggregated populations/pilot headcount without forcing accounts for every prospective beneficiary.
4. The matrix **rows** are an expandable Task taxonomy, **columns** are AI configurations (measured and theoretical), and the selected population determines values.
5. Each quantified cell's **background intensity only** represents potential profitability on a common legend; its **single icon only** represents deployment/benchmark/forecast/intuition status.
6. Truly **uncovered cells are blank** (no fill and no icon), whereas idea-only cells have an intuition icon and no fabricated quantified heat.
7. A deployed cell is recognized through **verified first use**, not mere permission or approved request. Partial deployment is visible and split appropriately in totals.
8. A measured+forecast candidate can show a **benchmark-dominant, explicitly weighted** projection while retaining both source estimates and evidence maturity.
9. Forecast-only Task × candidate projections can be shown without pretending the candidate is an existing measured AI Solution.
10. Failure, irrelevant coverage and missing metrics cannot be converted into unwarranted profitable benchmark results.
11. A submitted intuition appears without automatically creating a Task/To-Do, Watch Entry, Forecast, campaign or request.
12. A matrix cell opens a **small progressive inspector**; each factor can be clicked into its parent references, versions and original source with back navigation.
13. Aggregate values can be explored without unauthorized leakage of individual user records, private rates or restricted evidence.
14. The dashboard exposes **Activated Potential, Benchmarked Opportunity, Forecast Opportunity** and their sum as three **non-overlapping annualized estimates**, plus unquantified idea count outside the monetary total.
15. A configured scenario does not double-count the same user's workload by selecting multiple alternative solutions simultaneously.
16. New Forecasts, Benchmarks, profile/rate changes, tariff updates and verified deployment changes update **current** projections; show freshness/validity when processing is not immediate.
17. The historical chart preserves dated prior values and source/algorithm versions; it does **not** rewrite old estimates, measured Runs or evidence after new data arrive.
18. A historical point can explain transitions between slices and changes to underlying potential separately.
19. Saved scenarios and automated suggestions coexist; neither selecting a heatmap cell nor receiving a suggestion silently starts deployment.
20. Explicitly selected eligible users/cohorts enter a **separate Deployment & Access** view with component-level access requirements, request status and approval/verification tracking.
21. Actual first use can be manually confirmed, with attribution; external provisioning is not required for the feature to function.
22. The **Experimental Budget** supports choosing a high-potential Forecast candidate and pilot user count, deriving meter/license needs without mandatory repeated user/task forms.
23. The **Rollout Budget** derives unmet benchmark-backed eligible-user needs using measured per-task consumption, workload frequencies and accessible offer rates.
24. Already-active capacity is optionally included as a **separate** budget category, with **no credential renewal workflow**.
25. Token/credit budgets are grouped by **native compatible meter and Provider/offer**; incompatible credits cannot be summed as one generic credit balance.
26. Flat-rate products produce required-access/seat counts, hybrid products produce both seats and metered usage; fixed subscriptions stay separate from marginal Run profitability.
27. Unknown consumption or tariff information is explicit, never automatically estimated as zero or guessed from purely monetary Forecasts.
28. Budget summaries and lines support period, units, source, assumption and interactive provenance into Forecasts/Benchmarks and Pricing Offer revisions.
29. Existing data and published benchmarks remain valid; no bulk fake migration, forced Run revision or silent change to technical AI Solution identity.
30. API, matrix, exports and explorer enforce access rights consistently; Demo and Server continue as independent first-class runtime modes.

## 17. Remaining explicit design questions (not decisions)

- **Benchmark/Forecast combination policy:** chosen initial benchmark-dominant weighting (80/20 was illustrative), comparability and quality gates; sample statistics and interpretation of failures.
- **Simulation source eligibility:** published/qualified only by default vs workgroup-only opt-in access to preliminary/draft evidence; ensure private drafts never leak into general-user aggregates.
- **Aggregated populations and incomplete rosters:** when/how to allocate aggregate eligibility, adoption coverage and licensing without falsely claiming specific people are provisioned.
- **Entitlement approvals:** roles/approvers and allowed transitions; earlier discussion proposed configurable designated approvers but the user has **not confirmed** a specific approval policy.
- **Deployment scope:** whether partial first use promotes the primary cell icon immediately or a distinct partial variant; the underlying count and monetary slices must always be correct.
- **Pilot duration and default margin:** organization-level conventions, how many runs per pilot user, and minimum data required for a justified trial quota. User wishes to enter essentially just the pilot headcount where sufficient data already exist.
- **Missing meter usage in a Forecast or failed Benchmark:** how to represent bounded quota estimates or request an essential missing assumption without inventing observations.
- **Temporal distribution:** uniform period allocation vs per-job seasonal overrides for heavy bursts.
- **Cross-solution displacement:** exact net-incremental-gain accounting when replacing a currently deployed solution with a more attractive one.
- **Cash-vs-capacity and negative value:** precise summary treatment of costs, nonproductive periods and unfavorable AI Runs without hiding evidence.
- **Performance / historical storage:** incremental invalidation, snapshot cadence, change attribution, deep links and configurable retention/privacy.
- **UX legends/icons/accessibility:** icon artwork and heatmap color scale for zero, negative, unknown and accessibility needs; keep semantics fixed.

Resolve these during issue breakdown/design without forcing end users to fill redundant fields.

## 18. Explicit exclusions and boundaries

- **No merged all-in-one simulation/deployment/budget editor;** exactly three coordinated purpose-built views.
- **No credential renewal/rotation, password/secret custody, enterprise credit-wallet ledger, live invoice reconciliation, global shared-credit deduction, automatic licenses purchasing or mandatory external provisioning** in this domain.
- **No automatic To-Dos, assignments or mandated innovation pipeline** from heatmap intuition or Forecast presence.
- **No invented savings or quota** for intuition-only, missing data or noncomparable evidence.
- **No automatic rewriting of Run evidence, published Forecasts, historical pricing, original opinions or frozen historical simulation values.**
- **No assumption that deployment equates to realized cash savings.** Confirmed first use only changes the *activated modeled potential* classification.
- **No hardcoded required cloud identity provider or enterprise IAM integration**; reserve interface boundaries for future connectors.

This page defines the shared planning, evidence, eligibility and financial projection semantics consumed by Workgroup, Management and deployment/resource workflows.

## 19. Cross-feature ownership and current-vs-historical publication

**This source owns** workload-driven *prospective* economics, the Task-tree × configuration profitability heatmap, Forecast/Benchmark combination, non-overlapping Activated/Benchmarked/Forecast slices, historical economic snapshots, interactive calculation provenance, external access/deployment planning and resource/budget requirements. It does **not** own the authoritative Run publish/revoke/delete state, tariff-meter definitions, OS classifications or persona navigation chrome.

- [Publication & Information Lifecycle](publication-and-information-lifecycle.md) is the **authority for which Run measurements are currently publishable/active**, for correction/withdrawal and for orphan cleanup. This DAP engine consumes the centrally filtered **current effective** measured evidence; pending metering-incomplete Runs and withdrawn Runs contribute **no observed result**. An authorized correction or revocation invalidates affected current economic scenarios; do not let stale cached gains/quotas appear current while recomputation is pending. Prior as-of scenario snapshots remain historical with clear supersession/revocation context.
- [Technology Accessibility & Pricing](technology-accessibility-and-pricing.md) is the sole authority for registered Offers, billable meters, fixed vs variable charges and selected source price revisions. Budgets derive supported native-unit requirements from those data and available measured/Forecast consumption; they do not invent unknown units or manage live pooled provider credit balances.
- [OS Compatibility](os-compatibility-and-user-environment.md) is the sole authority for coarse Windows/Linux viability; consider an alternative OS as an **environmental prerequisite** rather than treating an incompatible person as already provisioned or as permanently ineligible.
- [Role-Based UX](role-based-user-experience-and-guided-navigation.md) owns personalized presentation/navigation. Methodology-derived measured suitability, not editable editorial preference, determines the automatically computed engineering shortlist. Explanatory editorial context and guide access appear next to measured results, but never override their methodological meaning.
- [Data Governance Audit Explorer](data-governance-audit-explorer.md) traces modifications by actor/time; DAP's **Evidence & Calculation Explorer** instead explains *why a derived monetary value is what it is*. They share source revision pointers, not a mandatory single explorer or a duplicate audit event stream.

This full DAP product direction remains future scope except **DAP-01**, the already delivered restricted workload-profile foundation. The reorganization establishes ownership, **not delivery order or issue approval**.
