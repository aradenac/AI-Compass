# Future evolutions — delivery ledger and prioritized plan

> **Updated:** 2026-10-13, reconciled with merged UX #114–#116 and #123–#125 (PRs #129–#132, #134), the re-grounded UX gate #126 (PR #133, review pending) and still-open FUT #92–#95.
> **Source of truth:** GitHub merge/issue state for delivery; [current product documentation](../product-definition.md) for implemented domain specifications; this plan for priority and dependencies.
> **Original approval/history:** [2026-10-10 complete phase plan](../history/fut-plan-approved-2026-10-10.md). Original requirements are retained, not erased.

## Phased outcome map

| Phase | Actual completion checkpoint | Current disposition |
| --- | --- | --- |
| P0 — Release and secure delivery foundations | #75–#76 merged | **Completed code** |
| P1 — Shared frontend and persona entry | #77–#78 merged | **Completed code; UX acceptance recovery prioritized** |
| P2 — Pricing, environment and setup contracts | #79–#81 merged | **Completed code** |
| P3 — Campaign evaluations and tariff-driven Runs | #82–#83 merged | **Completed code** |
| P4 — Publication and Engineer usage | #84–#86 merged | **Completed code; UX acceptance recovery prioritized** |
| P5 — Opportunity modelling and Management | #87–#88 merged | **Completed code; UX acceptance recovery prioritized** |
| P6 — Deployment and resources | #89–#90 merged | **Completed code** |
| P7 — Audit, purge, archives, security/capacity and release CLI | #91 merged; #92–#95 open | **Partially delivered; remaining P7 deferred behind UX** |
| UX-R01 → UX-R03 — initial recovery | #114–#116 merged/closed | **Completed code, selected Chromium journeys passed** |
| UX-R04 → UX-R07 — remaining UX specification coverage | #123/#124 merged/closed; #125/#126 open | **Top priority before remaining P7** |

## Status and phase vocabulary

