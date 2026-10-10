# Future evolutions — outcome-led implementation plan

> **Status:** Proposed sequencing for owner review; **not yet approved for implementation**.
> **Prepared:** 2026-10-10.
> **Authority:** Planning and coverage index only. Detailed requirements remain in the linked source specifications.
> **Not in scope here:** GitHub issue creation, implementation tasks/estimates, code changes, production GO, or repository-wide documentation restructuring.

## Goal and execution strategy

Deliver useful, trustworthy AI Compass outcomes as early as possible, without rebuilding the same feature twice:

1. **First usable path:** an actual workgroup member can configure a technology, plan and perform an evaluation, publish an *eligible subset* of reproducible evidence, and an engineer can find an evidence-based configuration and its applicable installation instructions.
2. **Next measurable business result:** authorized management/planners can inspect a Task × AI-configuration economic opportunity, its uncertainty and exact source revisions.
3. **Then deployment decisions:** plan real beneficiaries, verify access and first use, and derive defensible pilot/rollout resource needs.
4. **Harden for operation without delaying the first outcomes:** audit, safe purge, scalable verified archives, capacity policies, Internet-specific readiness and further release automation progress on their own dependency path.

**Do not turn this into a platform-first rewrite.** The existing Django/PostgreSQL, immutable revisions, UUIDv7/public IDs, evidence store, RBAC, Demo/Server and PLAT recovery mechanisms are the starting point. Make only the technical changes needed for the next vertical outcome. The accepted frontend convergence is performed **together with role-based UX**; no intermediate third UI, second business frontend, new services or microservices.

**Delivery order is a dependency order, not a commitment to serialize all work.** Independent parts may run concurrently if they respect the contracts below. Every stage has an observable end-user/operator result. Preserve both permanent runtime modes (fake offline Demo; authenticated, initially empty real Server), with no cross-mode data exchange or fallback. A browser prototype is not equivalent to a delivered shared Server capability.

## Phased outcome map

