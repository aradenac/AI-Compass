# Server Campaign Planning & Lifecycle — PLAT-12

> **New target UI (not current Server implementation):** [Benchmark Workspace UI contract](benchmark-workspace-workgroup-ui-spec.md) and [versioned manager](prototypes/benchmark-workspace/index.html)/[campaign detail](prototypes/benchmark-workspace/campaign.html) prototypes. They introduce free multi-Task/multi-configuration campaign plans (no Task-centred/Solution-centred mode selector) and collaborative review threads with independent Open/Closed status. The historical Server API/mode fields and immutable revisions described below remain current until explicit migration.


AI Compass uses **the same `prototype.html`** with two strictly independent runtimes.
`?mode=demo` is fictitious browser `localStorage`; `?mode=server` is authenticated Django/PostgreSQL. Server creates **zero campaigns** or other business records at installation. No transfer between modes is attempted.

## Domain contract

- **Permanent campaign identity:** UUIDv7 `CatalogItem` with public `cmp-<word>-<word>-<word>`.
- **Immutable campaign revision:** each plan change, lifecycle transition, archive or restore appends `CatalogRevision` and a protected `CampaignSnapshot`; old revision IDs remain readable. Revisions are never overwritten or deleted; PostgreSQL guards also protect case and component pins.
- **Experimental method:** immutable `ObjectTypeVersion` descriptor `campaign_method_task_centred` or `campaign_method_solution_centred`, with independently versioned `steps`, `criteria`, `fields` and extensions. Version 1 is installed as *technical metadata only*. Creating a v2 method definition does not reinterpret campaigns pinned to v1. The API lists all method versions; users can explicitly revise a campaign onto a newer definition, creating a new campaign revision. No separate protocol selection UI is required.
- **Typed FKs:** owner; fixed engineering task + *exact* task revision in task-centred mode; or model/provider/harness + their exact revisions in solution-centred mode; optional Setup Guide + exact revision; zero or more Test Cases + exact revisions. Task-centred Test Cases must belong to the fixed task. New Server Test Cases, tasks, components and guides can be selected immediately after creation; references to Demo IDs or wrong object types are rejected.
- **Configuration:** campaign-level settings are versioned JSON, with unknown properties preserved. Link changes are deliberate and create a new snapshot. Revising a linked Test Case/Guide/Model elsewhere does not refresh existing pins.
- **Evidence:** campaign files use the existing generic `/api/v1/catalog/items/<cmp-id>/evidence` store. Evidence is never replaced, even if the campaign is archived/reopened.
- **Permissions:** `business_read` to inspect campaigns and revisions, `business_write` to create/edit/manage lifecycle; **`publication_review`** for publish/unpublish decisions. CSRF and optimistic revision checks apply to all mutations. Data Maintainers without business privileges cannot read or mutate campaigns.

## API

| Verb | Endpoint | Outcome |
| --- | --- | --- |
| GET | `/api/v1/campaign-methods` | Versioned method descriptors |
| GET/POST | `/api/v1/campaigns` | List and create |
| GET/PATCH | `/api/v1/campaigns/<cmp-id>` | Read or append a planning revision |
| POST | `/api/v1/campaigns/<cmp-id>/actions/<action>` | Begin, close, rework, reopen, publish, unpublish, archive, restore |
| GET | `/api/v1/campaigns/<cmp-id>/revisions` | Immutable full history |
| GET | `/api/v1/campaigns/<cmp-id>/revisions/<N>` | Exact historical pin/snapshot |
| GET | `/api/v1/campaigns/pipeline` | Read-only columns for workgroup daily dashboard |

For POST to `/campaigns`, supply a `name` (1–160), `objective`, `mode` (`task_centred` or `solution_centred`), optional `owner` (existing active contributor), `notes`, `properties` (unknown JSON extension fields), `configuration` (arbitrary object), optional `guide_id`, `test_case_ids`, optional `method_version` (defaults to latest registered for that mode), and the appropriate fixed `task_id` or `component_ids` object with `model`, `provider`, `harness` public IDs. PATCH accepts the same fields plus a required `expected_revision`. Omitting a link on PATCH retains its exact preceding **revision pin**, not the latest external version. Resubmitting unchanged links **does not repin** them. Only changing the reference ID, or setting `repin: true` explicitly (the UI checkbox), selects the latest revisions of existing links.

For lifecycle actions, send `{"expected_revision":"r001"}`; a mismatch yields HTTP 409. Allowed transitions are:

```
planned --start--> in_progress --close--> under_review --publish--> published
                                     | --rework/reopen--> in_progress
published --unpublish--> under_review
published --reopen--> in_progress
```

Archive and restore add immutable revisions without destroying the previous status. Archived campaigns cannot be edited or transitioned until restored. The pipeline excludes archived records but historical queries preserve them. Reopened published campaigns retain evidence and previous published revisions.

**Boundary with PLAT-14/15:** This increment does **not** create sessions, runs, outcomes or scores. `Published` here is a *reviewed campaign-plan lifecycle marker*, not evidence of measured performance or an AI Solution recommendation. Until run closure arrives, the publication action requires at least one linked Test Case but cannot claim a completed run. Later issues must enforce the stricter run-backed publication gate before publishing actual benchmark results. The `completed_runs` pipeline field is explicitly zero; no fabricated evidence or Demo history is imported. Composite Framework participants are PLAT-13.

## Reproducible test and demonstration

Run in a disposable, unseeded Server environment:

```bash
docker compose up -d --wait --build
docker compose run --rm api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_campaigns config.test_setup_guides config.test_test_cases -v 2
node scripts/test-server-campaigns.js
node scripts/test-server-guides.js
node scripts/test-server-test-cases.js
```

1. Sign in as a Server contributor at `/prototype.html?mode=server`; create a task and Test Case in Task management / Test Design; optionally create a reusable guide or catalog model/provider/harness.
2. In **Benchmark Workspace · Campaigns**, select a mode and method version, create a campaign with a fixed task or three components, select real Test Cases and a guide, then save. Reload in a separate authenticated browser: the same permanent ID and links remain visible.
3. Edit notes, re-open **Details / history** and verify r001 stays unchanged. Revise the linked guide elsewhere; confirm the campaign's guide revision is still pinned until deliberately reselected.
4. Start → Close for review. A contributor cannot publish; a user with `publication_review` can publish (with at least one Test Case). Archive and restore; inspect the seven preserved revisions and read-only pipeline.
5. Switch explicitly to `?mode=demo`; the standalone fictional campaign workflows remain independent and functional. Server does not automatically load Demo data even if API requests fail.
6. Verify invalid links, obsolete `expected_revision`, unauthenticated writes, CSRF-free writes, maintenance-only accounts, and invalid lifecycle transitions are rejected without creating partial campaign revisions.

Migration `0011_campaigns` adds three relational tables and registers only technical descriptors; it does **not** alter or backfill existing business records. Restore/recovery uses the existing verified PostgreSQL + evidence backup workflow. No automatic destructive or semantic migration is involved.
