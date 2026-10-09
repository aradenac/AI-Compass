# AI Compass — Product Definition

> **Status:** Agreed functional baseline  
> **Date:** 2026-10-08  
> **Scope:** Internal web platform, extensible across business units (BUs)  
> **Purpose of this document:** Record product decisions agreed during initial scoping. It describes *what* the platform must achieve, not a frozen UI, technology stack, database schema, or scoring algorithm.

**Technical direction:** The selected platform architecture, persistence, immutable revision strategy, identifiers, recovery and independent maintenance permissions are documented in [Platform Architecture & Data Governance](platform-architecture-and-data-governance.md). This document continues to define business capabilities and workflows.

## 1. Product vision

**AI Compass is an evidence-driven, continuously updated decision-support platform for selecting, comparing, qualifying, and sharing AI solutions for engineering tasks.**

It is the shared source of truth for the AI workgroup, engineering users, management, and ultimately the wider group. Its core question is:

> For this engineering activity, which AI solution is appropriate, with which configuration, based on what evidence, at what total cost, and with how much remaining human involvement?

The platform connects engineering needs, evolving task definitions, reproducible experiments, user experience, and explainable recommendations.

**Core loop:** Discover → Evaluate → Decide → Use → Feedback → Re-evaluate.

### Product goals

- Provide transparent, traceable, current information and recommendations.
- Help engineers select solutions based on *tasks*, not only model leaderboards.
- Compare complete AI solutions, including the harness and configuration.
- Measure quality, autonomy, human work, and economic value in real engineering conditions.
- Preserve enough experimental evidence to audit, challenge, and reproduce benchmark conditions.
- Capitalize on workgroup activities and real-world feedback.
- Support continuous technology watch and obsolescence management.
- Provide useful reporting for engineering, management, and the wider group.
- Remain extensible to other BUs without segregating results by BU.

## 2. Audiences and use cases

| Audience | Primary needs |
| --- | --- |
| Engineer | Explore the catalog; browse the task hierarchy; search, filter, sort, and compare AI solutions; find recommended configurations; read guides, FAQ, training material and the Impulse/AI usage charter; submit feedback, ideas, and unmet needs; consult news and newly published results. |
| AI workgroup | Maintain independent model/provider/harness catalogs, manage engineering tasks and test designs, organize and review qualification experiments, preserve evidence, publish results, recommendations and guides, discuss feedback in public and internal threads, and re-evaluate obsolete decisions. |
| Management / Group | Track engineering/V-cycle coverage, progress, adoption, operational outcomes, cost/value, and workgroup activity; identify uncovered needs and investment priorities. |
| Other BUs | Access the same published knowledge and contribute experimental evidence and feedback, subject to publication permissions. |

The platform serves both **operational discovery** (the engineer needs an answer) and **experimental inquiry** (the workgroup needs defensible evidence).

### Workgroup-specific navigation and workflow ownership

The workgroup requires a distinct information architecture, not the end-user `Discover / Evaluate / Collaborate` navigation:

| Workgroup screen | Primary responsibility |
| --- | --- |
| Dashboard | **Read-only daily campaign pipeline**: Planned, In progress, Under review, Published; latest feedback and technology-watch signals. No campaign editing or state-changing controls. |
| Task management | Maintain the task tree in place while still inspecting the engineer-facing navigation and task evidence. |
| Technology watch | Create evidence-backed hypotheses, select previously registered citations or add new ones, derive theoretical forecasts and manage their publication state. |
| Technology catalog | Maintain Models, Providers, Harnesses and Frameworks independently; frameworks describe coordinated multi-participant workflows, not single model/provider/harness triples. |
| Test design | Create and inspect reusable, versioned Test Cases; navigate the parent–fork tree and assign collision-free fork versions. |
| Benchmark workspace | **Campaign-centred operational entry point**: create/edit campaigns, link Technology Watch signals and setup guides, optionally select a Framework and configure several model/provider/harness participants, attach Test Cases, record executions, close, review/publish and reopen campaigns. |
| Results explorer | **The analytical entry point** for published run evidence, coverage and task- or solution-centric comparison; distinct from the operational workbench. |
| Recommendations (Knowledge & Collaboration) | Inspect and maintain evidence-linked decisions and their publication state; this screen is not under Experiments. |
| Guides & charter | Maintain, filter, search, sort, edit and publish knowledge articles. |
| Feedback & discussions | Read end-user contributions and reply through one chronological thread with public/internal visibility per message; no corrective-action management. |
| Activity feed & management view | Activity feed records enriched attributable events, opens per-event details, and exports structured JSON/CSV for workgroup reporting; management views remain separately scoped. |

The **campaign pipeline** is the workgroup's daily dashboard: **Planned → In progress → Under review → Published**. It is a strictly read-only summary; campaigns are created, opened, edited, closed, reviewed, published, reopened or archived in **Benchmark workspace**. The campaign replaces separate qualification queues as the central work object. A measured AI Solution is still identified by its first controlled run, not by creating a campaign.

## 3. Access, publication, and organizational scope

These are agreed decisions:

- **Published information is readable by everyone with access to the platform.** “Public in reading” means shared visibility within the intended platform audience; it does **not** imply that confidential R&D content is published on the open Internet.
- **Official publication requires authentication and workgroup membership.** A single authorized workgroup member may qualify and publish a recommendation; mandatory two-reviewer approval or consensus is not required.
- Drafts and staging materials may remain unpublished until a workgroup member publishes them.
- Engineers can submit feedback, requests, or proposals without directly modifying official benchmark conclusions or recommendations. Contributions are handled separately from official publications.
- Results form **one shared knowledge base** across BUs. BUs do not have separate recommendation universes or result silos.
- User accounts can identify BU affiliation and contribution provenance. Access rules may use these attributes where needed.
- The platform should support roles/permissions and an audit history of published changes.
- An independent **Maintenance & Governance** workspace is reserved for data integrity, quality, schema compatibility and migration stewardship; its **Data Maintainer** role need not grant access to campaign execution or unrelated business functions. **User Administrator** account/permission management and **Platform Administrator** operations are separate, composable capabilities (see the [architecture baseline](platform-architecture-and-data-governance.md)).

