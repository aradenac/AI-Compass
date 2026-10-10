# AI Compass — Incremental Platform Implementation Roadmap

> **Status:** Active, dependency-driven **PLAT** issue backlog · **Updated:** 2026-10-10  
> **Proposed future feature registry (NOT this backlog):** [docs/features](features/README.md)  
> **Agent contract:** [AGENTS.md](../AGENTS.md) · **Architecture:** [Platform Architecture & Data Governance](platform-architecture-and-data-governance.md) · **Product:** [Product Definition](product-definition.md)

## Operating principle

**One issue = one independently demonstrable outcome with a focused PR and tests.** Several autonomous agents may implement the **same issue on separate branches from the exact same baseline commit**; choose the best PR after comparable CI and review. An issue is not closed until a selected solution is merged and all acceptance checks pass. The issue plus linked repository references must suffice **without any assistant's chat memory**.

Size heuristics: **S** extends a mechanism; **M** delivers one functional vertical across backend/frontend/tests; **L** spans several subsystems and should be narrowed before implementation. Optimize the **critical dependency path**, not just ticket count. The actual order is controlled by `Depends on`, not issue numbers.

## Active delivery sequence

### 1. Completed technical foundation and next first UI slice

| Issue | Outcome |
| --- | --- |
| [#1](https://github.com/aradenac/AI-Compass/issues/1) | **Done** — Django/PostgreSQL/Caddy, persistence and restore smoke |
| [#2](https://github.com/aradenac/AI-Compass/issues/2) | **Done** — real session login and independent roles |
| [#3](https://github.com/aradenac/AI-Compass/issues/3) | **Done** — Model REST API, UUIDv7/HRIDs, immutable revisions |
| [#5](https://github.com/aradenac/AI-Compass/issues/5) | **Next** — same Models UI in independent Demo and initially empty Server mode |

[#4](https://github.com/aradenac/AI-Compass/issues/4) was cancelled: never import fake Demo business data into Server.

### 2. Early durability, extensibility and safe migration foundations

| Issue | Outcome / actual prerequisite |
| --- | --- |
| [#34](https://github.com/aradenac/AI-Compass/issues/34) | Scheduled DB snapshots + **verified isolated restoration**; after #5 |
| [#25](https://github.com/aradenac/AI-Compass/issues/25) | Model v2 / generic version-aware schema compatibility, before more catalog types; after #34 |
| [#17](https://github.com/aradenac/AI-Compass/issues/17) | Reusable, immutable EvidenceBlob/Link store across all later business domains; after #34 |
| [#35](https://github.com/aradenac/AI-Compass/issues/35) | Isolated temporary Server staging, migration trial, **manual validation through real frontend**, accept/reject/discard/recreate; after #25/#34 |
| [#26](https://github.com/aradenac/AI-Compass/issues/26) | Governed production apply of **staging-approved** schema/data migration, new restorable snapshot and retry; after #35 |

These are **capabilities**, not a requirement to block every independent catalog feature until #26. A data-affecting migration cannot bypass #35/#26; adding a new type with its own non-destructive schema/revisions does not necessarily require a production data conversion.

### 3. Persistent catalog, taxonomy and reusable experimental definitions

| Issue | Outcome |
| --- | --- |
| [#6](https://github.com/aradenac/AI-Compass/issues/6) | **Consolidated** Provider + Harness + Framework catalogs using shared Model/schema adapter (former #7/#8) |
| [#9](https://github.com/aradenac/AI-Compass/issues/9) | Editable hierarchical engineering task taxonomy |
| [#10](https://github.com/aradenac/AI-Compass/issues/10) | Independent versioned Test Cases and fork lineage, with evidence links |
| [#11](https://github.com/aradenac/AI-Compass/issues/11) | Reusable Setup Guides (text/URL/version history) |

Former [#7](https://github.com/aradenac/AI-Compass/issues/7) and [#8](https://github.com/aradenac/AI-Compass/issues/8) were closed as **consolidated into #6**, not deleted.

### 4. Campaign execution and reproducible benchmark evidence

| Issue | Outcome |
| --- | --- |
| [#12](https://github.com/aradenac/AI-Compass/issues/12) | Campaigns, lifecycle, version-pinned extensible experimental method |
| [#13](https://github.com/aradenac/AI-Compass/issues/13) | Framework campaign participant trios; depends on consolidated #6 |
| [#14](https://github.com/aradenac/AI-Compass/issues/14) | Resumable, incrementally server-saved interactions and step state |
| [#15](https://github.com/aradenac/AI-Compass/issues/15) | Immutable individual benchmark run with exact method/config/evidence snapshots |
| [#16](https://github.com/aradenac/AI-Compass/issues/16) | Composite Framework runs; never assign team scores to an individual AI Solution |

### 5. Knowledge, forecasts, evaluation, recommendations and discussions

| Issue | Outcome |
| --- | --- |
| [#18](https://github.com/aradenac/AI-Compass/issues/18) | **Consolidated** Research Source library + Technology Watch Entries and links (former #19) |
| [#20](https://github.com/aradenac/AI-Compass/issues/20) | Versioned theoretical forecasts, distinct from observed runs |
| [#21](https://github.com/aradenac/AI-Compass/issues/21) | Results Explorer and evaluations with frozen inputs/methods |
| [#22](https://github.com/aradenac/AI-Compass/issues/22) | Reviewed, evidence-linked recommendations |
| [#23](https://github.com/aradenac/AI-Compass/issues/23) | Attributed versioned feedback and threaded discussions |
| [#24](https://github.com/aradenac/AI-Compass/issues/24) | **Can happen early**: generic Activity Feed from existing Model audit events; other domains emit events as they are delivered |

Former [#19](https://github.com/aradenac/AI-Compass/issues/19) was closed as **consolidated into #18**.

### 6. Operations and final acceptance

| Issue | Outcome |
| --- | --- |
| [#28](https://github.com/aradenac/AI-Compass/issues/28) | **Can happen early**: independent user administration built on #2, no dependency on health dashboard |
| [#27](https://github.com/aradenac/AI-Compass/issues/27) | Data Health, reconciliation/triage and maintenance workspace |
| [#29](https://github.com/aradenac/AI-Compass/issues/29) | **Can happen once #34/#17 are ready**: coordinated DB+file backup, independent destination, verified full-stack restore (advanced PITR deferred) |
| [#30](https://github.com/aradenac/AI-Compass/issues/30) | Portable logical export with complete evidence/history/checksum manifest |
| [#31](https://github.com/aradenac/AI-Compass/issues/31) | Restore native AI Compass archives; no fake Demo or external-source ingestion |
| [#32](https://github.com/aradenac/AI-Compass/issues/32) | **Acceptance campaign only:** orchestrate already-delivered E2E, staging, recovery, Demo/Server and go/no-go checks; no wholesale feature rewrite |

### 7. Only after validated production deployment

| Issue | Outcome |
| --- | --- |
| [#33](https://github.com/aradenac/AI-Compass/issues/33) | First deliberately selected **real external-source import**, with preview/provenance/idempotency; never import fake Demo records |

## Multi-agent PR workflow

1. Freeze and record the **same exact baseline `main` commit SHA**, issue version and dependency state for all candidates. Give each agent an isolated branch/worktree and the same [AGENTS.md](../AGENTS.md), references and verification criteria.
2. Agents may implement **the same issue independently in parallel**. Each produces a PR against `main` with diff, design choices, reproducible test commands/results and acknowledged limitations; never push straight to `main` or close the issue on submission.
3. Run the **same project CI** on every PR and compare behavior/acceptance, immutability and data safety, resilience, maintenance complexity and change scope. Critical data loss or invalid recovery is disqualifying.
4. Select/merge one PR, or carefully compose isolated fixes with a separate verification pass. Confirm all acceptance checks on the **final merged commit**, close the issue and update its evidence links. Do not mix competitors' code before their initial comparison.
5. Work on **different issues in parallel only when their actual prerequisites are met**. Agents may overlap on one issue intentionally for competition; avoid simultaneous unrelated modifications to the same monolithic frontend without isolation.

## Permanent safety and acceptance gates

- Demo is a permanent independent seeded-fake `localStorage` runtime. The **same frontend** in Server mode uses authenticated PostgreSQL, initially with no business records. Never implicitly copy, synchronize, mix or fall back.
- Stable UUIDv7/HRIDs, immutable revisions, exact method/Test Case/run snapshots, preserved unknown JSON properties, relational links, append-only audit and content-addressed file evidence are non-negotiable.
- Baseline DB recovery **#34** precedes substantive data growth. Evidence store **#17** is cross-domain; combined DB+file recovery **#29** verifies exact file/link consistency.
- For a **data-changing migration**, use a verified recovery point; validate a versioned migration artifact in isolated staging **#35** with automated tests **and real frontend manual acceptance**; only then use separately governed **#26** production application. Rejections/retries and staging edits never mutate production. Never promote the staging database over current operational data.
- Every issue adds **focused positive, negative and relevant non-regression tests** and short operator documentation; the final #32 orchestrates these already-existing suites. Splitting a large issue is acceptable **before** implementation, not by dropping acceptance.
- [#4](https://github.com/aradenac/AI-Compass/issues/4), [#7](https://github.com/aradenac/AI-Compass/issues/7), [#8](https://github.com/aradenac/AI-Compass/issues/8) and [#19](https://github.com/aradenac/AI-Compass/issues/19) are closed without independent implementation.

## Next action (as of 2026-10-10)

**Owner decision:** close technically completed issues even when operational
human acceptance will happen later. **#35, #26, #32 are CLOSED as code
deliveries**, following merged CI-green PRs #45/#68, #49/#69 and #65
respectively; manual staging, separately approved migration replay and
release sign-off are **still not performed**. These are **hard safety gates**,
not optional acceptance. The [release readiness protocol](release-readiness.md)
retains the actual checklist and unchanged **NO-GO** state. Any later
failure is tracked as a new corrective issue referencing the relevant
delivery.

**Next open issue: [#33](https://github.com/aradenac/AI-Compass/issues/33)**,
external real-data onboarding. Its first actual adapter cannot be written
or accepted until the real external source, representative sample, ownership,
permitted fields, first business entity and stable source key are selected,
and an operational deployment is approved. The independently testable
read-only [source intake preflight](external-source-onboarding.md)
provides an initial safe review step; it does not populate Server data.
Do NOT insert a fabricated "representative" Demo fixture as a production
source or close #33 on the basis of source discovery alone.

Future product features in [docs/features](features/README.md) remain
outside this approved PLAT backlog until a separate issue plan is accepted.
