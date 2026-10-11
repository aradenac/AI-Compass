# AI Compass — Composable Setup Guides & Lifecycle

> **Reference:** Product/domain specification maintained with the implemented application. The delivery tracker and outstanding UX acceptance work are maintained in the [implementation plan](future-evolutions/implementation-plan.md).

> **Contract:** Reusable Setup Guide modules, exact applicability, composed recipes, rendered guide history and validation semantics.
> **Discussed:** 2026-10-10  
> **Area:** Knowledge & Collaboration / Guides & Charter; Technology Catalog; Benchmark Workspace; solution-facing documentation.  
> **Existing baseline:** [Setup Guides Server](setup-guides-server.md), [Benchmark Workflow](benchmark-workflow.md), [Product Definition](product-definition.md).  
> **Scope of this page:** Setup Guide composition, capture, applicability, readiness, lifecycle, and reuse only.

## 1. Objective

Give an engineer **one precise, actionable Setup Guide for the complete AI setup** they intend to use, without repeatedly documenting common installation steps or making separate component guides unmanageably large.

A full setup may combine a **Model, Provider, Harness**, versions, configuration parameters, operating system/architecture and deployment environment; **Frameworks** may additionally orchestrate multiple configured participants. Installation instructions can be both shared across setups and specific to component combinations.

The workgroup should enter setup knowledge **once, at the moment it is easiest to capture**, reuse it wherever applicable, and supply any missing portions during real campaign work. No complete documentation is required merely to register a model, provider, harness or framework in the catalog.

**Key product rule:** Every **evaluated solution configuration** published from a campaign must have an adequate setup procedure tailored to that complete configuration. This procedure can be **assembled from reusable parts** rather than authored as one duplicated standalone document.

## 2. Reusable components and rendered guide

Recommended **conceptual** separation (not an imposed one-table-per-concept schema):

| Concept | Responsibility |
| --- | --- |
| **Setup Module** | Reusable documentation section for a component, integration, prerequisite, environment, or verification step; can contain native text, a URL, or both. |
| **Setup Recipe** | Ordered composition of applicable module revisions plus any configuration-specific steps, substitutions, dependencies, and environment variants. |
| **Solution Setup Guide (rendered view)** | Coherent, deduplicated installation procedure presented to the engineer for an exact solution/configuration. A view of a recipe, **not an independently copied knowledge source**. |
| **Run Setup Snapshot** | The exact documentation/configuration known and used for a historical Test Run, including declared deviations; never silently rewritten by subsequent edits. |

Modules may describe a Harness alone, Provider access, Model settings, a particular Harness + Provider or Harness + Model integration, or a Framework's wiring and coordination. **The mere presence of standalone component guides does not prove a complete combination is supported or reproducible.** Integration instructions and verification may still be necessary.

Guides must preserve the current benefits of versioned reusable catalog items (permanent `gui-*` identifiers, immutable revisions and references); the design must **extend**, not silently replace, current URL-only, text-only or combined guide entries.

## 3. Configuration identity, matching and environment variants

A recipe's applicability must account for:

- Exact composition: Model, Provider, Harness, and optional Framework/participants.
- Relevant versions and settings (API parameters, authentication mode, extensions/skills and orchestration parameters where they affect installation).
- Deployment environment: OS and version, CPU architecture, relevant runtime/container and other necessary prerequisites.
- Explicit compatibility constraints, required integration instructions, and supported environment variants.

**Do not select a guide on superficial component-name matching.** A different model plugged into the same Harness or a different Provider may require additional or replacement instructions.

Keep a distinction between:
- **Logical recipe identity:** relevant solution composition, versions and significant configuration.
- **Validated applicability/variants:** the environments for which the steps are declared applicable.

One recipe may cover multiple environments using explicit conditional sections **when their differences are understood**; do not assume compatibility across untested or undocumented variants. Changes affecting the *actual measured configuration* belong to new versioned configurations/runs, not retroactive edits to historical conditions.

### Example — shared setup knowledge

Two hypothetical solutions:
1. Cline + GLM-5.2 + Scaleway — Ubuntu 22.04 x86-64.
2. Cline + Qwen3-Coder + Scaleway — Ubuntu 22.04 x86-64.

Both may reuse **Install Cline**, **Scaleway API access**, and **Cline/Scaleway integration** modules. Each refers to different model-specific settings; each solution also needs an applicable end-to-end verification procedure. The engineer sees **one assembled guide**, not a collection of unrelated documents.

## 4. Documentation capture: progressive, in the workflow

