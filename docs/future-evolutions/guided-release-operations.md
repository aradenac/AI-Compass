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

## 7. Delivery boundaries and minimum acceptance

The future issue plan should separate: (a) contract/convergence foundations, (b) UX migration on shared screens, (c) manifest and artifact build, (d) compatibility checks + safe operator CLI, and (e) documented staging/production/recovery acceptance. Their exact order and scope require owner approval, not inference from this document.

Minimum outcomes:
1. One Catalog/Task/Campaign view is demonstrably the **same implementation** in Demo and Server; later covered domains replace their old duplicated views.
2. Standalone Demo starts from static files with only fictional data; Server starts empty, authenticated and remains isolated on outage.
3. Compatible backend update passes tests against the prior frontend; a breaking API update is either served compatibly or explicitly rejected before rollout.
4. A release can be reconstructed from recorded frontend/backend digests, API/schema capability manifest and CI evidence; release notes explain known changes and operator actions.
5. An incompatible migration cannot be applied without a verified recovery point, accepted real-browser staging verdict and authorized explicit production operation. Reject/discard/recreate and recovery remain tested.
6. No future proposed feature is implemented merely because the convergence framework has become available.

**Governance:** Future technical direction accepted; no new approved GitHub issues or automatic implementation permission. The [technical-debt register](../technical-debt.md) tracks cleanup and deliberately deferred validation without duplicating these design decisions.
