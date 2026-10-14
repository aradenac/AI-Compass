# Needs & Feedback — Workgroup view UI specification

**Decision status:** visual/layout proposal accepted by product owner on 2026-10-14. This is a target **for future implementation**, not a statement that the backend already supports new statuses, priority or taxonomy.

**Live HTML design reference:** [Needs & Feedback prototype](prototypes/needs-feedback/index.html) · [Design handoff](prototypes/needs-feedback/DESIGN.md) · [Repository-wide prototype convention](prototypes/README.md).

**Existing domain contracts:** [Feedback & Discussions (Server)](feedback-discussions-server.md) and [role-based UX](role-based-user-experience-and-guided-navigation.md). Keep their existing conversation security, evidence/revision guarantees and cross-role navigation; explicitly evolve schema/contracts for any new feature before shipping.

## Purpose

Give Workgroup contributors a workspace for reading, searching, classifying and discussing user contributions by **type of Workgroup action implied**, without forcing the discussion into a helpdesk process. The page is **view content only**: no application-wide shell, side menu or redundant footer.

## Layout (desktop 1366 × 900; usable from 1024px)

1. **Top summary strip:** aggregate counts, derived from real authorized records and the actual three-state model; one primary **New need / feedback** action for Workgroup-initiated contributions. Never invent counts or show restricted totals to unauthorized readers.
2. **Left column — browse:** keyword search, filtered list, category/type selection, state and priority filters and sorting; display title, type, concise excerpt, creation date and participation cues. Selection updates the central conversation without losing filters.
3. **Center — selected thread:** title, type, creation author and date, initial description and evidence attachments, one chronological conversation; public versus internal message visibility is unmistakable. Allow contextual reply and attachment actions with permissions and recorded attribution.
4. **Right column — metadata:** editable **type**, **state** and **priority** with appropriate permissions; author name links to their authorized user profile. Show accurately pinned Task/component/measured Solution context. Do **not** include team, business-domain category or tags.

Make the center pane visually dominant, and allow sensible column collapse/width adjustment at the 1024px desktop minimum. Search/filtering must not affect the content of a selected published conversation unexpectedly.

## Type classification

The existing generic Feedback/Question/Idea/Request/Discussion model remains the compatibility baseline. The proposed user-facing Workgroup categorization is:

- **New idea** — possible new usage or technology.
- **Support request** — help needed from the Workgroup.
- **Experience feedback** — observations after actual usage.
- **Question** — clarification or information request.
- **Request** — general functional/access-oriented request, distinct from approval or granting access.
- **Discussion** — general topic not fitting above.

Type is a **classification**, not an automatic Workgroup assignment, action creation, SLA, business Task, Forecast, or official recommendation. Migration/mapping from existing kinds must be specified, version-aware and lossless before implementation.

## Status and priority — new domain decisions

Introduce a configurable presentation of **New / In progress / Closed**, with **free transitions in any direction**, including reopening. Never auto-close or infer status from number of comments or age.

Preserve a **priority** attribute; values and default semantics must be defined in the backend/domain contract before implementation. Priority is Workgroup metadata, *not* an automatic ranking or an assertion of guaranteed response time.

These are **new business model/API requirements**, absent from the existing discussion contract. Implementation must specify the authority for editing them, optimistic revision/concurrency behavior, immutable audit history, backfill/defaults for existing threads, and the exact filter/count semantics. Until shipped, they remain illustrative in the prototype and must not be presented as operational.

## Author and participants

Show author identity and accurate creation timestamp; clicking the author opens the user profile **only when authorized**. No team field or inferred organizational grouping. Author identity does not give the Workgroup access to otherwise private user data.

Workgroup members may create threads themselves via **New need / feedback**, with the same contextual validation and recorded provenance as ordinary contributions.

## Conversation, visibility and attachments

Retain **one ordered thread**, not separate public/internal tickets. Mark each message visibly **Public** or **Internal** for authorized Workgroup viewers; never disclose restricted messages, revisions, attachment metadata or counts to ordinary readers. Maintain immutable message and attachment source revisions and original files, corrected-message attribution, edit reasons and HTTP 409 revision protection.

Do not assume that switching the UI metadata or reply visibility bypasses the existing backend restrictions on thread scope, reply parent visibility and historic information.

## Navigation

Search, filter, select a thread, inspect author profile/context, respond publicly or internally as authorized, and return to the same filtered list. Linked Tasks, catalog components and measured Solutions must resolve through real existing routes with authorization and original pinned revision context where present.

## Acceptance

- Test three-column desktop layouts at 1366 × 900 and 1024px, with actual screenshot inspection, readable controls and keyboard/focus behavior.
- Verify search, filters, classifications, priority, free state transitions and creation on **real authorized Server APIs** after domain changes; Demo mock must remain isolated.
- Verify public/internal visibility, attachment access and immutable history with positive and denied-role tests.
- Verify accurate stats and profile links do not disclose unauthorized information.
- Preserve existing Feedback discussion APIs and old records via an explicit version/migration plan; no loss of existing fields or attachments.
- Keep the prototype as visual reference and update it alongside future approved changes; passing CI alone is not design approval.

**Implementation note:** the approved prototype is interactive but runs on fictional in-memory data. It is not connected to the Server backend and must not be loaded as production business code.
