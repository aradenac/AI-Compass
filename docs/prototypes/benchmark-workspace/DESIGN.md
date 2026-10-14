# Benchmark Workspace prototypes — implementation handoff

[UI contract](../../benchmark-workspace-workgroup-ui-spec.md) · [Manager](index.html) · [Campaign detail](campaign.html)

This directory intentionally contains **two independent, standalone HTML documents**. Open `index.html`, then select a campaign to navigate to `campaign.html`. They are editable visual references, not application assets, and use simulated browser data.

The manager prioritizes a four-column campaign lifecycle pipeline and offers search/filter/list mode. The campaign detail contains overview, evaluation matrix, Runs and collaborative Review. The most recently approved campaign prototype deliberately removes Task-centred / Solution-centred UX and introduces review discussion threads with independent Open/Closed status and multi-author replies.

**Important backend mismatches:** the existing Campaign API still requires mode-specific configuration, and review discussion threads require a new explicit persistence model. Do not claim these exist in Server just because the HTML demonstrates them. Plan additive migrations and version-pinned linkage. Respect review/publication permissions and immutable run evidence.

Visual acceptance requires manual inspection of captured screenshots at desktop 1366×900 and 1024px, alongside interaction and permission tests. Current prototype is user-reviewed direction, **not** production acceptance.