Exact identity-provider/SSO implementation and finer-grained access policies remain technical design choices.

## 4. Catalog and definition of an AI solution

The **workgroup catalog is organized around four independent, reusable component types: AI Models, Providers, Harnesses and Frameworks**. Members maintain each item's version, capabilities, availability, lifecycle and provenance. These catalog candidates exist **before** they are combined or benchmarked; they are **not** themselves AI Solutions.

**A measured AI Solution is registered by the first controlled benchmark run of a specific assembled setup.** Before that run, the workgroup may create a distinct, task-linked **Theoretical Configuration / Forecast** based on Technology Watch evidence. Forecasts are comparable solution candidates, but their numbers remain predictions and not empirical AI Solution results. During benchmark preparation, a workgroup member selects one model, one provider, one harness, and the complete versioned configuration (prompts, parameters, tools, skills, etc.). Once that setup has a recorded run — including a failed or unpublished run — it becomes an identifiable AI Solution linked to its evidence. The same exact configuration can be reused across tasks, TCs and runs; materially changed components or configurations produce a distinct solution.

This defines **two evidence channels**: a workgroup's theory-backed forecast may be drafted, staged, reviewed and published without a controlled run; the benchmarked AI Solution is independently identifiable once a run exists. Publishing a forecast does not qualify a model, make its projected metrics measured, or implicitly publish a measured solution. Component catalog records, Watch Entries, forecasts, benchmark runs and official recommendations retain separate identities and lifecycles.

An **AI Solution** is the concrete, reproducible combination of:

- **Model:** model name and exact version/revision where available.
- **Provider:** service/API or deployment delivering the model.
- **Harness:** agent or interaction environment (CLI, IDE, web, orchestrator, etc.).
- **Configuration:** parameters, prompts, system instructions, tools, skills, permissions, routing, and other relevant settings.
- **Capabilities:** agentic tools such as web search, filesystem, shell, MCP integrations, document formats, vision, and other supported functions.
- **Versions and dependencies:** information necessary to interpret and, when possible, recreate the evaluated setup.

The same model under different providers, harnesses, or configurations can constitute distinct AI solutions and yield different results.

**Frameworks are a fourth catalog type, not another field in a single model/provider/harness triple.** A Framework is a workflow or orchestration methodology (examples: n8n, BMAD Method, GitHub Spec Kit), which can assemble several **participants**. Each participant has a stable ID within its campaign, a role, a model, a provider, a harness, a configuration version, parameters, available tools, and an access flag. The campaign stores a `frameworkId` and an arbitrary-length collection of `frameworkInstances`; these participants are separate potential AI Solution configurations, not copies of the Framework itself. The framework identity, chosen participant and configuration are pinned in execution snapshots.

The user-requested label **PMAD** is kept as an *unverified* example, separately from verified **BMAD Method**, pending identification of the intended product. Do not present PMAD as verified or silently identify it with BMAD.

**Current prototype modes:** a Framework campaign supports (1) **individual participant runs**, each linked to one exact model/provider/harness configuration and capable of registering a measured AI Solution; and (2) **collaborative workflow runs**, selecting two or more registered Framework participants within one Test Case execution. Collaborative runs preserve all participating roles, component references, framework workflow wiring, selected Setup Guide and per-interaction responsible participant. Their **composite quality, information utility, cost and duration belong to the overall workflow**, not to its participants individually. They therefore carry a composite benchmark flag without asserting individual AI Solution scores. Existing independently tested participant solutions can be linked for context, but are not credited with the collective result.

Component candidates and resulting AI Solutions may be **accessible or inaccessible** to enterprise users. Accessibility is a visible/filterable property, not an exclusion rule. Untested candidates remain discoverable in the independent component catalogs and technology watch; only recorded benchmark combinations appear in the AI Solution discovery view.

Technology-watch entries are free-standing **reasoned hypotheses** that may concern a model, harness, provider or *complete proposed configuration*. They can include multiple external literature sources and need not immediately create or link any technology catalog component. One or more watch entries may support a forecast for an engineering task.

## 5. Flexible engineering task hierarchy

The task reference structure is an **editable, arbitrary-depth tree** from broad activities to specific engineering tasks.

Example navigation path:

**Software Development → Embedded Software → MCU → Driver Development → KSZ8851SNL Driver**

The system must support:

- Adding, renaming, moving, grouping, ordering, and retiring nodes without a fixed number of levels.
- **In-place taxonomy authoring for workgroup members:** directly edit a node and reorganize the hierarchy through drag-and-drop between sections, as children of other nodes, or before/after siblings. Provide an alternative parent selector and up/down controls for keyboard or touch use, and prevent cycles or self-parenting.
- **Section-level organization:** top-level branches act as editable sections; adding, moving, and reordering complete branches must preserve all descendant relationships and stable task identities.
- Browsing and searching from any node; finding solutions without requiring the user to reach a leaf.
- Metadata and transversal filters independent of the tree (e.g., domain, specialty, project phase, V-cycle activity, complexity, confidentiality).
- Contextual information or properties associated with tasks and their branches.
- **Inherited task properties:** a node can expose effective classification/context properties inherited from its ancestors, alongside its own explicitly defined properties. Local overrides or exceptions must be identifiable rather than silently changing the meaning of a parent's property.
- Stable identities and historical references: rearranging the tree or changing inherited properties must not retroactively reinterpret the recorded context of past experiments.
- Aggregated performance/coverage views at higher levels without pretending they were directly benchmarked.
- Distinct task-linked **theoretical forecasts** containing expected metrics and supporting Watch Entries, visible alongside measured TC/run evidence without mixing the two evidence classes.

