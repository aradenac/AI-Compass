# AI Compass — Agent implementation contract

Use this file together with the GitHub issue assigned to you. **The repository, not chat history or agent memory, is the source of truth.**

## Delivery scope and planning lanes

**Current development queue (2026-10-11):** FUT #75–#91 **code merged and closed**; **UX #114 → #115 → #116 are the highest-priority open implementation issues**, and P7 FUT #92–#95 are deferred until UX #116 acceptance. Select next work using the [live implementation ledger](docs/future-evolutions/implementation-plan.md) and GitHub open/closed/PR state, never by issue number alone. All detailed completed domain requirements now live under [current docs](docs/features/README.md); [future evolutions](docs/future-evolutions/README.md) covers only still-open P7 scope. The earlier PLAT roadmap is delivered code with separate **NO-GO** operational release gates.

One issue is intended as **one maximal coherent agent-conversation implementation** with a focused PR and complete acceptance; do not overdecompose into tiny tickets. If technical evidence proves an issue too large to finish safely, document the blocker and ask for explicit replan rather than dropping requirements.

## Authoritative references
- [Product semantics](docs/product-definition.md) and [benchmark workflow](docs/benchmark-workflow.md)
- [Persistence, immutable evidence, migration and recovery rules](docs/platform-architecture-and-data-governance.md)
- [Active FUT roadmap and GitHub issue dependencies](docs/future-evolutions/implementation-plan.md)
- [Maintained product/domain specifications and delivered feature ledger](docs/features/README.md), and [remaining future scopes](docs/future-evolutions/README.md)
- [Completed PLAT roadmap and preserved release gates](docs/platform-implementation-roadmap.md)
- [Local installation, commands and safe operation](docs/local-installation.md)
- [Current Model REST API](docs/model-catalog-architecture.md)

## Competing-agent delivery
1. Read the complete assigned issue, its prerequisites, relevant reference sections, implementation and existing tests **before modifying code**. Do not assume inaccessible conversation context.
2. Each competing agent branches from **the same explicitly pinned commit SHA** in an isolated branch/worktree. Do not fetch or merge another competitor's implementation during the comparison.
3. Implement **only the bounded issue** end to end, not speculative future issues. Prefer reuse of existing domain services, one Django backend, same frontend. If scope truly exceeds one coding session, report the blocker and propose a vertical split; do not silently drop acceptance criteria.
4. Submit a **PR against `main`** with issue reference, concise design/diff summary, commands and test results, operational/migration effects and known limitations. Never push directly to `main`, merge/close the issue, or claim unrun tests passed. A reviewer chooses a PR after common-base tests.
5. PRs are assessed on acceptance behavior, correctness and data preservation, architecture, robustness, focused tests and complexity. Breaking integrity or losing historical data fails regardless of other scores.

## Invariants
- **Demo**: the existing seeded fake browser `localStorage` mode works independently without backend. **Server**: authenticated Django/PostgreSQL using the same frontend; new Server starts with an empty business catalog. Never copy/synchronize/fallback between Demo and Server.
- All durable identities and revisions remain stable and inspectable. Store important relationships via foreign keys, type-specific extensions in validated versioned JSONB. Keep unknown properties; do not invent values for missing metrics.
- Original measurements, prompts, documents, comments, audit trail and linked evidence must not disappear when objects/methods/schemas evolve. Changes append versions; historical runs pin method, Test Case, component, configuration and evidence revisions.
- File evidence uses immutable bytes with hashes and stable linked provenance. No orphan or partial blob may be represented as a valid evidence attachment.
- Structural/semantic data migrations require a **verified recovery point** (#34/#29), isolated staging with automated + real-frontend acceptance and reject/recreate (#35), then separate approved production application (#26). Never replace production with a staging DB.
- Keep user roles simple but enforce privileges at the API, prevent accidental destructive operations, and keep secrets out of Git.

## UI acceptance gate (priority before further feature work)

- Follow [UX-R01 #114](https://github.com/aradenac/AI-Compass/issues/114), [UX-R02 #115](https://github.com/aradenac/AI-Compass/issues/115), and [UX-R03 #116](https://github.com/aradenac/AI-Compass/issues/116) in that order. Do not start the deferred #92–#95 without the completed UI gate, regardless of numeric ticket order.
- For every PR that alters user-visible UI, perform actual Chromium Playwright journeys in BOTH Demo and authenticated Server, including a multi-role user. Inspect screenshots/traces and console exceptions. Verify exactly one active domain view, intended modals and form close behavior (NFR-UX-001/002), responsive presentation, breadcrumbs and meaningful round-trip navigation.
- Compare visual output to APPROVED intended references, never snapshots of a known-broken UI. A green JS-only test is not visual acceptance; report actual tests and artifacts, and block merge if required UI validation is missing/failed. Keep prior backend/data-integrity/security tests.

## Minimum verification for each PR
- Run the relevant existing Django tests, migration check and focused new nominal/negative/regression tests; use the project's CI workflow as the common baseline.
- Verify standalone Demo still works if touching frontend and Server persists across sessions if touching business UI/API. Verify unchanged historical revisions and backup/recovery behavior when affecting persistence.
- Document reproducible setup/smoke commands, affected API/schema and any migration/rollback requirements. Do not add long testing suites unrelated to the issue.

Use the [existing multi-agent PR workflow](docs/platform-implementation-roadmap.md#multi-agent-pr-workflow) to compare implementations of the **same** FUT issue, while taking active phase dependencies from the [live FUT/UX issue plan](docs/future-evolutions/implementation-plan.md).
