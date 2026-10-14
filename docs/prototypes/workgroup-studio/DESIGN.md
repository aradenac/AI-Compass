# Workgroup Studio homepage — implementation handoff

[Specification](../../workgroup-studio-home-ui-spec.md) · [Standalone prototype](index.html) · [Prototype conventions](../README.md)

The standalone `index.html` preserves the user-iterated HTML/CSS/SVG prototype. Open it directly in a desktop browser (no dependencies). It is a **visual design reference**, not production frontend code and not a substitute for the [normative domain UX specification](../../role-based-user-experience-and-guided-navigation.md).

## Agreed prototype scope

- **Content-only view**: five-zone navigable knowledge map. No application header/footer, permanent sidebars, updates panel or attention strip; these are not deleted product features.
- Five functional zones and every domain card from the normative specification, including Theoretical Forecasts.
- A compact top/center/bottom spatial arrangement with reserved relation tracks.
- Shared teal `#0d9488` SVG relationship styling, 2.7px stroke, rounded paths and filled directional markers. Primary relationships are solid; optional Engineer Workspace → Needs & Feedback is dashed and labelled “Retours d’usage et nouveaux besoins”.
- Demonstration dialog and destination strings are **mocked**, not authoritative routes.
- Current page contains some historical CSS/prototype scaffolding for elements removed during visual iterations; do not resurrect these as visible application components.

## Implementation notes

Reuse existing shared shell, role-aware navigation, route/context handling and Server/Demo adapters. Prefer semantic links/buttons and a single relationship-rendering function/component rather than manually drawn triangles. Resolve connector anchors from actual DOM element bounds, and reserve collision-free tracks.

Maintain the Workgroup graph as an **intuition-led navigation surface**, not a sequential workflow. Module connections are semantic annotations; the authoritative backend decides permissions and evidence/publication status.

## Required quality loop

Render in Chromium at 1366×900 and 1024px. **Actually inspect both screenshots**, including arrow shapes and arrowhead visibility; programmatic screenshots alone do not prove quality. Test keyboard/focus and click/Back/Forward routes with authorized and denied identities. Visual approval is by the product owner; current prototype is not yet formally approved for pixel-accurate implementation.

## Known prototype versus production boundaries

Prototype: mocked cards and destination modal, no API and no auth. Production: real section routes, authoritative content and permissions. The diagram's category-level connectors are intentionally a curated subset of the normative domain graph. No new data objects, tickets, synthetic counts, scoring or publication semantics.
