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

The app uses **localStorage** for records and the selected demo account. Changes survive page reloads in the same browser/origin. **Export data JSON** saves the prototype dataset; **Reset demo dataset** restores the initial mock records. Other devices, browsers, or origins do not share data.

### Mock accounts — choose one on the login screen

| Test user | Simulated role | Suggested journey |
| --- | --- | --- |
| Maya Laurent | AI workgroup · Embedded Systems | Create task nodes, TCs, protocols and runs; inspect evidence; publish and triage feedback. |
| Sofia Ramos | AI workgroup · Digital Solutions | Contribute benchmarks from another BU to the same shared dataset. |
| Nicolas Bernard | Engineer · Embedded Systems | Navigate tasks, compare solutions, read guides, and submit field feedback or needs. |
| Lena Martin | R&D Management | Assess V-cycle/task coverage, adoption, potential value, and workgroup throughput. |
| Amir Haddad | Group reader · Group Innovation | Explore shared published knowledge and submit cross-BU needs. |

No passwords are required. **Identity and permissions are simulated in the browser; this is not an authentication or security implementation.**

### Exercise the complete workflow

1. **Engineer:** Task explorer → KSZ8851SNL Driver → inspect the DoD, TCs and solution comparison; open evidence or guidance.
2. **Engineer:** Feedback & ideas → submit a new use case, gap, or real-world observation.
3. **Workgroup:** Switch account → triage the feedback → create or fork a Test Case challenging an earlier result.
4. **Workgroup:** Benchmark lab → create a campaign and a controlled run (prompt, interaction trace, artifacts, rubric, human effort, tokens, cost, autonomy).
5. **Workgroup:** Workgroup studio → publish the draft run → revise the recommendation for a solution.
6. **Manager:** Switch account → review consolidated experimental coverage and illustrative cost/value/adoption indicators.
7. **Workgroup:** Catalog components → create models/providers/harnesses → register a configured solution → stage and publish it. Add a protocol revision or create documentation from the corresponding pages.

Runs retain a **snapshot of their test case, protocol, and solution** as created, so later changes do not rewrite the historical experimental setup. Recommendation and catalog edits are tracked in prototype revision records.

> **Prototype limitations:** Demo data, accounts, scores, costs, adoption figures, artifacts and transcripts are synthetic. Evidence filenames are illustrative text, not real uploaded files. Local role guards can be bypassed by someone with browser developer tools; confidential material must not be entered. No real AI model calls, automated execution, centralized multi-user synchronization or production authentication exist yet.
