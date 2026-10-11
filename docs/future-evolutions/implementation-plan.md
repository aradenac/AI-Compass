# Future evolutions — delivery ledger and prioritized plan

> **Updated:** 2026-10-11, checked against live GitHub issues #75–#95.
> **Source of truth:** GitHub merge/issue state for delivery; [current product documentation](../product-definition.md) for implemented domain specifications; this plan for priority and dependencies.
> **Original approval/history:** [2026-10-10 complete phase plan](../history/fut-plan-approved-2026-10-10.md). Original requirements are retained, not erased.

## Status and phase vocabulary

- **Code merged**: the implementation PR was merged and its original FUT issue closed; does **not** imply independent UX acceptance, real staging acceptance, user sign-off or production GO.
- **Open — priority**: approved corrective issue that precedes normal functional expansion.
- **Open — deferred**: existing approved issue remains unchanged in scope and resumes after the corrective acceptance gate.
- **Operational release:** still **NO-GO** pending existing independent real staging/browser/recovery/operator decision gates in [Release Readiness](../release-readiness.md).

## Execution order — mandatory

1. **UX-R01 [#114](https://github.com/aradenac/AI-Compass/issues/114) — P0-UX, FIRST:** automated real-browser Playwright acceptance, inspectable captures, agreed visual references, cross-cutting UX invariants and enforceable merge gate.
2. **UX-R02 [#115](https://github.com/aradenac/AI-Compass/issues/115) — P1-UX:** one shared application shell, exactly one selected business view, role-safe routing, uniform styling and accessible form/dialog behavior. Requires #114.
3. **UX-R03 [#116](https://github.com/aradenac/AI-Compass/issues/116) — P2-UX:** complete contextual top-down/bottom-up navigation, meaningful domain details, exact revision links, breadcrumbs, return paths and full persona acceptance. Requires #114 and #115.
4. **Only when #116 is merged and UI acceptance is green:** resume original open P7 issues [#92](https://github.com/aradenac/AI-Compass/issues/92), [#93](https://github.com/aradenac/AI-Compass/issues/93), [#94](https://github.com/aradenac/AI-Compass/issues/94), [#95](https://github.com/aradenac/AI-Compass/issues/95) subject to their original technical dependencies. No new UI feature merges around the gate.
5. Backend-only independent work may proceed if it cannot change UI behavior or bypass release/integrity gates. Code already merged remains in place; no rollback or loss of data is implied.

**Authority boundary:** all previously approved business outcomes and P7 scope are preserved. Priorities change, not the original technical requirements. Distinguish a delivered incremental implementation from successful whole-product visual acceptance.

## Completed code — recorded, not re-planned

| Phase | Issue | Delivered increment | Status |
| --- | --- | --- | --- |
| P0 | [#75](https://github.com/aradenac/AI-Compass/issues/75) | Release identity, artifact manifest, contract and compatibility | **Code merged / issue closed** |
| P0 | [#76](https://github.com/aradenac/AI-Compass/issues/76) | Deployment/profile and protected archive foundations | **Code merged / issue closed** |
| P1 | [#77](https://github.com/aradenac/AI-Compass/issues/77) | Shared Demo/Server bootstrap, Catalog/Task provider/controller | **Code merged / issue closed** |
| P1 | [#78](https://github.com/aradenac/AI-Compass/issues/78) | Workgroup Studio and knowledge projections | **Code merged / issue closed** |
| P2 | [#79](https://github.com/aradenac/AI-Compass/issues/79) | Enterprise access, offers and pricing | **Code merged / issue closed** |
| P2 | [#80](https://github.com/aradenac/AI-Compass/issues/80) | OS compatibility and user environment | **Code merged / issue closed** |
| P2 | [#81](https://github.com/aradenac/AI-Compass/issues/81) | Composable guides and recipes | **Code merged / issue closed** |
| P3 | [#82](https://github.com/aradenac/AI-Compass/issues/82) | Campaign evaluation matrix | **Code merged / issue closed** |
| P3 | [#83](https://github.com/aradenac/AI-Compass/issues/83) | Tariff-driven session/Run capture | **Code merged / issue closed** |
| P4 | [#84](https://github.com/aradenac/AI-Compass/issues/84) | Partial publication and eligibility | **Code merged / issue closed** |
| P4 | [#85](https://github.com/aradenac/AI-Compass/issues/85) | Run correction, withdrawal and effective evidence | **Code merged / issue closed** |
| P4 | [#86](https://github.com/aradenac/AI-Compass/issues/86) | Engineer My AI Workspace | **Code merged / issue closed** |
| P5 | [#87](https://github.com/aradenac/AI-Compass/issues/87) | Economic projection foundations | **Code merged / issue closed** |
| P5 | [#88](https://github.com/aradenac/AI-Compass/issues/88) | Task × configuration opportunity heatmap | **Code merged / issue closed** |
| P6 | [#89](https://github.com/aradenac/AI-Compass/issues/89) | Deployment targets and access/adoption tracking | **Code merged / issue closed** |
| P6 | [#90](https://github.com/aradenac/AI-Compass/issues/90) | Resource and rollout budgets | **Code merged / issue closed** |
| P7 | [#91](https://github.com/aradenac/AI-Compass/issues/91) | Maintenance Data Governance Audit Explorer | **Code merged / issue closed** |

Completed domain specifications have been promoted into maintained documentation (see [Current product specifications](#current-product-specifications)). The feature catalogue in [features/README.md](../features/README.md) tracks their delivery states. UX-R02/03 correct acceptance gaps of P1/P4/P5 work, **not** new FUT business scope.

## Current prioritized remediation

| Priority | Issue | Observable acceptance | Dependency |
| --- | --- | --- | --- |
| 1 — blocking | [#114](https://github.com/aradenac/AI-Compass/issues/114) | Chromium Demo/Server role fixtures, screenshot/trace review, CI FAIL on deliberately stacked workspaces, wrong modal behavior and broken navigation; branch protection verified or reported as blocker | None |
| 2 — blocking | [#115](https://github.com/aradenac/AI-Compass/issues/115) | One shell + single active view for multi-role users, modal parity, responsive common design; green browser journeys | #114 |
| 3 — blocking | [#116](https://github.com/aradenac/AI-Compass/issues/116) | Workgroup → Campaign → Run → Evidence and return; Task ↔ Solution → Guide/Feedback; Management → calculation sources; pinned revisions, role/permission parity | #114, #115 |

**Definition of Done for each corrective issue:** relevant source specs plus automated positive/negative/regr. tests, actual browser execution, human/agent-inspectable screenshots, visual-design and behavior checks, no regressions to immutable data, permission isolation, CSRF, Server outage/no Demo fallback and a report separating tested/untested requirements. No self-declared success from HTML/string assertions alone.

## Deferred outstanding original FUT scope (P7)

| Resume order | Issue | Undelivered scope | Specific remaining specification / dependencies |
| --- | --- | --- | --- |
| After UX gate | [#92](https://github.com/aradenac/AI-Compass/issues/92) — FUT-18 | Logical retirement, protected reference/orphan inventory, dry-run, privileged race-safe garbage collection and policy | [Controlled retirement & purge](controlled-retirement-and-purge.md); #76, #85, #91, #116 |
| After UX gate | [#93](https://github.com/aradenac/AI-Compass/issues/93) — FUT-19 | Secure asynchronous immutable native/full archive jobs; scoped token; resumable HTTP and integrity | [Remote archive / operations](secure-operations-and-capacity.md); #75, #76, #116 |
| After #93 | [#94](https://github.com/aradenac/AI-Compass/issues/94) — FUT-20 | Bounded resource policy, health/dashboard, safe Internet ingress and security profile | [Capacity / Internet](secure-operations-and-capacity.md); #76, #91, #93, #116 |
| After #93 | [#95](https://github.com/aradenac/AI-Compass/issues/95) — FUT-21 | Guided compatibility/staging/deploy/upgrade/recovery CLI with operational approvals | [Guided release operations](guided-release-operations.md); #75, #76, #93, #116 |

Issues #92 and #93 may execute independently once #116 closes; #94/#95 must preserve their individual P7 prerequisites. A production release still needs human operational gates beyond any issue merge.

## Current product specifications

The following are normative, maintained documentation of the domain contracts implemented by the closed FUT issues. This is **not** a second issue backlog:

- [Campaign evaluation matrix](../campaign-evaluation-matrix.md)
- [Composable setup guides](../composable-setup-guides.md)
- [Enterprise accessibility and pricing](../technology-accessibility-and-pricing.md)
- [OS compatibility and user environment](../os-compatibility-and-user-environment.md)
- [Deployment/adoption planning and budgets](../deployment-and-adoption-planning.md)
- [Role-based experience, navigation and UX acceptance](../role-based-user-experience-and-guided-navigation.md) — normative UX reference for #114–#116
- [Publication, Run correction and effective evidence](../publication-and-information-lifecycle.md)
- [Data Governance Audit Explorer](../data-governance-audit-explorer.md)
- [Shared frontend, API and coordinated release contracts](../shared-frontend-and-release-lifecycle.md)
- [Development/LAN security baseline](../secure-operations-baseline.md)
- [Nonfunctional interactions](../non-functional-requirements.md)
- [Release readiness / real operational approval](../release-readiness.md)

Detailed delivery/implementation guides under `docs/` (e.g. `campaign-evaluation-matrix-server.md`, `workgroup-studio.md`, `governance-audit-explorer.md`) complement these normative references.

## Boundaries and safe execution

- The implementation ledger and current documentation must not assert that a closed issue has passed an acceptance test that was never run.
- The deployed business database is initially empty; synthetic Demo records remain permanently independent.
- Stable friendly IDs, immutable source/evidence/revision history, exact publication membership, permitted corrections, RBAC, staging recovery protections and data preservation are unconditional.
- P7 changes must not undermine release compatibility, confidential archive controls, special maintenance permissions or human go/no-go.
- A feature may be functionally complete without operational production approval; the real-browser UX gate addresses presentation quality, not production deployment approval.

## Historical references

- [Original 21-issue plan, full phased contracts and cross-feature mapping](../history/fut-plan-approved-2026-10-10.md)
- [PLAT implementation history](../platform-implementation-roadmap.md)
- [Technical-debt registry](../technical-debt.md)

Further new business features are not authorized by this reordering. New work here consists only of the explicitly requested quality and UI remediation issues #114–#116.
