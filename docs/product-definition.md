# AI Compass — Product Definition

> **Status:** Agreed functional baseline  
> **Date:** 2026-10-08  
> **Scope:** Internal web platform, extensible across business units (BUs)  
> **Purpose of this document:** Record product decisions agreed during initial scoping. It describes *what* the platform must achieve, not a frozen UI, technology stack, database schema, or scoring algorithm.

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
| AI workgroup | Define tasks, solutions, protocols and test cases; maintain technology-watch candidates; stage and compare unpublished evaluations; execute and challenge benchmarks; preserve evidence; publish results, recommendations, guides, and updates; handle feedback; re-evaluate obsolete advice. |
| Management / Group | Track engineering/V-cycle coverage, progress, adoption, operational outcomes, cost/value, and workgroup activity; identify uncovered needs and investment priorities. |
| Other BUs | Access the same published knowledge and contribute experimental evidence and feedback, subject to publication permissions. |

The platform serves both **operational discovery** (the engineer needs an answer) and **experimental inquiry** (the workgroup needs defensible evidence).

## 3. Access, publication, and organizational scope

These are agreed decisions:

- **Published information is readable by everyone with access to the platform.** “Public in reading” means shared visibility within the intended platform audience; it does **not** imply that confidential R&D content is published on the open Internet.
- **Official publication requires authentication and workgroup membership.** A single authorized workgroup member may qualify and publish a recommendation; mandatory two-reviewer approval or consensus is not required.
- Drafts and staging materials may remain unpublished until a workgroup member publishes them.
- Engineers can submit feedback, requests, or proposals without directly modifying official benchmark conclusions or recommendations. Contributions are handled separately from official publications.
- Results form **one shared knowledge base** across BUs. BUs do not have separate recommendation universes or result silos.
- User accounts can identify BU affiliation and contribution provenance. Access rules may use these attributes where needed.
- The platform should support roles/permissions and an audit history of published changes.

Exact identity-provider/SSO implementation and finer-grained access policies remain technical design choices.

## 4. Catalog and definition of an AI solution

The **workgroup catalog is organized primarily around three independent, reusable component types: AI Models, Providers, and Harnesses**. Members maintain each item's version, capabilities, availability, lifecycle and provenance. These catalog candidates exist **before** they are combined or benchmarked; they are **not** themselves AI Solutions.

**An AI Solution is registered as the outcome of the first benchmark run of a specific assembled setup.** During benchmark preparation, a workgroup member selects one model, one provider, one harness, and the complete versioned configuration (prompts, parameters, tools, skills, etc.). Once that setup has a recorded run — including a failed or unpublished run — it becomes an identifiable AI Solution linked to its evidence. The same exact configuration can be reused across tasks, TCs and runs; materially changed components or configurations produce a distinct solution.

This is a **creation and identity rule**, not a qualification decision: the new AI Solution remains experimental and unpublished until explicitly reviewed and published. Candidates can stay in the catalog or technology-watch pipeline without ever generating an AI Solution.

An **AI Solution** is the concrete, reproducible combination of:

- **Model:** model name and exact version/revision where available.
- **Provider:** service/API or deployment delivering the model.
- **Harness:** agent or interaction environment (CLI, IDE, web, orchestrator, etc.).
- **Configuration:** parameters, prompts, system instructions, tools, skills, permissions, routing, and other relevant settings.
- **Capabilities:** agentic tools such as web search, filesystem, shell, MCP integrations, document formats, vision, and other supported functions.
- **Versions and dependencies:** information necessary to interpret and, when possible, recreate the evaluated setup.

The same model under different providers, harnesses, or configurations can constitute distinct AI solutions and yield different results.

Component candidates and resulting AI Solutions may be **accessible or inaccessible** to enterprise users. Accessibility is a visible/filterable property, not an exclusion rule. Untested candidates remain discoverable in the independent component catalogs and technology watch; only recorded benchmark combinations appear in the AI Solution discovery view.

Technology-watch records may refer to individual components without inventing a future combined solution.

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
- Any TC-specific settings or deviations from the common protocol.
- Its version and evolution history.

**New TCs can be added at any time specifically to challenge, invalidate, or strengthen earlier conclusions.** They expand experimental coverage; they do not replace earlier results.

The system must distinguish:

- **New TC:** a new experimental challenge or coverage dimension.
- **New run of an existing TC:** a repeat under documented conditions to observe variability, reliability, or changes over time.

There is no mandatory quota of TCs per task. A task can start with one and accumulate more.

## 7. Two complementary benchmarking directions

Both of the following are first-class workflows based on **the same underlying experimental records**:

