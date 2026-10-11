"""Authenticated Server Chromium journeys: identity, grants, revisions and isolation."""
import json
import secrets

from .accessibility import PageWatch, assert_accessible, assert_dialog_focus
from .support import (assert_exactly_one_view, assert_no_horizontal_overflow,
                      assert_no_privileged_view, capture)

EXPECTED_GRANTS = {
    "workgroup": ["business_read", "business_write"],
    "engineer": ["business_read"],
    "management": ["planning_manage", "planning_view"],
    "maintenance": ["audit_view", "maintenance_triage", "maintenance_view"],
    "multi_role": ["business_read", "business_write", "planning_manage",
                   "planning_view", "users_manage", "users_view"],
}

# Every entry is a capability the fixture deliberately does not hold: the API must
# refuse it even when the caller edits the URL or calls the endpoint directly.
API_DENIALS = {
    "workgroup": [("GET", "/api/v1/planning/profiles", None),
                  ("GET", "/api/v1/maintenance/audit", None)],
    "engineer": [("POST", "/api/v1/guides", {"name": "refused probe", "text": "refused"}),
                 ("GET", "/api/v1/planning/profiles", None),
                 ("GET", "/api/v1/maintenance/audit", None)],
    "management": [("GET", "/api/v1/guides", None)],
    "maintenance": [("GET", "/api/v1/guides", None)],
    "multi_role": [("GET", "/api/v1/maintenance/audit", None)],
}

# The same fixtures must still read the evidence their own workspace displays.
API_ALLOWED = {
    "workgroup": [("GET", "/api/v1/guides", None)],
    "engineer": [("GET", "/api/v1/guides", None)],
    "management": [("GET", "/api/v1/planning/profiles", None)],
    "maintenance": [("GET", "/api/v1/maintenance/audit", None)],
    "multi_role": [("GET", "/api/v1/planning/profiles", None)],
}

LANDING_ROUTES = {
    "workgroup": "/?mode=server&workspace=workgroup",
    "engineer": "/?mode=server&workspace=engineer",
    "management": "/?mode=server&workspace=management",
    "maintenance": "/maintenance?mode=server",
    "multi_role": "/?mode=server&workspace=workgroup",
}

LANDING_SCREEN = {
    "workgroup": "#server-workgroup-home",
    "engineer": "#server-engineer",
    "management": "#server-management-insights",
    "maintenance": "#server-governance-audit",
    "multi_role": "#server-workgroup-home",
}

PERSONA_PERMISSION = {"engineer": "business_read", "workgroup": "business_write",
                      "management": "planning_view", "maintenance": "maintenance_view"}

PERSONA_SCREEN = {"engineer": "#server-engineer", "workgroup": "#server-workgroup-home",
                  "management": "#server-management-insights",
                  "maintenance": "#server-governance-audit"}


def available_personas(role):
    """The switcher may only offer workspaces the fixture is actually granted."""
    grants = EXPECTED_GRANTS[role]
    return [name for name, permission in PERSONA_PERMISSION.items() if permission in grants]


def sign_in(page, base_url, creds, role, path=None, timeout=25000):
    page.goto(base_url + (path or LANDING_ROUTES[role]), wait_until="domcontentloaded")
    page.locator("#server-login-form").wait_for(state="visible", timeout=timeout)
    page.locator("#server-username").fill(creds[role]["username"])
    page.locator("#server-password").fill(creds[role]["password"])
    page.get_by_role("button", name="Sign in to Server").click()
    page.locator("#server-login-form").wait_for(state="hidden", timeout=timeout)
    page.locator('#ux-screen-host[data-ux-current]').wait_for(state="visible", timeout=timeout)


def csrf(page):
    return page.evaluate(
        "() => (document.cookie.match(/csrftoken=([^;]+)/) || [])[1]")


def api(page, base_url, method, path, body=None):
    if method == "GET":
        return page.request.get(base_url + path)
    return page.request.post(base_url + path, data=json.dumps(body or {}),
                             headers={"Content-Type": "application/json",
                                      "X-CSRFToken": csrf(page), "Referer": base_url + "/"})


