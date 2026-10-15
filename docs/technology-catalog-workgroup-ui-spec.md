# Technology Catalog — Workgroup UI specification

**Approved reference:** [interactive HTML](prototypes/technology-catalog/index.html) · [design handoff](prototypes/technology-catalog/DESIGN.md).

## Purpose and layout

Workgroup-maintained **independent** Model, Provider, Harness and Framework technology component records. The catalog covers both accessible and candidate technologies, including restricted, inaccessible or unknown enterprise availability. AI Solutions assembled from components, experimental Runs, rankings and suitability belong to other modules.

A desktop two-column view displays a searchable/filterable component inventory and a selected component editor/detail. Search by name and capabilities; filter by component type and enterprise-wide accessibility. **No maturity filter, field or evaluation proxy:** observed capabilities and benchmark outcomes are evaluated elsewhere.

## Component detail

All component types retain name, description, capabilities, limitations, pertinent type-specific properties, and **enterprise-wide accessibility** (accessible, restricted, not accessible, unknown). Editing/creation must preserve unknown extensible properties and append immutable revisions without rewriting original data.

**Models:** do not display an **Access & Pricing** tab or supplier tariff entry. Model pricing is represented in applicable billable Provider offers for the relevant model/configuration; avoid duplicate invoicing. Model does not require an installation guide.

**Providers, Harnesses and Frameworks:** show **Access & Pricing** with versioned commercial offers and their applicability, independently of accessibility; separate fixed from metered variable amounts, alternatives from cumulative charges, and retain original source/effective dates. This view is a management surface; exact applicable offers must still be selected for Runs per the pricing specification.

**Guides & links:** retrieve existing applicable Guides & Charter documents from the real document catalog. Workgroup can attach multiple references to the component, unlink references without deleting source content, and navigate to create a new guide then associate it. Providers, Harnesses and Frameworks are expected to have an installation/Setup Guide when installation/setup is relevant; absence must be visible, not silently counted as fulfilled. Models have no generic mandatory installation-guide requirement. AI Solution-specific assembly and compatibility guides may be linked separately in AI Solutions & Recommendations; do not clone documents into components.

## UI boundaries and history

The component detail need not expose a standalone **History** tab; immutable CatalogRevision records, original schemas, audit trail, compatibility controls and guarded writes **remain mandatory in backend** and can remain accessible through audit/maintenance tooling. Remove only the UI tab, not historical data or compliance diagnostics. The view must reject unsafe incompatible schema writes rather than pretending revisions can be mutated.

## Implementation notes / acceptance

- Demo HTML is self-contained with fictional in-memory records, not a production API implementation.
- Real CRUD must use current catalog endpoints and contributor permissions/CSRF, with optimistic revision checks and access-safe historical guarantees.
- Price/offer editing is an eventual integration: current Server catalog fields do not yet implement the full multi-offer pricing contract described in [Technology Accessibility & Pricing](technology-accessibility-and-pricing.md).
- Real guide search, creation and linkage require integrating Guides & Charter. Don't fabricate link success on the Server UI.
- Confirm independent type filters, free-text search, accessibility, model-specific tab absence, component edit/create and associated-guide linking interactions. Visually inspect desktop screenshots at 1366×900 and 1024px.

**Related:** [Technology Catalog Server](technology-catalog-server.md) · [Model Catalog Architecture](model-catalog-architecture.md) · [Technology Accessibility & Pricing](technology-accessibility-and-pricing.md) · [AI Solutions Workgroup UI](ai-solutions-workgroup-ui-spec.md).
