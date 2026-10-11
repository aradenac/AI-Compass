#!/usr/bin/env python3
"""AI Compass UI QA: disposable identities, real Chromium journeys and fail-closed probes.

Usage:
  python3 scripts/ux_qa.py provision --output /tmp/ux-qa-credentials.json
  python3 scripts/ux_qa.py test --base-url http://127.0.0.1:8080 \
    --demo-url http://127.0.0.1:8090/prototype.html \
    --credentials /tmp/ux-qa-credentials.json --artifacts /tmp/ux-qa

Only synthetic, isolated CI accounts are used. Never run provisioning on production.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from datetime import datetime, timezone

ROLES = {
    "workgroup": ["contributor"],
    "engineer": ["user"],
    "management": ["deployment-planner"],
    "maintenance": ["data-maintainer"],
    "multi_role": ["contributor", "user-admin", "deployment-planner"],
}


def provision(output):
    path = Path(output).resolve()
    if path.exists():
        raise RuntimeError("Refusing to overwrite an existing credential fixture")
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "manage.py",
                    "bootstrap_identity"], check=True)
    users = {}
    for label, roles in ROLES.items():
        name = "uxqa-" + label.replace("_", "-") + "-" + secrets.token_hex(3)
        password = secrets.token_urlsafe(30)
        command = ["docker", "compose", "exec", "-T", "api", "python", "manage.py",
                   "bootstrap_identity", "--username", name]
        for role in roles:
            command.extend(["--role", role])
        command.append("--password-stdin")
        subprocess.run(command, input=password + "\n", text=True, stdout=subprocess.DEVNULL,
                       check=True)
        users[label] = {"username": name, "password": password}
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(users, handle)
    print("Created five disposable, independent, randomized role fixtures (credentials not logged).")


def assert_exactly_one_view(page, selector):
    visible = page.locator(selector).filter(visible=True)
    count = visible.count()
    if count != 1:
        raise AssertionError(f"Expected exactly one active business view; found {count}: {selector}")


def assert_modal_form(page):
    dialog = page.get_by_role("dialog")
    if dialog.count() != 1 or not dialog.is_visible():
        raise AssertionError("A visible form dialog is required")
    if dialog.locator("form").count() == 0:
        raise AssertionError("The dialog must contain the editable form")
    closer = dialog.get_by_role("button", name="Close dialog")
    if closer.count() != 1:
        raise AssertionError("Missing explicit accessible modal close control")
    form_input = dialog.locator("input").first
    if form_input.count():
        form_input.fill("unsaved fixture text")
    page.locator(".modal-backdrop").click(position={"x": 3, "y": 3}, force=True)
    if not dialog.is_visible():
        raise AssertionError("Backdrop dismissed a form-containing dialog")
    page.keyboard.press("Escape")
    if not dialog.is_visible():
        raise AssertionError("Escape dismissed a form-containing dialog")
    if form_input.count() and form_input.input_value() != "unsaved fixture text":
        raise AssertionError("Form draft changed on backdrop/Escape")
    closer.click()
    if dialog.count() and dialog.is_visible():
        raise AssertionError("Explicit close button failed")


def assert_return_path(page):
    page.get_by_role("link", name="Open detail").click()
    if not page.get_by_role("heading", name="Object detail").is_visible():
        raise AssertionError("Detail navigation did not resolve")
    page.get_by_role("link", name="Back to list").click()
    if not page.get_by_role("heading", name="Objects list").is_visible():
        raise AssertionError("Contextual back navigation did not resolve")


def assert_no_horizontal_overflow(page):
    result = page.evaluate("""() => ({
      width: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body.scrollWidth
    })""")
    if result["scrollWidth"] > result["width"] + 2 or result["bodyWidth"] > result["width"] + 2:
        raise AssertionError("Viewport overflows horizontally: " + json.dumps(result))


def expect_failure(label, operation):
    try:
        operation()
    except (AssertionError, Exception) as error:
        # An injected break must be observed by the intended assertion, not by a
        # browser crash or other non-assertion error that can conceal a false pass.
        if not isinstance(error, AssertionError):
            raise AssertionError(f"{label}: unrelated exception instead of QA failure: {error}")
        return
    raise AssertionError(f"Mutation {label} was NOT detected by the acceptance assertion")


def mutation_probes(browser, artifacts):
    """Independent tests prove the gate rejects representative intentional regressions."""
    page = browser.new_page(viewport={"width": 1024, "height": 768})
    try:
        page.set_content('<main><section class="uxqa-domain">Catalog</section>'
                         '<section class="uxqa-domain">Unrelated Users</section></main>')
        expect_failure("stacked workspaces", lambda: assert_exactly_one_view(page, ".uxqa-domain"))
        page.set_content('<main><section class="uxqa-domain">Catalog</section></main>')
        assert_exactly_one_view(page, ".uxqa-domain")

        page.set_content('<form><input placeholder="Editor"></form>')
        expect_failure("missing modal", lambda: assert_modal_form(page))
        modal = """<style>.modal-backdrop{position:fixed;inset:0;background:#2229;
            display:grid;place-items:center}.modal{background:white;padding:30px}</style>
            <div class="modal-backdrop"><div role="dialog" aria-label="Editor" class="modal">
            <button aria-label="Close dialog" onclick="this.closest('.modal-backdrop').remove()">×</button>
            <form><input value="draft"></form></div></div>"""
        page.set_content(modal)
        assert_modal_form(page)
        page.set_content(modal.replace('onclick="this.closest(\'.modal-backdrop\').remove()"',
                                       'onclick="this.closest(\'.modal-backdrop\').remove()"') +
                         "<script>document.querySelector('.modal-backdrop').onclick=()=>"
                         "document.querySelector('.modal-backdrop').remove()</script>")
        expect_failure("backdrop discards draft", lambda: assert_modal_form(page))

        page.set_content("""<h1 id="list">Objects list</h1>
            <a href="#detail" onclick="document.getElementById('detail').hidden=false">Open detail</a>
            <section id="detail" hidden><h2>Object detail</h2>
            <a href="#list" onclick="document.getElementById('detail').hidden=true">Back to list</a></section>""")
        assert_return_path(page)
        page.set_content("""<h1 id="list">Objects list</h1>
            <a href="#detail" onclick="document.getElementById('detail').hidden=false">Open detail</a>
            <section id="detail" hidden><h2>Object detail</h2>
            <a href="#missing" onclick="document.getElementById('list').hidden=true">Back to list</a></section>""")
        expect_failure("broken breadcrumb/return", lambda: assert_return_path(page))

        page.set_content('<div style="width:2000px;height:20px">overflow</div>')
        expect_failure("overflow", lambda: assert_no_horizontal_overflow(page))
        page.set_content('<div style="max-width:100%;height:20px">inside</div>')
        assert_no_horizontal_overflow(page)

        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.evaluate("() => { setTimeout(() => { throw new Error('uxqa deliberate script error') }, 0) }")
        page.wait_for_timeout(100)
        if not any("uxqa deliberate script error" in error for error in errors):
            raise AssertionError("JavaScript runtime exception was not captured")
        page.screenshot(path=str(artifacts / "mutation-fixtures.png"))
    finally:
        page.close()


def capture(page, directory, name):
    # Never retain sensitive credentials or the contents of unfinished auth forms.
    page.evaluate("""() => document.querySelectorAll('input[type="password"]')
        .forEach(input => { input.value = ''; })""")
    page.screenshot(path=str(directory / (name + ".png")), full_page=True,
                    animations="disabled")


def demo_journey(browser, demo_url, artifacts, role, label, viewport):
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    page.set_default_timeout(12000)
    errors = []
    api_calls = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda request: api_calls.append(request.url)
            if "/api/v1/" in request.url else None)
    try:
        # Each browser context is clean; no server identity or database is available.
        page.goto(demo_url + "?mode=demo&workspace=" + label, wait_until="domcontentloaded")
        page.locator(f'[data-act="login"][data-id="{role}"]').click()
        page.locator(".app").wait_for(state="visible", timeout=20000)
        if not page.locator(".ux-shell .ux-content").is_visible() or not page.locator(".ux-shell .ux-sidebar").is_visible():
            raise AssertionError("Demo did not render the common shell")
        if page.locator(".ux-shell").count() != 1:
            raise AssertionError("Demo has competing application shells")
        assert_no_horizontal_overflow(page)
        if api_calls:
            raise AssertionError("Standalone Demo unexpectedly contacted API: " + str(api_calls))
        capture(page, artifacts, "demo-" + label + "-" + str(viewport["width"]))
        if role == "u1":
            # UX-R04: inspect actual shared business surfaces, not source text.
            for section, domain in [
                ("knowledge", "guides"), ("watch", "watch"),
                ("feedback", "feedback"), ("recommendations", "recommendations"),
                ("benchmark", "campaigns"), ("testdesign", "cases")
            ]:
                page.locator(f'[data-act="nav"][data-id="{section}"]').click()
                if domain == "cases":
                    surface = page.locator('.shared-case-tree[data-shared-cases="demo"]')
                else:
                    surface = page.locator(
                        f'.shared-business-list[data-business-domain="{domain}"]')
                surface.wait_for(state="visible", timeout=20000)
                if surface.locator('[data-business-record]').count() == 0 and domain != "cases":
                    raise AssertionError("Seeded Demo lacks real shared " + domain + " record cards")
                assert_no_horizontal_overflow(page)
                if domain in ("guides", "campaigns", "cases"):
                    capture(page, artifacts, "demo-shared-" + domain + "-" + str(viewport["width"]))
            page.locator(".shared-case-tree button[data-act=caseDetail]").first.click()
            detail = page.locator('.shared-case-detail[data-shared-case-detail="demo"]')
            detail.wait_for(state="visible")
            if detail.locator("h3").count() != 1:
                raise AssertionError("Shared Test Case detail lacks semantic heading")
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()

        if role == "u1":
            # Real Demo form -> local save -> same semantic Guide read view.
            page.locator('[data-act="nav"][data-id="knowledge"]').click()
            page.locator('[data-act="newGuide"]').first.click()
            dialog = page.get_by_role("dialog")
            dialog.wait_for(state="visible")
            form = dialog.locator('[data-shared-guide-fields="demo"]')
            form.locator('input[name="title"]').fill("UX-R04 complete Demo guide")
            form.locator('textarea[name="body"]').fill("Shared instructions survive")
            form.locator('textarea[name="description"]').fill("Keep immutable context")
            form.locator('input[name="url"]').fill("https://example.org/demo-guide")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-shared-guide-form-" + str(viewport["width"]))
            dialog.get_by_role("button", name="Create document").click()
            card = page.locator('[data-business-domain="guides"] [data-business-record]').filter(
                has_text="UX-R04 complete Demo guide").first
            card.wait_for(state="visible", timeout=20000)
            card.locator('button[data-act="guideDetail"]').click()
            detail = page.locator('[data-shared-guide-detail="demo"]')
            detail.wait_for(state="visible")
            for expected in ("Shared instructions survive", "Keep immutable context",
                             "https://example.org/demo-guide"):
                if expected not in detail.inner_text():
                    raise AssertionError("Demo Guide content missing: " + expected)
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
            capture(page, artifacts, "demo-shared-guide-detail-" + str(viewport["width"]))
        if role == "u1":
            # The actual Demo form must honor the same NFR modal contract.
            page.locator('[data-act="nav"][data-id="testdesign"]').click()
            page.locator('[data-act="newCase"]').first.click()
            demo_dialog = page.get_by_role("dialog")
            demo_dialog.wait_for(state="visible", timeout=12000)
            if demo_dialog.locator("form").count() != 1:
                raise AssertionError("Demo Test Case form missing from dialog")
            original = demo_dialog.locator("input:not([type=hidden])").first
            original.fill("Preserve this unfinished Demo draft")
            page.locator("#backdrop").click(position={"x":2,"y":2}, force=True)
            page.keyboard.press("Escape")
            if not demo_dialog.is_visible() or original.input_value() != "Preserve this unfinished Demo draft":
                raise AssertionError("Demo modal unexpectedly discarded unsaved form")
            demo_dialog.get_by_role("button", name="Close dialog").click()
            demo_dialog.wait_for(state="hidden")
            # Same form fields as Server: persist a fictional complete
            # challenge and inspect its semantic values after re-render.
            page.locator('[data-act="newCase"]').first.click()
            sample = page.get_by_role("dialog")
            sample.wait_for(state="visible")
            sample.locator('input[name="title"]').fill("UX-R04 Demo challenge completeness")
            sample.locator('textarea[name="objective"]').fill("Verify complete shared form")
            sample.locator('textarea[name="constraints"]').fill("Offline only")
            sample.locator('textarea[name="expected_outputs"]').fill("Six fields retained")
            sample.locator('textarea[name="environment"]').fill("Disposable Chromium")
            sample.locator('textarea[name="inputs"]').fill("Fictional fixture")
            sample.locator('textarea[name="dod"]').fill("All values remain visible")
            sample.get_by_role("button", name="Create Test Case").click()
            page.locator('[data-shared-case]').filter(
                has_text="UX-R04 Demo challenge completeness").first.wait_for(state="visible")
            page.locator('[data-shared-case]').filter(
                has_text="UX-R04 Demo challenge completeness").first.locator(
                    'button[data-act="caseDetail"]').click()
            details = page.locator('[data-shared-case-detail="demo"]')
            details.wait_for(state="visible")
            detail_text = details.inner_text()
            for expected in ("Offline only", "Six fields retained",
                             "Disposable Chromium", "All values remain visible"):
                if expected not in detail_text:
                    raise AssertionError("Demo did not preserve Test Case field: " + expected)
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()

        if role == "u1":
            # Real seeded Workgroup path: Studio → Watch → selected record → origin
            page.locator('[data-act="nav"][data-id="studio"]').click()
            page.locator('[data-studio-section="watch"]').click()
            filt = page.locator('[data-ux-list-filter]')
            filt.wait_for(state="visible", timeout=20000)
            filt.fill("agent")
            page.locator('.shared-list-row a').first.click()
            page.locator('.ux-context-detail').wait_for(state="visible", timeout=20000)
            if page.locator(".ux-advanced-source pre").is_visible():
                raise AssertionError("Raw JSON shown by default instead of domain detail")
            if "agent" not in page.locator(".ux-context-detail").inner_text().lower():
                raise AssertionError("Workgroup record context lost on navigation")
            page.locator("#ux-context-navigation .ux-return-link").click()
            page.locator('[data-ux-list-filter]').wait_for(state="visible", timeout=20000)
            if page.locator('[data-ux-list-filter]').input_value() != "agent":
                raise AssertionError("Return to origin lost Workgroup filter")
            if page.locator(".ux-context-detail").count():
                raise AssertionError("Back from detail still displays selected record")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-workgroup-return-" + str(viewport["width"]))
        if role == "u2":
            # Engineer Task/Tool → Solution detail → measured Run → contextual return.
            page.locator("[data-engineer-view=tool]").click()
            page.locator("[data-engineer-view=task]").click()
            page.locator("[data-engineer-detail]").first.click()
            page.locator("#ux-engineer-setup").wait_for(state="visible", timeout=20000)
            page.locator("#ux-engineer-feedback").wait_for(state="visible")
            if not page.locator("[data-engineer-home]").is_visible():
                raise AssertionError("Engineer detail has no discoverable origin")
            before = page.url
            page.get_by_role("link", name="Open measured Run and provenance").first.click()
            page.locator("#ux-demo-run-context").wait_for(state="visible", timeout=20000)
            if page.locator("#ux-demo-run-context .ux-advanced-source pre").is_visible():
                raise AssertionError("Default Demo Run detail is a raw JSON dump")
            page.go_back(wait_until="domcontentloaded")
            page.locator("#ux-engineer-setup").wait_for(state="visible", timeout=20000)
            if page.url != before:
                raise AssertionError("Browser back lost the exact Engineer Task/Solution URL")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-engineer-origin-" + str(viewport["width"]))
        if role == "u3":
            # Management: source-specific, as-of Inspector, not just a green API.
            scenario = page.locator("[data-heat-scenario]")
            scenario.wait_for(state="visible", timeout=20000)
            scenario.select_option("opp-demo-insights")
            candidate = page.locator("button[data-heat-cell]:has(.heat-selected)").first
            candidate.wait_for(state="visible", timeout=20000)
            candidate.click()
            page.locator(".heat-inspector").wait_for(state="visible", timeout=20000)
            page.locator("[data-heat-branch]").first.click()
            page.locator(".heat-inspector .ux-inspector-kv").wait_for(state="visible", timeout=20000)
            if page.locator(".heat-inspector > section pre").is_visible():
                raise AssertionError("Management default drilldown exposes raw JSON")
            if not page.locator("[data-heat-asof]").is_visible():
                raise AssertionError("Management original as-of state is missing")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-management-inspector-" + str(viewport["width"]))
        if errors:
            raise AssertionError("Demo JS runtime error(s): " + "; ".join(errors[:3]))
    finally:
        context.tracing.stop(path=str(artifacts / ("demo-" + label + "-" + str(viewport["width"]) + ".zip")))
        context.close()


def server_journey(browser, base_url, creds, artifacts, role, viewport):
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    traced = False  # Keep the password entry entirely outside the downloadable trace.
    page = context.new_page()
    page.set_default_timeout(15000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    path = "/maintenance?mode=server" if role == "maintenance" else (
        "/?mode=server&workspace=" + ("workgroup" if role == "multi_role" else role) +
        ("&section=studio" if role in ("workgroup", "multi_role") else ""))
    try:
        page.goto(base_url + path, wait_until="domcontentloaded")
        page.locator("#server-login-form").wait_for(state="visible", timeout=25000)
        page.locator("#server-username").fill(creds[role]["username"])
        page.locator("#server-password").fill(creds[role]["password"])
        page.get_by_role("button", name="Sign in to Server").click()
        page.locator('#ux-screen-host[data-ux-current]').wait_for(state="visible", timeout=25000)
        page.locator("#server-login-form").wait_for(state="hidden", timeout=25000)
        if page.locator("#server-account-name").text_content() != creds[role]["username"]:
            raise AssertionError("Authenticated user does not match the fixture")
        if role in ("workgroup", "multi_role"):
            page.locator("#server-workgroup-home").wait_for(state="visible", timeout=20000)
        elif role == "engineer":
            page.locator("#server-engineer").wait_for(state="visible", timeout=20000)
        elif role == "management":
            page.locator("#server-management-insights").wait_for(state="visible", timeout=20000)
        elif role == "maintenance":
            page.locator("#server-governance-audit").wait_for(state="visible", timeout=20000)
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        traced = True
        page.reload(wait_until="domcontentloaded")
        page.locator('#ux-screen-host[data-ux-current]').wait_for(state="visible", timeout=25000)
        page.locator("#server-login-form").wait_for(state="hidden", timeout=25000)
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
        capture(page, artifacts, "server-" + role + "-" + str(viewport["width"]))
        if errors:
            raise AssertionError("Server JS runtime error(s): " + "; ".join(errors[:3]))
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
            capture(page, artifacts, "server-shared-guide-detail-" + str(viewport["width"]))
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
                page.locator("#server-user-open-create").click()
                user_dialog = page.locator("#server-user-create-panel[role=dialog]")
                user_dialog.wait_for(state="visible")
                page.keyboard.press("Escape")
                if not user_dialog.is_visible():
                    raise AssertionError("Escape incorrectly dismissed account-creation form")
                user_dialog.get_by_role("button", name="Close dialog").click()
                user_dialog.wait_for(state="hidden")
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
        return {"visible_active_screens": 1, "shared_shell": True}
    finally:
        if traced:
            context.tracing.stop(path=str(artifacts / ("server-" + role + "-" + str(viewport["width"]) + ".zip")))
        context.close()


def run_tests(base_url, demo_url, credentials, artifacts):
    from playwright.sync_api import sync_playwright
    directory = Path(artifacts)
    directory.mkdir(parents=True, exist_ok=True)
    directory = directory.resolve()
    creds = json.loads(Path(credentials).read_text(encoding="utf-8"))
    records = []
    debts = []
    start = time.monotonic()

    def run(label, fn):
        try:
            details = fn() or {}
            records.append({"name": label, "result": "PASS", "details": details})
            if details.get("legacy_stack_observed"):
                debts.append({"test": label, "issue": 115,
                              "finding": "Multiple legacy domain containers simultaneously visible",
                              "count": details.get("visible_legacy_domains")})
            print("PASS", label, flush=True)
        except Exception as error:
            records.append({"name": label, "result": "FAIL",
                            "message": str(error)[:800]})
            print("FAIL", label, str(error)[:300], flush=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            run("Mutation probes (deliberate UI defects rejected)",
                lambda: mutation_probes(browser, directory))
            # Product support scope: desktop browsers only (2026-10-11).
            # Mobile/tablet adaptation is not part of acceptance or CI.
            viewports = [{"width": 1366, "height": 900}]
            for viewport in viewports:
                width = viewport["width"]
                run(f"Standalone Demo workgroup {width}",
                    lambda v=viewport: demo_journey(browser, demo_url, directory, "u1", "workgroup", v))
                run(f"Standalone Demo engineer {width}",
                    lambda v=viewport: demo_journey(browser, demo_url, directory, "u2", "engineer", v))
                run(f"Standalone Demo management {width}",
                    lambda v=viewport: demo_journey(browser, demo_url, directory, "u3", "management", v))
                for role in ROLES:
                    run(f"Authenticated Server {role} {width}",
                        lambda k=role, v=viewport: server_journey(
                            browser, base_url, creds, directory, k, v))
        finally:
            browser.close()
    failed = [record for record in records if record["result"] == "FAIL"]
    report = {
        "version": 1,
        "suite": "UX-R03 Chromium role-journey and contextual-origin acceptance",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if failed else "PASS",
        "ui_conformance": "CONTEXTUAL_JOURNEYS_CHECKED; MANUAL_STAGING_AND_FULL_PERSONA_DATA_REQUIRE_SEPARATE_REVIEW",
        "production_approval": "NO-GO: separate operational gates",
        "checks": records,
        "known_ux_findings": debts,
        "duration_seconds": round(time.monotonic() - start, 2),
    }
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# UI QA — " + report["status"], "",
             f"Chromium journeys: **{len(records) - len(failed)}/{len(records)} passed**.",
             "**Common shell, modal and seeded contextual navigation journeys exercised in Chromium.** Manual staging, full production evidence and deployment remain NO-GO.",
             "", "| Check | Result | Detail |", "| --- | --- | --- |"]
    for rec in records:
        lines.append(f"| {rec['name']} | {rec['result']} | " +
                     str(rec.get("message", rec.get("details", {}))).replace("|", "/")[:230] + " |")
    if debts:
        lines.extend(["", "## Legacy visual defects (not approved baselines)"])
        for item in debts:
            lines.append(f"- {item['test']}: {item['finding']} ({item['count']}). Track in #{item['issue']}.")
    lines.extend(["", "Screenshots/traces/JSON are retained as CI artifacts. "
                  "They are inspection evidence, NOT approved golden snapshots."])
    (directory / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    provision_parser = sub.add_parser("provision")
    provision_parser.add_argument("--output", required=True)
    test_parser = sub.add_parser("test")
    test_parser.add_argument("--base-url", required=True)
    test_parser.add_argument("--demo-url", required=True)
    test_parser.add_argument("--credentials", required=True)
    test_parser.add_argument("--artifacts", required=True)
    args = parser.parse_args()
    if args.command == "provision":
        provision(args.output)
        return 0
    return run_tests(args.base_url.rstrip("/"), args.demo_url, args.credentials, args.artifacts)


if __name__ == "__main__":
    sys.exit(main())
