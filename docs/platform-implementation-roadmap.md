# AI Compass — Incremental Platform Implementation Roadmap

> **Status:** Ordered GitHub implementation backlog · **Created:** 2026-10-09
> **Architecture:** [Platform Architecture & Data Governance](platform-architecture-and-data-governance.md)
> **Existing functional contract:** [Product Definition](product-definition.md) · [Benchmark Workflow](benchmark-workflow.md) · [Non-Functional Requirements](non-functional-requirements.md)

## Operating principle

**One issue = one focused coding conversation = one independently testable vertical increment = one direct, reviewable commit on `main` (no PR).** This is a sizing heuristic, **not** a guaranteed wall-clock or token budget. `S` and `M` effort labels are relative only. If an increment cannot be completed with its tests and safety checks in one conversation, **split it before implementing**, keeping a smaller observable end-to-end outcome rather than dropping tests or losing history.

Start at [PLAT-01](https://github.com/aradenac/AI-Compass/issues/1). The labels `PLAT-01`...`PLAT-33` indicate recommended presentation order; the real prerequisites are the linked **Depends on** issue references inside each ticket. Some catalog slices can run independently after their common foundation, but process only one issue at a time when working with a coding assistant.

Each issue contains: **user-visible outcome**, bounded **in-scope changes**, **acceptance tests**, explicit **out-of-scope**, **prerequisites**, and immutable-data **safety guardrails**. All issues are engineering work, not empty umbrella epics; no issue should be closed on the strength of scaffolding alone.

## Ordered issues

### 1. Executable foundation and first durable vertical slice

| Issue | Usable increment |
| --- | --- |
| [PLAT-01](https://github.com/aradenac/AI-Compass/issues/1) | **Completed** — Django/PostgreSQL infrastructure, unchanged Demo frontend, tested restore and install guide |
| [PLAT-02](https://github.com/aradenac/AI-Compass/issues/2) | **Completed** — real Django session login, CSRF, six independent roles, Demo/Server switching |
| [PLAT-03](https://github.com/aradenac/AI-Compass/issues/3) | **Completed** — UUIDv7 + HRIDs, versioned JSON Schema, immutable Model revisions, audit and authorized REST API |
| [PLAT-04](https://github.com/aradenac/AI-Compass/issues/4) | **Cancelled (not planned)** — fake Demo records are never migrated to Server |
| [PLAT-05](https://github.com/aradenac/AI-Compass/issues/5) | Enable API-backed Models in Server mode without removing the local Demo provider |

### 2. Persist the rest of the catalog and design assets

| Issue | Usable increment |
| --- | --- |
| [PLAT-06](https://github.com/aradenac/AI-Compass/issues/6) | Providers catalog |
| [PLAT-07](https://github.com/aradenac/AI-Compass/issues/7) | Harnesses catalog |
| [PLAT-08](https://github.com/aradenac/AI-Compass/issues/8) | Frameworks catalog |
| [PLAT-09](https://github.com/aradenac/AI-Compass/issues/9) | Editable task tree |
| [PLAT-10](https://github.com/aradenac/AI-Compass/issues/10) | Versioned Test Cases and forks |
| [PLAT-11](https://github.com/aradenac/AI-Compass/issues/11) | Reusable Setup Guides |

### 3. Record reproducible experiments and original evidence

| Issue | Usable increment |
| --- | --- |
| [PLAT-12](https://github.com/aradenac/AI-Compass/issues/12) | Campaign planning and lifecycle |
| [PLAT-13](https://github.com/aradenac/AI-Compass/issues/13) | Framework participants |
| [PLAT-14](https://github.com/aradenac/AI-Compass/issues/14) | Resumable timed sessions |
| [PLAT-15](https://github.com/aradenac/AI-Compass/issues/15) | Individual immutable runs and measured solutions |
| [PLAT-16](https://github.com/aradenac/AI-Compass/issues/16) | Composite Framework runs |
| [PLAT-17](https://github.com/aradenac/AI-Compass/issues/17) | Immutable document upload and retrieval |

### 4. Publish attributable knowledge and expose results

| Issue | Usable increment |
| --- | --- |
| [PLAT-18](https://github.com/aradenac/AI-Compass/issues/18) | Reusable external-source library |
| [PLAT-19](https://github.com/aradenac/AI-Compass/issues/19) | Watch hypotheses and source links |
| [PLAT-20](https://github.com/aradenac/AI-Compass/issues/20) | Versioned theoretical forecasts |
| [PLAT-21](https://github.com/aradenac/AI-Compass/issues/21) | Results and evaluation revisions |
| [PLAT-22](https://github.com/aradenac/AI-Compass/issues/22) | Evidence-linked recommendations |
| [PLAT-23](https://github.com/aradenac/AI-Compass/issues/23) | Feedback and discussion |
| [PLAT-24](https://github.com/aradenac/AI-Compass/issues/24) | Attributable Activity Feed |

### 5. Schema evolution and autonomous maintenance

| Issue | Usable increment |
| --- | --- |
| [PLAT-25](https://github.com/aradenac/AI-Compass/issues/25) | Backward-compatible schema v2 and safe UI |
| [PLAT-26](https://github.com/aradenac/AI-Compass/issues/26) | Governed dry-run/apply/retry of data migration |
| [PLAT-27](https://github.com/aradenac/AI-Compass/issues/27) | Maintenance dashboard, quality checks and issues |
| [PLAT-28](https://github.com/aradenac/AI-Compass/issues/28) | Separate user administration |

### 6. Demonstrable disaster recovery and production readiness

| Issue | Usable increment |
| --- | --- |
| [PLAT-29](https://github.com/aradenac/AI-Compass/issues/29) | Automated backup and isolated restore reports |
| [PLAT-30](https://github.com/aradenac/AI-Compass/issues/30) | Verifiable portable export |
| [PLAT-31](https://github.com/aradenac/AI-Compass/issues/31) | Restore/verify **native AI Compass** archives for recovery, not external-source ingestion |
| [PLAT-32](https://github.com/aradenac/AI-Compass/issues/32) | Validate operational Server launch with an **empty business database**, Demo unchanged |

### 7. Only after production deployment is validated — real-source onboarding

| Issue | Usable increment |
| --- | --- |
| [PLAT-33](https://github.com/aradenac/AI-Compass/issues/33) | First deliberately selected **real external data source** (one domain/format per issue) with preview, provenance, idempotent import and audit |

**Boundary:** External data ingestion is *not* a prerequisite for Server readiness. Source systems, representative formats and mapping are selected after the platform deployment is accepted.

## Execution protocol for each conversation

1. **Select one ready issue** (all referenced prerequisites accepted). Read the ticket and architecture/product contracts, then inspect the current code and relevant tests.
2. **Protect data first:** keep a baseline export or restorable snapshot before a destructive-risk step; never silently rewrite historical revisions or discard unknown fields.
3. **Implement the smallest integrated vertical flow:** API and storage plus the required existing UI where specified; avoid unrelated refactoring and speculative infrastructure.
4. **Prove it in both modes:** positive/negative automated tests, permissions, compatibility, resilience and a clear manual smoke path. For migrations, show dry-run/rollback/retry evidence. The standalone Demo interface must remain usable without backend services.
5. **Review the diff and document the outcome:** add minimal run instructions, actual test commands and risks. Commit directly to `main` without a PR and close the issue only after acceptance criteria pass.
6. **Stop at the issue boundary.** Do not start another issue during the same exhausted conversation; record follow-up observations in a separate ticket.

## Permanent data-safety gates

- From **PLAT-01**, PostgreSQL backup/restore is demonstrable before switching any domain from localStorage.
- From **PLAT-03**, all new catalog data uses immutable revision semantics and permanent UUIDv7 + HRID identities; no revision is overwritten.
- **PLAT-04 is cancelled:** the seeded Demo dataset is intentionally fictitious and must never be automatically staged, migrated or reconciled into the Server database. A fresh Server must contain **zero business objects**, but required tables, schemas, permissions and accounts are allowed.
- Each Server-mode domain uses **single-writer server authority** and creates its own real objects and HRIDs from scratch; no Demo ID mapping, hidden dual write, automatic fallback or synchronization. The same UI must continue to support independent Demo-mode `localStorage` persistence and seeded fake data.
- From **PLAT-17**, document bytes are content-addressed, checked and referenced only once durable.
- **PLAT-29–31** strengthen independent backup, native AI Compass archive portability and disaster recovery; they do **not** import business records from Demo or unrelated external sources.
- **PLAT-32** establishes full **Server-mode readiness** and explicitly checks an empty business database on a fresh installation; Demo remains supported. **PLAT-33 starts later**, once production deployment has been validated, to import real data from identified external systems.

## Next action

**PLAT-01 is completed on main.** [GitHub Actions validation](https://github.com/aradenac/AI-Compass/actions/runs/37864857989) passed Docker startup, migrations, Django/API tests, isolated backup/restore, container recreation and independent standalone Demo HTTP serving. [PLAT-02](https://github.com/aradenac/AI-Compass/issues/2) is also **completed and verified** ([passing auth and recovery CI](https://github.com/aradenac/AI-Compass/actions/runs/37865692273)). [PLAT-03](https://github.com/aradenac/AI-Compass/issues/3) is also **completed** and documented in [Model Catalog Architecture](model-catalog-architecture.md); [PLAT-04](https://github.com/aradenac/AI-Compass/issues/4) has been cancelled as unnecessary. **Next: [PLAT-05](https://github.com/aradenac/AI-Compass/issues/5)**, connecting the same Models UI to an initially empty Server catalog while keeping seeded Demo data separate. Real external-source import is deliberately deferred to [PLAT-33](https://github.com/aradenac/AI-Compass/issues/33) after the production deployment is validated.