def assert_grant_matrix(page, base_url, role):
    """The fixture's real capabilities and refusals are enforced by Django."""
    identity = page.request.get(base_url + "/api/v1/auth/me").json()
    if not identity.get("authenticated"):
        raise AssertionError("Server session was not established for " + role)
    if sorted(identity.get("permissions", [])) != EXPECTED_GRANTS[role]:
        raise AssertionError("Fixture grants for " + role + " changed: " +
                             json.dumps(sorted(identity.get("permissions", []))))
    for method, path, body in API_DENIALS[role]:
        response = api(page, base_url, method, path, body)
        if response.status != 403:
            raise AssertionError(
                f"{role} was not refused {method} {path}: HTTP {response.status}")
    for method, path, body in API_ALLOWED[role]:
        response = api(page, base_url, method, path, body)
        if response.status != 200:
            raise AssertionError(
                f"{role} could not read its own authorized {path}: HTTP {response.status}")


def assert_location_fail_closed(page, base_url, role, path, forbidden_selector, forbidden_label):
    """A refused route must not render the surface nor claim it in the breadcrumb."""
    page.goto(base_url + path, wait_until="domcontentloaded")
    page.locator('#ux-screen-host[data-ux-current]').wait_for(state="visible", timeout=25000)
    page.wait_for_timeout(400)
    assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
    assert_no_privileged_view(page, forbidden_selector, role + " navigation to " + path)
    crumbs = page.locator("#ux-context-navigation").inner_text()
    if forbidden_label in crumbs:
        raise AssertionError(
            f"{role} breadcrumb claims a refused location ({forbidden_label}): {crumbs!r}")
    if page.locator('#server-side-navigation a[aria-current="page"]').count() != 1:
        raise AssertionError(f"{role} lost its single active navigation entry after {path}")
    return crumbs.strip()


