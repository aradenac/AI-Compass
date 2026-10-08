# AI Compass

**Evidence-driven AI solution selection for engineering.**

AI Compass is a shared decision-support platform for discovering, benchmarking, comparing, and recommending AI solutions for R&D and other engineering activities.

It connects an evolving hierarchy of engineering tasks with reproducible test cases, versioned AI configurations, experimental evidence, cost/value metrics, and engineer feedback. The goal is to make recommendations **transparent, auditable, current, and actionable**.

## What it enables

- **Engineers:** Find and compare solutions for their tasks, access configurations and guidance, and submit feedback or new needs.
- **AI workgroup:** Maintain Models, Providers and Harnesses independently; assemble and benchmark configurations; review evidence and publish the resulting AI Solutions.
- **Management and other business units:** Track evaluation coverage, adoption, cost/value, and progress using a common knowledge base.

Benchmarking works in both directions: **compare solutions on the same task**, or **evaluate one solution across multiple tasks**. New test cases can continuously challenge earlier results.

## Product definition

See **[Product Definition](docs/product-definition.md)** for the agreed product scope, roles, task hierarchy, benchmarking model, evidence and scoring principles, publishing workflow, and evolution roadmap.

**Guiding principle:** *Measure and preserve evidence first; derive explainable recommendations from it.*

For the benchmarker's guided campaign workflow, see **[Benchmark Campaign Workflow](docs/benchmark-workflow.md)**.

## Interactive prototype

**[Open the standalone prototype source](prototype.html)** · Single self-contained HTML file (vanilla CSS/JavaScript; no build system, backend, or external dependencies).

To run it reliably with browser-local persistence, clone or download the repository and serve its root directory:

```bash
python3 -m http.server 8080
# Open http://localhost:8080/prototype.html
```

The app uses **localStorage** for records and the selected demo account. Changes survive page reloads in the same browser/origin. **Export data JSON** saves the records visible to the current role; workgroup accounts can export/import the full dataset for sharing test scenarios. **Reset demo dataset** restores the initial mock records. Other devices, browsers, or origins do not share data automatically.

### Mock accounts — choose one on the login screen

| Test user | Simulated role | Suggested journey |
| --- | --- | --- |
| Maya Laurent | AI workgroup · Embedded Systems | Create task nodes, TCs, protocols and runs; inspect evidence; publish and triage feedback. |
| Sofia Ramos | AI workgroup · Digital Solutions | Contribute benchmarks from another BU to the same shared dataset. |
| Nicolas Bernard | Engineer · Embedded Systems | Navigate tasks, compare solutions, read guides, and submit field feedback or needs. |
| Lena Martin | R&D Management | Assess V-cycle/task coverage, adoption, potential value, and workgroup throughput. |
| Amir Haddad | Group reader · Group Innovation | Explore shared published knowledge and submit cross-BU needs. |

No passwords are required. **Identity and permissions are simulated in the browser; this is not an authentication or security implementation.**

### Catalog components → Benchmark → AI Solution

The workgroup **Technology catalog** contains three independent inventories: **Models**, **Providers**, and **Harnesses**, including accessible, inaccessible and unbenchmarked candidates. Manage versions, lifecycle and notes in each inventory; do not preregister a solution merely because its components exist.

In **Benchmark workspace → Record benchmark run**, choose **Assemble a new configuration**, select the three components, specify the complete configuration and record the run. That first run creates a **measured AI Solution** with a stable identifier and evidence snapshots. Theoretical configurations may exist earlier as **Forecasts**, but have no observed runs. Repeating the same combination/version/settings **reuses** the solution; changing the configuration creates a **distinct** solution. An unsuccessful run still identifies the tested configuration, but does not qualify or recommend it. Alternatively, choose **Repeat / compare an already benchmarked solution**.

An AI Solution is not automatically visible to engineers: its recommendation and publication remain controlled by the workgroup's review process. Legacy seeded benchmark records remain intact.

### Workgroup information architecture (current prototype)

Sign in as **Maya Laurent** or **Sofia Ramos**. The workgroup has its own sidebar, organized by actual responsibilities rather than the standard user-oriented `Discover / Evaluate / Collaborate` categories.

| Group | Screen | Purpose |
| --- | --- | --- |
| Workspace | **Dashboard** | Daily read-only **campaign pipeline** (Planned, In progress, Under review, Published), recent user feedback and watch signals. |
| Workspace | **Task management** | Edit/reparent/reorder the taxonomy in-place, and inspect its engineer-facing view. |
| Technology intelligence | **Technology watch** | Create evidence-backed watch hypotheses and task-linked theoretical forecasts with staging and review. |
| Technology intelligence | **Technology catalog** | Maintain models, providers and harnesses independently; no benchmark launch button. |
| Experiments | **Test design** | Define Test Cases and benchmark protocols. No result-interpretation workflow mixed into this screen. |
| Experiments | **Benchmark workspace** | **Campaign-centric** guided process: create/edit a campaign, choose a comparison mode, add Test Cases, record timed iterations and outcomes, close for peer review, publish or reopen. |
| Experiments | **Results explorer** | Compare theoretical predictions against measured runs with separate evidence labels, plus inspect benchmark matrices. |
| Experiments | **Recommendations** | Maintain evidence-linked published decisions and guidance. |
| Knowledge & collaboration | **Guides & charter** | Search, sort, filter and edit existing articles, plus create and publish new ones. |
| Knowledge & collaboration | **Feedback & discussions** | Triage contributions and respond in separate public and private workgroup threads. |
| Knowledge & collaboration | **Activity feed** | Continue using the existing activity and revision history. |
| Reporting | **Management view** | Remains unchanged for this iteration. |

