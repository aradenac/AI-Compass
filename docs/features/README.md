# Delivered features and approval ledger

> **Checked 2026-10-11:** original FUT issues #75–#91 are closed with code merged; the remaining original P7 issues #92–#95 are still open. Corrective UI acceptance issues #114–#116 are now first priority. This is a delivery-status register, **not** production release approval.

## Delivered functional and technical specifications

| Domain | Maintained specification | Closed implementation issues | Delivery |
| --- | --- | --- | --- |
| Campaign Evaluation Matrix | [Current contract](../campaign-evaluation-matrix.md) | [#82](https://github.com/aradenac/AI-Compass/issues/82), [#84](https://github.com/aradenac/AI-Compass/issues/84) | Code merged |
| Composable Setup Guides | [Current contract](../composable-setup-guides.md) | [#81](https://github.com/aradenac/AI-Compass/issues/81), [#83](https://github.com/aradenac/AI-Compass/issues/83), [#84](https://github.com/aradenac/AI-Compass/issues/84) | Code merged |
| Enterprise accessibility / pricing | [Current contract](../technology-accessibility-and-pricing.md) | [#79](https://github.com/aradenac/AI-Compass/issues/79), [#83](https://github.com/aradenac/AI-Compass/issues/83), [#87](https://github.com/aradenac/AI-Compass/issues/87), [#90](https://github.com/aradenac/AI-Compass/issues/90) | Code merged |
| OS compatibility / user environment | [Current contract](../os-compatibility-and-user-environment.md) | [#80](https://github.com/aradenac/AI-Compass/issues/80), [#86](https://github.com/aradenac/AI-Compass/issues/86), [#89](https://github.com/aradenac/AI-Compass/issues/89) | Code merged |
| Deployment and adoption planning | [Current contract](../deployment-and-adoption-planning.md) | DAP-01 [#66](https://github.com/aradenac/AI-Compass/issues/66), FUT [#87–#90](https://github.com/aradenac/AI-Compass/issues/87) | Code merged |
| Role-based UX, workgroup/engineer/management entries | [Normative UX requirements](../role-based-user-experience-and-guided-navigation.md) | [#77](https://github.com/aradenac/AI-Compass/issues/77), [#78](https://github.com/aradenac/AI-Compass/issues/78), [#86](https://github.com/aradenac/AI-Compass/issues/86), [#88](https://github.com/aradenac/AI-Compass/issues/88) | Code merged; cross-cutting UX acceptance in #114–#116 |
| Partial publication and Run corrections | [Current contract](../publication-and-information-lifecycle.md) | [#84](https://github.com/aradenac/AI-Compass/issues/84), [#85](https://github.com/aradenac/AI-Compass/issues/85) | Code merged |
| Data Governance Audit Explorer | [Current contract](../data-governance-audit-explorer.md) | [#91](https://github.com/aradenac/AI-Compass/issues/91) | Code merged |
| Coordinated releases / shared providers | [Current contract](../shared-frontend-and-release-lifecycle.md) | [#75](https://github.com/aradenac/AI-Compass/issues/75), [#77](https://github.com/aradenac/AI-Compass/issues/77), [#78](https://github.com/aradenac/AI-Compass/issues/78) | Code merged; presentation acceptance in #114–#116 |
| Local/LAN security and archive permission foundations | [Operational profiles](../secure-operations-baseline.md) | [#76](https://github.com/aradenac/AI-Compass/issues/76) | Code merged |

These specifications contain the domain rules, acceptance criteria, cross-relationships and UX contracts as maintained product documentation. They are not repeated in `future-evolutions`. Detailed implementation documentation under `docs/` is retained.

## Active corrections — priority before new P7 work

| Priority | Issue | Scope |
| --- | --- | --- |
| **P0-UX** | [#114](https://github.com/aradenac/AI-Compass/issues/114) | Playwright, visual reference and fail-closed UI acceptance pipeline |
| **P1-UX** | [#115](https://github.com/aradenac/AI-Compass/issues/115) | Shared shell, single-view routing, role isolation and modals |
| **P2-UX** | [#116](https://github.com/aradenac/AI-Compass/issues/116) | Contextual top-down/bottom-up navigation and complete persona journeys |

## Still to implement — original P7 scope (deferred)

| Issue | Detailed remaining requirement |
| --- | --- |
| [#92](https://github.com/aradenac/AI-Compass/issues/92) | [Controlled retirement, retention and privileged purge](../future-evolutions/controlled-retirement-and-purge.md) |
| [#93](https://github.com/aradenac/AI-Compass/issues/93) | [Asynchronous secure resumable archive](../future-evolutions/secure-operations-and-capacity.md) |
| [#94](https://github.com/aradenac/AI-Compass/issues/94) | [Capacity limits, health and Internet security](../future-evolutions/secure-operations-and-capacity.md) |
| [#95](https://github.com/aradenac/AI-Compass/issues/95) | [Guided release/staging/recovery CLI](../future-evolutions/guided-release-operations.md) |

Read [the live phased delivery ledger](../future-evolutions/implementation-plan.md) for mandatory dependency order, historical issue completion and QA gates. Read [the original 2026-10-10 approval ledger](../history/feature-approval-ledger-2026-10-10.md) for history.

## Approval and release boundary

The product owner approved the FUT backlog and then the corrective UI reprioritization on 2026-10-11. Closure of a GitHub implementation issue records a merged implementation, not a claim of real visual acceptance or authority to deploy. Separate [release-readiness gates](../release-readiness.md) remain **NO-GO** until independently satisfied.

Do not introduce speculative features, invent external provider data, weaken RBAC, or treat Demo fixtures as real Server records. Feature scope changes outside #114–#116 and the existing P7 issues require separate approval.
