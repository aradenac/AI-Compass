# Future evolution — Data Governance Audit Explorer

> **Status:** Proposed cross-platform feature — product decisions and preliminary impact, not an implementation claim.  
> **Discussed:** 2026-10-10  
> **Area:** Maintenance & Governance / Audit & Changes  
> **Scope:** All persistent business objects and relevant administrative changes in AI Compass.  
> **Related baseline:** [Platform Architecture & Data Governance](../platform-architecture-and-data-governance.md) · [Activity Feed](../activity-feed-server.md) · [Data Health](../data-health.md) · [Users & Access](../users-and-access.md)

## 1. Objective

Provide authorized governance operators with an **independent, comprehensive, searchable interface** answering:

- **Who** changed a persistent object?
- **What** object, relationship, or field changed?
- **When** was the change committed?
- **How did the content change** (before/after values, structural diff, or version comparison)?
- **What type of operation** took place (create, edit, link/unlink, lifecycle transition, correction, archive, administrative change, automated operation, etc.)?

This is a governance **inspection/control experience**, conceptually similar to an Activity Feed but with a different purpose: review exact data mutations and their historical content, not narrate workgroup activity.

### Non-negotiable user-experience constraint

**Audit must be passive and transparent for ordinary users and workgroup contributors.** Recording changes must **not** require additional fields, manually supplied audit comments, classifications, approval requests, confirmation steps, or recurring validation tasks. Do **not** clutter regular business pages with audit counters, badges, timestamps, or a second navigation flow merely to support auditing.

Existing domain-specific inputs remain unchanged: for example, a *Waived* campaign evaluation still requires its **business justification** because the waiver workflow calls for it, **not** because the audit system does.

## 2. Product placement: dedicated governance workspace

Use the existing independent **`/maintenance`** workspace and introduce a dedicated **Audit & Changes / Data Governance Audit Explorer** section. A maintenance-only operator should be able to inspect authorized change history **without** being granted normal workgroup editing or publishing capabilities.

Do **not** conflate this with:
- The workgroup's **Activity Feed**, which emphasizes meaningful activities and reporting.
- **Data Health**, which detects quality/integrity problems and tracks maintenance findings.
- **Users & Access**, which manages accounts and privileges.
- A mandatory object-history panel in each user-facing application view.

Reuse compatible underlying change records; **do not create two competing event-capture pipelines** simply to support two different screens.

## 3. Functional explorer — illustrative view

The dedicated frontend should support an overview of committed changes and a **detail pane** for each selected event:

| When (example) | Actor | Object | Operation | Change summary |
| --- | --- | --- | --- | --- |
| 2026-10-10 14:07 | Contributor A | Benchmark Run RUN-042 | Data correction | Total tokens: 125,000 → 152,000 |
| 2026-10-10 11:35 | Contributor B | Setup Guide GUI-018 | Documentation edit | Installation step clarified |
| 2026-10-09 17:20 | Contributor A | Campaign CMP-009 | Relation added | AI Solution linked |
| 2026-10-09 15:12 | Contributor C | Test Case TC-014 | Content revision | Definition of Done updated |

These rows are **fictional UX examples**, not actual repository or production events.

On selecting a row, show object identity, operation, actor, commit time, **changed fields or relationships**, content before/after (or a suitable text/JSON/list diff), and corresponding immutable revision references. When useful, link to authorized historical snapshots, the parent/batch operation, and dependent objects **without altering those objects**.

The explorer should offer:
- Search/filter by period, actor, object type, object public ID, operation, source (human, integration, automated job, migration), and optionally changed field.
- **Object history**: all changes to a single object in chronological order, with revision comparison.
- **Global history**: changes across permitted object types.
- Distinguishable group/batch events and per-object/field changes for one logical operation.
- Clear indicators when a historical detail is unavailable in legacy events; **never fabricate old values, actors, or timestamps**.
- Authorized, scope-limited export for investigation and compliance, ideally leveraging existing JSON/CSV patterns without leaking restricted content.
- Pagination and bounded queries so large histories remain usable.

There should be no requirement to expose every technical write as a noisy standalone item: a single business transaction can yield a compact summary with expandable constituent field/relationship changes.

## 4. Coverage — persistent modifications, not user surveillance

**Target coverage:** all identified persisted business objects and relevant administrative records, including:

- Model, Provider, Harness, Framework, their versions and catalog properties;
- AI Solutions and recorded configurations;
- Task taxonomy changes, Test Cases and forks;
- Campaigns, evaluation-plan combinations, status/selection/waiver changes, lifecycle transitions and links;
- Benchmark sessions, Test Runs, declarative metrics and corrections;
- Setup Guides/modules/recipes, recommendations and other knowledge records;
- Technology Watch, forecasts, sources, and references;
- Relevant user/role/access and maintenance/governance actions, **subject to stricter privileges**;
- Relationship additions/removals, reordering, property changes, archive/restore and other persistent operations.

**Not in scope by default:** page views, clicks, routine reads, search queries, ordinary navigation, or an engineer's day-to-day AI conversations. This is an audit of **committed changes**, not behavioral monitoring.

New persistent object types must join this audit contract as part of their development rather than requiring a later one-off audit UI.

## 5. Minimum automatic event information

For each successfully committed change capture, whenever applicable:

| Attribute | Meaning |
| --- | --- |
| Event ID | Unique durable event identity. |
| Object ID/type | Stable object identifier and its semantic object type. |
| Actor | Authenticated user/service principal responsible; preserve historical identity even if account metadata changes. |
| Timestamp | Accurate server-side commit time (UTC; format in viewer's locale as needed). |
| Action | Create, update, relation change, publication/reopening, archive, correction, etc. |
| Change set | Affected fields/paths and before/after values or pointers to immutable revisions enabling exact reconstruction. |
| Revision links | Previous and resulting revision identifiers or snapshots, where objects are versioned. |
| Origin | Interactive API, authorized integration, automated process, import/migration, etc., where determinable. |
| Correlation | Transaction/batch/request identifier linking coordinated changes. |

An audit record's **technical context is generated by the platform**, never solicited as extra input from the user. A rationale is not globally required. Business-specific reasons may already exist in the modified object's data and need not be duplicated.

When the operation changes confidential material, the audit **may record that a protected value changed** without recording or disclosing the secret itself.

## 6. Corrections, publication and historic meaning

The platform should support corrections of ordinary declarative records even after they have been accepted or published, without an artificial campaign reopen/review solely for a typo, omitted skill, documentation clarification, or corrected entered metric, **provided the relevant domain workflow permits the edit**.

Examples:
- Correct a Test Run's declared token count after checking original logs.
- Add a previously omitted skill or explanatory note.
- Clarify a Setup Guide without altering historical evidence.
- Correct descriptive or declared campaign information after publication.

The governance interface must show **what changed, from what, to what, when and by whom**.

Keep the following distinct:
1. **Original raw evidence and historical snapshots:** unchanged and individually retrievable under applicable retention/access rules.
2. **Correctable declared business data:** the current representation can be superseded by a new revision, with preceding values inspectable.
3. **Derived scores/metrics:** may be recomputed on corrected inputs or changed calculation methods; preserve provenance and the earlier derived result.

**Do not silently rewrite measured historical conditions**, re-point pinned run references, invalidate past benchmark results, or break dependency links when a catalog component evolves. An update to current content is not proof that historical experiments used the updated content.

Corrections are audited automatically. They **do not, on their own, mandate reapproval or republication**. Adding new evaluation scope / fresh Test Runs follows the separate campaign reopening rules described in [Campaign Evaluation Matrix](campaign-evaluation-matrix.md).

This proposal does **not** authorize destructive changes to original evidence or remove existing business permissions.

## 7. Backend and data-governance design guidelines

Build upon the existing source-of-truth mechanisms:
- **Immutable revisions** for catalog and other versioned domain objects.
- Domain-level committed audit events (for example `CatalogAuditEvent`, `UserAccessAuditEvent`, `DataHealthEvent`) and future producers for additional domains.
- The existing Activity Feed as one **permission-filtered projection** over source events.
- A separate Audit Explorer as a richer **permission-filtered projection** with change diffs and version navigation.

Required invariants:
- **Transactional atomicity:** commit the domain change and its required event together whenever both reside in the same database; no successful change without its corresponding audit entry.
- **Immutable history:** normal application operations cannot overwrite or silently delete earlier audit entries or object revisions.
- **Exact attribution:** avoid guessing the actor or historic role for old records lacking that metadata; identify service/background actors rather than misattributing to end users.
- **Structured diffs:** compute/store comparable field-level/relationship-level differences, protecting against misleading diffs of unordered arrays and structured content.
- **Concurrency-aware revisioning:** avoid silent lost updates, and keep previous/current revision linkage.
- **Completeness checks:** detect and surface missing/inconsistent change provenance when objectively detectable; do not pretend that preexisting gaps are backfilled.
- **Retention/legal exceptions:** any separately authorized redaction/erasure obligations must be handled by defined policy without claiming unconditional infinite retention.

Prefer **one authoritative recording contract with multiple read models**, not a generalized second mutation channel.

## 8. Access control, privacy and security

Provide independent audit **view** permission(s), for example conceptual `audit.view`, separate from:
- `business_read` / `business_write`;
- `maintenance_view` / `maintenance_triage`;
- `users_manage` and security/platform administration.

**Audit metadata visibility must not automatically grant access to full object content, evidence payloads, account details, confidential draft records, or secrets.** Resolve sensitive detail server-side using explicit grants and scoped field redaction, including in search results, diffs and exports. Hide or mask restricted objects when even metadata would disclose confidential information.

In particular, credentials, tokens, password hashes, sensitive recovery material and secret values must never appear in an audit diff or export. Account-security change details remain subject to Users & Access privileges. Access checks must be enforced at API level, not just by omitting frontend navigation.

The governance-only operator should be able to audit the permissible metadata without acquiring permission to edit, publish, download evidence, or manage users.

## 9. Preliminary impact

| Area | Assessment | Expected work |
| --- | --- | --- |
| Domain mutation services | High, cross-cutting | Ensure every persistent object/change path emits committed, attributable events. |
| Audit/revisions | Medium–high | Harmonize event contract, change-set semantics, historic revision lookup, source coverage. |
| API | Medium | Permission-filtered queries, event detail, diff, history, filtering and bounded export. |
| Maintenance frontend | Medium | Dedicated Audit & Changes screen with timeline, filters, diff/history inspector. |
| Security/RBAC | Medium–high | Independent audit grants, field/object-level redaction and tests. |
| Activity Feed | Low–medium | Reuse existing source events; retain its original workgroup-oriented purpose. |
| Data Health | Low–medium | Optionally detect missing/inconsistent audit provenance; no automatic rewrite. |
| Existing business UIs | **Minimal by design** | No new audit-specific user input, forms or required workflows. |

Existing backend audit captures **some** catalogs and access changes, but current source coverage and existing Activity Feed display are **not** yet a platform-wide full-content diff explorer. Do not represent this proposal as already complete.

## 10. Draft acceptance criteria

1. A contributor edits a Model, Test Case, Campaign, Run metric or Setup Guide using the **existing form only**; the change is persisted and recorded with **zero audit-specific input**.
2. An authorized audit operator finds the change by actor, time, object ID or type, and sees the appropriate **before/after** value or structured comparison.
3. A change to a linked relation is visible as a link addition/removal rather than an opaque unexplained object revision.
4. A multi-object operation is traceable as one grouped action with its constituent object changes.
5. A post-publication correction of an allowed declarative Run field appears in the explorer; the prior value and original evidence remain available, and the correction does **not automatically reopen** its campaign or require reapproval.
6. The Activity Feed and Audit Explorer can project the **same recorded event**, but with purpose-specific presentation and privileges; there is no duplicate audit source of truth.
7. An audit-only / maintenance-only account can inspect permitted audit records but cannot edit business records, access forbidden evidence or administer users.
8. Restricted secret values and sensitive account content do not leak through event detail, diff, search, filters or export.
9. Background/system mutations show truthful service attribution; rejected/uncommitted transactions do not appear as committed success events.
10. Existing records without sufficient metadata are marked **unknown/unavailable** where relevant, not falsely reconstructed.
11. New persistent object types cannot silently bypass the mutation-audit contract.
12. No routine user-facing screen becomes more cumbersome or visually cluttered solely because this governance audit is enabled.

## 11. Open implementation questions

- How to define a reliable **coverage inventory** for all write paths, including relationships and legacy modules?
- Which structured-diff strategy best handles JSONB, rich text, ordered/unordered relations and evidence metadata without storing duplicated sensitive content?
- What exact audit operator roles/scopes are required, especially for cross-business-unit metadata and account-security changes?
- Which exports, date ranges and retention guarantees are operationally necessary?
- What completeness signal can be asserted for already-existing records, without claiming historical data that was never captured?
- What performance/indexing strategy will keep the explorer responsive as event volume grows?

These are implementation decisions, **not** reasons to add user-facing audit questions or publication blockers.

## 12. Scope boundary

This proposal is a **cross-platform governance capability**. It does not replace the Activity Feed, add a mandatory review to business workflows, change the Setup Guide lifecycle, or alter the Campaign Evaluation Matrix. It does not require additional justifications for normal edits, track routine reading/navigation, or grant auditors unrestricted access to business content.