def server_journey(browser, base_url, creds, artifacts, role, viewport):
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    traced = False  # Keep the password entry entirely outside the downloadable trace.
    page = context.new_page()
    page.set_default_timeout(15000)
    watch = PageWatch(page)
    findings = []
    try:
        sign_in(page, base_url, creds, role)
        page.locator(LANDING_SCREEN[role]).wait_for(state="visible", timeout=25000)
        if page.locator("#server-account-name").text_content() != creds[role]["username"]:
            raise AssertionError("Authenticated user does not match the fixture")
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        traced = True
        page.reload(wait_until="domcontentloaded")
        page.locator("#server-login-form").wait_for(state="hidden", timeout=25000)
        page.locator('#ux-screen-host[data-ux-current]').wait_for(state="visible", timeout=25000)
        if page.locator(".ux-shell").count() != 1:
            raise AssertionError("Competing Server application shells")
        assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
        if not page.locator(".ux-shell .ux-sidebar").is_visible():
            raise AssertionError("Server sidebar missing from shared shell")
        if role == "multi_role" and page.locator("#server-users").is_visible():
            raise AssertionError("Users & Access leaked onto Workgroup screen")
        if role == "engineer" and page.locator("#server-planning").is_visible():
            raise AssertionError("Planning leaked into Engineer screen")
        assert_no_horizontal_overflow(page)
        assert_accessible(page, "Server " + role + " landing", review=findings)
        capture(page, artifacts, "server-" + role + "-" + str(viewport["width"]))
        # Deliberate authorization probes run from a separate page so the journey's
        # own console/network gate is not polluted by expected 403 refusals.
        probe = context.new_page()
        probe.goto(base_url + "/?mode=server", wait_until="domcontentloaded")
        assert_grant_matrix(probe, base_url, role)
        watch.assert_clean("Server " + role + " landing")
        # UX-R02 routes one domain at a time. Check real form dialogs as well
        # (a green static HTML test must never substitute for this interaction).
        if role == "workgroup":
            # Empty real Server is legitimate; Demo fixtures must NEVER leak.
            # Each domain is rendered by the same list component as offline Demo.
            for section, domain in [
                ("guides", "guides"), ("watch", "watch"),
                ("feedback", "feedback"), ("recommendations", "recommendations"),
                ("benchmark", "campaigns"), ("forecasts", "forecasts")
            ]:
                page.goto(base_url + "/?mode=server&workspace=workgroup&section=" + section + "&view=editor",
                          wait_until="domcontentloaded")
                page.locator(
                    f'[data-business-domain="{domain}"], [data-business-empty="{domain}"]'
                ).first.wait_for(state="visible", timeout=30000)
                assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
                assert_no_horizontal_overflow(page)
                assert_accessible(page, "Server workgroup " + domain, review=findings)
                if domain in ("guides", "campaigns"):
                    capture(page, artifacts, "server-shared-" + domain + "-" + str(viewport["width"]))
        if role == "workgroup":
            # Real Server write must remain persisted and revision-addressable.
            page.goto(base_url + "/?mode=server&workspace=workgroup&section=guides&view=editor",
                      wait_until="domcontentloaded")
            page.locator("#guide-add").wait_for(state="visible", timeout=30000)
            page.locator("#guide-add").click()
            form = page.locator("#guide-editor form.guide-form")
            form.wait_for(state="visible", timeout=12000)
            assert_dialog_focus(page, "Server Guide editor")
            page.locator("#guide-add").click()
            form = page.locator("#guide-editor form.guide-form")
            form.wait_for(state="visible", timeout=12000)
            fields = form.locator('[data-shared-guide-fields="server"]')
            fields.locator('input[name="name"]').fill("UX-R04 persisted setup guide")
            fields.locator('textarea[name="text"]').fill("Original controlled instructions")
            fields.locator('textarea[name="description"]').fill("Keep revisions and provenance")
            fields.locator('input[name="url"]').fill("https://example.org/server-guide")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "server-shared-guide-form-" + str(viewport["width"]))
            form.locator('button[type="submit"]').click()
            card = page.locator('[data-business-domain="guides"] [data-business-record]').filter(
                has_text="UX-R04 persisted setup guide").first
            card.wait_for(state="visible", timeout=30000)
            page.reload(wait_until="domcontentloaded")
            card = page.locator('[data-business-domain="guides"] [data-business-record]').filter(
                has_text="UX-R04 persisted setup guide").first
            card.wait_for(state="visible", timeout=30000)
            card.locator('button[data-action="inspect"]').click()
            detail = page.locator('[data-shared-guide-detail="server"]')
            detail.wait_for(state="visible", timeout=30000)
            for expected in ("Original controlled instructions",
                             "Keep revisions and provenance",
                             "https://example.org/server-guide"):
                if expected not in detail.inner_text():
                    raise AssertionError("Server Guide content missing: " + expected)
            page.locator("#guide-history details").first.wait_for(state="visible")
            assert_accessible(page, "Server workgroup guide detail", review=findings)
            capture(page, artifacts, "server-shared-guide-detail-" + str(viewport["width"]))
        if role == "workgroup":
            # Create a real Watch hypothesis without inventing external evidence.
            page.goto(base_url + "/?mode=server&workspace=workgroup&section=watch&view=editor",
                      wait_until="domcontentloaded")
            page.locator("#watch-add-entry").wait_for(state="visible", timeout=30000)
            page.locator("#watch-add-entry").click()
            watch_form = page.locator("#watch-form")
            watch_form.wait_for(state="visible")
            watch_form.locator('input[name="name"]').fill("UX-R04 Watch detail")
            watch_form.locator('textarea[name="hypothesis"]').fill(
                "An unmeasured, source-independent hypothesis")
            watch_form.locator('textarea[name="assumptions"]').fill(
                "Uncertainty must remain explicit")
            watch_form.locator('button[type="submit"]').click()
            watch_card = page.locator('[data-business-domain="watch"] [data-business-record]').filter(
                has_text="UX-R04 Watch detail").first
            watch_card.wait_for(state="visible", timeout=30000)
            page.reload(wait_until="domcontentloaded")
            watch_card = page.locator('[data-business-domain="watch"] [data-business-record]').filter(
                has_text="UX-R04 Watch detail").first
            watch_card.wait_for(state="visible", timeout=30000)
            watch_card.locator('button[data-action="inspect"]').click()
            detail = page.locator(
                '[data-knowledge-domain="watch"][data-knowledge-mode="server"]')
            detail.wait_for(state="visible", timeout=30000)
            for expected in ("An unmeasured, source-independent hypothesis",
                             "Uncertainty must remain explicit"):
                if expected not in detail.inner_text():
                    raise AssertionError("Watch detail lost controlled content: " + expected)
            page.locator("#watch-detail details").first.wait_for(state="visible")
            capture(page, artifacts, "server-shared-watch-detail-" + str(viewport["width"]))
        if role in ("workgroup", "multi_role"):
            page.goto(base_url + "/?mode=server&workspace=workgroup&section=testdesign&view=editor",
                      wait_until="domcontentloaded")
            page.locator("#case-new").wait_for(state="visible", timeout=25000)
            assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
            page.locator("#case-new").click()
            dialog = page.locator("#case-editor[role=dialog]")
            dialog.wait_for(state="visible", timeout=15000)
            if dialog.get_attribute("aria-modal") != "true":
                raise AssertionError("Editable form was not promoted to an accessible dialog")
            if dialog.locator("form").count() != 1:
                raise AssertionError("Test Case form missing from dialog")
            box = dialog.locator('input[name="name"]')
            box.fill("Unsaved browser QA text")
            page.locator(".ux-dialog-backdrop").click(position={"x": 2, "y": 2}, force=True)
            page.keyboard.press("Escape")
            if not dialog.is_visible() or box.input_value() != "Unsaved browser QA text":
                raise AssertionError("Backdrop/Escape unexpectedly dismissed the form or lost draft")
            dialog.get_by_role("button", name="Close dialog").click()
            dialog.wait_for(state="hidden")
            if role == "workgroup":
                # Real persisted Test Design round-trip: UI Task creation -> TC
                # save -> same shared presenter after a full browser reload.
                page.goto(base_url + "/?mode=server&workspace=workgroup&section=tasks&view=editor",
                          wait_until="domcontentloaded")
                page.locator("#server-task-add-root").wait_for(state="visible", timeout=30000)
                page.locator("#server-task-add-root").click()
                task_dialog = page.locator("#server-task-editor[role=dialog]")
                task_dialog.wait_for(state="visible", timeout=15000)
                task_name = "UX-R04 reusable browser Task"
                task_dialog.locator('input[name="name"]').fill(task_name)
                task_dialog.get_by_role("button", name="Save task revision").click()
                task_dialog.wait_for(state="hidden", timeout=25000)
                page.locator(".server-task-node").filter(has_text=task_name).first.wait_for(
                    state="visible", timeout=25000)
                page.goto(base_url + "/?mode=server&workspace=workgroup&section=testdesign&view=editor",
                          wait_until="domcontentloaded")
                page.locator("#case-new").wait_for(state="visible", timeout=30000)
                page.locator("#case-new").click()
                case_dialog = page.locator("#case-editor[role=dialog]")
                case_dialog.wait_for(state="visible", timeout=15000)
                case_title = "UX-R04 preserved browser challenge"
                case_dialog.locator('input[name="name"]').fill(case_title)
                task_choice = case_dialog.locator('select[name="task_id"] option').filter(
                    has_text=task_name).first
                task_id = task_choice.get_attribute("value")
                if not task_id:
                    raise AssertionError("Created real Task was not selectable")
                case_dialog.locator('select[name="task_id"]').select_option(task_id)
                case_dialog.locator('textarea[name="objective"]').fill(
                    "Validate shared Demo and Server presentation")
                case_dialog.locator('textarea[name="inputs"]').fill(
                    "Synthetic, disposable browser fixture")
                case_dialog.locator('textarea[name="dod"]').fill(
                    "Created object remains readable after reload")
                case_dialog.locator('button[type="submit"]').click()
                case_dialog.wait_for(state="hidden", timeout=30000)
                page.locator('[data-shared-case]').filter(has_text=case_title).first.wait_for(
                    state="visible", timeout=30000)
                capture(page, artifacts, "server-shared-test-cases-persisted-" +
                        str(viewport["width"]))
                page.reload(wait_until="domcontentloaded")
                page.locator('[data-shared-case]').filter(has_text=case_title).first.wait_for(
                    state="visible", timeout=30000)
                if page.locator('[data-shared-case-detail="demo"]').count():
                    raise AssertionError("Server Test Case incorrectly displayed Demo detail")
            if role == "multi_role":
                # Same authenticated session: Users & Access must be explicit,
                # and its account-creation form a protected, closed-by-default modal.
                page.goto(base_url + "/?mode=server&workspace=workgroup&section=users",
                          wait_until="domcontentloaded")
                page.locator("#server-user-open-create").wait_for(state="visible", timeout=25000)
                assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
                if page.locator("#server-test-cases").is_visible():
                    raise AssertionError("Test Case editor leaked into Users & Access")
                assert_accessible(page, "Server multi-role users & access", review=findings)
                page.locator("#server-user-open-create").click()
                user_dialog = page.locator("#server-user-create-panel[role=dialog]")
                user_dialog.wait_for(state="visible")
                page.keyboard.press("Escape")
                if not user_dialog.is_visible():
                    raise AssertionError("Escape incorrectly dismissed account-creation form")
                user_dialog.get_by_role("button", name="Close dialog").click()
                user_dialog.wait_for(state="hidden")
        if role in ("engineer", "workgroup"):
            # §13-08/§13-18: a route outside the resolved workspace must fail
            # closed in the content AND in the announced current location.
            assert_location_fail_closed(
                page, base_url, role, "/?mode=server&workspace=management&section=planning",
                "#server-management-insights", "Planning & Resources")
            if role == "engineer":
                assert_location_fail_closed(
                    page, base_url, role, "/?mode=server&workspace=workgroup&section=users",
                    "#server-users", "Users & Access")
        if role == "engineer":
            # §13-18: /maintenance is a separate controlled workspace.
            assert_location_fail_closed(
                page, base_url, role, "/maintenance?mode=server",
                "#server-governance-audit", "Audit & Changes")
            page.locator("#ux-auth-panel").wait_for(state="visible", timeout=20000)
            if page.locator("#server-account-name").text_content() != creds[role]["username"]:
                raise AssertionError("Maintenance fallback lost the authenticated identity")
        if role == "management":
            # Management sees authorized aggregate planning only, never the
            # Workgroup authoring editors.
            page.goto(base_url + "/?mode=server&workspace=management&section=planning",
                      wait_until="domcontentloaded")
            page.locator("#server-planning").wait_for(state="visible", timeout=25000)
            assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
            assert_no_privileged_view(page, "#server-test-cases", "Management route")
            assert_accessible(page, "Server management planning", review=findings)
            capture(page, artifacts, "server-management-planning-" + str(viewport["width"]))
        if role == "maintenance":
            # Maintenance-only identity keeps audit/health and nothing else.
            assert_location_fail_closed(
                page, base_url, role, "/?mode=server&workspace=workgroup&section=guides",
                "#server-guides", "Setup Guides")
            page.goto(base_url + "/maintenance?mode=server&section=health",
                      wait_until="domcontentloaded")
            page.locator("#server-data-health").wait_for(state="visible", timeout=25000)
            assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
            assert_accessible(page, "Server maintenance data health", review=findings)
            capture(page, artifacts, "server-maintenance-health-" + str(viewport["width"]))
        if role == "multi_role":
            # Fail closed: a missing protected record never resolves to a
            # different current record or a Demo fixture; foreign from rejected.
            page.goto(base_url +
                "/?mode=server&workspace=workgroup&section=watch&record=uxqa-not-present"
                "&revision=r999&from=%2F%2Fevil.example",
                wait_until="domcontentloaded")
            page.locator("#server-shared-summary").wait_for(state="visible", timeout=25000)
            page.locator("#server-shared-summary [role=alert]").wait_for(state="visible", timeout=20000)
            if page.locator(".ux-return-link").count():
                raise AssertionError("External navigation origin was accepted")
            assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
            page.goto(base_url + "/?mode=server&workspace=engineer&section=results"
                "&record=uxqa-missing-run&revision=r999", wait_until="domcontentloaded")
            page.locator("#ux-results-context [role=alert]").wait_for(state="visible", timeout=20000)
            if not page.locator("#ux-results-context").is_visible():
                raise AssertionError("Unavailable original Run was silently hidden")
        watch.assert_clean("Server " + role)
        return {"visible_active_screens": 1, "shared_shell": True,
                "grants": EXPECTED_GRANTS[role], "findings": findings}
    finally:
        if traced:
            context.tracing.stop(path=str(artifacts / ("server-" + role + "-" +
                                                       str(viewport["width"]) + ".zip")))
        context.close()


