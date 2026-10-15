# Deployment & Access — prototype Workgroup

## Views
- Three orientations: Tasks grouped by project phase, Tasks grouped by specialty, and persons grouped by specialty. A person may appear in multiple groups without becoming a second person or duplicated entitlement.
- Column AI Solutions reflect measured/qualified catalog candidates; publication is explicitly shown and never inferred from benchmark acceptance. Some unpublished candidates are shown for readiness planning only.
- Left group rows collapse by default. Search expands matching groups. Cells provide a compact state; click reveals authorized evidence entry.

## Distinct facts
1. Benchmark qualification is not engineer visibility.
2. Publication is a separate editorial gate in AI Solutions.
3. Personal availability requires eligibility, enterprise access, applicable guides, manually verified Model/Provider/Harness component entitlements, license and setup verification.
4. First real use requires an attributable person with verified readiness and an evidence reference. Task-based confirmation can originate from a benchmark only when its scope was a real productive activity rather than a synthetic lab exercise.

No credential, secret, or license key is requested. Revocation of an individual entitlement, publication or enterprise accessibility must invalidate derived current availability and associated current confirmed deployment; immutable event history stays intact.

## Existing Server contracts versus proposed UX
The existing FUT-15 implementation uses a **Task × candidate × population deployment target**, seat identifiers, component-level requested/approved/provisioned/verified events, setup verification, and first_use with proof. The prototype's per-person checkboxes summarize that workflow for illustration and **are not substitutes for the Server's ordered events or authorizations**. The person×solution matrix and reusable person-wide readiness display, and task-level operational use rollups, require explicit projection and identity scope design. The state in HTML is fictitious in memory and not persisted to the server.

The operator must hold planning_view/planning_manage; ordinary engineers may inspect only self-owned deployment readiness through dedicated APIs. Do not publish colleague-level entitlements or demographic aggregates to engineer/public Workgroup views. Verify at 1366×900 and 1024px, keyboard behavior, audit evidence, and status invalidation.

## Révision UX — déclaration groupée (2026-10-15)
- Une case Task × AI Solution permet de sélectionner **plusieurs personnes** éligibles et disposant d'un accès prêt, et de valider leur déclaration d'utilisation d'un seul geste.
- Aucun champ de preuve d'utilisation réelle dans cette boîte de dialogue ; la validation d'une disponibilité personnelle conserve ses contrôles séparés. Le modèle Server FUT-15 exige aujourd'hui une référence de preuve sur `first_use` : écart métier/API à arbitrer avant implémentation.
- Le bouton s'appelle simplement « Retirer la confirmation » et l'encart explicatif sur le benchmark réel est retiré.
- Les objets fictifs de démonstration conservent une liste d'identifiants de personnes par Task × AI Solution. La publication reste décidée dans AI Solutions.

## UX revision — October 15, 2026
- Task-oriented phase and specialty matrices are **read-only**: no action on grey/non-applicable cells or other task cells. They summarize use and readiness.
- Person view permits interaction **only for eligible person × solution combinations**. A nonpublished solution presents a single global **Publish solution** action (same global publication state as AI Solutions), not individual access checks or Unpublish.
- A published solution's person-specific check is simplified to **(1) necessary rights and licences verified, (2) installation successfully tested by that person**. No user-facing proof-reference input. Nonpublished/pending solutions are labelled **À publier**.
- Production architecture must preserve independent publication_review authorization and audited changes. Existing Server contract expects component events and proof references; this approved UX does **not** mean existing Server guarantees can be bypassed. Derive supporting audit references server-side only if substantively legitimate or explicitly redesign the API after approval.
- Historical fictional per-task usage remains read-only in this view; future workflow for adding actual task use needs a separate authorized entry path or explicit UX decision.