| Phase | Outcome and why it comes now | Main authoritative sources | Completion checkpoint |
| --- | --- | --- | --- |
| **P0 — Safe delivery spine** | Minimum reproducible coordinated release, compatibility and deployment protections; remove traps that could invalidate subsequent features. Keep full Internet and bulk-export work later. | [Shared frontend/release](shared-frontend-and-release-lifecycle.md), [Secure operations](secure-operations-and-capacity.md), [technical debt](../technical-debt.md) | A documented, pinned frontend/backend pair, manifest/notes/CI evidence, verified compatibility/recovery checks, safe local/LAN configuration; production stays NO-GO pending human gates. |
| **P1 — One UI and persona entry** | One shared frontend/provider boundary for Demo and Server while introducing the role-aware application skeleton. Migrate working domain screens **progressively**, without duplicating the old shell. | [Role-based UX](role-based-user-experience-and-guided-navigation.md), [Shared frontend/release](shared-frontend-and-release-lifecycle.md) | At least one real Catalog/Task/Campaign journey uses the **same view implementation** in both modes; role/capability routing and 401/403/409 behavior work; Demo stays standalone. |
| **P2 — Configurations are usable and costable** | Register enterprise access, versioned commercial offers/meter rules, basic OS availability, reusable setup modules/recipes, and user environment; expose this information during configuration selection. | [Accessibility & pricing](technology-accessibility-and-pricing.md), [OS compatibility](os-compatibility-and-user-environment.md), [Composable guides](composable-setup-guides.md) | A real Model/Provider/Harness or Framework participant configuration has pinned component/offer references, a coherent consumption schema and an applicable environment/setup candidate; unknowns remain explicit. |
| **P3 — Evaluate in a campaign** | Give workgroup users their central Test Case × AI Solution matrix, flexible evaluation scope, guided setup and tariff-driven Runs; connect the Workgroup Studio to the real experiment flow. | [Campaign matrix](campaign-evaluation-matrix.md), [Pricing](technology-accessibility-and-pricing.md), [Guides](composable-setup-guides.md), [Role-based UX](role-based-user-experience-and-guided-navigation.md) | Workgroup can plan/select/waive/repeat an evaluation, record individual or composite evidence and true meter inputs, resume an incomplete attempt, and inspect exact campaign/Run revisions. |
| **P4 — Publish evidence, make it actionable** | Introduce a single effective-evidence and partial-publication rule; validate the setup *for included Runs*, support correction/withdrawal, and present method-based engineering results and an actionable My AI Workspace. **First complete business loop.** | [Publication lifecycle](publication-and-information-lifecycle.md), [Guides](composable-setup-guides.md), [Role-based UX](role-based-user-experience-and-guided-navigation.md), [Campaign matrix](campaign-evaluation-matrix.md) | An engineer navigates Task → applicable measured configuration → evidence/limits → current guide → feedback/access interest; only eligible published Runs affect ranking; reopening/correction/withdrawal never misrepresents active or historical evidence. |
| **P5 — Quantify opportunities and explain them** | Reuse **delivered DAP-01** workloads and P2–P4 evidence/pricing to compute the Task-tree × configuration profitability matrix, scenario summaries, three non-overlapping annual opportunity slices, immutable trends and drill-down provenance. Build Management Insights on these same data. | [Deployment & Adoption Planning §§3–9, 12–13](deployment-and-adoption-planning.md), [Role-based UX](role-based-user-experience-and-guided-navigation.md) | Authorized planner/manager can see a qualified annual *potential* (not realized savings), forecast vs measured maturity, assumptions and revision-accurate derivation; missing inputs never produce invented values. |
| **P6 — Target adoption and resources** | Explicitly select beneficiaries, track component entitlements, installation/OS readiness, provisioned and verified rights, confirmed first use, then derive pilot, rollout and optional active-usage capacity budgets. | [Deployment & Adoption Planning §§10–13](deployment-and-adoption-planning.md), [Pricing](technology-accessibility-and-pricing.md), [OS](os-compatibility-and-user-environment.md), [Guides](composable-setup-guides.md) | Authorized users trace opportunity → deliberate deployment target → access/first-use status → source-backed budget; privacy and distinct experimental/rollout/active budget totals are enforced. |
| **P7 — Govern, retain and operate at scale** | Complete the passive Governance Audit Explorer, controlled soft deletion / orphan preview and privileged purge/retention policy; deliver secured resumable native/full archive transfer, operations policies/capacity warnings and remaining exposure profiles. | [Audit explorer](data-governance-audit-explorer.md), [Publication lifecycle](publication-and-information-lifecycle.md), [Secure operations](secure-operations-and-capacity.md), [Shared frontend/release](shared-frontend-and-release-lifecycle.md) | An authorized maintainer can inspect exact who/what/when/diffs without new business-user forms; a separately privileged operator can dry-run and safely purge genuinely unreferenced content; large verified archives transfer over authenticated HTTP(S); wider exposure only after its own security acceptance. |

**Early value checkpoints:** P1 = first shared usable UI; P3 = first planned, fully recorded evaluation; **P4 = first end-to-end published recommendation path**; P5 = first quantified, explainable management decision. Do not wait for P6/P7 to show P4 value. The release process may publish intermediate compatible builds, but no build is implicitly production-approved.

## Essential phase contracts and dependencies

### P0–P1: protect the core without gratuitous refactoring

- One **monorepo**, independently identified frontend and backend artifacts, one *coordinated* immutable release manifest with their digests, API/schema/migration compatibility, release notes, tests and recovery references. Rebuilds and dependencies should be pinned. Compatible changes use backward-compatible API evolution; incompatible data migrations need isolated rehearsal, verified recovery, explicit authorized production action and **never** staging DB promotion. Reuse [PLAT release readiness](../release-readiness.md) and its unchanged NO-GO rule.
- Fix CI input coverage, basic release/package versioning, secure development vs LAN defaults and authorization-critical export gaps before depending on them. Progressively normalize typed API contracts and shared HTTP/CSRF/error handling, rather than rewriting every Django endpoint. **Internet ingress is not a prerequisite to local/LAN demonstrations.**
- Combine role-aware route/shell/navigation redesign with the provider-backed shared frontend. Each migrated journey includes real Server RBAC/optimistic conflict handling and independently working fake Demo. Preserve the workgroup read-only daily campaign board, maintenance-only entry and all existing data/screen functionality. No all-at-once rewrite.

### P2–P4: the shortest trustworthy workgroup → engineer route

