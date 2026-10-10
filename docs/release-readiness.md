# PLAT-32 — Dual-mode Server release acceptance

**Release status: NO-GO until operational safety gates are witnessed.** A
green CI run proves the automated campaign but cannot count as human
inspection of a staged migration or an approved production replay.

## Reproducible automated campaign

From a reviewed, pinned Git commit, trigger the existing platform-smoke
GitHub Actions workflow:

    gh workflow run platform-smoke.yml --ref main
    gh run list --workflow platform-smoke.yml --limit 5
    gh run download <RUN_ID> -n plat-32-readiness-<RUN_ID>-1

The final success-gated step publishes report.json and report.md as
workflow artifacts and in the Actions job summary. Missing report,
failed workflow or unmatched commit is **not** a pass. The report
intentionally remains NO-GO until the independent human release gates
are completed.

### Acceptance coverage

- #5, #25: fresh authenticated Server begins with zero business records,
  but immutable versioned technical schemas are initialized.
- #2, #28: real account/session/role permissions and CSRF; no fake login.
- #9–#23: Tasks, Test Cases, Campaigns, Sessions, original measurement,
  individual/composite Runs, attached original evidence, evaluated results,
  reviewed/public Recommendations and their immutable history.
- #30/#31: portable original ZIP, independent offline integrity validator
  and Server-to-disposable-Server restoration, idempotent retry and drift
  refusal.
- #34/#29: coordinated PostgreSQL + original evidence restore in a
  completely isolated target; exact hashes, counts and real authorized
  evidence download; tampered/missing data rejected.
- #35: snapshot into temporary Server, registered v1-to-v2 migration,
  CI verifies original v1 is immutable, acceptance without actual GUI
  inspection is REFUSED, then reject/discard and recreate twice.
- #26: automated negative tests on proof, recovery, rollback/retry,
  immutable receipts, permissions and stale source fingerprints.
- #1: same frontend loads from Python http.server without Docker; Demo
  fake localStorage remains independent; no Server fallback/sync.

New config.test_release_readiness tests an integrated *cross-role*
workflow using real Server APIs and PostgreSQL: contributor -> Task ->
Test Case -> Campaign -> Session -> Run -> original attached evidence ->
Evaluation -> draft Recommendation, independent authorized reviewer
publication -> fresh reader browser session sees published decision and
downloads original bytes. The test also checks historical exact revisions,
unknown JSON fields, permission boundaries and stored measurement metrics.

Reproduce focused tests on a disposable Server, not a production system:

    python3 -m unittest discover -s scripts -p test_release_acceptance.py -v
    docker compose exec -T api python manage.py test config.test_release_readiness -v 2
    docker compose exec -T api python manage.py makemigrations --check --dry-run
    bash scripts/smoke-platform.sh

These are supplemental; only the complete GitHub workflow confirms the
whole automated regression.

## Closed development tickets do NOT approve production

**2026-10-10 owner decision:** PLAT-35, PLAT-26 and PLAT-32 are closed
as **technically delivered and CI-tested**, while their real-world manual
acceptance is explicitly deferred until there is an actual operational
deployment to validate. Closing the GitHub tickets does NOT change
the CI-generated NO-GO release decision and does NOT turn staging approval
or production migration safety checks off.

Before any operational release, the operator must still complete ALL
manual tasks below with reviewable evidence. Failed acceptance creates
new corrective GitHub issues linked to the original PLAT tickets; a
production deployment must not be inferred from issue states.

PLAT-33 was closed on **2026-10-10 as an explicitly MOCKED code-only
delivery**, not as genuine source onboarding. The staging-only mock adapter
and its synthetic fixture are not approved external data. Source-discovery
tooling is
documented in [external-source-onboarding.md](external-source-onboarding.md);
the actual source-specific real-data adapter remains **unimplemented**
until its owner/source/type is selected, and any production intake remains
blocked until release approval is independently recorded. A new
source-specific GitHub ticket is required.

## Mandatory operational acceptance before GO

1. #35: Restore a named verified DB-and-original-evidence snapshot into
   an isolated staging Server. Using a REAL browser and the actual Server
   frontend (/?mode=server), inspect old and new Model revisions, unknown
   fields, evidence downloads, IDs and history. Record candidate ID,
   full source recovery ID and manifest hash, build SHA, migration SHA,
   reviewer, time, notes and an explicit accepted/rejected decision via
   the built-in frontend-checked PLAT-35 verdict mechanism. A CI curl or
   banner test does not count. Also prove reject/discard/recreate leaves
   source records and original evidence unchanged.
2. #26: Replay only that pinned accepted migration artifact against an
   independently approved production-like disposable dataset using the
   existing signed promotion procedure. Take and verify a NEW independent
   coordinated recovery point immediately before apply; validate saved
   signing proof, original hashes, UUID/revision histories, schema receipts,
   restart/retry behavior and rollback readiness. NEVER replace a live
   production database with the staging clone. Do not mistake unit tests
   of the promotion guard for actual replay acceptance.
3. #32: Independently review the reproducible CI report, full recovery
   manifests, signed/manual staging verdict, operational promotion/receipt
   evidence, and rollback drill. The accountable release operator must
   record a go/no-go verdict with source build SHA, exact candidate ID,
   approved artifact and recovery hashes, timestamp and any blockers.

On failure: freeze writes, recover PostgreSQL AND original evidence files
from the independently verified coordinated recovery point. Do not assume
schema operations have reversible SQL. See the existing runbooks:
docs/migration-staging.md, docs/migration-production.md,
docs/native-archive-restore.md and docs/local-installation.md.

## Report safety and scope

scripts/release_acceptance.py is executed as the LAST regular CI step,
after every relevant domain/recovery/Demo test has succeeded. It checks
the live GitHub commit/run identity plus machine-readable on-disk
staging candidate IDs, exact shared recovery manifest SHA, original
blob hash inventory, restored authenticated download and immutable
recreation source identity. Unavailable or incompatible evidence makes
CI fail, not produce a fabricated pass. Artifacts include only sanitized
test identifiers/hashes and explicit blockers: no ZIP, private customer
files, backup dumps, keys or passwords in the public Actions artifact.

An automated script cannot certify an unperformed real browser review or
approve production mutation. Its report is always NO-GO until actual
operator checks and release authority are completed. The owner's decision
to close the implemented #32 development ticket does not waive the pending
manual checks, and does not establish operational readiness.