| Workflow point | Expected experience |
| --- | --- |
| **Catalog entry creation/update** | Users may create or enrich generic component/integration modules, but incomplete documentation does **not** block catalog registration. |
| **Campaign planning** | Suggest applicable existing modules/recipes based on each selected configuration; expose missing or conflicting sections. Avoid requiring duplicated authoring. |
| **Setup during a Test Run** | Reuse the closest applicable guide; document actual environment, versions, setup actions and deviations. Users may add a missing fragment without first producing a polished guide. |
| **Test Run closure** | **Automatically suggest** contributing new/corrected setup knowledge discovered during installation. This capture is **optional and non-blocking** for Run closure. Do not silently publish raw notes as validated instructions. |
| **Campaign review** | Show documentary readiness for each evaluated configuration to be included in publication. The workgroup can complete missing sections and perform the **initial guide validation** here. |
| **After publication** | Guides remain reusable and correctable as knowledge evolves, without mandatory re-review of existing campaigns. |

Avoid prompting the experimenter to enter identical information on every Run. Existing validated instructions should be preselected when applicable; capture the **delta** (uncovered steps, corrections, verified variants, deviations) and offer to reuse it for future setups.

The end user's guide is rendered at **AI Solution/configuration level**, regardless of whether its underlying modules were contributed from component catalog screens, setup sessions or campaign review.

## 5. Initial validation and publication gate

**Decisions made:**
1. **When:** the guide is validated **during campaign review, before publication**, not upon every catalog-component edit.
2. **Who:** **any authorized AI workgroup member**, including its author; there is no requirement for independent second-person review.
3. **Granularity:** the guide/recipe must cover the exact **combination + versions + environment** relevant to the actual evaluation.

A campaign may be planned, run tests and gather evidence **while setup documentation is incomplete**. Its *Publish* action is blocked **only for a proposed subset containing an evaluated configuration** that lacks an appropriately complete, initially validated setup procedure. A reviewed [partial publication](publication-and-information-lifecycle.md) of other eligible, documented Runs is permitted; pending/incomplete attempts are not included. The Workgroup must not present such a partial release as full plan completion.

This documentary gate is separate from experimental outcome:
- A Run with failed acceptance criteria is still a real Run; negative findings may be published with **accurate reproducibility documentation of the attempted setup**, not a false claim that the installation succeeded.
- **Not Selected** and **Waived** Test Case × Solution combinations create **no documentation obligation by themselves**. If the same solution was actually evaluated in another combination, its published evaluation still requires coverage.
- The gate verifies **document availability, applicability and sufficient detail**; it does **not** certify model quality, universal compatibility, successful Test Case outcomes or a recommendation.
- Previously validated documentation is **reused without recurring approval** when it matches the evaluated configuration and environment.
- The workgroup's review action and the publication action retain their existing campaign lifecycle/permission semantics.

Suggested readiness fields: each evaluated configuration, matching recipe/revision, applicability, missing module/integration/verification details, documentation status, and an intelligible **Publish blocked: N incomplete setups** message. A recipe should cover prerequisites, exact versions/settings, actionable setup steps, integrations, and checks needed to reproduce the tested environment.

## 6. Post-validation evolution: corrections without review cascades

**Explicit policy:** a component update **must not automatically invalidate** prior Test Runs, their results, existing relationships/dependencies, previously published campaigns, or already approved recipes.

- A Model/Provider/Harness/Framework update does **not** launch a required revalidation campaign or a new documentation review.
- Corrections and incremental refinements to setup instructions (including typographical, explanatory and other declarative fixes) are allowed **after guide validation/publication** without reopening or reapproving the associated campaign.
- New versions/revisions of edited documentation preserve the original revision referenced by historical Runs and published snapshots. Historical evidence remains attached to what was actually used, not silently repointed to the newest instructions.
- **Do not change measured Run results** as a side-effect of documentation edits or component updates.
- Newly discovered defects or incompatibilities may be corrected progressively as encountered. They need not block unrelated operations or force a cascade of obsolescence statuses.
- If a change describes a genuinely different technical setup, preserve its distinct versioned configuration/recipe applicability; do not pretend historical results measured that new setup.
- Historical links remain valid even if a later guide provides better instructions or corrects a mistake.

This is **lightweight lifecycle management**, not a recurring certification workflow. The initial publication gate remains; routine improvements after initial validation do not force a fresh review. Local guide-revision preservation follows the existing immutable revision architecture.

## 7. Frameworks and composite workflows

For a collaborative Framework run, the rendered setup should compose:
- Installation and configuration of the Framework itself.
- Relevant module/recipe for each participant's exact Model + Provider + Harness + environment.
- Wiring, routing/handoffs, shared credentials handling, orchestration parameters, deployment prerequisites and end-to-end verification of the **composite workflow**.

A Framework is **not itself an individual AI Solution trio**. Documentation completeness for separate participants does not automatically establish completeness for the composite workflow.

Keep the existing distinction between individual measured solutions and composite Framework Runs; the recipe system should support both rather than manufacture an individual-solution identity for the Framework.

