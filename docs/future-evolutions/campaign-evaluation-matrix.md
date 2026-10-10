# Future evolution — Campaign Evaluation Matrix

> **Status:** Proposed feature; product decisions captured, not an implementation claim.  
> **Discussed:** 2026-10-10  
> **Area:** Benchmark Workspace / Campaigns  
> **Intent:** Preserve the agreed behavior for later refinement, issue breakdown, and implementation.  
> **Related baseline:** [Product Definition](../product-definition.md) · [Benchmark Workflow](../benchmark-workflow.md) · [Campaigns Server](../campaigns-server.md) · [Test Cases Server](../test-cases-server.md)

## 1. Summary

A campaign has a clearly defined **evaluation objective** and may assess **any number of AI Solutions against multiple engineering Tasks**. The campaign's execution plan is not a direct Task × Solution benchmark. Instead, users associate AI Solutions **with Tasks** and select one or more of each Task's **Test Cases** for each solution. **Actual Test Runs execute Test Cases against configured solutions**.

The Benchmark Workspace should expose a central **Campaign Evaluation Matrix** with a row per Test Case and a column per AI Solution (groupable/filterable by Task). It must show execution obligations, progress, deliberate non-selection, and justified waivers at a glance.

The matrix is **incrementally editable**, including after a campaign has been closed/published and subsequently reopened. Revisions and earlier closure/publication snapshots remain auditable and immutable; previously recorded evidence is never rewritten.

## 2. Domain distinctions — do not conflate these

| Concept | Meaning | Role in the campaign |
| --- | --- | --- |
| **Task** | A node in the extensible engineering-work taxonomy; it classifies a type of activity. | Select and organize the evaluation scope; aggregate results. |
| **Test Case** | A concrete, reusable, versioned experimental challenge linked to a Task, with inputs, constraints, expected outcomes and Definition of Done (DoD). It is **not** a Task subtree/category. | Define the challenge actually executed. |
| **AI Solution** | The identified configuration/capability under evaluation (model, provider, harness, settings and pinned versions, with existing catalog semantics). | Chosen **for a Task** and evaluated against selected Test Cases. |
| **Campaign evaluation combination** | One selected-or-candidate **Test Case × AI Solution** pair in a specific campaign plan/revision, with an identifiable decision and execution requirement. | Track selection, planning, waiver, coverage and associated runs. |
| **Test Run** | An actual execution attempt using a defined Test Case and solution configuration, recording outcomes, measurements and evidence. | Produce experimental results; repeatable for the same combination. |

Example Task taxonomy: Software Development → Embedded Software → MCU → Driver Development → KSZ8851SNL Driver. Test Cases TC1, TC2 and TC3 can exercise different concrete challenges of that Task; they are **instances**, not functional taxonomy levels. Implementation, robustness and regression can be acceptance/evaluation criteria, not mandated Task categories.

The existing system also supports **Frameworks** and composite collaborative runs. How a collaborative workflow is represented as a matrix column is an **open design question** (section 9), not a resolved change to the meaning of an individually measured AI Solution.

## 3. Campaign scope and matrix generation

1. The campaign owner defines an **objective**, selects one or more **Tasks**, and associates an arbitrary number of **AI Solutions with each Task**. Solutions need not be the same for every Task.
2. For each **Task × AI Solution** association, the user can choose **one or several relevant Test Cases** belonging to that Task; different solutions can use different subsets.
3. The UI builds the **candidate Test Case × AI Solution combinations** from the solutions assigned to each Task and that Task's eligible/available Test Cases. Do not take an indiscriminate global cartesian product across unrelated Tasks.
4. **By default, candidate combinations are selected for evaluation**, and each selected combination carries an obligation for **at least one Test Run**. Users can explicitly deselect individual combinations.
5. A **Not Selected** combination remains represented/derivable in the matrix, but visually understated, with **no outstanding execution expectation**. Optional selection notes may be supported.
6. A selected combination may have **several Test Runs** (repetition, further investigation, confirmation, reproducibility). Failed experimental results remain valid evidence and must not be confused with a failure to execute the required run.
7. Adding a Task, an AI Solution, or a Test Case updates the candidate matrix, proposes the newly applicable combinations as **selected by default**, and lets the user deselect or waive them explicitly. Existing selections and historical outcomes are preserved.
8. The current plan must remain revisable while in progress or reopened. Changes must preserve earlier revisions and historical references.

