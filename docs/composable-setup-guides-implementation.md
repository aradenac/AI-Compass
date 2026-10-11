# FUT-07 — composable setup work in progress

## Current behavior

The permanent Server Setup Guide catalog retains `gui-*` identities and immutable revisions. A versioned guide can carry an additional `properties.recipe` object while retaining legacy text-only and URL-only entries. A new read-only `POST /api/v1/guides/render` endpoint takes `guide_id`, pinned `revision` (such as `r001`), and an exact `configuration` object; its response returns ordered pinned sections, missing/invalid coverage and `ready`. This is an applicability aid, **not publication validation**.

Example recipe stored in a guide revision:

```json
{
  "text": "Composite installation guide",
  "recipe": {
    "required": ["os", "model", "provider", "harness"],
    "modules": [
      {"id": "gui-install-example", "revision": "r001",
       "applies_to": {"os": "ubuntu-22.04", "harness": "cline"},
       "requires": []}
    ]
  }
}
```

The module must already exist on Server as a Setup Guide and have a matching immutable revision. Missing or inapplicable modules are surfaced as incomplete, never replaced with current versions. Dependencies are topologically ordered, and reused references appear once. External URLs are emitted as inert metadata only.

## Limitations / release status

**Not complete and not ready for merger as FUT-07.** Still required: enforce recipe validation at save, end-to-end frontend recipe authoring and exact configuration chooser, Framework participant/wiring representation, historical Run pins, offline Demo parity, UX for missing coverage, security/negative/end-to-end CI evidence. The FUT-10 publication gate is a separate issue. No production data migration, publication approval or release GO is implied.
