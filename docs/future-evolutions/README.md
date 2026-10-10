# Future evolutions — functional domain map

This directory preserves the **accepted product direction and detailed working specifications** for AI Compass's future capabilities.

**Approved issue backlog (2026-10-10):** The [Outcome-led Implementation Plan](implementation-plan.md#approved-github-implementation-backlog--maximal-coherent-issue-slices) now connects every functional and technical proposal to **21 owner-requested issues #75–#95**. These are implementation plans, **not delivered functionality**; original specs remain authoritative, and real release acceptance remains NO-GO. The directory remains a thematic map, not a new repository-wide documentation hierarchy.

**Do not confuse:** the implemented product baseline in [Product Definition](../product-definition.md), existing delivered server capabilities, proposed future behavior, and the now-approved implementation backlog. Original feature pages are preserved at their existing paths; only their cross-references/contradictions are harmonized. Repository-wide folder moves and the overall `docs/features` register restructuring are **explicitly deferred**.

## Five business domains

### A. Technologies & Référentiels

| Source of truth | What it owns | Consumed by |
| --- | --- | --- |
| [OS Compatibility & User Environment](os-compatibility-and-user-environment.md) | User Windows/Linux self-declaration; required Harness/Framework supported OS; coarse composite compatibility and other-OS discovery. | Personalized Engineer view, Setup Guide matching, deployment eligibility. |
| [Technology Accessibility & Pricing Management](technology-accessibility-and-pricing.md) | Enterprise accessibility, versioned offers, exact per-configuration commercial selection, dynamic Run meter inputs and calculated reference variable costs. | Benchmark Workspace, Results, Profitability, Budget. |

**Keep separate:** OS compatibility, enterprise technology accessibility, individual entitlements and actual first use. The **chosen Pricing Offer**, not an ad hoc Run form, specifies which consumption units must be recorded. All Pricing-derived publication gates are coordinated with [Information Lifecycle](publication-and-information-lifecycle.md).

### B. Benchmark & Reproducibility

| Source of truth | What it owns | Consumed by |
| --- | --- | --- |
| [Campaign Evaluation Matrix](campaign-evaluation-matrix.md) | Task → Test Case × candidate configuration planning, selected/not-selected/pending/waived/evaluated distinctions, repeated Runs, campaign revision and comparison matrix. | Benchmark Workspace, Results Explorer, Workgroup Studio. |
| [Composable Setup Guides & Lifecycle](composable-setup-guides.md) | Shared modules, configuration/environment-specific recipes, initial validation for **Runs included in a publication**, reusable guides and historical pinned applicability. | Campaign review, Run setup and Engineer solution detail. |

**Coordinating contracts:** [Pricing](technology-accessibility-and-pricing.md) owns commercial metering, and [Information Lifecycle](publication-and-information-lifecycle.md) owns **partial publication, pending Runs, correction and withdrawal**. A Campaign may publish its complete eligible subset without claiming its entire experimental plan is finished. A failed-DoD Run may be valid **negative evidence** if complete; a metering-incomplete attempt remains pending. A configuration candidate is **not yet a measured AI Solution** before its first controlled Run.

### C. Evidence, Comparisons & Economic Value

| Source of truth | What it owns | Consumed by |
| --- | --- | --- |
| Existing [Product Definition](../product-definition.md) and Results Explorer (baseline) | Separation of measured Runs, theoretical Forecasts and actual published experimental evidence; reproducible results and comparison methodology. | Workgroup and engineer discovery. |
| [Deployment & Adoption Planning](deployment-and-adoption-planning.md) — **Profitability & Opportunities** (§§5–9) | Task × configuration heatmap; profit-intensity fill / status icon; Forecast+Benchmark projections; three non-overlapping annual slices; historical snapshots and progressive calculation provenance. | Management, planning and Workgroup contextual exploration. |
| [Role-Based User Experience](role-based-user-experience-and-guided-navigation.md) — **AI Solutions / Recommendations** (§§4, 7) | **Presentation and personalized selection** based on currently eligible **methodology-based measured results**, supplemented but never overridden by editorial profile/limitations and documentation. | My AI Workspace and AI Solution Detail. |

The published experimental **methodology is authoritative for measured rankings**; the reviewed editorial Recommendation supplies descriptive context and limitations, **not arbitrary promotion, suppression or scoring overrides**. Publishing measured evidence is not auto-publishing a manual Recommendation; negative measured evidence must not be auto-promoted.

### D. Deployment, Access & Resources

| Source of truth | What it owns | Consumed by |
| --- | --- | --- |
| [Deployment & Adoption Planning](deployment-and-adoption-planning.md) — **Organization / Deployment / Budget** (§§3, 10–12) | Job/specialty/person workload, selected beneficiaries and actual verified use; individual entitlements/access flow; distinct experimental, rollout and optional active-usage capacity budgets. | Management, engineers, administration of external-tool access. |

**Partially delivered:** DAP-01 implemented the restricted, immutable **workload-profile foundation** — [existing Server contract](../workload-planning.md), [issue #66](https://github.com/aradenac/AI-Compass/issues/66), [PR #67](https://github.com/aradenac/AI-Compass/pull/67). This does **not** mean the future Profitability matrix, access management and budgets already exist.

The **same DAP source document spans C and D**; this thematic map assigns responsibility by subsection instead of copying or prematurely splitting it.

### E. Experience, Discovery & Knowledge

| Source of truth | What it owns | Consumed by |
| --- | --- | --- |
| [Role-Based User Experience & Guided Navigation](role-based-user-experience-and-guided-navigation.md) | Four permission-aware entry experiences; one categorized Workgroup Studio knowledge/navigation diagram and resolvable counters; contextual Task-tree/AI Solution exploration, stepper/breadcrumbs/draft recovery, sensible multi-user concurrency. | All user interfaces and supporting services. |
| Existing [Recommendations Server](../recommendations-server.md) and [Guides](composable-setup-guides.md) | Immutable published editorial solution profiles/Task-linked decisions and contextual documentation, **without creating a second solution catalog or manual ranking authority**. | AI Solution Detail and user-facing guidance. |

The user-facing solution detail is a **composed view** over current measured results, descriptive editorial records, relevant guides and real access status. Unrelated global discovery is secondary to the user's actual Task profile. A Workgroup attention badge appears **only** if the existing structured data provides a resolvable status; never fabricate To-Do states.

## Two cross-cutting capabilities

### X1. Publication, correction, withdrawal and controlled deletion — NEW

**Authoritative specification:** [Publication & Information Lifecycle](publication-and-information-lifecycle.md).

- Publish **only the eligible Run subset** and preserve incomplete session data privately; clearly disclose experimental coverage.
- Reopen a published Campaign **without withdrawing its last eligible published result set**; draft changes are not immediately public.
- Immediately propagate an **authorized published measurement correction or Run revocation** into the **current effective** public Results/rankings/profitability/resources, while preserving historic snapshots.
- Ordinary removal = **logical deletion/retirement**. Physically purging eligible, provably unreferenced files and managed DB records is a **privileged Maintenance & Governance control** with preview, safety/referential checks, configurable grace/optional automatic policy and durable audit.
- Thirty days is an illustrative configurable retention value, **not** an automatic purge of all unused historic data. Deduplicated files, published evidence and historical/archived pins must not be silently deleted.

**Cross-domain authority:** Campaign Matrix owns planning states; Pricing owns meter schema; Guides owns documentary readiness; this **Lifecycle page owns current effective publication, Run-level withdrawal, deletion and GC**. Read models must consume one consistent eligibility rule.

### X2. Governance and change audit

**Authoritative specification:** [Data Governance Audit Explorer](data-governance-audit-explorer.md).

Provides a passive, permissioned **history of committed changes, exact revisions and diffs** within the separate Maintenance interface. It is **not** the action authority for publication status, delete eligibility, purge policy or runtime comparisons. Reuse one underlying audit/event stream, with separate analytical provenance in DAP. New purge operations proposed in X1 appear as audited maintenance events without creating an alternate audit system.

## Platform consolidation prerequisites — accepted technical direction

These are **cross-cutting engineering proposals**, not new business feature domains and **not** an automatic GitHub implementation backlog. They specify how existing capabilities and future UX can be delivered safely without duplicating or weakening the platform.

| Technical direction | Owns | Coordination |
| --- | --- | --- |
| [Shared Frontend, API Contracts & Release Lifecycle](shared-frontend-and-release-lifecycle.md) | Keep one monorepo; converge Demo/Server on one shared presentation/provider boundary; component build/version identities, immutable release manifest + notes; API compatibility, reversible release orchestration, staged incompatible migrations. | Implement shared screens together with [Role-Based UX](role-based-user-experience-and-guided-navigation.md) to **avoid two frontend rewrites**. Preserve PLAT recovery and operational NO-GO gates. |
| [Secure Operations, Remote Archives & Capacity Governance](secure-operations-and-capacity.md) | Dev/LAN/Internet profiles; authenticated multi-GiB native and complete recovery downloads with resumable HTTPS, archive-specific short-lived tokens, protected jobs; versioned policy limits, proactive capacity and administrator controls. | Reuse Django/PostgreSQL/Caddy and existing archives/recovery mechanisms; keep operator capability separate from business-data permission and Data Governance Audit Explorer. |
| [Technical Debt & Deferred Checks](../technical-debt.md) | Observed implementation gaps, cleanup candidates and consciously deferred validation such as exhaustive browser/volume/public-ingress tests. | **Tracking only**; do not confuse deferred checks with accepted future business features or active GitHub issues. |

The owner selected **coordinated releases with independently identified frontend/backend artifacts**, not separate repositories/release trains; **both runtime modes remain permanent**. Existing specific migration scripts do **not** constitute a generic operator upgrade tool. Operational download retains HTTP(S) instead of requiring SCP/SSH, but must be redesigned for large immutable verified archives. No artifact may be treated as production-ready merely because CI passed; [PLAT-32 release readiness](../release-readiness.md) governs GO/NO-GO.

## Ownership and non-duplication rules

| Topic | Owner | Other proposals must do |
| --- | --- | --- |
| Task/TC evaluation obligations | Campaign Evaluation Matrix | Link to it, not implement independent gates. |
| Pricing and dynamic Run consumption form | Technology Accessibility & Pricing | Derive meters from pinned offers; do not redefine tariffs in Runs. |
| Setup module/recipe completeness | Composable Setup Guides | Reuse only applicable exact-version/environment instructions. |
| Partial publications, active vs historical evidence, withdrawal and GC | Publication & Information Lifecycle | Use common Run eligibility and propagate source changes; no competing publication rules. |
| Economic formulas, opportunity maturity/history and source navigation | Deployment & Adoption Planning | Reuse its calculations; Management is an entry view, not a separate data source. |
| Evidence-based engineer rankings | Results/methodology (authoritative) + Role-Based UX presentation | Editorial Recommendation remains *descriptive*, not a scoring override. |
| Individual OS compatibility | OS Compatibility & User Environment | Keep separate from enterprise access and individual entitlement. |
| Audit of committed changes | Data Governance Audit Explorer | Do not build a second audit event pipeline. |
| Persona home, steppers, breadcrumbs, local drafts and conflict UX | Role-Based User Experience | Reuse existing backend expected_revision/409 and RBAC. |

## Functional acceptance versus delivery status

| Feature specification | Product scope | Implemented today | Delivery plan/issues |
| --- | --- | --- | --- |
| Campaign Evaluation Matrix | Accepted future scope | Not delivered as proposed | [#82](https://github.com/aradenac/AI-Compass/issues/82), [#84](https://github.com/aradenac/AI-Compass/issues/84) |
| Composable Setup Guides & Lifecycle | Accepted future scope | Existing simpler Guides only | [#81](https://github.com/aradenac/AI-Compass/issues/81), [#83](https://github.com/aradenac/AI-Compass/issues/83), [#84](https://github.com/aradenac/AI-Compass/issues/84) |
| Technology Accessibility & Pricing Management | Accepted future scope | Existing commercial/evidence foundations only | [#79](https://github.com/aradenac/AI-Compass/issues/79), [#83](https://github.com/aradenac/AI-Compass/issues/83), [#87](https://github.com/aradenac/AI-Compass/issues/87), [#90](https://github.com/aradenac/AI-Compass/issues/90) |
| OS Compatibility & User Environment | Accepted future scope | Not delivered as proposed | [#80](https://github.com/aradenac/AI-Compass/issues/80), [#86](https://github.com/aradenac/AI-Compass/issues/86), [#89](https://github.com/aradenac/AI-Compass/issues/89) |
| Deployment & Adoption Planning | Accepted future scope | **DAP-01 workload foundation only** | [#87](https://github.com/aradenac/AI-Compass/issues/87), [#88](https://github.com/aradenac/AI-Compass/issues/88), [#89](https://github.com/aradenac/AI-Compass/issues/89), [#90](https://github.com/aradenac/AI-Compass/issues/90) |
| Role-Based User Experience & Guided Navigation | Accepted future scope | Existing separate user/workgroup screens, not target UX | [#77](https://github.com/aradenac/AI-Compass/issues/77), [#78](https://github.com/aradenac/AI-Compass/issues/78), [#86](https://github.com/aradenac/AI-Compass/issues/86), [#88](https://github.com/aradenac/AI-Compass/issues/88) |
| Publication & Information Lifecycle | Accepted future scope | Some Campaign revision/reopen/unpublish; **not** Run withdrawal, subset publication or safe GC | [#84](https://github.com/aradenac/AI-Compass/issues/84), [#85](https://github.com/aradenac/AI-Compass/issues/85), [#92](https://github.com/aradenac/AI-Compass/issues/92) |
| Data Governance Audit Explorer | Accepted future scope | Existing audit/event foundations, not complete explorer | [#91](https://github.com/aradenac/AI-Compass/issues/91) |

The linked **21-issue plan is now approved**. Repository-wide reorganization (`docs/features`, baseline/reference docs, global folder layout) remains **deliberately deferred**. Preserve original specs and historical decisions; implementation status is managed per issue/PR, not inferred from approved product scope.

**Baseline rule:** the existing [approved PLAT implementation roadmap](../platform-implementation-roadmap.md) remains separate from these future functional requirements. Creating or refining a spec alone does **not** automatically create, reprioritize or execute issues; the specifically owner-authorized FUT backlog is documented separately.
