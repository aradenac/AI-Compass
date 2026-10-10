# Future evolutions

This directory collects **proposed enhancements** for AI Compass. Pages here capture product decisions and preliminary impact assessments **before** implementation. They do not supersede [the agreed product baseline](../product-definition.md) or describe deployed behavior.

## Proposals

| Feature | Summary | Status |
| --- | --- | --- |
| [Campaign Evaluation Matrix](campaign-evaluation-matrix.md) | Task-scoped solution selection, Test Case × Solution execution planning, explicit non-selection and justified waivers, a central interactive frontend matrix, and additive campaign revisions/reopening after closure. | Proposed — decisions recorded; implementation pending |
| [Composable Setup Guides & Lifecycle](composable-setup-guides.md) | Modular reusable setup knowledge, solution- and environment-specific recipes, optional capture at Test Run closure, initial validation in campaign review, a publication readiness gate, and non-blocking post-publication corrections. | Proposed — decisions recorded; implementation pending |
| [Data Governance Audit Explorer](data-governance-audit-explorer.md) | Passive, comprehensive recording of persistent changes and an independent permission-controlled governance interface for who changed what, when, and how content evolved; no additional business UI input. | Proposed — decisions recorded; implementation pending |
| [Technology Accessibility & Pricing Management](technology-accessibility-and-pricing.md) | Enterprise-wide component accessibility, reusable versioned pricing offers with cumulative charges, mandatory manual campaign price selection, automatic Run variable-cost calculation, subscriptions kept separate, no shared-quota allocation, and historical preservation. | Proposed — decisions recorded; implementation pending |
| [Deployment & Adoption Planning](deployment-and-adoption-planning.md) | Task-tree × AI configuration profitability heatmap (intensity for gains, icon for maturity/deployment), Forecast+Benchmark projections, three annual opportunity slices and history, progressive source exploration, workload profiles, verified access/use, and low-input experimental/rollout quota and licensing budgets. | **Partially implemented (DAP-01 only)** — remainder requires an approved issue plan |

These are proposal specifications, **not prioritized approved GitHub issues**.
See the [feature approval ledger](../features/README.md) before changing
the backlog. DAP-01 (#66/#67) was delivered before this governance
separation; its existence does not approve DAP-02 or any subsequent feature.

Before further implementation, resolve open questions and obtain an
explicitly approved issue plan, then update baseline documentation as
each approved vertical is delivered.