- P2 pricing offers are **versioned alternatives with cumulative charge components**; the workgroup explicitly selects applicable offers per configuration/participant. Distinguish enterprise-wide accessibility, user entitlement, OS compatibility, price, and actual first use. Subscriptions/seat fees remain separate from measured marginal consumption, and unknown consumption is never zero. Existing catalog candidates can remain unavailable or unbenchmarked.
- P2 supported OS classification is **Windows/Linux only**, mandatory for newly classified Harness/Framework records, historical unknowns retained; users self-declare available systems. OS mismatch affects practical shortlist and setup matching, **not discovery suppression**. Setup modules + ordered recipes use exact versions, configuration and execution environment, including Framework wiring and participant guides; do **not** block catalog creation on guide completeness.
- P3 matrix is generated from **Task-associated configurations and that Task's Test Cases**, not a global Cartesian product. Keep distinct **Not Selected**, **Planned/Pending**, **Waived with reason**, **In Progress**, **Evaluated/Completed** and repeated Runs. Waivers satisfy waived plan obligations but are never treated as observed results. Campaign plans can evolve under immutable revisions after reopening.
- Each P3 Run snapshots exact configuration/participant(s), TC, environment, selected offer revisions, applicable Setup Guide and evidence. Meter fields come **from the selected tariff**; an incomplete pre-run tariff prevents starting the affected Run. Missing *post-run* required consumption retains the attempt as pending, with all partial data. Failed DoD is publishable **negative evidence** if otherwise complete. Composite Framework metrics belong to the overall workflow, never automatically to individual participants.
- P4 publication validates initial guide/recipe coverage **only for the selected completed Run subset**. A workgroup member can publish an eligible subset while other evaluations remain pending. Reopening retains the last effective publication. Guide improvements do not rewrite or automatically re-review historical pinned guides/Runs.
- **One centrally enforced active-evidence rule:** publication membership, completion and authorization, Run correction/supersession and withdrawal. Changes promptly remove invalidated sources from *all* current results/rankings/guide contexts/DAP-derived projections (fail closed or mark stale until recomputed). Preserve immutable historical publication/calculation snapshots. Editorial Recommendations are descriptive and may not override measured methodological ranking; never turn a Forecast or a negative Run into a positive measured recommendation.
- P1/P3/P4 UX results: Workgroup Studio's **one navigable grouped knowledge map** with resolvable attention counters only; Task and solution deep links, simple steppers only for sequential operations, breadcrumbs, local resumable unsaved drafts, existing expected_revision/409 for shared edits, one owner per Run. Engineer **My AI Workspace** prioritizes relevant Tasks/configurations and reuses one composed AI Solution detail, current guides, feedback/interest and Workgroup news. No duplicate solution catalog or mandatory workflow orchestrator.

### P5–P6: economic and adoption value, not a new measurement system

- Preserve [DAP-01](../workload-planning.md): scoped immutable job/specialty/person/cohort workloads, Task frequencies, overrides and confidential rates. P5 adds the **Task hierarchy on the left, AI configurations horizontally**, scoped by authorized population, not an employee × Task primary grid. Cell **fill** represents economic potential; **one icon** represents only maturity/deployment state. Idea-only and uncovered cells never receive fabricated financial figures.
- Use declared baselines, assisted human effort, appropriately blended Forecast/Benchmark evidence and P2 variable pricing, plus uncertainty, failed attempts and applicable TC coverage. Distinguish **Activated Potential**, **Benchmarked Opportunity**, **Forecast Opportunity** as non-overlapping annualized *capacity values* (not cash savings), including partial deployment. Preserve snapshots and source-version-aware historical trends. Click-through provenance should be incremental: summary → formula factors → exact revision/evidence, not an oversized static graph.
- P6 deployment requires **deliberate selection**; viewing a promising cell does not create access requests or licenses. Track enterprise component availability, **person-specific external-tool entitlements**, environment/setup readiness, verification and first confirmed use separately. Derive **experimental pilot**, **rollout** and optional **already-active** resource needs without duplicate counts or imaginary credentials; distinguish fixed and variable spending. Restrict person-level/rate/entitlement data through queries, UI, chart tooltips and exports.
- Management Insights is an entry to P5/P6 projections, not another calculation engine. A high-scoring tool with an incompatible OS remains visible as a potential opportunity, not immediately runnable or deployed.

