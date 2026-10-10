# AI Compass

**Evidence-driven AI solution selection for engineering.**

AI Compass is a shared decision-support platform for discovering, benchmarking, comparing, and recommending AI solutions for R&D and other engineering activities.

It connects an evolving hierarchy of engineering tasks with reproducible test cases, versioned AI configurations, experimental evidence, cost/value metrics, and engineer feedback. The goal is to make recommendations **transparent, auditable, current, and actionable**.

## What it enables

- **Engineers:** Find and compare solutions for their tasks, access configurations and guidance, and submit feedback or new needs.
- **AI workgroup:** Maintain Models, Providers, Harnesses and Frameworks independently; assemble one or more AI participant trios under a Framework; review results and publish measured AI Solutions.
- **Management and other business units:** Track evaluation coverage, adoption, cost/value, and progress using a common knowledge base.

Benchmarking works in both directions: **compare solutions on the same task**, or **evaluate one solution across multiple tasks**. New test cases can continuously challenge earlier results.

## Product definition

Cross-cutting interaction, slider and tooltip rules: **[Non-Functional Requirements](docs/non-functional-requirements.md)**. Guided benchmark procedure: **[Benchmark Workflow](docs/benchmark-workflow.md)**.

See **[Product Definition](docs/product-definition.md)** for the agreed product scope, roles, task hierarchy, benchmarking model, evidence and scoring principles, publishing workflow, and evolution roadmap.

For user-managed Windows/Linux environments and versioned Harness/Framework compatibility (including other-OS alternatives), see **[FUT-06 OS Environment Compatibility](docs/os-environment-compatibility.md)**.\n\nFor explicit enterprise accessibility, source-backed versioned commercial alternatives and pinned Campaign tariffs, see **[FUT-05 Enterprise Pricing](docs/enterprise-pricing.md)**.\n\nFor the navigable five-zone Workgroup Studio, shared knowledge projections and isolated unsaved form drafts, see **[FUT-04 Workgroup Studio](docs/workgroup-studio.md)**.\n\nFor the first shared **Demo/Server Catalog and Task controllers**, role navigation and centralized API handling see **[FUT-03 Shared Workspace Bootstrap](docs/shared-workspace-bootstrap.md)**. This is a foundation, not the complete later role-specific UX.\n\nFor local versus secured LAN server operation, archive export privileges and evidence verification, see **[FUT-02 Deployment and Archive Security](docs/deployment-profiles-and-archive-permissions.md)**. LAN and Internet operational release gates remain separate.

For coordinated, individually identified frontend/backend artifacts, automatic manifest verification, and strict API v1 compatibility, see **[FUT-01 Coordinated Release](docs/coordinated-release.md)**. The release still requires human PLAT-32 operational acceptance (**NO-GO** until approved).

For operational database protection, see the **[Verified Backup & Recovery Runbook](docs/backup-and-recovery.md)** (PLAT-34): automated snapshots, isolated restore drills, integrity reports and retention.

See **[Platform Architecture & Data Governance](docs/platform-architecture-and-data-governance.md)** for the target backend, persistence, immutable revisions, human-readable IDs, migration strategy, evidence storage, backup/recovery, deployment and independent Maintenance & Governance workspace.

See **[Incremental Platform Implementation Roadmap](docs/platform-implementation-roadmap.md)** for the existing PLAT delivery history. The separate **[proposed Future Evolutions Implementation Plan](docs/future-evolutions/implementation-plan.md)** maps all accepted future features into outcome-led phases; it is **not yet an approved development issue plan**.

See **[Non-Functional Requirements](docs/non-functional-requirements.md)** for system-wide interaction and quality rules, including the modal form dismissal policy (**NFR-UX-001**). Forms can only be dismissed through explicit controls, while read-only modals retain backdrop/Escape dismissal.

**Guiding principle:** *Measure and preserve evidence first; derive explainable recommendations from it.*