### A. Solution-centric evaluation

Select an AI solution and evaluate it on TCs associated with **multiple tasks**, to determine its strengths, limitations, versatility, and applicable engineering scope.

Question: **What can this solution do effectively?**

### B. Task-centric comparison

Select a task and run **multiple AI solutions against shared TCs**, to compare their results under comparable conditions.

Question: **Which solution is most appropriate for this task?**

These are alternative views over a task × test-case × AI-solution result space; they must not become incompatible benchmark systems.

A **Benchmark Campaign** may group a deliberate collection of runs (e.g., “qualify model X” or “compare five solutions on driver development”). This is an organizational convenience, not a second source of measurement truth.

## 8. Benchmark protocol, run, and evidence

### Benchmark Protocol

A protocol describes **how an evaluation is conducted** and defines comparison invariants where applicable:

- Experimental objective and relevant task/TC.
- Setup and preparation; input context and permissible resources.
- Scope of agent autonomy (manual, semi-autonomous, autonomous).
- Interaction, interruption, re-prompting, and intervention rules.
- Required deliverables and DoD, including pass/fail requirements and graded criteria.
- Measurement instructions, evaluation rubric, and applicable cost assumptions.
- Repetition requirements where useful.

A common protocol helps compare solutions fairly; variations must be recorded.

### Benchmark Run

A run is one execution of **one fully specified combined setup on one TC**, using a specified protocol/version. For a setup without existing evidence, the run **creates its AI Solution identity** and stores the component references, their versions, the complete configuration, and experimental snapshots. For subsequent runs, the existing exact solution may be reused. Multiple runs of the same pairing are allowed and useful.

A run records:

1. Exact solution/model/provider/harness/configuration versions.
2. Test case, protocol, run date, and relevant environment/input revisions.
3. Initial prompt/instructions and any subsequent interactions.
4. Execution trace, interruptions, re-prompts, failures, and interventions.
5. Produced deliverables and results against acceptance criteria.
6. Human effort, runtime, tokens, monetary costs, and other metrics.
7. Reviewer observations, required corrections, and final acceptance outcome.
8. Supporting files and references (source, diffs, tests, logs, reports).

### Auditability and reproducibility

**Official benchmark experiments must retain prompts, conversations, artifacts, and supporting evidence**, subject to access/security controls for sensitive content.

Each run should provide:

- A **reproducibility package**: the inputs, prompts, versions, configuration, environment, protocol, and dependencies needed to recreate experimental conditions.
- An **evidence package**: traces, outputs, tests, cost records, reviews, corrections, observations, and relevant provenance supporting the reported results.

A reproducible setup does **not** guarantee identical outputs from stochastic AI systems. Repeated runs characterize that variability.

**External evidence is also relevant:** public or third-party benchmarks, research, provider documentation, and other published observations can support technology watch or qualification. The source, publication/retrieval date, tested setup, methodology (where known), and limitations should be recorded. Such references must be labeled separately from controlled internal runs and voluntary field feedback; unsupported vendor claims must not be presented as reproduced results.

**Ordinary engineer usage is different:** the platform does not retain their day-to-day prompts, complete conversations, or artifacts merely because a recommended solution is used. Engineers may nevertheless submit voluntary feedback.

## 9. Metrics: quality, autonomy, information, and economic value

Benchmark results must preserve **raw observations** separately from derived metrics and scoring.

| Dimension | Examples |
| --- | --- |
| Quality and acceptance | Mandatory DoD pass/fail; graded rubric; defects; completeness, maintainability, test outcomes. |
| Human preparation | Time preparing context, files, baseline setup, and initial request. |
| Human steering | Approximate time guiding the solution; interventions, interruptions, iterations, and re-prompts. |
| Human review | Approximate time inspecting, understanding, and verifying deliverables. |
| Human corrections | Approximate additional engineering work required to reach acceptance. |
| Autonomy | Successful independent progression, human intervention demand, failure/escalation patterns. |
| AI resource use | Input/output tokens, model calls, elapsed runtime, tooling/API expenditure. |
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

## 12. Technology watch, staging, publishing, and obsolescence

The workgroup must be able to:

1. Enter and maintain an interesting **individual model, provider or harness** from technology watch, even before access or qualification, without preregistering an AI Solution.
2. Enrich the candidate's metadata and capabilities as information arrives.
3. Start a qualification from component candidates, assemble their configuration in the benchmark workflow, then automatically link the resulting AI Solution to the qualification and its runs.
4. Compare staged candidates with already known solutions.
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

Feedback and controlled benchmark evidence must be distinguished, though both can motivate an update.

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

