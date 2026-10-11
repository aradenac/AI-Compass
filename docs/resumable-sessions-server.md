# Resumable Server benchmark sessions — PLAT-14

This increment adds real Django/PostgreSQL Test Case execution **drafts**, separate from the single-file seeded-fake Demo workflow. Session state survives a browser change, sign-out and process/container recreation. A session starts `in_progress`, can be explicitly `paused` and `resumed` via immutable checkpoints, and is not silently marked completed. It **does not** create, close or publish a Benchmark Run, measured AI Solution or score; those belong to #15 and #16.

## Frozen provenance and data protection

An immutable `BenchmarkSession` (`ses-<word>-<word>-<word>`, UUIDv7) pins:
- The exact immutable **campaign snapshot/revision**, including its Framework, participant trios and their component revisions/configuration;
- An exact `CampaignCasePin` for the selected Test Case revision;
- The exact `ObjectTypeVersion` method definition **and a copied JSON schema/step/field descriptor**;
- The selected Setup Guide **and exact immutable guide revision**, either the one from the campaign or an explicitly selected reusable guide;
- Creator, creation timestamp and, if Framework-enabled, selected participant IDs from that campaign snapshot.

Session identity, snapshot relationships and the method descriptor cannot be changed. Every save appends an immutable `SessionCheckpoint` carrying the **full latest draft state**, actor, timestamp, action, monotonic revision `r001`, `r002`, etc., and exact `SessionCheckpointEvidence` links. PostgreSQL protects all three tables from `UPDATE/DELETE`, checks campaign/Test Case/method/guide FK consistency and rejects evidence references not attached to the original campaign or Test Case.

The initial checkpoint records **no guessed measurements**: installation duration and human/agent iteration durations start at `null`, not zero. Explicit `0` is retained. Unknown JSON properties and interim descriptions remain inspectable. Per-step form values, status, notes, duration, schema version, extensions, and evidence links are preserved across saves; each interaction has permanent UUIDv7 ID, append order, client or server timestamp, type, full content, separate human/agent durations, participant attribution, notes, unknown extensions and source evidence. Summed times are **null** if any contributing measurement is missing, rather than pretending unmeasured time was zero.

Any previously uploaded #17 evidence on the campaign or Test Case may be linked to setup, step or interaction. The backend verifies the existing bytes/checksum before accepting a link, then snapshots explicit `EvidenceLink` FKs, preventing accidental orphan/mismatched references. Original binaries are not duplicated and no new document-upload subsystem exists.

The method form adapter reads `session.method_descriptor.steps` and `fields`, allowing new method definitions to add/reorder steps and fields while old sessions keep their original frozen descriptors. A step not in a session's original method is rejected. Experimental method version upgrades and campaign changes never reconfigure already-started sessions.

## API and concurrency

| Method | Endpoint | Meaning |
| --- | --- | --- |
| GET/POST | `/api/v1/campaigns/<cmp-id>/sessions` | List all real draft sessions or create one for a currently **In progress** campaign |
| GET | `/api/v1/sessions/<ses-id>` | Resume latest server-confirmed checkpoint |
| GET | `/api/v1/sessions/<ses-id>/checkpoints` | List original checkpoint chronology |
| GET | `/api/v1/sessions/<ses-id>/checkpoints/<number>` | Read unchanged historical checkpoint and evidence |
| POST | `/api/v1/sessions/<ses-id>/actions/pause` or `/actions/resume` | Append a durable lifecycle checkpoint; a paused draft rejects step/interaction changes until resumed |
| PATCH | `/api/v1/sessions/<ses-id>/setup` | Save installation timestamp, environment, setup duration, notes, extensions, evidence |
| PATCH | `/api/v1/sessions/<ses-id>/steps/<key>` | Save a frozen-method step's partial values/status/timing/notes and evidence |
| POST | `/api/v1/sessions/<ses-id>/interactions` | Append one timestamped first/follow-up interaction and evidence |

