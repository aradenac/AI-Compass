# PLAT-20 — Theoretical Forecasts and empirical validation campaigns

**Purpose.** Provide an independent task-scoped theoretical AI setup (Model + Provider + Harness) that can be planned and reviewed before a real controlled Run exists. Forecasts have **no measured AI Solution identity** and never write run metrics. Only #15/#16 controlled Run closure produces observational evidence.

## Durable types and invariants

The additive `0017_theoretical_forecasts` migration registers a `forecast` ObjectTypeVersion, allocates permanent `fct-*` plus UUIDv7 identity through existing CatalogItem/Revision and appends four immutable, FK-guarded relational tables:

- `ForecastSnapshot` pins the exact Task/Task revision, Model/Provider/Harness and their exact revisions and full extensible JSON configuration at each forecast revision. Numerical theoretical metrics, explicit unknown/null, rationale, assumptions and uncertainty live in the unchanged catalog revision.
- `ForecastWatchPin` pins each Watch Entry and its exact historical revision (not a mutable latest pointer). Staging requires cited Watch evidence via the #18 immutable original Research Source/Watch relationships. Publishing additionally requires those exact Watch revisions and their linked source revisions to be publicly visible.
- `CampaignForecastOrigin` pins a new validation Campaign revision to the **exact original staged/reviewed/published ForecastSnapshot** and frozen Task revision.
- `CampaignForecastWatchPin` preselects the exact originating Watch signals in the validation campaign. Every later campaign revision preserves all this historical provenance.

All new FKs are protected against deletions, PostgreSQL checks cross-table type/revision consistency, and SQL triggers reject every UPDATE/DELETE on the four new tables. The existing immutable CatalogRevision/audit engine is reused, not copied.

**Validation lifecycle:** `draft → staged → reviewed → published`. Stage is a contributor action requiring at least one Watch Entry backed by an original Research Source, explicit rationale and uncertainty. Review is a separate reviewer-only action with mandatory justification. Publishing is reviewer-only and requires all pinned Watch Entry and Research Source revisions to be published. Material edits append a new **draft** revision, invalidating approval while retaining the historical staged/published snapshot. Predictions, including nulls and unknown extensible fields, remain unchanged on every earlier revision. Publishing never qualifies a model or produces a measured AI Solution.

## REST contract

| Operation | Endpoint |
| --- | --- |
| List / create | GET / POST `/api/v1/forecasts[?task_id=tsk-*]` |
| Read / edit | GET / PATCH `/api/v1/forecasts/<fct-*>` |
| Read immutable history | GET `/api/v1/forecasts/<fct-*>/revisions` |
| Read historical revision | GET `/api/v1/forecasts/<fct-*>/revisions/<number>` |
| Stage / rework | POST `/api/v1/forecasts/<fct-*>/actions/stage|rework` |
| Review / publish / unpublish | POST `/api/v1/forecasts/<fct-*>/actions/review|publish|unpublish` |
| Start planned validation | POST `/api/v1/forecasts/<fct-*>/campaigns` |

Example draft:

```json
{
  "name":"KSZ8851SNL embedded driver candidate",
  "task_id":"tsk-real-task-id",
  "component_ids":{"model":"mdl-real-model","provider":"prv-real-provider","harness":"hrn-real-harness"},
  "configuration":{"reasoning":"high","tools":["shell"],"future":null},
  "watch_links":[{"id":"wat-real-persisted-watch","revision":"r005"}],
  "properties":{
    "rationale":"Published vendor report plus cited benchmark suggest benefits",
    "uncertainty":"No comparable internal Twister regression runs",
    "confidence":"low",
    "assumptions":{"engineering_rate_eur_h":60,"unknown":null},
    "predicted_metrics":{"quality_score":78,"acceptance_probability":null,
      "autonomy_score":55,"human_minutes":90,"ai_cost_eur":null,"tokens":null}
  }
}
```

Properties are versioned; unknown JSON fields are preserved, never silently ignored. A missing predicted cost is **null, never zero**. Scores are bounded 0–100; durations/costs nonnegative and nullable. `evidence_class:"theoretical"` and `measured_solution_id:null` appear explicitly in every returned forecast.

Stages require `{"expected_revision":"r001"}`; reviewer `review` additionally requires `"review_notes":"..."`. Every action appends a revision and reports a 409 on stale expected revision. A user who can only read permitted business content may fetch published forecasts but not internal current or historical revisions, raw generic catalog details or private evidence URLs. Staged/reviewed remain available to workgroup contributors and reviewers for internal comparisons.

To validate a staged forecast:

```json
{
  "forecast_revision":"r002",
  "name":"Controlled SPI driver validation",
  "objective":"Test forecast assumptions using original Twister evidence",
  "test_case_ids":["tcs-real-case-id"]
}
```

The Server returns HTTP 201 and a normal `planned` **task-centred** Campaign containing immutable `forecast_origin` and original pinned `watch_links`. The proposed model/provider/harness revisions and configuration assumptions are prefilled in `configuration.forecast_candidate` and permanently backed by the Forecast's FK snapshot. No campaign is created from a Draft; no measured Run or Solution is fabricated. The original forecast survives later catalog, Watch, task and campaign revisions. Campaign sessions and Runs continue to follow #14/#15, using independently recorded outcomes.

## Server frontend and acceptance

Open `/?mode=server` and sign in as contributor. In *Technology Watch · Theoretical Forecasts*, draft a task-linked setup and choose its exact Watch Entries. Stage it with cited evidence and explicit uncertainty; as reviewer, add justification and review/publish once its cited Watch/Research Source original revisions are publicly visible. Compare only alongside (never pooled with) **measured** Benchmark Runs. Choose *Validate as new campaign* and open the generated Campaign through the existing Benchmark Workspace; add Test Cases if needed, then record ordinary controlled Sessions/Runs.

The same `prototype.html` remains independently usable via `/?mode=demo` and standalone without Docker. Server never reads or imports seeded browser data. Real database starts without Forecast instances. Staging uses the same frontend script but its own isolated database/evidence volumes.

Reproduce the automated checks:

```bash
docker compose up -d --wait --build
docker compose exec -T api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_watch config.test_forecasts config.test_campaigns config.test_runs -v 2
node scripts/test-server-forecasts.js
node scripts/test-server-watch.js
```

Manual negative checks: unknown task/component/Watch, unsigned/missing CSRF, unqualified Watch evidence, stale revisions, unauthorized reviewer and attempted direct access to internal forecast history. After a staged campaign starts, edit the Forecast's predictions and the components; verify both the original forecast revision and campaign origin retain their exact historical content. Repeat with a real completed Run and confirm the forecast's predicted metrics remain unmodified.

**Scope boundary:** no automatic forecasting, no inferred metric weights, no conversion to observed results, no fake Demo import, no promotion of the staging database. The operational migration/recovery gates #35/#26 are separate from this additive empty-schema implementation.
