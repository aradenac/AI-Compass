# AI Solutions & Recommendations — Workgroup UI contract

> **Related deployment UI:** [Deployment & Access prototype](prototypes/deployment-access/index.html) · [specification](deployment-access-workgroup-ui-spec.md). Eligible persons may initiate a **global Publish** action from the Deployment matrix, but that action must use the same authorized AI Solutions editorial publication gate. Unpublish/revoke belongs only to AI Solutions; publication cannot be implied by a checked individual licence or installation.


**Approved product-owner prototype:** [interactive HTML](prototypes/ai-solutions/index.html) · [design handoff](prototypes/ai-solutions/DESIGN.md). See [prototype convention](prototypes/README.md).

**Current implemented baseline:** [Evidence-linked Recommendations](recommendations-server.md), [Results Explorer target](results-explorer-workgroup-ui-spec.md), [Role-based UX](role-based-user-experience-and-guided-navigation.md), and [Composable Setup Guides](composable-setup-guides.md). This document defines the *target experience*, not yet-implemented APIs or thresholds.

## Entry inventory and discovery

The **only default inventory** is the current **minimal recommended portfolio of individually measured, positively qualified AI Solutions UNION every currently published AI Solution**. The latter remain discoverable even if later results degrade their qualification, or they leave the minimal selection. Mark them clearly “outside current portfolio; publication maintained” and require an explicit authorized withdrawal decision; never silently hide/unpublish. Include withdrawn solutions only when eligible under the current portfolio or appropriately reachable via authorized history; publication and qualification are distinct.

No Task tree or Task names are shown in this view. Search solution/configuration text; allow categorization by **project phase** or **profession/specialty**, with publication-state filtering. These classifications derive from existing Task associations/labels and must not imply duplicated solution identities.

The portfolio must **maximize validated evaluated-Task coverage using the smallest sensible set** under explicit, auditable and versioned qualification, methodological comparability, coverage and tie-break rules. The heuristic used in the standalone demo is illustrative only. Qualification requires real published, accepted individual Runs satisfying defined criteria; no Forecasts or composite Framework results can qualify an individual solution. Do not assume missing data means positive evidence.

## Two-column presentation

**Left:** searchable, filterable inventory described above, grouped by phase/specialty. No option to switch into the full measured inventory in the default view.

**Right:** one solution details/editor pane. Show full exact configuration, publication state, editable Workgroup editorial note (strengths, appropriate uses, limitations) and **linked applicable Guides**. Avoid redundant raw proof metrics, selection-method explanations, evidence provenance and KPI strip; use Results Explorer for primary result inspection.

At the **top of the solution detail**, place explicit **Publish / Unpublish** action. Directly below it show the **publication readiness/diagnostics**, never far below the editable text and guides. A withdrawn solution must retain editorial history and evidence. If source evidence later becomes unfavorable, surface an actionable review warning rather than silently revoking publication.

## Guide linking and readiness

Guides are **references to existing catalog records, not checkboxes or duplicated document bodies**.
- Resolve/apply compatible linked component and harness guides **automatically** from the exact Model/Provider/Harness/Framework, version/configuration and environment where relevant.
- Permit the Workgroup to **attach additional catalog guides manually** and remove manual links, with provenance (“automatic” versus “manual”).
- Automatic bindings must be based on actual compatible authoritative metadata, not matching only by display names. Respect existing guide composition and exact configuration pinning.
- Present missing mandatory documentation in a clear diagnostic beside Publish; distinguish “linked” from “reviewed/applicable” as required by a future readiness policy. Do not invent completed user/setup/charter coverage from generic links.

## Editorial publication

Qualifying/published benchmark evidence **does not automatically expose an AI Solution to engineers**. Authorized Workgroup reviewers must finish the editorial note, check applicable documentation and explicitly publish. They can later unpublish/revoke with a required rationale. Editing notes must not change original measured results or calculate a subjective score override.

**Backend integration gap:** currently persisted Recommendations are Task+Solution+Run-pinned reviewed records, not a global per-solution engineer visibility state. Extend the domain deliberately and additively; preserve original recommendation IDs, visibility, immutability, review and unpublish guarantees. Define a consistent link between the new global solution publication gate and the existing per-Task published recommendation semantics. Do not implement the new UX by pretending Task-pinned Recommendation publication already gates all solution visibility.

## Acceptance

- In the first view, return only minimal recommended candidates plus already published solutions, with deterministic de-duplication and explicit stale/out-of-portfolio labelling.
- Verify grouping/search/status filters, responsive two-column desktop rendering at 1366×900 and 1024px, and keyboard accessibility.
- Verify source qualification excludes Forecasts, composite runs, failed DoD and unpublished evidence.
- Validate automatic Guide eligibility, extra manual Guide references, unlinking and readiness messages.
- Verify immediate publish diagnostics, authorized publication and explicit justified unpublication; never change public visibility solely because benchmark scores evolve.
- Preserve Server/Demo separation, immutable originals, backend access controls and review history. Inspect actual captured screenshots visually.

The standalone prototype contains fictitious in-memory data and does not imply backend implementation.
