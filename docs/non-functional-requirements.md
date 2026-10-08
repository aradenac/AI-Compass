# AI Compass — Non-Functional Requirements

> **Status:** Product quality and interaction baseline  
> **Scope:** All AI Compass roles, screens and interaction flows (unless explicitly scoped)  
> **Functional requirements:** [Product Definition](product-definition.md)  
> **Purpose:** Document *how the product must behave* across workflows, separately from its functional capabilities. Compliance with a requirement in this file must be verified independently; a working HTML prototype is not evidence of production-level security, reliability or accessibility.

## 1. Interaction and usability

### NFR-UX-001 — Prevent accidental dismissal of forms

**Requirement.** A modal dialog **containing a form** shall not close when a user clicks its backdrop (the area outside the dialog). The user shall instead use an explicit dismissal control, such as the clearly identified **× Close** button or an explicitly offered **Cancel** action.

**Scope.** All creation, editing, reply and guided multi-step forms, including forms embedded in otherwise informational dialogs. Protection is based on whether a form is present in the dialog, **not** on a hard-coded list of screens or form identifiers.

**Keyboard behavior.** In this prototype, pressing `Escape` shall also **not** dismiss a form-containing modal, to avoid inadvertent loss of unsaved inputs. An explicit Close / Cancel control remains available.

**Non-form dialogs.** Informational or read-only modal dialogs **may close** when users click the backdrop or press `Escape`, and still provide an explicit × button.

**Data integrity.** A backdrop click or `Escape` in a form dialog shall neither discard in-progress entries nor submit the form. Closing explicitly does not imply auto-saving; current save/submit validation remains unchanged.

**Acceptance criteria**

| Test ID | Scenario | Expected result |
| --- | --- | --- |
| UX-001-A | Open any create/edit form and click the backdrop | Dialog remains open; entered values are untouched; nothing is submitted |
| UX-001-B | Open a form and press `Escape` | Dialog remains open; no submission or data loss |
| UX-001-C | Open a form and activate × Close | Dialog closes normally |
| UX-001-D | Open a form with **Cancel** and activate it | Dialog closes normally |
| UX-001-E | Open a read-only/detail dialog and click outside | Dialog closes |
| UX-001-F | Open a read-only/detail dialog and press `Escape` | Dialog closes |
| UX-001-G | Open a detail modal containing an embedded reply form | It behaves as a form modal, including for backdrop and `Escape` |
| UX-001-H | Open a new form introduced in a future feature | The same rule applies without introducing a special-case handler |

**Prototype implementation:** `prototype.html` — `modalContainsForm()` inspects the rendered dialog and the shared backdrop / keyboard handlers use it to decide whether dismissal is allowed.

### NFR-UX-002 — Explicit modal close affordance

All modal dialogs, including forms, shall expose an identifiable, keyboard-operable close control (×) with an accessible label. When an explicit **Cancel** action is present, it must close without submitting. Dismissal behavior must not depend on the workgroup/engineer role.

### NFR-UX-003 — Guided metric input and interpretation

- Each benchmark metric entry shall have a concise **hover/focus information affordance**, documenting accepted units, scope, measurement/estimation basis and interpretation. Its help content shall be visible on hover **and keyboard focus**, and its actual explanatory text (not merely an uninformative label) shall be available to screen-reader users.
- **Quality** and **Information Utility** shall have synchronized **0–100 sliders and editable numeric inputs**. Their own supporting free-text evaluations shall be adjacent to each metric.
- Human preparation, human intervention, agent duration and final human review/correction shall use synchronized **nonlinear duration sliders**, from **0 to 10,080 minutes (7 days)**. Retain exact editable minutes; labels shall adapt to **minutes, hours and days**. Fine resolution near zero and progressively coarser movement at longer durations are expected.
- Optional total token consumption shall support a multiplier (×1, ×10, ×100, ×1,000 or ×1,000,000) and show the calculated total. Blank means unknown, **not zero**.
- Cost controls shall distinguish **run-specific EUR amount**, **flat-rate/subscription** and **unknown**, showing the amount input only for the first case. A nonallocated cost must not be treated as zero.
- Total agent runtime shall be **computed from recorded iterations** rather than elicited redundantly in the final form.

