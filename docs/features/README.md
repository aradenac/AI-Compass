# Delivered features and approval ledger

> **Checked 2026-10-11:** original FUT issues #75–#91 are closed with code merged; the remaining original P7 issues #92–#95 are still open. UX recovery issues #114–#116 are merged/closed; new desktop UX completion issues #123–#126 are first priority before P7. This is a delivery-status register, **not** production release approval.

## Delivered functional and technical specifications

| Domain | Maintained specification | Closed implementation issues | Delivery |
| --- | --- | --- | --- |
| Campaign Evaluation Matrix | [Current contract](../campaign-evaluation-matrix.md) | [#82](https://github.com/aradenac/AI-Compass/issues/82), [#84](https://github.com/aradenac/AI-Compass/issues/84) | Code merged |
| Composable Setup Guides | [Current contract](../composable-setup-guides.md) | [#81](https://github.com/aradenac/AI-Compass/issues/81), [#83](https://github.com/aradenac/AI-Compass/issues/83), [#84](https://github.com/aradenac/AI-Compass/issues/84) | Code merged |
| Enterprise accessibility / pricing | [Current contract](../technology-accessibility-and-pricing.md) | [#79](https://github.com/aradenac/AI-Compass/issues/79), [#83](https://github.com/aradenac/AI-Compass/issues/83), [#87](https://github.com/aradenac/AI-Compass/issues/87), [#90](https://github.com/aradenac/AI-Compass/issues/90) | Code merged |
| OS compatibility / user environment | [Current contract](../os-compatibility-and-user-environment.md) | [#80](https://github.com/aradenac/AI-Compass/issues/80), [#86](https://github.com/aradenac/AI-Compass/issues/86), [#89](https://github.com/aradenac/AI-Compass/issues/89) | Code merged |
| Deployment and adoption planning | [Current contract](../deployment-and-adoption-planning.md) | DAP-01 [#66](https://github.com/aradenac/AI-Compass/issues/66), FUT [#87–#90](https://github.com/aradenac/AI-Compass/issues/87) | Code merged |
| Role-based UX, workgroup/engineer/management entries | [Normative UX requirements](../role-based-user-experience-and-guided-navigation.md) | [#77](https://github.com/aradenac/AI-Compass/issues/77), [#78](https://github.com/aradenac/AI-Compass/issues/78), [#86](https://github.com/aradenac/AI-Compass/issues/86), [#88](https://github.com/aradenac/AI-Compass/issues/88) | Code merged; UX-R01–R03 merged, remaining specification journeys in #123–#126 |
| Partial publication and Run corrections | [Current contract](../publication-and-information-lifecycle.md) | [#84](https://github.com/aradenac/AI-Compass/issues/84), [#85](https://github.com/aradenac/AI-Compass/issues/85) | Code merged |
| Data Governance Audit Explorer | [Current contract](../data-governance-audit-explorer.md) | [#91](https://github.com/aradenac/AI-Compass/issues/91) | Code merged |
| Coordinated releases / shared providers | [Current contract](../shared-frontend-and-release-lifecycle.md) | [#75](https://github.com/aradenac/AI-Compass/issues/75), [#77](https://github.com/aradenac/AI-Compass/issues/77), [#78](https://github.com/aradenac/AI-Compass/issues/78) | Code merged; shell accepted in #115, remaining business presentation parity in #123 |
| Local/LAN security and archive permission foundations | [Operational profiles](../secure-operations-baseline.md) | [#76](https://github.com/aradenac/AI-Compass/issues/76) | Code merged |

These specifications contain the domain rules, acceptance criteria, cross-relationships and UX contracts as maintained product documentation. They are not repeated in `future-evolutions`. Detailed implementation documentation under `docs/` is retained.

## UI delivery status and remaining priority

**Completed and merged:** [#114](https://github.com/aradenac/AI-Compass/issues/114) (browser acceptance foundation), [#115](https://github.com/aradenac/AI-Compass/issues/115) (shared shell, single-view routing and modals), [#116](https://github.com/aradenac/AI-Compass/issues/116) (contextual navigation). Their closed status is *not* certification of all §13 user journeys.

**Remaining UX/UI work, mandatory BEFORE P7:**

| Order / priority | Issue | Scope and verification obligation |
| --- | --- | --- |
| **1 / P0-UX-GAP** | [#123](https://github.com/aradenac/AI-Compass/issues/123) — UX-R04 | Truly shared **business-domain** presentation components across Demo/Server, TD-01, no feature loss |
| **2 / P1-UX-GAP** | [#124](https://github.com/aradenac/AI-Compass/issues/124) — UX-R05 | Draft resume / revision conflict / Run stepper and owner-safe edit behavior, reusing existing helpers |
| **3 / P2-UX-GAP** | [#125](https://github.com/aradenac/AI-Compass/issues/125) — UX-R06 | End-to-end Engineer, Workgroup, Results/Recommendations and Management user journeys |
| **4 / P3-UX-GAP** | [#126](https://github.com/aradenac/AI-Compass/issues/126) — UX-R07 | Desktop Chromium coverage of 20 UX scenarios, visual consistency and accessibility baseline |

All four retain **desktop-web-only** scope. No mobile/tablet requirement; run independent Server and Demo tests. Existing branch rule enforcement is deliberately deferred under [TD-UI-01](../technical-debt.md).

## Still to implement — original P7 scope (deferred until UX-R07 #126)

| Issue | Detailed remaining requirement |
| --- | --- |
| [#92](https://github.com/aradenac/AI-Compass/issues/92) | [Controlled retirement, retention and privileged purge](../future-evolutions/controlled-retirement-and-purge.md) |
| [#93](https://github.com/aradenac/AI-Compass/issues/93) | [Asynchronous secure resumable archive](../future-evolutions/secure-operations-and-capacity.md) |
| [#94](https://github.com/aradenac/AI-Compass/issues/94) | [Capacity limits, health and Internet security](../future-evolutions/secure-operations-and-capacity.md) |
| [#95](https://github.com/aradenac/AI-Compass/issues/95) | [Guided release/staging/recovery CLI](../future-evolutions/guided-release-operations.md) |

Read [the live phased delivery ledger](../future-evolutions/implementation-plan.md) for mandatory dependency order, historical issue completion and QA gates. Read [the original 2026-10-10 approval ledger](../history/feature-approval-ledger-2026-10-10.md) for history.

## Approval and release boundary

The product owner approved the FUT backlog and then the corrective UI reprioritization and remaining gap issue sequencing on 2026-10-11. Closure of a GitHub implementation issue records a merged implementation, not a claim of real visual acceptance or authority to deploy. Separate [release-readiness gates](../release-readiness.md) remain **NO-GO** until independently satisfied.

Do not introduce speculative features, invent external provider data, weaken RBAC, or treat Demo fixtures as real Server records. Feature scope changes outside the explicitly approved **#123–#126** UX gaps and existing P7 issues require separate approval.
