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
