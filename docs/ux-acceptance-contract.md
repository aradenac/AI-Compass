# UI acceptance contract — AI Compass

> **Status:** Normative interaction acceptance derived from the approved [role-based UX specification](role-based-user-experience-and-guided-navigation.md) and [NFR](non-functional-requirements.md). **Visual proposal**, not an owner-approved golden screenshot. Final visual approval is separate from executable correctness.
> **Scope:** Standalone fictional Demo, real authenticated Server, Workgroup, Engineer, Management and independent Maintenance.
> **Delivery:** UX-R01 [#114](https://github.com/aradenac/AI-Compass/issues/114) sets up the gate; [#115](https://github.com/aradenac/AI-Compass/issues/115) and [#116](https://github.com/aradenac/AI-Compass/issues/116) bring the old screens into conformance. No synthetic fixtures may become live Server business records.

## Shared shell — desktop (reference layout)

    ┌────────────────────┬────────────────────────────────────────────────────────────────┐
    │ AI COMPASS         │ Current location / role               Account / workspace ▼ │
    │                    ├────────────────────────────────────────────────────────────────┤
    │ Discover           │ Breadcrumb: Studio › Campaign › Run › Evidence              │
    │  Task Explorer     │                                                                │
    │  Catalog           │  Page heading                    Contextual actions            │
    │                    │  Short purpose / status / source provenance                 │
    │ Benchmark          │ ┌────────────────────────────────────────────────────────────┐ │
    │  Test Cases        │ │ Selected primary content, list/detail/stepper as required │ │
    │  Campaigns         │ │                                                    │ │
    │  Results           │ └────────────────────────────────────────────────────────────┘ │
    │                    │                                                                │
    │ Knowledge          │ Secondary context only when it relates to active selection    │
    │  Guides            │                                                                │
    └────────────────────┴────────────────────────────────────────────────────────────────┘

- Exactly **one active business view** (not one per authorized capability). No unrelated Catalog, Admin, Planning and editor sections displayed in parallel.
- Selected location and role are unambiguous. A user with multiple roles can switch workspace without signing in again. Permission-gated API calls always remain authoritative.
- Workgroup entry is **one grouped five-zone knowledge map**, not a long stack of sections, duplicated list+editor+preview shells, or a support-ticket inbox.
- Engineer entry is **Task-first**, with optional By Tool inversion, then one assembled Solution Detail, current Guide and Feedback/interest.
- Management entry uses the **Task × candidate economic heatmap**, a clear maturity indicator, and progressive drill-down to calculation factors and exact evidence.
- Maintenance remains a **separate controlled workspace**, with audit/governance, health and authorized operations only.
- All four entries use the same visual primitives, hierarchy, text style and content density. The backend mode changes data, not the presentation language.

## Contextual navigation — top down AND bottom up

    Studio / My AI Workspace / Management
       └── Task or Campaign
              └── Test Case / AI Solution
                     └── Run / source
                            └── Evidence / exact revision
                     ↑ Back to the same Run with source context intact
              ↑ Back to original filtered Task/Campaign
       ↑ Return to original role landing without clearing the user's context

- Stable deep links resolve the exact object/revision. Breadcrumbs return to the same logical origin; back/forward works.
- Preserve selected object, filters, expanded tree branch, permitted revision and scroll position when practical.
- Do not show JSON/raw source dumps as the default business detail. Raw revision inspection remains an explicitly requested advanced view.
- A stepper is for truly sequential Run actions; general browsing must not be forcibly linear.

## Form/modal reference — both modes

    ┌─────────────────────── darkened backdrop ───────────────────────────────────┐
    │             ┌────────────────────────────────────────────┐                   │
    │             │ Create / edit / reply                 [×]  │                   │
    │             ├────────────────────────────────────────────┤                   │
    │             │ Clear title, labeled controls              │                   │
    │             │ Inline field errors and draft preservation │                   │
    │             ├────────────────────────────────────────────┤                   │
    │             │ [Cancel]                        [Save]      │                   │
    │             └────────────────────────────────────────────┘                   │
    └──────────────────────────────────────────────────────────────────────────────┘

- NFR-UX-001: A dialog containing a form **must remain open** on backdrop click and Escape. Unsaved fields never disappear from these gestures. Explicit × or Cancel dismisses.
- NFR-UX-002: Every dialog has an accessible × Close button. A read-only dialog may allow Escape/backdrop dismissal.
- Focus, keyboard navigation and screen reader dialog names are required. A closed dialog returns focus to its invoker when possible.
- Server must not convert an expected modal into an inline editor simply because it reuses the same API/validation.

## Visual direction — design tokens to validate, NOT current screenshot goldens

| Token | Reference intent |
| --- | --- |
| Typography | System sans, 16px default body, strong but compact headings, readable labels; no 12px body paragraphs |
| Spacing | 4px base, 8/12/16/24/32px scale with intentional grouping |
| Content | One primary page canvas; max readable narrative column; data tables may grow within viewport |
| Surfaces | Calm neutral background, white content surfaces, subtle borders, restrained shadow |
| Semantic color | Neutral navigation; one primary interaction accent; separate danger/warning/success states, never color-only statuses |
| Controls | Consistent buttons, focus rings, input heights and modal dimensions |
| Responsive | At <=768px, compact navigation, one-column content, scrollable tables without whole-page horizontal overflow |
| Density | Progressive disclosure: summary first, advanced provenance on demand, no repeated permanent admin/diagnostics blocks |
| Accessibility | Keyboard-operable actions, visible focus, labels, dialogs, state announcement and adequate contrast |

The above are **design expectations**, not claims that current product screenshots are correct. Do not use an unreviewed baseline update to make a visual regression pass.

## Browser test matrix

| Journey / invariant | Desktop 1366×900 | Mobile 390×844 | Demo | Server |
| --- | --- | --- | --- | --- |
| First sign-in / persona entry | Required | Required | Fictional identity | Real session + CSRF |
| Workgroup navigation | Required | Required | Fictional | Contributor |
| Engineer Task-first | Required | Required | Fictional | Reader |
| Management insight | Required | Required | Fictional | Planner |
| Maintenance and audit | Required | Required | Not a privileged Demo API | Maintainer |
| Multiple roles, single active view | Required | Required | Simulated role switch | Combined grants |
| Back/breadcrumb and modal interactions | Required | Required | Representative | Representative |
| No page errors / no unintended overflow | Required | Required | Required | Required |
| Data isolation / no fallback | Required | Required | Zero API use | Real authenticated API only |

**Gate maturity:** R01 supplies real browser smoke, representative captures, traces and deliberately broken mutation fixtures that prove detectors work. R02 and R03 must promote the current live single-view, modal and contextual-journey invariants from diagnostic findings to mandatory failing checks. A preexisting broken UI must never be approved as its own golden baseline.

## Review / evidence protocol

1. The agent runs Chromium against disposable, uniquely named users, checks the report and **opens representative screenshots/traces** instead of trusting a green label.
2. A targeted interaction failure is **FAIL**, not "best effort". The full report identifies untested and not-yet-certified UX.
3. Upload a JSON report, readable Markdown summary, replayable traces and screenshots on every CI run. No passwords, actual production data, tokens or privileged real evidence may enter artifacts.
4. Intentional visual updates require a change proposal against these references; snapshot approval must be explicit, not an auto-updated image. Backend immutability and RBAC remain separate acceptance requirements.
5. GitHub branch rule for protected \`main\`: require the exact workflow job status \`ui-qa\`; disallow bypass for ordinary merges and verify enforcement in GitHub settings. **A successful workflow by itself is not proof that this rule is enabled.** If the connector lacks rule-edit permission, keep the remaining enforcement action visible in #114 and never falsely claim it was configured.
6. Production release remains NO-GO under [release readiness](release-readiness.md), independently of browser CI.

## Local commands

    python3 -m pip install "playwright==1.56.0"
    python3 -m playwright install chromium
    python3 scripts/init-env.py
    docker compose up -d --build --wait
    docker compose exec -T api python manage.py migrate --noinput
    python3 scripts/ux_qa.py provision --output /tmp/uxqa-credentials.json
    python3 -m http.server 8090 --bind 127.0.0.1 --directory .
    # From a second shell:
    python3 scripts/ux_qa.py test --base-url http://127.0.0.1:8080 \
       --demo-url http://127.0.0.1:8090/prototype.html \
       --credentials /tmp/uxqa-credentials.json --artifacts /tmp/uxqa-report

Run against a **disposable database** only; the provisioner creates users and refuses to overwrite its credentials file. Inspect \`/tmp/uxqa-report/report.md\`, \`report.json\`, \`*.png\`, and \`*.zip\` with \`playwright show-trace\` (or Chromium trace viewer). This is separate from the existing full platform integrity/restore CI.