- **Code merged**: the implementation PR was merged and its original FUT issue closed; does **not** imply independent UX acceptance, real staging acceptance, user sign-off or production GO.
- **Open — priority**: approved UX-R06–R07 corrective work (#125 in review, #126 the final gate) that precedes all FUT P7 expansion.
- **Open — deferred**: existing FUT P7 issues #92–#95 retain original scope and technical dependencies but resume only after UX-R07 acceptance.
- **Operational release:** still **NO-GO** pending existing independent real staging/browser/recovery/operator decision gates in [Release Readiness](../release-readiness.md).

## Execution order — mandatory

1. **[#114](https://github.com/aradenac/AI-Compass/issues/114) / [#115](https://github.com/aradenac/AI-Compass/issues/115) / [#116](https://github.com/aradenac/AI-Compass/issues/116) — COMPLETED:** Chromium real-browser infrastructure, shared shell/single active view/protected modals, contextual navigation. Merged in PRs #118/#120/#121. Their closure does not independently prove all 20 §13 UX scenarios, durable drafts, complete role journeys or a truly shared business presentation layer.
2. **[#123](https://github.com/aradenac/AI-Compass/issues/123) — UX-R04, P0-UX-GAP, MERGED/CLOSED:** one *business* presentation implementation using Demo/Server adapters; TD-01 resolved. No duplicate view/DOM layers. Merged on `main` (PRs #129–#131).
3. **[#124](https://github.com/aradenac/AI-Compass/issues/124) — UX-R05, P1-UX-GAP, MERGED/CLOSED:** complete form/Run stepper draft resume, role/mode isolation, revision conflicts and authoritative session ownership. Merged on `main` (PR #132); extended the existing draft system.
4. **[#125](https://github.com/aradenac/AI-Compass/issues/125) — UX-R06, P2-UX-GAP, MERGED/CLOSED:** complete Engineer/Workgroup/Results/Management and knowledge journeys, including published-only updates, accurate counters, source/role-sensitive detail. Merged on `main`; per-scenario status, remaining blockers and the explicit DAP access-request spec dependency are recorded in [UX-R06 persona coverage](../ux-r06-persona-coverage.md). The one gap it left is the structured DAP access-request object (owner/product decision), tracked as BLOCKED in the #126 matrix.
5. **[#126](https://github.com/aradenac/AI-Compass/issues/126) — UX-R07, P3-UX-GAP, FINAL UX GATE:** traceable automated and reviewed **desktop** acceptance across the 20 normative UX scenarios, targeted accessibility and approved visual references. Fix demonstrable UX defects; keep the platform security/data/recovery tests. Requires #123–#125.
   **Gate implemented, run on the merged #123–#125 base (PR pending review):** [`scripts/ux_qa.py`](../../scripts/ux_qa.py) runs the `ui-qa` job with a split journey package, a machine-readable coverage registry and the [Desktop UX acceptance matrix](../../docs/ux-acceptance-matrix.md). The executed run on a fresh disposable stack reports **24/24 checks PASS and 19 VERIFIED / 3 PARTIAL / 2 BLOCKED** requirements with no UNMAPPED. **#126 stays open** for review; the remaining BLOCKED/PARTIAL scenarios are 5, 6, 11, 16 and 17, each with a named reason (owner/product decision or a gap asserted elsewhere).
6. **Only after #126 is closed with real-browser acceptance passing:** resume the already approved P7 work [#92](https://github.com/aradenac/AI-Compass/issues/92) and [#93](https://github.com/aradenac/AI-Compass/issues/93), then [#94](https://github.com/aradenac/AI-Compass/issues/94) and [#95](https://github.com/aradenac/AI-Compass/issues/95) in their existing dependency order. Do not interpret this scheduling change as a new business feature.
7. Backend work provably independent of UI may proceed only without circumventing security/recovery or UX acceptance. Operational production release remains separately **NO-GO** until real staging and an authorized decision.

**Device scope:** Desktop web **only** (reference Chromium 1366×900, standard desktop 1024px+). Mobile/tablet and touch-specific UX/test requirements were explicitly removed by product-owner decision; do not add mobile breakpoints back to CI.

**CI governance:** the `ui-qa` workflow runs and is checked; making its status **mandatory in GitHub branch rules** remains deliberately deferred as [TD-UI-01](../technical-debt.md). That policy deferral does not relax agent-executed browser or backend tests.

**Authority boundary:** The originally approved domain/operational outcomes and P7 scope are preserved. Closed coding issues must not be described as human production acceptance or as proof of untested journeys.


## Completed code — recorded, not re-planned

## Approved GitHub implementation backlog — maximal coherent issue slices

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

**UX-R01–R03 code closure:** #114–#116 implemented and merged (PR #118, #120, #121), supported by scoped desktop Chromium checks; other applicable journeys remain scheduled as #123–#126.

Completed domain specifications have been promoted into maintained documentation (see [Current product specifications](#current-product-specifications)). The feature catalogue in [features/README.md](../features/README.md) tracks their delivery states. UX-R02/03 correct acceptance gaps of P1/P4/P5 work, **not** new FUT business scope.

## Current prioritized remediation — desktop UX gap closure

| Priority | Issue | Missing/partial specification coverage to close | Required predecessor |
| --- | --- | --- | --- |
| **1 — P0-UX-GAP** | [#123](https://github.com/aradenac/AI-Compass/issues/123) — UX-R04 | Common business-level renderers/controllers, actual Demo/Server UX equivalence; TD-01 | #114–#116 closed; **merged/closed on `main`** |
| **2 — P1-UX-GAP** | [#124](https://github.com/aradenac/AI-Compass/issues/124) — UX-R05 | Existing draft helper coverage: Campaign, Run/session steppers, resume/discard, base-revision 409 conflict & ownership safety. **Merged on `main` ([PR #132](https://github.com/aradenac/AI-Compass/pull/132)); issue closed.** Behaviour: [draft, conflict and Run-stepper contract](../draft-conflict-and-run-stepper.md). | #123 |
| **3 — P2-UX-GAP** | [#125](https://github.com/aradenac/AI-Compass/issues/125) — UX-R06 | Complete §13 role journeys: Engineer profiles/access/feedback; Workgroup five-zone diagram, publication-only updates and valid counts; Results/Recommendations; Management provenance; cross-role boundaries. **Merged/closed on `main`.** | #123, #124 |
| **4 — P3-UX-GAP** | [#126](https://github.com/aradenac/AI-Compass/issues/126) — UX-R07 | Executable 20-scenario evidence matrix, desktop visual/accessibility baseline and regression gate including negative fixtures — **gate and matrix implemented and run on the merged #123–#125 base: 24/24 checks, 19 VERIFIED / 3 PARTIAL / 2 BLOCKED**; the remaining PARTIAL/BLOCKED scenarios are 5, 6, 11, 16 and 17 | #123–#125 |

**Previously completed recovery:** [#114](https://github.com/aradenac/AI-Compass/issues/114) (Playwright foundation), [#115](https://github.com/aradenac/AI-Compass/issues/115) (shell/modals/one active view), [#116](https://github.com/aradenac/AI-Compass/issues/116) (context links) merged and closed. Their prior acceptance evidence remains valid for what was actually tested.

**Definition of Done — every UX gap issue:** preserve normative domain specification, positive/negative and regression tests, real disposable authenticated Server *and* isolated Demo, user-visible Chromium desktop captures/traces inspected by the implementing agent, transparent untested/blocked cases, no regression in CSRF/permissions, version pinning, publication, original evidence or recovery. No green certification from unexecuted routes, source-string assertions or unreviewed screenshots. Preserve faster CI and the NO-GO production decision.


## Deferred outstanding original FUT scope (P7)

| Resume order | Issue | Undelivered scope | Specific remaining specification / dependencies |
| --- | --- | --- | --- |
| After #126 | [#92](https://github.com/aradenac/AI-Compass/issues/92) — FUT-18 | Logical retirement, protected reference/orphan inventory, dry-run, privileged race-safe garbage collection and policy | [Controlled retirement & purge](controlled-retirement-and-purge.md); #76, #85, #91, #116, #126 |
| After #126 | [#93](https://github.com/aradenac/AI-Compass/issues/93) — FUT-19 | Secure asynchronous immutable native/full archive jobs; scoped token; resumable HTTP and integrity | [Remote archive / operations](secure-operations-and-capacity.md); #75, #76, #116, #126 |
| After #93 | [#94](https://github.com/aradenac/AI-Compass/issues/94) — FUT-20 | Bounded resource policy, health/dashboard, safe Internet ingress and security profile | [Capacity / Internet](secure-operations-and-capacity.md); #76, #91, #93, #116, #126 |
| After #93 | [#95](https://github.com/aradenac/AI-Compass/issues/95) — FUT-21 | Guided compatibility/staging/deploy/upgrade/recovery CLI with operational approvals | [Guided release operations](guided-release-operations.md); #75, #76, #93, #116, #126 |

Issues #92 and #93 may execute independently **only after #126 is accepted**; #94/#95 must preserve their individual P7 prerequisites. The original completed prerequisite #116 remains valid. A production release still needs human operational gates beyond any issue merge.

## Current product specifications

The following are normative, maintained documentation of the domain contracts implemented by the closed FUT issues. This is **not** a second issue backlog:

- [Campaign evaluation matrix](../campaign-evaluation-matrix.md)
- [Composable setup guides](../composable-setup-guides.md)
- [Enterprise accessibility and pricing](../technology-accessibility-and-pricing.md)
- [OS compatibility and user environment](../os-compatibility-and-user-environment.md)
- [Deployment/adoption planning and budgets](../deployment-and-adoption-planning.md)
- [Role-based experience, navigation and UX acceptance](../role-based-user-experience-and-guided-navigation.md) — normative UX reference for completed #114–#116 and upcoming #123–#126
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

Further new business features are not authorized by this reordering. The new issues #123–#126 close the *existing* normative desktop UI/UX gaps before FUT #92–#95.
