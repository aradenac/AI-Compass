# Future evolution — Publication & Information Lifecycle

> **Product status:** Scope agreed for future development; implementation not yet scheduled or decomposed into issues. This is a proposed contract, **not** a claim that individual Run withdrawal, partial publication or physical purge already works.  
> **Decision context:** October 2026 — consolidation of future evolutions.  
> **Role:** **Cross-cutting authoritative specification** for changes to previously published business information, publishable subsets, revocation, logical deletion, physical retention/purge and dependent read-model consistency.  
> **Closely related:** [Campaign Evaluation Matrix](campaign-evaluation-matrix.md), [Technology Accessibility & Pricing](technology-accessibility-and-pricing.md), [Composable Setup Guides](composable-setup-guides.md), [Data Governance Audit Explorer](data-governance-audit-explorer.md), [Deployment & Adoption Planning](deployment-and-adoption-planning.md), [Role-Based UX](role-based-user-experience-and-guided-navigation.md), [Product Definition](../product-definition.md), [Platform Architecture & Data Governance](../platform-architecture-and-data-governance.md), [Benchmark Workflow](../benchmark-workflow.md), [Server Campaigns](../campaigns-server.md).

## 1. Problem and principles

AI Compass is an evolving evidence repository: a Campaign/Run can be published, an original measurement can later be found wrong, a Run can be withdrawn, a published Campaign can be reopened, and a published object or evidence attachment may ultimately require deletion.

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
9. **Physical purge is an independently privileged Maintenance/Governance operation**: administrable, previewable, policy-driven, auditable and conservatively garbage-collected.
10. "Orphan" is a provable domain/storage condition, **not** merely "nobody has linked to this meaningful standalone catalog object yet." Preserve all necessary current, historical and legal references.
11. Source revisions/evidence are owned once; affected domain projections are derived, invalidated and recomputed through consistent shared rules.
12. All changes respect RBAC, original evidence access controls, published/draft visibility and the permanent Server vs Demo separation.

## 2. Distinct lifecycle operations and expected impact

| Operation | Current public business view | Stored source/history | Preconditions & authorization |
| --- | --- | --- | --- |
| **Edit an unpublished draft** | No impact until explicitly published, apart from authorized Workgroup preview | Append version/revision as appropriate | Existing editor and optimistic concurrency rules |
| **Correct an already published declared value** | **Immediately** use the new authoritative corrected revision in current projections; invalidate/recompute dependents | Original declaration, correction author/time/reason where domain needs it, raw evidence and historic revisions remain | Authorized correction with audit; server validates source identity/revision |
| **Reopen a published Campaign** | Keep **last valid published subset** accessible; new Tasks/Runs/plan changes are not automatically public | New working revision and old published revisions coexist | Existing campaign lifecycle + expected_revision |
| **Republish a Campaign** | Atomically move to a new published **eligible subset** after checks; new content becomes available | Earlier publication membership/snapshots remain | Existing review/publish rights, documentary and evidence rules |
| **Withdraw a single published Run** | **Immediately exclude** that Run from all current public results/scores/ranking and all projections using active evidence | Historical Run and withdrawal event/reason remain restricted to permitted historical views | Explicit authorized Run-level withdrawal; neither silently deletes its Campaign nor other Runs |
| **Unpublish / recall whole Campaign** | Withdraw its current published membership; other campaigns may continue supporting shared AI Solutions | Historical publication/decision and source evidence preserved | Existing authorized Campaign unpublish semantics extended to read models |
| **Archive / logically delete an object** | Hide from current discovery/ordinary references; retain necessary tombstone/historical links | Original IDs are never reused; referenced history and audits retained | Domain policy; reject unsafe operations or safely retire link visibility |
| **Manual physical purge** | Content already logically withdrawn, and no protected required references remain (or an approved exceptional erasure plan supplies safe redaction/tombstones) | Minimal lawful/auditable deletion proof, never orphan live FKs | Privileged maintenance policy/checklist; preview + safety gates |
| **Policy-based automatic purge** | No user-visible broken data; only **eligible** items outside retention grace | Audit each purge decision/aggregate batch and failure | Authorized and enabled administrator policy; scheduled safe worker + recheck |

