# AI Compass

**Evidence-driven AI solution selection for engineering.**

AI Compass is a shared decision-support platform for discovering, benchmarking, comparing, and recommending AI solutions for R&D and other engineering activities.

It connects an evolving hierarchy of engineering tasks with reproducible test cases, versioned AI configurations, experimental evidence, cost/value metrics, and engineer feedback. The goal is to make recommendations **transparent, auditable, current, and actionable**.

## What it enables

- **Engineers:** Find and compare solutions for their tasks, access configurations and guidance, and submit feedback or new needs.
- **AI workgroup:** Catalog candidates, run and challenge benchmarks, preserve evidence, and publish recommendations.
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

### Workgroup daily dashboard

Sign in as **Maya Laurent** or **Sofia Ramos**. The default **Overview** becomes a workgroup daily/qualification desk rather than the general engineer discovery dashboard. It includes recent user feedback, new technology-watch signals, a four-stage qualification pipeline (**To qualify → Qualifying → Review → Published**), owner/priority/due-date tracking, and pending publication actions.

Try the full operational workflow:

1. From **Latest technology-watch signals** or a user-feedback record, choose **Qualify / Start qualification**; link an AI solution and engineering task, then assign an owner, priority, and due date.
2. Move the qualification from **To qualify** to **Qualifying**. Create a new Test Case if needed and record controlled benchmark runs.
3. Advance to **Review**, inspect published runs and draft a reasoned conclusion.
4. **Publish conclusion** once matching controlled evidence exists. This updates the solution's recommendation and stores a history revision; it does not erase experiments.
5. Use **Requalify** on a published item to open a new cycle while retaining the published decision and prior evidence.

The pipeline describes **workgroup activities**, distinct from solution accessibility, model maturity or raw catalog publication. Everything is browser-local and shared across simulated accounts within one browser.

### In-place task hierarchy organizer

Sign in as **Maya Laurent** or **Sofia Ramos** (workgroup), open **Task explorer** and select **Organize tree**. The existing task taxonomy becomes an editable multi-section board:

- **Drag the ⠿ handle** onto another node to make it a child, or onto the separators to insert it before a sibling. The same action works across root sections; the target areas expand while dragging.
- Use **✎** or select a node to edit its name, engineering phase, domain, description, acceptance criteria, baseline and parent **inline** without leaving Task Explorer.
- Use **＋** to create a child, **+ Root section** to add a main section, and **↑ / ↓** to reorder siblings without dragging.
- Choose **Done organizing** to return to the usual read-only browsing and evidence comparison view.

All changes are persisted in `localStorage`; node IDs remain stable, and prior benchmark snapshots are not rewritten when a node is moved. Moving a node underneath itself or any descendant is forbidden. Changes are tracked in the workgroup's revision history. Other roles can browse the tree but cannot reorganize it.

### Exercise the complete workflow

1. **Engineer:** Task explorer → KSZ8851SNL Driver → inspect the DoD, TCs and solution comparison; open evidence or guidance.
2. **Engineer:** Feedback & ideas → submit a new use case, gap, or real-world observation.
3. **Workgroup:** Switch account → triage the feedback → create or fork a Test Case challenging an earlier result.
4. **Workgroup:** Benchmark lab → create a campaign and a controlled run (prompt, interaction trace, artifacts, rubric, human effort, tokens, cost, autonomy).
5. **Workgroup:** Workgroup studio → publish the draft run → revise the recommendation for a solution.
6. **Manager:** Switch account → review consolidated experimental coverage and illustrative cost/value/adoption indicators.
7. **Workgroup:** Catalog components → create models/providers/harnesses → register a configured solution → stage and publish it. Add a protocol revision or create documentation from the corresponding pages.
8. **Workgroup:** Mark an outdated solution as superseded or retired, link its successor and verify that historical benchmark evidence remains inspectable. Inspect change history in the activity feed.

Runs retain a **snapshot of their test case, protocol, and solution** as created, so later changes do not rewrite the historical experimental setup. Recommendation and catalog edits are tracked in prototype revision records.

> **Prototype limitations:** Demo data, accounts, scores, costs, adoption figures, artifacts and transcripts are synthetic. Evidence filenames are illustrative text, not real uploaded files. Local role guards can be bypassed by someone with browser developer tools; confidential material must not be entered. No real AI model calls, automated execution, centralized multi-user synchronization or production authentication exist yet.
