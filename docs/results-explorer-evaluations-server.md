# PLAT-21 · Results Explorer and versioned evaluations (Server)

## What is recorded

Results Explorer reads persisted original **measured individual Runs**, **measured composite Framework workflow Runs**, and **theoretical Forecasts** as **three separate types**. Task-centred and candidate/solution-centred views are read-only matrices. They do not infer missing Test Cases, aggregate unknown values into zero, average across dissimilar methods, or redistribute composite team results among participant AI Solutions. Published Forecasts are labelled `THEORETICAL`; their predicted values are never counted as measured scores.

An **Evaluation** is a fourth, explicitly interpretive record (`evl-<friendly-id>`, UUIDv7 catalog identity), separate from both measured runs and predictions. The new additive migration `0018_versioned_evaluations` registers `evaluation` and a versioned `evaluation_scoring_method` descriptor and creates the following protected tables:

- `EvaluationSnapshot`: exact immutable Evaluation CatalogRevision and FK to scoring method version, with its exact configuration. Supported v1 is descriptive comparison only; there is **no new aggregation/ranking algorithm**.
- `EvaluationIndividualRunPin`: immutable FK to each individual BenchmarkRun, FK to the precise original experimental method `ObjectTypeVersion`, and a deep-copied input context recording run ID, source metrics, immutable campaign/session/Test Case revisions, original experimental method descriptor, original result and identity.
- `EvaluationCompositeRunPin`: same guarantees for composite Framework run; its input context has `solution_id: null` and records `framework_id`, preventing aggregate workflow results from being interpreted as individual measurements.

PostgreSQL triggers validate Evaluation-to-revision type, scoring method type/version, Run-to-method identity, and reject mutation/deletion of the new source relationships. All references are `PROTECT` FKs, with distinct per-snapshot uniqueness constraints. Earlier Evaluation revisions, original Run metrics, captured evidence and published theoretical Forecasts are never edited when a new interpretation is saved.

### Comparability and unknown data

Each Evaluation carries `assessment` (`supported`, `unsupported`, `inconclusive`), human notes, limitations, optional extensible metadata and a pinned `scoring_config`:

```json
{
  "selected_metrics": ["quality_score", "cost_eur"],
  "comparison_basis": "descriptive_only",
  "extensions": {"uncalibrated": null}
}
```

All selected measured fields are checked without substituting numbers: when any selected value is missing/null, the persisted `missing_fields` identifies it. Differences between the exact original Run experimental-method IDs or method descriptors are reported as `mixed_methods`; both conditions yield `mixed_methods_and_incomplete_metrics`. Comparable means **only that these specific structural checks found no differences or unknown selected values**, not that the experiment is statistically equivalent or that the setup has been validated. A change in metric selection or scoring method appends a new Evaluation revision with its own input snapshot and comparability status; it does not recompute any past score.

## REST API

| Request | Description |
| --- | --- |
| `GET /api/v1/results/explorer?view=task` | Task × candidate matrix |
| `GET /api/v1/results/explorer?view=solution` | Candidate × task matrix (measured solutions, composite Framework and theoretical Forecasts are distinct) |
| `GET /api/v1/results/explorer?kind=individual|composite|theoretical` | Filter evidence class; no composite-to-Solution inflation |
| `GET /api/v1/results/explorer?task_id=tsk-*&solution_id=sol-*&campaign_id=cmp-*` | Strict real Server ID filters; incompatible combinations refused |
| `GET /api/v1/evaluations` | Read evaluation summaries with full pinned inputs |
| `POST /api/v1/evaluations` | Contributor-only immutable Evaluation `r001` creation |
| `GET /api/v1/evaluations/<evl-id>` | Latest evaluation |
| `PATCH /api/v1/evaluations/<evl-id>` | Contributor-only new revision, mandatory `expected_revision` |
| `GET /api/v1/evaluations/<evl-id>/revisions` | Original chronological interpretation history |
| `GET /api/v1/evaluations/<evl-id>/revisions/<number>` | Exact historical interpretation, including original method and metrics |

POST example, with real original measured IDs, not Forecast IDs:

```json
{
  "name": "SPI driver controlled evidence appraisal",
  "run_ids": ["run-real-original-A", "run-real-original-B"],
  "scoring_method_version": 1,
  "scoring_config": {"selected_metrics": ["quality_score", "cost_eur"],
                     "comparison_basis": "descriptive_only"},
  "properties": {"assessment": "inconclusive",
                 "notes": "Evidence supports partial conclusions",
                 "limitations": "Few TCs and unknown flat-rate inference costs"}
}
```

For a new interpretation, PATCH the current object with `expected_revision:"r001"`, altered evaluation notes, metric selection and/or run IDs. This appends `r002`. Comparing `GET /revisions/1` and `GET /revisions/2` must show both original input contexts intact. A stale expected revision gives HTTP 409, malformed/broken/nonexistent Run IDs give HTTP 400, missing CSRF is rejected, and a role without business access cannot read or write. Only contributors write; ordinary signed-in readers can inspect measured results and saved evaluations. Lists are bounded at 500 records and individual evaluation input sets at 40 runs.

## Frontend and reproducible verification

Open `/?mode=server` and sign in with a real workgroup account. Scroll to **Results Explorer · observed and theoretical**. Switch orientation Task-centred / Solution-centred. Filter by task, individual/composite/theoretical scope, real measured AI Solution and campaign. A run row shows original measured quality, cost, human duration, method version and **Unknown / not measured** when null. Composite rows remain Framework-scoped. Theoretical rows display their *own* projected values, `THEORETICAL FORECAST` and uncertainty, with no measured fields promoted from them.

Under *Versioned evaluations*, create an evaluation by selecting real `run-*` IDs. Review/submit descriptive assessment and selected metrics; reload the page or a new browser to see the saved record. Reinterpret it and open **Details / immutable history**: the older revision's metrics/protocol inputs stay unchanged. The measured Source Run endpoint is linked in the table and is unchanged. A damaged or unknown real Run reference must raise an explicit API error rather than silently producing a fabricated result.

Check that independent `/?mode=demo` still works without Docker or any Server login: its original seeded-fake browser `localStorage` prototype is unchanged. The Server adapter uses authenticated PostgreSQL exclusively. Staging has its own volume/data isolation and mounts the same static frontend assets as Server.

To verify:

```bash
docker compose up -d --wait --build
docker compose exec -T api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_runs config.test_composite_runs config.test_forecasts config.test_evaluations -v 2
node scripts/test-server-results.js
```

The platform CI additionally covers original evidence integrity, backups, offline DB+blob recovery, staging reject/recreate, Docker volume retention and offline Demo. Migration adds only empty versioned tables and registry rows; no historical source Run, original proof or business configuration is converted. Further model/protocol migrations remain governed by #35 and #26.
