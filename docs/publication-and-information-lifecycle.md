# AI Compass — Publication and information lifecycle

**Functional reference:** eligibility, versioned campaign publication, corrected/withdrawn Runs and effective current evidence. See the [benchmark workflow](benchmark-workflow.md) and [campaign server](campaigns-server.md).

## Problem and principles

AI Compass is an evolving evidence repository: a Campaign/Run can be published, an original measurement can later be found wrong, a Run can be withdrawn, a published Campaign can be reopened, and published objects may evolve through new immutable versions.

The requirements are **both**:
- **Reliable current information:** a corrected or revoked source must promptly stop contaminating live Results Explorer, measured comparisons, automatic Task ↔ AI Solution ranking, current Recommendations context, Profitability/Opportunities, Deployment projections, Resource/Budget calculations and other dependent published views.
- **Reproducible historical meaning:** the original Run, raw evidence, Campaign publication revision, calculation inputs, source revision and audit trail remain identifiable **unless explicitly subject to a controlled physical purge or legal/security erasure policy**.

**A current-state view is not the same as a historical snapshot.** Do not achieve freshness by modifying past immutable records, and do not achieve immutability by leaving known-invalid results in current rankings.

This specification concerns *domain lifecycle* and resulting consistency. Governance Audit Explorer is only the **read/inspection interface for recorded changes**, not the subsystem that decides publication eligibility, performs revocation, computes ratings or physically garbage-collects files.

### Non-negotiable rules

1. **Soft deletion / withdrawal for ordinary users; no blind destructive cascading deletes.**
2. Corrections are explicit **new revisions/superseding values**, not silent mutation of original recorded experimental conditions.
3. **Run-level** withdrawal must be possible without automatically withdrawing every other Run in a Campaign.
4. **Campaign reopen ≠ unpublish:** the previously published validated content remains available while a new working revision is developed.
5. **Partial publication** of complete, eligible Run results is permitted; incomplete attempts are durably retained but not published, ranked or economically treated as observed outcomes.
6. A **valid failed-DoD experiment** can be published as negative evidence; it must never automatically become a positive recommendation.
7. Published read projections must apply **current authorized corrections/revocations**, even if their original publication snapshots remain historically inspectable.
8. Referenced evidence files are never blindly unlinked or erased just because one business object is hidden or archived.
10. "Orphan" is a provable domain/storage condition, **not** merely "nobody has linked to this meaningful standalone catalog object yet." Preserve all necessary current, historical and legal references.
11. Source revisions/evidence are owned once; affected domain projections are derived, invalidated and recomputed through consistent shared rules.
12. All changes respect RBAC, original evidence access controls, published/draft visibility and the permanent Server vs Demo separation.

## Distinct lifecycle operations and expected impact

| Operation | Current public business view | Stored source/history | Preconditions & authorization |
| --- | --- | --- | --- |
| **Edit an unpublished draft** | No impact until explicitly published, apart from authorized Workgroup preview | Append version/revision as appropriate | Existing editor and optimistic concurrency rules |
| **Correct an already published declared value** | **Immediately** use the new authoritative corrected revision in current projections; invalidate/recompute dependents | Original declaration, correction author/time/reason where domain needs it, raw evidence and historic revisions remain | Authorized correction with audit; server validates source identity/revision |
| **Reopen a published Campaign** | Keep **last valid published subset** accessible; new Tasks/Runs/plan changes are not automatically public | New working revision and old published revisions coexist | Existing campaign lifecycle + expected_revision |
| **Republish a Campaign** | Atomically move to a new published **eligible subset** after checks; new content becomes available | Earlier publication membership/snapshots remain | Existing review/publish rights, documentary and evidence rules |
| **Withdraw a single published Run** | **Immediately exclude** that Run from all current public results/scores/ranking and all projections using active evidence | Historical Run and withdrawal event/reason remain restricted to permitted historical views | Explicit authorized Run-level withdrawal; neither silently deletes its Campaign nor other Runs |
| **Unpublish / recall whole Campaign** | Withdraw its current published membership; other campaigns may continue supporting shared AI Solutions | Historical publication/decision and source evidence preserved | Existing authorized Campaign unpublish semantics extended to read models |