For the benchmarker's guided campaign workflow, see **[Benchmark Campaign Workflow](docs/benchmark-workflow.md)**.

## Runtime modes: permanent Demo and Server alternatives

AI Compass intentionally maintains **two independent data modes using the same frontend**:

- **Demo (standalone):** seeded fictitious records and simulated accounts persisted in browser `localStorage`. No Django, Docker or DB is required; this mode remains supported permanently.
- **Server (progressively implemented):** starts with an **empty business database** (only required technical schemas/roles/accounts are initialized); real shared data is created by users via Django Ninja/PostgreSQL and will later be imported deliberately from external real-world sources **after production deployment validation**.

The Models interface now uses a shared `LocalStorageDataProvider` (Demo) or authenticated `ApiDataProvider` (Server), with the same Models card UI; other domains will adopt this pattern as their APIs arrive. Demo and Server never silently mix data or fall back to one another. **Fake Demo fixtures are never imported into Server.** The cancelled [PLAT-04](https://github.com/aradenac/AI-Compass/issues/4) is no longer a prerequisite; real external-source onboarding is deferred to [PLAT-33](https://github.com/aradenac/AI-Compass/issues/33) after Server production validation. **PLAT-01–03 provide the persistent stack, identity and versioned Model API; PLAT-05 connects the graphical Models screen in Server mode. Providers, Harnesses, Frameworks, tasks, campaigns and other modules await their own Server integrations.**

See **[Local Installation & Deployment](docs/local-installation.md)** for setup and Server login, **[Model Catalog Architecture & API](docs/model-catalog-architecture.md)** for the versioned Model API, and [Platform Architecture](docs/platform-architecture-and-data-governance.md).

### First real Model in Server mode

Start the Docker stack and create a Django Contributor as described in [Local Installation](docs/local-installation.md). Open **http://127.0.0.1:8080/prototype.html?mode=server**, sign in, and select **+ Add** in the Models lane. Save, then open the same page in another authenticated browser to confirm the Model is shared. **Edit** appends r002; **History** shows r001 and later revisions without rewriting them. View-only roles can list/history but cannot mutate. Backend/CSRF/permission errors show explicitly and never switch to Demo data.

The same visual Models lane remains operational in `?mode=demo` with independent fictional browser data. **No Model, ID or fixture is transferred between runtimes.** For JavaScript adapter tests, run `node scripts/test-model-catalog.js` (no npm install).

## Interactive prototype

**[Open the standalone prototype source](prototype.html)** · Single self-contained HTML file (vanilla CSS/JavaScript; no build system, backend, or external dependencies).

To run it reliably with browser-local persistence, clone or download the repository and serve its root directory:

```bash
python3 -m http.server 8090 --bind 127.0.0.1
# Demo only: open http://127.0.0.1:8090/prototype.html
```

The app uses **localStorage** for records and the selected demo account. Changes survive page reloads in the same browser/origin. **Export data JSON** saves the records visible to the current role; workgroup accounts can export/import the full dataset for sharing test scenarios. **Reset demo dataset** restores the initial mock records. Other devices, browsers, or origins do not share data automatically.

### Mock accounts — choose one on the login screen

| Test user | Simulated role | Suggested journey |
| --- | --- | --- |
| Maya Laurent | AI workgroup · Embedded Systems | Create task nodes, fork/versioned TCs and runs; inspect evidence; publish and triage feedback. |
| Sofia Ramos | AI workgroup · Digital Solutions | Contribute benchmarks from another BU to the same shared dataset. |
| Nicolas Bernard | Engineer · Embedded Systems | Navigate tasks, compare solutions, read guides, and submit field feedback or needs. |
| Lena Martin | R&D Management | Assess V-cycle/task coverage, adoption, potential value, and workgroup throughput. |
| Amir Haddad | Group reader · Group Innovation | Explore shared published knowledge and submit cross-BU needs. |

No passwords are required. **Identity and permissions are simulated in the browser; this is not an authentication or security implementation.**

### Catalog components → Benchmark → AI Solution

The workgroup **Technology catalog** contains four independent inventories: **Models**, **Providers**, **Harnesses**, and **Frameworks**, including accessible, inaccessible and unbenchmarked candidates. Manage versions, lifecycle and notes in each inventory; do not preregister a solution merely because its components exist.

In **Benchmark workspace**, create a campaign, choose the fixed setup (or the Framework participants), then open the campaign and execute a Test Case. Without a Framework, choose a model/provider/harness combination for the run. That first run creates a **measured AI Solution** with a stable identifier and evidence snapshots. Theoretical configurations may exist earlier as **Forecasts**, but have no observed runs. Repeating the same combination/version/settings **reuses** the solution; changing the configuration creates a **distinct** solution. An unsuccessful run still identifies the tested configuration, but does not qualify or recommend it. Alternatively, choose **Repeat / compare an already benchmarked solution**.

An AI Solution is not automatically visible to engineers: its recommendation and publication remain controlled by the workgroup's review process. Legacy seeded benchmark records remain intact.

### Framework participants and setup references

A **Framework** organizes a workflow; it does not substitute for any of the three components that define a measured AI Solution. During campaign creation, select a Framework and add as many labeled participant trios as required. Participants retain independent roles, exact model/provider/harness references, versioned configuration and capability notes. Each guided Test Case execution can measure **one selected participant** (a single AI Solution) or a **collaborative Framework workflow with two or more participants**. The latter produces a **composite benchmark run** with group-level quality, utility, cost and runtime, explicit participant references and optional per-interaction actor labels. Collective results are not counted as individual AI Solution scores. The browser prototype records these observations but does not orchestrate real AI agents.

A Setup Guide is always a knowledge-base record with its own ID. The user may select an existing guide or create one directly from campaign planning or the installation step, supplying **text only**, **URL only**, or **both**. Guide references are reusable and the selected snapshot is retained in run evidence. Prefer HTTP(S) URLs to maintained instructions.

## Workgroup information architecture (current prototype)

Sign in as **Maya Laurent** or **Sofia Ramos**. The workgroup has its own sidebar, organized by actual responsibilities rather than the standard user-oriented `Discover / Evaluate / Collaborate` categories.

| Group | Screen | Purpose |
| --- | --- | --- |
| Workspace | **Dashboard** | Daily read-only **campaign pipeline** (Planned, In progress, Under review, Published), recent user feedback and watch signals. |
| Workspace | **Task management** | Edit/reparent/reorder the taxonomy in-place, and inspect its engineer-facing view. |
| Technology intelligence | **Technology watch** | Create evidence-backed watch hypotheses and task-linked theoretical forecasts with staging and review. |
| Technology intelligence | **Technology catalog** | Maintain models, providers, harnesses and frameworks independently; no benchmark launch button. |
| Experiments | **Test design** | Define Test Cases and navigate task-grouped parent/fork trees. Forking assigns collision-free child versions. No protocol tab or protocol selector. |
| Experiments | **Benchmark workspace** | **Campaign-centric** guided process: create/edit a campaign, link any number of technology-watch signals, choose a comparison mode, add Test Cases, record timed iterations and outcomes, close for review, publish or reopen. |
| Experiments | **Results explorer** | Compare theoretical predictions against measured runs with separate evidence labels, plus inspect benchmark matrices. |
| Knowledge & Collaboration | **Recommendations** | Maintain evidence-linked published decisions and guidance. |
| Knowledge & collaboration | **Guides & charter** | Search, sort, filter and edit existing articles, plus create and publish new ones. |
| Knowledge & collaboration | **Feedback & discussions** | Review user-submitted ideas and experiences in a single chronological thread with public/internal visibility per reply; no action-tracking disposition. |
| Knowledge & collaboration | **Activity feed** | Automatically attributed, searchable activity records with per-event detail, revision provenance and JSON/CSV reporting exports. |
| Reporting | **Management view** | Remains unchanged for this iteration. |

### Workgroup daily dashboard

The **Dashboard** now shows the four **campaign states**: **Planned → In progress → Under review → Published**. The board is read-only and intended for a daily workgroup meeting. Every card summarizes the campaign objective, mode, owner, included Test Cases and completed runs. Changes happen only in **Benchmark workspace**. Recent user feedback and technology-watch signals remain visible below.

### Guided benchmark campaign workflow

The **campaign is the workgroup's primary unit of experimental work and review**. A controlled run remains the atomic unit of evidence, and Test Cases remain reusable independent challenges.

1. **Create campaign:** specify name, qualification goal, owner, comments, **zero or more linked technological signals**, and an optional catalogued **Setup Guide**. Optionally select a **Framework** (n8n, GitHub Spec Kit, BMAD Method; the PMAD example is unverified) and instantiate one or more separately configured Model/Provider/Harness trios. Choose **Solution-centred** (one fixed model + provider + harness + configuration across Test Cases and potentially multiple tasks) or **Task-centred** (one fixed engineering task, multiple AI configurations compared on the task's Test Cases).
2. **Open the campaign:** a new campaign starts in **Planned**. Open it to begin execution. The campaign can later be closed, reopened or edited. A configuration is defined using already declared catalog components; a newly measured AI Solution is registered after its first run.
3. **Add challenges:** create Test Cases directly inside the campaign (task, inputs, constraints, DoD) or attach existing reusable Test Cases. No separate benchmark protocol is required. Task-centred campaigns restrict cases to the fixed task; solution-centred campaigns accept tasks across the taxonomy.
4. **Execute each Test Case via guided forms:**
   - **Installation & setup (Step 3):** select an existing **Installation guide** from Guides & Charter or create a reusable guide inline, optionally linked to the AI Solution. Record environment, install/start timestamp and **human installation duration** (0–7 days). Prompts are not part of installation.
   - **Timed interactions (Step 4):** the **first prompt** is logged as the first interaction. Subsequent prompts, input documents, skills/options, reviews, corrections and intermediate artifacts have their own timestamps, human duration and agent duration. Agent runtime is summed automatically.
   - **Results, artifacts & metrics (Step 5):** DoD accepted/failed; **Quality** and **Information Utility** sliders with numeric entry and narrative evaluation; **optional total tokens**, with 1/10/100/1,000/1,000,000 multiplier; cost mode **EUR amount / flat subscription / unknown**; final review/correction durations; one list of final **Produced outputs**, then **Additional notes (optional)**. Unknown values are not recorded as zero.
   - **Close Test Case:** store referenced guide snapshot, all timed interactions, calculated runtime, known/unknown metrics and output evidence; accepted and failed runs remain auditable.
5. **Close campaign → Under review:** the **campaign author or another workgroup member** may review and publish or request rework. A published campaign may be **unpublished to review**, or reopened for further experiments; historical evidence remains retained.
6. **Reopen when needed:** even a published or under-review campaign can return to **In progress** for additional Test Cases and runs. Previously published run evidence is preserved. Edit campaign goals/notes, archive an evidence-bearing campaign without deleting its audit history, or remove an empty campaign.

An uncompleted Test Case session can be **resumed from the campaign**. Sessions and campaign states persist in browser `localStorage`; no live AI agent, timer daemon, upload endpoint or real benchmarking service is executed. Timestamps/durations and file paths are manually declared, and all starting values are simulated.

**Test with Maya Laurent (campaign author/reviewer) or Sofia Ramos (another reviewer):** Create → Open → Add a Test Case → Save setup → Add two interactions at different times → Record a failed or accepted result → Close → Switch workgroup account → Review & publish → Reopen and inspect preserved runs.

### Technology Watch: evidence-backed forecasts

A Watch Entry now supports both selecting citations from the existing evidence library and registering new references, rather than requiring repeated literature entry.

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

**Test design** manages reusable, versioned Test Cases and a task-grouped parent/fork hierarchy. **Guides & Charter** registers install/setup references as procedure text, an HTTP(S) URL, or both; a campaign selects an existing reference or creates one inline. **Benchmark workspace** owns qualification planning, configurations, execution records, draft-run review and publication. **Results explorer** owns comparison and analytical reading, including the shared TC evidence matrix. These roles are separated deliberately rather than provided as flat tabs of one `Benchmark lab`.

Try the evidence-first path **Technology Watch → sources → theoretical forecast → stage/review → Results explorer**, or the controlled path **Test design → Benchmark workspace → benchmark run → measured AI Solution**. Existing run snapshots and revision history remain intact.

### Feedback discussions, source reuse and audit reporting

**Technology Watch sources:** `+ Watch entry` offers a searchable **shared reference library** where several existing citations can be selected. An optional collapsed `Register a new source` section allows new literature references, with multiple new citations when needed. Duplicate reference identifiers/URLs are reused rather than creating a second record. The reference-to-watch relationship is **many-to-many**: one paper/benchmark may underpin several hypotheses, and one hypothesis may cite many sources. Historical Watch Entry links are migrated into this relationship model without losing existing records. Deselecting a source on edit unlinks it from that hypothesis without deleting the shared reference.

**Feedback & discussions:** feedbacks are **submitted by regular users**, not workgroup accounts. Workgroup members read them and converse in a **single timestamp-ordered thread**, combining public replies and clearly marked internal workgroup notes. Reader views and public exports hide internal messages. The former workgroup disposition/status editor and artificial links to corrective action/evidence were removed: tracking fixes belongs to other engineering workflows, not this contribution discussion.

**Activity Feed:** every new automatic event records timestamp, identity/role, business unit, category, workspace, short summary, linked objects (with snapshots when available), and associated change revisions. The visible feed is concise and searchable by type, contributor or text. Clicking **Details** opens its full event metadata, including revision history. Workgroup members can export a detailed **JSON** or **CSV** reporting file. The full local dataset export also retains enriched activity records. Older imported events with fewer fields remain readable. No server-side reporting service is used in this prototype.

In **Guides & charter**, workgroup members can search, filter, sort, edit and publish existing articles. Changes remain traceable in the Activity Feed.

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
3. **Maya:** Open **Test design** to create a Test Case, then fork it twice. Observe distinct child versions (for example, 1.0.1 and 1.0.2) in the hierarchy.
4. **Maya:** Open **Benchmark workspace**, create a campaign in one of the two modes, open it, define Test Cases, and follow guided setup → interactions → result steps.
5. **Maya:** Close the campaign for independent peer review, then switch to Sofia Ramos to approve publication or request rework.
6. **Maya:** Open **Results explorer → Measured vs theoretical** to compare staged theoretical forecasts and benchmarked configurations with explicit provenance.
7. **Maya:** In **Feedback & discussions**, write an internal note and a public response in the same chronological conversation; inspect the visibility badges and test reader access.
8. **Maya:** Open **Activity Feed**, inspect an event detail and export detailed JSON/CSV. Then edit an article in **Guides & charter** and inspect its revision history.
9. **Nicolas (engineer):** Switch account; verify only the public feedback conversation and published documents are visible. Management view remains a separate, largely unchanged perspective.

Runs retain a **snapshot of their Test Case and AI solution**, together with the campaign's linked technological signals, as created, so later changes do not rewrite the historical experimental setup. Recommendation and catalog edits are tracked in prototype revision records.

> **Prototype limitations:** Demo data, accounts, scores, costs, adoption figures, artifacts and transcripts are synthetic. Evidence filenames are illustrative text, not real uploaded files. Local role guards can be bypassed by someone with browser developer tools; confidential material must not be entered. No real AI model calls, automated execution, centralized multi-user synchronization or production authentication exist yet.