ROLES_INDEX = ["workgroup", "engineer", "management", "maintenance", "multi_role"]


def server_fail_closed_index(browser, base_url, creds, artifacts, viewport):
    """§13-08/§13-17/§13-18: URL edits and direct API calls never widen a role."""
    summary = {}
    refused_routes = {
        "engineer": [("/?mode=server&workspace=management&section=planning",
                      "#server-management-insights", "Planning & Resources"),
                     ("/maintenance?mode=server", "#server-governance-audit", "Audit & Changes")],
        "workgroup": [("/?mode=server&workspace=management&section=planning",
                       "#server-management-insights", "Planning & Resources"),
                      ("/maintenance?mode=server", "#server-governance-audit", "Audit & Changes")],
        "maintenance": [("/?mode=server&workspace=workgroup&section=guides", "#server-guides",
                         "Setup Guides")],
    }
    for role in ROLES_INDEX:
        context = browser.new_context(viewport=viewport, reduced_motion="reduce")
        page = context.new_page()
        page.set_default_timeout(30000)
        probe = context.new_page()
        try:
            sign_in(page, base_url, creds, role)
            probe.goto(base_url + "/?mode=server", wait_until="domcontentloaded")
            assert_grant_matrix(probe, base_url, role)
            denied = []
            for path, selector, label in refused_routes.get(role, []):
                crumbs = assert_location_fail_closed(page, base_url, role, path, selector, label)
                if label in crumbs:
                    raise AssertionError(f"{role} kept a refused breadcrumb for {path}")
                denied.append(path)
            summary[role] = {"grants": EXPECTED_GRANTS[role],
                             "api_denials": [path for _, path, _ in API_DENIALS[role]],
                             "refused_routes": denied}
        finally:
            context.close()
    return summary


