# PLAT-15 · Permanent individual benchmark Runs and measured AI Solutions

This increment closes one **Server** session with a pinned individual Model / Provider / Harness configuration into an irreversible accepted/failed controlled **Benchmark Run**. Closing does **not** publish or recommend an AI Solution or a campaign. Collaborative Framework sessions (>1 participant) remain resumable for #16; they cannot accidentally attribute a group result to one member.

## Identity, versioning and evidence

The additive `0014_individual_benchmark_runs` migration creates an empty technical `ai_solution` schema (no fake business records) and immutable relational tables:

- `SessionSolutionPin` is written with the session creation and contains exact Model/Provider/Harness **identity and revision foreign keys**, configuration version, JSON settings and extensible capabilities. In a solution-centred campaign, the trio comes from the original campaign snapshot. In a Framework session selecting **exactly one** participant, it comes from that frozen participant. In a task-centred campaign without Framework, the contributor chooses the trio and settings when creating the session. Older #14 sessions with no defined individual setup remain readable; their missing setup is **not fabricated** at closure — start a new session with recorded setup to obtain a measured run.
- `MeasuredSolution` points to a stable `CatalogItem(type_slug="ai_solution")` with an immutable v1 `CatalogRevision` and a unique SHA-256 fingerprint over canonical JSON of exact component UUIDs/**revision UUIDs**, settings, properties/capabilities and configuration version. `sol-*` ID is created inside the **first successful run-close transaction**, never by staging a theoretical candidate or an unmeasured campaign. The same fingerprint reuses its identity; changed parameters, component versions or capabilities create a distinct solution. Lifecycle starts **draft**, even for an accepted trial. No recommendation is inferred.
- `BenchmarkRun` has its own permanent `run-*` public ID + UUIDv7, immutable FK to the **single** originating session, exact **closed checkpoint**, measured solution and its initial catalog revision; accepted/failed DoD, raw metrics, source provenance and original human report. `BenchmarkRunEvidence` FK-pins each #17 `EvidenceLink`. All four new tables have database-level immutability triggers and reference guards.
- Closure appends an **immutable final session checkpoint** with status `closed` and full original setup, method step values, unknown JSON extensions, ordered/timestamped interactions and their evidence IDs, plus results. Neither the run, checkpoint nor past catalog revisions can be overwritten. Subsequent session writes are rejected. References to evidence already attached to the campaign/Test Case are verified by SHA-256 on closure. The original bytes remain in the shared evidence volume; a Run only links them.

A failed trial is valid and permanently inspectable, **not** an automatically qualified/recommended AI Solution. Read-only Run detail exposes the original experimental-method descriptor/version, campaign mode/configuration/revision, Test Case revision and task linkage via its frozen campaign snapshot, Setup Guide revision, source trio/settings fingerprint, raw timeline and evidence hashes. Changes in the catalog, Guide, Test Case or method never rewrite these records. If a later process recomputes conclusions, it must create **new versioned derived evaluations**, not update the Run.

## Metrics validation

The closure requires an explicit `outcome: "accepted"|"failed"`, at least one persisted interaction and a nonempty canonical `produced_outputs` string. Validated fields are:

- `quality_score`, `information_utility_score`: 0–100 or `null`, each with separate descriptive evaluation.
- `tokens_count`: integer ≥0 or `null`; `tokens_multiplier`: 1, 10, 100, 1000 or 1000000. Computed `tokens_total` remains `null` if tokens were not known; explicit zero remains zero.
- `cost_mode`: `amount` with finite, nonnegative `cost_eur`; `flat_rate` or `unknown` with `cost_eur:null`. No invisible conversion from subscription/unknown to €0.
- `human_review_minutes`, `human_correction_minutes`: independently optional in minutes. Installation and each interaction human/agent duration already belong to the frozen session. Agent total is derived from per-interaction values, not separately input; if a contributing value was unmeasured, aggregate is `null` rather than a false zero. Human total includes installation + interactions + review + correction only if all known.
- `notes`, `extensions` JSON object (retains unknown typed properties), and additional `evidence_link_ids` (pre-uploaded original evidence); all preserved exactly within immutable context.

All requested output values are validated before the transaction commits. A wrong evidence source/type, broken SHA-256, malformed metrics or stale session revision rejects the **entire** closure.

## API (Server only)

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/v1/sessions/<ses-id>/close` | CSRF + `auth.business_write`, session creator or campaign owner, single atomic closure |
| GET | `/api/v1/runs?campaign_id=<cmp-id>` | Read-only original run list (also `solution_id` filter) |
| GET | `/api/v1/runs/<run-id>` | Original result, full timeline, known/unknown metrics, evidence SHA-256 and provenance |
| GET | `/api/v1/solutions` | Only registered (measured) stable AI Solution identities, no untested candidates |
| GET | `/api/v1/solutions/<sol-id>` | Exact frozen solution setup, initial revision and its constituent Run IDs |

Start a task-centred non-Framework individual session:

```json
{
  "test_case_id": "tcs-existing-server-case",
  "component_ids": {
    "model": "mdl-existing-server-model",
    "provider": "prv-existing-server-provider",
    "harness": "hrn-existing-server-harness"
  },
  "configuration_version": "1",
  "settings": {"reasoning_effort":"high"},
  "properties": {"tools":["git","shell"],"future":{"nullable":null}}
}
```

POST close example (requires the **last confirmed** session `expected_revision`):

```json
{
  "expected_revision": "r003",
  "outcome": "accepted",
  "quality_score": 85,
  "quality_evaluation": "Driver builds and passes regression",
  "information_utility_score": 70,
  "information_utility_evaluation": "Limited noise, actionable output",
  "tokens_count": null,
  "tokens_multiplier": 1,
  "cost_mode": "flat_rate",
  "cost_eur": null,
  "human_review_minutes": 3,
  "human_correction_minutes": 0,
  "produced_outputs": "drivers/ksz8851.c; twister report",
  "notes": "Specific original observations",
  "extensions": {"custom":{"unknown":null}},
  "evidence_link_ids": ["uuid-of-previously-uploaded-campaign-evidence"]
}
```

The response is HTTP **201** with `Location: /api/v1/runs/<run-id>`. A stale/concurrent/double close returns **409**. A successful response contains a `solution_id`; follow-up identical individual setups reuse that ID, **regardless of acceptance outcome**, while the solution remains draft/unqualified. Readers have access via `auth.business_read`; no ability to mutate a Run. Server never imports/synchronizes fake Demo sessions.

## Reproduce / manual proof

```bash
docker compose up -d --wait --build
docker compose run --rm api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_sessions config.test_runs -v 2
node scripts/test-server-sessions.js
node scripts/test-server-runs.js
```

1. In `?mode=server`, create real Model, Provider, Harness, task, Test Case and optional reusable Setup Guide. Create and start a task-centred campaign. Open **Sessions / resume**, select the Test Case and **all three individual components** (with explicit settings), create the session and confirm its frozen setup.
2. Save setup, a step, two timestamped interactions (one unknown agent time), and any original `#17` file already uploaded to the campaign/Test Case. Complete **Results / Close** with accepted DoD, known quality score, optional tokens and flat-rate cost. After confirmation open **Read original run** and verify the named AI Solution, revision, preserved unknown properties, raw step values, file hashes and distinct unknown-vs-zero metrics.
3. Refresh, change browser, restart Django, revise Model, Guide and Test Case; original Run and bytes remain identical. Try to write to the closed session or close again — 409. Read as a reader (authorized). An unrelated contributor cannot close another creator's draft (403).
4. Execute the **same exact setup** on a second session with failed outcome: it yields a second immutable Run with the **same** solution ID but no automatic recommendation. Change one configuration setting and repeat: a **different** solution ID is allocated.
5. Attempt a malformed token/cost/score, missing output or broken evidence link. Assert no Run, solution or closing checkpoint is committed. Repeat with a single Framework participant (allowed); a session with multiple participants cannot produce an individual run (#16).
6. In `?mode=demo`, the independent seeded-fake workflow must still work with no backend/Docker, and switching modes never synchronizes or imports local data.

All migrations are additive. Existing campaigns, sessions, evidence and prior revisions are **not backfilled or rewritten**. Governed production rollout still uses existing verified recovery and staging procedures; creating the migration in Git is not permission to bypass those gates.
