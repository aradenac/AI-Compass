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
    # The combined UX-R06 fixture also carries `reviewer` (publication_review).
    "multi_role": ["business_read", "business_write", "planning_manage",
                   "planning_view", "publication_review", "users_manage", "users_view"],
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
        if ("conflict" not in draft_text.lower()
                or "revision" not in draft_text.lower()):
            raise AssertionError(
                "Conflict banner did not explain the refused revision: " + draft_text[:160])
        if "not overwritten" not in draft_text.lower() and "overwritten" not in draft_text.lower():
            raise AssertionError(
                "Conflict banner did not state the draft/record was preserved: " + draft_text[:160])
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