def server_multirole_switch(browser, base_url, creds, artifacts, viewport):
    """§13-08: one session switches workgroup/management/engineer/maintenance."""
    summary = {}
    for role in ("multi_role", "maintenance"):
        context = browser.new_context(viewport=viewport, reduced_motion="reduce")
        page = context.new_page()
        page.set_default_timeout(25000)
        watch = PageWatch(page)
        expected = available_personas(role)
        try:
            sign_in(page, base_url, creds, role)
            page.locator(LANDING_SCREEN[role]).wait_for(state="visible", timeout=25000)
            account = page.locator("#server-account-name").text_content()
            offered = page.evaluate(
                "() => Array.from(document.querySelectorAll('.shared-personas a[data-persona]'))"
                ".map(a => a.dataset.persona)")
            if sorted(offered) != sorted(expected):
                raise AssertionError(
                    f"{role} switcher offers {sorted(offered)} but its grants allow "
                    f"{sorted(expected)}")
            for label in [item for item in expected if item != expected[0]] + [expected[0]]:
                persona = page.locator(f'.shared-personas a[data-persona="{label}"]')
                persona.click()
                page.locator(PERSONA_SCREEN[label]).wait_for(state="visible", timeout=25000)
                page.locator("#server-login-form").wait_for(state="hidden", timeout=5000)
                assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
                if page.locator("#server-account-name").text_content() != account:
                    raise AssertionError("Workspace switch signed the user out: " + label)
                if page.locator('#server-side-navigation a[aria-current="page"]').count() != 1:
                    raise AssertionError("Workspace " + label + " lost its single current location")
                assert_accessible(page, "Server " + role + " switch to " + label, review=[])
                capture(page, artifacts, "server-" + role + "-switch-" + label + "-" +
                        str(viewport["width"]))
            watch.assert_clean("Server " + role + " workspace switching")
            summary[role] = {"offered_workspaces": offered}
        finally:
            context.close()
    return summary