**Subtle but required distinction:** a published Campaign has a **frozen publication snapshot**, whereas a **current effective published view** is its authorized still-active published membership filtered through later corrections and revocations. The historical snapshot says *what was announced then*; the effective projection says *what can be trusted and used now*. Ordinary public readers must never bypass a withdrawal by querying an older "historical" endpoint; any historic access is permission-filtered and prominently labeled, subject to revocation/erasure policy.

Corrections to published measured values are a **specific approved correction operation**, not general editing of draft Campaign contents. They can become effective without republishing the Campaign while the independent source revision/audit remains visible. New evaluation scope and newly completed Runs remain private until the explicit publish action.

## 3. Run lifecycle, pricing-dependent evidence and partial publication

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

## 4. Recalculation, visibility, references and consistency guarantees

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

## 5. Logical deletion is the normal business deletion

Users authorized to retire/remove a Task, Catalog entry, Guide, Forecast, Campaign, Run or other versioned business object generally perform **archive/retire/revoke/soft delete** appropriate to that domain.

- Remove it from current default catalogs, search, auto suggestions, deployment-ready lists and published results as required, but preserve stable IDs and history (including historical citations). Never reuse an assigned public readable ID.
- Prevent future links to a retired/ineligible object as an active candidate unless the domain allows reactivation.
- Referenced objects must not be physically cascaded away. Display a safe tombstone/restricted historic label when something formerly linked is no longer available.
- Where a referenced item is a reusable shared Guide or a reused source file, ordinary deletion must not break another valid record's historical meaning.
- Distinguish **delete**, **archive**, **unpublish**, **revoke**, **correct** and **purge** in wording and audit: they are not interchangeable.
- A deletion of a published parent does not silently invalidate independent published content in other parents; compute affected active membership from actual references and policy.

Ordinary business deletion is **not automatically physical data erasure**. Highly privileged exceptions for security, unlawful content or privacy may need a controlled different process, possibly with redacted/tombstone historical refs; never promise infinite retention against applicable law.

## 6. Physical purge: Maintenance & Governance with optional automated retention

### 6.1 Operator experience and authorization

The user explicitly requests a **Maintenance/Governance** control for physical purge of genuinely unreferenced eligible items. This is an **approved future requirement** of this feature; it does not authorize building unrelated new maintenance modules.

The maintenance interface should provide:

1. **Storage health / orphan inventory:** list eligible content-addressed blobs, temporary/orphan physical files and eligible managed DB records with age, owner/type, size/count, first eligible/orphan timestamp, last reference check, retention rule and why considered removable.
2. **Dry-run impact preview:** list which logical evidence links, snapshots, archives, approved published references, backups/holds and protected historic versions were checked. Show projected disk reclamation, row count and evidence of *zero protected references*.
3. **Manual controlled purge:** authorized administrator triggers an idempotent job with explicit confirmation, reference/hold recheck, durable audit/receipt and failure reporting.
4. **Retention policy settings:** admin can enable/disable automatic garbage collection; set a **grace period by item class** (e.g. **30 days** is an *illustrative* initial value, not a committed hardcoded business rule); choose scheduled check cadence and allowed classes. Require explicit administrative authorization to enable an irreversible policy. Ordinary Workgroup users cannot configure physical deletion.
5. **Scheduled GC status:** last execution, candidates, removed objects/files, reclaimed bytes, blocked items with reasons, failed/retry state and links to actual deletion audit.
6. **Safety maintenance:** detect stale/missing/orphan file metadata separately from eligible garbage. Integrity anomalies are **diagnostics**, not authorization to purge.

Operator permissions for browse/preview and purge/configuration must be **separate**. A Data Maintainer's normal read-only ability does not implicitly grant destructive purge. Reuse existing role/permission architecture, audit, backups and Data Health interface.

### 6.2 What qualifies as an orphan?

**A zero count of direct links is not sufficient by itself** if objects are valid independent knowledge, pinned via historic snapshots, referenced in old publications, retained under policy or needed for recovery.

A candidate can be automatically purged only after all applicable checks pass:

- **Explicit disposal eligibility:** already soft-deleted/retired **and** cleanup-eligible by domain policy, or a technical temporary/uncommitted/unlinked artifact whose lifecycle specifically allows reclamation. Independent Watch Entries, external sources, Models, Guides, ideas and Test Cases are **not** deleted simply because no Campaign has linked them.
- **No protected references:** no live relational FK/link, required archive/history/snapshot/publication source reference, other user's file link, cross-solution reference, valid source pin or other retention/legal hold. Check **transitive/indirect** provenance as needed; a historical Run may still require a blob even when not in today's active ranking.
- **Grace period elapsed:** count from the **later** of first verified orphan eligibility/explicit retirement and last protected-reference removal, rather than solely from creation/upload time. A newly unlinked ancient blob must not disappear instantly.
- **Concurrent recheck:** within the purge transaction/coordination window verify it has not been re-referenced. New valid references must be prohibited once irrevocable purge begins.
- **Backups/retention policy:** comply with coordinated DB+blob recovery and independently protected backup retention; physical deletion from active store **does not claim instantaneous deletion from immutable backup copies**.
- **Audit integrity:** produce reason, checks, actor/job, time, status and counts; maintain minimal tombstone/receipt as law and referential integrity permit.

**Blob-specific:** immutable SHA-256 blobs may be deduplicated: many EvidenceLink/revisions may share one file. Delete bytes **only when all protected references are gone** and policy permits; removing one Run's file link is not proof that the hash is exclusively owned by that Run.

**DB-specific:** "orphan" is meaningful for explicitly garbage-collectable dependent/temporary rows, expired generated read projections and logically retired records that meet a domain policy. **Do not globally garbage-collect standalone entity rows just because they have no incoming link.** For immutable audit/revision rows still needed to interpret retained history, automatic purge is prohibited. Avoid naive SQL ON DELETE CASCADE against authoritative evidence links; preserve necessary tombstones and foreign-key integrity.

An exceptional **explicit authorized erasure** of otherwise historically referenced material requires its own impact/redaction/tombstone procedure and retention/legal assessment. That exceptional path must not be silently disguised as routine orphan GC.

### 6.3 Simple cleanup implementation, strong guarantees

Prefer one **policy-driven, periodic reconciler/GC job** rather than a complex distributed deletion engine:

1. Discover eligible candidates and store a durable job/preview snapshot.
2. Re-check referential protection, policy version, age, legal holds and current permissions under appropriate locks/transactions.
3. Mark candidates as purge-in-progress/deny new links; use safe outbox/two-phase coordination where DB and filesystem cannot share a transaction.
4. Delete eligible physical blob bytes idempotently; remove or tombstone eligible dependent metadata **only when safe**, reconcile partial failures and verify no protected reference became dangling.
5. Record job result, bytes reclaimed, counts, anomalies and durable audit identifiers. Retried jobs cannot delete unrelated shared blobs.

**Fail closed:** DB/file errors, unknown provenance, unresolved backup requirements, reference inconsistencies and competing updates mean **do not purge**; surface the candidate in Maintenance for resolution. A dry run/preview should be repeatable and accurate enough to support operator decision.

**Configurable default:** provide a safe admin-defined retention policy with an illustrative grace value such as 30 days. Automatic purge may be **initially disabled pending explicit admin enablement/verification**; activation and retention changes must be audited. The exact period and enablement default are implementation/policy decisions, **not** assumptions that old unreferenced files should be immediately erased.

### 6.4 Retention and backup implications

A true purge cannot break the backup/recovery contract. Restore procedures must distinguish:
- objects deleted from current store but still present in a historical independently retained backup;
- tombstones/revocation events that must be **reapplied or reconciled after restoration** to prevent removed source content reappearing as active published data;
- special legal/security erasure requiring separate backup-retention handling and access restrictions.

Never claim that deleting an active EvidenceBlob deletes it from all Restic archives, PITR history or exported copies. Communicate retention guarantees precisely.

## 7. Data domains and dependency ownership