**Centralized feedback and ideas register:** submissions should be available to the workgroup in one place, with enough structured context to identify the referenced task/solution, classify and search themes, review and triage contributions, track their disposition or follow-up, and link them to resulting experiments, documentation changes, or new test cases. This is a workflow for managing contributions, **not** a requirement to capture ordinary user conversations. Contribution visibility, moderation, and detailed status names remain design choices.

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

Adoption analytics should use appropriate aggregate activity/feedback data and **must not require storing engineers' normal AI conversations**.

## 15. Conceptual information model

These are functional entities/relationships, **not a mandated physical database schema**:

| Concept | Function |
| --- | --- |
| Task Node | A stable, editable node in the engineering activity tree, with parent/children and metadata. |
| Test Case | A concrete, versioned experimental challenge linked to a task. Not a task-tree level. |
| Benchmark Protocol | The versioned method, invariants, acceptance criteria, and measurement rules. |
| AI Model / Provider / Harness | Versioned catalog components. |
| AI Solution | Versioned and uniquely identifiable combination of model, provider, harness, configuration and capabilities, registered from its **first benchmark run**; never merely an untested candidate. |
| Benchmark Run | One solution × one TC × one protocol execution, with conditions and observations. |
| Benchmark Campaign | Optional grouping of runs for an experimental objective. |
| Evidence | Inputs, traces, reviews, artifacts, provenance, test results, and cost records. |
| Evaluation | Interpreted results, metrics, aggregation, and versioned scoring method. |
| Recommendation | Published, attributable, evidence-linked conclusion and guidance on a solution. |
| Charter / Guide | Cross-cutting usage policy, training, FAQ, setup, or instructional content. |
| Feedback / Idea | A user's experience, proposed need, or improvement request. |
| User / BU | Identity, publication permissions, and optional organizational provenance. |

Core relationship:

**Component catalogs (Model / Provider / Harness) → Configured benchmark setup → First Run → AI Solution → Evaluation → Recommendation**

**Task hierarchy → Task ↔ Test Cases ↔ Benchmark Runs ↔ AI Solutions**

Qualification may begin from one or more component candidates, before the AI Solution exists; the first run establishes and links the solution identity.

The benchmark results can be explored in either direction: **from task to solutions** or **from solution to tasks**.

## 16. Non-functional requirements and design constraints

- **Traceability:** conclusions link to their source runs, evidence, review, and scoring model.
- **Versioning and history:** record changes to tasks, TCs, protocols, solutions, scoring, and published guidance.
- **Auditability:** official published recommendations can be reconstructed from recorded evidence and decision rules.
- **Reproducibility:** retain the experimental setup, artifacts, and inputs needed to replay a benchmark where technically possible.
- **Security:** authentication for publishing; access control, data sensitivity labeling, and safe handling of source code and documents.
- **Shared access:** readers can consult published information without needing workgroup permissions.
- **Interoperability:** API and export-friendly, machine-readable data, persistent links and references.
- **Extensibility:** additional BUs, activity taxonomies, providers, harnesses, evaluation methods, and reporting views.
- **Maintainability:** clean separation of catalog, experimental records, scoring, decisions, and documentation.
- **Timeliness:** identify freshness, availability, depreciation/retirement, and the need to requalify recommendations.

## 17. Delivery scope and progressive automation

### Initial product / MVP

Prioritize the **correct knowledge and experimental model** before advanced dashboards or large-scale automation:

- Independent workgroup catalogs of **models, providers and harnesses**, including inaccessible and as-yet untested candidates; AI Solutions appear after the first recorded benchmark run.
- Editable engineering task hierarchy and transversal properties.
- Test-case and benchmark protocol definitions.
- Manual benchmark runs with measurable results and complete evidence attachments.
- Solution-centric and task-centric exploration/comparison.
- Traceable evaluations and published recommendations.
- Simple drafting/publication controls and user-facing documentation.
- Ability to receive engineer feedback.

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

Automation is an **evolution of the same Benchmark Run / Evidence model**, not a separate evaluation system. Manual and automated runs should remain comparable where protocols allow.

## 18. Explicitly open design decisions

The following have **not** been specified or mandated yet:

- Exact scoring algorithms, metric weights, confidence thresholds, aggregation and normalization methods.
- Detailed benchmark protocol templates and test-set design requirements.
- Inheritance and override semantics for task properties, including historical version snapshots.
- Exact qualification maturity labels, feedback triage statuses, and contribution moderation policy.
- Information-density measurement methodology and handling of unreliable external benchmark claims.
- Final UX, page structure, data storage, stack, deployment topology, or integration architecture.
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