def server_publication_boundary(browser, base_url, creds, artifacts, viewport):
    """§13-07: a reader never receives an internal, unpublished Watch entry."""
    marker = "UX-R07 internal publication boundary " + secrets.token_hex(3)
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    page = context.new_page()
    page.set_default_timeout(30000)
    try:
        sign_in(page, base_url, creds, "workgroup")
        page.goto(base_url + "/?mode=server&workspace=workgroup&section=watch&view=editor",
                  wait_until="domcontentloaded")
        page.locator("#watch-add-entry").wait_for(state="visible", timeout=30000)
        page.locator("#watch-add-entry").click()
        form = page.locator("#watch-form")
        form.wait_for(state="visible")
        form.locator('input[name="name"]').fill(marker)
        form.locator('textarea[name="hypothesis"]').fill("Internal hypothesis, not published")
        form.locator('button[type="submit"]').click()
        page.locator('[data-business-domain="watch"] [data-business-record]').filter(
            has_text=marker).first.wait_for(state="visible", timeout=30000)
        contributor = page.request.get(base_url + "/api/v1/watch-entries").json()
        if marker not in json.dumps(contributor):
            raise AssertionError("Contributor cannot read the internal record it just created")
        capture(page, artifacts, "server-watch-internal-" + str(viewport["width"]))
    finally:
        context.close()
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    page = context.new_page()
    page.set_default_timeout(30000)
    try:
        sign_in(page, base_url, creds, "engineer")
        reader = page.request.get(base_url + "/api/v1/watch-entries").json()
        if marker in json.dumps(reader):
            raise AssertionError("Internal unpublished Watch entry leaked to a reader")
        for row in reader.get("results", []):
            properties = row.get("properties") or {}
            if properties.get("visibility") not in (None, "published"):
                raise AssertionError("Reader list contains an unpublished record: " +
                                     str(properties.get("visibility")))
        assert_no_privileged_view(page, "#server-watch", "Engineer publication boundary")
        return {"internal_records_visible_to_reader": 0,
                "published_records_visible_to_reader": len(reader.get("results", []))}
    finally:
        context.close()


