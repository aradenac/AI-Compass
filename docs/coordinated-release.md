# FUT-01 — Coordinated release manifest and API compatibility

> Implementation: [FUT-01](https://github.com/aradenac/AI-Compass/issues/75).
> **Packaging is NOT production approval.** The [PLAT-32 release readiness](release-readiness.md) remains **NO-GO** until independent manual browser/staging, recovery and sign-off gates are met.

## Output of the final GitHub smoke CI

The workflow emits a `fut-01-release-<run>-<attempt>` artifact after generating the success-gated PLAT-32 acceptance report.

| File | Evidence |
| --- | --- |
| `manifest.json` | `ai-compass/coordinated-release@1`, tested git commit, run URL, independent frontend and backend versions, frontend ZIP SHA-256 and file hashes, backend immutable image ID and source hashes, API/schema compatibility, migration fingerprint, package inventory, recovery attestation, explicit NO-GO |
| `frontend.zip` | Deterministically packaged exact static assets mounted via Compose (sorted, fixed timestamps/perms), SHA-256 recorded in manifest |
| `backend-packages.txt` | Exact installed transitive package versions obtained inside backend container with `pip freeze --all`, SHA-256 recorded in manifest |
| `release-acceptance.json` | Untampered PLAT-32 report for the exact commit/repository/workflow run; absence, failed automated checks or approval mismatch stops packaging |
| `release-notes.md` | Release identity, independent components, API compatibility, automated tests, migration/recovery evidence and outstanding manual gates |

One coordinated release pins a tested frontend/backend pair; they may have **different versions**. `release/versions.json` is the explicit version contract. Bump only the components whose contents change and bump release version when publishing a new coordinated release. Actual built artifacts are distinguished by commit and immutable hashes. The old Demo continues to run from static files.

Backend direct Python requirements are pinned to exact published versions; the complete installed transitive inventory and image content SHA are recorded for reconstruction and controlled promotion. Mutable Docker image tags are **not** immutable deployment references: retain/promote the tested image ID (prefer registry `name@sha256:...`) instead of silently rebuilding. FUT-21 supplies the future guided deploy/rollback CLI, not FUT-01.

## Verification

From the exact source commit and downloaded matching artifact directory:

```bash
python3 scripts/build_coordinated_release.py verify --root . --output /path/to/coordinated-release
python3 -m unittest discover -s scripts -p 'test_build_coordinated_release.py' -v
node scripts/test_release_contract.js
```

Verification refuses modified/missing ZIP, changed frontend/backend sources, changed installed dependency inventory, malformed image ID or missing/mismatched acceptance evidence. This is an integrity/consistency check, **not a cryptographic signature or production authorization**; verify the CI run and commit through trusted GitHub governance.

## Backwards-compatible API v1 handshake

Unauthenticated read-only `GET /api/v1/contract` declares `ai-compass/api-contract@1`, API major 1, supported client major 1 and capability/error metadata. The Server UI fetches the contract before any auth/business request and fails closed on invalid/missing/incompatible contract. It never silently switches to Demo.

Previous `/api/v1` business routes and legacy `{ "error": "..." }` response shapes remain unchanged, so older v1 frontends continue working with this additive backend. New endpoints may opt into the typed `{ "error": { "schema":"ai-compass/api-error@1", "code": "...", "detail": "..." } }` format. FUT-03 consolidates common frontend request handling; no massive Django endpoint rewrite is done here.

## CI, staging and recovery

The CI path filters now capture **all root `server-*.js` modules**, including Watch/Forecasts/Results/Recommendations/Discussions, plus release, backend, scripts, deployment and workflow inputs. The existing full dual-mode, immutable evidence, staging rejection, isolated DB+blob restoration and no-Demo-fallback smoke steps remain. The release build/verification step runs *after* the acceptance report and fails the CI job if any mandatory artifact is missing.

For backward-compatible changes: preserve v1 route semantics and old-client tests. For incompatible data/API changes: use registered migration, verified complete recovery, independent staging and operator-authorized production transition. A CI-green release cannot replace those gates.
