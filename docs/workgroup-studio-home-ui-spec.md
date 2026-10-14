# Workgroup Studio — homepage graphical UI contract

**Status:** proposed view-design specification, pending owner visual approval and integration planning.  
**Normative functional requirements:** [Role-based user experience §6](role-based-user-experience-and-guided-navigation.md), [Workgroup Studio](workgroup-studio.md), [UX acceptance contract](ux-acceptance-contract.md). Functional and security constraints in those documents take precedence over illustrative content in the prototype.

**Executable visual reference:** [HTML prototype](prototypes/workgroup-studio/index.html) · [Prototype technical handoff](prototypes/workgroup-studio/DESIGN.md).  
**Repository-wide convention for subsequent views:** [UI prototypes README](prototypes/README.md).

## Goal and scope

The Workgroup's homepage is **a direct, intuitive knowledge map**, not an app menu, personal ticket queue, dashboard of fabricated KPIs, or compulsory wizard. Users understand how domains relate and click directly into the appropriate existing workspace.

This prototype specifies **only the useful view content**. Do not render application header, footer, left/right sidebar, duplicated navigation menus, public Updates list, or Attention panel inside the view component. The shared application shell and optional separate published Updates experience remain independently specified. Removing those areas from this design **does not remove their backend capabilities or authorized destination routes**.

## Spatial hierarchy and modules

Five visibly distinct zones. The main engineering cores — **Technology Catalog, Tasks, Test Design, Benchmark Workspace and Results Explorer** — receive slightly stronger emphasis without hiding any other destination:

| Zone | Modules | Purpose |
| --- | --- | --- |
| 1 · Sources & Référentiels | Needs & Feedback; Technology Watch; Technology Catalog | Discover user needs, watch signals and component inventory |
| 2 · Formalisation & Études | Tasks; Test Design; Theoretical Forecasts | Structure use cases, reusable challenges and explicitly theoretical projections |
| 3 · Expérimentation & Analyse | Benchmark Workspace; Results Explorer | Execute controlled campaigns/Runs; inspect measured evidence |
| 4 · Capitalisation & Décision | AI Solutions & Recommendations; Guides & Charter; Profitability & Opportunities | Qualify and disseminate evidence, methods and opportunities |
| 5 · Mise à disposition | Deployment & Resources; Engineer Workspace | Enable authorized deployment and actual use |

Place zones 1 and 2 across the top, zone 3 centrally, zones 4 and 5 across the bottom. Use reserved lanes between zones for the relationship graph. Avoid connectors crossing module cards. At 1024px cards, text and labels must remain legible without horizontal overflow.

## Relations and arrows

Use **one SVG visual language** for all relationships: turquoise `#0d9488`, 2.7px rounded paths, smooth corners, filled triangular destination arrowheads and legible labels. Position paths in reserved gutters and preserve direction through resizes. Use continuous lines for core explanatory relations; dashed `8 6` only for optional/feedback relationships.

The current prototype abstracts these category-level exchanges:

| Relationship label | Intended reading |
| --- | --- |
| Besoins → Tasks | Identified needs can inform formal Task definition |
| Tests & candidats | Test Design and eligible Catalog components inform evaluations |
| Veille & composants | Watch and Catalog can inform proposed experimentation |
| Preuves mesurées | Executed controlled Runs supply Results and subsequent capitalisation |
| Candidats à déployer | Qualified opportunities can inform deployment decisions |
| Guides & recommandations | Capitalised knowledge helps engineers use solutions |
| Retours d’usage et nouveaux besoins | **Engineer Workspace → Needs & Feedback**, optional field feedback |

The last edge must be a **real SVG connector with a visible directional arrowhead**, not a substitute link or footer, and it should start/end at the appropriate module anchors rather than implying a mandatory whole-zone transition. Explanatory connections do **not** create records or impose prerequisites. The full, detailed semantic graph in the normative §6.2 remains authoritative: this landing view intentionally visualizes only a legible subset.

## Interactions

- Every module card is keyboard-focusable, has a descriptive accessible name and routes directly to its existing authorized Workgroup workspace; preserve origin/context, object ID and browser history.
- Prototype card clicks show a **mock destination dialog**, not live application navigation. Implementation replaces this with existing shared routing and real permission checks.
- Hover/focus clarifies the destination; related-edge emphasis may highlight source/destination cards, but cannot be the sole navigation path.
- Never treat an explanatory relationship as a workflow gate or create a personal ticket/status transition.
- Provide restricted/unavailable states without disclosing private objects. No Demo-to-Server fallback, no client-side role escalation, no duplicate business data.
- The prototype's mock counts, sample messages and illustrative routing strings are **not product data or final URL contracts**.

## Design parameters

Desktop-only: test at 1366 × 900 and minimum 1024px width. Prefer CSS grid for layout, semantic buttons/links, a single SVG connector component/system, a neutral `#f5f8fd` page surface and restrained blue/green/orange/violet/teal zone washes. Maintain visible focus, sensible contrast, and readable typography.

The page should use the available width to communicate the domains and their relations; avoid reintroducing a bulky header, footer, side panels, duplicated quick links or unrelated KPI cards.

## Acceptance and delivery

1. Verify all five zones and thirteen specified module destinations against real navigation in Demo and Server.
2. Verify arrows are visible, homogeneously styled, oriented correctly and do not cover cards at 1366px **and** 1024px.
3. Verify `Engineer Workspace → Needs & Feedback` is a dashed, directed explanatory connection with clear textual meaning.
4. Check keyboard traversal, accessible labels/focus, navigation and return context.
5. Verify permission filtering, authorized routes and unpublished data isolation through real backend/API checks.
6. Capture screenshots at both desktop widths and **open/inspect them visually**; fix overlaps, cropped arrowheads, clipped labels and inconsistent visual hierarchy.
7. Treat prototype visual sign-off and implemented UI acceptance as separate gates; do not claim either merely because Playwright passed.
8. Do not close related product/UX work until the implemented view matches this **approved** specification, without regressing the normative functional behavior.

## Prototype interpretation and future evolution

`docs/prototypes/workgroup-studio/index.html` is an intentionally isolated, editable design candidate. `DESIGN.md` explains its architecture and known limitations. Neither is loaded by production. The published-only Updates feed and resolvable counters are retained elsewhere in the product specification, but excluded from this **content-only** view prototype by explicit design decision.

For each future view: add a corresponding `docs/prototypes/<view-slug>/` prototype and a view specification, then cross-reference them and update `docs/prototypes/README.md` rather than scattering prototypes through the repository root.
