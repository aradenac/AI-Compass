# Results Explorer — Workgroup read-only view specification

**Approved UX direction:** a purely read-only results explorer, with no authored Evaluations UI.  
**Prototype:** [standalone HTML](prototypes/results-explorer/index.html) · [handoff](prototypes/results-explorer/DESIGN.md) · [prototype conventions](prototypes/README.md).

**Sources:** [Results Explorer and Evaluations Server](results-explorer-evaluations-server.md), [Individual Runs](individual-benchmark-runs-server.md), [Composite Runs](composite-benchmark-runs-server.md), [Benchmark Workspace](benchmark-workspace-workgroup-ui-spec.md), and [Recommendations](recommendations-server.md).

## Scope

This view is for inspecting original immutable results and source provenance, **never entering, editing or interpreting evidence by writing a new Evaluation**. The existing backend Evaluation model/API and immutable historical records remain intact; their authoring UI is excluded from this target view, not silently deleted from persisted data.

Present a searchable, filterable central result table with two read-only orientations: **By Task** and **By solution / Framework**. An associated read-only detail pane reveals original Run identity, Task/Test Case/campaign, exact method/configuration and source evidence links, including measured quality, DoD acceptance/failure, cost, human/agent duration, unknown fields and methodological limitations. Preserve navigation back to original campaigns and runs where authorized.

Three distinct evidence classes must not be conflated:
1. **Individual measured Run:** exact measured AI Solution and original metrics.
2. **Composite Framework Run:** overall workflow evidence only, never apportioned to participant solutions.
3. **Theoretical Forecast:** explicitly marked THEORETICAL, with projected values/uncertainty; not a measured run.

Unknown/unrecorded measurements remain **unknown**, not zero. Never infer statistical comparability or rankings where the original experimental methods or selected measurements differ.

## Handoff to AI Solutions (separate responsibility)

Results Explorer does not contain a review/publish form. An **automated, evidence-based candidate projection** should surface individual measured AI Solutions in AI Solutions only when qualifying evidence is **published, DoD-accepted and meets explicitly defined qualification criteria**. Merely having a published Campaign does not guarantee every solution passes qualification. Composite Framework results and theoretical Forecasts must not be converted into qualifying individual Solution evidence.

**AI Solutions** owns:
- Examination of eligible candidates and their measurement provenance;
- Editorial assessment/notes and additional qualification by Workgroup;
- Verification that relevant User/Setup Guides and other required documents exist and are applicable to the exact configuration;
- Explicit decision to publish/unpublish or expose/hide the solution to engineers according to real authorization and publication rules.

Qualification thresholds/scoring policy, eligibility freshness, revocation/reassessment when source evidence is unpublished, and the relationship between qualification and editorial publication are **open domain-policy and backend design requirements**. Do not invent thresholds or silently auto-publish engineer-facing solutions.

## Deliberately excluded UI
- “Saved Evaluations”, “New Evaluation”, user-authored Evaluation revisions or assessment forms.
- Create/edit/save controls anywhere in Results Explorer.
- Auto-publishing candidates directly from the results table.
- Conflating composite Framework/Forecast evidence with individual measured Solution qualification.

## Acceptance
- Desktop web 1366×900 and minimum width 1024px; capture **and visually inspect** both.
- Verify independent search/filter views, authorized evidence drill-down and stable back navigation.
- Verify read-only role/API behavior and restricted-source visibility.
- Prove missing metrics, method differences and theoretical/composite distinctions remain explicit.
- Confirm AI Solutions candidate projection uses authoritative published, accepted measured evidence and qualified criteria, followed by separate Workgroup editorial/publication approval.
- Preserve all prior immutable Evaluation history/API and Server/Demo separation.

The HTML contains fictional content and is not the production frontend or evidence qualification engine.
