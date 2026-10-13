"""Normative §13 scenario registry: every check maps to a requirement, or is blocked.

The registry is the machine-readable half of docs/ux-acceptance-matrix.md. A
scenario is only reported as verified when *all* of its mapped checks ran and
passed in the same run; a missing or failing check can never be silently
reported as satisfied.
"""

SOURCE = "docs/role-based-user-experience-and-guided-navigation.md#13-recommended-ux-validation-journeys"

SCENARIOS = [
    {"id": "S13-01", "state": "verified",
     "title": "Engineer with a defined job/specialty: Task-first discovery, By Task/By Tool, "
              "solution detail, contextual return with filters preserved",
     "personas": "Engineer (reader)", "mode": "Demo + Server",
     "fixture": "Fictional Demo engineer seed; empty authenticated Server catalog",
     "checks": ["Standalone Demo engineer 1366", "Authenticated Server engineer 1366"]},
    {"id": "S13-02", "state": "verified",
     "title": "Windows-only engineer sees Windows-capable tools first; Linux-only "
              "alternatives stay discoverable with 'Requires Linux'",
     "personas": "Engineer (reader)", "mode": "Demo + Server",
     "fixture": "Fictional Demo OS metadata (delivered by UX-R06 #125)",
     "checks": ["Standalone Demo multi-role persona journeys 1366"]},
    {"id": "S13-03", "state": "verified",
     "title": "Engineer without a complete workload profile sees an explicit "
              "profile-not-configured state and no invented Task membership",
     "personas": "Engineer (reader)", "mode": "Demo + Server",
     "fixture": "Empty authenticated Server; Demo engineer with simulation-only profile",
     "checks": ["Standalone Demo engineer 1366", "Authenticated Server engineer 1366"]},
    {"id": "S13-04", "state": "verified",
     "title": "Engineer with access submits usage feedback linked to a measured "
              "solution/Task with preserved permissions",
     "personas": "Engineer (reader)", "mode": "Demo + Server",
     "fixture": "Real seeded published measured Server Run (UX-R06 #125)",
     "checks": ["Authenticated Server Engineer feedback and Management drill-down 1366"]},
    {"id": "S13-05", "state": "blocked",
     "title": "Deployment-eligible engineer without access expresses interest; the "
              "structured DAP access request stays linked and is not modeled as a ticket",
     "personas": "Engineer (reader)", "mode": "Server",
     "checks": [],
     "reason": "The interest/discussion path is delivered (UX-R06 #125), but a *structured "
               "access-request object with a resolvable approval status* does not exist and "
               "is an explicit owner/product decision, not part of #125 or #126. No proxy "
               "assertion is substituted."},
    {"id": "S13-06", "state": "blocked",
     "title": "Engineer proposes a new use from Task context without creating a mandatory "
              "Watch/Forecast/Task or a Workgroup To-Do",
     "personas": "Engineer (reader)", "mode": "Server",
     "checks": [],
     "reason": "Owned by UX-R06 (#125); the idea-submission UI does not exist yet on this "
               "base, so it is reported as blocked instead of an unexecuted pass."},
    {"id": "S13-07", "state": "verified",
     "title": "Engineer follows published Workgroup knowledge only: no internal drafts "
              "and no privileged Activity Feed events",
     "personas": "Engineer (reader) vs Contributor", "mode": "Demo + Server",
     "fixture": "Demo draft Guide and internal Activity event; internal Server Watch entry",
     "checks": ["Standalone Demo publication boundary 1366",
                "Authenticated Server publication boundary 1366",
                "Authenticated Server workgroup 1366"]},
    {"id": "S13-08", "state": "verified",
     "title": "Multi-role user switches Engineer -> Workgroup -> Management -> Maintenance "
              "only when permitted, without logout, and cannot reach unavailable APIs",
     "personas": "Multi-role contributor + planner + user-admin", "mode": "Server",
     "fixture": "Combined-grant fixture plus single-capability fixtures",
     "checks": ["Authenticated Server multi-role workspace switching 1366",
                "Authenticated Server authorization fail-closed 1366",
                "Authenticated Server multi_role 1366"]},
    {"id": "S13-09", "state": "verified",
     "title": "Workgroup Studio loads the five themed blocks, emphasizes core study areas, "
              "keeps semantic links and no mandatory sequence, including the "
              "Profitability -> Technology Catalog opportunity link",
     "personas": "Contributor", "mode": "Demo + Server",
     "fixture": "Fictional Demo seed; empty authenticated Server catalog",
     "checks": ["Standalone Demo workgroup 1366", "Authenticated Server workgroup 1366"]},
    {"id": "S13-10", "state": "verified",
     "title": "Counters: one resolvable count for under-review Campaigns, no artificial "
              "pending count where no closure state exists",
     "personas": "Contributor", "mode": "Demo",
     "fixture": "Demo under-review Campaign and Watch/feedback fixtures",
     "checks": ["Standalone Demo workgroup 1366"]},
    {"id": "S13-11", "state": "partial",
     "title": "Direct path from the Workgroup diagram into Benchmark, a Campaign and the "
              "exact Run, then breadcrumbs/browser Back without losing context",
     "personas": "Contributor, Engineer", "mode": "Demo + Server",
     "fixture": "Demo Campaign/Run fixtures; Server stable views",
     "checks": ["Standalone Demo workgroup 1366", "Standalone Demo engineer 1366",
                "Authenticated Server multi_role 1366",
                "Standalone Demo draft/Run-stepper 1366"]},
    {"id": "S13-12", "state": "verified",
     "title": "Run stepper traverses Setup -> Interactions -> Results, survives navigation "
              "and restores local unsaved fields without phantom Server Runs",
     "personas": "Contributor", "mode": "Server",
     "fixture": "Real Server campaign/session/run (UX-R05 #124)",
     "checks": ["Standalone Demo draft/Run-stepper 1366",
                "Authenticated Server draft/stepper/conflict/ownership 1366"]},
    {"id": "S13-13", "state": "verified",
     "title": "Incompatible local draft is invalidated without migrating authoritative "
              "campaign/evidence records",
     "personas": "Contributor", "mode": "Demo + Server",
     "fixture": "Injected stale-revision/expired/foreign-scope draft entries",
     "checks": ["Demo/Server draft isolation contract 1366"]},
    {"id": "S13-14", "state": "verified",
     "title": "Concurrent Campaign edit: a stale save returns 409 and keeps the unsaved "
              "draft with no silent overwrite or automatic merge",
     "personas": "Two independent contributors", "mode": "Server",
     "fixture": "Real persisted Setup Guide revised by two Chromium sessions",
     "checks": ["Authenticated Server revision conflict 409 1366"]},
    {"id": "S13-15", "state": "verified",
     "title": "Run edit ownership: a second contributor cannot hijack another person's "
              "active Run but can open a separate Run",
     "personas": "Contributor", "mode": "Server",
     "fixture": "Two contributor sessions over a real Server Run (UX-R05 #124)",
     "checks": ["Authenticated Server draft/stepper/conflict/ownership 1366"]},
    {"id": "S13-16", "state": "partial",
     "title": "Recommendations remain editorial opinions linked to Task/Solution/Run, "
              "editable through the existing role-gated flow, and a published failed Run "
              "never becomes a positive recommendation automatically",
     "personas": "Contributor, Engineer", "mode": "Demo + Server",
     "fixture": "Demo published recommendations with a failed Run",
     "checks": ["Standalone Demo workgroup 1366", "Standalone Demo engineer 1366",
                "Server Recommendation review/withdraw lifecycle 1366"],
     "reason": "Role-gated recommendation visibility, the shared read view and the real "
               "Server publish/withdraw lifecycle (UX-R04 #123 / UX-R05 #124) are verified. "
               "The specific 'a published failed Run is never made a positive "
               "recommendation' editorial rule is asserted by the backend suite "
               "(config.test_updates), not by a Chromium journey, so it is reported as a "
               "named gap rather than a browser-verified pass."},
    {"id": "S13-17", "state": "partial",
     "title": "Management lands on authorized DAP metrics and can open a sourced result "
              "without exposing restricted individual rates",
     "personas": "Planner", "mode": "Demo + Server",
     "fixture": "Demo opportunity heatmap; empty authenticated Server planning data",
     "checks": ["Standalone Demo management 1366", "Authenticated Server management 1366",
                "Authenticated Server authorization fail-closed 1366",
                "Authenticated Server Engineer feedback and Management drill-down 1366"]},
    {"id": "S13-18", "state": "verified",
     "title": "Maintenance-only identity enters /maintenance with its authorized health "
              "views and without Workgroup business editing or account administration",
     "personas": "Maintainer", "mode": "Server",
     "fixture": "Maintenance fixture plus a reader fixture attempting the same route",
     "checks": ["Authenticated Server maintenance 1366",
                "Authenticated Server authorization fail-closed 1366"]},
    {"id": "S13-19", "state": "verified",
     "title": "Demo/Server: the shared frontend works with separately scoped records, the "
              "local draft cache never crosses modes and a Server outage never falls back "
              "to fake Demo data",
     "personas": "Contributor, Engineer", "mode": "Demo + Server",
     "fixture": "Offline Demo seed, real Server session, aborted API traffic",
     "checks": ["Standalone Demo workgroup 1366", "Demo/Server draft isolation contract 1366",
                "Authenticated Server offline isolation 1366",
                "Standalone Demo publication boundary 1366"]},
    {"id": "S13-20", "state": "verified",
     "title": "Desktop keyboard and assistive-technology traversal of diagram nodes, "
              "counts, steppers and breadcrumbs",
     "personas": "All fixtures", "mode": "Demo + Server",
     "fixture": "Real Chromium desktop sessions",
     "checks": ["Mutation probes (deliberate UI defects rejected)",
                "Standalone Demo workgroup 1366", "Standalone Demo engineer 1366",
                "Standalone Demo management 1366",
                "Authenticated Server workgroup 1366",
                "Authenticated Server multi_role 1366"],
     "reason": "Focus containment, focus return, tab order, accessible dialog/control names, "
               "one current location and one main landmark are asserted. This is not a "
               "screen-reader session and does not certify AT narration quality."},
]