def server_revision_conflict(browser, base_url, creds, artifacts, viewport):
    """§13-14: a stale save returns 409, keeps the draft and never overwrites."""
    # Unique names keep repeated local/CI runs independent of earlier fixtures.
    token = secrets.token_hex(3)
    original = "UX-R07 conflict guard " + token
    revised = original + " v2"
    context_a = browser.new_context(viewport=viewport, reduced_motion="reduce")
    context_b = browser.new_context(viewport=viewport, reduced_motion="reduce")
    page_a = context_a.new_page()
    page_b = context_b.new_page()
    page_a.set_default_timeout(30000)
    page_b.set_default_timeout(30000)
    watch_b = PageWatch(page_b, allowed_responses=[(409, "/api/v1/guides/")])
    try:
        sign_in(page_a, base_url, creds, "workgroup")
        page_a.goto(base_url + "/?mode=server&workspace=workgroup&section=guides&view=editor",
                    wait_until="domcontentloaded")
        page_a.locator("#guide-add").wait_for(state="visible")
        page_a.locator("#guide-add").click()
        form = page_a.locator("#guide-editor form.guide-form")
        form.wait_for(state="visible")
        fields = form.locator('[data-shared-guide-fields="server"]')
        fields.locator('input[name="name"]').fill(original)
        fields.locator('textarea[name="text"]').fill("First controlled revision")
        form.locator('button[type="submit"]').click()
        page_a.locator('[data-business-domain="guides"] [data-business-record]').filter(
            has_text=original).first.wait_for(state="visible", timeout=30000)

        # Second contributor loads the same revision and opens its editor.
        sign_in(page_b, base_url, creds, "multi_role")
        page_b.goto(base_url + "/?mode=server&workspace=workgroup&section=guides&view=editor",
                    wait_until="domcontentloaded")
        card_b = page_b.locator('[data-business-domain="guides"] [data-business-record]').filter(
            has_text=original).first
        card_b.wait_for(state="visible", timeout=30000)
        stale_snapshot = card_b.inner_text()
        card_b.locator('button[data-action="edit"]').click()
        form_b = page_b.locator("#guide-editor form.guide-form")
        form_b.wait_for(state="visible", timeout=15000)
        fields_b = form_b.locator('[data-shared-guide-fields="server"]')
        fields_b.locator('textarea[name="text"]').fill("Second contributor unsaved draft")
        fields_b.locator('textarea[name="text"]').dispatch_event("input")
        page_b.wait_for_timeout(300)

        # Writer A moves the authoritative revision forward.
        card_a = page_a.locator('[data-business-domain="guides"] [data-business-record]').filter(
            has_text=original).first
        card_a.locator('button[data-action="edit"]').click()
        form_a = page_a.locator("#guide-editor form.guide-form")
        form_a.wait_for(state="visible", timeout=15000)
        form_a.locator('[data-shared-guide-fields="server"] input[name="name"]').fill(revised)
        form_a.locator('button[type="submit"]').click()
        page_a.locator('[data-business-domain="guides"] [data-business-record]').filter(
            has_text=revised).first.wait_for(state="visible", timeout=30000)

        # The stale save must be refused, keep the draft and change nothing.
        form_b.locator('button[type="submit"]').click()
        page_b.wait_for_timeout(1500)
        if not watch_b.observed(409, "/api/v1/guides/"):
            raise AssertionError("Stale Guide save did not return HTTP 409")
        status_text = page_b.locator("#guide-status").first.inner_text()
        draft_text = page_b.locator("#guide-editor .shared-draft-status").first.inner_text()
        if not ("not saved" in status_text.lower() or "409" in status_text):
            raise AssertionError("409 was not surfaced to the user: " + status_text[:160])
        if "409" not in draft_text:
            raise AssertionError("Conflict banner did not report the 409: " + draft_text[:160])
        if fields_b.locator('textarea[name="text"]').input_value() != \
                "Second contributor unsaved draft":
            raise AssertionError("Stale save cleared the unsaved draft values")
        drafts = page_b.evaluate(
            "() => Object.keys(window.localStorage).filter(k => "
            "k.startsWith('ai-compass-working-draft:')).length")
        if not drafts:
            raise AssertionError("Local unsaved draft was discarded on conflict")
        capture(page_b, artifacts, "server-revision-conflict-" + str(viewport["width"]))
        authoritative = page_a.request.get(base_url + "/api/v1/guides").json()
        if revised not in json.dumps(authoritative):
            raise AssertionError("Authoritative record changed after a refused stale save")
        return {"stale_save_status": 409, "draft_preserved": True,
                "authoritative_revision_kept": revised,
                "stale_card_snapshot": stale_snapshot[:80]}
    finally:
        context_a.close()
        context_b.close()