**Subtle but required distinction:** a published Campaign has a **frozen publication snapshot**, whereas a **current effective published view** is its authorized still-active published membership filtered through later corrections and revocations. The historical snapshot says *what was announced then*; the effective projection says *what can be trusted and used now*. Ordinary public readers must never bypass a withdrawal by querying an older "historical" endpoint; any historic access is permission-filtered and prominently labeled, subject to revocation/erasure policy.

Corrections to published measured values are a **specific approved correction operation**, not general editing of draft Campaign contents. They can become effective without republishing the Campaign while the independent source revision/audit remains visible. New evaluation scope and newly completed Runs remain private until the explicit publish action.

## Run lifecycle, pricing-dependent evidence and partial publication

### 3.1 Pricing choice drives meter fields (owned by Pricing feature)

- Workgroup chooses among **actual applicable commercial offers** for the configuration **before executing that Run**. The offer/revision is pinned; alternate vs cumulative charge lines cannot be double billed.
- The **Run form derives its consumption fields directly from the chosen offer's billable meter definitions**: e.g. credits, input tokens, output tokens, reasoning/cache tokens, requests, GPU time or other native units, only where relevant to the offer.
- Flat-rate-only licensing/subscription does **not** require a fabricated per-Run usage meter. Fixed subscriptions are displayed separately from marginal measured Run cost. Hybrid offers need only their deterministically billable variable counters.
- If the commercial terms are unregistered or essential pre-run offer information is incomplete, follow Pricing's agreed **pre-start gate**: Campaign and draft Test Cases may exist; the affected Run cannot start under an unresolved commercial plan.
- If the Run *was* started under a fully described plan but observed consumption later proves unavailable, **preserve all already entered setup, interactions, human/agent timings, produced artifacts, known quality data and original evidence**. Missing is not zero, and is not a manufactured tariff default.

### 3.2 Separate "recorded" from "publishable"

A Run/execution can have several orthogonal facts:

- **Draft/in progress/incomplete (pending):** recorded evidence exists, possibly missing a selected offer's required metering, experiment fields, DoD, artifacts or other actual completion prerequisites. Still recoverable/editable by its owner within the allowed lifecycle; **not publishable**, never silently discarded.
- **Complete individual Run:** required setup/method/evidence/metrics satisfied, including price-relevant meters or genuinely not-applicable metering. It may have passed **or failed** DoD. It can be **included in an authorized publication** provided its exact guide/recipe readiness and other release gates are met.
- **Published / active:** included in an eligible published Run membership and not currently withdrawn/revoked.
- **Withdrawn/revoked:** retained historically subject to permissions, but excluded from all current published-result read models.
- **Superseded correction:** original declared metrics still exist as historic evidence; currently eligible value is the authorized corrected revision unless revoked.

**Unknown cost meter** ≠ **Failed DoD**. A complete unsuccessful benchmark with known required measurements remains valuable publishable negative evidence. A cost-incomplete attempt is **pending**, even if a quality score or outcome was already entered.

### 3.3 Partial publication contract

A Campaign may publish a **subset** of complete, guide-covered and otherwise eligible Runs even when other planned evaluations/sessions remain incomplete. This supersedes the proposed global "all selected combinations must be completed/waived before any publication" behavior in [Campaign Evaluation Matrix](campaign-evaluation-matrix.md).

- Define **exact published membership** (specific Run IDs and eligible revisions, Test Cases/configurations, relevant campaign/review and guide references) in a versioned publication manifest/decision. Conceptual contract, not mandated physical table.
- Show counts separately: candidate combinations, selected obligations, complete/evaluated, incomplete/pending, waived, publishable, **included in current publication** and excluded/withdrawn. **Partial coverage is explicitly labeled**. A partially published campaign is not misreported as fully executed/qualified.
- For publication, a Setup Guide/recipe must be valid for **each configuration actually included**. Incomplete/unpublished attempts do not create blocking guide obligations for the published subset.
- A complete Run with **failed** DoD can be included as valid **negative evidence**; quantitative ranking/gain rules handle failure honestly.
- Missing-meter executions remain editable/pending. Reopening the Campaign permits completion of them, new Runs or additional Test Cases; the earlier publication remains effective until the next explicit publication action or direct revocation.
- A re-publication must not silently discard previously published still-valid evidence merely because new work is incomplete. Explicitly version the changed membership and reasons for any deliberate exclusion/revocation.
- Do not silently relabel a partial Campaign publication as final completion of the full planned experimental matrix, and do not assert a measured AI Solution score from a pending attempt.