| Concern | Owning proposal/domain | This feature's integration requirement |
| --- | --- | --- |
| Evaluation combinations and selected/waived/pending plan | [Campaign Evaluation Matrix](campaign-evaluation-matrix.md) | Replace all-or-nothing publication gate with eligibility of exact published Run subset; keep separate plan completion counts |
| Pricing offers, dynamic meter fields, fixed vs variable | [Technology Accessibility & Pricing](technology-accessibility-and-pricing.md) | Affected Run pending/not-publishable until required selected-offer meters are known |
| Setup Modules/Recipes and documentation readiness | [Composable Setup Guides](composable-setup-guides.md) | Validate **included** configurations for each new publication; do not retro-invalidate older Run snaps on guide edit |
| Published Run eligibility, correction, recall, soft delete, GC | **This lifecycle feature** | Defines current-effective vs historic and admin purge contract reused across domains |
| Immutable action/event history, diffs, access-scoped audit browsing | [Data Governance Audit Explorer](data-governance-audit-explorer.md) | Show actions; **does not own** eligibility or GC decision rules |
| Derived quality and automatic solution ranking | Results/analytics and [Role-Based UX](role-based-user-experience-and-guided-navigation.md) | Consume only eligible currently active measured evidence; editorial notes don't override methodology |
| Economic scenarios and budget read models | [Deployment & Adoption Planning](deployment-and-adoption-planning.md) | Invalidate/recompute current value when an underpinning Run changes; preserve old as-of snapshots |
| Maintenance controls | Existing [Governance baseline](../platform-architecture-and-data-governance.md) + this extension | Add scoped manual purge, GC policy and safe preview/status only as specified here |

## 8. Minimal conceptual model (implementation is not prescribed)

Use existing stable typed IDs and immutable revisions wherever possible. Conceptually there may be:
- **PublishedSelection / PublishedManifest:** Campaign revision, exact included eligible Run IDs/revisions and pinned guides/method; visibility period/status and reviewer attribution;
- **Correction / Supersession:** exact source/run revision, corrected declared fields, new revision/actor/time and original immutable evidence anchors;
- **Revocation / Withdrawal:** target Run/Campaign/item, effective moment, author, reason and source revision; tombstone and read-eligibility consequences;
- **EffectiveEvidenceQuery / derived projection:** one centrally reusable authoritative eligibility rule for results/ratings/economic consumers, referencing active publication and revocations;
- **PurgePolicy:** enabled flag, eligible object classes, grace duration, scheduled frequency, version and authorized editor;
- **PurgeCandidate / PurgeJob / PurgeReceipt:** first eligibility time, immutable preview/hash/reference guard, job/race state, reclaimed bytes/counts, blockers and audit entries.

These are **conceptual responsibilities, not instructions to create separate tables for everything**. Prefer extending existing CatalogRevision, CampaignSnapshot, Audit Events and evidence storage contracts. Introduce only minimum extra persisted membership/retirement state necessary to make semantics provable, not a general document CMS workflow engine.

## 9. Preliminary implementation impact and risks

| Area | Impact | Key concern |
| --- | --- | --- |
| Campaign and Run APIs | **High** | Partial publication membership, Run pending state, Run-level recall and effective publication while reopened |
| Method/results selection | **High** | Distinguish incomplete vs failed, selectable final results, exact revisions and negative evidence |
| Tariff-driven Run UI | **High dependency** | Required meter fields from selected offer and deterministic cost; preserve partial work |
| Results/automatic ranking | **High** | Single evidence-eligibility rule; revoke takes effect without stale public leakage |
| DAP/projections | **High dependency** | Invalidation/async recomputation, freshness/trace, historic snapshot immutability |
| Evidence files/storage | **High** | Shared SHA-256 blob references, GC race safety, transactional DB/filesystem reconciliation |
| Maintenance & Governance UI | Medium–high | Reviewable orphan inventory, controlled manual purge and optional policy-based GC |
| Governance Audit Explorer | Medium | Show precise correction, recall and purge events using original event stream |
| Security/backup/recovery | **High** | Protected historic references, hard-erasure exceptions, privilege separation, restore-with-tombstones |
| Demo/Server parity | Medium | Demo should model same visible lifecycle semantics with fake data; Server never falls back to Demo |

## 10. Acceptance criteria (future, not yet tested)