The hierarchy is primarily an **engineering activity taxonomy**. A task can be broad or specific. Multiple cross-cutting classifications may apply to the same task; they should not all be forced into the tree.

### Task information

A task definition may include:

- Name, purpose, problem statement, and expected engineering benefit.
- Task categories/taxonomy, specialty, domain, project or V-cycle activity (including audit and general engineering work).
- Typical input context, tools, constraints, expected deliverables, and relevant environment.
- Acceptance criteria and Definition of Done (DoD), including mandatory minimum requirements and criteria eligible for scoring.
- An original **engineer-only effort estimate** as the baseline for cost/value assessment.
- Other relevant properties such as complexity and data sensitivity.

**Implementation quality, error handling, test coverage, regression behavior, and similar concerns are expected outcomes or acceptance criteria.** They are not automatically separate task-tree branches or distinct test-case categories.

## 6. Test cases are experimental instances, not tree levels

**Test Cases (TCs) are attached to relevant tasks, but are separate from the task hierarchy.** This is a deliberate distinction.

For the task “Develop KSZ8851SNL Driver,” the workgroup might define TC1, TC2, and TC3 as *different concrete challenges*. Each can use a different starting repository, amount of supplied context, hardware constraints, difficulty, or failure mode while evaluating the same underlying engineering activity.

A TC should document:

- The associated task and purpose of the challenge.
- Initial state, input files/assets, dependencies, environment, and constraints.
- Expected output and applicable DoD/acceptance criteria.
- Any TC-specific test conditions, constraints and variations needed to interpret results.
- Its version, optional direct parent (when forked) and evolution history.

**New TCs can be added at any time specifically to challenge, invalidate, or strengthen earlier conclusions.** They expand experimental coverage; they do not replace earlier results.

The system must distinguish:

- **New TC:** a new experimental challenge or coverage dimension.
- **New run of an existing TC:** a repeat under documented conditions to observe variability, reliability, or changes over time.

There is no mandatory quota of TCs per task. A task can start with one and accumulate more.

**Fork lineage in Test Design.** An independent Test Case is a root (for example, version `1.0`). Forking creates a **distinct child Test Case** with a stable technical ID, its parent's ID, and a version built by appending a new integer to the parent's full version: `1.0 → 1.0.1` and `1.0.2`, or `1.0.1 → 1.0.1.1`. The suffix is assigned at save time and must not collide with existing versions for that engineering task. Children inherit their parent's task; the previous cases, versions and measured runs remain intact. A task-grouped navigable tree presents the parent/fork hierarchy. Older cases without explicit parent metadata are treated as roots rather than given speculative ancestry. The original `TC1` naming in demo titles is descriptive, not a globally unique key.

## 7. Campaign-centred benchmarking and comparison modes

The **Benchmark Campaign** is the principal workgroup object for experimental preparation, controlled execution, peer review and publication. Benchmark Runs remain the atomic, independently auditable measurement records, and Test Cases remain reusable challenges linked to the task taxonomy. Campaigns coordinate them without redefining their meaning.

### Mode A — Solution-centred campaign

A member chooses and pins **one concrete AI configuration** (model, provider, harness, version, permissions, tools and relevant configuration). The campaign then evaluates this setup across **several Test Cases**, optionally drawn from **multiple engineering tasks**, to map its applicability, strengths, weaknesses, costs, quality and autonomy.

Question: **What can this particular AI configuration accomplish across the chosen engineering tasks?**

Without a Framework, the fixed configuration is recorded at campaign creation before any run. With a Framework selected, the campaign instead records one or more individually labeled and configured participants, plus optional orchestration/wiring notes; execution selects either one participant for an individual evaluation or multiple participants for one composite workflow evaluation. A new measured AI Solution identity is generated when that specific configuration has its first controlled run.

### Mode B — Task-centred comparison campaign

The member chooses **one engineering task** as the fixed comparison scope. Several reusable or newly authored Test Cases associated with that task challenge **multiple AI configurations**. Each execution selects or builds the tested solution (model, provider, harness and configuration), and records the outcome under the same experimental data model.

Question: **Which tested configuration is appropriate for this task, with what evidence, effort and cost?**

Comparisons must report the Test Cases, experimental conditions and sample sizes; unmatched challenge sets must not be treated as like-for-like rankings.

### Lifecycle and ownership

A campaign defines its experimental objective, strategy, fixed task or fixed AI setup, optionally a Framework and its participant configurations, **an optional referenced setup guide**, owner, notes, **zero or more linked Technology Watch signals**, and Test Cases/runs. Signals are selected by checkboxes at creation or editing and may be associated with a forecast. Links preserve references without copying or transforming Technology Watch estimates into measured results. New benchmark run records pin a snapshot of the campaign's selected signals; changing links while a campaign is Under review requires a new review cycle. Its operational lifecycle is:

**Planned → In progress → Under review → Published**

- **Planned:** prepared and editable, but not yet executing new Test Cases.
- **In progress:** add or attach Test Cases and execute guided, resumable runs.
- **Under review:** closing stages collected evidence and outcomes for another workgroup member's review; publication has not yet occurred.
- **Published:** peer-reviewed controlled run evidence is released, including accepted and failed trials. Publication is not a blanket endorsement of the AI configuration.
- **Reopen:** move an under-review or published campaign back to In progress, preserving all earlier evidence and audit events. A review can also reject the submission and reopen it for corrections.
- **Edit/delete:** campaign metadata is editable, with guards preserving comparison scope once trials exist. Empty campaigns can be deleted; evidence-bearing campaigns are archived so underlying runs never disappear. Archived campaigns can be restored.

