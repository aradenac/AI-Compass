# Future evolution — Controlled retirement, retention and privileged physical purge

**Remaining scope:** FUT-18 [#92](https://github.com/aradenac/AI-Compass/issues/92), scheduled after [UX-R07 #126](https://github.com/aradenac/AI-Compass/issues/126) (the earlier UX-R03 #116 is complete). Ordinary logical retirement, safe orphan inventory, privileged dry-run/hold checks, configurable optional retention and auditable garbage collection.

**Context:** [current publication and evidence lifecycle](../publication-and-information-lifecycle.md).

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
| Evaluation combinations and selected/waived/pending plan | [Campaign Evaluation Matrix](../campaign-evaluation-matrix.md) | Replace all-or-nothing publication gate with eligibility of exact published Run subset; keep separate plan completion counts |
| Pricing offers, dynamic meter fields, fixed vs variable | [Technology Accessibility & Pricing](../technology-accessibility-and-pricing.md) | Affected Run pending/not-publishable until required selected-offer meters are known |
| Setup Modules/Recipes and documentation readiness | [Composable Setup Guides](../composable-setup-guides.md) | Validate **included** configurations for each new publication; do not retro-invalidate older Run snaps on guide edit |
| Published Run eligibility, correction, recall, soft delete, GC | **This lifecycle feature** | Defines current-effective vs historic and admin purge contract reused across domains |
| Immutable action/event history, diffs, access-scoped audit browsing | [Data Governance Audit Explorer](../data-governance-audit-explorer.md) | Show actions; **does not own** eligibility or GC decision rules |
| Derived quality and automatic solution ranking | Results/analytics and [Role-Based UX](../role-based-user-experience-and-guided-navigation.md) | Consume only eligible currently active measured evidence; editorial notes don't override methodology |
| Economic scenarios and budget read models | [Deployment & Adoption Planning](../deployment-and-adoption-planning.md) | Invalidate/recompute current value when an underpinning Run changes; preserve old as-of snapshots |
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

## 10. Remaining purge and retention acceptance criteria

1. An ordinary authorized deletion/retirement hides the object from current views while preserving stable IDs/tombstones and necessary historical relations.
2. Physical deletion never removes a shared content-addressed blob that remains referenced by **any** protected current, archived or historic object.
3. An independent legitimate unreferenced Catalog object is **not** auto-purged merely for lacking incoming links.
4. The maintenance interface shows eligible orphan blob and managed-record candidates, grace period, blockers, storage impact and a **dry-run preview**.
5. A separately privileged maintenance administrator can manually purge approved eligible content; the action and verification are audit-recorded.
6. An authorized admin may configure and explicitly enable/disable a scheduled retention/GC policy, with selectable grace period and eligible classes; 30 days is an example, not a forced universal setting.
7. Scheduled purge only removes records meeting **all** eligibility checks after expiry; rechecks current references/holds under concurrent conditions and fails closed.
8. A partial DB/filesystem cleanup failure is recoverable/idempotent; no dangling live EvidenceLink or silent lost valid file appears.
9. Revoked and purged content cannot leak via guessed object/revision/file URL, export, cache or stale comparison API.
10. Backup/restore tests explicitly verify tombstones/revocations are not lost such that previously withdrawn records reappear as active published data.
11. Existing Demo records and Server data remain completely separate; neither environment imports fake evidence as a side effect of lifecycle changes.
12. All operations enforce RBAC, CSRF, attribution, transactional integrity, version checks and relevant object scopes, not only hidden frontend controls.

## 11. Implementation decisions and explicit boundaries

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

**Approval boundary:** functional intent is accepted and owned by FUT-18 [#92](https://github.com/aradenac/AI-Compass/issues/92). The actual execution order is controlled by the [current implementation plan](implementation-plan.md): wait for UX-R07 #126 and preserve operational recovery/approval gates; this specification alone does not authorize deploying an untested purge./planning.
