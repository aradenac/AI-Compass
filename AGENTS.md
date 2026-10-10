# AI Compass — Agent implementation contract

Use this file together with the GitHub issue assigned to you. **The repository, not chat history or agent memory, is the source of truth.**

## Delivery scope and planning lanes

Only issues from the **existing approved PLAT roadmap** are eligible for automatic
"next priority issue" work. Concepts documented in
[Feature proposals](docs/features/README.md) or
[Future evolutions](docs/future-evolutions/README.md) are **not** a delivery
backlog and must not be implemented, split into GitHub issues, or prioritized
without an explicit approved issue plan from the project owner. Previously
shipped DAP-01 is historical, **not** implicit approval for DAP-02 or later.

## Authoritative references
- [Product semantics](docs/product-definition.md) and [benchmark workflow](docs/benchmark-workflow.md)
- [Persistence, immutable evidence, migration and recovery rules](docs/platform-architecture-and-data-governance.md)
- [Roadmap and issue dependencies](docs/platform-implementation-roadmap.md)
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

## Minimum verification for each PR
- Run the relevant existing Django tests, migration check and focused new nominal/negative/regression tests; use the project's CI workflow as the common baseline.
- Verify standalone Demo still works if touching frontend and Server persists across sessions if touching business UI/API. Verify unchanged historical revisions and backup/recovery behavior when affecting persistence.
- Document reproducible setup/smoke commands, affected API/schema and any migration/rollback requirements. Do not add long testing suites unrelated to the issue.

See [the roadmap's multi-agent PR workflow](docs/platform-implementation-roadmap.md#multi-agent-pr-workflow) for how several PRs for one issue are compared.
