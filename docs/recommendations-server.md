# PLAT-22 — Evidence-linked Recommendations (Server)

A Recommendation is a manually-reviewed decision about an **individual measured AI Solution** for an engineering Task, not a new Run or an automatically computed leaderboard. It lives under **Knowledge & Collaboration**, never under Experiments. Its original evidence is source Run (and optional Evaluation) data; no original experimental measurements or evidence file is rewritten.

## Persistent model, safe revisions and authorization

Additive Django migration `0019_recommendations` registers a `recommendation` schema in `ObjectTypeVersion` and creates two new append-only, SQL-trigger-protected tables:

- `RecommendationSnapshot`: FK to the exact Recommendation `CatalogRevision`, current Task and pinned Task revision, measured `MeasuredSolution` plus its pinned catalog revision, optional **exact EvaluationSnapshot revision**, and separate reviewer FK/timestamp. This always describes the original decision context, regardless of later taxonomy/campaign/model changes.
- `RecommendationRunPin`: FK to each exact original **individual** BenchmarkRun. PostgreSQL validates every inserted Run against the snapshot's Task and Solution; **CompositeBenchmarkRun is deliberately excluded**. The existing run evidence retains original `EvidenceBlob` SHA-256 and immutable run/evidence attribution. Every recommendation revision owns new pins; no UPDATE or DELETE allowed.

Objects have permanent `rec-<simple words>` IDs and UUIDv7 internal IDs, validated schema v1, append-only `CatalogRevision`, immutable and attributable `CatalogAuditEvent`. A new Server starts with no recommendations and no fake seeds. Existing Run/Campaign/Forecast/Evaluation schemas and measurements are not converted.

Lifecycle:
1. Contributor creates **draft** with required rationale, Task ID, measured Solution ID, at least one true individual Run ID matching that Task/Solution, and optional exact Evaluation ID + `r001` revision. Only real Server evidence is accepted. Source-evaluation membership is checked (selected Runs must be present in that exact Evaluation revision).
2. Contributor edits via optimistic `expected_revision` or uses **submit** to move to `in_review`. Editing a published recommendation creates an entirely new **draft** revision and resets the review metadata, **without withdrawing the last published revision**.
3. A user with `auth.publication_review` publishes a submitted recommendation with a required substantive `review_note`. A single authorized reviewer is enough: no new multi-approver consensus process. Publication records that user's FK/name, exact timestamp and original evidence pins. No silent auto-publication.
4. A reviewer may explicitly **unpublish** the live recommendation with a required reason, regardless of whether the workgroup is preparing a new draft. This appends an `unpublished` revision, suppresses all earlier public history and file access, and **does not delete** the original approved revision.
5. Later evidence is a read-side *review signal*, not automatic modification: if another real individual Run for the exact Task + Solution is closed **after** the published revision, the public payload reports `review_needed: true`, the precise `new_run_ids`, and `contradictory_run_ids` for failed outcomes. A successful new Run also triggers re-review as newly available evidence (no invented quality thresholds). Original Decision revision is unchanged. New Test Cases and reopened Campaigns use their usual execution semantics.

Access: a signed-in `auth.business_read` reader sees **only the last live published revision**, even when a newer draft/in-review revision exists. Drafts, unreviewed revisions and their evidence attachments cannot be fetched by guessing exact URLs. Contributor with `business_write` sees and creates private revisions; reviewer with `publication_review` can inspect internal records and approve/withdraw publications. All writes are CSRF-protected and transactional. Generic raw catalog and direct `/api/v1/evidence/<uuid>[/download]` endpoints respect the same visibility, using exact attachment revision; an early draft document never becomes public just because the object is later published.

## API

| Action | Endpoint |
| --- | --- |
| Browse/filter | `GET /api/v1/recommendations?task_id=tsk-*&solution_id=sol-*` |
| Create | `POST /api/v1/recommendations` |
| Read current visible / edit draft | `GET / PATCH /api/v1/recommendations/<rec-id>` |
| Immutable history | `GET /api/v1/recommendations/<rec-id>/revisions` |
| Exact historic revision | `GET /api/v1/recommendations/<rec-id>/revisions/<number>` |
| Submit for review | `POST /api/v1/recommendations/<rec-id>/actions/submit` |
| Review and publish | `POST /api/v1/recommendations/<rec-id>/actions/publish` |
| Withdraw publication | `POST /api/v1/recommendations/<rec-id>/actions/unpublish` |

Create example (replace placeholder IDs with persisted real Server IDs):

```json
{
  "name": "KSZ8851SNL driver engineering",
  "task_id": "tsk-real-engineering-task",
  "solution_id": "sol-real-measured-solution",
  "run_ids": ["run-original-controlled-test"],
  "evaluation_id": "evl-real-evaluation",
  "evaluation_revision": "r002",
  "properties": {
    "decision": "conditional",
    "rationale": "Known working SPI implementation with original Twister evidence",
    "limitations": "Not yet qualified across the complete HIL suite",
    "extensions": {"unknown_future_field": null}
  }
}
```

A successful response includes exact task/solution/evaluation revision IDs, per-source Run ID/outcome/raw original metrics/method version/original evidence IDs and hashes, reviewer attribution and current review flags. The original Evaluation is **referenced**, not reinterpreted or modified. An invalid/nonexistent source or incompatible Solution/Task returns HTTP 400; stale `expected_revision` returns HTTP 409. No access returns 401/403/404 according to the existing authorization gates.

Submit: `{"expected_revision":"r001"}`. Publish: `{"expected_revision":"r002","review_note":"Reviewed Twister evidence and limitations"}`. Withdraw: `{"expected_revision":"r003","review_note":"New failed controlled run"}`.

## Functional smoke

```bash
docker compose up -d --wait --build
docker compose exec -T api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_recommendations -v 2
node scripts/test-server-recommendations.js
```

In the existing `/?mode=server` frontend, sign in as a contributor, create a real controlled individual Run, and open *Knowledge & Collaboration · Recommendations*. Link the Task/Solution/Run and optional saved Evaluation; create a draft and reload. As ordinary reader, check that the draft is absent, including guessed direct version and evidence URLs. Submit for review and sign in as a reviewer; publish it with an explicit written rationale. The reader can now inspect the original evidence and reviewer details. As contributor, revise the recommendation: the reader still sees the **earlier published** decision while the workgroup sees the newer draft. Close another failed individual Run for the same Task/Solution: the published view reports exact new/failed Run IDs and a review requirement, but its immutable historical rationale stays intact. As reviewer, withdraw it; public read access disappears, while every historical revision remains inspectable by authorized workgroup members. Test CSRF, permission denial, stale revision conflict, composite-only evidence rejection and original SHA-256 download.

Finally, stop Django and open the same static `/?mode=demo` prototype: the original independent seeded `localStorage` journey continues without network or Server. Server has no import/sync/fallback from Demo. Production and isolated staging mount the same new frontend script, but have independent DB/evidence volumes. Coordinated backup/recovery CI continues to test originals; no production data transformation, staging DB promotion or speculative automatic decision algorithm was introduced.
