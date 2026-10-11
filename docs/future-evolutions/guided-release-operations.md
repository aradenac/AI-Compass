# Future evolution — Guided compatible and incompatible release operations

**Remaining scope:** FUT-21 [#95](https://github.com/aradenac/AI-Compass/issues/95), after UX recovery and its P7 dependencies. Build the operator commands and recoverability safeguards described below on the [current coordinated release contract](../shared-frontend-and-release-lifecycle.md).

## 5. Guided operator workflow (target; not available yet)

Expose a small, documented operator entrypoint that orchestrates existing safe commands rather than introducing a second migration engine:

~~~text
compass release check
compass release stage <version>
compass release deploy <version>
compass release status
compass release recover
~~~

**These commands are examples of intended UX and do not exist in the current repository.**

- **check**: verify host/profile, pinned artifacts/digests, supported API pair, current SQL/schema state, migration dependencies, backup destination, free space, secrets/configuration, operator authority and readiness.
- **stage**: deploy *the exact proposed artifacts* in an isolated copy restored from a coordinated recovery point, run compatibility and recovery tests, collect actual browser acceptance and a signed/pinned verdict. Permit reject/discard/recreate.
- **deploy**: refuse if any required approvals/preflights fail; for compatible changes, update backend before frontend; for incompatible data changes, close writes safely, capture/verify fresh recovery point, apply the approved artifact against current production, verify invariants, start the tested backend and frontend, then reopen writes.
- **status**: display manifest, running frontend/backend versions, schema compatibility, maintenance state, latest verified recovery point, operator decision and incomplete operations.
- **recover**: show a safe recovery plan and implications; require explicit target, privileges and confirmation; never quietly overwrite production or assume code rollback equals database rollback.

Preserve durable, idempotent state and crash-safe recovery for interrupted operations. Do not require Kubernetes, event buses, an external workflow system or a separate database for release metadata. Existing PLAT-26/29/34/35 guarantees remain mandatory. Human acceptance gates may be completed later, but the system must never report operational GO simply because code was merged or CI passed.

## Release-operation acceptance criteria

1. Validate a known coordinated frontend/backend pair, API/schema compatibility and relevant artifact digests before deployment.
2. A compatible update is reproducible with pinned notes, running-version status and proper backend/frontend order.
3. An incompatible update requires a complete verified recovery point, disposable real-browser staging acceptance and an explicit authorized verdict before altering live data.
4. Rejection, interruption or failed staging leaves production untouched, with recovery/status safely inspectable.
5. The operator workflow does not silently promote a staging database, create a second migration engine or claim production GO from CI alone.

**Existing foundation:** [coordinated release contracts](../shared-frontend-and-release-lifecycle.md), [release readiness](../release-readiness.md), [migration staging](../migration-staging.md), [migration production](../migration-production.md).
