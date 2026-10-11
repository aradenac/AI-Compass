# Remaining future evolutions — AI Compass

> **Updated:** 2026-10-11. This directory contains **only outstanding functional/operational evolutions and the delivery ledger**, not specifications of already delivered FUT features.
> **Authoritative implementation priority:** [Live delivery ledger](implementation-plan.md). [Issues #75–#91](https://github.com/aradenac/AI-Compass/issues?q=is%3Aissue+is%3Aclosed) are closed. Initial UX recovery [#114–#116](https://github.com/aradenac/AI-Compass/issues/114) is merged/closed. Outstanding desktop UX completion [#123–#126](https://github.com/aradenac/AI-Compass/issues/123) is now **first**, before P7 #92–#95.

## What remains

| Future requirement | Scope / owning issue | Prerequisites |
| --- | --- | --- |
| [Controlled retirement and physical purge](controlled-retirement-and-purge.md) | FUT-18 [#92](https://github.com/aradenac/AI-Compass/issues/92): archive/retire, safe orphan preview, protected history/holds, race-safe purge and optional bounded retention | UX-R07 #126, #76, #85, #91, #116 |
| [Secure remote archives and Internet/capacity](secure-operations-and-capacity.md) | FUT-19 [#93](https://github.com/aradenac/AI-Compass/issues/93): immutable asynchronous native/full archive transfer; FUT-20 [#94](https://github.com/aradenac/AI-Compass/issues/94): resource policy, dashboard and Internet ingress | #93 after #126; #94 after #93 |
| [Guided compatible/incompatible release operations](guided-release-operations.md) | FUT-21 [#95](https://github.com/aradenac/AI-Compass/issues/95): check/stage/deploy/status/recover CLI and guarded staging, approval and recovery | #126, #116, #75, #76, #93 |

**Execution order:** completed UX [#114](https://github.com/aradenac/AI-Compass/issues/114), [#115](https://github.com/aradenac/AI-Compass/issues/115), [#116](https://github.com/aradenac/AI-Compass/issues/116); now implement UX-R04 [#123](https://github.com/aradenac/AI-Compass/issues/123) → UX-R05 [#124](https://github.com/aradenac/AI-Compass/issues/124) → UX-R06 [#125](https://github.com/aradenac/AI-Compass/issues/125) → UX-R07 [#126](https://github.com/aradenac/AI-Compass/issues/126); then resume existing FUT [#92–#95](https://github.com/aradenac/AI-Compass/issues/92). These are **corrective UI/quality issues for the already approved domain specs**, not a new business-feature catalogue. Desktop web only; do not add mobile requirements.

## Delivered scope is documented elsewhere

The detailed normative requirements for completed FUT work have moved to regular maintained documentation:

| Domain | Current product reference |
| --- | --- |
| Campaign scope, Test Case matrix and versioned planning | [Campaign Evaluation Matrix](../campaign-evaluation-matrix.md) |
| Reusable setup modules, recipes and guide history | [Composable Setup Guides](../composable-setup-guides.md) |
| Provider/model/harness availability and versioned commercial terms | [Accessibility and Pricing](../technology-accessibility-and-pricing.md) |
| OS environment, capabilities and compatibility | [OS Compatibility & User Environment](../os-compatibility-and-user-environment.md) |
| Economic scenarios, opportunities, beneficiaries and resource budgets | [Deployment and Adoption Planning](../deployment-and-adoption-planning.md) |
| Engineer/Workgroup/Management/Maintenance UX principles | [Role-Based User Experience](../role-based-user-experience-and-guided-navigation.md) |
| Published subset, effective Run correction/withdrawal | [Publication and Information Lifecycle](../publication-and-information-lifecycle.md) |
| Passive committed-change audit and governance explorer | [Data Governance Audit Explorer](../data-governance-audit-explorer.md) |
| Coordinated manifests, API compatibility and frontend architecture | [Shared Frontend & Release Lifecycle](../shared-frontend-and-release-lifecycle.md) |
| Development/LAN safe operating modes | [Operational Profiles](../secure-operations-baseline.md) |

Business features already delivered are **not** recreated as future proposals merely because UX-R01–03 will restore presentation compliance. Existing domain API, evidence, immutable revisions, data permission and rollout requirements remain in their operational docs.

## Planning, history and safety

- [Live implementation plan: done/open/deferred and sequencing](implementation-plan.md)
- [Delivered feature ledger](../features/README.md)
- [2026-10-10 original approved roadmap](../history/fut-plan-approved-2026-10-10.md)
- [Historical prior thematic mapping](../history/future-evolution-map-2026-10-10.md)
- [Release readiness](../release-readiness.md): production **NO-GO** until real staging/browser/recovery acceptance and an authorized operational decision.

Planning, issue closure and production release approval are three different states. Do not infer deployment approval from a merged PR.