**Acceptance:** moving a duration/score slider updates its paired numeric value; typing an exact value updates the slider; assistive text remains available via keyboard focus; optional token inputs and missing costs are never auto-filled with zero; the chosen cost mode governs which amount field is visible.

### NFR-UX-004 — Concise, resumable benchmark forms

The experimental installation step shall reference reusable **installation guides**, distinct from the first prompt or subsequent input exchanges. Those exchanges belong to the timed interactions. Generic/unassigned installation guides shall always be selectable; guides linked to a measured AI Solution shall only appear for the **exact matching versioned configuration**, not any configuration that merely shares its component names. Changing a selected solution or configuration shall refresh applicable guide options; submission shall reject an incompatible linked guide even if controls are bypassed. The workgroup's guided Test Case session shall remain resumable with previously saved installation-guide and interaction snapshots.

The final result form shall avoid duplicated deliverable narrative fields: one canonical **Produced outputs** entry shall be followed by only one free-form **Additional notes (optional)** field, aside from explicitly metric-linked evaluations.

**Acceptance:** create two differently configured solutions sharing the same model/provider/harness; a guide linked to the first shall be unavailable and rejected under the second. Generic guides remain selectable. Documents and skills supplied in interactions shall not be stored as setup inputs in new run records, and previously saved run records remain readable.

All form modals remain protected from accidental outside-click dismissal under **NFR-UX-001**.

## 2. Cross-cutting system qualities

The following requirements were separated from the Product Definition's original non-functional section. They remain platform-level requirements and **are not claimed as fully implemented by the browser-only prototype**.

| ID | Quality attribute | Requirement |
| --- | --- | --- |
| NFR-TRC-001 | Traceability | Conclusions must link to source benchmark runs, evidence, reviews and applicable scoring models. |
| NFR-VRS-001 | Versioning and history | Preserve relevant changes to tasks, Test Cases, protocols, AI solutions, scoring rules and published guidance. |
| NFR-AUD-001 | Auditability | Official published recommendations should be reconstructible from recorded evidence and documented decision rules. |
| NFR-REP-001 | Reproducibility | Retain benchmark setup, artifact references and inputs needed to replay a benchmark where technically possible. |
| NFR-SEC-001 | Security | Enforce authentication/authorization for publication, data sensitivity classification and safe handling of code and documents. |
| NFR-ACC-001 | Shared access | Permit authorized readers to consult published data without requiring workgroup privileges. |
| NFR-INT-001 | Interoperability | Support machine-readable API/export formats and persistent references. |
| NFR-EXT-001 | Extensibility | Support additional business units, task taxonomies, providers, harnesses, evaluation approaches and reporting views. |
| NFR-MNT-001 | Maintainability | Keep catalog objects, experimental records, scoring, decisions and documentation logically separated. |
| NFR-FRS-001 | Timeliness | Record freshness, service availability, retirement/deprecation and when recommendations require requalification. |

## 3. Documentation and validation rules

- **Functional specification:** the [Product Definition](product-definition.md) describes roles, data objects, business workflows and expected outcomes.
- **Non-functional specification (this file):** describes usability, interaction consistency and platform quality constraints. New global UX rules should be added here, rather than embedded in individual workflow descriptions.
- **Workflow guides:** for example, [Benchmark Campaign Workflow](benchmark-workflow.md), explain how users perform a task and should reference the relevant NFR when necessary.
- **Validation:** include positive and negative cases for form and non-form dialogs, and re-run them whenever the shared modal implementation changes.

**Prototype boundary.** Form dismissal behavior is implemented in the single-file HTML prototype and can be verified by its event handlers. Its simulated roles, `localStorage` data, exports and audit trail do not replace production-grade authentication, secure persistence, or independent accessibility and end-to-end browser testing.
