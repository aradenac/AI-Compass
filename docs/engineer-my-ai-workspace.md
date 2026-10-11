# FUT-12 — Engineer My AI Workspace (Server and fictional offline Demo)

## User journey and contracts

Enter **My AI Workspace** with `?mode=server&workspace=engineer` (or
`?workspace=engineer` for the independent fictional Demo). The default
personalized Task hierarchy is constrained to the current account's **own**
linked `person` DAP-01 Workload Profile, with inherited role/specialty Task
allocations and ancestor Task breadcrumbs. A missing, conflicting or
unassigned personal profile displays an explicit unknown state and a
conscious **Explore all Tasks and solutions** fallback, never assumed
eligibility or an arbitrary inferred occupation.

The Server projection reads **only** current active published individual
`BenchmarkRun` IDs from `publication_services.effective_ids`; withdrawn,
unpublished and pending attempts do not enter this corpus. Observed
accepted/failed outcomes, exact Test Case/revision, experimental method
identity/version and amendment revision are shown. Results Explorer retains
independent composite Framework and theoretical Forecast views. No
composite global workflow outcomes are misattributed to a single model/
provider/harness trio.

**Ranking boundary:** the current evaluation-scoring method v1 explicitly
has `aggregation: none` and `comparison_basis: descriptive_only`. As a
result, FUT-12 can distinguish accepted observations, failed-only and
contradictory evidence, but **cannot truthfully calculate a numeric ranking
or claim a universally qualified solution**. It shows `score:null`,
`rank:null`, observed Run counts and Test Case coverage. Display sorting
groups compatible accepted observations first and interesting alternative-OS
evidence second, then uses stable name/ID order; it never manufactures
quality averages, costs, projected gains or access grants. A future
versioned, validated ranking policy may replace this conservative sorting
without rewriting any Run or editorial Recommendation.

The current Server catalog's OS support is applied to the actual currently
registered Harness revision and the **self-declared** user's Windows/Linux
set. Original source component IDs/revision IDs remain separately pinned
to the immutable Session configuration; current catalog compatibility
does not change the Run's historical setup. A Windows-only user still sees
accepted Linux-only evidence under an explicit `other_os` section.
Enterprise accessibility is reduced conservatively across the three
currently registered components: accessible, restricted, not accessible,
unknown. Personal effective entitlement is **always unknown/unverified**
until a future Deployment & Access source is introduced (FUT-15).
An access-interest message is never a provisioning or approval event.

## Stable API and action contract

The following endpoints require an authenticated active identity and the
normal `business_read` grant. Ordinary users do **not** receive the
confidential `planning_view` grant:

- `GET /api/v1/engineer/workspace?view=task&all_tasks=false` — personally
  relevant hierarchy, measured configurations, method outcome and coverage;
  `view=tool` inverts the same underlying dataset; `all_tasks=true`
  explicitly opens the global discovery tree.
- `GET /api/v1/engineer/solutions/{sol-id}?task_id={tsk-id}` — exact
  published evidence references, currently applicable Setup Guide if
  independently published/recipe-ready, distinctly labeled historical
  Run-pinned setup, current OS and access state, editorial Recommendation
  rationale/limitations and other supported Tasks.
- `POST /api/v1/engineer/feedback` — `{"kind":"feedback"|"request"|"idea",
  "context_id":"sol-..."|"tsk-...","body":"..."}`. Creates an ordinary
  public chronological Discussion with strict context validation, CSRF
  enforcement and bounded payload. `feedback` requires a currently
  published Solution, `idea` requires a Task, and `request` accepts
  either; requests produce no entitlement or purchase and no automatic
  workgroup To-Do. Public/internal discussion message permissions,
  edits, attachments and chronology remain owned by the existing
  Discussions subsystem.

Draft evaluations, other people's workload allocations, hourly rates,
headcounts, account records, raw unpublished transcript/checkpoint,
unpublished guide revisions and internal discussion notes never appear
in the Engineer public payload. Withdrawals propagate immediately.
Editor-only historical source inspection is not implicitly granted by
Engineer navigation.

## Guide applicability and source history

A current guide is rendered only when the linked original
`setup_guide` has a currently **published**, recipe-ready revision
compatible with the exact measured trio. The past measured setup remains
clearly labeled `historical`, with its original revision pinned; it is
not automatically upgraded by changes to guide text or module references.
Missing or unreviewed currently applicable documentation is explicit.
The generic *User Guide*, charter/FAQ and entitlement-provisioning plans
are different concepts and are marked as not registered where no
authorized exact link exists.

## Frontend and deployment

`shared-engineer.js` provides one Task-first/detail/feedback component
with separate `serverProvider` and `demoProvider`. Server transport
uses CSRF and same-origin `/api/v1/` routes with **no Demo/localStorage
fallback**. The Demo provider consumes only the existing fictional
`db.tasks/db.runs/db.solutions/db.guides/db.feedback` data and appends
feedback there. The latter remains a simulation, not authoritative
commercial or experimental qualification. Role selection follows the
existing persona menu; `/maintenance` remains independent.

The widget is explicitly mounted by `compose.yaml` and
`staging/compose.yaml`, not bundled from a shadow copy. A previous
full-domain Engineer/Results demonstration can still be opened from
the new focused Demo landing. Neither data store is migrated or seeded.

## Checks, backward compatibility and rollback

- `python manage.py test config.test_engineer -v 2` against disposable
  PostgreSQL: positive/negative evidence, no-profile/privacy fallback,
  personal workload projection without rate disclosure, OS alternatives,
  exact guides, feedback CSRF and publication withdrawal.
- `node scripts/test-shared-engineer.js`: a shared renderer/provider
  compiled and independently called with offline Demo and Server sources.
- Existing FUT-06/07/10/11 and Results/Recommendations/Feedback suites
  continue unchanged; full release CI must succeed on the final PR head.

**Schema migration: none.** This release introduces additive URLs and
read projections plus safe Discussion context reuse. Existing permanent
IDs, immutable source records, schema/backup restore semantics and
release manifest compatibility do not change. Rolling back the frontend
and API removes the new workspace without modifying persisted evidence
or discussions; feedback already recorded remains in ordinary immutable
Discussion records. Production authorization requires the established
staging/recovery gates independently of GitHub CI success.
