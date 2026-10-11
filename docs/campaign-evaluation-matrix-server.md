# FUT-08 — Campaign Evaluation Matrix (Server + offline Demo)

## Purpose and identity

The **Workgroup Benchmark Workspace** owns Task-scoped planning. A campaign has one permanent `cmp-*` identity, mutable *current* plan and immutable `CatalogRevision` history. Under `properties.matrix_plan` (optional), each version records:

- **Configuration assignment**: stable `evl-*` public ID; Task ID and pinned revision; `individual` pinned Model/Provider/Harness revision IDs, configuration version and settings; or `framework` selected participant IDs and frozen participant version/setting snapshots.
- **Candidate evaluation**: distinct `evl-*` ID, configuration assignment ID, Test Case ID, plan decision, immutable decision/waiver history, first-introduced plan revision.
- **Decision**: `selected`, `not_selected`, or `waived`. Waivers require a justification while the obligation is selected; waiver author, timestamp and source revision are appended. Reinstatement creates another campaign revision, not an edit to an earlier snapshot.

The existing legacy campaign mode and method versions remain readable, and campaigns without `matrix_plan` are not retroactively reinterpreted as matrix evidence. Both `task_centred` and `solution_centred` APIs remain unchanged for legacy callers. In current Workgroup UI, create a *task-centred* campaign with an anchor Task, then add any Task-scoped AI configurations and relevant Test Cases using the matrix editor; that is the supported multi-Task extension without changing the registered experimental-method schema. No global Task × configuration cross-product occurs: only Tests belonging to the specifically associated Task generate candidate cells.

### Counts and statuses

- **Pending**: selected, no active nor closed attempt.
- **In Progress**: selected, ≥1 active checkpointed Test Case attempt and no closed Run.
- **Evaluated**: selected, ≥1 immutable closed Run. A failed DoD is still evaluated **negative evidence**. Repeated Runs are preserved individually.
- **Waived**: selected obligation explicitly released by attributable written decision. Existing measured evidence, if any, remains available but never changes the waived plan decision into measured coverage.
- **Not Selected**: candidate deliberately outside the plan; no execution obligation or measured credit.

`full_plan_complete` is independent of any publication eligibility: it means no **selected** Pending/In Progress cells. `experiment_coverage` uses selected obligations as denominator, excludes Waived/Not Selected and reports measured Run count separately. This planning projection is not the FUT-10 publication permission gate. Pending plan cells do **not** prevent publishing an independently eligible completed Run subset once the dedicated publication feature exists.

## API

| Method and path | Purpose |
| --- | --- |
| `GET /api/v1/campaigns/<id>/matrix` | Current matrix, Task associations, derived attempt status, separate coverage summary |
| `GET /api/v1/campaigns/<id>/matrix?revision=rNNN` | Historical immutable plan decisions with current observed attempts **labeled as a live projection** |
| `PATCH /api/v1/campaigns/<id>/matrix/edit` | CSRF-protected business_write; requires `expected_revision` and an operation, returns new immutable campaign revision |
| `POST /api/v1/campaigns/<id>/sessions` | Optional `evaluation_id` for legacy, **required** for campaigns with a matrix; pinned configuration and selected Test Case must match |
 
Example operation to add a Task-associated individual AI configuration:

```json
{
  "expected_revision": "r001",
  "operation": {
    "action": "add_configuration",
    "kind": "individual",
    "task_id": "tsk-known-task",
    "label": "Cline + Provider + Model, v1",
    "component_ids": {
      "model": "mdl-real-model",
      "provider": "prv-real-provider",
      "harness": "hrn-real-harness"
    },
    "configuration_version": "1",
    "settings": {},
    "test_case_ids": ["tcs-task-test-1", "tcs-task-test-2"]
  }
}
```

To add newly eligible Test Cases, use `action: "add_cases"`, `configuration_id`, `test_case_ids`. All assignments to the same Task receive *new* selected default cells while their existing decisions remain intact. To change a cell, use `{"action":"decide","evaluation_id":"evl-...","decision":"not_selected"}` or `waived` with `reason`; use `selected` to reinstate. Optimistic conflicts return HTTP 409, invalid scope/waivers return 400, unauthorized writes 403. Existing Server permission separation and CSRF are retained.

## Closure and explicitly partial review

For a versioned matrix campaign, ordinary `POST /api/v1/campaigns/<id>/actions/close` rejects outstanding selected Pending/In Progress obligations (HTTP 409). Workgroup can deliberately request a **partial review** using `{"expected_revision":"rNNN","partial_review":true}`. This transitions to `under_review` without claiming full-plan completion; the new immutable campaign revision records `properties.review_scope: "partial"`. When no selected obligation is outstanding, normal close records `"full"`. Subsequent evidence-subset publication validation remains FUT-10, which must check actual selected completed Runs independently of this flag. Reopening can expand a formerly published campaign without altering historical evidence.

## Reopening, provenance and limits

Reopen published/under-review campaigns using the *existing* controlled lifecycle; editing generates a new immutable campaign plan revision while preserving earlier review/publication state and historic Run references. A Test Run is linked to a candidate evaluation by an `evaluation_id` stored in its **first immutable SessionCheckpoint**. Its canonical configuration comes from the version-pinned matrix assignment, not current catalog revisions. Current published Runs are never altered by matrix decisions. Untagged legacy Runs are not guessed into individual matrix cells.

Framework configurations are **composite columns**: they pin selected participant identities and original trios/settings. They must not be represented as independent scored Model configurations. Their completion is based on the collaborative Run as a whole.

The matrix is size-bounded (128 configurations / 1024 cells), has stable readable IDs with a random collision-resistance suffix, validates Task ↔ Test Case membership, is not automatically populated from the full Task tree, and never fabricates a missing measurement. Current status projection joins bounded campaign sessions to immutable finalized individual/composite Runs.

## Demo and rollback

The existing single-file Demo retains its **fictional, browser-local** campaigns. It adds an independent Task-scoped planning matrix, deliberate selection/waiver forms and immutable original Run linkage. No real Server records are imported or fetched from Demo, and legacy mock campaigns remain readable. Server remains empty of business fixtures on fresh deployment.

**No relational migration required**: the plan is an optional additive field in already-immutable `Campaign CatalogRevision.properties` and exact Test Run identity is pinned in the existing immutable initial checkpoint JSON. Rollback to the prior application disregards the optional plan and evaluation fields but **does not remove** historical JSON revisions or Run data. Do not use the old interface to add new matrix Runs after rollback; retain snapshots and restore a compatible application version instead.

## Verification

```bash
docker compose exec -T api python manage.py test config.test_campaigns config.test_campaign_matrix config.test_sessions config.test_runs config.test_composite_runs -v 2
node scripts/test-campaign-matrix.js
node scripts/test-server-campaigns.js
node scripts/test-server-sessions.js
```

GitHub Actions runs these checks as part of the integrated platform workflow, including migration/recovery and frontend mode separation. Passing CI is **not** a production go-live decision; operator staging, browser/manual acceptance, recovery verification and signed release remain separate.
