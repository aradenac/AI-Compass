# AI Compass — Shared frontend, API contracts and coordinated releases

**Engineering reference:** single business frontend with separate Demo and Server providers, versioned artifacts, compatibility controls and reproducible release evidence. The [role-based UX contract](role-based-user-experience-and-guided-navigation.md) governs presentation.

## Decisions and implementation boundary

1. **Keep one Git repository.** Organize the sources into frontend, backend, deployment/release tooling and common contract/test areas as needed. Independently build and version the frontend and backend artifacts **within a coordinated release**; do not introduce separate repositories, microservices or independent release trains without demonstrated need.
2. **One genuine business frontend.** Demo and Server must render the *same* domain views/forms/behavior via mode-specific data providers. The existing second Server UI shell and domain-specific presentation copies are an implementation gap, not the accepted final architecture. Do not accidentally preserve two permanent UI implementations.
3. **Preserve both runtime modes.** Demo works from static assets without Django, PostgreSQL, Docker or a backend; synthetic browser-local data is visibly labelled and never imported into Server. Server uses real authenticated APIs and initially empty business records; network failure never falls back to Demo. Permission differences must remain explicit.
4. **Combine convergence with the planned UX redesign.** Build the shared presentation layer while implementing the [role-based experience](role-based-user-experience-and-guided-navigation.md), rather than recreating the obsolete UI twice. A single substantial refactor is acceptable before production, provided testable checkpoints and preservation of existing features/rights/data are enforced. Do not use UX redesign to change business semantics or server authorization.
5. **Version the API contract, not every page against every database field.** The frontend talks to a stable API representation; relational schema migrations and versioned JSONB business documents can evolve independently. Unknown and historical records must degrade safely without fabricated values.
6. **Make releases reproducible and operator-friendly.** Build once, promote the same verified artifacts from staging to the target deployment, retain release manifests, release notes, acceptance evidence and recovery references. No operator should need to compose ad hoc Docker commands to determine whether a release is compatible.

The application uses one coordinated release identity while retaining independent Demo and authenticated Server data modes.

## Shared frontend contract

Use a presentation/controller layer which consumes a mode-neutral domain provider. The provider is selected **once at bootstrap**, not inside each view:

| Concern | Demo adapter | Server adapter | Shared view contract |
| --- | --- | --- | --- |
| Domain reads/writes | Synthetic fixtures and namespaced localStorage | Authenticated, same-origin HTTP API | Stable list/detail/revision/action representations |
| Identity | Explicit simulated demo persona | Real Django session and RBAC | Display capabilities; backend always enforces authorization |
| Errors | Local invalid/demo state | 401/403/409/422/unavailable/network | Distinguish permission, conflict, incomplete schema and outage |
| Schema evolution | Versioned fake-fixture/draft compatibility | API compatibility metadata and original historical data | Safe raw/read-only fallback, never blank/crash whole screen |
| Evidence | Synthetic samples only | Immutable evidence URLs with authorization | No cross-mode import, download or origin mixing |
| Unsaved work | Scoped to Demo/browser origin | Scoped to Server/account/mode/revision | Prevent leaked drafts and accidental overwrites |

- Keep shared UI components and forms for Catalog, Tasks, Test Cases, Campaigns, Runs, Guides, Recommendations and all later domains; do not maintain per-mode copies.
- Retain extensible typed payloads, exact IDs/revision pins, optimistic concurrency (409), permission-aware field/action states, proper HTML escaping and safe server error handling. Never treat hiding a button as authorization.
- New features can be **prototyped using synthetic Demo fixtures first**. They must be explicitly identified as prototypes; readiness for Server and production requires the corresponding contract, permissions, persistence and tests. A fake prototype cannot silently manufacture server evidence.
- The static Demo distribution remains easily launched without a mandatory JS build tool installed on the end user's computer. A build step during CI/release packaging is acceptable if static built output remains portable/offline.
- Convergence and future UX redesign share implementation work, but the [UX proposal](role-based-user-experience-and-guided-navigation.md) owns navigation/personas and **this document owns the technical runtime/data-provider contract**.