Any workgroup member, **including the campaign creator**, may document and approve the campaign review. Publication, explicit unpublication back to review and reopening are reversible transitions recorded in the history; no mandatory independent second reviewer is required in the prototype. Unpublishing a campaign retracts its published runs. A benchmark-generated AI Solution is returned to Draft when it no longer has any published run, but retains its publication when another campaign still supplies published evidence; trial records and reviews remain auditable.

The daily Dashboard shows the four campaign columns and progress/ownership **read-only**, while the Benchmark Workspace is the actual control surface.

## 8. Benchmark run and evidence

### Experimental conditions without a separate protocol object

The active Test Design interface deliberately does **not** expose benchmark protocols or a separate protocol catalog. The Test Case itself defines the challenge, input state, environment, constraints and Definition of Done. The guided benchmark session captures configuration, installation guide, timestamped interactions, durations, reviewer assessments, and artifacts. For meaningful comparison, engineers must still document relevant differences in conditions and samples, but no additional versioned protocol must be created or selected.

Historical records may retain legacy protocol identifiers and snapshots for backward compatibility; they are not requested in new forms and are not presented as a current workflow.

### Guided workgroup execution

A Test Case in an **open campaign** follows a guided, resumable sequence.

1. **Installation and setup:** use the reusable **Setup / Installation guide** preselected when creating the campaign, choose another compatible guide from Guides & Charter, or register a new one inline. Every guide is a catalogued resource identified by an ID, and can contain **procedure text, an HTTP(S) URL, or both**, with at least one of the latter required. A guide may optionally be associated with an exact AI Solution or a Framework; unassigned guides are reusable across solutions. The selected guide and its content/URL snapshot are retained in the run. Record actual model/provider/harness setup, local installation start, environment/deployment notes and human setup duration. Prompting the agent, submitting inputs or activating runtime skills/options is **not installation**.
2. **Timed interactions (at least one):** initial prompt/instructions are logged as the first interaction. Subsequent prompts, input documents, enabled skills/options, reviews and corrections are timestamped with independent human intervention and agent runtime/waiting durations plus intermediate evidence. **Total agent runtime is derived by summing those iteration durations**, not independently entered in Step 5.
3. **Results, artifacts and metrics:** record accepted/failed DoD, Quality and Information Utility scores (0–100, supported by free-form evaluation), **optional total tokens** with explicit multiplier, and one cost classification: run-specific numeric EUR amount, flat-rate/subscription (cost unallocated), or unknown. Flat-rate/unknown must not be treated as €0. Record final human review and correction durations, one canonical set of produced output references, and optional additional notes. No redundant separate input/output token fields, additional runtime input, duplicated deliverable descriptions or utility-related loose text fields.
4. **Close run:** pin Test Case, solution configuration, installation guide, interaction timeline, outputs and known/unknown metrics. Failed runs remain auditable. Closing a run does not close the campaign.

Setup guides are reusable knowledge-base entries: create/select them at campaign planning and select/override them when executing. They support text-only, URL-only and combined references; links use HTTP(S) and are not binary uploads. Their IDs and snapshots give provenance even when the referenced website changes.

### Benchmark Run

A run is one execution of **one fully specified AI setup or orchestrated Framework workflow on one Test Case**, with documented execution conditions. Individual runs refer to one measured AI Solution; composite Framework runs refer to the Framework and multiple participant configurations, without manufacturing a single-trio AI Solution identity. For a setup without existing evidence, the run **creates its AI Solution identity** and stores the component references, their versions, the complete configuration, and experimental snapshots. For subsequent runs, the existing exact solution may be reused. Multiple runs of the same pairing are allowed and useful.

A run records:

1. Exact solution/model/provider/harness/configuration versions, or the pinned Framework and all joint participant roles/configurations for a composite run.
2. Test Case (including fork lineage when available), run date, and relevant environment/input revisions.
3. Initial prompt/instructions and any subsequent interactions.
4. Execution trace, interruptions, re-prompts, failures, and interventions.
5. Produced deliverables and results against acceptance criteria.
6. Human effort, runtime, tokens, monetary costs, and other metrics.
7. Reviewer observations, required corrections, and final acceptance outcome.
8. Supporting files and references (source, diffs, tests, logs, reports).

### Auditability and reproducibility

**Official benchmark experiments must retain prompts, conversations, artifacts, and supporting evidence**, subject to access/security controls for sensitive content.

Each run should provide:

- A **reproducibility package**: the inputs, prompts, versions, configuration, environment, and dependencies needed to recreate experimental conditions.
- An **evidence package**: traces, outputs, tests, cost records, reviews, corrections, observations, and relevant provenance supporting the reported results.

A reproducible setup does **not** guarantee identical outputs from stochastic AI systems. Repeated runs characterize that variability.

**External evidence is also relevant:** public or third-party benchmarks, research, provider documentation, and other published observations can support technology watch or qualification. The source, publication/retrieval date, tested setup, methodology (where known), and limitations should be recorded. Such references must be labeled separately from controlled internal runs and voluntary field feedback; unsupported vendor claims must not be presented as reproduced results.

**Ordinary engineer usage is different:** the platform does not retain their day-to-day prompts, complete conversations, or artifacts merely because a recommended solution is used. Engineers may nevertheless submit voluntary feedback.

## 9. Metrics: quality, autonomy, information, and economic value

Benchmark results must preserve **raw observations** separately from derived metrics and scoring.