The exact behavior of bulk Task-tree selection (including descendants), Test Case applicability filters, and minimum-run policies beyond the default of one remains open.

## 4. Three distinct decisions; execution is a separate dimension

| State / decision | Meaning | Justification | Blocks full-plan completion? | Matrix presentation |
| --- | --- | --- | --- | --- |
| **Not Selected** | Candidate combination intentionally left out of the evaluation scope. No Test Run is expected. | Optional | **No** | Discreet / muted, but visible |
| **Planned / Pending** | Combination selected; its required Test Run(s) have not been completed. | Not applicable | **Yes for full plan**; does not block a partial publication of other valid Runs | Prominent outstanding obligation |
| **Waived** | A previously selected combination is **explicitly released from its execution obligation**, for example because it is no longer promising. | **Mandatory explanation** | **No** | Distinct waiver status and reason |
| **In Progress** | A selected combination has an active attempt but has not fulfilled the completion criterion. | Not applicable | **Yes for full plan**; not a reason to publish its incomplete attempt | Progress indicator |
| **Evaluated / Completed** | The defined minimum execution obligation is fulfilled and recorded. This is **not** equivalent to an AI Solution passing the Test Case or being recommended. | Run evidence / outcome | **No** | Completion indicator and run links |

**Critical distinction:** Deselecting *before or during planning* is not a waiver. **Waived** is an auditable, motivated decision to stop expecting an evaluation **previously included in the plan**. If runs already exist, their outcomes and immutable evidence remain available after a waiver.

Model **selection/waiver decisions independently of execution status** where practical: a run may fail its DoD without implying the planned evaluation was not performed. Record waiver author, time, explanation, relevant plan revision and history. Permit reactivation through a new revision, not by erasing the old waiver.

## 5. Frontend reference — Evaluation Matrix

**This table is a functional reference for the intended Benchmark Workspace UI**, not merely report output. Rows are Test Cases, columns are AI Solutions, grouped/filterable by Task. Keep the status and justification directly discoverable from the corresponding cell.

**Example — Task: Develop an Ethernet driver**

| Test Case | Solution A | Solution B | Solution C |
| --- | --- | --- | --- |
| **TC1 — Implement driver** | ✅ Evaluated | ⏳ **Pending** | *— Not Selected* |
| **TC2 — Correct injected defect** | ✅ Evaluated | ⊘ **Waived**¹ | ✅ Evaluated |

¹ **Waiver explanation — TC2 × Solution B:** “Early evidence from comparable trials suggests limited promise; additional evaluation cost is not justified.”

**Full evaluation plan remains incomplete:** TC1 × Solution B is pending. A reviewed **partial publication** can nevertheless include the already complete, properly documented Runs of other selected combinations. Pending Runs are not published or counted as evaluated. Not Selected and Waived have no execution obligation.

Frontend behavior to retain:
- Always provide an intelligible view of all candidate combinations, including muted **Not Selected** cells (with optional visibility controls for large matrices).
- Click/open a cell to view associated Test Runs, measurements/evidence, decision history and any waiver justification.
- Provide explicit actions to **select/deselect**, **waive with mandatory justification**, **reinstate**, and launch/add Test Runs where permitted.
- Support **adding AI Solutions and Test Cases at any time**, multi-Task grouping, filters, bulk actions where useful, and highlighting of **new combinations** after a plan revision.
- Clearly surface outstanding **Pending/In Progress** obligations and **full-plan completion** separately from **publishable Run subset** readiness; an incomplete combination must not prevent publication of independent eligible results. Do not mark a waived, unselected or incomplete cell as a completed experiment.
- Distinguish candidate coverage, selected obligations, executed evaluations, outstanding evaluations, and waived evaluations in counts and reporting.
- Keep the operational editing UI in **Benchmark Workspace**; the **Dashboard remains read-only** under the existing information architecture.

### Coverage and completion semantics

Report, at minimum, separate counts for **all candidate combinations**, **Not Selected**, **selected and pending**, **In Progress**, **Evaluated**, and **Waived**. Do not inflate experimental coverage by counting waived or non-selected cells as measured results. A useful distinction is theoretical candidate coverage versus fulfillment of the **selected plan**; both metrics need explicit denominators.