**Implementation integration:** Campaign Evaluation Matrix owns the UI/planning obligation states; Pricing owns tariff/meter schema and pre-start choice; Composable Setup Guides owns documentary readiness; **this lifecycle contract owns membership, partial publication, withdrawals and resulting visibility**. Avoid duplicating those state machines in each frontend module.

### 3.4 Results of a corrected vs revoked Run

Suppose Campaign publication P1 includes Runs A and B:

1. Reopen Campaign and draft Run C. **A and B remain in the effective published set**, C does not.
2. Correct erroneous *declared* consumption of published Run A through a permitted correction action. Its **current effective metric and derived costs/rankings recompute**; P1's original measurement and original statement remain inspectable by authorized historical viewers.
3. Withdraw Run B because its measurements are invalid. **B immediately stops contributing** to active public measured averages, task-specific automatic rankings, publications' effective read models, Forecast/Benchmark economic blends, deployed opportunity estimations and budgets.
4. Complete C but leave D incomplete. Publish P2 with **A (corrected) and C**, explicitly leaving D pending.
5. If B was the sole supporting published Run for a measured configuration, that configuration's measured historic identity remains but it no longer claims **currently published qualifying evidence**. Other independent published Runs can still support it.

Recalculation should preserve original as-of snapshots and permit explaining why current output changed. An editorial Recommendation pinned to an invalidated Run **cannot silently remain an unqualified positive public assertion**: mark it stale/needs review and suppress/qualify its applicability in current automatic advice; do not retroactively rewrite its published historic content or make an editorial override over measured methodology. Exact public descriptive-display policy should be checked during implementation.

## Recalculation, visibility, references and consistency guarantees

**Causal dependency impact:** identify current read models and derived figures dependent on modified/revoked source revisions, including:
- Campaign/Results Explorer, Test Case × configuration coverage, measured performance/quality/utilities, score methods;
- AI Solution qualification and user-specific Task suitability **computed from active eligible evidence**;
- published Recommendation descriptive context, freshness/review-needed flags, source inspection;
- DAP Profitability current heatmap, Activated/Benchmarked/Forecast opportunity slices, scenario projections and current budget/resource calculations;
- links in Workgroup Studio, My AI Workspace, Management Insights and published Workgroup updates; prospective source-dependent results.

The system must **commit correction/revocation and eligibility/visibility change atomically** for authoritative current reads, or use an equivalent fail-closed consistency boundary. Immediately after withdrawal succeeds, ordinary APIs must no longer serve B as active published evidence, even if asynchronous derived aggregates still need recomputation.

For expensive projections, invalidate/mark stale the previous calculated view and rebuild asynchronously with **explicit freshness/version**. Do **not** keep serving a stale positive ranking/economic number as current when it depends on a withdrawn source. If recompute fails, report not-current/unavailable as appropriate rather than silently use invalid data.

Use stable typed object IDs, pin exact source revisions where required, a dependency projection/index where justified, versioned calculation methods and existing immutable audit records. Reuse APIs/services for source eligibility across views; do not implement independent inconsistent filtering per page.

**Historical read semantics:** old frozen Campaign publication manifests and economic snapshots preserve what was known *at that time*, with provenance and correction/withdrawal annotations. Historical audit access follows rights, explicit deletions and special erasure constraints; no direct file URL or earlier revision may circumvent current revocation/access restrictions. Explain differences between historical measured raw facts, superseding declared values and current recalculated interpretations.

**Concurrency:** reuse optimistic expected_revision/HTTP 409 behavior, immutable revisions and transactional updates. Permissions for correction/withdrawal may be domain-specific; UI actions require explicit intent/reason where materially changing published meaning, **without making routine unrelated edits require new audit paperwork**.