| Dimension | Examples |
| --- | --- |
| Quality and acceptance | Mandatory DoD pass/fail; graded rubric; defects; completeness, maintainability, test outcomes. |
| Human preparation | Active tool installation, deployment and initial environment readiness work, excluding agent prompting and later input exchanges. |
| Human steering | Approximate active human time guiding the solution, including the initial prompt, input submissions, interventions, iterations and re-prompts. |
| Human review | Approximate time inspecting, understanding, and verifying deliverables. |
| Human corrections | Approximate additional engineering work required to reach acceptance. |
| Autonomy | Successful independent progression, human intervention demand, failure/escalation patterns. |
| AI resource use | Optional total tokens consumed (if known), model calls where documented, computed agent runtime, and run-specific tooling/API expenditure or an explicit flat-rate/unknown classification. |
| Information utility / density | Relevant, novel, correct, actionable information in proportion to the amount produced (e.g., tokens or output volume), accounting for irrelevant content and adverse side effects. |
| Reliability | Variation between repeated runs; completion/acceptance rate; recurring failure modes. |
| Cost/value | Direct AI/tool costs, valued human effort, saved work versus engineer-only baseline, cost per accepted result. |

**Useful information density** is a distinct evaluation objective: outputs should be assessed for how much correct, relevant, novel, actionable content they deliver per unit of output, not simply for length or novelty alone. Errors, misleading conclusions, and additional verification or correction burdens count against practical utility. The precise measurement method is still open; no particular formula is mandated.

The four human effort categories are **approximately declared**, not required to be timed precisely. Their uncertainty and the method of estimation should be visible; false numerical precision should be avoided.

Illustrative derived quantities (definitions/valuation policies still to be finalized):

- **AI-assisted human effort** = preparation + steering + review + correction.
- **Human effort saved** = engineer-only baseline − AI-assisted human effort.
- **Total assisted cost** = AI/tool/service cost + valued AI-assisted human effort.
- **Cost per accepted result** = aggregate total assisted cost / accepted results (with the population and acceptance criteria specified).

These measures are valuable only when baselines and output quality are sufficiently comparable. Cost per token alone is not an adequate proxy for engineering value.

## 10. Evaluation, comparison, and scoring

**Evidence and measured results are the source of truth. Scores and recommendations are explainable interpretations of those data.**

An evaluation can summarize one run, repeated runs on one TC, or multiple TCs associated with a task. Aggregation must preserve the relationship between the original observations and the conclusions.

Required principles:

- Store raw observations and individual outcomes permanently, without overwriting them with a new aggregate.
- Keep scoring rubrics, formulas, criteria, weights, and algorithm versions explicit and auditable.
- Permit recalculation when scoring models evolve.
- Present important dimensions separately (quality, autonomy, cost/value, reliability, etc.); a single composite score must not obscure trade-offs.
- Support **comparison on a common set of TCs** as distinct from performance observed over different tested subsets.
- Surface coverage, sample size, missing evaluations, uncertainty, and confidence in conclusions.
- Treat untested cases as **unknown**, not successes or failures.
- Avoid extrapolating the performance of one narrow TC to an entire engineering domain without appropriate evidence.
- Keep evaluation evidence distinct from workgroup judgment and from end-user feedback.

**The precise scoring formula, weighting scheme, confidence thresholds, and aggregation mathematics have not been fixed.** They must be configurable/versioned decisions derived from the retained measures.

## 11. Recommendations, charters, and documentation

Recommendations are **globally shared**, not isolated per BU or generated as separate official recommendation sets for each context.

There are at least two distinct publication levels:

1. **Per-solution recommendations:** suitability, supported tasks, known limitations, relevant capabilities, expected quality/autonomy/cost, recommended configuration, confidence, and linked evidence.
2. **General charters and guidance:** usage rules, recommendations applicable across solutions, acceptable practices, organizational guidance, FAQs, training, and documentation.

Users personalize discovery through **properties, filters, sorting, and comparisons** (task, capabilities, access, costs, suitability, etc.), rather than maintaining parallel BU-specific recommendations.

Published content can include benchmark results, setup and usage guides, comparison summaries, charter links, qualification conclusions, and advice on available alternatives.

A recommendation must remain explainable: **what was concluded, on what evidence, when, and by whom**.

Knowledge articles must support editing existing content, filtering by document type and publication status, searching title/content and sorting by recency or title. Revisions retain editor identity and history; creating a new article must not be the only authoring path.

## 12. Technology watch, staging, publishing, and obsolescence

The workgroup must be able to:

1. Enter and maintain an interesting **individual model, provider or harness** from technology watch, even before access or qualification, without preregistering an AI Solution.
2. Enrich the candidate's metadata and capabilities as information arrives.
3. **Within Benchmark Workspace**, start a Campaign, select a solution-centred or task-centred experimental scope, add Test Cases, and record controlled runs. The first completed run of a new configuration automatically registers and links the measured AI Solution. Neither a Watch Entry nor the component catalog should launch an experimental campaign directly.
4. Compare staged theoretical forecasts and published controlled experiments in clearly separated evidence categories.
5. Publish findings, recommendations, documentation, and corrections.
6. Re-evaluate existing recommendations when new TCs, models, versions, evidence, prices, or retirements make them questionable.

A lightweight content lifecycle is sufficient initially:

**Draft → Published → Superseded / Retired**

**Keep three separate dimensions rather than one overloaded status:**

- **Accessibility:** whether the solution is accessible to enterprise users; inaccessible candidates remain visible and comparable.
- **Qualification maturity:** whether evidence is still preliminary/experimental, has been evaluated, or is sufficient for qualification. These descriptors summarize evidence maturity and do not themselves grant publication rights.
- **Publication and recommendation lifecycle:** draft versus published content, followed where relevant by supersession/retirement; publication of a solution's record does not automatically mean it is recommended.

