# Draft resume, Run stepper and conflict-safe concurrent editing — UX-R05

Issue: [#124](https://github.com/aradenac/AI-Compass/issues/124) · Normative UX reference: [Role-based UX §§8.2, 9, 10 and §13 cases 12–15](role-based-user-experience-and-guided-navigation.md) · Related: [Resumable Server sessions](resumable-sessions-server.md), [Workgroup Studio](workgroup-studio.md), [Shared frontend and release lifecycle](shared-frontend-and-release-lifecycle.md).

This document describes the **delivered** stateful-editing behaviour on the consolidated desktop UI. It extends the existing `shared-drafts.js` helper and the existing `expected_revision` / HTTP 409 contracts; it introduces no second draft engine, no new database, no CRDT/real-time editing and no mobile scope.

## 1. Scoped ephemeral drafts (`shared-drafts.js`, format 2)

A draft is an **uncommitted, per-account, device-local working copy** of unsaved form input plus the active step of that form. It is never a business record, never shared across accounts or Demo/Server modes, never promoted to evidence, and never applied without an explicit user action.

Envelope and scope:

- **Scope key** = mode (`demo`/`server`) + browser origin + account + form kind + object public ID (or `new`) + base revision + schema version. A different account, mode, object or schema can never read another draft.
- **Step identity** = the active step key plus its declared step list, so a resumed sequential form returns to the step the user was on.
- **Retention** = per-call `retentionMs` (default 7 days) plus a bounded number of drafts (default 24, oldest pruned first). Expired/incompatible entries are dropped, never migrated.
- **Excluded fields** = password, file/hidden inputs, and any field whose name matches the sensitive-pattern list; `data-draft-skip`/`dataset.draftSkip` marks an element as never cached; callers may pass an additional `exclude` list, regular expression or predicate. Session drafts raise `maxFields`/`maxLength` bounds but keep the same exclusion rules, and evidence binaries are never cached.

Behaviour:

- On open, an existing matching draft shows **Resume draft / Discard** and is *not* applied automatically. A draft whose base revision or schema no longer matches is refused with an actionable notice (copy the old text, review the latest form, discard) and the authoritative Server state stays untouched.
- Input/change autosaves locally with a visible "not committed to Server" cue. A draft that is already identical to the live form is treated as redundant and not proposed again.
- A successful authoritative save clears the draft; on the Server Run workspace the draft is instead **rebased** onto the new revision so genuinely unsaved input in other steps stays resumable.
- API/validation failures and HTTP 409 keep the draft. Storage-disabled/full browsers produce an explicit warning instead of a silent "saved".
- `AICompassDrafts.notice()` renders the same accessible, dismiss-free conflict panel for non-form conflicts (for example a Campaign plan/waiver change), and `guardUnload` registers a single `beforeunload` cue while unsaved local input exists.

Covered flows: Server Guide, Watch Entry/Research Source, theoretical Forecast, Test Case, editorial Recommendation, Campaign (including the matrix builders and waiver text) and the Run/session workspace; Demo Campaign, Test Case, Guide, Run/session step and benchmark Run forms.

## 2. Revision-conflict UX (HTTP 409)

`AICompassRuntime.httpError`/`failureInfo` preserve the HTTP status and detail from the shared transport and each module's own wrapper. On a stale write the object's form shows a **first-class conflict notice** that names the object, the newer Server revision and the local base revision, states that nothing was overwritten or merged, and offers:

- **Reload latest** — re-reads the newest authoritative revision and re-renders the editor; the local draft is kept for manual reapplication;
- **Review / Copy my unsaved text** — shows or copies the captured local values for manual reapplication;
- **Discard** — removes only the local draft.

No field-level merge, implicit re-pin of configuration/Test Case/setup/waiver/history references, or automatic replay of the old object is performed. A stale revision never silently replaces a newer Server revision.

## 3. Run interaction stepper

The Server Run workspace renders a real sequential stepper (`#session-stepper`, panels `data-session-panel`, buttons `data-session-goto`) over the frozen method definition: **Setup → each method step → Interactions → Results** (Results only when the Run can actually be closed). Fields and step order still come from the session's original `method_descriptor`.

- Step navigation is **purely local**: it writes no checkpoint, creates no phantom session and promotes no local cache into measured evidence.
- Only explicit Save/Append/Close buttons append an immutable checkpoint. Each acknowledged save updates the displayed Server revision and the affected sub-view (for example the interaction timeline) without re-rendering — and therefore without discarding — unsaved input in other steps.
- Unsaved inputs and the active step are kept in the scoped draft; leaving the screen, reloading or returning offers an explicit Resume that restores both the values and the step. Closing the Run as a permanent Run clears the ephemeral draft.
- The Demo benchmark Run uses the same step vocabulary (Setup → Interactions → Results) with a `shared-draft-step` stepper on the session card, and reopens the step the user was last on.

## 4. One experimenter writes one active Run

`session_services.can_edit` now allows **only the account that created the session** (plus the existing superuser override) to append checkpoints or close it into a Run. Authorized co-workers keep read access, may inspect original checkpoints and may create *separate* sessions for the same Campaign; the Campaign owner is no longer an implicit co-writer. A refused write returns HTTP 403 `permission_denied` and appends no checkpoint, and the UI explains the single-writer rule instead of retrying.

## 5. Verification

Focused automated checks:

```bash
node scripts/test-shared-drafts.js          # isolation, privacy, step identity, retention, stale refusal, 409
node scripts/test-server-sessions.js        # stepper contract, draft scope, rebase/conflict, single-writer note
node scripts/test-server-campaigns.js       # campaign draft integration and conflict surface
node scripts/test-server-guides.js          # guide draft + conflict reload
node scripts/test-server-test-cases.js      # Test Case draft + conflict reload
node scripts/test-server-watch.js           # Watch/Source draft + conflict reload
node scripts/test-server-forecasts.js       # Forecast draft + conflict reload
node scripts/test-server-recommendations.js # editorial draft + review conflict
docker compose exec -T api python manage.py test config.test_sessions config.test_runs \
  config.test_composite_runs config.test_campaigns -v 2
```

Real Chromium journeys (disposable Server + standalone Demo, desktop 1366×900) are part of the UI acceptance gate:

```bash
python3 -m http.server 8090 --bind 127.0.0.1 --directory .
python3 scripts/ux_qa.py provision --output /tmp/uxqa-credentials.json
python3 scripts/ux_qa.py test --base-url http://127.0.0.1:8080 \
  --demo-url http://127.0.0.1:8090/prototype.html \
  --credentials /tmp/uxqa-credentials.json --artifacts /tmp/uxqa-report
```

`Standalone Demo draft/Run-stepper` and `Authenticated Server draft/stepper/conflict/ownership` cover: unsaved Campaign resume/discard with no business write; Run step navigation without a phantom session; unsaved step input resumed after leaving the screen; exactly one finalized Run; creator-only Server writes with a 403 for a second contributor who can still start their own session; and an Alice/Bob concurrent Campaign edit where the stale submit receives 409 with the draft intact and the newer revision preserved.

## 6. Boundaries

No global wizard, CRDT, real-time collaborative editing, permanent draft database, cross-user draft sharing, automatic field merge, mobile-specific UX or migration of historical business records. Backend authorization, immutable revisions, exact setup/reference pins, publication rules and the operational production **NO-GO** are unchanged.