### P7 and continuous controls: governance without blocking delivery

- The [Data Governance Audit Explorer](data-governance-audit-explorer.md) is a **passive inspector** of committed changes, before/after revisions, actor/time and links inside independently permissioned **/maintenance**. Reuse the existing audit stream; no new ordinary-user audit fields or redundant Activity Feed.
- [Publication Lifecycle](publication-and-information-lifecycle.md) owns delete/retire/withdrawal semantics and purge eligibility. Soft-delete is normal. Physical purge is a *separate, privileged* idempotent action with orphan inventory, dry-run reference/hold/backup checks, race-safe recheck, configurable optional retention/schedule and durable receipt. Thirty days is an example, **not** a universal auto-delete default. Protect deduplicated shared blobs and historical/published references.
- Operational archives: keep portable **native business archive** and **complete coordinated recovery point** distinct; explicit export-creation vs full-download grants, immutable background-produced artifacts, archive-scoped short-lived credentials, authenticated resumable Range downloads, manifest/hash validation and bounded memory. Reuse Django/PostgreSQL/Caddy/storage unless load measurements justify extra infrastructure.
- Add versioned, bounded operator limits/thresholds, health/capacity signals and safe dev/LAN/Internet profiles; separately qualify genuine Internet or multi-BU access. The release compatibility/operator workflow is progressively completed here, but the minimal P0 manifest and gates must already exist.
- Remaining heavy browser/accessibility, volume/soak, public-ingress and production-sized recovery drills remain [tracked deferred checks](../technical-debt.md) until the relevant rollout gate; each newly delivered feature **still requires** focused positive, negative, security and nonregression checks.

## Dependency and parallel-work rules

The principal value-producing path is:

**P0 minimum safeguards + P1 shared foundation → P2 offer/environment/setup contracts → P3 matrix and measured Runs → P4 active publication and engineer usage → P5 opportunity calculation → P6 access and budgets**.