A candidate can be inaccessible and qualified, while an accessible solution can be experimental or not recommended. Exact labels and transitions can be settled during design without conflating these dimensions.

The system should retain dates and provenance such as **created, published, last verified/reviewed, validity, and supersession relationship**. It should highlight advice potentially due for review or rendered obsolete, and maintain history rather than silently replacing previous conclusions.

### Technology-watch hypotheses and evidence-first screening

The intended first flow is now:

**Watch Entry → explicit rationale and sources → task-linked theoretical configuration → Draft → Staged → Reviewed → Published (THEORETICAL)**

A Watch Entry is an investigative **hypothesis**, not a pending catalog component. It records the question or intuition, expected opportunity, assumptions, scope and multiple public sources (papers, published benchmarks, vendor statements, expert estimates) **during creation**, not only after submission. Each source stores citation, claim, limitations, confidence and origin. Later sources can be appended without erasing the original hypothesis. Several Watch Entries may support one forecast; a Watch Entry may support several forecasts.

**Reusable source library:** external publications, public benchmark reports, vendor claims and expert estimates are independently registered source records. Watch Entry creation and editing must support **search/select existing references** or **register new ones inline**, without forcing repeated multi-field forms for already cataloged literature. Source identity and citations are shared through a **many-to-many Watch Entry ↔ Source relationship**, including author, citation, publication status, confidence and limitations. Creation deduplicates equivalent references (at least normalized source URL or equivalent title/reference) and reuses identifiers. Unlinking a source from one Watch Entry must not delete it from the library, remove its links to other Watch Entries, or silently change frozen forecast evidence snapshots. Existing single-watch source records must migrate without evidence loss.

An individual Model, Provider or Harness catalog item can be created independently when concrete technical inventory is useful, but must **not** be generated automatically or presented as a mandatory step from a Watch Entry. Technology Watch should not expose redundant navigation buttons to Technology Catalog or unexplained lists of "unqualified components."

### Theoretical configuration and projected value

The workgroup may compose a **theoretical candidate configuration** using selected model/provider/harness components, a versioned set of assumptions/configuration, and one **stable engineering task reference**. Its expected metrics may include:

- **Estimated** quality and acceptance probability against the task's DoD.
- **Estimated** degree of agent autonomy and engineer preparation/steering/review/correction effort.
- **Estimated** AI/tooling cost and labor-value potential relative to an explicit task baseline, labor-rate assumption and expected acceptance probability.
- Confidence/uncertainty, assumptions, supporting literature and the reasoning used to infer each metric.
- Explicit immutable provenance links to the Watch Entries and underlying sources.

Estimated scores may be entered manually or, in later increments, derived through documented AI-assisted synthesis. The system must **not fabricate precision or silently equate a literature benchmark with an internal task-specific observation**. If necessary assumptions are missing, an economic metric should be marked unavailable rather than treated as zero.

A theoretical candidate has an independent lifecycle:

**Draft → Staged → Reviewed → Published (THEORETICAL)**

Draft is editable. Staging makes it available in **internal comparisons** without publication. Review documents the reasoning and evidence. Publication is an explicit workgroup decision, **not a claim of experimental qualification**; published forecasts must remain clearly labeled theoretical. Material changes invalidate the previous review and require a new staging/review cycle. Published forecasts must retain versioned history.


#### Visibility, traceability and lightweight authoring

A Watch Entry is initially **internal / Draft** until explicitly published. It is distinct from any Model, Provider or Harness item; the workgroup should not be forced into the catalog after creating a hypothesis. Each entry should accept multiple sources within its initial form.

A forecast may explicitly register an otherwise missing model/provider/harness **inline**, labeling those technical records unverified, without interrupting Technology Watch. Source Watch Entries must be published before the forecast itself can be publicly published.

When a theoretical forecast enters **Staged**, snapshot its linked hypotheses, sources, component identities/versions, numerical assumptions and contextual reasoning. Later changes to a source or component catalog item must not silently alter the historical projected claim. Any material forecast modification returns it to Draft and triggers a fresh review. Published forecasts are immutable; further changes create a new revision.

A forecast's illustrative net financial value may be estimated as **engineer-only baseline labor cost − expected assisted cost per accepted result**, using declared assumptions for hourly labor cost and anticipated acceptance probability. Show the formula's assumptions, and do not compute a net value where baseline or acceptance probability is missing. This is an *economic scenario*, never measured ROI.

### Parallel, comparable but non-equivalent evidence

The second input path is still:

**Task → Test Case (with fork lineage where applicable) → Controlled benchmark run → Measured AI Solution → qualification/recommendation**

Task-centric discovery and the Results Explorer must support **side-by-side comparisons of forecasts and experimentally tested solutions**. The presentation must distinguish estimated versus observed metrics and display source type, evidence coverage/sample count, confidence and comparable task scope. In particular, expected quality/acceptance/cost/time must never be rendered as observed benchmark means, even if the forecast has been published.

A staged theoretical configuration can later seed a **new prepopulated Benchmark Campaign** in the Benchmark Workspace. The campaign then follows guided Test Case setup, timed interactions, outcome recording, closure and peer review. The resulting run pins a **snapshot of the original forecast** and creates or reuses the measured solution identity; the source forecast remains intact. Any difference between predicted and observed results can then be audited instead of rewriting the past prediction.

The Technology Watch screen owns evidence collection and forecast staging/review. The Benchmark Workspace owns controlled experiment planning and execution, and qualification decisions for measured solutions. The daily dashboard remains a read-only progress overview.

Feedback and controlled benchmark evidence must be distinguished, though both can motivate updates.

## 13. Engineer experience and feedback loop

Engineers should be able to:

