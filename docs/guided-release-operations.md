# Guided release operations — FUT-21

A small operator entrypoint that composes the already-verified PLAT tools instead
of introducing a second migration engine, Kubernetes, an event bus or a separate
release database. It turns the existing pieces — the coordinated release manifest
(`scripts/build_coordinated_release.py`), migration staging/promotion
(`scripts/migration_stage.py`, `scripts/migration_promote.py`) and the
coordinated recovery point (`scripts/full_recovery.py`) — into a guided workflow
whose unsafe transitions are refused *before* any live data changes.

```bash
scripts/release_ops.py check   --release ./artifacts --state release-state.json
scripts/release_ops.py status  --state release-state.json
scripts/release_ops.py stage   --release ./artifacts
scripts/release_ops.py deploy  --release ./artifacts --state release-state.json \
                               --operator ops@example --recovery-point prod.dump \
                               --approve r0.6.0+abcdef123456
scripts/release_ops.py recover --recovery-point prod.dump --operator ops@example
```

It is pure standard-library Python, imports no Django, and works offline against
a `--contract-json` snapshot or over HTTP against a running instance's
`GET /api/v1/contract` handshake. The `--release` directory is the artifact set
produced by CI; the operator never rebuilds images under the same release id.

## What each command does

| Command | Purpose | Touches live data? |
| --- | --- | --- |
| `check` | Re-validate the pinned manifest (digests, acceptance evidence, NO-GO) and classify the pairing against the running instance | no |
| `status` | Show the last recorded release state and, best-effort, the live contract | no |
| `stage` | Describe the isolated staging rehearsal it delegates to `migration_stage.py` | no (isolated copy only) |
| `deploy` | Emit an ordered, recorded, idempotent rollout plan; requires approval (and a verified recovery point when incompatible) | no — plan only |
| `recover` | Emit a safe recovery plan against an explicitly named target | no — plan only |

Deployment is never executed silently. The command records the plan and its
guards; the *apply* stays with the existing, separately guarded tools, which
re-enforce their own confirmation, so a second engine can never diverge from
them.

## Compatibility classification

`check` classifies the candidate **before** any change:

- **compatible** — the running instance accepts the candidate API major *and*
  the candidate's Django migration snapshot matches the recorded one. A
  compatible update needs no recovery point.
- **incompatible** (`api_major_incompatible`, `schema_migration_required`) — the
  candidate introduces an API/schema change. This requires, in addition to the
  manifest, an **independently verified** recovery point (a `<dump>.full.json`
  report with `complete: true`) and an explicit privileged approval
  (`--approve <release_id>`). A refusal, interruption or failed staging leaves
  production untouched.
- **fail-closed** (`installed_schema_unknown`) — when the running instance's
  schema cannot be established, the pairing is treated as incompatible rather
  than assumed safe. Only an explicit `--fresh` **new install** (no prior data to
  lose) bypasses this.

The manifest is only ever accepted as a **NO-GO** manifest: a candidate that
claims operational GO is refused, mirroring the PLAT-32 rule that CI cannot
fabricate production approval.

## Release notes and checklist

`build_coordinated_release.py` already emits `release-notes.md` with the exact
old/new frontend artifact digest, backend image ID and migration snapshot, and
the migration/rollback pointers. `release_ops.py` re-checks that the notes keep
the `**Production decision: NO-GO.**` blocker before it will operate on the
directory. Production GO remains explicitly NO-GO absent real browser staging
inspection, a production replay with a fresh recovery point, and accountable
operator sign-off.

## Idempotent dry-run and error recovery

Every command is a pure read or a *plan*; running `check`/`status` repeatedly
changes nothing, and re-running `deploy`/`stage`/`recover` only rewrites the
recorded plan. The recovery plan stops writes first, verifies the recovery point
with `full_recovery.py verify`, restores **only into an operator-named target**
(never the running production database implicitly), reconciles
revisions/retirements lost to a point-in-time restore, then restarts and
verifies. Code rollback is not database rollback: an image revert does not
restore data, and the plan says so.

## Boundaries

- Never promotes a staging database; staging is an isolated rehearsal.
- Never creates a second migration engine, event bus or release database.
- Never claims production readiness from CI alone.
- Reuses the existing coordinated release / recovery tooling; it does not
  re-implement archive, backup or migration mechanics.

## Verification

```bash
python3 -m unittest discover -s scripts -p 'test_release_ops.py' -v
python3 -m unittest discover -s scripts -p 'test_build_coordinated_release.py' -v
```

Covers: candidate integrity re-validation (tampered artifact, modified acceptance
evidence, a GO manifest) refused before any operation; compatible update accepted
with no recovery point; schema drift and a running instance with an unknown
schema both fail closed (the latter only bypassable by an explicit fresh
install); API-major mismatch refused; an incompatible deploy refused without a
verified recovery point, without its independent verification report, and without
the exact approval token; the recorded plan is idempotent and pins the manifest
digest; `recover` requires an explicit target; `stage` never promotes and targets
the existing tool; `status` still reports recorded state when the live contract is
unreachable.
