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

In **Benchmark workspace → Record benchmark run**, choose **Assemble a new configuration**, select the three components, specify the complete configuration and record the run. That first run creates an AI Solution with a stable identifier and evidence snapshots. Repeating the same combination/version/settings **reuses** the solution; changing the configuration creates a **distinct** solution. An unsuccessful run still identifies the tested configuration, but does not qualify or recommend it. Alternatively, choose **Repeat / compare an already benchmarked solution**.

An AI Solution is not automatically visible to engineers: its recommendation and publication remain controlled by the workgroup's review process. Legacy seeded benchmark records remain intact.

### Workgroup information architecture (current prototype)

Sign in as **Maya Laurent** or **Sofia Ramos**. The workgroup has its own sidebar, organized by actual responsibilities rather than the standard user-oriented `Discover / Evaluate / Collaborate` categories.

| Group | Screen | Purpose |
| --- | --- | --- |
| Workspace | **Dashboard** | Daily read-only qualification pipeline; latest user feedback and technology-watch signals. No KPIs or transition/add buttons. |
| Workspace | **Task management** | Edit/reparent/reorder the taxonomy in-place, and inspect its engineer-facing view. |
| Technology intelligence | **Technology watch** | Capture and review signals, create/link independent catalog components, record external literature and estimates. |
| Technology intelligence | **Technology catalog** | Maintain models, providers and harnesses independently; no benchmark launch button. |
| Experiments | **Test design** | Define Test Cases and benchmark protocols. No result-interpretation workflow mixed into this screen. |
| Experiments | **Benchmark workspace** | Start/continue qualification processes, create campaigns and runs, review drafts, publish evidence and conclusions. |
| Experiments | **Results explorer** | Inspect published runs, task-versus-solution matrix and campaign evidence without editing the experimental process. |
| Experiments | **Recommendations** | Maintain evidence-linked published decisions and guidance. |
| Knowledge & collaboration | **Guides & charter** | Search, sort, filter and edit existing articles, plus create and publish new ones. |
| Knowledge & collaboration | **Feedback & discussions** | Triage contributions and respond in separate public and private workgroup threads. |
| Knowledge & collaboration | **Activity feed** | Continue using the existing activity and revision history. |
| Reporting | **Management view** | Remains unchanged for this iteration. |

### Workgroup daily dashboard

The **Dashboard is observational**, suitable for a daily meeting. It displays the four qualification stages (**To qualify → Qualifying → Review → Published**) as a **read-only board** with ownership, dates and evidence counts, plus recent feedback and watch signals. The four previous KPI cards and **Add to Pipeline** button have been removed. Viewing a card opens a read-only snapshot; modifications and decisions belong to **Benchmark workspace**.

### Technology Watch: collection before qualification

Technology Watch is an information-gathering and screening workflow, **not** a start-qualification shortcut:

1. Record a new announcement, model, provider, harness, technical publication or market signal using **Watch entry**.
2. Add or link a **Model / Provider / Harness** item to the independent **Technology catalog** (the item may remain inaccessible or untested).
3. Register public benchmarks, scientific publications, provider claims or workgroup performance estimates, documenting source, provenance, confidence, assumptions and limitations. These are **not** presented as internally reproduced benchmark runs.
4. Later, from **Benchmark workspace**, select relevant components and launch controlled tests or formal qualification.

### Benchmark process vs. result exploration vs. test design

**Test design** manages reusable, versioned Test Cases and protocols. **Benchmark workspace** owns qualification planning, configurations, execution records, draft-run review and publication. **Results explorer** owns comparison and analytical reading, including the shared TC evidence matrix. These roles are separated deliberately rather than provided as flat tabs of one `Benchmark lab`.

Try the workgroup journey: **Technology Watch → Technology Catalog → record external evidence → Test design → Benchmark workspace → first run creates an AI Solution → Review → Publish → Results explorer**. Existing run snapshots and revision history remain intact.

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
2. **Maya:** Open **Technology Watch** to register a signal, add it to **Technology catalog**, and record an independently sourced estimate.
3. **Maya:** Open **Test design** to create a TC and a versioned protocol.
4. **Maya:** Open **Benchmark workspace** to create a qualification, select components, record a run and inspect its evidence.
5. **Maya:** Continue the qualification to **Review** and publish a reasoned conclusion when controlled evidence is available.
6. **Maya:** Open **Results explorer** to compare published results independently of their workflow status.
7. **Maya:** In **Feedback & discussions**, post an internal note and then a public response; inspect those conversations after reloading the page.
8. **Maya:** In **Guides & charter**, filter articles, edit an existing guide and verify its revision in **Activity feed**.
9. **Nicolas (engineer):** Switch account; verify only the public feedback conversation and published documents are visible. Management view remains a separate, largely unchanged perspective.

Runs retain a **snapshot of their test case, protocol, and solution** as created, so later changes do not rewrite the historical experimental setup. Recommendation and catalog edits are tracked in prototype revision records.

> **Prototype limitations:** Demo data, accounts, scores, costs, adoption figures, artifacts and transcripts are synthetic. Evidence filenames are illustrative text, not real uploaded files. Local role guards can be bypassed by someone with browser developer tools; confidential material must not be entered. No real AI model calls, automated execution, centralized multi-user synchronization or production authentication exist yet.
