# FUT-11 — Effective published Run amendments and withdrawal

## Operational contract

Original `BenchmarkRun` / `CompositeBenchmarkRun`, closed `SessionCheckpoint`,
raw conversation, offer/guide/method pins, attachments and historical Campaign
publication manifests **never change** when a declared measurement is corrected.
`RunAmendment` is an append-only r002+ version chain, with an `audit_event`
pointer into the existing `CatalogAuditEvent` committed-change stream.
`r001` is the original stored Run. PostgreSQL immutability triggers refuse
UPDATE/DELETE of amendments; uniqueness and serializing Run row locks reject
conflicting versions.

An authenticated reviewer with `publication_review` may amend **only an
original Run already included in a current Campaign publication**, using:

- `POST /api/v1/runs/{id}/actions/corrected`: JSON
  `{"expected_revision":"r001","reason":"Correct recorded measurement","metrics_patch":{"quality_score":65},"outcome":"failed"}`.
  Any supplied metric patch is validated. Allowed fields are quality/utility
  scores, declared human/agent time components, token count/multiplier and
  original manual EUR cost; derived totals are recalculated. For tariff-priced
  Runs, raw `cost_eur` is never manually amended. An optional source-keyed
  `observations` payload is quoted against the **original pinned offer
  revisions** using the same metering engine as Run close. It must contain
  every required meter; no unknown or missing values are coerced to zero.
  Corrections to narrative, guide, method, raw checkpoint or evidence files are
  deliberately excluded; make a new Run for new physical evidence.
- `POST /api/v1/runs/{id}/actions/withdrawn`: JSON
  `{"expected_revision":"r002","reason":"Declared evidence demonstrably invalid"}`.
  A Run withdrawal is **terminal** for that original Run, requires an
  explanation, and cannot be reversed by simply correcting or republishing
  the same ID. Historical reviewer access remains subject to privileges.
- `GET /api/v1/runs/{id}/revisions`: private, role-gated amendment history
  with exact immutable source versions, original/raw measurement and actor,
  date, justification and audit event pointer.

Mutations use CSRF and an optimistic `expected_revision` (`409` if stale).
Malformed/untrusted/incomplete corrections return `400`. Workgroup editors
without reviewer permissions cannot revoke a published result; ordinary users
cannot access private Run history, draft or withdrawn source records.
A consumer correction to accepted vs failed DoD is an explicit authorized
supersession; a complete failed DoD remains negative evidence.

## Shared current-effective evidence authority

`publication_services.effective_ids()` delegates to the single
`run_lifecycle_services.effective_ids()` membership/withdrawal selector.
The latter starts from last active Campaign publication decisions and masks
all Run-specific withdrawal events; it does not infer membership from a
Campaign status, any matrix cell or editorial Recommendation.
Run details/list, active manifest and attachments, measured AI Solution
presence, Results Explorer and matrix all use the same eligibility rule.

Public / current responses show the latest **declared** correction, marked
by `revision`; `raw_session_state` and original immutable facts are not
rewritten. Workgroup views can inspect the original revision chain. A withdrawn
Run is absent from current public Run URLs, lists, results/score inputs and
effective manifest selection, while unrelated published Runs remain. The
immutable Campaign publication remains inspectable in historical, privileged
Campaign revisions, including formerly published pin references. Excluded
Run identifiers are not leaked by the ordinary active manifest API.

Editorial Recommendations are **not** an independent measured-score
authority. Their existing immutable Run pins now also retain which Run
amendment revision the editor reviewed. If a pinned Run is later withdrawn,
unpublished or superseded, the published Recommendation is marked
`evidence_freshness: stale`, `review_needed: true` and
`eligible_for_current_suitability: false`. Public descriptive detail gives
only a safe unavailable placeholder for noncurrent source IDs, not their raw
metrics. An authorized editor may create a new version and submit it for
review; old versioned rationale remains an historical editorial decision.
There is no automatic positive ranking inferred from incomplete, failed,
stale or theoretical evidence. Prospective DAP read models (FUT-13, #87)
must consume this exact authority, never historic pinned originals.

## Deployment and rollback

Migration `0025_run_amendments` is additive: two existing immutable Run
tables and campaign/recommendation source histories are untouched. It creates
Run amendments, audit links and optional acknowledged revision pins on
new Recommendation revisions. No backfill or invented historic corrections.
New code can read preexisting r001 originals without creating any amendments.

Rollback to an earlier application release **must be blocked** while any
RunAmendment exists: that release does not apply withdrawal in read models,
and could misleadingly serve recalled evidence. Database schema rollback
would erase legally/audit-relevant corrections and is not an acceptable
production downgrade. Use verified staged recovery, accompanied by an
effective-publication suppression gate, rather than silently restoring a
pre-revocation view. No production GO is granted by green CI.

Run focused tests with disposable PostgreSQL:

`python manage.py test config.test_run_lifecycle`

Cross-module regression suites: `config.test_publication`,
`config.test_recommendations`, `config.test_campaign_matrix`,
`config.test_evaluations`, `config.test_runs` and
`config.test_composite_runs`. Workgroup UI remains Server-only and
the independent offline Demo is not coupled to real Run data.