An eligible selected combination counts toward **full-plan completion** only when the defined minimum Run obligation is fulfilled **or** an active justified waiver exists. A Not Selected combination has no execution obligation. **Full-plan completion is independent of the ability to publish a complete, documented subset of Runs**. Pending/incomplete attempts remain durably editable and **excluded from the published result set**; no published completeness count may imply the whole plan was evaluated.

Existing workgroup publication/review permissions remain. The publication action must validate the **explicitly selected subset of completed Run evidence**, including the compatible Setup Guides, regardless of other pending attempts in the same plan. An implementation must adapt the existing Close → Under review → Publish transitions as needed to support a **partial campaign publication without falsely declaring full-plan completion**. **A published failed-DoD complete Run remains negative evidence, never proof that a solution passed its test.** See [Publication & Information Lifecycle](publication-and-information-lifecycle.md).

## 6. Campaigns evolve after closure

A campaign keeps its **permanent identity**, but its **evaluation plan changes through immutable revisions**. Reopening an already closed/published campaign is explicitly supported for new Tasks, AI Solutions, Test Cases, or additional evaluations, followed by a subsequent closure/review.

Illustrative lifecycle:

1. **Revision 1:** Three solutions and four Test Cases are evaluated as planned; campaign is reviewed/closed or published.
2. **Reopen → Revision 2:** Add a fourth AI Solution and its applicable Test Case combinations. The new plan has new pending obligations; prior closed revision remains inspectable.
3. **Close/review again:** Fulfill or waive every new required combination under the current revision; retain all previous runs and evidence.
4. **Reopen → Revision 3:** Add new Test Cases to confirm or challenge prior conclusions; assess new obligations without rewriting earlier findings.

Rules:
- Existing campaign public ID and historical revision references do not change.
- Retain **every previous closure/review/publication decision** and exact historical plan/scope snapshots.
- Existing Test Runs, associated configurations, pinned Test Case revisions, results and evidence remain **immutable**.
- Do not silently re-pin an existing Test Case or AI configuration because its source catalog entry changed; deliberately selecting a new revision is a traceable change.
- Reopening is **not** equivalent to deleting or retroactively invalidating previous conclusions. Preserve the existing rule that reopening published campaigns does **not by itself unpublish earlier evidence**; surface current revision versus previously reviewed/published evidence distinctly.
- Completion of a new plan revision is independently checked before its next closure/publication.

## 7. Preliminary impact analysis (non-binding design)

| Area | Likely impact | Notes |
| --- | --- | --- |
| Campaign domain | **Medium–high** | Multiple Task → AI Solution associations, versioned planning scope, matrix obligation model; reconcile current task-centred vs solution-centred methods. |
| Planning/evaluation entities | **High** | Candidate identity/decision, planned obligations, optional exclusion, waiver reason and history, repeat runs. Conceptual separation between `CampaignTaskSolution` and `CampaignEvaluation` is suggested, **not mandated**. |
| Test Cases and runs | **Medium** | Link runs to exact combination and pinned Test Case/configuration; retain independent, immutable measured run identity and evidence. |
| Backend/API | **Medium** | Query/build matrix, bulk generation, selection/waiver/reinstatement, revisioning, locking/optimistic concurrency, validation and closure checks. |
| Frontend | **Medium–high** | Primary interactive matrix, Task grouping, filters, status/detail cells, justifications, additions and reopening. |
| Analytics/reporting | **Medium** | Candidate vs selected vs executed coverage, waiver rates, Task-level aggregation, historical revision comparison. |
| Security/governance | **Medium** | Existing business permissions, publication-review authority, attributable waiver decisions and audit integrity. |
| Migrations/compatibility | **To assess** | Preserve existing campaigns/method versions, Demo/Server isolation and published run evidence; prefer additive schema evolution. |

**Important existing-system constraints:**
- Current Server campaign methods include **task-centred** and **solution-centred** with presently fixed scopes; this future multi-Task/multi-Solution selection requires explicit compatibility and migration design rather than assuming it already works.
- Current catalog distinguishes an **AI Solution established by measured runs** from draft/candidate configurations. The planned selection UI must support eligible candidate setups without fabricating measured results or measured-solution identities.
- Current lifecycle terminology is **Planned → In progress → Under review → Published**, with reopening supported. The feature should work within or deliberately evolve this workflow without losing review/publication semantics.
- **Framework** participant and composite collaborative run attribution needs explicit treatment; avoid representing a Framework itself as an ordinary individual model/provider/harness trio.

