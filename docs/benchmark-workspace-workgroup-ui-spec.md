# Benchmark Workspace — Workgroup view design contract

**Design reference:** [Campaign manager HTML](prototypes/benchmark-workspace/index.html) · [Campaign detail HTML](prototypes/benchmark-workspace/campaign.html) · [design handoff](prototypes/benchmark-workspace/DESIGN.md).

**Status:** user-reviewed candidate for future implementation. The existing [Campaign Evaluation Matrix](campaign-evaluation-matrix.md), [Campaign API](campaigns-server.md) and [Benchmark Workflow](benchmark-workflow.md) remain normative where not explicitly superseded by these new product decisions.

## Two separate pages

1. **Campaign manager** (`index.html`): searchable/filterable campaign cards presented primarily in the native lifecycle pipeline, **Planned → In progress → Under review → Published**; alternative sorted list view; ability to create and open campaigns. Opening a campaign navigates to the **full campaign page**, never an edit modal. Archived campaigns require distinct treatment.
2. **Campaign detail** (`campaign.html`): dedicated page with overview/objective/description, editable Tasks/Test Cases/solutions evaluation plan, Runs, and collaborative review/publication. Maintain breadcrumb and back navigation.

Both files are standalone demonstrations using fictional data, not the live frontend.

## Campaign scope: no forced mode

**Remove Task-centred and Solution-centred modes from the target UX.** A campaign freely combines **multiple Tasks**, their respective **Test Cases**, and **AI Solution configurations**. The authoritative planning unit remains Test Case × configuration (only applicable combinations per Task). The evaluation matrix presents selection/plan, pending/in progress/completed execution, optional non-selection and justified waivers distinctly. Runs represent measured attempts; a DoD failure does not negate that evaluation occurred.

**Backend gap:** existing persisted campaigns have mode-dependent fixed Task or model/provider/harness FKs. Real multi-Task/multi-solution campaigns require a reviewed additive schema/API migration, legacy compatibility, immutable revision-pinned associations and no destruction or silent reinterpretation of historical evidence. Do not simply hide required mode fields while using the unchanged Server API.

## Campaign detail structure

- **Overview:** name, objective, explanatory description, responsible person, linked Setup Guide/Watch where present and true campaign lifecycle status, with eligible lifecycle transitions.
- **Evaluation plan:** select or remove Tasks, choose or remove their Test Cases, assign configurations and inspect/edit the Task-grouped Test Case × solution matrix, with per-cell selection/waiver, run progress and history. Candidate combinations should only arise from real Task associations, not a global Cartesian product.
- **Runs:** list and inspect repeated executions, their recorded outcomes, evidence and review status; launch a new Run for a valid selected combination and enter the dedicated Run workflow rather than treating it as a trivial completed checkbox.
- **Review & publication:** multiple Workgroup participants may create **review threads**, reply chronologically with authors and timestamps, and independently set each thread's status **Open/Closed**, reversible with accountable history. Closing a thread does not approve the campaign; discussion status and overall campaign lifecycle/publication authorization are separate. Preserve all previous comments and reviewed/published snapshots.

## Acceptance conditions

- Manager works at 1366×900 and minimum desktop width 1024px; filters, sorting and pipeline navigation keep context. Campaign click opens the second page.
- Detail supports Tasks/Test Cases/configurations selection and editable matrix with obligations, waived explanations, execution evidence and immutable history.
- Runs remain attributable to exact pinned evaluation combinations, not just a loosely associated Test Case.
- Multiple authorized authors can discuss a review thread; status may be Open or Closed, not silently deleting comments.
- Server API and permissions enforce all writes, optimistic concurrency and publication_review; the UI cannot grant rights.
- Ensure no mode selector remains in either **target product view**; handle legacy mode in migration rather than deleting data.
- Open/inspect screenshots at 1366 and 1024 before visual sign-off. The prototype does not constitute completed production implementation.