All mutations require business write privileges and CSRF. **One experimenter owns one active Run**: since UX-R05 ([#124](https://github.com/aradenac/AI-Compass/issues/124)) only the **account that created the session** (or a superuser) may append checkpoints or close it into a Run; the campaign owner is no longer an implicit co-writer. Other workgroup readers, including the campaign owner, keep read access to the original context and checkpoints, and any authorized contributor may create a **separate** session for the same campaign. A refused write returns HTTP 403 and appends no checkpoint. For each PATCH/POST action include `expected_revision: "rNNN"`; a stale write receives HTTP 409 and does not mutate a previously accepted draft. Each write is a single atomic transaction with its FK evidence pins and returns a new confirmed revision.

## Run interaction stepper and unsaved local input (UX-R05)

The workspace presents the frozen workflow as an explicit sequential stepper — **Setup → each frozen method step → Interactions → Results** — and only one step panel is shown at a time. Moving between steps is **purely local**: it writes no checkpoint, creates no phantom session and never promotes a browser cache into measured evidence. Only the explicit Save/Append/Close buttons append an immutable checkpoint. An acknowledged save updates the displayed `rNNN` revision and the affected sub-view without re-rendering the whole form, so unsaved input in other steps survives.

Unsaved inputs and the active step use the scoped ephemeral draft described in [Draft resume, Run stepper and conflict-safe concurrent editing](draft-conflict-and-run-stepper.md): leaving the screen, reloading or returning offers an explicit *Resume* that restores the values and the remembered step, a 409 keeps the draft and names both revisions, and closing the Run as a permanent Run clears it. The persisted PostgreSQL checkpoint always remains authoritative.

POST create body:
```json
{
  "test_case_id": "tcs-real-test-case",
  "guide_id": "gui-optional-server-guide",
  "selected_participant_ids": ["ptp-selected-framework-member"]
}
```
Only the Test Case ID is mandatory for a non-Framework campaign. With a Framework, select at least one participant from the pinned campaign snapshot; participants need not be selected for other campaigns.

A typical incremental interaction write:
```json
{
  "expected_revision": "r003",
  "type": "human_prompt",
  "content": "Implement the SPI driver and run native_sim tests",
  "occurred_at": "2026-10-10T09:15:00+02:00",
  "human_minutes": 4.5,
  "agent_minutes": null,
  "extensions": {"custom": {"nullable": null}},
  "evidence_link_ids": ["existing-immutable-uuid-v7-link"]
}
```

After the confirmation returns `r004`, another interaction can be saved with `expected_revision: "r004"`. Backend rejects missing/foreign links, wrong campaign/Test Case, missing permissions, malformed dates, negative durations, unsupported step keys, replayed revisions and overlarge payloads. Read endpoints never silently fall back to Demo.

A write attempt by any other account — including the campaign owner — is rejected with `403 permission_denied` (`Only the experimenter who created this active Run may edit its session`) and appends no checkpoint. The rejected account can still read the session, its checkpoints and original evidence, and can create its own session for the same campaign.

## Reproduce and manually demonstrate

```bash
docker compose up -d --wait --build
docker compose run --rm api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_campaigns config.test_campaign_participants config.test_sessions -v 2
node scripts/test-server-campaigns.js
node scripts/test-server-sessions.js
```

1. Sign in as a Server contributor, create a real task/Test Case and optionally a reusable guide and a Framework with participants. Start a campaign. Go to **Campaigns → Sessions / resume**, select its Test Case and optionally the Setup Guide/Framework participant, and create the session.
2. Record an installation timestamp and an **unknown** installation duration and press **Save installation checkpoint**. Fill the method-guided planning step, unknown custom JSON and save that step. Confirm the new revision is displayed **after** each HTTP acknowledgement. Do not mistake unsaved text for persisted content.
3. Append a first prompt and a follow-up, with distinct human/agent times and unknown values where appropriate; each is immediately and separately submitted to Server and appears in the saved timeline. To attach original artefacts, first upload a valid file to the existing `/api/v1/catalog/items/<cmp-id>/evidence/upload` endpoint (or Test Case equivalent) using `curl -F file=@... -F revision=r001` with session auth/CSRF, then reopen the session and select the evidence entry on the relevant form. The original SHA-256 is returned with the session. This issue intentionally does not implement an additional binary uploader.
4. Refresh, sign out/in, then use browser B → **Sessions / resume**. Check that step order, original method descriptors, prompt texts, unknown extension fields, elapsed times, evidence UUIDs and downloaded bytes/hash are unchanged. Recreate the API container (not the database volume) and resume again.
5. Edit the catalogued guide/Test Case, then revise the campaign's experimental method and step ordering. The pre-existing session must still show the **original** Test Case, guide, campaign revision and method/step order. New sessions may select the newer version.
6. Attempt a stale `expected_revision`, a wrong step, foreign evidence and a draft update by an unrelated contributor — including the **campaign owner** — : all must fail with HTTP 409/403 and append no checkpoint. Read and compare `/checkpoints/1` and the latest checkpoint to confirm originals were not overwritten. A second contributor may still create their own separate session for the same campaign.
7. Exercise the Run stepper: move between Setup, method steps, Interactions and Results without pressing a Save button, leave the screen and return. No checkpoint may be appended by navigation alone, and the unsaved input plus the remembered step must be offered as an explicit Resume.
8. In `?mode=demo`, use the original independent fake workflow without Docker, login or connection to Server. No sample sessions have been imported into a fresh Server.

The additive `0013_benchmark_sessions` migration adds only new tables, foreign keys, constraints and immutable guards; no existing business records are modified or backfilled. The current verified PostgreSQL + evidence backup and isolated staging mechanisms cover these draft records. There is no destructive migration, schema conversion or automatic production data promotion.
