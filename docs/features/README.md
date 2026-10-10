# Feature proposals and approval ledger (not the PLAT delivery backlog)

The product owner requested and authorized the [21-issue FUT implementation backlog](../future-evolutions/implementation-plan.md#approved-github-implementation-backlog--maximal-coherent-issue-slices) on **2026-10-10**. Issues **#75–#95 are open** with explicit prerequisites and feature-spec links. This is an approved **delivery plan**, not a claim that functionality is implemented, a production release GO, or authorization for extra speculative issues.

This directory is a **product-feature register**, separate from the
[approved PLAT issue roadmap](../platform-implementation-roadmap.md).
Detailed working specifications live in [../future-evolutions](../future-evolutions/README.md);
links here provide stable decision and approval state without duplicating
a long spec or making the spec look implemented.

**Governance contract:** A proposal, a product decision, a prototype, a
specification document or a partial implementation is **not** authorization
to automatically create/execute the next GitHub feature issue. The project
owner must validate any **new or changed** scoped issue plan (dependencies, delivery order,
acceptance and priority) first. The previously approved **PLAT** issues #35, #26, #32 and #33 are now
closed as code-delivery items; real staging acceptance, migration rehearsal
and production GO/NO-GO remain **deferred operational gates**, not evidence
that deployment was approved. Do not mix candidate features with future
[platform-consolidation proposals](../future-evolutions/README.md#platform-consolidation-prerequisites--accepted-technical-direction)
or infer implementation authorization for **unplanned** scope merely because technical scope was
discussed and documented.

| Future feature | Original authoritative specification | Implementation issue(s) | Delivery state |
| --- | --- | --- | --- |
| Campaign Evaluation Matrix | [Spec](../future-evolutions/campaign-evaluation-matrix.md) | [#82](https://github.com/aradenac/AI-Compass/issues/82), [#84](https://github.com/aradenac/AI-Compass/issues/84) | Planned, not implemented |
| Composable Setup Guides & Lifecycle | [Spec](../future-evolutions/composable-setup-guides.md) | [#81](https://github.com/aradenac/AI-Compass/issues/81), [#83](https://github.com/aradenac/AI-Compass/issues/83), [#84](https://github.com/aradenac/AI-Compass/issues/84) | Planned, not implemented |
| Data Governance Audit Explorer | [Spec](../future-evolutions/data-governance-audit-explorer.md) | [#91](https://github.com/aradenac/AI-Compass/issues/91) | Planned, not implemented |
| Technology Accessibility & Pricing Management | [Spec](../future-evolutions/technology-accessibility-and-pricing.md) | [#79](https://github.com/aradenac/AI-Compass/issues/79), [#83](https://github.com/aradenac/AI-Compass/issues/83), [#87](https://github.com/aradenac/AI-Compass/issues/87), [#90](https://github.com/aradenac/AI-Compass/issues/90) | Planned, not implemented |
| OS Compatibility & User Environment | [Spec](../future-evolutions/os-compatibility-and-user-environment.md) | [#80](https://github.com/aradenac/AI-Compass/issues/80), [#86](https://github.com/aradenac/AI-Compass/issues/86), [#89](https://github.com/aradenac/AI-Compass/issues/89) | Planned, not implemented |
| Role-Based UX & Guided Navigation | [Spec](../future-evolutions/role-based-user-experience-and-guided-navigation.md) | [#77](https://github.com/aradenac/AI-Compass/issues/77), [#78](https://github.com/aradenac/AI-Compass/issues/78), [#86](https://github.com/aradenac/AI-Compass/issues/86), [#88](https://github.com/aradenac/AI-Compass/issues/88) | Planned, not implemented |
| Publication & Information Lifecycle | [Spec](../future-evolutions/publication-and-information-lifecycle.md) | [#84](https://github.com/aradenac/AI-Compass/issues/84), [#85](https://github.com/aradenac/AI-Compass/issues/85), [#92](https://github.com/aradenac/AI-Compass/issues/92) | Planned, not implemented |
| [Deployment & Adoption Planning](deployment-and-adoption-planning.md) | [Full spec](../future-evolutions/deployment-and-adoption-planning.md) | [#87](https://github.com/aradenac/AI-Compass/issues/87), [#88](https://github.com/aradenac/AI-Compass/issues/88), [#89](https://github.com/aradenac/AI-Compass/issues/89), [#90](https://github.com/aradenac/AI-Compass/issues/90) | **DAP-01 delivered**; rest planned, not implemented |
| Shared Frontend, API Contracts & Release Lifecycle | [Technical spec](../future-evolutions/shared-frontend-and-release-lifecycle.md) | [#75](https://github.com/aradenac/AI-Compass/issues/75), [#77](https://github.com/aradenac/AI-Compass/issues/77), [#78](https://github.com/aradenac/AI-Compass/issues/78), [#95](https://github.com/aradenac/AI-Compass/issues/95) | Planned, not implemented |
| Secure Operations, Remote Archives & Capacity Governance | [Technical spec](../future-evolutions/secure-operations-and-capacity.md) | [#76](https://github.com/aradenac/AI-Compass/issues/76), [#93](https://github.com/aradenac/AI-Compass/issues/93), [#94](https://github.com/aradenac/AI-Compass/issues/94), [#95](https://github.com/aradenac/AI-Compass/issues/95) | Planned, not implemented |

## Delivery status and exceptions

- **DAP-01 / [issue #66](https://github.com/aradenac/AI-Compass/issues/66) /
  [PR #67](https://github.com/aradenac/AI-Compass/pull/67):** already merged
  as an isolated, additive, private workload-profile foundation. The
  implemented contract is in [../workload-planning.md](../workload-planning.md).
  Preserve and maintain it; this merge **must not** be used to assert that
  the broad Deployment & Adoption Planning proposal has been validated.
- **Remaining DAP scope:** now mapped to **FUT-13–FUT-16 (#87–#90)**, not to newly created issues named DAP-02 etc. DAP-01 remains the delivered foundation; the four FUT issues are open and not implemented. Follow dependency order, not an automatic numeric queue.

## Approval promotion protocol

An owner-approved transition should explicitly record what scope is accepted,
what questions remain unresolved, an ordered set of bounded GitHub issues
with prerequisites/acceptance, and the author/date of the decision.
Only then move the status from *proposed* to *approved for implementation*
and link the actual issues. Keep the original specification traceable;
do not erase proposals, change history or retrospectively call them delivered.

**Approval decision recorded:** 2026-10-10, project owner requested creation of coarse phase-aligned GitHub issues. Per-issue implementation PRs, acceptance evidence and any later scope changes remain subject to their own checks. Deferred real staging/production gates remain unchanged.