1. A Campaign's last published, valid Runs remain visible to authorized readers when it is reopened for new Tasks, Test Cases or Runs; incomplete new work stays private.
2. A Campaign can explicitly republish a new **subset** of complete Runs, and its published membership/coverage is auditable as a dated immutable version.
3. Incomplete/pending Runs preserve all declared steps and attachments, with exact missing meter/field reasons, without fabricating an observed complete Run.
4. A fully measured Run with failed DoD can be published as legitimate **negative experimental evidence**, not a positive recommendation.
5. Run form fields are derived from the pinned selected Pricing Offer: credits, input/output/reasoning/cached tokens or other applicable units, without unsupported extra mandatory fields.
6. Flat-rate-only offers do not force irrelevant consumption fields; hybrid offers account for applicable variable components only.
7. Missing required post-execution consumption prevents **that Run's** inclusion, not publication of independent eligible Runs in the same Campaign.
8. Only Runs included in a currently effective published selection contribute to ordinary published comparisons, rankings and future value projections.
9. Correcting an existing published declared measurement via authorized action creates an auditable superseding revision and **promptly changes its effective current derived values**; original raw source and past snapshots remain attributable.
10. Run withdrawal becomes effective in all authorized published APIs and read models **without withdrawing unrelated Runs**. No stale cached figure is presented as current.
11. Revoking a Run invalidates its contribution to Task-specific automatic selection and economic projections; an AI Solution with other valid published Runs remains usable from those sources.
12. Corrections/withdrawals flag dependent published editorial context requiring review as appropriate, but **do not turn editorial commentary into the authority** for measured scores.
13. An ordinary authorized deletion/retirement hides the object from current views while preserving stable IDs/tombstones and necessary historical relations.
14. Physical deletion never removes a shared content-addressed blob that remains referenced by **any** protected current, archived or historic object.
15. An independent legitimate unreferenced Catalog object is **not** auto-purged merely for lacking incoming links.
16. The maintenance interface shows eligible orphan blob and managed-record candidates, grace period, blockers, storage impact and a **dry-run preview**.
17. A separately privileged maintenance administrator can manually purge approved eligible content; the action and verification are audit-recorded.
18. An authorized admin may configure and explicitly enable/disable a scheduled retention/GC policy, with selectable grace period and eligible classes; 30 days is an example, not a forced universal setting.
19. Scheduled purge only removes records meeting **all** eligibility checks after expiry; rechecks current references/holds under concurrent conditions and fails closed.
20. A partial DB/filesystem cleanup failure is recoverable/idempotent; no dangling live EvidenceLink or silent lost valid file appears.
21. Historical publication/Forecast/Run/economic snapshots are not retroactively rewritten by normal correction or Catalog/Guide edits; historic authorized viewers see superseding/revocation context.
22. Revoked and purged content cannot leak via guessed object/revision/file URL, export, cache or stale comparison API.
23. Backup/restore tests explicitly verify tombstones/revocations are not lost such that previously withdrawn records reappear as active published data.
24. Existing Demo records and Server data remain completely separate; neither environment imports fake evidence as a side effect of lifecycle changes.
25. All operations enforce RBAC, CSRF, attribution, transactional integrity, version checks and relevant object scopes, not only hidden frontend controls.

## 11. Deferred refinements and explicit boundaries

**Deferred choices that do not block writing this specification:**
- Precise technical representation of current effective publication membership vs frozen historical manifests, and efficient invalidation of derived projections;
- Whether individual Run-level correction must be performed by the author, a publisher, or either under specific permissions; preserve the chosen existing domain permissions and clearly audit who acted;
- Exact periods/class-specific rules for physical retention and policy enablement defaults; 30 days is illustrative;
- Which independent managed DB child artifacts can be garbage collected (safe allowlist) and which legally-required records need longer retention;
- Whether correction/withdrawal of currently published evidence temporarily suspends a specific automatic ranking vs fully excluding a candidate pending rerun;
- Detailed deletion/restore treatment of privileged legal/security erasure outside ordinary orphan GC;
- Feasibility of real-time derived recomputation vs fail-closed stale flags for expensive estimates;
- Exact handling of single Run's completed final record vs incomplete recording/session in evolving current Server execution APIs.

**Out of scope:** mandatory external data sync; auto-purchasing licenses; arbitrary bulk deletion of historic catalog records; multi-user simultaneous editing of a Run; a second audit pipeline; requiring additional unrelated user form fields; irreversible erase-on-click from an ordinary engineer screen; an automatic 30-day deletion default applied to all unlinked records; mutation of historically pinned raw benchmark evidence.

**Approval boundary:** functional intent is accepted. No issue-priority ordering, GitHub issue creation, repository-wide documentation restructuring or source-code implementation follows from this page alone. This proposal will be used later when the user requests issue breakdown/planning.