- Navigate the hierarchical task tree at any level.
- Search a task by category, specialty, or free text.
- Discover accessible solutions and separately inspect inaccessible candidates.
- Filter, sort, and compare solutions for a task.
- Read configuration instructions, recommended practices, charters, training, and FAQs.
- See what has changed through a news feed (new solutions, experiments, results, recommendations, or guides).
- Submit qualitative feedback on real usage.
- Suggest tasks, tools, new needs, missing documentation, or further evaluation.

**Centralized user feedback and ideas register:** this is a library of experiences, problems, suggestions and needs **submitted by ordinary user accounts**, not a support ticketing or corrective-action tracking system. Workgroup accounts review and discuss those contributions but do not originate end-user feedback. If a workgroup member also needs a separate ordinary-user perspective, that is a distinct user role/account.

### Unified chronological feedback discussion

Every feedback record has **one chronological conversation**. Each attributed, timestamped message declares **visibility = Public or Internal**, and the two classes are displayed together in actual sequence for the workgroup. Public replies are visible to eligible readers; internal workgroup notes are strictly excluded from reader views and exports. A workgroup member chooses the visibility of each response, not a separate discussion tab.

The feedback detail should **not** include a support-ticket disposition, triage status editor, corrective-action fields or evidence attachment management. Feedback remains a source of user insight; any actual corrective actions, experimental plans or engineering tasks are managed in their dedicated workspaces. Historic status attributes can remain for migration but should not drive the feedback interface.

Feedback contributes to a **continuous improvement loop**:

**Benchmark → Publication → Use → Feedback → New evidence or TC → Reassessment**

Field feedback is useful operational evidence but must not be misrepresented as equivalent to a controlled, reproducible benchmark.

## 14. Management and group reporting

Management views should be derived from the same underlying catalog, task hierarchy, and evidence rather than from a separate reporting database of manually re-entered conclusions.

Desired indicators include:

- Coverage by activity, specialty, V-cycle phase, and other engineering views.
- Number and maturity of evaluated tasks/solutions, with uncovered high-value needs.
- Adoption and active use of recommended tools, where legitimate usage information is available.
- Human effort saved, acceptance outcomes, quality, and cost/value.
- Workgroup throughput: candidates researched, experiments performed, qualifications, publications, guides, reviews.
- Evidence freshness, reliability, and rate of obsolescence.
- Provider/model concentration and potential dependency.
- Feedback volume and themes, including relevant BU attribution.

**Activity metrics are not outcome metrics:** benchmark volume alone does not demonstrate effectiveness or return on investment.

### Auditable Activity Feed and reporting exports

The Activity Feed is an **automatically generated event log**, not a manually updated dashboard. Each newly recorded workgroup activity should preserve exact date/time, actor identity and role, business unit, activity type, originating workspace, a concise description, linked object IDs, and relevant object/revision snapshots or structured context where available. Longer metadata may remain hidden in the default timeline but must be accessible by opening an **Activity Detail** panel for any event.

Support filtering/searching, retain historical revision-before/after data for auditing, and allow exports usable for cross-team reporting (**structured JSON and flat CSV with serialized nested metadata**). Exports must differentiate events from experimental outcome metrics. Internal comments, private watch drafts, restricted records and internal audit snapshots must never be leaked into reader-level exports. Legacy events without enriched fields should remain readable; the prototype is browser-local rather than a tamper-proof centralized audit service.

Adoption analytics should use appropriate aggregate activity/feedback data and **must not require storing engineers' normal AI conversations**.

## 15. Conceptual information model

These are functional entities/relationships, **not a mandated physical database schema**:

| Concept | Function |
| --- | --- |
| Task Node | A stable, editable node in the engineering activity tree, with parent/children and metadata. |
| Test Case | A concrete, versioned experimental challenge linked to a task, optionally a child fork of another Test Case. Not a task-tree level. |
| AI Model / Provider / Harness | Versioned component catalog records defining an individually measured AI configuration. |
| Framework | Catalogued orchestration/process tool, optionally linked to one or more independently configured AI participants within a campaign. |
| Framework Participant | Campaign-scoped, role-labeled model/provider/harness trio, exact version/configuration and stable participant ID. |
| AI Solution | Versioned and uniquely identifiable combination of model, provider, harness, configuration and capabilities, registered from its **first benchmark run**; never merely an untested candidate. |
| Benchmark Run | Either one measured AI Solution × one Test Case, or one composite Framework execution with multiple selected participants × one Test Case. Group metrics are not imputed to individual AI Solutions. |
| Campaign Trial Session | In-progress step-by-step Test Case execution: initial setup, timestamped iterative human/agent interventions, interim artifacts, and eventual accepted/failed outcome. |
| Benchmark Campaign | **Primary workgroup process**: objective, comparison mode, optionally Framework plus participant trios, referenced Setup Guide, fixed task or single setup, linked watch signals, owner, lifecycle, Test Cases and runs, closure and review. |
| Evidence | Inputs, traces, reviews, artifacts, provenance, test results, and cost records from controlled runs. |
| External Research Evidence | Reusable canonical literature/source records with citation, type, confidence, scope and limitations, distinct from internal runs; not owned by just one Watch Entry. |
| Watch-Source Link | Many-to-many references linking shared external sources to Watch Entries without copying their content. |
| Watch Hypothesis | Independent evidence-backed intuition or opportunity with assumptions, reasoning and one-to-many supporting sources. |
| Theoretical Forecast | Task-specific candidate model/provider/harness/configuration, expected (not observed) metrics, risk, economic assumptions, linked watch hypotheses and distinct staging/review/publication state. |
| Forecast Validation Link | Reference from a controlled run to the immutable forecast snapshot whose configuration motivated the experiment. |
| Qualification | Workgroup-owned operational process with assigned owner, stage, task/candidate selection, experiments, review and publication decision. |
| Feedback Message | Timestamped, attributed entry within one chronological feedback conversation, labeled Public or Internal on each message. |
| Activity Event | Automatically generated, attributed workgroup event with exact timestamp, BU, role, workspace, object references, structured details and linked change revisions for reporting. |
| Evaluation | Interpreted results, metrics, aggregation, and versioned scoring method. |
| Recommendation | Published, attributable, evidence-linked conclusion and guidance on a solution. |
| Charter / Guide | Cross-cutting usage policy, training, FAQ, setup, or instructional content. |
| Feedback / Idea | A user's experience, proposed need, or improvement request. |
| User / BU | Identity, publication permissions, and optional organizational provenance. |

