# FUT-04 — Shared AI Workgroup Studio and stable knowledge views

> **Homepage visual design candidate (2026-10-14):** [Workgroup Studio homepage specification](workgroup-studio-home-ui-spec.md) and [versioned standalone HTML prototype](prototypes/workgroup-studio/index.html) ([implementation handoff](prototypes/workgroup-studio/DESIGN.md)). The homepage prototype covers only the central five-zone map: the application shell, published Updates and attention indicators remain separate product functions. The design is pending owner visual approval, not automatically a completed feature. See [prototype conventions](prototypes/README.md) for all subsequent view mockups.

Issue: [#78](https://github.com/aradenac/AI-Compass/issues/78) · Original specification: [Role-based navigation](role-based-user-experience-and-guided-navigation.md) · [Shared frontend](shared-frontend-and-release-lifecycle.md).

## Workgroup navigation

Demo and Server render the **same** five-zone, keyboard-accessible, mobile-responsive Workgroup map in `shared-workgroup.js` and `shared-workgroup.css`: Sources & Référentiels; Formalisation & Études; Expérimentation & Analyse; Capitalisation & Décision; Mise à disposition. The five engineering evaluation cores (Catalog, Tasks, Test Design, Benchmark Workspace, Results Explorer) have a stronger visual treatment. Links navigate **directly**; lines describe evidence relationships, not prerequisite workflow gates.

- Offline Demo: open `prototype.html` with its bundled static files, select the fictional Workgroup account, or `?mode=demo&workspace=workgroup&section=studio`. Links are relative to the file to remain usable under `file://`.
- Authenticated Server: `/?mode=server&workspace=workgroup&section=studio`; navigation is available with **actual** business authoring rights. Each module is `section=watch`, `testdesign`, `forecasts`, `guides`, `feedback`, `activity`, `benchmark`, etc.; direct object links use `&record=<public-id>`. The server still enforces every permission. Maintenance continues in its **separate** authorized workspace; a role/URL selection grants nothing.
- The map has **no artificial To-Do list, assignment system or status transitions**. Badges appear only for non-archived Campaigns `under_review`, Forecasts `staged`, and Recommendations `in_review` / `review_needed` from authoritative records visible through authorized Server list endpoints. Permission denied or unavailable status means **no badge**, not "zero." Unanswered feedback, idle Watch items and draft guides never become invented overdue tasks.

## Published Workgroup Updates and coverage-gap navigation (UX-R06)

- **Workgroup Updates · What's New** (`shared-updates.js`, `GET /api/v1/updates`) is a
  published-only read projection over existing authoritative objects: current effective published
  Campaigns and measured Runs (via the shared publication selector, so withdrawals and corrections
  apply immediately), published editorial Recommendations, published Setup Guides, published Watch
  signals and recently recorded Catalog components. Every entry carries the exact source object ID
  and revision, with a link that only resolves when the reader's persona may open that workspace;
  otherwise the provenance line is shown without a link. Drafts, internal hypotheses, private
  discussions, theoretical Forecasts and the privileged Activity Feed/audit log are never reused
  as a news source. The service creates no business object, status model or assignment.
- **Coverage-gap navigation:** the Capitalisation zone and every Management heatmap Task row expose
  an explicit "Profitability & Opportunities → Technology Catalog" link. It explains that a blank
  or uncovered cell means no current effective published measured configuration exists, offers no
  candidate, and creates nothing automatically; the Catalog then shows the same notice with a
  clear-filter link.
- **Counter refinement:** a Campaign that already has an **effective publication** is no longer
  counted as awaiting a review decision, even though its working revision may still be
  `under_review` (reopen/unpublish remain explicit actions). The count badge opens the module with
  the read-only `status=awaiting_publication` filter preapplied and states that it is not a
  personal assignment.

## Common views, source details, existing specialist editors

Both modes use the **same** `renderList`/read projection for Technology Watch, theoretical Forecasts, Test Design, Guides & Charter, Feedback/Discussions and Activity. The Demo adapter projects existing local fictional objects through their original visibility rules; Server uses exclusively authenticated `/api/v1/` list endpoints, refuses malformed/failed responses and never imports Demo data. A record link opens an authorized read-only current-row projection with exact ID/revision; this is **not** falsely presented as a historical snapshot. The original full form/history/source/evidence editors remain available from **Open full workspace / edit / history**, preserving every existing ability including Test Case forks, source attachments, publication transitions, messages, corrections and confidential-feedback authorization rather than imitating those complex editors inside a generic CRUD form. Only one common listing is the default view. This is a transitional specialization boundary pending future campaign/Run redesign, not a second model or replica database.

The original Server campaign board remains read-only with respect to its status summary, while existing explicit campaign/session actions still follow their respective permissions and exact optimistic revisions. Results and measured AI Solutions are not re-scored, and Forecasts are never presented as measured evidence. No new migration or data schema is introduced.

## Context, drafts and concurrency

- Workgroup routes and source IDs are explicit URL query parameters, so copied links and browser back/forward use normal navigation. Breadcrumbs preserve the Workgroup origin. Forms and source revisions are not silently merged.
- The optional `shared-drafts.js` helper saves **uncommitted** local form values (not server records) keyed by mode, browser origin, account, form kind, object ID, base revision, schema and active step. It offers **Resume / Discard** only for matching revisions, refuses stale/differently-schema'd drafts with an actionable notice, and never replays old content automatically. It clears drafts after **successful** authorized saves, retains them on errors/409, and rebases them after a confirmed Server Run save so unsaved input in other steps stays resumable. Delivered scope (UX-R05), exclusions, retention and the conflict panel are specified in [Draft resume, Run stepper and conflict-safe concurrent editing](draft-conflict-and-run-stepper.md).
- Passwords, API keys, secrets, uploads/files and excessive free text are explicitly excluded from draft storage; `data-draft-skip` and caller-provided `exclude` rules add further exclusions, and Session drafts keep the same exclusions while using higher bounds. Keys are pruned after seven days and capped per browser; browser storage failures generate a visible warning and do not pretend a save occurred. Operators should disable local draft retention in shared-device/private-data settings when organizational policy requires it. Always treat local drafts as **uncommitted and device-specific**.
- Backend authorization, historical revisions, exact source pins, publication approval, HTTP 409 rejection and the creator-only Run writer rule remain authoritative. No global lock/CRDT or cross-user draft sharing.

## Tests, rollout and fallback

```bash
node scripts/test-workgroup-studio.js
node scripts/test-shared-drafts.js
node scripts/test-shared-frontend.js
node scripts/test-shared-demo-task.js
```

The platform CI includes these checks plus all prior integration, integrity, restore, migration and coordinated release checks. Frontend changes are packaged with the coordinated manifest. Roll back using the **previous tested coordinated frontend artifact**, not by mixing old and new scripts. Business revisions/data remain unchanged by these UI additions.

**Not part of FUT-04:** Campaign Evaluation Matrix and full Run stepper (FUT-08/09); effective Run publication (FUT-10/11); Engineer suitability (FUT-12); Management financial heatmap (FUT-13/14), Internet/production readiness (FUT-20). PLAT release acceptance remains **NO-GO** until human staging, recovery and sign-off gates are independently fulfilled.
