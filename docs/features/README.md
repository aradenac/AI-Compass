# Feature proposals and approval ledger (not the PLAT delivery backlog)

This directory is a **product-feature register**, separate from the
[approved PLAT issue roadmap](../platform-implementation-roadmap.md).
Detailed working specifications live in [../future-evolutions](../future-evolutions/README.md);
links here provide stable decision and approval state without duplicating
a long spec or making the spec look implemented.

**Governance contract:** A proposal, a product decision, a prototype, a
specification document or a partial implementation is **not** authorization
to automatically create/execute the next GitHub feature issue. The project
owner must validate the scoped issue plan (dependencies, delivery order,
acceptance and priority) first. The previously approved **PLAT** issues #35, #26, #32 and #33 are now
closed as code-delivery items; real staging acceptance, migration rehearsal
and production GO/NO-GO remain **deferred operational gates**, not evidence
that deployment was approved. Do not mix candidate features with future
[platform-consolidation proposals](../future-evolutions/README.md#platform-consolidation-prerequisites--accepted-technical-direction)
or infer implementation authorization merely because technical scope was
discussed and documented.

| Candidate feature | Source specification | Status in repository | Approved delivery plan |
| --- | --- | --- | --- |
| Campaign Evaluation Matrix | [Spec](../future-evolutions/campaign-evaluation-matrix.md) | Proposed, decisions documented | **Not approved** — no plan of issues |
| Composable Setup Guides & Lifecycle | [Spec](../future-evolutions/composable-setup-guides.md) | Proposed, decisions documented | **Not approved** — no plan of issues |
| Data Governance Audit Explorer | [Spec](../future-evolutions/data-governance-audit-explorer.md) | Proposed, decisions documented | **Not approved** — no plan of issues |
| Technology Accessibility & Pricing Management | [Spec](../future-evolutions/technology-accessibility-and-pricing.md) | Proposed, decisions documented | **Not approved** — no plan of issues |
| [Deployment & Adoption Planning](deployment-and-adoption-planning.md) | [Complete working spec](../future-evolutions/deployment-and-adoption-planning.md) | **Partially delivered: DAP-01** | **DAP-02 onward not approved** |

## Delivery status and exceptions

- **DAP-01 / [issue #66](https://github.com/aradenac/AI-Compass/issues/66) /
  [PR #67](https://github.com/aradenac/AI-Compass/pull/67):** already merged
  as an isolated, additive, private workload-profile foundation. The
  implemented contract is in [../workload-planning.md](../workload-planning.md).
  Preserve and maintain it; this merge **must not** be used to assert that
  the broad Deployment & Adoption Planning proposal has been validated.
- **DAP-02 and subsequent phases:** design ideas only, **not** active issues
  and **not** automatically next priority. Await a separately approved
  coherent issue set, then revise this ledger and the approved roadmap.

## Approval promotion protocol

An owner-approved transition should explicitly record what scope is accepted,
what questions remain unresolved, an ordered set of bounded GitHub issues
with prerequisites/acceptance, and the author/date of the decision.
Only then move the status from *proposed* to *approved for implementation*
and link the actual issues. Keep the original specification traceable;
do not erase proposals, change history or retrospectively call them delivered.
