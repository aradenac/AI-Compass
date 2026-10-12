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
import re
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
            # Both knowledge-domain records use the shared semantic detail.
            page.locator('[data-act="nav"][data-id="watch"]').click()
            watch_button = page.locator(
                '[data-business-domain="watch"] button[data-act="watchDetail"]').first
            watch_button.wait_for(state="visible", timeout=20000)
            watch_button.click()
            watch_detail = page.locator(
                '[data-knowledge-domain="watch"][data-knowledge-mode="demo"]')
            watch_detail.wait_for(state="visible")
            if not watch_detail.locator("h3").count():
                raise AssertionError("No shared Watch detail")
            capture(page, artifacts, "demo-shared-watch-detail-" + str(viewport["width"]))
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
            forecast_button = page.locator(
                '[data-business-domain="forecasts"] button[data-act="forecastDetail"]').first
            forecast_button.wait_for(state="visible", timeout=20000)
            forecast_button.click()
            forecast_detail = page.locator(
                '[data-knowledge-domain="forecasts"][data-knowledge-mode="demo"]')
            forecast_detail.wait_for(state="visible")
            if "never measured" not in forecast_detail.inner_text().lower():
                raise AssertionError("Forecast missing explicit theoretical provenance")
            # The same shared review/publication bar, with the canonical labels
            # used by the authenticated Server, inside the Forecast detail.
            lifecycle = page.locator(
                '[data-shared-lifecycle="forecasts"][data-lifecycle-mode="demo"]')
            lifecycle.wait_for(state="visible", timeout=20000)
            if lifecycle.locator("button").count() == 0:
                raise AssertionError("Demo forecast detail exposes no permitted transition")
            if "never turns its estimates into measured results" not in lifecycle.inner_text():
                raise AssertionError("Forecast review bar lost its theoretical provenance notice")
            capture(page, artifacts, "demo-shared-forecast-lifecycle-" + str(viewport["width"]))
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
            # The measured-Run detail is the shared presentation in both modes.
            page.locator('[data-act="nav"][data-id="results"]').click()
            runs_tab = page.locator('[data-act="resultsTab"][data-id="runs"]')
            if runs_tab.count():
                runs_tab.first.click()
            # The comparison matrix is the same shared component as Server's.
            matrix_tab = page.locator('[data-act="resultsTab"][data-id="matrix"]')
            if matrix_tab.count():
                matrix_tab.first.click()
                demo_matrix = page.locator(
                    '[data-shared-observation-matrix][data-observation-mode="demo"]')
                demo_matrix.wait_for(state="visible", timeout=20000)
                if demo_matrix.locator('[data-observation-row]').count() == 0:
                    raise AssertionError("Demo comparison matrix rendered no row")
                if demo_matrix.locator('[data-observation-label]').count() == 0:
                    raise AssertionError("Demo comparison matrix rendered no column")
                if not demo_matrix.locator('[data-observation-empty]').count():
                    raise AssertionError(
                        "Demo comparison matrix no longer marks unobserved cells explicitly")
                capture(page, artifacts,
                        "demo-shared-observation-matrix-" + str(viewport["width"]))
            runs_tab = page.locator('[data-act="resultsTab"][data-id="runs"]')
            if runs_tab.count():
                runs_tab.first.click()
            run_button = page.locator('button[data-act="runDetail"]').first
            run_button.wait_for(state="visible", timeout=20000)
            run_button.click()
            run_detail = page.locator('[data-shared-run-detail][data-run-mode="demo"]')
            run_detail.wait_for(state="visible", timeout=20000)
            if run_detail.get_attribute("data-run-provenance") != "measured":
                raise AssertionError("A measured Demo Run is not presented as measured evidence")
            if "MEASURED RUN" not in run_detail.inner_text():
                raise AssertionError("Shared measured-Run detail lost its provenance marker")
            if run_detail.locator(".shared-run-metrics > div").count() == 0:
                raise AssertionError("Shared measured-Run detail shows no recorded metric")
            if run_detail.locator("[data-run-pin-mismatch]").count():
                raise AssertionError("A verifiable Demo Run was reported as a revision mismatch")
            capture(page, artifacts, "demo-shared-run-detail-" + str(viewport["width"]))
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
            # Decimal metrics remain valid while negative measurements are
            # refused: the historical Demo number contract, shared with Server.
            page.locator('[data-act="nav"][data-id="watch"]').click()
            page.locator('[data-act="newForecast"]').first.wait_for(state="visible", timeout=20000)
            page.locator('[data-act="newForecast"]').first.click()
            forecast_dialog = page.get_by_role("dialog")
            forecast_dialog.wait_for(state="visible")
            cost = forecast_dialog.locator('input[name="aiCost"]')
            cost.fill("0.5")
            if not cost.evaluate("el => el.validity.valid && !el.validity.stepMismatch"):
                raise AssertionError("Fractional Demo metric was rejected by native validation")
            cost.fill("-1")
            if cost.evaluate("el => el.validity.valid"):
                raise AssertionError("Negative Demo metric passed native validation")
            cost.fill("0.5")
            if forecast_dialog.locator('input[name="hourlyRate"]').evaluate(
                    "el => el.getAttribute('step')") != "any":
                raise AssertionError("Demo numeric fields lost their fractional step")
            capture(page, artifacts, "demo-shared-fractional-metric-" + str(viewport["width"]))
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
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
        if role == "u1":
            # UX-R04: the Demo Campaign matrix is the shared component, and one
            # real fictional decision is recorded through the shared form.
            page.locator('[data-act="nav"][data-id="benchmark"]').click()
            card = page.locator(
                '[data-business-domain="campaigns"] [data-business-record]'
            ).filter(has_text="planned").first
            card.wait_for(state="visible", timeout=20000)
            card.locator('button[data-act="campaignDetail"]').click()
            dialog = page.get_by_role("dialog")
            dialog.wait_for(state="visible", timeout=20000)
            add = dialog.locator('button[data-act="campaignMatrixAdd"]')
            if add.count():
                add.first.click()
                form = page.locator("#modalForm")
                form.wait_for(state="visible", timeout=20000)
                form.locator('input[name="label"]').fill("UX-R04 shared Demo configuration")
                for name in ("model", "provider", "harness"):
                    select = form.locator(f'select[name="{name}"]')
                    values = [value for value in select.locator("option").evaluate_all(
                        "options => options.map(option => option.value)") if value]
                    if not values:
                        raise AssertionError(
                            "Demo lacks fictional catalog components for " + name)
                    select.select_option(values[0])
                page.get_by_role("button", name="Add evaluation column").click()
            matrix = page.locator('[data-shared-matrix][data-matrix-mode="demo"]')
            matrix.wait_for(state="visible", timeout=20000)
            if matrix.locator("[data-shared-matrix-cell]").count() == 0:
                raise AssertionError("Shared Demo matrix rendered no evaluation cell")
            if not page.locator('[data-shared-stepper][data-stepper-mode="demo"]').count():
                raise AssertionError("Demo campaign lifecycle does not use the shared stepper")
            # Dialog contract: closing returns focus to the control that opened
            # the dialog, in Demo and Server alike.
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
            opened_by = page.evaluate(
                "() => document.activeElement && document.activeElement.dataset "
                "? (document.activeElement.dataset.act || '') : ''")
            if opened_by != "campaignDetail":
                raise AssertionError(
                    "Focus did not return to the dialog trigger: " + str(opened_by))
            page.locator(
                '[data-business-domain="campaigns"] [data-business-record]'
            ).filter(has_text="planned").first.locator(
                'button[data-act="campaignDetail"]').click()
            page.get_by_role("dialog").wait_for(state="visible", timeout=20000)
            matrix = page.locator('[data-shared-matrix][data-matrix-mode="demo"]')
            matrix.wait_for(state="visible", timeout=20000)
            demo_lifecycle = page.locator(
                '[data-shared-lifecycle="campaigns"][data-lifecycle-mode="demo"]')
            demo_lifecycle.wait_for(state="visible", timeout=20000)
            demo_labels = sorted(demo_lifecycle.locator("button").all_inner_texts())
            # Canonical labels shared with the authenticated Server for a
            # planned campaign: start and archive, in the same wording.
            expected_labels = sorted(["Start / open campaign", "Archive campaign"])
            if demo_labels != expected_labels:
                raise AssertionError(
                    "Demo planned campaign transitions are not canonical: " + str(demo_labels))
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-shared-campaign-matrix-" + str(viewport["width"]))
            matrix.locator("[data-shared-matrix-cell] button").first.click()
            cell = page.locator('[data-matrix-cell-detail][data-matrix-mode="demo"]')
            cell.wait_for(state="visible", timeout=20000)
            if "never measured evidence" not in cell.inner_text().lower():
                raise AssertionError("Shared Demo matrix cell lost its evidence provenance notice")
            decision_form = page.locator("#modalForm")
            decision_form.locator('select[name="decision"]').select_option("waived")
            decision_form.locator('textarea[name="reason"]').fill(
                "UX-R04 Demo waiver recorded through the shared decision form")
            page.get_by_role("button", name="Save decision").click()
            matrix = page.locator('[data-shared-matrix][data-matrix-mode="demo"]')
            matrix.wait_for(state="visible", timeout=20000)
            matrix_text = matrix.inner_text()
            if "Waived: 1" not in matrix_text:
                raise AssertionError("Shared Demo matrix did not apply the waiver")
            if "UX-R04 Demo waiver recorded" not in matrix_text:
                raise AssertionError("Shared Demo matrix lost the recorded waiver reason")
            capture(page, artifacts,
                    "demo-shared-campaign-matrix-decided-" + str(viewport["width"]))
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
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
            # Fail closed: a workgroup-only write surface must never render for
            # the Engineer persona, and no other mode may be substituted.
            page.goto(base_url + "/?mode=server&workspace=workgroup&section=testdesign",
                      wait_until="domcontentloaded")
            page.locator('#ux-screen-host[data-ux-current]').wait_for(state="visible", timeout=25000)
            page.wait_for_timeout(1500)
            if page.locator("#case-new").count() or page.locator("#server-test-cases").is_visible():
                raise AssertionError("Engineer persona reached the Workgroup Test Case editor")
            assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")
            if not page.locator("#server-engineer").is_visible():
                raise AssertionError("Unauthorized Workgroup section did not fall back closed")
            capture(page, artifacts, "server-engineer-denied-" + str(viewport["width"]))
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
            # The shared shell returns focus to the editor trigger on close.
            if page.evaluate("() => document.activeElement ? document.activeElement.id : ''") != "case-new":
                raise AssertionError(
                    "Server editor did not restore focus to its trigger: " +
                    str(page.evaluate(
                        "() => document.activeElement ? document.activeElement.id : ''")))
            if role == "workgroup":
                # Real persisted Test Design round-trip: UI Task creation -> TC
                # save -> same shared presenter after a full browser reload.
                page.goto(base_url + "/?mode=server&workspace=workgroup&section=tasks&view=editor",
                          wait_until="domcontentloaded")
                page.locator("#server-task-add-root").wait_for(state="visible", timeout=30000)
                page.locator("#server-task-add-root").click()
                task_dialog = page.locator("#server-task-editor[role=dialog]")
                task_dialog.wait_for(state="visible", timeout=15000)
                fixture_suffix = secrets.token_hex(3)
                task_name = "UX-R04 reusable browser Task " + fixture_suffix
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
                case_title = "UX-R04 preserved browser challenge " + fixture_suffix
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
                # Unavailable domain API: the screen must fail closed with the
                # shared error presentation and never substitute Demo fixtures.
                unavailable = context.new_page()
                unavailable.set_default_timeout(20000)
                try:
                    unavailable.route(
                        "**/api/v1/campaigns**",
                        lambda route: route.fulfill(
                            status=503, content_type="application/json",
                            body=json.dumps({"detail": "Service unavailable (injected probe)"})))
                    unavailable.goto(
                        base_url + "/?mode=server&workspace=workgroup&section=benchmark&view=editor",
                        wait_until="domcontentloaded")
                    unavailable.locator(
                        '#campaign-status [data-shared-status="error"]').first.wait_for(
                            state="visible", timeout=30000)
                    unavailable_text = unavailable.locator("#campaign-status").inner_text().lower()
                    if "unavailable" not in unavailable_text and "failed" not in unavailable_text:
                        raise AssertionError(
                            "Unavailable API did not report a domain error: " + unavailable_text[:120])
                    if unavailable.locator('[data-business-domain="campaigns"]').count():
                        raise AssertionError("Unavailable API still rendered Server campaign cards")
                    if unavailable.locator('[data-shared-matrix][data-matrix-mode="demo"]').count():
                        raise AssertionError("Unavailable Server screen fell back to Demo content")
                    demo_titles = unavailable.locator(
                        'text=Plan: agent autonomy for intermittent driver bugs').count()
                    if demo_titles:
                        raise AssertionError("Demo fixtures leaked into a failed Server request")
                    assert_exactly_one_view(unavailable, "#ux-screen-host > [data-ux-screen]")
                    capture(unavailable, artifacts,
                            "server-unavailable-api-" + str(viewport["width"]))
                finally:
                    unavailable.close()

                # Results explorer: same observation matrix component, with an
                # explicit empty state on a database without measured Runs.
                page.goto(base_url + "/?mode=server&workspace=workgroup&section=results&view=editor",
                          wait_until="domcontentloaded")
                server_matrix = page.locator(
                    '[data-shared-observation-matrix][data-observation-mode="server"]')
                server_matrix.wait_for(state="visible", timeout=30000)
                if not server_matrix.locator("[data-observation-empty-matrix]").count():
                    raise AssertionError(
                        "Empty Server results did not state that nothing is recorded")
                if server_matrix.locator('[data-shared-observation-matrix="demo"]').count():
                    raise AssertionError("Server results leaked the Demo matrix")
                assert_no_horizontal_overflow(page)
                capture(page, artifacts,
                        "server-shared-observation-matrix-" + str(viewport["width"]))

                # Tasks: one shared tree in both modes; a stale move revision
                # must be refused explicitly, never applied.
                page.goto(base_url + "/?mode=server&workspace=workgroup&section=tasks&view=editor",
                          wait_until="domcontentloaded")
                page.locator("#server-task-add-root").wait_for(state="visible", timeout=30000)
                page.locator("#server-task-add-root").click()
                sibling = page.locator("#server-task-editor[role=dialog]")
                sibling.wait_for(state="visible", timeout=15000)
                sibling.locator('input[name="name"]').fill("UX-R04 sibling section")
                sibling.get_by_role("button", name="Save task revision").click()
                sibling.wait_for(state="hidden", timeout=25000)
                page.locator("#server-task-list").wait_for(state="visible", timeout=25000)
                stale_tasks = context.new_page()
                stale_tasks.set_default_timeout(20000)
                try:
                    stale_tasks.goto(page.url, wait_until="domcontentloaded")
                    stale_tasks.locator("#server-task-list").wait_for(state="visible", timeout=30000)
                    move = page.locator(
                        '#server-task-list button[data-task-action="down"]').first
                    move.wait_for(state="visible", timeout=25000)
                    move.click()
                    page.locator("#server-task-state", has_text="task node(s)").first.wait_for(
                        state="visible", timeout=25000)
                    stale_move = stale_tasks.locator(
                        '#server-task-list button[data-task-action="down"]').first
                    stale_move.click()
                    refusal = stale_tasks.locator(
                        '#server-task-state [data-shared-status="error"]').first
                    refusal.wait_for(state="visible", timeout=25000)
                    if "refused" not in refusal.inner_text().lower():
                        raise AssertionError(
                            "Stale task move was not refused explicitly: " +
                            refusal.inner_text()[:120])
                    if "revision" not in refusal.inner_text().lower() and \
                            "changed" not in refusal.inner_text().lower():
                        raise AssertionError(
                            "Stale task move refusal lacks the revision reason")
                    capture(stale_tasks, artifacts,
                            "server-task-stale-refusal-" + str(viewport["width"]))
                finally:
                    stale_tasks.close()

                # UX-R04: real Server campaign matrix through the shared component.
                page.goto(base_url + "/?mode=server&workspace=workgroup&section=catalog&view=editor",
                          wait_until="domcontentloaded")
                page.locator(".shared-catalog-workspace").wait_for(state="visible", timeout=30000)
                for component_type in ("model", "provider", "harness"):
                    page.locator(
                        f'button[data-act="newComponentType"][data-id="{component_type}"]'
                    ).first.click()
                    editor = page.locator("[data-common-form]")
                    editor.wait_for(state="visible", timeout=20000)
                    editor.locator('input[name="name"]').fill("UX-R04 " + component_type)
                    if component_type == "harness":
                        editor.locator('input[name="osWindows"]').check()
                    editor.locator('button[type="submit"]').click()
                    editor.wait_for(state="hidden", timeout=30000)
                page.goto(base_url + "/?mode=server&workspace=workgroup&section=benchmark&view=editor",
                          wait_until="domcontentloaded")
                page.locator("#campaign-add").wait_for(state="visible", timeout=30000)
                page.locator(
                    '[data-business-domain="campaigns"], [data-business-empty="campaigns"]'
                ).first.wait_for(state="visible", timeout=30000)
                page.locator("#campaign-add").click()
                campaign_form = page.locator("#campaign-form")
                campaign_form.wait_for(state="visible", timeout=20000)
                campaign_title = "UX-R04 shared matrix campaign " + secrets.token_hex(3)
                campaign_form.locator('input[name="name"]').fill(campaign_title)
                campaign_form.locator('textarea[name="objective"]').fill(
                    "Verify the shared campaign evaluation matrix in an authenticated Server")
                task_choice = campaign_form.locator('select[name="task_id"] option').filter(
                    has_text=task_name).first
                task_value = task_choice.get_attribute("value")
                if not task_value:
                    raise AssertionError("Created real Task was not selectable for a campaign")
                campaign_form.locator('select[name="task_id"]').select_option(task_value)
                case_choice = campaign_form.locator('select[name="test_case_ids"] option').filter(
                    has_text=case_title).first
                case_value = case_choice.get_attribute("value")
                if not case_value:
                    raise AssertionError("Created real Test Case was not offered to the campaign")
                campaign_form.locator('select[name="test_case_ids"]').select_option(case_value)
                campaign_form.locator('button[type="submit"]').click()
                campaign_card = page.locator(
                    '[data-business-domain="campaigns"] [data-business-record]').filter(
                        has_text=campaign_title).first
                campaign_card.wait_for(state="visible", timeout=30000)
                campaign_card.locator('button[data-action="matrix"]').click()
                matrix = page.locator('[data-shared-matrix][data-matrix-mode="server"]')
                matrix.wait_for(state="visible", timeout=30000)
                if not page.locator('[data-shared-stepper][data-stepper-mode="server"]').count():
                    raise AssertionError("Server campaign lifecycle does not use the shared stepper")
                server_lifecycle = page.locator(
                    '[data-shared-lifecycle="campaigns"][data-lifecycle-mode="server"]')
                server_lifecycle.wait_for(state="visible", timeout=20000)
                # Same canonical wording as the offline Demo for a planned campaign.
                expected_labels = sorted(["Start / open campaign", "Archive campaign"])
                server_labels = sorted(server_lifecycle.locator("button").all_inner_texts())
                if server_labels != expected_labels:
                    raise AssertionError(
                        "Server planned campaign transitions differ from the shared Demo "
                        "presentation: " + str(server_labels))
                # The add-configuration form is disclosed, not always open.
                page.locator("details:has(#matrix-add-form)").locator("summary").first.click()
                add_form = page.locator("#matrix-add-form")
                add_form.wait_for(state="visible", timeout=20000)
                add_form.locator('input[name="label"]').fill("UX-R04 shared Server configuration")
                # Bind the configuration to the campaign's own Task: the default
                # option may be another Task with no eligible Test Case.
                add_form.locator('select[name="task_id"]').select_option(task_value)
                add_form.locator('select[name="test_case_ids"] option').first.wait_for(
                    state="attached", timeout=20000)
                if add_form.locator('select[name="test_case_ids"] option[selected]').count() == 0:
                    raise AssertionError(
                        "The campaign Task offered no eligible Test Case to the matrix")
                for component in ("model", "provider", "harness"):
                    add_form.locator(f'select[name="{component}"]').select_option(index=0)
                add_form.locator('button[type="submit"]').click()
                cell_button = page.locator(
                    '[data-shared-matrix][data-matrix-mode="server"] [data-shared-matrix-cell] button'
                ).first
                try:
                    cell_button.wait_for(state="visible", timeout=30000)
                except Exception:
                    raise AssertionError(
                        "Matrix configuration was rejected: " +
                        page.locator("#campaign-status").inner_text()[:200])
                assert_no_horizontal_overflow(page)
                capture(page, artifacts, "server-shared-campaign-matrix-" +
                        str(viewport["width"]))
                cell_button.click()
                cell = page.locator('[data-matrix-cell-detail][data-matrix-mode="server"]')
                cell.wait_for(state="visible", timeout=30000)
                if "never measured evidence" not in cell.inner_text().lower():
                    raise AssertionError("Shared Server matrix cell lost its provenance notice")
                # The rendered link must open the exact evaluated Test Case
                # revision, not the current version.
                cell_text = cell.inner_text()
                pinned = re.search(r"pinned revision (r\d{3})", cell_text)
                if not pinned:
                    raise AssertionError(
                        "Cell detail does not state the pinned Test Case revision: " +
                        cell_text[:160])
                context_link = cell.locator('a', has_text="Open Test Case context").first
                if context_link.count() == 0:
                    raise AssertionError("Cell detail lost the Test Case context link")
                href = context_link.get_attribute("href") or ""
                if f"revision={pinned.group(1)}" not in href:
                    raise AssertionError(
                        "Test Case context link does not open the pinned revision: " + href)
                decision = page.locator("#matrix-decision-form")
                decision.wait_for(state="visible", timeout=20000)
                decision.locator('select[name="decision"]').select_option("waived")
                decision.locator('textarea[name="reason"]').fill(
                    "UX-R04 Server waiver recorded through the shared decision form")
                decision.locator('button[type="submit"]').click()
                matrix = page.locator('[data-shared-matrix][data-matrix-mode="server"]')
                matrix.locator('[data-matrix-state="waived"]').first.wait_for(
                    state="visible", timeout=30000)
                matrix_text = matrix.inner_text()
                if "UX-R04 Server waiver recorded" not in matrix_text:
                    raise AssertionError("Shared Server matrix lost the recorded waiver reason")
                if "Waived: 1" not in matrix_text:
                    raise AssertionError("Shared Server matrix did not apply the waiver")
                capture(page, artifacts, "server-shared-campaign-matrix-decided-" +
                        str(viewport["width"]))
                page.reload(wait_until="domcontentloaded")
                persisted = page.locator(
                    '[data-shared-matrix][data-matrix-mode="server"] [data-matrix-state="waived"]')
                persisted.first.wait_for(state="visible", timeout=30000)
                if "UX-R04 Server waiver recorded" not in page.locator(
                        '[data-shared-matrix][data-matrix-mode="server"]').inner_text():
                    raise AssertionError("Persisted Server matrix waiver was lost after reload")
                # Negative: a stale plan revision must be refused explicitly,
                # through the shared status presentation, with no silent
                # overwrite and no cross-mode fallback.
                stale = context.new_page()
                stale.set_default_timeout(20000)
                try:
                    stale.goto(page.url, wait_until="domcontentloaded")
                    stale_matrix = stale.locator(
                        '[data-shared-matrix][data-matrix-mode="server"]')
                    stale_matrix.wait_for(state="visible", timeout=30000)
                    # Advance the plan revision by reinstating the evaluation.
                    page.locator(
                        '[data-shared-matrix][data-matrix-mode="server"] '
                        '[data-shared-matrix-cell] button').first.click()
                    page.locator("#matrix-decision-form").wait_for(state="visible")
                    page.locator('#matrix-decision-form select[name="decision"]'
                                 ).select_option("selected")
                    page.locator('#matrix-decision-form button[type="submit"]').click()
                    page.locator(
                        '[data-shared-matrix][data-matrix-mode="server"] '
                        '[data-shared-matrix-cell][data-matrix-state="pending"]').first.wait_for(
                            state="visible", timeout=30000)
                    # The other browser still holds the previous revision.
                    stale.locator(
                        '[data-shared-matrix][data-matrix-mode="server"] '
                        '[data-shared-matrix-cell] button').first.click()
                    stale.locator("#matrix-decision-form").wait_for(state="visible")
                    stale.locator('#matrix-decision-form select[name="decision"]'
                                  ).select_option("waived")
                    stale.locator('#matrix-decision-form textarea[name="reason"]').fill(
                        "Stale browser revision must be refused")
                    stale.locator('#matrix-decision-form button[type="submit"]').click()
                    refusal = stale.locator(
                        '#campaign-status [data-shared-status="error"], '
                        '[data-shared-status="error"]')
                    refusal.first.wait_for(state="visible", timeout=30000)
                    refusal_text = refusal.first.inner_text().lower()
                    if "revision" not in refusal_text:
                        raise AssertionError(
                            "Stale matrix revision refusal lacks an explicit reason: " +
                            refusal_text[:120])
                    stale_text = stale.locator(
                        '[data-shared-matrix][data-matrix-mode="server"]').inner_text()
                    if "Stale browser revision must be refused" in stale_text:
                        raise AssertionError("A stale revision was silently applied")
                    if stale.locator(
                            '[data-shared-matrix-cell][data-matrix-state="waived"]').count() == 0:
                        raise AssertionError(
                            "The refused stale write altered the stale page state")
                    if stale.locator('[data-browser-domain="demo"]').count():
                        raise AssertionError("Refused Server write fell back to Demo")
                    capture(stale, artifacts, "server-shared-campaign-matrix-stale-" +
                            str(viewport["width"]))
                finally:
                    stale.close()
                if "Stale browser revision must be refused" in page.locator(
                        '[data-shared-matrix][data-matrix-mode="server"]').inner_text():
                    raise AssertionError("Refused stale write altered the committed plan")
                # Read-only historical plan: no lifecycle transition may be
                # offered from a revision that is not the current campaign one.
                # Pick the revision immediately before the displayed one: an
                # older plan that definitely carries a matrix plan.
                option_info = page.evaluate("""() => {
                  const select = document.getElementById('matrix-revision');
                  if (!select) return null;
                  const options = Array.from(select.options).map(
                    option => ({value: option.value, selected: option.selected}));
                  return options.length > 1 ? options : null;
                }""")
                if not option_info:
                    raise AssertionError("No historical plan revision was available to inspect")
                current_index = next(
                    (index for index, option in enumerate(option_info) if option["selected"]), 0)
                pick = current_index + 1 if current_index + 1 < len(option_info) else current_index - 1
                older = option_info[pick]["value"]
                page.locator("#matrix-revision").select_option(older)
                try:
                    page.locator('[data-shared-matrix][data-matrix-mode="server"]').wait_for(
                        state="visible", timeout=25000)
                except Exception:
                    raise AssertionError(
                        "Historical plan revision did not render: " +
                        page.locator("#campaign-detail").inner_text()[:200])
                if page.locator('[data-shared-lifecycle="campaigns"] button').count():
                    raise AssertionError(
                        "Historical plan revision still offers lifecycle transitions")
                if not page.locator('[data-shared-lifecycle-empty]').count():
                    raise AssertionError(
                        "Historical plan revision lacks an explicit read-only notice")
                if "revision=r007" in page.locator(
                        '[data-shared-matrix][data-matrix-mode="server"]').inner_text():
                    raise AssertionError("Historical revision mismatch")
                capture(page, artifacts,
                        "server-shared-campaign-matrix-historical-" + str(viewport["width"]))
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
