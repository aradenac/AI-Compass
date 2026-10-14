# UI design prototypes — repository convention

This directory contains **reviewable, standalone HTML design references** for AI-Compass views. A prototype is a visual/interaction specification for implementation agents, **not** production code and **not** authoritative business logic.

## Convention for every future view prototype

```text
docs/
  prototypes/
    README.md
    <view-slug>/
      index.html          # self-contained, runnable HTML/CSS/JS prototype
      DESIGN.md           # rationale, UI contract, interaction details, limitations
      ...                 # optional small local test data or approved reference assets
```

1. Write or update an authoritative, view-specific specification under `docs/`; link that specification **both ways** to `docs/prototypes/<view-slug>/index.html` and `DESIGN.md`.
2. Keep `index.html` **readable by text-only coding agents**: semantic markup, textual module names, CSS tokens, real SVG paths and documented interaction states. Do not use a screenshot as the page background or rely on remote dependencies.
3. The prototype shows **only the view's useful content**. The AI-Compass shell/header/account selector/footer are outside the per-view prototype unless a view explicitly owns them.
4. Preserve authoritative domain models, roles, permissions, publication, immutability, revisions, routes and Demo/Server boundaries from the project's normative documents. Mock counts, links and dialogs must say they are mock.
5. Make semantic links and their direction comprehensible without color alone. Distinguish explanatory graph edges from mandatory business transitions. Add real navigation/keyboard/focus semantics during application integration.
6. Design for desktop web, reference 1366 × 900, supported from 1024px. Document deliberate compromises; do not claim mobile acceptance.
7. **Review screenshots visually** at both supported widths before approving a prototype and again after implementation. A passing Chromium journey or a generated PNG is not visual approval.
8. Keep changes reviewable: separate design-reference changes from functional implementation. A prototype is an approved visual target **only after product-owner approval**, never automatically by committing it.

## Index

| View | Specification | Prototype | Status |
| --- | --- | --- | --- |
| Needs & Feedback Workgroup view | [UI specification](../needs-feedback-workgroup-ui-spec.md) | [HTML](needs-feedback/index.html) · [Design handoff](needs-feedback/DESIGN.md) | Visual layout approved; new metadata model pending implementation |
| Task Explorer Workgroup taxonomy | [UI specification](../task-explorer-workgroup-ui-spec.md) | [HTML](task-explorer/index.html) · [Design handoff](task-explorer/DESIGN.md) | Design candidate; schema/permissions implementation pending |
| Test Design Workgroup view | [UI specification](../test-design-workgroup-ui-spec.md) | [HTML](test-design/index.html) · [Design handoff](test-design/DESIGN.md) | Approved simplified prototype; production integration pending |
| Workgroup Studio landing knowledge map | [Workgroup landing UI contract](../workgroup-studio-home-ui-spec.md) | [HTML](workgroup-studio/index.html) · [Design handoff](workgroup-studio/DESIGN.md) | Candidate reference; pending owner visual approval |

Future views should receive their own directory and index entry; do not overwrite another view's prototype.
