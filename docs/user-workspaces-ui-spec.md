# User Workspaces — approved role-separated UX

[Workgroup Profiles prototype](prototypes/user-workspaces/workgroup-profiles.html) · [Engineer home prototype](prototypes/user-workspaces/my-ai-workspace.html) · [design handoff](prototypes/user-workspaces/DESIGN.md).

## Experiences and boundaries

**No personal Workgroup member dashboard**: Workgroup participation remains collaborative in Workgroup Studio and existing shared functional views. Instead, its **User Profiles** management view configures the usage environment of ordinary users, subject to Workgroup business permissions; this is **not** account administration, IAM or assigning app roles.

**My AI Workspace** is the **ordinary user's main landing immediately after selecting the User experience**, including for a user who also holds independently granted Workgroup permissions. It does not expose a Workgroup profile editor, Workgroup navigation switch or privileged personnel information.

A multi-role account can choose **User** versus **Workgroup** in the authenticated **top-level session/account experience selector**, not in either of these destination pages. Only granted experiences appear. A user with one experience sees no redundant selector. Switching does not require separate credentials, but server routes and APIs enforce the selected authorization context; hiding a link is not access control. Preserve context preference where safe. No universal administrator shortcut.

## Workgroup — user profile configuration

- Browse and select one or multiple existing users without altering authentication identities or permissions.
- Edit contextual deployment preferences and constraints: IDE(s), permitted Operating Systems (Windows/Linux), WSL allowance, relevant specialties. Clarify declared environment versus actual verified availability; these flags do not themselves issue licenses.
- Assign relevant engineering Tasks to one person or bulk-select several, search Tasks freely, classify by project phase or professional specialty, and show any cross-classification without duplicating formal Task records.
- Maintain accountable changes/versioned provenance; do not expose or edit sensitive workforce cost assumptions in this UI.

## Engineer — My AI Workspace

- Default personalized **Task-oriented** discovery (optional inverse By tool), with search and classification by phase or specialty. Relevant Tasks derive from the person's authorized profile/explicit assignments, with clear fallback if unavailable.
- Opposite each Task, show compact, actually measured, qualified, published and relevant AI Solutions plus effective accessibility/deployment status. Experimental Forecasts, if exposed, must be separate, explicitly theoretical and never promoted to validated solutions.
- Contextual solution detail: editorial suitability/limits, guides for exact configuration and OS, eligibility, effective person-specific rights and setup verified status, options to request access and leave feedback or express a new need.
- A user may confirm their own ability to instantiate/test a solution, but cannot self-grant provider access/licences, publish AI Solutions or forge verified deployment/first-use status. Merge with Deployment & Access state through a reviewed auditable read/write contract.

## Integration safeguards

Workforce Planning APIs are planner-private; My AI Workspace must use a dedicated privacy-filtered **self-scoped** Task and eligibility projection, never expose organization-wide rosters, other colleagues or labor valuation. The Workgroup profile editor needs its own explicit scoped permission/endpoint, not global user-admin capabilities. Preserve independent Demo/Server state and all historical source revisions. Inspect 1366×900 and 1024px screenshots and test per-role navigation and forbidden API/deep links. Prototype behavior is illustrative, not a shipped server feature.