MODALS = [
    {"id": "NFR-UX-001", "state": "verified",
     "title": "A dialog containing a form stays open on backdrop click and Escape and "
              "never loses unsaved fields",
     "personas": "Contributor", "mode": "Demo + Server",
     "fixture": "Real Demo/Server editors with an unfinished form",
     "checks": ["Mutation probes (deliberate UI defects rejected)",
                "Standalone Demo workgroup 1366",
                "Authenticated Server workgroup 1366"]},
    {"id": "NFR-UX-002", "state": "verified",
     "title": "Every dialog exposes an accessible close control and returns focus to its "
              "invoker",
     "personas": "Contributor", "mode": "Demo + Server",
     "fixture": "Real Demo/Server editors opened from a visible trigger",
     "checks": ["Mutation probes (deliberate UI defects rejected)",
                "Authenticated Server workgroup 1366"]},
    {"id": "NFR-A11Y-01", "state": "verified",
     "title": "Semantic headings, labelled controls, one main landmark and exactly one "
              "current location on every rendered desktop view",
     "personas": "All fixtures", "mode": "Demo + Server",
     "fixture": "Every view rendered by the journeys",
     "checks": ["Standalone Demo workgroup 1366", "Standalone Demo engineer 1366",
                "Standalone Demo management 1366",
                "Authenticated Server workgroup 1366", "Authenticated Server engineer 1366",
                "Authenticated Server management 1366",
                "Authenticated Server maintenance 1366",
                "Authenticated Server multi_role 1366"]},
    {"id": "NFR-ERR-01", "state": "verified",
     "title": "No uncaught JavaScript exception and no unexpected HTTP failure during a "
              "desktop journey",
     "personas": "All fixtures", "mode": "Demo + Server",
     "fixture": "Real Chromium console/network capture",
     "checks": ["Standalone Demo workgroup 1366", "Standalone Demo engineer 1366",
                "Standalone Demo management 1366",
                "Authenticated Server workgroup 1366", "Authenticated Server engineer 1366",
                "Authenticated Server management 1366",
                "Authenticated Server maintenance 1366",
                "Authenticated Server multi_role 1366"]},
]

