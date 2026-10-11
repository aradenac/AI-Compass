# FUT-17 — Maintenance Governance Audit & Changes Explorer

## Operator usage

Sign into `/maintenance` as **data-maintainer**. A separate **Audit & Changes** panel shows committed modifications, newest first. Filter by authoritative source, object type, stable ID, current actor name, action, UTC timestamp range, or an exact changed field. Select **Inspect** to view before/after changes, relationship pins and version identifiers. Object-specific chronology is also available through `/history/<public-id>` API. Narrow filters before exporting JSON or CSV. The Workgroup Activity Feed remains at its original separate business workspace and uses the **same original CatalogAuditEvent** adapter, not a copy or alternative event recorder. No extra user-facing audit inputs or navigation tracking were added.

All endpoints are **GET only** and require the independent `auth.audit_view` capability, granted by the existing `data-maintainer` role using idempotent `bootstrap_identity`. No business-write, publication, delete, account administration or evidence-download privilege is implied.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/maintenance/audit` | Permission-scoped global list, 25/page, bounded newest 500; `source`, `object_type`, `object_id`, `actor`, `action`, `field`, offset-aware `from`, `to`, `page` |
| `GET /api/v1/maintenance/audit/<source>:<uuid>` | Safe field and relationship difference, exact immutable revision links |
| `GET /api/v1/maintenance/audit/history/<public-id>` | Object chronology (same source-level restrictions) |
| `GET /api/v1/maintenance/audit/export?format=json|csv` | Filtered metadata only, max 500 events; no private before/after blobs or secret data; 422 rather than truncated export |

Account/OS environment audit records are **not listed or discoverable by an audit-only operator**: `users_manage` is additionally required, including direct event lookup and export. Unknown/private Research, Watch, Forecast and Discussion catalog types are omitted from the generic operator projection; unauthorized IDs cannot be brute-forced through detail. Confidential planning/Deployment metadata expose aggregate counts/IDs only, **never salary/rates, employee names, evidence references or private prompts**. Commercial offers use an explicitly enumerated charge-field schema, excluding supplier conditions and arbitrary properties. Raw evidence and secrets are never embedded. Date ranges require ISO-8601 timezone offsets. CSV formula-injection prefixes are escaped; no-store and nosniff headers are used.

## One capture contract, multiple read models

The immutable authoritative source records are **CatalogAuditEvent** (including linked RunAmendment corrections and withdrawals), **UserAccessAuditEvent**, **DataHealthEvent**, **BenchmarkRun / CompositeBenchmarkRun**, **SessionCheckpoint**, **WorkloadRevision**, **OpportunitySnapshot**, **BudgetRevision**, **DeploymentRevision / DeploymentEvent**, and **UserEnvironmentRevision**. The latter objects are themselves original committed append-only version rows, *not new telemetry or backfilled facsimiles*. A governance reader never modifies them.

Catalog structural differences use adjacent immutable `CatalogRevision` IDs and snapshots, including Campaign case, component, pricing, participant, framework, Task ancestry, and Recommendation Task/Solution relationship pins. Measured Run corrections use `RunAmendment.audit_event_id`, compare original or prior corrected metrics with the current amendment, and preserve publication authority in FUT-11. Native version streams compare supported safe fields of consecutive immutable revisions. Unsupported/protected fields are explicitly not returned rather than silently claimed recoverable.

**Historical limits:** legacy events without recorded role, origin, BU or actor are never assigned fictitious attributes. `created_at` is recorded on the server with the append-only source row during the same atomic operation; it is not a separately instrumented post-commit timestamp. Username shown is its **current name**, not a frozen historic identity label. Correlation is emitted **only where an actual source link exists** (RunAmendment → CatalogAuditEvent); no guessed request or batch IDs. Only source-supported safe fields have exact diff fidelity; other content is indicated as restricted/unavailable. The field filter is applied on the already-authorized safe snapshot. Expanding provenance requires editing the original authoritative mutation service rather than creating a parallel Audit table.

## Future producer hook and completeness inventory

Domain implementers must (a) persist mutation and existing audit event **inside one atomic transaction**, via `record_catalog_event` for versioned catalog objects; or (b) create a complete immutable row in an existing domain-specific revision/event table. Register that source in `governance_audit_services.SOURCES`, define the source summary, previous/current snapshots and **allowlisted safe fields**; confirm both the visible and forbidden test cases. Do not log API reads, mouse clicks, prompt content or credentials. If the existing domain has a direct audit FK, preserve it as the correlation ID. For new write domains, add schema/SQL immutability enforcement with migration and rollback verification.

**Coverage inventory:**
- Direct/linked: Models, Providers, Harnesses, Frameworks, Tasks, Test Cases, Campaigns, Setup Guides, AI Solutions, Evaluations, Recommendations, Pricing Offers, published individual/composite Run records and subsequent corrections/withdrawals;
- Original version/event histories: Session steps, Workload profiles, Opportunity decisions, Resource budgets, Deployment selections and external entitlement events, Maintenance Data Health triage, Users & Access, user OS declarations;
- Restricted: internal private Technology Watch, Forecast, research sources and discussion content are not available to the metadata-only maintenance reader; access to their original revisions still follows their existing specific business read/privacy policies;
- Legacy completeness: an absent event or prior revision remains **unavailable** and is not synthesized. Future auditing of additional domain-specific side-effect tables requires an authoritative commit-time source, not a blind retroactive best guess.

## Reproducible checks and deployment

```bash
docker compose exec -T api python manage.py bootstrap_identity
docker compose exec -T api python manage.py test config.test_governance_audit config.test_activity -v 2
node --check server-governance-audit.js
node scripts/test-server-governance-audit.js
node scripts/test-server-activity.js
docker compose exec -T api python manage.py makemigrations --check --dry-run
```

No new schema migration or extra write-side pipeline is introduced. Role bootstrap is additive/idempotent; old role grants are not removed. Roll back only the coordinated application release if needed, retaining original database/audit sources. Unpublish/redaction/source access rules remain authoritative after rollback; normal platform staging, backup and restore GO/NO-GO remain independently required.
