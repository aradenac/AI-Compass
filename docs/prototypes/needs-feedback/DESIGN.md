# Needs & Feedback — Workgroup UI prototype

Standalone `index.html` to explore the proposed Workgroup view. No remote dependencies and no global application shell.

## Decisions captured

- Three panels: left search/filter/list, center selected thread and chronological public/internal conversation, right editable metadata and linked context.
- Upper strip: totals by explicitly modeled **proposed** status and an action to create a new Workgroup-authored thread.
- Workgroup classification by action-oriented types: Idée, Support, Retour d’expérience, Question, Demande, Discussion. This is a **proposal for mapping/expanding** the existing feedback/question/idea/request/discussion types, not yet an approved backend schema.
- Proposed statuses Nouveau / En cours / Fermé with **unrestricted transitions** and independent priorities Basse / Normale / Haute. These are NEW domain requirements, not existing repository guarantees. Implement via approved versioned domain model, tests and migrations only after product decision; never hide this gap.
- Keep original author, timestamp and link to authorized user profile. No team, business-domain field or tags.
- Single chronological conversation: each message visibly Public or Interne; original evidence attachments and versions must remain protected and inspectable via existing services.
- Existing contextual Task/component/measured Solution references, no automatic issue creation or mandatory Workgroup workflow.

## Mock boundaries

All six sample discussions, counts, users, dates, attachments and destinations are fictional. Metadata selection, creation and replies change in-memory data only and disappear after reload. Author profiles, attachments and related-object links open explanation dialogs. No business record is written, no real file is uploaded, and no permission enforcement is simulated.

Normative backend reference: `docs/feedback-discussions-server.md`. The existing service uses immutable thread scope and per-message revisions/visibility, optimistic concurrency, protected original attachment bytes and restrictions on moderation. Respect these rather than copying local prototype behavior into production without review.

## Visual acceptance

Review 1366×900 and 1024px desktop layouts, filtered list, selected thread, metadata controls, internal messages and creation dialog. Test keyboard/focus and authorized public/internal separation after integration. This design is not yet approved or committed to the AI-Compass repo.