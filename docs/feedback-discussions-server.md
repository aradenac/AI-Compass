# PLAT-23 — Persistent Feedback & Discussions (Server)

## Outcome

Authorized engineers can create a new Feedback/Question/Idea/Request/Discussion thread, reply to each other in **one chronological conversation shared between accounts and browsers**, correct their own posts, and attach original evidence files. Workgroup contributors/reviewers may write **Internal** messages and moderate/edit any discussion message with a reason. Every message, correction and attachment keeps original attribution. Existing offline seeded fake **Demo** remains independent, and a fresh Server starts with **zero** real discussion threads/messages.

### Data model and invariants

Additive migration `0020_feedback_discussions` creates two registered ObjectTypeVersion JSON schemas, permanent `thr-*` and `msg-*` (UUIDv7 internally), and protected relational models:

- `DiscussionThread` links its CatalogItem (and immutable initial CatalogRevision with title, kind, scope and any unknown extension properties) to an optional existing **public catalog object** plus its **exact immutable CatalogRevision**, pinned at creation. Supported contexts: Task, Model, Provider, Harness, Framework and real measured individual Solution. A real Server reference that is missing, unsupported or not eligible for a public thread is rejected, not silently ignored. Thread scope is Public or Internal and immutable.
- `DiscussionMessage` links its permanent CatalogItem, parent `DiscussionThread`, and optional parent `DiscussionMessage` via real foreign keys. SQL checks ensure a child belongs to the same thread. Text, visibility, edit_reason and unknown extensions reside in versioned immutable CatalogRevisions, created with user/time and attributable CatalogAuditEvents. Original messages are never overwritten or hard deleted. Corrections and moderation *append a new revision* after an `expected_revision` check (stale returns 409). Original author or an authorized workgroup member may correct a message, but **only** workgroup can switch its visibility.
- A Public reply cannot be placed beneath an Internal parent. A public parent with currently public direct descendants cannot be changed to Internal until the descendants are moderated first. Internal threads cannot contain Public messages. Messages retain their own visibility independently.
- Original file attachments are recorded as `EvidenceLink` to **exact message CatalogRevision**, `EvidenceBlob` with private original bytes and SHA-256 verification, using the already-shared #17 store. An engineer may upload **only to their own latest message**. Workgroup may attach evidence to authorized messages. No browser-local attachment is accepted as authoritative. Prior revisions and all previous EvidenceBlob bytes remain inspectable by authorized workgroup members.

**Visibility and access:** Public means readable only by users authenticated to the intended platform (not the open Internet). Any `auth.business_read` user can post Public feedback and reply in a Public thread. Only `auth.business_write` or `auth.publication_review` can see Internal threads/messages and create or moderate Internal replies. A reader gets no Internal content via thread list/detail, message detail/history/exact revision, generic raw catalog lookup, evidence list, guessed EvidenceLink UUID metadata or direct binary download. If a message becomes Internal, its **earlier Public versions and attachments also cease to be visible to regular readers**. If a workgroup member changes Internal→Public, its earlier Internal versions **remain hidden**. Internal replies never leak through Parent IDs, public listing counts or error-specific IDs.

## REST API (all require a real Django session)

| Action | Endpoint |
| --- | --- |
| List shared threads | `GET /api/v1/discussions` |
| Create thread + first feedback | `POST /api/v1/discussions` |
| Read ordered messages | `GET /api/v1/discussions/<thr-id>` |
| Reply, optionally to parent ID | `POST /api/v1/discussions/<thr-id>/messages` |
| Read / correct message | `GET / PATCH /api/v1/discussions/messages/<msg-id>` |
| Immutable revision history | `GET /api/v1/discussions/messages/<msg-id>/revisions` |
| Exact readable revision | `GET /api/v1/discussions/messages/<msg-id>/revisions/<number>` |
| Attach verified original evidence | `POST multipart /api/v1/discussions/messages/<msg-id>/attachments` |
| List file metadata (permission-checked) | `GET /api/v1/catalog/items/<msg-id>/evidence` |
| Download original bytes | `GET /api/v1/evidence/<evidence-uuid>/download` |

Public new thread example:

```json
{
  "title": "KSZ8851SNL driver: missing error-path handling",
  "body": "I observed an error when the SPI transfer times out during init.",
  "context_id": "tsk-actual-engineering-task",
  "properties": {
    "scope": "public",
    "kind": "feedback",
    "extensions": {"future_field": null}
  }
}
```

Public reply (`parent_id` optional) at `POST /discussions/<thr-id>/messages`:

```json
{"body":"Can you share the Twister test report?","visibility":"public","parent_id":"msg-real-parent"}
```

Append correction at `PATCH /discussions/messages/<msg-id>`:

```json
{
  "expected_revision":"r001",
  "properties":{"body":"Corrected observation with IRQ trace",
                "edit_reason":"Reproduced with a different interrupt sequence"}
}
```

An optional evidence upload uses `FormData` fields `file` (single permitted PDF/PNG/JPG/WebP/ZIP/UTF-8 TXT/MD/CSV/JSON document) and `expected_revision=r001`. Uploaded bytes are verified and stored privately before the metadata transaction; every referenced SHA is checked. CSRF headers required for all writes; input/attachment sizes are bounded by the platform's established rules.

## Functional acceptance

```bash
docker compose up -d --wait --build
docker compose exec -T api python manage.py migrate --noinput
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api python manage.py test config.test_discussions config.test_evidence config.test_recommendations -v 2
node scripts/test-server-discussions.js
```

Open `/?mode=server` with one ordinary authenticated engineer and open **Knowledge & Collaboration · Feedback & Discussions**. Verify the list begins empty; create a Public feedback linked to a real `tsk-*` or `sol-*` ID. From a second engineer browser/session, reload, read the thread, reply and inspect the ordered messages with original authors/timestamps. Correct a message and verify original and corrected revisions still exist, with recorded actor and reason. Upload a TXT trace and verify SHA-256, list and download using a separate authorized browser.

As a workgroup contributor, reply **Internal** under a public parent. The ordinary engineer must not see the message, its identity or any binary evidence through guessed direct URLs; the workgroup sees it. Confirm Public→Internal and Internal→Public moderation preserve old revisions but do not expose content from any Internal revision. Verify CSRF failures, wrong-thread parent, unknown target, stale edit, non-author edit and unavailable evidence file are rejected without inventing data.

Open `/?mode=demo` with the Server stopped. Existing fake Feedback/Discussions UI continues to run purely in the browser with `localStorage`. Shared `prototype.html` loads the Server adapter only when Server mode is selected; Server does not import any browser fixture. Staging mounts the same frontend script but uses isolated DB/volume/network. The full platform GitHub workflow exercises migrations, all existing experimental/evidence/recovery tests, staging reject/recreate and Demo non-regression.

**Boundaries:** no corrective-action workflow, no sentiment/AI summaries, no unreviewed promotion to official recommendations, no deletion/modification of prior messages, no real deployment data import, no new permission roles or workgroup consensus policy.
