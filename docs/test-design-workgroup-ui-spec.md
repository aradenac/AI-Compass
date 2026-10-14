# Test Design — Workgroup UI specification

**Design decision (October 2026):** simplified two-pane Test Design experience, approved as a prototype direction. **Prototype:** [interactive HTML](prototypes/test-design/index.html) · [handoff](prototypes/test-design/DESIGN.md) · [prototype convention](prototypes/README.md).

**Related normative domain models:** [Test Cases Server](test-cases-server.md), [Task Explorer view](task-explorer-workgroup-ui-spec.md), [Campaign Evaluation Matrix](campaign-evaluation-matrix.md), [Guided Benchmark Workflow](benchmark-workflow.md). These retain authority for data integrity, stable IDs, access and campaign semantics.

## Purpose and layout

A Workgroup member can find existing Test Designs (persisted domain **Test Cases**), create a Test Design belonging to a real Task, inspect/edit its challenge definition and see where it is used in campaigns.

**Left pane — find:** reuse the same hierarchical, collapsible Task taxonomy presentation as Task Explorer, with permanent Task leaves and expandable category nodes. Test Designs are linked to Tasks, **not inserted as child Task nodes**. Search and filters must apply to both Task discovery and Test Design discovery, including inherited configurable phase, specialty and other Task label families. A Task may hold multiple Test Designs. Show clearly which Task is selected and list its matching designs. Keep the expansion state stable across selection and filtering.

**Main pane — define:** selected Test Design title, parent Task reference and the existing challenge fields: objective, inputs, constraints, expected outputs and **Definition of Done**. Provide optional evidence attachments, creation/edit actions and clear saved/unsaved states. Preserve immutable evidence history and backend access controls. The parent Task identity of an existing Test Case remains fixed under the current backend contract; do not simulate arbitrary reparenting.

At the **bottom of this main pane**, a modest, read-only **Associated campaigns** section lists campaigns that actually include this Test Design and each campaign's **own native status** (e.g., Planned, In progress, Closed as defined by Campaign). Never infer a campaign status from evaluation coverage or map matrix states into it. Campaign links navigate to the real authorized campaign workspace. An empty state must be explicit. The association must be derived from precise Test Case references and the campaign's current plan/revisions, respecting visibility.

## Exclusions decided in the prototype review

- **No statistics strip:** no summary counts of Test Designs, Tasks covered or other KPI cards.
- **No reset-demo action** in the view (it is a prototyping utility, not a product feature).
- **No right-hand attachment/coverage panel** and no dropdown to inspect one campaign.
- **No AI Solution coverage or Test Case × Solution matrix** in this view; that belongs to Benchmark Workspace.
- **No visible Test Case versions or forks**, including create-fork actions, fork-lineage tree and displayed semantic version strings.

The remaining top action may provide **Create Test Design**, contextual to the selected Task or with mandatory Task selection. No separate application-level header/footer/side navigation belongs inside the prototype.

## Data/compatibility boundary: UI suppression is not historical deletion

Existing Server Test Cases have immutable CatalogRevision history and fork-parent/version linkage. **Do not delete, overwrite, sever or silently migrate those records simply because the UI no longer presents versions/forks.** Preserve stable IDs, revision-pinned campaign and evidence references, optimistic concurrency and existing API compatibility.

The desired simplified *user experience* removes visible fork/version management. If the product later decides to eliminate these constructs from the domain model, that requires a **separate reviewed design and migration**, with explicit handling of already referenced Test Case identities and benchmark evidence.

Similarly, edits of a Test Design referenced by historical runs or campaigns must never silently reinterpret measured historical evidence: preserve immutable snapshots and original links; surface potential consistency implications when appropriate without creating a mandatory new workflow.

## Acceptance

1. Compare Task tree, expansion affordances and category behavior against the [versioned Task Explorer prototype](prototypes/task-explorer/index.html); reject conflicting tree presentations.
2. Verify Task and Test Design searches and cumulative filtering without altering the permanent taxonomy.
3. Verify creation, editing, required objective and DoD, optional attachments, genuine Task association and backend revision/conflict rules.
4. Verify associated campaign list matches real inclusion and displays each campaign's **native status**; no solution coverage/waiver/status reinterpretation.
5. Confirm all excluded controls/panels/counts and fork/version text are absent from the visible view.
6. Test desktop Chromium at 1366×900 and minimum 1024px; inspect actual screenshots and keyboard access, not only automated pass/fail.
7. Test Server authorization, restricted campaign visibility, historical run integrity, Demo isolation and archive/revision compatibility.

The standalone HTML uses sample data and is not a production API implementation. Its approval does not claim that the full Server view has been built.