## Versioned artifacts and compatibility

Keep three independent notions, with one coordinated release identity:

1. **Frontend artifact version** and immutable checksum (static bundle).
2. **Backend artifact version** and immutable container digest.
3. **Data/contract capabilities**, comprising API version and declared compatibility range, Django migration state, registered object-type schema versions, storage/archive format and migration artifact IDs.

The **coordinated release** pins a tested frontend/backend pairing without requiring both artifact versions to change on every release. A schema revision embedded in a historical object is *not* the frontend version, and a migration number is *not* by itself an API compatibility promise.

Represent the release by a machine-readable **immutable manifest**, packaged alongside immutable artifact references and human release notes. Suggested illustrative structure (precise schema to be defined by delivery issue):

~~~json
{
  "release": "0.10.0",
  "source_commit": "<full-git-sha>",
  "artifacts": {
    "frontend": {"version": "0.10.0", "sha256": "<digest>"},
    "backend": {"version": "0.10.0", "image_digest": "sha256:<digest>"}
  },
  "compatibility": {
    "api_provided": "v1",
    "frontend_api_supported": ["v1"],
    "django_migration_target": "0022_external_import_mock",
    "object_schemas": {"model": [1, 2]},
    "archive_format": "ai-compass-native-v1"
  },
  "migration_plan": ["<registered-artifact-if-needed>"],
  "verification": {
    "ci_run": "<link>",
    "staging_verdict": "pending",
    "release_decision": "NO-GO"
  }
}
~~~

All values above are **examples, not a claim that release 0.10.0 exists**. Include exact workflow/commit/manifest hashes, tested platform profile, release provenance and documented operator acceptance. Do **not** embed credentials, full private snapshots, employee data, evidence payloads or sensitive CI logs in a public GitHub Release.

**Release notes**: document user-visible changes, bug/security fixes, API changes, migrated schema/data changes, backward compatibility, changed privileges/limits, test evidence, known limitations, actions required by operators, rollback conditions and GO/NO-GO sign-off. Link changed issues/PRs only after explicit issue-plan approval. GitHub tags/releases may be generated by CI with appropriately scoped permissions; publication capability needs validating and is not assumed from repository write access.

**Contract enforcement**: frontend build declares its supported API contract(s); backend advertises actual compatibility in a bounded capability/metadata endpoint. Check the pairing in CI, startup/deployment preflight and frontend initialization. Unknown or incompatible APIs must show a clear blocked/limited state, **never silently reinterpret data or switch to Demo**. Do not introduce a large persistent frontend↔backend version matrix before an actual multi-version need.

## Change classification and release order

| Change | Procedure | Availability |
| --- | --- | --- |
| **Additive/compatible** (new optional field/endpoint) | Ship backwards-compatible backend/API, then frontend as needed; preserve old field semantics and read adapters. | Prefer online deploy; verify old frontend with new backend. |
| **API-incompatible** (renamed/reinterpreted field, removed endpoint) | Expand API to support old+new representation or introduce a separately versioned route; deploy compatible backend, then new frontend; retire old contract only after verified consumers are gone. | Prefer online rollout with temporary compatibility layer. |
| **Structural/semantic data-incompatible** | Approve registered migration; restore verified DB+original-evidence snapshot in isolated staging, test actual frontend and artifacts, record human verdict; establish fresh complete recovery point; lock writes/maintenance, apply registered migration to *current production*, verify and switch exact tested assets. | Planned maintenance if backward compatibility cannot be maintained safely. |

**Never replace production data with a staging clone**. Staging remains disposable; execute the same reviewed transformation against the current production records so intervening production writes are not lost. Preserve source revisions and unknown fields. A rollback of frontend/backend binaries is allowed only when compatible with committed schema changes. Otherwise follow explicit, independently verified coordinated recovery with disclosed loss window, not an improvised database downgrade.