## 8. Data/model and frontend implications (preliminary)

| Area | Impact / direction |
| --- | --- |
| **Guide Catalog** | Add reusable module composition and applicability information while maintaining existing `gui-*` guides and historical revisions. |
| **AI configuration / solution selection** | Resolve the most specific applicable recipe for exact versions/settings/environment. A prospective configuration may need documentation **before** the first Run gives rise to a measured AI Solution identity. |
| **Benchmark Workspace** | Inline reuse/edit/add of missing modules; optional capitalisation prompt on Run closure; readiness and completion controls in campaign review. |
| **Review / Publish API** | Compute per-configuration guide completeness and reject publication only when relevant evaluated setups are undocumented/unvalidated. |
| **Run evidence** | Pin exact recipe/module revision and actual used setup/deviations, preserving prior Run evidence. |
| **Engineer-facing solution view** | Present one contextual, ordered, readable Setup Guide instead of a manual set of unrelated links. |
| **Framework workflows** | Compose participant guidance and extra workflow-specific integration instructions. |
| **Conflict management** | Warn about contradictory modules, missing preconditions and overlaps; support explicit overrides/substitutions. Start with a simple **assisted composition** rather than an elaborate rules engine. |

Avoid secret leakage: guides should describe credential acquisition, required permissions and configuration-variable **names**, never actual API keys, tokens, passwords or other sensitive values.

## 9. Acceptance criteria

1. A new Harness or Provider may be registered without a completed setup guide.
2. An experimenter configuring a solution can retrieve relevant existing guidance and supply only missing integration/variant details.
3. Two solutions sharing Cline and Scaleway reuse common modules but can have distinct model instructions and final rendered guides, with no copied source sections.
4. A Test Run can be closed while documentation is incomplete; it offers a **non-blocking optional** prompt to contribute missing setup knowledge.
5. A campaign with completed experimental obligations but an incomplete/unvalidated guide for an evaluated configuration **cannot Publish**; it can proceed to review and complete that guide there.
6. An authorized workgroup member can perform initial approval of a recipe during campaign review, including approving their own work.
7. An already validated applicable recipe is accepted in a later campaign **without redundant review**.
8. A documented but unsuccessful/failed setup can support publishing a negative Run without falsely asserting that the installation was successful.
9. **Not Selected** and **Waived** candidate combinations require no guide unless the solution was otherwise actually evaluated.
10. Updating a catalog component or improving a validated guide creates **no automatic invalidation or mandatory re-review** of existing measured results, dependencies, published campaigns or historical guide snapshots.
11. Published guide corrections are allowed without rewriting historical Run documentation or measured outcomes.
12. The engineer receives a coherent recipe for the **precise versions and environment** of the solution; incompatible or missing sections are not silently merged.

## 10. Questions for later implementation design

- Should Setup Modules be independent catalog entities, or composable versioned sections of the existing `setup_guide` type?
- How should exact applicability rules, supported environment variants and explicit substitutions be represented without unnecessary rules-engine complexity?
- What is the minimum objective checklist for **initial readiness** (including intentionally unsuccessful setups)?
- How should a newly captured installation fragment be proposed for reuse and associated with pre-measurement candidate configurations?
- How should user-facing changes to an already validated guide be exposed while retaining pinned historical versions?
- How much should the frontend automate composition versus require workgroup selection/confirmation?

## 11. Boundaries

This page specifies **Setup Guides only**. It does not redefine generic data editing, platform-wide audit policy, permissions, global revision requirements, benchmark scoring, or unrelated governance. It records a future functional direction, **not a claim that modular recipes or documentary publication gates have already been implemented**.

## 12. Cross-feature ownership: published subset and corrected guides

This feature owns **reusable Setup Modules/Recipes, matching exact configurations/environment and initial validation of documentation**. The cross-cutting [Publication & Information Lifecycle](publication-and-information-lifecycle.md) owns **which complete Runs are in the current effective published subset**, its later correction/withdrawal and any physical deletion rules. Initial documentary readiness applies **only to exact evaluated setups in the proposed published subset**, not incomplete or abandoned sessions. A complete Run with a failed DoD may be published if its attempted setup is documented accurately; failure is not a reason to fabricate installation success.

**Later guide changes are not retrospective invalidation:** a reused guide may acquire improved steps, newer modules or corrections in subsequent Campaigns. Prior Campaigns and Runs retain their exact originally pinned guide/recipe revisions and stay historically valid; no cascading republish, mandatory re-review or rewriting of earlier evidence. Current solution detail may navigate to the newest applicable instructions, clearly distinct from the historically used setup.

[OS Compatibility](os-compatibility-and-user-environment.md) owns coarse Windows/Linux declarations for Harnesses/Frameworks; this Guide feature owns **environment-specific installation instructions** even when capabilities are declared equivalent across the two systems.