## 8. Draft acceptance criteria

1. Selecting **one Task**, **3 AI Solutions**, and **2 linked Test Cases** yields **6 candidate combinations**, all selected/planned by default.
2. Deselecting one marks **Not Selected**, keeps a discoverable muted cell and removes its execution obligation.
3. Waiving another previously selected combination **requires an explanation**, records actor/time/revision and removes its execution obligation without recording an artificial failure.
4. Three combinations with completed recorded run(s), one Pending, one Not Selected and one Waived produce a **blocked closure**, because the selected Pending combination still requires execution. Completing the outstanding run removes this specific blocker, subject to normal review/publication rules.
5. A completed execution with **failed DoD** is an evaluated attempt and retains its negative evidence; the run is not silently treated as absent.
6. Reinstating a waived combination returns its required evaluation to the current revision, preserving the waiver history.
7. Different AI Solutions assigned to the same Task may have **different selected Test Case subsets**.
8. Adding a Test Case or AI Solution while the campaign is open creates newly applicable candidate combinations, selected by default, with no change to previous runs or historical pins.
9. A closed/published campaign can be reopened, enriched and subsequently closed/reviewed again; previous revision snapshots, publication decisions and run evidence remain queryable and unchanged.
10. The frontend exposes matrix statuses, waiver explanations, new-combination indicators, clear closure blockers and distinct coverage statistics.

## 9. Open questions — not decided in the discussion

- Should selecting a parent Task include descendants, and how are Test Cases proposed across such a hierarchy?
- What constitutes an **eligible** Test Case for a particular Task × Solution pairing beyond Task membership? How are zero-Test-Case draft selections represented?
- Should bulk defaults be configurable, and should changing a Task's Test Case catalog offer opt-in/automatic inclusion for already active campaigns? Newly **explicitly added** Test Cases are proposed as selected by default.
- How should **Framework multi-participant collaborative evaluations** and composite runs appear in matrix columns and obligations?
- Who can authorize **Waived** decisions (campaign owner, contributors, designated reviewer)? Is additional approval ever required?
- Which existing Close → Under review / Publish transitions need adjustment to support **partial publication of eligible Run membership** while the Campaign still contains pending obligations? This is an implementation detail; **all-or-nothing campaign publication is no longer the desired product rule**.
- Is one recorded, finalized Test Run always sufficient, or can a campaign prescribe repetitions or stricter completion requirements?
- How are matrix dimensions and bulk actions displayed efficiently at very large cardinality?
- How should existing historical campaigns with a fixed task/solution mode be projected into the new matrix without semantic reinterpretation?

## 10. Boundaries

This page is a **future feature specification**, not an implemented behavior, a migration instruction, or authorization to alter the current campaign workflow. It records the decisions reached in the conversation and marks remaining design questions as open. Implement it through separate issues/PRs, while preserving existing architecture, identity, audit, permission and evidence guarantees.

## 11. Integration and source-of-truth boundary (consolidated)

This document owns **campaign planning and the Test Case × candidate configuration matrix**: selection, deselection, waiver, pending, in-progress, evaluated and **full-plan completion**. Its historic snapshots and exact Run refs remain immutable. A **configuration candidate before first Run** is a versioned selection/configuration reference, **not yet a measured AI Solution ID**; first controlled Run may register the measured Solution identity while preserving the candidate link. Collaborative Framework metrics remain composite.

The cross-cutting [Publication & Information Lifecycle](publication-and-information-lifecycle.md) owns **publication membership and partial release**, Run-level withdrawal/revocation, corrections and read-model visibility. The plan can remain incomplete even when a reviewed, documented subset of finalized Runs is published. Selected Pricing Offers drive the dynamic Run consumption fields (see [Technology Accessibility & Pricing](technology-accessibility-and-pricing.md)); [Composable Setup Guides](composable-setup-guides.md) validates the exact configurations **included in each publication**, not abandoned/unpublished attempts. These contracts supersede the older all-or-nothing closure/publication wording but do **not** erase waiver history or lower the standard for Runs that are actually published.