- **Parallelizable:** P0 release/CI work and P1 view convergence after agreeing the minimal API contract; P2 pricing vs OS vs guide catalog models; P3 matrix presentation vs guide capture; P5 economic projection engine vs P4 engineer-oriented UX (but publication-dependent calculations cannot be declared correct before P4's effective-evidence contract); P7 audit inspection and remote-transfer engineering can advance whenever their permissions/event-storage dependencies exist.
- **Do not parallelize contradictory authorities:** a second tariff schema in Run forms; a second active evidence/ranking filter; a second guide copy/store; a second audit pipeline; a second frontend presentation. Resolve shared contracts before splitting work.
- **Do not block the first result on:** physical purge automation, multi-GiB export completion, Internet domain/SSO, full visual E2E suite, optional active-capacity budget or speculative service extraction. **Do block unsafe exposure or destructive changes** on their applicable security, backup, migration and independent recovery gates.

## Source-to-phase coverage matrix — no feature omitted

Every accepted future-evolution specification listed in the [domain register](README.md) is represented below. These links point to the **authoritative scope**, not a replacement abridgment.

| Original authoritative specification | Accountable phases | Covered outcomes |
| --- | --- | --- |
| [Campaign Evaluation Matrix](campaign-evaluation-matrix.md) | **P3**, P4 | Task/TC/configuration planning and matrix; selection, pending, waiver, repetition, mutable plan/immutable history; partial publication consumes eligibility from P4. |
| [Composable Setup Guides & Lifecycle](composable-setup-guides.md) | **P2–P4**, P6 | Version/environment-aware reusable modules and recipes; inline capture; workflow/composite setup; initial publish validation; later corrections without historical cascades; engineer/deployment retrieval. |
| [Technology Accessibility & Pricing Management](technology-accessibility-and-pricing.md) | **P2–P4**, P5–P6 | Enterprise status; free/PAYG/credits/usage/subscription/tier/hybrid offers; manual choice, exact tariff history and dynamic Run meters; cost, composite accounting and derived budgets. |
| [OS Compatibility & User Environment](os-compatibility-and-user-environment.md) | **P2**, P4, P6 | User Windows/Linux self-declaration; Harness/Framework support; composite compatibility and visible other-OS alternatives; guide/deployment readiness. |
| [Deployment & Adoption Planning](deployment-and-adoption-planning.md) | **DAP-01 already delivered**; **P5–P6** | Workload source; economic methodology/matrix, maturity, scenario, three annual slices, historic projections, provenance; intentional deployment, access verification, first use, pilot/rollout/active resources, privacy. |
| [Role-Based User Experience & Guided Navigation](role-based-user-experience-and-guided-navigation.md) | **P1**, P3–P5, P7 | Four experiences (Engineer, Management, Workgroup, Maintenance); grouped Studio map, conditional attention, solution detail, role entry, breadcrumbs/deep links, steppers, local drafts, conflict UX and reusable evidence-based ranking. |
| [Publication & Information Lifecycle](publication-and-information-lifecycle.md) | **P4**, P7 | Eligible subset publication and reopened campaigns, pending/negative evidence, corrections/revocation, active-vs-historical projections, soft delete and protected privileged physical GC. |
| [Data Governance Audit Explorer](data-governance-audit-explorer.md) | **P7** (event contracts from P0/P4) | Authorized passive search/detail/diff/revision/provenance of committed operations and administrative/purge events; shared audit capture. |
| [Shared Frontend, API Contracts & Release Lifecycle](shared-frontend-and-release-lifecycle.md) | **P0–P1**, continued through P7 | Unified Demo/Server provider views, contract/version discipline, independent artifacts/coordinated manifest, compatibility checks, release notes, operator stages and migration/recovery/CI gates. |
| [Secure Operations, Remote Archives & Capacity Governance](secure-operations-and-capacity.md) | **P0**, **P7** | Safe profiles and privileges first; separate native/full archive purposes, async immutable export, scoped resumable verified HTTP(S) delivery, versioned limits and capacity/health, later Internet security acceptance. |

### Technical-debt and verification crosswalk

Source: [Technical Debt & Deferred Engineering Checks](../technical-debt.md).

| Records | Incorporated in |
| --- | --- |
| **TD-01/02/06/07/08/10** (shared view, CI paths, dependency pinning, typed contracts, reproducible release, common helpers) | P0–P1; release/operator completion remains coordinated through P7 |
| **TD-04** (deployment profile/TLS/auth hardening) | P0 local/LAN safeguards; P7 Internet exposure acceptance |
| **TD-03/05/09** (evidence-list hashing, archive privileges/large exports, capacity limits) | Early P0 permission safeguard as needed; P7 scalable implementation/policies |
| **TD-11** (stale documentation status) | Ongoing documentation hygiene, not a business feature |
| **TD-V01–V06** (deferred real-browser, volume, Internet, operational restore, measured optimization, full supply-chain audit) | Track against the corresponding P1/P4/P7 deployment gates; never waive minimum feature/regression/security checks |
| **Existing PLAT-32/26/35/34/29 gates and operational NO-GO** | Preserved across *all phases*; issue closure is not production sign-off |

## Tracking and change governance

This file is the **single high-level plan**, not a duplicate feature specification or technical issue backlog. The [domain register](README.md) remains the functional inventory; [features ledger](../features/README.md) remains the approval record; [PLAT roadmap](../platform-implementation-roadmap.md) describes the **already delivered** platform implementation history.

| Phase | Planning state | Implementation status | Evidence/issue references |
| --- | --- | --- | --- |
| P0 | Proposed | Not started as this future plan | — |
| P1 | Proposed | Not started as this future plan | — |
| P2 | Proposed | Not started as this future plan | — |
| P3 | Proposed | Not started as this future plan | — |
| P4 | Proposed | Not started as this future plan | — |
| P5 | Proposed (DAP-01 baseline already delivered) | Remaining feature scope not started | [DAP-01](../workload-planning.md) |
| P6 | Proposed | Not started as this future plan | — |
| P7 | Proposed | Not started as this future plan | — |

**Update protocol:** When the owner accepts/reorders this plan, record that decision and the change rationale here, keep all source links intact, and *only later* derive appropriately bounded implementation issues with dependencies and acceptance evidence. A phase is complete only when the described end-user/operator outcome, applicable invariants and evidence are demonstrated, not merely when its code or a prototype exists. No GitHub issues are created by this plan.