STATUS_LABEL = {"verified": "VERIFIED", "partial": "PARTIAL",
                "blocked": "BLOCKED", "unmapped": "UNMAPPED", "failed": "FAILED"}


def resolve(entries, results):
    """Attach the observed result of every mapped check to each requirement."""
    table = []
    unmapped = []
    for entry in entries:
        row = dict(entry)
        row["results"] = []
        missing = []
        for name in entry["checks"]:
            outcome = results.get(name)
            if outcome is None:
                missing.append(name)
            else:
                row["results"].append({"check": name, **outcome})
        failed = [item for item in row["results"] if item["result"] == "FAIL"]
        if entry["state"] in ("blocked",):
            row["status"] = STATUS_LABEL["blocked"]
        elif missing:
            row["status"] = STATUS_LABEL["unmapped"]
            unmapped.append({"requirement": entry["id"], "missing_checks": missing})
        elif failed:
            row["status"] = STATUS_LABEL["failed"]
        elif entry["state"] == "partial":
            row["status"] = STATUS_LABEL["partial"]
        else:
            row["status"] = STATUS_LABEL["verified"]
        table.append(row)
    return table, unmapped


def build(results):
    rows, unmapped = resolve(SCENARIOS + MODALS, results)
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    return {"source": SOURCE, "requirements": rows, "counts": counts,
            "unmapped": unmapped}
