# Task Explorer — Workgroup taxonomy and classification UI specification

**Status:** approved prototype direction, pending business schema and authorization implementation. The [interactive HTML prototype](prototypes/task-explorer/index.html) and [design handoff](prototypes/task-explorer/DESIGN.md) are versioned reference designs, not production UI.

## Product model
Every **Task is a leaf** in a permanent, navigable Task taxonomy. Internal nodes are categories (not executable Tasks). Each Task has one authoritative location and stable ID; rearranging categories or moving a Task must preserve immutable history, existing Test Case, Campaign, Run, evidence and public-ID references. No Task can acquire descendants.

The permanent taxonomy is **independent** of configurable multi-valued classifications. Tasks can bear zero or several labels in each editable family:
- **Project phase:** RFQ, Architecture, Design, Qualification, Maintenance (examples only; membership may overlap).
- **Profession and specialty:** multiple job families and specialties per Task, e.g., Software, Embedded, Zephyr or Linux.
- **Additional user-defined families:** e.g., cross-functional subjects such as voice transcription or meeting notes.

A category in the permanent tree is **not the same concept** as a label family. Do not duplicate a Task to represent multiple memberships. Editing a family or label must not silently rewrite the permanent tree.

## View layout
A useful-content-only desktop view (1366×900 reference, from 1024px), in three panes:
1. **Left:** searchable, expandable permanent taxonomy, optional grouped-by-label projection, cumulative multi-axis filters, drag-and-drop reorganization.
2. **Center:** selected Task title, description, original human effort estimate (hours, with clear unit), optional attachments and traceable linked domain objects.
3. **Right:** editable multi-select label families and values; taxonomy/label-family administration tools accessible to authorized Workgroup users.

Creation and editing should preserve selections and unsaved drafts. Users can create Task leaves, create or rename category nodes, reorganize them, and add/edit/remove label families and labels. Enforce cycle prevention, nonempty-category removal safeguards, and no-loss behavior for already referenced entities. The prototype's in-memory state is synthetic; real writes require optimistic revision checking, audit and backend validation.

## Acceptance and unresolved implementation decisions
- Reject attempts to place a category *under* a Task or to attach child Tasks to a Task; Task nodes are always leaves.
- Preserve category/Task identity, immutable revisions and reference lineage during moves/forks.
- Verify category and Task drag-and-drop, keyboard alternatives and clear drop targets, including invalid-drop refusal.
- Verify additive AND filtering across selected families, OR within a family where multi-selection is supported; clarify exact semantics in production UI.
- Support arbitrary future label families without hardcoding only phase, profession and transverse.
- Preserve original time estimate as attributable/revisioned input; do not silently substitute measured Run duration or hypothetical forecast.
- Files require authorized evidence/attachment storage and revision tracking, never unversioned overwrite.
- Decide and document deletion/archive policies for categories and labels in use, migration of existing Tasks, specialized profile-to-Task applicability, and permissions before production integration.
- Verify 1366px/1024px Chromium captures **visually**, alongside functional, access-control and Demo/Server isolation checks.

The [role-based user experience specification](role-based-user-experience-and-guided-navigation.md) remains authoritative for user-facing Task discovery and identity/permission constraints. This contract extends Workgroup editing and classification; it does not invent completed backend support.
