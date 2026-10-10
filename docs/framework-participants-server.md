# Framework Participants in Server Campaigns — PLAT-13

The optional Framework is a **version-pinned catalog item**, not a measured AI Solution. Each campaign may now contain **1–64 ordered participants** with permanent `ptp-*` IDs, role and label, independently chosen Model / Provider / Harness components, a configuration version, arbitrary JSON `settings` and extensible JSON `properties` (tools, capabilities, access flags or later descriptors). Adding a participant does not execute any agent or create a measured run.

## Persistence and compatibility

Migration `0012_framework_participants` adds nullable `CampaignSnapshot.framework` and `framework_revision` foreign keys, a permanent campaign-owned `CampaignParticipantIdentity`, and immutable `CampaignParticipantPin` rows for **each** exact campaign revision. It adds no sample data and does not rewrite pre-existing campaigns. All old campaigns have no Framework and remain readable unchanged.

Every participant snapshot stores independently validated Model, Provider and Harness IDs and **exact immutable** `CatalogRevision` UUIDs. The Framework has its own exact revision FK. PostgreSQL triggers reject wrong-type revisions, cross-campaign identity reuse, updates/deletes of identity or snapshot rows, and unsanctioned Framework links. Every campaign edit or transition copies its participant configuration to a new immutable revision; historical `/revisions/<N>` endpoints preserve the old trio, role, settings, Framework selection and order. No component edit is retroactive.

- **Task-centred:** a fixed task remains required; Framework participants each supply their own independent trio.
- **Solution-centred:** without a Framework, existing fixed model/provider/harness behavior is unchanged; with a Framework, the participant trios *replace* that one fixed trio.
- With no Framework, participant data must be absent/empty. A Framework requires at least one complete participant. All referenced records must exist in the real Server catalogs.
- Changing a Framework requires new participant identities. Removing a Framework requires explicit `participants: []`, so no participant is accidentally lost in a partial PATCH.
- Editing a participant's label, role, configuration version, settings or component selection keeps its permanent `id`; removing an ID takes it out of the current view but preserves earlier snapshots.
- Submitting the same trio references keeps the old revision pins even if the catalog has changed. `repin: true` explicitly advances **retained** IDs to the then-current component/Framework revisions and appends a new campaign revision. No silent repinning.
- Unknown fields inside `settings` and `properties` round-trip unchanged, subject to bounded JSON object size. There is no measured quality, cost or runtime score at this stage.

## API extension

The existing `POST /api/v1/campaigns` and `PATCH /api/v1/campaigns/<cmp-id>` accept:

```json
{
  "name": "AI-assisted embedded driver",
  "objective": "Evaluate orchestrated development",
  "mode": "task_centred",
  "task_id": "tsk-existing-server-id",
  "framework_id": "frm-existing-server-id",
  "participants": [
    {
      "label": "Planning agent",
      "role": "Planner",
      "component_ids": {
        "model": "mdl-existing-server-id",
        "provider": "prv-existing-server-id",
        "harness": "hrn-existing-server-id"
      },
      "configuration_version": "1.0",
      "settings": {"reasoning_effort": "high"},
      "properties": {"tools": ["terminal"], "accessible": true}
    }
  ]
}
```

On initial creation, omit `id`; Server assigns permanent globally unique `ptp-*` IDs. On PATCH, provide each previously saved `id` to retain its identity. The `participants` array is an **ordered replacement** when supplied: omit it to retain the current list as-is; include it to add/edit/reorder/remove. Existing list members may omit unchanged fields. Existing historical participants not in the replacement list remain queryable via earlier campaign revisions. A new participant never accepts an arbitrary user-supplied ID. Each `POST/PATCH` remains CSRF-protected, role-restricted and revision-conditional; PATCH requires `expected_revision`.

The campaign GET and history responses include `framework_id`, `framework_revision_id`, and ordered `participants` with their ID, UUID, label, role, position, settings, properties, component IDs and pinned revision UUIDs.

## Verification and manual demonstration

```bash
docker compose up -d --wait --build
docker compose run --rm api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_campaigns config.test_campaign_participants -v 2
node scripts/test-server-campaigns.js
```

1. In `?mode=server`, sign in as a contributor, add **three distinct Models, Providers and Harnesses**, at least one Framework, and a task/Test Case.
2. Open **Benchmark Workspace · Campaigns** and select a Framework, then **Add participant** three times. Choose a distinct Model/Provider/Harness trio for each; enter separate roles, names, settings and capabilities. Save.
3. Reopen the same campaign in another authenticated browser and confirm the three stable `ptp-*` IDs, ordered roles and exact settings. Change a Model in Technology Catalog, then edit only campaign notes: the participant's old revision remains pinned.
4. Edit the campaign: reorder participants, change one role and configuration, remove one and add another. Reopen **Details / history**; the old campaign revision still shows all three original entries unchanged. Use **Re-pin** to explicitly capture newer Model/Framework revisions.
5. Attempt a wrong-type component, missing trio, cross-campaign participant ID, duplicate ID, disabled writer or stale revision; the API rejects the whole mutation. Start/reopen/archive the campaign: pins and identities remain auditable.
6. Switch to `?mode=demo` without Django/Docker: original fictitious Framework examples remain local and independent. There is no automatic import or Server fallback.

This is an additive schema change. It does not require semantic migration of existing real records, does not change the evidence store, and does not introduce run execution, composite scoring or live orchestration (#14–16).