### Workgroup daily dashboard

The **Dashboard** now shows the four **campaign states**: **Planned → In progress → Under review → Published**. The board is read-only and intended for a daily workgroup meeting. Every card summarizes the campaign objective, mode, owner, included Test Cases and completed runs. Changes happen only in **Benchmark workspace**. Recent user feedback and technology-watch signals remain visible below.

### Guided benchmark campaign workflow

The **campaign is the workgroup's primary unit of experimental work and review**. A controlled run remains the atomic unit of evidence, and Test Cases remain reusable independent challenges.

1. **Create campaign:** specify name, qualification goal, owner, comments and experimental strategy. Choose **Solution-centred** (one fixed model + provider + harness + configuration across Test Cases and potentially multiple tasks) or **Task-centred** (one fixed engineering task, multiple AI configurations compared on the task's Test Cases).
2. **Open the campaign:** a new campaign starts in **Planned**. Open it to begin execution. The campaign can later be closed, reopened or edited. A configuration is defined using already declared catalog components; a newly measured AI Solution is registered after its first run.
3. **Add challenges:** create Test Cases directly inside the campaign (task, protocol, inputs, DoD) or attach existing reusable Test Cases. Task-centred campaigns restrict cases to the fixed task; solution-centred campaigns accept tasks across the taxonomy.
4. **Execute each Test Case via guided forms:**
   - **Initial configuration:** dated start, initial prompt, input documents/versions, provided skills, agent configuration, preparation notes and estimated human setup duration.
   - **Timed interactions:** repeatable entries with calendar date/time, human intervention duration, agent/runtime duration, interaction kind, review or corrective action, prompt modifications and intermediate artifacts. Add as many as needed.
   - **Conclusion & metrics:** accepted or failed DoD, scored quality and useful information density, input/output tokens, AI expense, additional machine runtime, final review/correction effort, produced files, outcomes and reasoning.
   - **Close Test Case:** save an auditable benchmark run linked to this campaign, task, Test Case, protocol, component/version snapshots and all recorded interactions. Failures remain evidence. A new Test Case or new solution may be tested next.
5. **Close campaign → Under review:** stages the campaign and its collected runs for other members' review. A different workgroup member (e.g. **Sofia Ramos** for Maya's campaign) documents a review decision. **Publish** shares completed run evidence or **Rework** reopens the campaign.
6. **Reopen when needed:** even a published or under-review campaign can return to **In progress** for additional Test Cases and runs. Previously published run evidence is preserved. Edit campaign goals/notes, archive an evidence-bearing campaign without deleting its audit history, or remove an empty campaign.

An uncompleted Test Case session can be **resumed from the campaign**. Sessions and campaign states persist in browser `localStorage`; no live AI agent, timer daemon, upload endpoint or real benchmarking service is executed. Timestamps/durations and file paths are manually declared, and all starting values are simulated.

**Test this with Maya Laurent (campaign author) and Sofia Ramos (independent reviewer):** Create → Open → Add a Test Case → Save setup → Add two interactions at different times → Record a failed or accepted result → Close → Switch workgroup account → Review & publish → Reopen and inspect preserved runs.

### Technology Watch: evidence-backed forecasts

Workflow: watch hypothesis → theoretical forecast → staged review → comparison with empirical results.

Technology Watch now has an **evidence-first workflow**, separate from controlled benchmarks.

1. **Create Watch Entry:** document the intuition, reasoning, assumptions and expected benefit; attach one or more public sources, each with a citation, claim, confidence and limitations **in the same creation form**. A Watch Entry is not a catalog component.
2. **Build theoretical forecast:** choose an engineering task and a hypothetical model/provider/harness/configuration. Link multiple watch signals. Enter predicted quality, acceptance, autonomy, human effort, AI cost, hourly labor assumption, rationale and uncertainty.
3. **Stage → Reviewed → Published:** forecasts are drafts until explicitly staged. Staged forecasts are available for internal review and comparison. A documented review is required before publication. Publication never turns projected metrics into observed benchmarks.
4. **Task management:** task nodes display linked forecasts separately from their Test Cases and empirical benchmark evidence.
5. **Results explorer → Measured vs theoretical:** compare literature-based projections to published controlled runs. Estimated and observed metrics occupy distinct rows with confidence and evidence counts.
6. **Benchmark Workspace:** choose experimental validation of a staged forecast to create a **prepopulated campaign**, then add task-specific Test Cases and follow the guided setup → timed interactions → outcome process. Completed runs pin the original forecast and link the resulting measured AI Solution.