Core relationship:

**Technology Watch hypotheses + literature → Theoretical Forecast (task + components + assumptions) → Staging → Review → Optional theoretical publication**

**Component catalog (Model / Provider / Harness) → Single configured participant → Individual Run → Measured AI Solution → Evaluation → Recommendation; Framework + multiple participants → Composite Run → Joint workflow outcome (separate from individual AI Solution scores)**

**Theoretical forecast ↔ Controlled benchmark run (optional validation, immutable original prediction)**

**Task hierarchy → Task ↔ Test Cases ↔ Benchmark Runs ↔ AI Solutions**

Qualification may begin from one or more component candidates, before the AI Solution exists; the first run establishes and links the solution identity.

The benchmark results can be explored in either direction: **from task to solutions** or **from solution to tasks**.

## 16. Non-functional requirements — separate specification

Platform quality, interaction consistency, usability, accessibility, traceability, auditability, security, interoperability and maintainability are specified in the dedicated **[Non-Functional Requirements](non-functional-requirements.md)** document.

The Product Definition remains authoritative for **functional scope and workgroup workflows**. Cross-cutting UI interaction rules, such as preventing backdrop dismissal of forms (**NFR-UX-001**), are maintained and verified in the non-functional specification rather than repeated in individual functional sections.

## 17. Delivery scope and progressive automation

### Initial product / MVP

Prioritize the **correct knowledge and experimental model** before advanced dashboards or large-scale automation:

- Independent workgroup catalogs of **models, providers and harnesses**, including inaccessible and as-yet untested candidates; AI Solutions appear after the first recorded benchmark run.
- Editable engineering task hierarchy and transversal properties.
- Test Case definitions and traceable fork/version lineage.
- Manual benchmark runs with measurable results and complete evidence attachments.
- Solution-centric and task-centric exploration/comparison.
- Traceable evaluations and published recommendations.
- Simple drafting/publication controls and user-facing documentation.
- Ability to receive engineer feedback in **one chronological thread**, with public/internal visibility per message and workgroup-only reply permissions.
- Role-specific workgroup navigation with a read-only daily dashboard and clearly separated **Technology watch, Technology catalog, Test design, Benchmark workspace and Results explorer**.
- Search/filter/sort and update existing knowledge articles.
- Sourced, clearly labeled external research and performance estimates in technology watch, with **searchable reusable citations and many-to-many evidence links**.
- Detailed automatically generated Activity Feed with inspectable per-event metadata and structured JSON/CSV exports.

### Subsequent increments

- Technology-watch and news-feed workflows.
- Rich management dashboards, adoption and cost/value analytics.
- Obsolescence detection and recommendation review support.
- Expanded cross-BU contributions and feedback analysis.

### Longer-term capabilities

- **Automated execution of benchmark experiments wherever feasible.**
- Automatic collection of tokens, cost, timing, test outcomes, logs, and artifacts when integrations support it.
- Integration with engineering systems such as repositories, CI, issue trackers, test environments, and agent harnesses.
- Repeatable campaigns and continuous requalification following new models, releases, or test cases.

Automation is an **evolution of the same Benchmark Run / Evidence model**, not a separate evaluation system. Manual and automated runs should remain comparable when task challenges and recorded execution conditions permit.

## 18. Explicitly open design decisions

The following have **not** been specified or mandated yet:

- Exact scoring algorithms, metric weights, confidence thresholds, aggregation and normalization methods.
- Detailed test-set design requirements and experimental comparability guidance.
- Inheritance and override semantics for task properties, including historical version snapshots.
- Exact qualification maturity labels, feedback triage statuses, and contribution moderation policy.
- Information-density measurement methodology and handling of unreliable external benchmark claims.
- Final UX, page structure and detailed integration architecture. The selected backend/database/deployment baseline and data-governance principles are now specified in [Platform Architecture & Data Governance](platform-architecture-and-data-governance.md); detailed physical schema and operational targets remain open.
- Exact role/identity technical implementation and confidential artifact access policy.
- Instrumentation for adoption measurement, automated benchmarking, and cost capture.
- Detailed retention rules for large or sensitive evidence artifacts.

These decisions should be made incrementally without contradicting the agreed principles above.

---

## Foundational rules

1. **Tasks describe engineering needs; test cases challenge solutions.**
2. **Task taxonomy is an evolving tree; test cases are independent experimental instances.**
3. **One evidence model supports both solution-centric and task-centric benchmarking.**
4. **New test cases can challenge old conclusions without deleting history.**
5. **A solution is more than a model: harness, provider, capabilities and configuration matter.**
6. **Measurements and evidence precede scores; scores must remain explainable.**
7. **Published recommendations are shared globally and explored through properties and filters.**
8. **Official benchmark conversations and artifacts are retained; ordinary end-user conversations are not.**
9. **Humans report approximate effort; total value accounts for human work as well as AI costs.**
10. **The platform starts with structured manual evidence and progressively automates reproducible experiments.**
