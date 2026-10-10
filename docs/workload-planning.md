# DAP-01: Deployment Planning workload foundations

This is the first increment of the larger Deployment & Adoption Planning
feature. It is an authenticated Server capability. It does **not** estimate
AI gains or actual employee productivity, issue licenses, manage tokens or
import Demo localStorage data.

## Install and open

On an isolated Server with a verified recovery point, run:

    docker compose up -d --wait --build
    docker compose exec -T api python manage.py migrate --noinput
    docker compose exec -T api python manage.py bootstrap_identity
    docker compose exec api python manage.py bootstrap_identity --username planner --role deployment-planner

The last command prompts for a password. Existing users are never given
planning privileges automatically. The independent deployment-planner role
has auth.planning_view and auth.planning_manage only, with no User Admin,
business_read, maintenance, publication, or platform permissions.

Sign in at http://127.0.0.1:8080/prototype.html?mode=server to see the
Deployment Planning panel. Standalone Demo remains entirely separate.
Ordinary contributors, reader users, reviewers, maintainers and user
administrators cannot read planning profiles, personal linked IDs, workload
assumptions or restricted labor rates. Re-run bootstrap_identity after a
deploy to seed new role permissions.

## Versioned Server model

- WorkloadProfile: permanent friendly wlp-word-word-word ID and UUIDv7,
  kind role, specialty, person or cohort.
- WorkloadRevision: append-only version with name, linked role/specialty,
  optional person account, headcount, hourly valuation, author and notes.
  Previous revisions cannot be updated or deleted.
- WorkloadAllocation: immutable link to the original real TaskNode,
  annual occurrence count, optional baseline human hours and exclusion.
  SQL triggers reject UPDATE and DELETE; concurrent updates require
  the exact expected revision and return HTTP 409 on conflict.

Direct Person or Cohort Task values REPLACE inherited role/specialty values.
When both inherited parents describe the same Task incompatibly, the
effective projection reports ambiguous and no numeric frequency.
A null occurrence is unknown, numeric 0 is explicitly zero, and
excluded=true removes an inherited Task. Matching inherited values count
once, not twice. Cohort headcount multiplies only resolved per-person
annual frequencies. Parent and child taxonomy Tasks are marked overlapping
rather than silently summed. A Person's labor valuation inherits its Role
then Specialty unless explicitly provided; unknown stays unknown.

## Server API

- GET /api/v1/planning/tasks: eligible permanent Task IDs/names.
- GET and POST /api/v1/planning/profiles: list and create.
- GET and PATCH /api/v1/planning/profiles/<profile_id>: current and revise.
- GET /api/v1/planning/profiles/<profile_id>/revisions: frozen history.
- GET /api/v1/planning/profiles/<profile_id>/revisions/<number>: original revision.
- GET /api/v1/planning/profiles/<profile_id>/effective: inherited Tasks,
  per-cohort frequency, source revision references and warnings.

POST/PATCH require same-origin Django session, CSRF and planning_manage.
GET requires planning_view. PATCH sends the full new workload list, plus
expected_revision such as r001; no partial in-place row update.

Example JSON create after defining a real Task in Task Management:

    {
      "kind": "role",
      "name": "Embedded developer",
      "hourly_rate_eur": "65.00",
      "workloads": [
        {"task_id": "tsk-<actual-existing-id>",
         "annual_occurrences": "12.00",
         "baseline_human_hours": "4.50"}
      ]
    }

Use null for unknown, "0.00" for explicit zero and excluded:true
with null frequency/hours for explicit exclusion.

## Acceptance

    docker compose exec -T api python manage.py makemigrations --check --dry-run
    docker compose exec -T api python manage.py test config.test_workloads -v 2
    node scripts/test-server-planning.js

The regular CI also checks independent Demo, immutable original evidence,
full recovery, native archive portability, and staging safety. As Workload
models live in config, the portable native archive includes their original
revisions and Task references without a special export workaround.

## Boundaries

No full Task-by-AI-configuration profitability matrix, three annualized
monetary opportunity slices, historical opportunity snapshots, external
tool account provisioning, access requests, quota/license budget or realized
profit estimates are implemented by DAP-01. See future-evolutions/
deployment-and-adoption-planning.md for the later increments.
