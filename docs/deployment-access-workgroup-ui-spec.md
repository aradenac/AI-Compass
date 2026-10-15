# Deployment & Access — approved Workgroup matrix UI

**Approved reference:** [HTML prototype](prototypes/deployment-access/index.html) · [design handoff](prototypes/deployment-access/DESIGN.md).

**Related:** [Deployment & Adoption Planning](deployment-and-adoption-planning.md), [Deployment Targets](deployment-targets.md), [AI Solutions](ai-solutions-workgroup-ui-spec.md).

## Three views

The matrix places qualified individual AI Solutions in columns. Each solution header distinguishes successful benchmark qualification, **global publication**, enterprise accessibility and associated Guides. A published benchmark is not automatically a published solution or a real-life deployment.

1. **By project phase:** group Tasks under phase labels, collapsed by default. Read-only Task × Solution cells summarize applicability, readiness and real-life use.
2. **By professional specialty/domain:** same read-only Task × Solution matrix, grouped by specialty. A Task can belong to several groups; never double-count repeated Task usage.
3. **By person:** group people by professional specialty, permitting an individual to appear in more than one group. Eligible Person × Solution cells are editable, always reflecting a shared underlying person state. Ineligible gray cells cannot be edited.

## User interactions

**Not applicable / ineligible:** disabled, not actionable. Do not offer user licensing or deployment controls here.

**Not globally published:** indicate **To publish**. In the person-oriented view, an authorized operator may publish the solution globally through the canonical AI Solutions approval gate. The publication action is global and must enforce the existing editorial note, Guide readiness and authorization checks for all users. There is no Unpublish control in Deployment; withdrawal remains in AI Solutions.

**Published + eligible individual:** two checks only: (1) **rights and licenses verified** and (2) **installation tested by this person**. Both are required before marking the solution **Available** for that person. Removing a check removes readiness. Do not expose separate Model/Provider/Harness entitlement checkboxes or mandatory evidence-reference entry in the target UI.

**Task-oriented views:** strictly read-only. Real-life usage is a distinct attributable fact from publication or availability. Underlying per-person use records feed this projection; Task cells do not create or edit them. Use during a benchmark may count only where it genuinely represents real production Task use.

## Backend compatibility and constraints

The currently implemented FUT-15 Server deployment API requires non-secret evidence references for verified component access, verified setup and first use, and retains independent component entitlement transitions. The approved two-check UI and no-required-reference entry **do not silently repeal** immutable event attribution, verification requirements or authenticated Server validation. Integration must propose an explicit, reviewed backend/domain accommodation (for example, derived readiness from detailed event state), ensuring real use is not asserted without a valid source. Until then do not fabricate compliant events or bypass the API.

A globally published solution becoming unqualified or losing accessibility must surface review/readiness warnings while retaining source audit/history. Don't confuse role eligibility, published state, enterprise accessibility, person-rights and first-use proof. Access to private employee/deployment data requires explicit permissions. Demo records are fictional and must not sync to Server.

## Acceptance

- Responsive desktop 1366×900 and 1024px.
- Same data across all three groupings; phase/domain Task matrices readonly.
- Gray ineligible cells cannot open forms or grant access.
- Person view allows publish action only for authorized users and uses exactly two availability checks.
- Publish updates global solution state without bypassing editorial publication; no withdrawal action in this screen.
- Repeat-person state consistent across specialty groups, reliable revoked-status propagation, auditable prior revisions.
- Keyboard usability and visual screenshot inspection required.

The HTML is a visual/interaction reference, not the production application.