A forecast may cite several Watch Entries, and one Watch Entry can underpin several configurations. Material edits return a forecast to Draft for re-review. Published projections remain marked **THEORETICAL** and are immutable in the prototype. Nonpublished proposals are visible only to workgroup accounts.

The Technology Catalog stays independent; creating a Watch Entry does not redirect to component management. Source-supported predictions and internal measurements remain distinct evidence classes.

**Optional inline component creation:** If the proposed model, provider or harness is absent, use the expandable fields on the forecast form. Only the explicitly named items are added to Technology Catalog as unverified; creating a Watch Entry still does not create a component automatically.

**Visibility and provenance:** New Watch Entries default to an internal Draft, with an explicit publishable setting. A theoretical forecast can be staged and compared internally, but cannot be published for readers until its supporting Watch Entries have been published. Source citations, linked hypotheses and component versions are frozen when staging, and later experimental runs retain the original forecast snapshot.

**Profitability scenario:** The projected net savings use the engineer-only baseline, a declared hourly rate and an estimated DoD acceptance probability to adjust expected AI/tool and engineer costs. They are not observed ROI and should not imply more confidence than the cited assumptions support.

### Benchmark process vs. result exploration vs. test design

**Test design** manages reusable, versioned Test Cases and protocols. **Benchmark workspace** owns qualification planning, configurations, execution records, draft-run review and publication. **Results explorer** owns comparison and analytical reading, including the shared TC evidence matrix. These roles are separated deliberately rather than provided as flat tabs of one `Benchmark lab`.

Try the evidence-first path **Technology Watch → sources → theoretical forecast → stage/review → Results explorer**, or the controlled path **Test design → Benchmark workspace → benchmark run → measured AI Solution**. Existing run snapshots and revision history remain intact.

### Feedback discussion and article management

Each feedback item supports two **independent chronological threads**: a **public thread** visible to ordinary users and a **workgroup-only internal thread** for analysis and coordination. Replies carry author and timestamp and persist in `localStorage`; the original status/triage information remains available. Internal comments must never be shown to engineers or in their export.

In **Guides & charter**, the workgroup can now search document content, filter by type/publication state, sort by name/date and directly edit existing articles. Article changes remain traceable in Change History.

### In-place task hierarchy organizer

Sign in as **Maya Laurent** or **Sofia Ramos** (workgroup), open **Task explorer** and select **Organize tree**. The existing task taxonomy becomes an editable multi-section board:

- **Drag the ⠿ handle** onto another node to make it a child, or onto the separators to insert it before a sibling. The same action works across root sections; the target areas expand while dragging.
- Use **✎** or select a node to edit its name, engineering phase, domain, description, acceptance criteria, baseline and parent **inline** without leaving Task Explorer.
- Use **＋** to create a child, **+ Root section** to add a main section, and **↑ / ↓** to reorder siblings without dragging.
- Choose **Done organizing** to return to the usual read-only browsing and evidence comparison view.

All changes are persisted in `localStorage`; node IDs remain stable, and prior benchmark snapshots are not rewritten when a node is moved. Moving a node underneath itself or any descendant is forbidden. Changes are tracked in the workgroup's revision history. Other roles can browse the tree but cannot reorganize it.

### Exercise the complete workflow

1. **Maya (workgroup):** Open **Dashboard**, observe qualification statuses and read feedback without manipulating the pipeline there.
2. **Maya:** Open **Technology Watch**, create a Watch Entry with literature sources directly in the form, then derive a task-linked theoretical forecast.
3. **Maya:** Open **Test design** to create a TC and a versioned protocol.
4. **Maya:** Open **Benchmark workspace**, create a campaign in one of the two modes, open it, define Test Cases, and follow guided setup → interactions → result steps.
5. **Maya:** Close the campaign for independent peer review, then switch to Sofia Ramos to approve publication or request rework.
6. **Maya:** Open **Results explorer → Measured vs theoretical** to compare staged theoretical forecasts and benchmarked configurations with explicit provenance.
7. **Maya:** In **Feedback & discussions**, post an internal note and then a public response; inspect those conversations after reloading the page.
8. **Maya:** In **Guides & charter**, filter articles, edit an existing guide and verify its revision in **Activity feed**.
9. **Nicolas (engineer):** Switch account; verify only the public feedback conversation and published documents are visible. Management view remains a separate, largely unchanged perspective.

Runs retain a **snapshot of their test case, protocol, and solution** as created, so later changes do not rewrite the historical experimental setup. Recommendation and catalog edits are tracked in prototype revision records.

> **Prototype limitations:** Demo data, accounts, scores, costs, adoption figures, artifacts and transcripts are synthetic. Evidence filenames are illustrative text, not real uploaded files. Local role guards can be bypassed by someone with browser developer tools; confidential material must not be entered. No real AI model calls, automated execution, centralized multi-user synchronization or production authentication exist yet.
