# PLAT-16 · Immutable composite Framework benchmark Runs (Server)

A recorded workflow with **two or more pinned Framework participants** can now be closed as one composite Benchmark Run. Unlike #15 individual Runs, **a composite Run has no AI Solution FK, fingerprint, solution revision, or per-participant scores**. Its quality, DoD outcome, cost, token count, information utility and human/agent times refer only to the **whole workflow**. The data model does not infer which participant performed unlabelled interactions and does not redistribute collaborative scores.

## Schema and invariants

Additive `0015_composite_runs` creates:

- `CompositeBenchmarkRun`: permanent UUIDv7 and readable `run-*` identity, one-to-one immutable source session and final `closed` checkpoint, FK-exact Framework ID and Framework catalog revision, global outcome, validated measurements and results, actor/time, and complete frozen provenance.
- `CompositeRunParticipant`: one ordered relational FK to each **exact `CampaignParticipantPin`** in the session's immutable campaign snapshot. The pin contains stable campaign participant identity, label/role, Model/Provider/Harness identities and exact revisions, settings, capabilities and configuration version. A copied read-only `participant_snapshots` JSON envelope makes historical inspection explicit. The entire original selected set must be present (deferred PostgreSQL constraint trigger); wrong campaign pins and double members are rejected.
- `CompositeRunEvidence`: append-only FK references to the existing immutable #17 EvidenceLinks on the campaign or Test Case. Original bytes are verified by SHA-256 before closing. No new upload store is created.

PostgreSQL triggers reject updates/deletes on all new objects; the session lock, terminal checkpoint and one-to-one session FK prevent double closure or racing writes. An accepted **or failed** composite close persists atomically. The existing `BenchmarkRun` table and `MeasuredSolution` tables from #15 remain unchanged. Reading a composite, running the same Framework again or reviewing its data **never creates or updates an individual AI Solution**.

### Interaction actor labels

Each original interaction preserves its existing stable participant identity, full text, timestamps, separate human/agent durations, attachments and unknown JSON fields. Composite Run detail additionally returns `interaction_actor_labels` associating each interaction with the original pinned label and role. If the interaction did not specify a participant, the label is `Coordinator / unspecified` — not an inferred attribution. The original `raw_session_state` and checkpoints are not mutated.

### API

The **same** existing endpoint `POST /api/v1/sessions/<ses-id>/close` routes sessions with ≥2 Framework participants to composite closure. No second Run creation API. It accepts the **same** #15 validated Results fields and `expected_revision` (optimistic concurrency). POST response: HTTP 201, `Location: /api/v1/runs/<run-id>`.

Read-only API exposes both kinds, explicitly discriminated:

| Query | Scope |
| --- | --- |
| `GET /api/v1/runs?campaign_id=<cmp-id>` | All individual and composite runs, each with `kind` |
| `GET /api/v1/runs?kind=individual` | Individual only |
| `GET /api/v1/runs?kind=composite` | Composite only |
| `GET /api/v1/runs?solution_id=<sol-id>` | Only individual runs belonging to the measured solution |
| `GET /api/v1/runs/<run-id>` | Frozen individual or composite details and original evidence |

Composite detail returns `kind: "composite"`, `scope: "framework_workflow"`, `solution_id: null`, `framework_id`, `framework_revision_id`, complete ordered `participants`, `metrics`, `provenance`, `raw_session_state`, and `interaction_actor_labels`. Individual detail now carries `kind: "individual"`, preserving all existing fields. A composite search with `solution_id` explicitly returns HTTP 400, avoiding misleading attribution.

### Guided UI, Demo isolation and manual validation

In `?mode=server`, start a real Framework Campaign with two or more configured participant trios, then **Sessions / resume**. Select at least two participants and create a session. Record setup and individual interactions (attributing each to the responsible participant when known); attach actual existing campaign or Test Case evidence. The standard **Results / Close Framework composite run** form captures one global accepted/failed DoD, quality and utility, tokens, flat-rate/unknown/amount EUR cost, final human review/correction, original deliverables and supporting evidence. Press Close; the UI confirms a **composite Framework Run / global metrics only**, and offers the exact saved read-only detail.

Reopen the Campaign's Run list. Individual entries say *Individual · Solution …*; composite entries say *Composite · Framework … · N participants*. Inspect its frozen original roles, component revisions, configuration, human/agent times and original file SHA-256. Revise the catalog or Framework campaign and verify the saved composite is unchanged. Try a second closure, malformed metrics, unauthorized user or foreign evidence: fail without partial data. Repeat with a single selected participant: it still produces an **individual measured AI Solution Run** through #15.

In `?mode=demo`, the independent fake seeded-`localStorage` workflow remains usable with no backend and no import, fallback or synchronization to Server.

## Reproduce

```bash
docker compose up -d --wait --build
docker compose run --rm api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_campaign_participants config.test_sessions config.test_runs config.test_composite_runs -v 2
node scripts/test-server-campaigns.js
node scripts/test-server-sessions.js
node scripts/test-server-runs.js
node scripts/test-server-composite-runs.js
```

Migration is additive, creates only new empty tables and immutability guards; there is no backfill of earlier runs, no data conversion and no live orchestration or fabricated per-agent scores. Existing full DB+evidence restore, isolated staging and governed production migration gates remain mandatory for deployment.