def server_no_fallback(browser, base_url, creds, artifacts, viewport):
    """§13-19: an unavailable Server never renders Demo fixtures."""
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    page = context.new_page()
    page.set_default_timeout(20000)
    page.route("**/api/v1/**", lambda route: route.abort())
    try:
        page.goto(base_url + "/?mode=server&workspace=workgroup", wait_until="domcontentloaded")
        page.locator("#server-state").filter(has_text="unavailable").first.wait_for(
            state="visible", timeout=25000)
        text = page.locator("body").inner_text()
        if "NOT be loaded" not in text:
            raise AssertionError("Offline Server did not state that Demo data is not loaded")
        if page.locator("[data-business-record]").count():
            raise AssertionError("Offline Server rendered business records (possible Demo fallback)")
        content = page.locator("#ux-main-content").inner_text()
        for marker in ["AI Usage Charter", "UX-R04 complete Demo guide", "Prepare a reproducible"]:
            if marker in content:
                raise AssertionError("Offline Server displayed Demo fixture content: " + marker)
        # An unreachable backend must not present a sign-in that cannot succeed.
        if page.locator("#server-login-form").is_visible():
            raise AssertionError("Offline Server presented an interactive sign-in form")
        identity = page.evaluate("""async () => {
            try {
              const res = await fetch('/api/v1/auth/me', {credentials: 'same-origin'});
              return (await res.json()).authenticated;
            } catch (_) { return false; }
        }""")
        if identity:
            raise AssertionError("Offline Server reported an authenticated session")
        capture(page, artifacts, "server-offline-" + str(viewport["width"]))
        return {"demo_business_records_rendered": 0, "explicit_unavailable_state": True}
    finally:
        context.close()
