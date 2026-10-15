# Guides & Charter — approved Workgroup UI

**Approved reference:** [HTML prototype](prototypes/guides-charter/index.html) · [design handoff](prototypes/guides-charter/DESIGN.md).

## View and interactions

The Workgroup Guides & Charter screen is a **simple shared document library**, not a guide-composition workflow. It shows searchable documents, filterable by document type and publication status, plus a focused document editor and preview. Supported document types include ordinary user guides, setup guides, reusable knowledge entries and general charters where applicable. A document may use text, an external HTTP(S) link, or both.

The document editor has **no visible revision identifier**, no Submit for Review action, no Composition & Applicability tab/editor, and no publication-readiness/quality verification panel. A member with the proper business-write/publication authorization can directly **Publish**, **Unpublish** and **Delete** from this view. Deletion has an explicit confirmation; canceled deletion changes nothing. Publication is global for authorized readers, and unpublication removes the document from its public/current discoverability without erasing historical benchmark sources.

Keep the interface minimal: no unrelated operational statistics, no large checklist, no duplicate standalone setup configurator. Contextual links from AI Solutions, Technology Catalog and Benchmark Workspace can still resolve the appropriate published document.

## Data and history constraints

Simplified UX does **not** imply that immutable historical guide revisions, exact pins on campaigns/runs, audit events or concurrency protection cease to exist. Preserve original source records and references even when revision IDs are hidden from this view. User-facing publication must respect existing access permissions and publication visibility; no review approval requirement is introduced here.

**Delete** is an approved UI action, but the current Setup Guides Server API has no DELETE endpoint and the source-of-truth uses immutable revisioned guides. Before implementing deletion, explicitly define backend authorization, referential integrity and safe erasure semantics: ideally allow deletion only for unreferenced current documents and handle referenced records via archival/withdrawal or another reviewed governed lifecycle that preserves pinned history. Never make a referenced historical document disappear silently, cascade-delete its evidence, or pretend local Demo deletion implements Server removal. Visible confirmation is necessary but not a sufficient historical safety policy.

Existing composable guide/recipe capabilities documented in [Composable Setup Guides](composable-setup-guides.md) are **preserved at the domain/API layer**, but are not exposed as controls in this approved Workgroup view. If advanced composition remains necessary, it should be handled contextually by the appropriate workflow or an independently approved specialized view; do not reintroduce it into Guides & Charter without product review.

Demo data are fictitious, kept independent of Server. Prototype is a UX handoff, not production code.
