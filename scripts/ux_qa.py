#!/usr/bin/env python3
"""AI Compass UI QA: disposable identities, real Chromium journeys and fail-closed probes.

UX-R07 (#126) keeps this the single CLI entry point and the stable CI check name
`ui-qa`, while the newer §13-scenario gate lives in the `uxqa` package next to it:

  support        shared low-level assertions and desktop screenshot capture
  accessibility  deterministic a11y/focus/console/network gates and audits
  demo           offline standalone Demo boundary checks
  server         authenticated Server boundary, conflict and fail-closed checks
  probes         deliberate-regression probes that must be rejected (superset)
  coverage       normative §13 / modal traceability registry
  report         machine- and human-readable report rendering

The established journeys (Demo/Server persona flows, Run stepper, draft isolation,
correction/withdrawal, fork/denial, recommendation lifecycle) remain in this module
and are all executed below; the package adds traceable coverage on top of them.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from uxqa import coverage as coverage_registry  # noqa: E402
from uxqa import demo as demo_checks  # noqa: E402
from uxqa import probes as probe_checks  # noqa: E402
from uxqa import report as report_render  # noqa: E402
from uxqa import server as server_checks  # noqa: E402
from uxqa.accessibility import assert_accessible  # noqa: E402
from uxqa.accessibility import PageWatch  # noqa: E402

SUITE = "UX-R07 (#126) desktop scenario, visual-consistency and accessibility gate"

ROLES = {
    "workgroup": ["contributor"],
    "engineer": ["user"],
    "management": ["deployment-planner"],
    "maintenance": ["data-maintainer"],
    # UX-R06 publishes real synthetic evidence and reviews it with the same
    # combined account; the grants stay independent, never inherited.
    "multi_role": ["contributor", "user-admin", "deployment-planner", "reviewer"],
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
    # A dedicated publication reviewer (not part of the role-journey loop) is
    # required to exercise the Server-only Recommendation review/withdraw
    # lifecycle, which no writer role may perform. It also carries the
    # Contributor grant because the Workgroup shell only routes a business
    # screen to a persona holding business_write; the reviewer capability alone
    # is what the publication transitions require, and it still denies every
    # ordinary write the lifecycle does not need.
    name = "uxqa-reviewer-" + secrets.token_hex(3)
    password = secrets.token_urlsafe(30)
    subprocess.run(["docker", "compose", "exec", "-T", "api", "python", "manage.py",
                    "bootstrap_identity", "--username", name,
                    "--role", "contributor", "--role", "reviewer",
                    "--password-stdin"], input=password + "\n", text=True,
                   stdout=subprocess.DEVNULL, check=True)
    users["reviewer"] = {"username": name, "password": password}
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(users, handle)
    print("Created disposable, independent, randomized role fixtures (credentials not logged).")


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
    """Independent tests prove the gate rejects representative intentional regressions.

    UX-R07 (#126): delegated to `uxqa.probes`, a superset that additionally proves
    the gate rejects injected authorization-visibility, dialog-focus/containment,
    focus-return and silent-revision-conflict regressions.
    """
    return probe_checks.mutation_probes(browser, artifacts)

def capture(page, directory, name):
    # Never retain sensitive credentials or the contents of unfinished auth forms.
    page.evaluate("""() => document.querySelectorAll('input[type="password"]')
        .forEach(input => { input.value = ''; })""")
    page.screenshot(path=str(directory / (name + ".png")), full_page=True,
                    animations="disabled")


def server_context_login(context, base_url, creds, role, path="/?mode=server"):
    """Real session + CSRF cookie through the visible Server sign-in form."""
    page = context.new_page()
    page.set_default_timeout(15000)
    page.goto(base_url + path, wait_until="domcontentloaded")
    page.locator("#server-login-form").wait_for(state="visible", timeout=25000)
    page.locator("#server-username").fill(creds[role]["username"])
    page.locator("#server-password").fill(creds[role]["password"])
    page.get_by_role("button", name="Sign in to Server").click()
    page.locator("#server-login-form").wait_for(state="hidden", timeout=25000)
    if page.locator("#server-account-name").text_content() != creds[role]["username"]:
        raise AssertionError("Authenticated Server account does not match its fixture")
    return page


def api_request(context, base_url, path, method="POST", payload=None, expect=(200, 201)):
    """Real same-origin API call using the authenticated session's CSRF cookie."""
    csrf = next((cookie["value"] for cookie in context.cookies()
                 if cookie["name"] == "csrftoken"), "")
    headers = {"X-CSRFToken": csrf, "Content-Type": "application/json"}
    response = context.request.fetch(
        base_url + path, method=method,
        data=None if payload is None else json.dumps(payload), headers=headers)
    if expect is not None and response.status not in expect:
        raise AssertionError(
            f"{method} {path} returned {response.status}: {response.text()[:400]}")
    if response.status == 204:
        return {}
    return response.json()


def seed_server_evidence(context, base_url, label, published=True, quantifiable=False):
    """Deterministic, explicitly synthetic Server evidence through the real API.

    Everything is created by an authenticated disposable account with real
    permissions; no Demo record, no mocked authorization and no vendor access.

    ``quantifiable`` records a complete setup duration and a numeric marginal
    cost so the published Run yields a quantifiable Management opportunity cell
    with pinned measured-run revisions (used by the deep §13 #17 drill-down).
    """
    harness = api_request(context, base_url, "/api/v1/catalog/harness", payload={
        "name": "UX-R06 " + label + " Linux-only synthetic harness",
        "properties": {"supported_os": ["linux"], "enterprise_accessibility": "accessible",
                       "interface": "cli", "version": "1.0-synthetic",
                       "details": "Disposable QA fixture, never a production technology"}})
    model = api_request(context, base_url, "/api/v1/models", payload={
        "name": "UX-R06 " + label + " synthetic model",
        "properties": {"enterprise_accessibility": "accessible"}})
    provider = api_request(context, base_url, "/api/v1/catalog/provider", payload={
        "name": "UX-R06 " + label + " synthetic provider",
        "properties": {"enterprise_accessibility": "accessible"}})
    task = api_request(context, base_url, "/api/v1/tasks",
                    payload={"name": "UX-R06 " + label + " synthetic Task"})
    case = api_request(context, base_url, "/api/v1/test-cases", payload={
        "name": "UX-R06 " + label + " synthetic Test Case", "task_id": task["id"],
        "properties": {"objective": "Disposable synthetic challenge",
                       "dod": "Synthetic acceptance only"}})
    guide = api_request(context, base_url, "/api/v1/guides", payload={
        "name": "UX-R06 " + label + " published synthetic guide",
        "properties": {"text": "Synthetic runbook for a disposable fixture"}})
    published_guide = api_request(context, base_url, "/api/v1/guides/" + guide["id"], method="PATCH",
        payload={"expected_revision": guide["revision"], "properties": {
            "text": "Synthetic runbook for a disposable fixture",
            "recipe": {"modules": [{"id": guide["id"], "revision": "r001"}],
                       "required": ["model", "provider", "harness"]},
            "publication": "published"}})["guide"]
    draft_guide = api_request(context, base_url, "/api/v1/guides", payload={
        "name": "UX-R06 " + label + " internal draft guide",
        "properties": {"text": "Draft only; must never appear as published knowledge"}})
    internal_watch = api_request(context, base_url, "/api/v1/watch-entries", payload={
        "name": "UX-R06 " + label + " internal hypothesis",
        "properties": {"hypothesis": "Unreviewed internal hypothesis",
                       "review_state": "draft", "visibility": "internal"}})
    campaign = api_request(context, base_url, "/api/v1/campaigns", payload={
        "name": "UX-R06 " + label + " synthetic campaign", "objective": "Disposable QA objective",
        "mode": "task_centred", "task_id": task["id"], "test_case_ids": [case["id"]],
        "guide_id": guide["id"], "configuration": {"reasoning": None}})
    started = api_request(context, base_url, "/api/v1/campaigns/" + campaign["id"] + "/actions/start",
        payload={"expected_revision": campaign["revision"]})["campaign"]
    session = api_request(context, base_url, "/api/v1/campaigns/" + started["id"] + "/sessions", payload={
            "test_case_id": case["id"],
            "component_ids": {"model": model["id"], "provider": provider["id"],
                              "harness": harness["id"]},
            "settings": {"reasoning": None}, "properties": {"tools": ["git"]},
            "configuration_version": "v1"})
    after_interaction = api_request(context, base_url, "/api/v1/sessions/" + session["id"] + "/interactions", payload={
            "expected_revision": session["revision"], "type": "human_prompt",
            "content": "Synthetic prompt for a disposable QA fixture",
            "human_minutes": 0, "agent_minutes": None})
    close_revision = after_interaction["revision"]
    if quantifiable:
        # Complete the setup duration and a numeric marginal cost so the closed
        # Run measures a quantifiable opportunity (measured human effort + cost),
        # instead of the default unquantifiable synthetic Run.
        setup = api_request(context, base_url, "/api/v1/sessions/" + session["id"] + "/setup",
                            method="PATCH",
                            payload={"expected_revision": close_revision,
                                     "installation_duration_minutes": 3})
        close_revision = setup["revision"]
    closed = api_request(context, base_url, "/api/v1/sessions/" + session["id"] + "/close",
                      payload={
                          "expected_revision": close_revision,
                          "outcome": "accepted", "quality_score": 85,
                          "quality_evaluation": "Synthetic acceptance under its method",
                          "information_utility_score": 67,
                          "information_utility_evaluation": "Synthetic utility",
                          "tokens_count": None, "tokens_multiplier": 1,
                          "cost_mode": "amount" if quantifiable else "flat_rate",
                          "cost_eur": 1.25 if quantifiable else None,
                          "human_review_minutes": 4, "human_correction_minutes": 0,
                          "produced_outputs": "synthetic-artifact.txt"})
    current = api_request(context, base_url, "/api/v1/campaigns/" + started["id"],
                       method="GET", expect=(200,))
    under_review = api_request(context, base_url, "/api/v1/campaigns/" + started["id"] + "/actions/close",
        payload={"expected_revision": current["revision"]})["campaign"]
    result = {"harness": harness, "model": model, "provider": provider, "task": task,
              "case": case, "guide": published_guide, "draft_guide": draft_guide,
              "internal_watch": internal_watch, "campaign": under_review,
              "run": closed, "published": False}
    if published:
        current = api_request(context, base_url, "/api/v1/campaigns/" + started["id"],
                           method="GET", expect=(200,))
        api_request(context, base_url,
                 "/api/v1/campaigns/" + started["id"] + "/publication/publish",
                 payload={"expected_revision": current["revision"], "run_ids": [closed["id"]],
                          "removal_reason": ""})
        result["published"] = True
    return result


def demo_journey(browser, demo_url, artifacts, role, label, viewport):
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    page.set_default_timeout(12000)
    errors = []
    api_calls = []
    findings = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda request: api_calls.append(request.url)
            if "/api/v1/" in request.url else None)
    try:
        # Each browser context is clean; no server identity or database is available.
        page.goto(demo_url + "?mode=demo&workspace=" + label, wait_until="domcontentloaded")
        assert_accessible(page, "demo sign-in " + label, expect_current=False,
                          require_landmark=False, review=findings)
        page.locator(f'[data-act="login"][data-id="{role}"]').click()
        page.locator(".app").wait_for(state="visible", timeout=20000)
        if not page.locator(".ux-shell .ux-content").is_visible() or not page.locator(".ux-shell .ux-sidebar").is_visible():
            raise AssertionError("Demo did not render the common shell")
        if page.locator(".ux-shell").count() != 1:
            raise AssertionError("Demo has competing application shells")
        assert_no_horizontal_overflow(page)
        assert_accessible(page, "Standalone Demo " + label, review=findings)
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

            # UX-R04: Recommendation detail is the same shared component as Server.
            page.locator('[data-act="nav"][data-id="recommendations"]').click()
            rec_card = page.locator(
                '.shared-business-list[data-business-domain="recommendations"] '
                '[data-business-record]').first
            rec_card.wait_for(state="visible", timeout=20000)
            rec_card.locator('button[data-act="recommendationDetail"]').click()
            rec_detail = page.locator(
                '[data-shared-domain-detail="recommendations"][data-domain-mode="demo"]')
            rec_detail.wait_for(state="visible", timeout=20000)
            if "authenticated Server-only" not in rec_detail.inner_text():
                raise AssertionError(
                    "Demo recommendation detail lacks the intentional Server-only model gap notice")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts,
                    "demo-shared-recommendation-detail-" + str(viewport["width"]))
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
        if role == "u1":
            # UX-R04: the Feedback conversation is the shared renderThread
            # component, with explicit public/internal visibility.
            page.locator('[data-act="nav"][data-id="feedback"]').click()
            fb_card = page.locator(
                '[data-business-domain="feedback"] [data-business-record]').filter(
                    has_text="Router context failure").first
            fb_card.wait_for(state="visible", timeout=20000)
            fb_card.locator('button[data-act="feedbackDetail"]').first.click()
            thread = page.locator('[data-shared-thread="demo"]')
            thread.wait_for(state="visible", timeout=20000)
            if thread.locator('[data-message-id]').count() == 0:
                raise AssertionError("Shared Demo feedback thread rendered no message")
            page.get_by_role("dialog").wait_for(state="visible", timeout=20000)
            if "chronological history" not in page.get_by_role("dialog").inner_text().lower():
                raise AssertionError("Shared Demo thread lost its chronological-history heading")
            # An internal reply posted through the shared field component is
            # tagged INTERNAL · workgroup only in the same presentation.
            reply_form = page.locator(".feedback-reply-form")
            reply_form.locator('select[name="visibility"]').select_option("internal")
            reply_form.locator('textarea[name="reply"]').fill(
                "UX-R04 internal workgroup-only Demo note")
            reply_form.get_by_role("button", name="Post reply").click()
            thread = page.locator('[data-shared-thread="demo"]')
            thread.wait_for(state="visible", timeout=20000)
            internal = thread.locator('[data-message-visibility="internal"]')
            if internal.count() == 0:
                raise AssertionError("Internal Demo reply did not render as internal")
            if "INTERNAL · workgroup only" not in internal.last.inner_text():
                raise AssertionError("Internal Demo reply lost its visibility tag")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-shared-feedback-thread-" + str(viewport["width"]))
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
            # UX-R04: the composed pinned-module setup reader is the shared
            # renderComposedSetup component. The Demo seed has no recipe guide,
            # so one is authored locally with a pinned module (explicit coverage
            # gap: Demo has no framework wiring) and re-inspected.
            page.locator('[data-act="nav"][data-id="knowledge"]').click()
            page.locator('[data-act="newGuide"]').first.click()
            gdialog = page.get_by_role("dialog")
            gdialog.wait_for(state="visible")
            gdialog.locator('select[name="type"]').select_option("Installation")
            gdialog.locator('input[name="title"]').fill("UX-R04 composed setup Demo guide")
            gdialog.locator('textarea[name="body"]').fill("Composed setup Demo instructions")
            gdialog.locator('textarea[name="recipe"]').fill(
                '{"modules":[{"id":"g2","revision":"r009"}]}')
            gdialog.get_by_role("button", name="Create document").click()
            gcard = page.locator('[data-business-domain="guides"] [data-business-record]').filter(
                has_text="UX-R04 composed setup Demo guide").first
            gcard.wait_for(state="visible", timeout=20000)
            gcard.locator('button[data-act="guideDetail"]').click()
            composed = page.locator(
                '[data-shared-composed-setup][data-composed-mode="demo"]')
            composed.wait_for(state="visible", timeout=20000)
            gaps = composed.locator("[data-composed-gaps]").inner_text().lower()
            if "missing coverage" not in gaps:
                raise AssertionError(
                    "Shared Demo composed setup did not state its coverage gap: " + gaps)
            if composed.get_attribute("data-composed-ready") != "false":
                raise AssertionError(
                    "Demo composed setup with an unsupplied framework claimed readiness")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-shared-composed-setup-" + str(viewport["width"]))
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
        if errors:
            raise AssertionError("Demo JS runtime error(s): " + "; ".join(errors[:3]))
        return {"findings": findings}
    finally:
        context.tracing.stop(path=str(artifacts / ("demo-" + label + "-" + str(viewport["width"]) + ".zip")))
        context.close()


def demo_persona_journey(browser, demo_url, artifacts, viewport):
    """UX-R06 Demo: published Updates, grounded counter filter, OS variants and
    persona switching for an explicitly multi-role fictional account."""
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    page.set_default_timeout(15000)
    errors = []
    api_calls = []
    findings = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda request: api_calls.append(request.url)
            if "/api/v1/" in request.url else None)
    try:
        page.goto(demo_url + "?mode=demo&workspace=workgroup", wait_until="domcontentloaded")
        page.locator('[data-act="login"][data-id="u6"]').click()
        page.locator(".app").wait_for(state="visible", timeout=20000)
        personas = page.locator(".shared-personas a").all_inner_texts()
        if len(personas) != 3 or any("Maintenance" in name for name in personas):
            raise AssertionError(
                "Multi-role Demo must expose exactly its granted personas: " + str(personas))
        if api_calls:
            raise AssertionError("Standalone Demo unexpectedly contacted an API")
        map_marker = page.locator("[data-workgroup-map]")
        map_marker.wait_for(state="visible", timeout=20000)
        zones = page.locator("[data-workgroup-map] .shared-studio-zone")
        if zones.count() != 5:
            raise AssertionError("Workgroup Studio must expose exactly five themed zones")
        if page.locator("[data-workgroup-map] .shared-studio-core").count() < 5:
            raise AssertionError("Core study areas lost their visual emphasis")
        if not page.evaluate("""() => Array.from(
                document.querySelectorAll('[data-studio-section]'))
                .every(node => node.textContent.trim().length > 0)"""):
            raise AssertionError("Studio blocks lack accessible names")
        published_link = page.locator('[data-studio-published="updates"]')
        gap_link = page.locator('[data-studio-gap="catalog"]')
        if not published_link.count() or not gap_link.count():
            raise AssertionError("Studio lost the published-updates or coverage-gap link")
        badge = page.locator('[data-attention-filter="benchmark"]')
        if not badge.count():
            raise AssertionError("Grounded Under-review attention count is missing")
        if not badge.get_attribute("aria-label"):
            raise AssertionError("Attention count has no accessible label")
        badge.focus()
        page.keyboard.press("Enter")
        page.locator("[data-campaign-focus]").wait_for(state="visible", timeout=20000)
        if "review" not in page.locator("[data-campaign-focus]").inner_text().lower():
            raise AssertionError("Attention count did not open its source filter")
        filtered = page.locator('[data-business-domain="campaigns"] [data-business-record]')
        if filtered.count() != 1:
            raise AssertionError(
                "Filtered campaign view must show the single unresolved record; found %d"
                % filtered.count())
        assert_no_horizontal_overflow(page)
        capture(page, artifacts, "demo-attention-filter-" + str(viewport["width"]))
        page.get_by_role("button", name="Show all stages").click()
        page.wait_for_timeout(300)
        if page.locator('[data-business-domain="campaigns"] [data-business-record]').count() <= 1:
            raise AssertionError("Clearing the counter filter did not restore every campaign")
        page.goto(demo_url + "?mode=demo&workspace=workgroup&section=updates",
                  wait_until="domcontentloaded")
        surface = page.locator('[data-shared-updates="demo"]')
        surface.wait_for(state="visible", timeout=20000)
        if surface.locator("[data-updates-kind]").count() == 0:
            raise AssertionError("Published Demo knowledge is unexpectedly empty")
        if surface.locator('[data-updates-id="g5"]').count():
            raise AssertionError("A draft Demo guide leaked into published updates")
        if surface.locator('[data-updates-id="w2"]').count():
            raise AssertionError("An internal Watch hypothesis leaked into published updates")
        if not surface.locator('[data-updates-id="g1"]').count():
            raise AssertionError("A published Demo guide is missing from published updates")
        # Desktop keyboard and assistive-technology contract for the new surface.
        nav_item = page.locator('[data-act="nav"][data-id="updates"]')
        nav_item.focus()
        if not page.evaluate(
                "() => document.activeElement && "
                "document.activeElement.textContent.includes('Workgroup updates')"):
            raise AssertionError("Published updates nav item is not keyboard focusable")
        withheld = surface.locator(".shared-updates-withheld")
        if not withheld.count() or not withheld.locator("summary").inner_text().strip():
            raise AssertionError("Published updates lack an accessible exclusion disclosure")
        withheld.locator("summary").click()
        if "never included" not in withheld.inner_text():
            raise AssertionError("Excluded internal sources are not stated explicitly")
        if surface.get_by_role("heading", name="Workgroup Updates · What's New").count() != 1:
            raise AssertionError("Published updates lack a single semantic heading")
        if surface.locator("[data-updates-group]").count() == 0:
            raise AssertionError("Published updates are not grouped for progressive reading")
        if not page.evaluate("""() => Array.from(
                document.querySelectorAll('.shared-updates-withheld summary'))
                .every(node => node.tabIndex >= 0 && node.textContent.trim().length > 0)"""):
            raise AssertionError("Exclusion disclosure is not a focusable labelled control")
        measured = surface.locator('[data-updates-kind="measured_result"]').first
        source_link = measured.get_by_role("link").first
        href = source_link.get_attribute("href") or ""
        if "section=results" not in href or "record=" not in href:
            raise AssertionError("Measured update source link lost its exact record route")
        source_link.click()
        page.locator("#ux-demo-run-context").wait_for(state="visible", timeout=20000)
        if page.locator("#ux-demo-run-context .ux-advanced-source pre").is_visible():
            raise AssertionError("Updates drilldown defaults to a raw JSON dump")
        assert_no_horizontal_overflow(page)
        capture(page, artifacts, "demo-updates-source-" + str(viewport["width"]))
        page.go_back(wait_until="domcontentloaded")
        surface.wait_for(state="visible", timeout=20000)

        page.locator('[data-persona="management"]').click()
        page.locator("#demo-management-insights").wait_for(state="visible", timeout=20000)
        page.locator("[data-heat-scenario]").select_option("opp-demo-insights")
        gap = page.locator("[data-heat-gap]").first
        gap.wait_for(state="visible", timeout=20000)
        uncovered_task = gap.get_attribute("data-heat-gap")
        gap.click()
        notice = page.locator("[data-coverage-gap]")
        notice.wait_for(state="visible", timeout=20000)
        if uncovered_task not in notice.inner_text():
            raise AssertionError("Coverage-gap navigation lost the requested Task context")
        if "not a hidden candidate" not in notice.inner_text():
            raise AssertionError("Coverage-gap notice does not state the missing evidence")
        if "created automatically" not in notice.inner_text():
            raise AssertionError("Coverage-gap notice does not deny automatic creation")
        capture(page, artifacts, "demo-coverage-gap-" + str(viewport["width"]))

        page.locator('[data-persona="engineer"]').click()
        page.locator("[data-engineer-body]").wait_for(state="visible", timeout=20000)
        unknown = page.locator("[data-engineer-os-unknown]")
        unknown.wait_for(state="visible", timeout=20000)
        profile_text = page.locator("[data-engineer-body]").inner_text()
        if "Unknown" not in profile_text and "not configured" not in profile_text:
            raise AssertionError("Missing OS profile is not presented as an explicit unknown")
        page.locator("#demo-environment-profile input[name=windows]").check()
        page.get_by_role("button", name="Save my environment").click()
        page.locator("[data-engineer-os-unknown]").wait_for(state="detached", timeout=20000)
        page.wait_for_timeout(600)
        if page.locator(".ux-os-alternative").count() == 0:
            raise AssertionError("A Linux-only alternative was hidden from a Windows-only user")
        alternative = page.locator(".ux-os-alternative").first.inner_text()
        if "Linux" not in alternative:
            raise AssertionError("Other-OS alternative does not name the required OS")
        body_text = page.locator("[data-engineer-body]").inner_text()
        if "windows" not in body_text.lower():
            raise AssertionError("Declared OS is not reflected in Engineer discovery")
        if page.locator("[data-engineer-view=tool]").count() != 1:
            raise AssertionError("By Tool inversion is not keyboard reachable")
        assert_no_horizontal_overflow(page)
        assert_accessible(page, "Standalone Demo multi-role engineer", review=findings)
        capture(page, artifacts, "demo-engineer-os-" + str(viewport["width"]))
        if errors:
            raise AssertionError("Demo persona JS runtime error(s): " + "; ".join(errors[:3]))
        return {"personas": len(personas), "zones": 5, "findings": findings}
    finally:
        context.tracing.stop(path=str(artifacts / ("demo-personas-" +
                                                   str(viewport["width"]) + ".zip")))
        context.close()


def server_publication_journey(browser, base_url, creds, artifacts, viewport):
    """UX-R06 Server: real published evidence, counter filter, reader boundaries."""
    publisher_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    workgroup_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    engineer_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    maintenance_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    try:
        server_context_login(publisher_context, base_url, creds, "multi_role",
                "/?mode=server&workspace=workgroup")
        evidence = seed_server_evidence(publisher_context, base_url, "published", published=True)
        review_campaign = seed_server_evidence(publisher_context, base_url, "review", published=False)
        seed_server_evidence(publisher_context, base_url, "second", published=True)

        workgroup = server_context_login(workgroup_context, base_url, creds, "workgroup",
                            "/?mode=server&workspace=workgroup&section=studio")
        home = workgroup.locator("#server-workgroup-home")
        home.wait_for(state="visible", timeout=25000)
        badge = workgroup.locator('#server-workgroup-home [data-attention-filter="benchmark"]')
        badge.wait_for(state="visible", timeout=25000)
        if badge.get_attribute("aria-label") is None:
            raise AssertionError("Server attention count has no accessible label")
        badge.click()
        workgroup.locator("[data-campaign-status-focus]").wait_for(state="visible",
                                                                   timeout=25000)
        focus_text = workgroup.locator("[data-campaign-status-focus]").inner_text().lower()
        if "awaiting a review decision" not in focus_text:
            raise AssertionError("Server counter filter does not name the pending decision")
        if "not a personal assignment" not in focus_text:
            raise AssertionError("Server counter filter does not explain its derived scope")
        if not workgroup.locator(
                '[data-business-record="%s"]' % review_campaign["campaign"]["id"]).count():
            raise AssertionError("Under-review campaign missing from the filtered list")
        if workgroup.locator(
                '[data-business-record="%s"]' % evidence["campaign"]["id"]).count():
            raise AssertionError("Published campaign leaked into the under-review filter")
        assert_no_horizontal_overflow(workgroup)
        capture(workgroup, artifacts, "server-counter-filter-" + str(viewport["width"]))
        workgroup.get_by_role("button", name="Show all campaigns").click()
        workgroup.wait_for_timeout(400)

        workgroup.goto(base_url + "/?mode=server&workspace=workgroup&section=updates",
                       wait_until="domcontentloaded")
        surface = workgroup.locator('[data-shared-updates="server"]')
        surface.wait_for(state="visible", timeout=25000)
        if surface.locator("[data-updates-kind]").count() == 0:
            raise AssertionError("Published Server knowledge is unexpectedly empty")
        for label, record in (("published guide", evidence["guide"]["id"]),
                              ("draft guide", evidence["draft_guide"]["id"]),
                              ("internal watch", evidence["internal_watch"]["id"])):
            present = surface.locator(f'[data-updates-id="{record}"]').count()
            if "published" in label and not present:
                raise AssertionError(f"A published Server {label} is missing from updates")
            if "draft" in label.lower() or "internal" in label:
                if present:
                    raise AssertionError(f"A restricted Server {label} leaked into updates")
        if surface.locator(f'[data-updates-id="{evidence["campaign"]["id"]}"]').count() == 0:
            raise AssertionError("Published campaign announcement is missing")
        if surface.locator(f'[data-updates-id="{review_campaign["campaign"]["id"]}"]').count():
            raise AssertionError("Unpublished campaign leaked into published updates")
        if surface.locator(f'[data-updates-id="{evidence["run"]["id"]}"]').count() == 0:
            raise AssertionError("Published measured Run is missing from updates")
        assert_no_horizontal_overflow(workgroup)
        capture(workgroup, artifacts, "server-updates-workgroup-" + str(viewport["width"]))

        engineer = server_context_login(engineer_context, base_url, creds, "engineer",
                           "/?mode=server&workspace=engineer&section=updates")
        reader_surface = engineer.locator('[data-shared-updates="server"]')
        reader_surface.wait_for(state="visible", timeout=25000)
        if reader_surface.locator("[data-updates-kind]").count() == 0:
            raise AssertionError("A reader cannot see published Server knowledge")
        denied = reader_surface.locator("[data-updates-source-denied]")
        if denied.count() == 0:
            raise AssertionError(
                "An unreachable Workgroup source was offered as a live reader link")
        if "is not available to this account" not in denied.first.inner_text():
            raise AssertionError("Unreachable source does not explain the access boundary")
        results_link = reader_surface.locator(
            '[data-updates-kind="measured_result"] a').first
        if "section=results" not in (results_link.get_attribute("href") or ""):
            raise AssertionError("Reader-visible measured source link is not authorized")
        draft_selector = '[data-updates-id="%s"]' % evidence["draft_guide"]["id"]
        if reader_surface.locator(draft_selector).count():
            raise AssertionError("Draft guide leaked into the reader's published view")
        capture(engineer, artifacts, "server-updates-engineer-" + str(viewport["width"]))

        maintainer = server_context_login(maintenance_context, base_url, creds, "maintenance",
                             "/maintenance?mode=server")
        maintainer.goto(base_url + "/maintenance?mode=server&section=updates",
                        wait_until="domcontentloaded")
        maintainer.wait_for_timeout(1500)
        if maintainer.locator("#server-updates").is_visible():
            raise AssertionError("Maintenance-only account received published Workgroup updates")
        if maintainer.locator("#server-governance-audit").is_hidden():
            raise AssertionError("Maintenance workspace lost its authorized audit view")
        assert_exactly_one_view(maintainer, "#ux-screen-host > [data-ux-screen]")
        maintainer.goto(base_url + "/?mode=server&workspace=workgroup&section=studio",
                        wait_until="domcontentloaded")
        maintainer.wait_for_timeout(1500)
        if (maintainer.locator("#server-workgroup-home").is_visible() or
                maintainer.locator("#server-campaigns").is_visible() or
                maintainer.locator("#server-updates").is_visible()):
            raise AssertionError(
                "Maintenance-only account obtained Workgroup business screens by URL")
        assert_exactly_one_view(maintainer, "#ux-screen-host > [data-ux-screen]")

        workgroup.goto(base_url + "/?mode=server&workspace=workgroup&section=users",
                       wait_until="domcontentloaded")
        workgroup.wait_for_timeout(1500)
        if workgroup.locator("#server-users").is_visible():
            raise AssertionError("A contributor reached Users & Access by URL")
        assert_exactly_one_view(workgroup, "#ux-screen-host > [data-ux-screen]")
        capture(maintainer, artifacts, "server-updates-maintenance-" + str(viewport["width"]))
        return {"published_items": reader_surface.locator("[data-updates-kind]").count()}
    finally:
        for context in (publisher_context, workgroup_context, engineer_context,
                        maintenance_context):
            context.close()


def server_persona_deep_journey(browser, base_url, creds, artifacts, viewport):
    """UX-R06 §13 #4 (Engineer feedback) and #17 (Management drill-down), real Server.

    A rendered link or an empty list is not a journey: this seeds real
    authenticated Server records and exercises the actual submissions,
    drill-down and non-disclosure, then the return navigation.
    """
    author_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    engineer_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    management_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    try:
        server_context_login(author_context, base_url, creds, "multi_role",
                             "/?mode=server&workspace=workgroup")
        evidence = seed_server_evidence(author_context, base_url, "deep", published=True,
                                        quantifiable=True)

        # --- §13 #4: Engineer submits authentic usage feedback tied to a measured
        # Solution/Task and verifies the recorded discussion and its visibility. ---
        # Open the exact published measured Solution through the authorized deep
        # link (task + solution route params) so the journey exercises the real
        # detail regardless of the person's reactive-relevance subset.
        engineer = server_context_login(
            engineer_context, base_url, creds, "engineer",
            "/?mode=server&workspace=engineer&all_tasks=true&task=%s&solution=%s"
            % (evidence["task"]["id"], evidence["run"]["solution_id"]))
        engineer.locator("#server-engineer").wait_for(state="visible", timeout=25000)
        engineer.locator("#ux-engineer-feedback").wait_for(state="visible", timeout=25000)
        comment = "UX-R06 authenticated feedback on measured Solution " + evidence["run"]["id"]
        engineer.locator("[data-engineer-kind]").select_option("feedback")
        engineer.locator("[data-engineer-comment]").fill(comment)
        engineer.locator("[data-engineer-send]").click()
        engineer.locator("[data-engineer-status]").filter(
            has_text="no entitlement or provisioning was granted").wait_for(
                state="visible", timeout=25000)
        # Read back through the real authorized, public, authenticated API: the
        # recorded thread is tied to the measured Solution's exact context id.
        solution_id = evidence["run"]["solution_id"]
        recorded = engineer.evaluate(
            "async (sid) => { const r = await fetch('/api/v1/discussions',"
            " {credentials: 'same-origin'}); const j = await r.json();"
            " return (j.results || []).filter(x => x.context_id === sid &&"
            "   x.properties && x.properties.kind === 'feedback')"
            "   .map(x => x.properties.scope); }", solution_id)
        if not recorded:
            raise AssertionError("Engineer feedback was not recorded as a readable discussion")
        if recorded != ["public"]:
            raise AssertionError("Engineer feedback discussion is not public-scoped: %s" % recorded)
        # Context preservation: the detail preserves its discovery context, and its
        # breadcrumb returns to the source list with the URL state intact.
        return_link = engineer.locator("[data-engineer-home]")
        if return_link.count() == 0:
            raise AssertionError("Engineer detail offers no return to its source discovery")
        if "all_tasks=true" not in (return_link.get_attribute("href") or ""):
            raise AssertionError("Engineer detail breadcrumb drops the discovery context")
        return_link.click()
        engineer.locator("[data-engineer-body]").wait_for(state="visible", timeout=20000)
        if "all_tasks=true" not in engineer.url:
            raise AssertionError("Engineer return navigation dropped the discovery context")
        assert_exactly_one_view(engineer, "#ux-screen-host > [data-ux-screen]")
        assert_no_horizontal_overflow(engineer)
        capture(engineer, artifacts, "server-engineer-feedback-" + str(viewport["width"]))

        # --- §13 #17: Management lands on authorized economics, drills to the exact
        # Task/configuration factors and revisions, and individual rates never leak. ---
        management = server_context_login(management_context, base_url, creds, "management",
                              "/?mode=server&workspace=management")
        management.locator("#server-management-insights").wait_for(state="visible", timeout=25000)
        # Build one real saved scenario for the seeded population; the fixture is
        # published measured evidence reached by the shared published selector.
        readiness = _management_seed_scenario(management, base_url, evidence)
        if not readiness:
            raise AssertionError("Management fixture (population/scenario) could not be built")
        seeded_profile = readiness["profile_id"]
        seeded_scenario = readiness["scenario_id"]
        management.reload(wait_until="domcontentloaded")
        management.locator("#server-management-insights").wait_for(state="visible", timeout=25000)
        profile_select = management.locator("[data-heat-profile]")
        profile_select.wait_for(state="visible", timeout=25000)
        profile_values = profile_select.locator("option").evaluate_all(
            "els => els.map(e => e.value).filter(Boolean)")
        if seeded_profile not in profile_values:
            raise AssertionError("Seeded population is not offered by the Management heatmap")
        profile_select.select_option(seeded_profile)
        scenario_select = management.locator("[data-heat-scenario]")
        scenario_select.wait_for(state="visible", timeout=25000)
        management.wait_for_timeout(1200)
        option_values = scenario_select.locator("option").evaluate_all(
            "els => els.map(e => e.value).filter(Boolean)")
        if seeded_scenario not in option_values:
            raise AssertionError("Seeded saved scenario is not offered for its population")
        scenario_select.select_option(seeded_scenario)
        management.wait_for_timeout(1200)
        # Drill into the seeded Task × measured configuration cell. The bounded
        # taxonomy pages the grid (row_size 8), and the seeded Task may sit past
        # the first page, so walk the authorized row/column pages until the exact
        # cell is reachable, then click it.
        cell = management.locator(
            '[data-heat-cell="%s|benchmark|%s"]'
            % (evidence["task"]["id"], evidence["run"]["solution_id"])).first

        def _reset_columns():
            for _ in range(6):
                prev_col = management.locator("[data-heat-cprev]")
                if prev_col.count() == 0 or prev_col.is_disabled():
                    break
                prev_col.click()
                management.wait_for_timeout(500)

        found = False
        for _rows in range(12):
            _reset_columns()
            for _cols in range(6):
                if cell.count() and cell.is_visible():
                    found = True
                    break
                next_col = management.locator("[data-heat-cnext]")
                if next_col.count() == 0 or next_col.is_disabled():
                    break
                next_col.click()
                management.wait_for_timeout(700)
            if found:
                break
            next_row = management.locator("[data-heat-rnext]")
            if next_row.count() == 0 or next_row.is_disabled():
                break
            next_row.click()
            management.wait_for_timeout(700)
        if not found:
            raise AssertionError(
                "Seeded Task cell is not reachable in the authorized heatmap")
        cell.click()
        inspector = management.locator(".heat-inspector")
        inspector.wait_for(state="visible", timeout=25000)
        # Expand the authorized factor branches until the exact pinned measured
        # source revision (immutable provenance) is visible.
        branches = management.locator(".heat-inspector [data-heat-branch]")
        pinned = management.locator(".heat-inspector .ux-source-ref")
        expanded = False
        for index in range(branches.count()):
            branches.nth(index).click()
            management.wait_for_timeout(300)
            if pinned.count():
                expanded = True
                break
        if not expanded:
            raise AssertionError("Management drill-down shows no pinned source revision")
        management.locator(".heat-inspector .ux-inspector-kv").first.wait_for(
            state="visible", timeout=20000)
        inspector_text = inspector.inner_text()
        if evidence["task"]["id"] not in inspector_text:
            raise AssertionError("Management drill-down does not name the exact source Task")
        if evidence["run"]["id"] not in inspector_text:
            raise AssertionError(
                "Management drill-down does not pin the exact measured Run revision")
        # The raw JSON dump must never be the default; it stays behind a disclosure.
        json_dump = management.locator(".heat-inspector .ux-advanced-source > pre")
        if json_dump.count() and json_dump.first.is_visible():
            raise AssertionError("Management drill-down exposes a raw JSON dump by default")
        # Restricted individual rates must never reach the Management view.
        page_text = management.locator("#server-management-insights").inner_text()
        for secret in ("hourly_rate_eur", "valuation_eur_per_hour",
                       "baseline_human_hours", "linked_user"):
            if secret in page_text:
                raise AssertionError("Management view leaked restricted field '%s'" % secret)
        assert_no_horizontal_overflow(management)
        capture(management, artifacts, "server-management-drilldown-" + str(viewport["width"]))
        return {"feedback_recorded": len(recorded), "management_cell": True}
    finally:
        for context in (author_context, engineer_context, management_context):
            context.close()


def _management_seed_scenario(page, base_url, evidence):
    """Create one real cohort population + saved annual scenario for the seeded Task."""
    profile = page.evaluate("""async (task) => {
        const r = await fetch('/api/v1/planning/profiles', {method: 'POST',
          credentials: 'same-origin', headers: {'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''},
          body: JSON.stringify({kind: 'cohort', name: 'UX-R06 synthetic population',
            headcount: 3, hourly_rate_eur: '375.75',
            workloads: [{task_id: task, annual_occurrences: '12', baseline_human_hours: '4'}]})});
        return {status: r.status, body: await r.json().catch(() => ({}))};
    }""", evidence["task"]["id"])
    if profile["status"] != 201:
        return False
    profile_id = profile["body"].get("id") or profile["body"].get("public_id")
    if not profile_id:
        return False
    scenario = page.evaluate("""async ({profile_id, task, solution}) => {
        const r = await fetch('/api/v1/planning/opportunities', {method: 'POST',
          credentials: 'same-origin', headers: {'Content-Type': 'application/json',
          'X-CSRFToken': (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || ''},
          body: JSON.stringify({profile_id: profile_id, scenario: {
            name: 'UX-R06 annual scenario', benchmark_weight: '0.8',
            choices: [{task_id: task, kind: 'benchmark', candidate_id: solution}]}})});
        return {status: r.status, body: await r.json().catch(() => ({}))};
    }""", {"profile_id": profile_id, "task": evidence["task"]["id"],
           "solution": evidence["run"]["solution_id"]})
    if scenario["status"] not in (200, 201):
        return False
    scenario_id = scenario["body"].get("id") or scenario["body"].get("public_id")
    if not scenario_id:
        return False
    return {"profile_id": profile_id, "scenario_id": scenario_id}


def server_journey(browser, base_url, creds, artifacts, role, viewport):
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    traced = False  # Keep the password entry entirely outside the downloadable trace.
    page = context.new_page()
    page.set_default_timeout(15000)
    errors = []
    findings = []
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
        assert_accessible(page, f"Authenticated Server {role}", review=findings)
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
                if domain == "recommendations":
                    history = page.locator('#rec-list button[data-action="history"]')
                    if history.count():
                        history.first.click()
                        rec_detail = page.locator(
                            '[data-shared-domain-detail="recommendations"][data-domain-mode="server"]')
                        rec_detail.wait_for(state="visible", timeout=20000)
                        if "Immutable, attributable publication history" not in rec_detail.inner_text():
                            raise AssertionError(
                                "Server recommendation detail does not use the shared projector")
                        assert_no_horizontal_overflow(page)
                        capture(page, artifacts,
                                "server-shared-recommendation-detail-" + str(viewport["width"]))

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
            # UX-R04: the composed pinned-module reader is the same shared
            # renderComposedSetup component. A real recipe guide is created and
            # rendered through the read-only applicability inspector; the
            # un-supplied module revision stays an explicit coverage gap.
            recipe_guide = "UX-R04 composed setup guide " + secrets.token_hex(3)
            page.locator("#guide-add").click()
            form = page.locator("#guide-editor form.guide-form")
            form.wait_for(state="visible", timeout=12000)
            rfields = form.locator('[data-shared-guide-fields="server"]')
            rfields.locator('input[name="name"]').fill(recipe_guide)
            rfields.locator('textarea[name="text"]').fill("Composed setup controller text")
            form.locator('textarea[name="recipe_spec"]').fill(
                '{"modules":[{"id":"gui-0000000000000000","revision":"r001"}]}')
            form.locator('button[type="submit"]').click()
            rcard = page.locator('[data-business-domain="guides"] [data-business-record]').filter(
                has_text=recipe_guide).first
            rcard.wait_for(state="visible", timeout=30000)
            rcard.locator('button[data-action="preview"]').click()
            page.locator("#guide-render-now").wait_for(state="visible", timeout=15000)
            page.locator("#guide-render-now").click()
            composed = page.locator(
                '#guide-render-result [data-shared-composed-setup][data-composed-mode="server"]')
            composed.wait_for(state="visible", timeout=20000)
            gaps = composed.locator("[data-composed-gaps]").inner_text().lower()
            if "missing coverage" not in gaps:
                raise AssertionError(
                    "Shared Server composed setup did not state its coverage gap: " + gaps)
            if composed.get_attribute("data-composed-ready") != "false":
                raise AssertionError(
                    "Server composed setup with an unresolved pin claimed readiness")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "server-shared-composed-setup-" + str(viewport["width"]))
        if role == "workgroup":
            # UX-R04: real Server feedback thread through the shared renderThread
            # component, with a correction that keeps the superseded body in an
            # immutable revision history.
            page.goto(base_url + "/?mode=server&workspace=workgroup&section=feedback&view=editor",
                      wait_until="domcontentloaded")
            page.locator("#discussion-new").wait_for(state="visible", timeout=30000)
            page.locator("#discussion-new").click()
            compose = page.locator("#discussion-compose form")
            compose.wait_for(state="visible", timeout=15000)
            thread_title = "UX-R04 discussion " + secrets.token_hex(3)
            compose.locator('input[name="title"]').fill(thread_title)
            compose.locator('textarea[name="body"]').fill("Original discussion body text")
            compose.get_by_role("button", name="Publish feedback").click()
            thread = page.locator('#discussion-messages [data-shared-thread="server"]')
            thread.wait_for(state="visible", timeout=30000)
            if thread.locator("[data-message-id]").count() == 0:
                raise AssertionError("Shared Server thread rendered no message")
            capture(page, artifacts, "server-shared-feedback-thread-" + str(viewport["width"]))
            first_message = thread.locator("[data-message-id]").first
            first_id = first_message.get_attribute("data-message-id")
            first_message.locator('button[data-action="correct"]').first.click()
            correction = page.locator("#discussion-correction-form")
            correction.wait_for(state="visible", timeout=15000)
            correction.locator('textarea[name="body"]').fill("Corrected discussion body text")
            correction.locator('textarea[name="edit_reason"]').fill(
                "UX-R04 shared correction reason")
            correction.get_by_role("button", name="Append correction revision").click()
            corrected_body = page.locator(
                '#discussion-messages [data-shared-thread="server"]').get_by_text(
                    "Corrected discussion body text")
            corrected_body.first.wait_for(state="visible", timeout=30000)
            thread = page.locator('#discussion-messages [data-shared-thread="server"]')
            corrected = thread.locator(f'[data-message-id="{first_id}"]').first
            corrected.wait_for(state="visible", timeout=20000)
            if "Corrected discussion body text" not in corrected.inner_text():
                raise AssertionError("Server correction did not update the shared thread")
            # Immutable history keeps the superseded original wording, rendered
            # through the shared revision-history reader.
            corrected.locator('button[data-action="history"]').first.click()
            history = page.locator("#discussion-history")
            history.wait_for(state="visible", timeout=15000)
            revision_reader = history.locator(
                '[data-shared-revision-history="discussions"][data-revision-mode="server"]')
            revision_reader.wait_for(state="visible", timeout=15000)
            revisions = revision_reader.locator("[data-shared-revision]")
            if revisions.count() < 2:
                raise AssertionError(
                    "Server revision history did not use the shared reader")
            # The revised bodies live inside collapsed <details>; expand the
            # retained revisions before asserting their immutable content.
            for summary in revision_reader.locator("details summary").all():
                summary.click()
            reader_text = revision_reader.inner_text()
            if "Original discussion body text" not in reader_text:
                raise AssertionError(
                    "Server correction history lost the original superseded body")
            if "UX-R04 shared correction reason" not in reader_text:
                raise AssertionError("Server correction history lost the retained reason")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts,
                    "server-shared-discussion-correction-" + str(viewport["width"]))
        if role == "workgroup":
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
            # UX-R04 §13 #19: an uncommitted draft is scoped to this mode/account
            # and can never cross into the Demo cache (or any other mode).
            page.locator("#watch-add-entry").click()
            draft_form = page.locator("#watch-form")
            draft_form.wait_for(state="visible")
            typed = "UX-R04 uncommitted Server draft value"
            draft_form.locator('input[name="name"]').fill(typed)
            draft_form.locator('textarea[name="hypothesis"]').fill(typed)
            draft_keys = page.evaluate("""() => Object.keys(window.localStorage)
                .filter(key => key.startsWith("ai-compass-working-draft:"))""")
            if not any("server" in key for key in draft_keys):
                raise AssertionError("Server draft was not scoped to the server mode")
            if any("demo" in key for key in draft_keys):
                raise AssertionError("A Demo draft key leaked into the Server context")
            if not page.evaluate(
                    "value => Object.keys(window.localStorage).some("
                    "key => window.localStorage.getItem(key).includes(value))", typed):
                raise AssertionError("The uncommitted Server draft value was not cached")
            server_draft_keys = page.evaluate("""() => Object.keys(window.localStorage)
                .filter(key => key.startsWith("ai-compass-working-draft:"))""")
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
        return {"visible_active_screens": 1, "shared_shell": True, "findings": findings}
    finally:
        if traced:
            context.tracing.stop(path=str(artifacts / ("server-" + role + "-" + str(viewport["width"]) + ".zip")))
        context.close()


def draft_isolation(browser, base_url, demo_url, creds, artifacts, viewport):
    """UX-R04 §13 #19: a local draft cache never crosses Demo/Server modes.

    Drafts are namespaced by [mode, origin, account, kind, id]; this proves the
    two modes write disjoint, non-overlapping key sets and that neither can read
    the other's uncommitted text.
    """
    prefix = "ai-compass-working-draft:"
    # Distinct per-mode literals so a same-origin substring scan cannot mistake
    # Demo's own legitimately-cached text for the Server's uncommitted value.
    server_typed = "UX-R04 cross-mode Server isolation value"
    demo_typed = "UX-R04 cross-mode Demo isolation value"
    typed = server_typed
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    page = context.new_page()
    page.set_default_timeout(30000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        # Authenticated Server: the draft cache is scoped to the Server mode.
        page.goto(base_url + "/?mode=server&workspace=workgroup&section=watch&view=editor",
                  wait_until="domcontentloaded")
        page.locator("#server-login-form").wait_for(state="visible", timeout=30000)
        page.locator("#server-username").fill(creds["workgroup"]["username"])
        page.locator("#server-password").fill(creds["workgroup"]["password"])
        page.get_by_role("button", name="Sign in to Server").click()
        page.locator('#ux-screen-host[data-ux-current]').wait_for(state="visible", timeout=30000)
        page.locator("#watch-add-entry").wait_for(state="visible", timeout=30000)
        page.locator("#watch-add-entry").click()
        watch_form = page.locator("#watch-form")
        watch_form.wait_for(state="visible")
        watch_form.locator('input[name="name"]').fill(typed)
        watch_form.locator('textarea[name="hypothesis"]').fill(typed)
        page.wait_for_timeout(300)  # The draft is saved on input/change.
        server_keys = page.evaluate(
            "prefix => Object.keys(window.localStorage).filter(k => k.startsWith(prefix))",
            prefix)
        if not server_keys:
            raise AssertionError("Server did not cache an uncommitted draft")
        if not any("server" in key for key in server_keys):
            raise AssertionError("Server draft key is not scoped to the server mode")
        if any(key.split(prefix, 1)[1].startswith("demo") for key in server_keys):
            raise AssertionError("A Demo-scoped draft key exists in the Server context")
        server_recovery = page.evaluate(
            "value => Object.keys(window.localStorage).filter(k => k.startsWith("
            "'ai-compass-working-draft:')).map(k => window.localStorage.getItem(k)).join('')",
            typed)
        if typed not in server_recovery:
            raise AssertionError("The uncommitted Server draft value was not recoverable")
        assert_exactly_one_view(page, "#ux-screen-host > [data-ux-screen]")

        # Standalone Demo (separate origin): only Demo-scoped drafts, and the
        # Server's uncommitted text is absent.
        demo = context.new_page()
        demo.set_default_timeout(30000)
        demo_errors = []
        demo.on("pageerror", lambda e: demo_errors.append(str(e)))
        demo.goto(demo_url + "?mode=demo&workspace=workgroup", wait_until="domcontentloaded")
        demo.locator('[data-act="login"][data-id="u1"]').click()
        demo.locator(".app").wait_for(state="visible", timeout=30000)
        demo.locator('[data-act="nav"][data-id="knowledge"]').click()
        demo.locator('[data-act="newGuide"]').first.click()
        gdialog = demo.get_by_role("dialog")
        gdialog.wait_for(state="visible")
        gdialog.locator('select[name="type"]').select_option("Installation")
        gdialog.locator('input[name="title"]').fill(demo_typed)
        gdialog.locator('textarea[name="body"]').fill("Demo-only draft body")
        demo.wait_for_timeout(300)
        demo_keys = demo.evaluate(
            "prefix => Object.keys(window.localStorage).filter(k => k.startsWith(prefix))",
            prefix)
        # If the Demo frontend ever attaches draft caching, its keys must be
        # Demo-scoped and must never include the Server's uncommitted text.
        if any(key.split(prefix, 1)[1].startswith("demo") for key in demo_keys):
            pass
        elif any(key.split(prefix, 1)[1].startswith("server") for key in demo_keys):
            raise AssertionError("A Server-scoped draft key exists in the Demo context")
        if demo.evaluate("value => Object.keys(window.localStorage).some("
                         "k => k.startsWith('ai-compass-working-draft:') && "
                         "window.localStorage.getItem(k).includes(value))", server_typed):
            raise AssertionError("The Server's uncommitted draft text leaked into Demo")
        if demo_errors:
            raise AssertionError("Demo JS runtime error(s): " + "; ".join(demo_errors[:3]))
        # Disjoint sets: no Server-scoped key exists in the Demo context and no
        # Demo-scoped key exists in the Server context.
        demo_scoped_in_server = [key for key in server_keys
                                 if key.split(prefix, 1)[1].startswith("demo")]
        server_scoped_in_demo = [key for key in demo_keys
                                 if key.split(prefix, 1)[1].startswith("server")]
        if demo_scoped_in_server or server_scoped_in_demo:
            raise AssertionError("Demo and Server draft scopes are not disjoint")
        assert_no_horizontal_overflow(page)
        return {"server_draft_keys": len(server_keys), "demo_draft_keys": len(demo_keys)}
    finally:
        context.close()


def api_call(page, method, path, payload=None):
    """Drive the real REST API from the authenticated browser context.

    Uses only the session cookie and CSRF token the page already holds; no
    privileged test hook and no Django fixture command. Returns status + JSON.
    """
    return page.evaluate("""async ({method, path, payload}) => {
        const cookie = document.cookie.split('; ')
            .find(c => c.startsWith('csrftoken='));
        const headers = {'Content-Type': 'application/json'};
        if (cookie) headers['X-CSRFToken'] = cookie.split('=')[1];
        const options = {method, headers, credentials: 'same-origin'};
        if (payload !== null && payload !== undefined)
            options.body = JSON.stringify(payload);
        const response = await fetch('/api/v1/' + path, options);
        const body = await response.json().catch(() => ({}));
        return {status: response.status, body};
    }""", {"method": method, "path": path, "payload": payload})


def assert_api(result, expected, label):
    if result["status"] != expected:
        raise AssertionError(f"{label} returned {result['status']}: " +
                             json.dumps(result["body"])[:200])
    return result["body"]


def upload_evidence(page, item_id, filename, content, revision=""):
    """Upload one real evidence blob from the authenticated browser context.

    Uses the session cookie + CSRF token the page already holds; never a Django
    fixture command. Returns status + JSON, exactly like api_call.
    """
    return page.evaluate("""async ({itemId, filename, content, revision}) => {
        const cookie = document.cookie.split('; ')
            .find(c => c.startsWith('csrftoken='));
        const headers = {};
        if (cookie) headers['X-CSRFToken'] = cookie.split('=')[1];
        const form = new FormData();
        form.append('file', new Blob([content], {type: 'text/plain'}), filename);
        form.append('source', 'UX-R04 automated proof');
        form.append('provenance', JSON.stringify({usage: 'probe'}));
        if (revision) form.append('revision', revision);
        const response = await fetch('/api/v1/catalog/items/' + encodeURIComponent(itemId) +
            '/evidence/upload', {method: 'POST', headers, credentials: 'same-origin',
            body: form});
        const body = await response.json().catch(() => ({}));
        return {status: response.status, body};
    }""", {"itemId": item_id, "filename": filename, "content": content,
           "revision": revision})


def sign_in(page, base_url, credential):
    page.goto(base_url + "/?mode=server&workspace=workgroup&section=studio",
              wait_until="domcontentloaded")
    page.locator("#server-login-form").wait_for(state="visible", timeout=30000)
    page.locator("#server-username").fill(credential["username"])
    page.locator("#server-password").fill(credential["password"])
    page.get_by_role("button", name="Sign in to Server").click()
    page.locator('#ux-screen-host[data-ux-current]').wait_for(state="visible", timeout=30000)
    page.locator("#server-login-form").wait_for(state="hidden", timeout=30000)


def build_measured_run(page, suffix, label="UX-R04"):
    """Create one real individual measured Run through the public REST API.

    No Django seed command (business fixtures are forbidden there). Returns the
    created Run dict plus the task / test case / campaign it belongs to, so a
    caller can reuse the same fixture for correction, withdrawal or evidence.
    """
    model = assert_api(api_call(page, "POST", "models", {
        "name": label + " model " + suffix, "properties": {}}), 201, "model")
    provider = assert_api(api_call(page, "POST", "catalog/provider", {
        "name": label + " provider " + suffix, "properties": {}}), 201, "provider")
    harness = assert_api(api_call(page, "POST", "catalog/harness", {
        "name": label + " harness " + suffix,
        "properties": {"osWindows": True}}), 201, "harness")
    task = assert_api(api_call(page, "POST", "tasks", {
        "name": label + " task " + suffix,
        "properties": {"phase": "SWE", "domain": "Embedded",
                       "criteria": "Disposable lifecycle fixture"}}), 201, "task")
    case = assert_api(api_call(page, "POST", "test-cases", {
        "name": label + " case " + suffix, "task_id": task["id"],
        "properties": {"objective": "probe", "inputs": "none",
                       "expected_outputs": "none", "dod": "probe DoD"}}),
        201, "test case")
    # A real publication requires a documented, ready setup recipe pinned to the
    # guide, covering the selected components. Build one the same way a real
    # author does: a guide with text, then a revision carrying the recipe.
    guide = assert_api(api_call(page, "POST", "guides", {
        "name": label + " guide " + suffix,
        "properties": {"text": "Install the pinned trio and verify wiring."}}),
        201, "guide")
    assert_api(api_call(page, "PATCH", "guides/" + guide["id"], {
        "expected_revision": guide["revision"],
        "properties": {"text": "Install the pinned trio and verify wiring.",
                       "recipe": {"modules": [{"id": guide["id"],
                                               "revision": guide["revision"]}],
                                  "required": ["model", "provider", "harness"]}}}),
        200, "guide recipe")
    campaign = assert_api(api_call(page, "POST", "campaigns", {
        "name": label + " campaign " + suffix,
        "objective": "produce one real individual measured Run",
        "mode": "task_centred", "task_id": task["id"],
        "test_case_ids": [case["id"]], "guide_id": guide["id"],
        "configuration": {"reasoning": None}}), 201, "campaign")
    started = assert_api(api_call(page, "POST",
        "campaigns/" + campaign["id"] + "/actions/start",
        {"expected_revision": campaign["revision"]}), 200, "campaign start")
    session = assert_api(api_call(page, "POST",
        "campaigns/" + campaign["id"] + "/sessions", {
            "test_case_id": case["id"],
            "component_ids": {"model": model["id"], "provider": provider["id"],
                              "harness": harness["id"]},
            "settings": {"nullable": None}, "configuration_version": "1",
            "properties": {"tool": "shell"}}), 201, "session")
    assert_api(api_call(page, "POST", "sessions/" + session["id"] + "/interactions", {
        "expected_revision": session["revision"], "type": "human_prompt",
        "content": "Create SPI driver", "human_minutes": 3, "agent_minutes": None,
        "extensions": {"unknown": None}}), 200, "interaction")
    run = assert_api(api_call(page, "POST", "sessions/" + session["id"] + "/close", {
        "expected_revision": "r002", "outcome": "accepted", "quality_score": 82,
        "quality_evaluation": "Regression passed", "information_utility_score": None,
        "tokens_count": None, "tokens_multiplier": 1, "cost_mode": "flat_rate",
        "cost_eur": None, "human_review_minutes": None,
        "human_correction_minutes": None,
        "produced_outputs": "driver.c and Twister output"}), 201, "run close")
    if run.get("kind") != "individual":
        raise AssertionError("Measured Run was not an individual Run")
    return {"run": run, "task": task, "case": case, "campaign": campaign,
            "model": model, "provider": provider, "harness": harness}


def publish_run(reviewer, campaign, run_id):
    """Close the campaign for review, then publish the chosen Run as reviewer.

    A Run may only be corrected/withdrawn once it is part of a real effective
    publication, so the fixture must go through the same publication path a real
    reviewer uses. The campaign revision advances as sessions are recorded, so
    the current revision is re-read before the close transition.
    """
    current = assert_api(api_call(reviewer, "GET",
        "campaigns/" + campaign["id"]), 200, "campaign read")
    current = current.get("campaign", current)
    closed = assert_api(api_call(reviewer, "POST",
        "campaigns/" + campaign["id"] + "/actions/close",
        {"expected_revision": current["revision"]}), 200, "campaign close")
    campaign = closed.get("campaign", closed)
    assert_api(api_call(reviewer, "POST",
        "campaigns/" + campaign["id"] + "/publication/publish",
        {"expected_revision": campaign["revision"], "run_ids": [run_id],
         "removal_reason": ""}), 200, "campaign publish")
    return campaign


def run_correction_withdrawal(browser, base_url, creds, artifacts, viewport):
    """UX-R04 (#123 bead ai-w3x.12): real published-Run correction + withdrawal.

    Proves in Chromium, over a Run built from real measured evidence, that only
    the authenticated reviewer may amend it, that a correction commits an
    immutable new revision carrying only the changed measurement, that a stale
    expected_revision is refused (409, never applied), and that withdrawal
    supersedes the publication while the original Run revision stays readable.
    """
    suffix = secrets.token_hex(3)
    writer_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    reviewer_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    writer = writer_context.new_page(); writer.set_default_timeout(30000)
    errors = []
    writer.on("pageerror", lambda e: errors.append(str(e)))
    try:
        sign_in(writer, base_url, creds["workgroup"])
        fixture = build_measured_run(writer, suffix, "UX-R04 amend")
        run = fixture["run"]
        identifier, revision = run["id"], run["revision"]

        # A Run is amendable only once it is part of a real effective
        # publication, so the reviewer publishes it first through the same
        # campaign close + publish path a real reviewer uses.
        reviewer = reviewer_context.new_page(); reviewer.set_default_timeout(30000)
        reviewer.on("pageerror", lambda e: errors.append(str(e)))
        sign_in(reviewer, base_url, creds["reviewer"])
        publish_run(reviewer, fixture["campaign"], identifier)

        # A writable non-reviewer must be refused the lifecycle action...
        refused = api_call(writer, "POST",
            "runs/" + identifier + "/actions/corrected",
            {"expected_revision": revision, "reason": "writer cannot review",
             "metrics_patch": {"quality_score": 70}})
        if refused["status"] != 403:
            raise AssertionError(
                "A non-reviewer was allowed to correct a published Run: " +
                str(refused["status"]))
        # ...and the UI must not offer it either.
        writer.goto(base_url +
                    "/?mode=server&workspace=workgroup&section=results&view=editor",
                    wait_until="domcontentloaded")
        writer.locator("#server-results").wait_for(state="visible", timeout=30000)
        writer.wait_for_timeout(1200)
        if writer.locator('button[data-amend-run="' + identifier + '"]').count():
            raise AssertionError("A non-reviewer was offered the Run amend action")

        # The reviewer corrects one measurement, giving a mandatory reason.
        reviewer.goto(base_url +
                      "/?mode=server&workspace=workgroup&section=results&view=editor",
                      wait_until="domcontentloaded")
        reviewer.locator("#server-results").wait_for(state="visible", timeout=30000)
        amend_button = reviewer.locator(
            'button[data-amend-run="' + identifier + '"]')
        amend_button.wait_for(state="visible", timeout=30000)
        amend_button.click()
        detail = reviewer.locator("#results-detail")
        detail.wait_for(state="visible", timeout=20000)
        # A correction with no measurement/outcome change must be refused
        # client-side, through the shared status presentation.
        reviewer.locator("#run-amend-action").select_option("corrected")
        reviewer.locator("#run-amend-reason").fill(
            "A sufficiently long justification that changes nothing measurable")
        reviewer.locator("#run-amend-save").click()
        reviewer.locator("#results-status").get_by_text(
            "specify at least one", exact=False).wait_for(
                state="visible", timeout=20000)
        # A stale expected_revision must be refused by the Server (409).
        stale = api_call(reviewer, "POST",
            "runs/" + identifier + "/actions/corrected",
            {"expected_revision": "r000", "reason": "stale correction attempt",
             "metrics_patch": {"quality_score": 91}})
        if stale["status"] != 409:
            raise AssertionError(
                "Stale Run correction was not refused with 409: " +
                str(stale["status"]))
        # The real correction commits an immutable new revision.
        reviewer.locator("#run-amend-quality").fill("91")
        reviewer.locator("#run-amend-save").click()
        reviewer.locator("#results-status").get_by_text(
            "committed", exact=False).wait_for(state="visible", timeout=30000)
        amended = assert_api(api_call(reviewer, "GET",
            "runs/" + identifier + "/revisions"), 200, "run revisions")
        if amended["current"]["revision"] == revision:
            raise AssertionError("Correction did not advance the Run revision")
        if len(amended["revisions"]) < 2:
            raise AssertionError("Correction did not record an immutable revision")
        new_revision = amended["current"]["revision"]
        capture(reviewer, artifacts,
                "server-run-corrected-" + str(viewport["width"]))

        # Persistence: a full browser reload must re-render the corrected
        # revision from PostgreSQL, not a cached pre-correction value.
        reviewer.goto(base_url +
                      "/?mode=server&workspace=workgroup&section=results&view=editor",
                      wait_until="domcontentloaded")
        reviewer.locator("#server-results").wait_for(state="visible", timeout=30000)
        reviewer.locator(
            'button[data-amend-run="' + identifier + '"]').first.wait_for(
                state="visible", timeout=30000)
        confirmed = assert_api(api_call(reviewer, "GET",
            "runs/" + identifier + "/revisions"), 200, "run revisions after reload")
        if confirmed["current"]["revision"] != new_revision:
            raise AssertionError(
                "Corrected Run revision did not survive a browser reload")

        # Withdrawal supersedes the publication; history keeps the original.
        reviewer.goto(base_url +
                      "/?mode=server&workspace=workgroup&section=results&view=editor",
                      wait_until="domcontentloaded")
        reviewer.locator("#server-results").wait_for(state="visible", timeout=30000)
        withdraw_button = reviewer.locator(
            'button[data-amend-run="' + identifier + '"]').first
        withdraw_button.wait_for(state="visible", timeout=30000)
        withdraw_button.click()
        reviewer.locator("#results-detail").wait_for(state="visible", timeout=20000)
        reviewer.locator("#run-amend-action").select_option("withdrawn")
        reviewer.locator("#run-amend-reason").fill(
            "Provenance of the retained raw log is invalid; withdraw the Run")
        reviewer.once("dialog", lambda dialog: dialog.accept())
        reviewer.locator("#run-amend-save").click()
        reviewer.locator("#results-status").get_by_text(
            "committed", exact=False).wait_for(state="visible", timeout=30000)
        after = assert_api(api_call(reviewer, "GET",
            "runs/" + identifier + "/revisions"), 200, "run revisions after withdraw")
        if after["current"]["status"] != "withdrawn":
            raise AssertionError(
                "Withdraw did not supersede the Run publication: " +
                str(after["current"]["status"]))
        if not after["revisions"]:
            raise AssertionError("Withdraw erased the immutable Run revision history")
        assert_exactly_one_view(reviewer, "#ux-screen-host > [data-ux-screen]")
        assert_no_horizontal_overflow(reviewer)
        capture(reviewer, artifacts,
                "server-run-withdrawn-" + str(viewport["width"]))
        if errors:
            raise AssertionError("Run amendment JS error(s): " + "; ".join(errors[:3]))
        return {"run": identifier}
    finally:
        writer_context.close()
        reviewer_context.close()


def test_case_fork_and_denial(browser, base_url, creds, artifacts, viewport):
    """UX-R04 (#123 bead ai-w3x.12): Test Case fork, evidence and denial.

    Proves in Chromium/real-API that a fork records an immutable source revision
    and a child version that survives a reload, that a real evidence blob lands
    attributed to the exact source revision, and that an Engineer (business_read
    only) is denied the fork editor, the evidence upload and any Task write
    without another mode being substituted.
    """
    suffix = secrets.token_hex(3)
    writer_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    engineer_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    writer = writer_context.new_page(); writer.set_default_timeout(30000)
    errors = []
    writer.on("pageerror", lambda e: errors.append(str(e)))
    try:
        sign_in(writer, base_url, creds["workgroup"])
        task = assert_api(api_call(writer, "POST", "tasks", {
            "name": "UX-R04 fork task " + suffix,
            "properties": {"phase": "SWE", "domain": "Embedded",
                           "criteria": "Fork lineage fixture"}}), 201, "task")
        case = assert_api(api_call(writer, "POST", "test-cases", {
            "name": "UX-R04 fork case " + suffix, "task_id": task["id"],
            "properties": {"objective": "probe", "inputs": "none",
                           "expected_outputs": "none", "dod": "probe DoD"}}),
            201, "test case")
        source_revision = case["revision"]

        writer.goto(base_url +
                    "/?mode=server&workspace=workgroup&section=testdesign&view=editor",
                    wait_until="domcontentloaded")
        writer.locator("#server-test-cases").wait_for(state="visible", timeout=30000)
        row = writer.locator('[data-shared-case="' + case["id"] + '"]')
        row.wait_for(state="visible", timeout=30000)
        # Fork through the real UI: the editor names the immutable source revision.
        row.locator('button[data-action="fork"]').click()
        editor = writer.locator("#case-editor")
        editor.wait_for(state="visible", timeout=20000)
        if source_revision not in editor.inner_text():
            raise AssertionError("Fork editor did not pin the source revision")
        editor.locator('input[name="name"]').fill(case["name"] + " (fork)")
        editor.get_by_role("button", name="Save fork").click()
        writer.locator("#case-status").get_by_text("Saved", exact=False).wait_for(
            state="visible", timeout=30000)

        forked = assert_api(api_call(writer, "GET",
            "test-cases/" + case["id"] + "/revisions"), 200, "case revisions")
        if not forked.get("revisions"):
            raise AssertionError("Fork did not expose the immutable case history")
        # Persistence: the fork lineage must survive a full browser reload and
        # a fresh list fetch (the child is rendered as a fork of its source).
        writer.goto(base_url +
                    "/?mode=server&workspace=workgroup&section=testdesign&view=editor",
                    wait_until="domcontentloaded")
        writer.locator("#server-test-cases").wait_for(state="visible", timeout=30000)
        fork_row = writer.locator('[data-shared-case]').filter(
            has_text="(fork)").first
        fork_row.wait_for(state="visible", timeout=30000)
        if "Fork" not in fork_row.inner_text():
            raise AssertionError("Fork lineage was lost after a browser reload")
        capture(writer, artifacts,
                "server-test-case-fork-" + str(viewport["width"]))

        # Evidence: a real attachment lands through the authorized API and is
        # attributed to the exact source revision.
        uploaded = upload_evidence(writer, case["id"],
                                   "ux-r04-" + suffix + ".txt",
                                   "original measured harness output", source_revision)
        if uploaded["status"] != 201:
            raise AssertionError("Evidence upload was not accepted: " +
                                 str(uploaded["status"]))
        linked = assert_api(api_call(writer, "GET",
            "catalog/items/" + case["id"] + "/evidence"), 200, "case evidence")
        if not linked.get("results"):
            raise AssertionError("Uploaded Test Case evidence is not listed")
        # The exact source revision carries the attachment.
        if not any(row.get("revision") == source_revision
                   for row in linked["results"]):
            raise AssertionError(
                "Evidence was not attributed to the exact source revision")

        # An Engineer (business_read only) must be denied the fork editor,
        # the evidence upload and any Task write, and handed nothing else.
        engineer = engineer_context.new_page(); engineer.set_default_timeout(30000)
        engineer.on("pageerror", lambda e: errors.append(str(e)))
        sign_in(engineer, base_url, creds["engineer"])
        engineer.goto(base_url + "/?mode=server&workspace=engineer&section=tasks",
                      wait_until="domcontentloaded")
        engineer.locator('#ux-screen-host[data-ux-current]').wait_for(
            state="visible", timeout=30000)
        engineer.wait_for_timeout(1200)
        if engineer.locator("#server-test-cases").is_visible() or \
                engineer.locator('button[data-action="fork"]').count():
            raise AssertionError("Engineer reached the Test Case fork editor")
        # No write affordance is offered on the shared Task tree either.
        if engineer.locator('#server-task-list button[data-task-action="up"], '
                            '#server-task-list button[data-task-action="edit"]').count():
            raise AssertionError("Engineer was offered a Task write affordance")
        # The evidence upload API must be refused for a read-only Engineer.
        denied = upload_evidence(engineer, case["id"], "denied.txt",
                                  "unauthorized", source_revision)
        if denied["status"] not in (403, 404):
            raise AssertionError(
                "Engineer was allowed to attach Test Case evidence: " +
                str(denied["status"]))
        assert_exactly_one_view(engineer, "#ux-screen-host > [data-ux-screen]")
        capture(engineer, artifacts,
                "server-test-case-fork-denied-" + str(viewport["width"]))
        if errors:
            raise AssertionError("Fork/denial JS error(s): " + "; ".join(errors[:3]))
        return {"case": case["id"]}
    finally:
        writer_context.close()
        engineer_context.close()


def recommendation_lifecycle(browser, base_url, creds, artifacts, viewport):
    """UX-R04: Server-only Recommendation review/withdraw lifecycle, end to end.

    Builds a real individual measured Run through the public REST API (no Django
    seed command — business fixtures are forbidden there), drafts a
    Recommendation over it, then proves in Chromium that only the authenticated
    reviewer may publish it with an explicit justification and later withdraw it,
    that the shared detail re-renders the new revision, and that a writable
    non-reviewer is never offered the transition.
    """
    suffix = secrets.token_hex(3)
    # The writer and the reviewer are different real identities: they must not
    # share a BrowserContext, whose cookie jar is the session. One context per
    # persona keeps their Server sessions independent, exactly as two operators
    # in two browsers would be.
    writer_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    reviewer_context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    writer = writer_context.new_page()
    writer.set_default_timeout(30000)
    errors = []
    writer.on("pageerror", lambda e: errors.append(str(e)))
    try:
        # --- Real measured evidence through the authenticated API -----------
        sign_in(writer, base_url, creds["workgroup"])
        model = assert_api(api_call(writer, "POST", "models", {
            "name": "UX-R04 review model " + suffix, "properties": {}}), 201, "model")
        provider = assert_api(api_call(writer, "POST", "catalog/provider", {
            "name": "UX-R04 review provider " + suffix, "properties": {}}), 201, "provider")
        harness = assert_api(api_call(writer, "POST", "catalog/harness", {
            "name": "UX-R04 review harness " + suffix,
            "properties": {"osWindows": True}}), 201, "harness")
        task = assert_api(api_call(writer, "POST", "tasks", {
            "name": "UX-R04 review task " + suffix,
            "properties": {"phase": "SWE", "domain": "Embedded",
                           "criteria": "Disposable lifecycle fixture"}}), 201, "task")
        case = assert_api(api_call(writer, "POST", "test-cases", {
            "name": "UX-R04 review case " + suffix, "task_id": task["id"],
            "properties": {"objective": "probe", "inputs": "none",
                           "expected_outputs": "none", "dod": "probe DoD"}}),
            201, "test case")
        campaign = assert_api(api_call(writer, "POST", "campaigns", {
            "name": "UX-R04 review campaign " + suffix,
            "objective": "produce one real individual measured Run",
            "mode": "task_centred", "task_id": task["id"],
            "test_case_ids": [case["id"]]}), 201, "campaign")
        started = assert_api(api_call(writer, "POST",
            "campaigns/" + campaign["id"] + "/actions/start",
            {"expected_revision": campaign["revision"]}), 200, "campaign start")
        session = assert_api(api_call(writer, "POST",
            "campaigns/" + campaign["id"] + "/sessions", {
                "test_case_id": case["id"],
                "component_ids": {"model": model["id"], "provider": provider["id"],
                                  "harness": harness["id"]},
                "settings": {"nullable": None}, "configuration_version": "1",
                "properties": {"tool": "shell"}}), 201, "session")
        assert_api(api_call(writer, "POST", "sessions/" + session["id"] + "/interactions", {
            "expected_revision": session["revision"], "type": "human_prompt",
            "content": "Create SPI driver", "human_minutes": 3, "agent_minutes": None,
            "extensions": {"unknown": None}}), 200, "interaction")
        run = assert_api(api_call(writer, "POST", "sessions/" + session["id"] + "/close", {
            "expected_revision": "r002", "outcome": "accepted", "quality_score": 82,
            "quality_evaluation": "Regression passed", "information_utility_score": None,
            "tokens_count": None, "tokens_multiplier": 1, "cost_mode": "flat_rate",
            "cost_eur": None, "human_review_minutes": None,
            "human_correction_minutes": None,
            "produced_outputs": "driver.c and Twister output"}), 201, "run close")
        if run.get("kind") != "individual":
            raise AssertionError("Measured Run was not an individual Run")
        record = assert_api(api_call(writer, "POST", "recommendations", {
            "name": "UX-R04 review recommendation " + suffix,
            "task_id": task["id"], "solution_id": run["solution_id"],
            "run_ids": [run["id"]],
            "properties": {"decision": "recommended",
                           "rationale": "Controlled Twister run passed",
                           "limitations": "Single scenario"}}), 201, "recommendation")

        # --- The writer drafts and submits; it may NOT publish --------------
        # The Run's created_at must be strictly later than the campaign start
        # (the publication freshness baseline), so this same Run is never later
        # mis-read as evidence that appeared *after* publication.
        time.sleep(1.1)
        assert_api(api_call(writer, "POST",
            "recommendations/" + record["id"] + "/actions/submit",
            {"expected_revision": record["revision"]}), 200, "submit")
        refused = api_call(writer, "POST",
            "recommendations/" + record["id"] + "/actions/publish",
            {"expected_revision": "r002", "review_note": "writer cannot review"})
        if refused["status"] != 403:
            raise AssertionError(
                "A non-reviewer was allowed to publish a recommendation: " +
                str(refused["status"]))

        # The shared list must not offer the review transitions to a writer.
        writer.goto(base_url +
                    "/?mode=server&workspace=workgroup&section=recommendations&view=editor",
                    wait_until="domcontentloaded")
        list_row = writer.locator(
            '[data-business-domain="recommendations"] [data-business-record]').filter(
                has_text="UX-R04 review recommendation " + suffix).first
        list_row.wait_for(state="visible", timeout=30000)
        if list_row.locator('button[data-action="publish"], '
                            'button[data-action="unpublish"]').count():
            raise AssertionError("A non-reviewer was offered a review transition")

        # --- The reviewer publishes with an explicit justification ----------
        reviewer = reviewer_context.new_page()
        reviewer.set_default_timeout(30000)
        reviewer.on("pageerror", lambda e: errors.append(str(e)))
        sign_in(reviewer, base_url, creds["reviewer"])
        reviewer.goto(base_url +
                      "/?mode=server&workspace=workgroup&section=recommendations&view=editor",
                      wait_until="domcontentloaded")
        review_row = reviewer.locator(
            '[data-business-domain="recommendations"] [data-business-record]').filter(
                has_text="UX-R04 review recommendation " + suffix).first
        review_row.wait_for(state="visible", timeout=30000)
        publish = review_row.locator('button[data-action="publish"]').first
        publish.wait_for(state="visible", timeout=20000)
        # The reviewer is prompted for an explicit, non-empty justification.
        reviewer.once("dialog", lambda dialog: dialog.accept(
            "Reviewed the original measured Run; one authorized decision"))
        publish.click()
        # The controller re-fetches the list and reports the recorded transition
        # ("Recommendation publish action recorded…"); the shared status only
        # flips once that attributable confirmation lands.
        reviewer.locator("#rec-status").get_by_text(
            "publish action recorded", exact=False).wait_for(
                state="visible", timeout=30000)
        # The shared detail projection re-renders the new immutable revision.
        review_row = reviewer.locator(
            '[data-business-domain="recommendations"] [data-business-record]').filter(
                has_text="UX-R04 review recommendation " + suffix).first
        review_row.locator('button[data-action="history"]').first.click()
        detail = reviewer.locator(
            '[data-shared-domain-detail="recommendations"][data-domain-mode="server"]')
        detail.wait_for(state="visible", timeout=30000)
        if "Immutable, attributable publication history" not in detail.inner_text():
            raise AssertionError("Published recommendation lost its shared detail projection")
        if "r003" not in detail.inner_text():
            raise AssertionError("Shared detail did not re-render the published r003 revision")
        assert_no_horizontal_overflow(reviewer)
        capture(reviewer, artifacts,
                "server-recommendation-published-" + str(viewport["width"]))

        # --- The reviewer withdraws it with a justification -----------------
        review_row = reviewer.locator(
            '[data-business-domain="recommendations"] [data-business-record]').filter(
                has_text="UX-R04 review recommendation " + suffix).first
        withdraw = review_row.locator('button[data-action="unpublish"]').first
        withdraw.wait_for(state="visible", timeout=20000)
        reviewer.once("dialog", lambda dialog: dialog.accept(
            "New failed evidence invalidates the prior qualification"))
        withdraw.click()
        reviewer.locator("#rec-status").get_by_text(
            "unpublish action recorded", exact=False).wait_for(
                state="visible", timeout=30000)
        # A rejected review (empty justification) must be refused client-side.
        review_row.locator('button[data-action="history"]').first.click()
        detail = reviewer.locator(
            '[data-shared-domain-detail="recommendations"][data-domain-mode="server"]')
        detail.wait_for(state="visible", timeout=30000)
        if "r004" not in detail.inner_text():
            raise AssertionError("Shared detail did not re-render the withdrawn r004 revision")
        assert_exactly_one_view(reviewer, "#ux-screen-host > [data-ux-screen]")
        assert_no_horizontal_overflow(reviewer)
        capture(reviewer, artifacts,
                "server-recommendation-withdrawn-" + str(viewport["width"]))
        if errors:
            raise AssertionError("Recommendation lifecycle JS error(s): " + "; ".join(errors[:3]))
        return {"recommendation": record["id"], "run": run["id"]}
    finally:
        writer_context.close()
        reviewer_context.close()
# --- UX-R05 (#124): draft resume, Run stepper, conflict and Run ownership ----

def _demo_counts(page):
    return page.evaluate("""() => ({campaigns: db.campaigns.length,
        trials: db.campaignTrials.length, runs: db.runs.length})""")


def demo_draft_stepper_journey(browser, demo_url, artifacts, viewport):
    """Fictional Demo: unsaved campaign/step drafts and one explicit Run close."""
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    page.set_default_timeout(15000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    try:
        page.goto(demo_url + "?mode=demo&workspace=workgroup", wait_until="domcontentloaded")
        page.locator('[data-act="login"][data-id="u1"]').click()
        page.locator(".app").wait_for(state="visible", timeout=20000)
        page.locator('[data-act="nav"][data-id="benchmark"]').click()
        before = _demo_counts(page)

        # 1. Unsaved campaign form -> route switch -> Resume restores, Discard writes nothing.
        page.locator('[data-act="newCampaign"]').first.click()
        dialog = page.get_by_role("dialog")
        dialog.wait_for(state="visible")
        dialog.locator('#modalForm [name="title"]').fill("UX-R05 unsaved Demo campaign")
        dialog.locator('#modalForm [name="purpose"]').fill(
            "Unsaved local draft survives a route switch without a Server-like write")
        assert_no_horizontal_overflow(page)
        capture(page, artifacts, "demo-uxr05-campaign-draft-" + str(viewport["width"]))
        dialog.get_by_role("button", name="Close dialog").click()
        dialog.wait_for(state="hidden")
        page.locator('[data-act="nav"][data-id="knowledge"]').click()
        page.locator('[data-act="nav"][data-id="benchmark"]').click()
        page.locator('[data-act="newCampaign"]').first.click()
        dialog = page.get_by_role("dialog")
        dialog.wait_for(state="visible")
        banner = dialog.locator('[data-draft-banner="campaign"]')
        banner.wait_for(state="visible", timeout=10000)
        text = banner.inner_text()
        if "Unsaved draft on this device" not in text or "not saved" not in text:
            raise AssertionError("Demo did not offer an explicit resume of the campaign draft: " + text[:200])
        if dialog.locator('#modalForm [name="title"]').input_value() != "":
            raise AssertionError("An incompatible or unconfirmed draft was applied without Resume")
        capture(page, artifacts, "demo-uxr05-campaign-resume-" + str(viewport["width"]))
        banner.get_by_role("button", name="Resume draft").click()
        if dialog.locator('#modalForm [name="title"]').input_value() != "UX-R05 unsaved Demo campaign":
            raise AssertionError("Resume did not restore the unsaved Demo campaign fields")
        if _demo_counts(page) != before:
            raise AssertionError("Resuming a local Demo draft wrote a business record")
        dialog.get_by_role("button", name="Close dialog").click()
        dialog.wait_for(state="hidden")
        # Reopen and explicitly discard: neither action may write a business record.
        page.locator('[data-act="newCampaign"]').first.click()
        dialog = page.get_by_role("dialog")
        dialog.wait_for(state="visible")
        banner = dialog.locator('[data-draft-banner="campaign"]')
        banner.get_by_role("button", name="Discard").click()
        if "Draft discarded" not in banner.inner_text():
            raise AssertionError("Discard did not clear the Demo draft")
        if _demo_counts(page) != before:
            raise AssertionError("Discarding a local Demo draft wrote a business record")
        if page.evaluate("() => Object.keys(localStorage).some(k => k.includes('working-draft'))"):
            raise AssertionError("Discarded Demo draft was not removed from local storage")
        dialog.get_by_role("button", name="Close dialog").click()
        dialog.wait_for(state="hidden")

        # 2. Real Run stepper: setup -> interactions -> results, resumed offline.
        page.locator('[data-business-record="demo_campaign_planned"] button',
                     has_text="Open campaign").click()
        detail = page.get_by_role("dialog")
        detail.wait_for(state="visible")
        detail.locator('[data-act="campaignActivate"]').click()
        detail.locator('[data-act="campaignNewCase"]').click()
        case_form = page.get_by_role("dialog")
        case_form.wait_for(state="visible")
        case_form.locator('#modalForm [name="title"]').fill("UX-R05 stepper challenge")
        case_form.locator('#modalForm [name="objective"]').fill("Verify the Run stepper")
        case_form.locator('#modalForm [name="dod"]').fill("Finalize exactly once")
        case_form.locator(".modal-footer button[type=submit]").click()
        case_form.locator('[data-act="campaignStartTrial"]').first.wait_for(
            state="visible", timeout=15000)
        case_form.locator('[data-act="campaignStartTrial"]').first.click()
        setup = page.get_by_role("dialog")
        setup.wait_for(state="visible")
        for kind in ("modelComponent", "providerComponent", "harnessComponent"):
            options = [value for value in page.eval_on_selector_all(
                f'#modalForm [name={kind}] option', "els => els.map(e => e.value)") if value]
            if options:
                setup.locator(f'#modalForm [name="{kind}"]').select_option(options[0])
        setup.locator('#modalForm [name="configuration"]').fill("model=alpha; harness=beta")
        setup.locator('#modalForm [name="installationGuide"]').select_option("guide_install_mock")
        setup.locator('#modalForm [name="setupMinutes"]').fill("30")
        # Keep this Run on the legacy manual-cost path so the results step stays
        # focused on draft/stepper behaviour instead of the fictional tariff example.
        setup.locator('#modalForm [name="tariffPlan"]').fill("")
        before_setup = _demo_counts(page)
        setup.locator(".modal-footer button[type=submit]").click()
        interactions = page.get_by_role("dialog")
        interactions.wait_for(state="visible", timeout=15000)
        if "Timed interactions" not in interactions.inner_text():
            raise AssertionError("Saving the setup step did not open the Interactions step")
        after_setup = _demo_counts(page)
        if after_setup["trials"] != before_setup["trials"] + 1:
            raise AssertionError("The setup step did not create exactly one session: " +
                                 json.dumps(after_setup))
        interactions.locator('#modalForm [name="description"]').fill(
            "UNSAVED-UXR05 interaction body")
        interactions.get_by_role("button", name="Close dialog").click()
        interactions.wait_for(state="hidden")
        page.locator('[data-business-record="demo_campaign_planned"] button',
                     has_text="Open campaign").click()
        detail = page.get_by_role("dialog")
        detail.wait_for(state="visible")
        stepper = detail.locator("ol.shared-draft-step[data-trial-steps]")
        stepper.wait_for(state="visible", timeout=15000)
        if stepper.locator('li[aria-current="step"]').inner_text().strip().startswith("2") is False:
            raise AssertionError("Demo Run stepper does not mark the current step")
        capture(page, artifacts, "demo-uxr05-run-stepper-" + str(viewport["width"]))
        detail.locator('[data-act="campaignResumeTrial"]').first.click()
        interactions = page.get_by_role("dialog")
        interactions.wait_for(state="visible")
        interactions_banner = interactions.locator('[data-draft-banner="campaignInteraction"]')
        interactions_banner.wait_for(state="visible", timeout=10000)
        if _demo_counts(page) != after_setup:
            raise AssertionError("Reopening the Run step created a phantom session")
        interactions_banner.get_by_role("button", name="Resume draft").click()
        if interactions.locator('#modalForm [name="description"]').input_value() != \
                "UNSAVED-UXR05 interaction body":
            raise AssertionError("Resume did not restore the unsaved Run interaction input")
        count_after_resume = _demo_counts(page)
        if count_after_resume != after_setup:
            raise AssertionError("Resuming unsaved Run input wrote a session or Run")

        # 3. Finish the Run once and confirm no duplicate Run appears.
        interactions.locator(".modal-footer button[type=submit]").click()
        interactions.wait_for(state="visible", timeout=15000)
        interactions.locator('[data-act="campaignFinishIterations"]').click()
        outcome = page.get_by_role("dialog")
        outcome.wait_for(state="visible")
        outcome.locator('#modalForm [name="score"]').fill("72")
        outcome.locator('#modalForm [name="utility"]').fill("64")
        outcome.locator('#modalForm [name="reviewMinutes"]').fill("5")
        outcome.locator('#modalForm [name="correctionMinutes"]').fill("2")
        outcome.locator('#modalForm [name="outputDocuments"]').fill(
            "UX-R05 produced driver diff and test log")
        outcome.locator('#modalForm [name="costMode"]').select_option("amount")
        outcome.locator('#modalForm [name="cost"]').fill("12")
        runs_before = count_after_resume["runs"]
        outcome.locator(".modal-footer button[type=submit]").click()
        page.wait_for_timeout(1200)
        final = _demo_counts(page)
        if final["runs"] != runs_before + 1:
            raise AssertionError("Run was not finalized exactly once: " + json.dumps(final))
        capture(page, artifacts, "demo-uxr05-run-finalized-" + str(viewport["width"]))
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        reloaded = _demo_counts(page)
        if reloaded["runs"] != runs_before + 1:
            raise AssertionError("Reload duplicated a finalized Demo Run: " + json.dumps(reloaded))
        if errors:
            raise AssertionError("Demo JS runtime error(s): " + "; ".join(errors[:3]))
        return {"draft_resume": True, "run_steps": "setup→interactions→results",
                "runs_without_duplicate": 1}
    finally:
        context.tracing.stop(path=str(artifacts / ("demo-uxr05-" + str(viewport["width"]) + ".zip")))
        context.close()


# Fixture creation runs through the real authenticated API inside the browser
# session, so every object used by the UX-R05 journeys is a genuine Django record.
SERVER_FIXTURE_JS = r"""async () => {
  const csrf = () => document.cookie.split('; ')
    .find(c => c.startsWith('csrftoken=')).split('=')[1];
  const call = async (path, method, body) => {
    const r = await fetch('/api/v1/' + path, {method: method || 'GET', credentials: 'same-origin',
      cache: 'no-store',
      headers: method && method !== 'GET' ? {'Content-Type': 'application/json',
        'X-CSRFToken': csrf()} : {},
      body: method && method !== 'GET' ? JSON.stringify(body) : undefined});
    let data = null;
    try { data = await r.json(); } catch (e) { data = null; }
    return {status: r.status, data: data};
  };
  const stamp = String(Date.now()).slice(-6);
  const kinds = ['model', 'provider', 'harness'];
  const comps = {};
  for (const kind of kinds) {
    const res = await call(kind === 'model' ? 'models' : 'catalog/' + kind, 'POST',
      {name: 'UXR05 ' + kind + ' ' + stamp, properties: {}});
    if (res.status !== 201) return {error: 'component ' + kind + ' ' + res.status};
    comps[kind] = res.data.id || res.data.item.id;
  }
  const offers = {};
  for (const kind of kinds) {
    const res = await call('pricing/offers', 'POST', {name: 'UXR05 offer ' + kind + ' ' + stamp,
      properties: {component_id: comps[kind], billing_owner: kind + '-owner', currency: 'EUR',
        source: 'https://example.invalid/uxr05', checked_on: '2026-10-11', status: 'active',
        effective_from: null, effective_to: null,
        lines: [{charge_id: kind + '-tokens', family: 'token', charge_type: 'variable',
          meter: 'input_tokens', unit_size: 1000000, rate: '2.500'}]}});
    if (res.status !== 201) return {error: 'offer ' + kind + ' ' + res.status};
    offers[kind] = res.data;
  }
  const task = await call('tasks', 'POST', {name: 'UXR05 draft task ' + stamp, properties: {}});
  if (task.status !== 201) return {error: 'task ' + task.status};
  const testCase = await call('test-cases', 'POST', {name: 'UXR05 draft challenge ' + stamp,
    task_id: task.data.id, properties: {objective: 'Verify drafts and stepper',
      dod: 'One Run, never a phantom session'}});
  if (testCase.status !== 201) return {error: 'case ' + testCase.status};
  const selection = kind => ({source_key: 'root:' + kind, component_id: comps[kind],
    offer_id: offers[kind].id, offer_revision_id: offers[kind].revision_id});
  const campaign = await call('campaigns', 'POST', {name: 'UXR05 draft campaign ' + stamp,
    objective: 'Verify conflict-safe concurrent editing', mode: 'solution_centred',
    method_version: 1, component_ids: comps, test_case_ids: [testCase.data.id],
    configuration: {}, pricing_selections: kinds.map(selection)});
  if (campaign.status !== 201) return {error: 'campaign ' + campaign.status};
  const row = campaign.data.campaign || campaign.data;
  const started = await call('campaigns/' + row.id + '/actions/start', 'POST',
    {expected_revision: row.revision});
  if (started.status !== 200) return {error: 'start ' + started.status};
  const session = await call('campaigns/' + row.id + '/sessions', 'POST',
    {test_case_id: testCase.data.id});
  if (session.status !== 201) return {error: 'session ' + session.status +
    ' ' + JSON.stringify(session.data)};
  return {campaign: row.id, session: session.data.id, case: testCase.data.id,
    task: task.data.id, owner: 'alice', stamp: stamp};
}"""


def _server_login(page, base_url, creds, role, path="/?mode=server&workspace=workgroup"):
    page.goto(base_url + path, wait_until="domcontentloaded")
    page.locator("#server-login-form").wait_for(state="visible", timeout=25000)
    page.locator("#server-username").fill(creds[role]["username"])
    page.locator("#server-password").fill(creds[role]["password"])
    page.get_by_role("button", name="Sign in to Server").click()
    page.locator('#ux-screen-host[data-ux-current]').wait_for(state="visible", timeout=25000)
    page.locator("#server-login-form").wait_for(state="hidden", timeout=25000)


def _row(payload):
    """Campaign reads may be returned directly or wrapped in {campaign: ...}."""
    if isinstance(payload, dict) and isinstance(payload.get("campaign"), dict):
        return payload["campaign"]
    return payload


def _api(page, path, method="GET", body=None):
    return page.evaluate("""async ({path, method, body}) => {
      const csrf = () => document.cookie.split('; ')
        .find(c => c.startsWith('csrftoken=')).split('=')[1];
      const r = await fetch('/api/v1/' + path, {method, credentials: 'same-origin',
        cache: 'no-store',
        headers: method !== 'GET' ? {'Content-Type': 'application/json',
          'X-CSRFToken': csrf()} : {},
        body: method !== 'GET' ? JSON.stringify(body || {}) : undefined});
      let data = null;
      try { data = await r.json(); } catch (e) { data = null; }
      return {status: r.status, data: data};
    }""", {"path": path, "method": method, "body": body})


def server_draft_stepper_conflict_journey(browser, base_url, creds, artifacts, viewport):
    """Real Server: local Run/step draft, 409 conflict retention and Run ownership."""
    alice = browser.new_context(viewport=viewport, reduced_motion="reduce")
    bob = browser.new_context(viewport=viewport, reduced_motion="reduce")
    page_a = alice.new_page(); page_b = bob.new_page()
    for page in (page_a, page_b):
        page.set_default_timeout(15000)
    errors = []
    page_a.on("pageerror", lambda e: errors.append("alice:" + str(e)))
    page_b.on("pageerror", lambda e: errors.append("bob:" + str(e)))
    writes = []
    page_a.on("request", lambda r: writes.append(r.method + " " + r.url)
              if r.method in ("POST", "PATCH") and "/api/v1/sessions/" in r.url else None)
    traced = False
    try:
        _server_login(page_a, base_url, creds, "workgroup",
                      "/?mode=server&workspace=workgroup&section=benchmark&view=editor")
        _server_login(page_b, base_url, creds, "multi_role",
                      "/?mode=server&workspace=workgroup&section=benchmark&view=editor")
        alice.tracing.start(screenshots=True, snapshots=True, sources=True)
        bob.tracing.start(screenshots=True, snapshots=True, sources=True)
        traced = True
        fixtures = page_a.evaluate(SERVER_FIXTURE_JS)
        if fixtures.get("error"):
            raise AssertionError("Real Server fixture creation failed: " + fixtures["error"])
        campaign, session = fixtures["campaign"], fixtures["session"]

        # 1. The Server Run stepper is local-only: no checkpoint on navigation.
        page_a.goto(base_url + "/?mode=server&workspace=workgroup&section=benchmark&view=editor",
                    wait_until="domcontentloaded")
        page_a.locator(f'[data-id="{campaign}"][data-action="sessions"]').wait_for(
            state="visible", timeout=30000)
        page_a.locator(f'[data-id="{campaign}"][data-action="sessions"]').click()
        page_a.locator(f'[data-open-session="{session}"]').wait_for(state="visible", timeout=30000)
        page_a.locator(f'[data-open-session="{session}"]').click()
        stepper = page_a.locator("#session-stepper")
        stepper.wait_for(state="visible", timeout=30000)
        steps = stepper.locator("[data-session-goto]")
        if steps.count() < 3:
            raise AssertionError("Server Run stepper lacks sequential steps")
        panels = page_a.locator("[data-session-panel]")
        visible = page_a.locator("[data-session-panel]:not([hidden])")
        writes.clear()
        for index in range(steps.count()):
            steps.nth(index).click()
            if visible.count() != 1:
                raise AssertionError("Exactly one Run step panel must be visible")
        if writes:
            raise AssertionError("Step navigation wrote checkpoints: " + str(writes[:2]))
        capture(page_a, artifacts, "server-uxr05-run-stepper-" + str(viewport["width"]))

        # 2. Unsaved step input survives leaving the screen and is resumed explicitly.
        steps.filter(has_text="Interactions").first.click()
        page_a.locator("#session-interaction [name=content]").fill(
            "UXR05 unsaved interaction content")
        page_a.goto(base_url + "/?mode=server&workspace=workgroup&section=guides&view=editor",
                    wait_until="domcontentloaded")
        page_a.goto(base_url + "/?mode=server&workspace=workgroup&section=benchmark&view=editor",
                    wait_until="domcontentloaded")
        page_a.locator(f'[data-id="{campaign}"][data-action="sessions"]').wait_for(
            state="visible", timeout=30000)
        page_a.locator(f'[data-id="{campaign}"][data-action="sessions"]').click()
        page_a.locator(f'[data-open-session="{session}"]').click()
        banner = page_a.locator('[data-draft-banner="session"]')
        banner.wait_for(state="visible", timeout=30000)
        if "Unsaved draft on this device" not in banner.inner_text():
            raise AssertionError("Server Run draft was not offered for resume")
        if page_a.locator("#session-interaction [name=content]").input_value() != "":
            raise AssertionError("A Server Run draft was applied without explicit Resume")
        capture(page_a, artifacts, "server-uxr05-run-resume-" + str(viewport["width"]))
        banner.get_by_role("button", name="Resume draft").click()
        if page_a.locator("#session-interaction [name=content]").input_value() != \
                "UXR05 unsaved interaction content":
            raise AssertionError("Resume did not restore the unsaved Server Run input")
        if not page_a.locator('[data-session-panel="interactions"]').is_visible():
            raise AssertionError("Resume did not return to the remembered Run step")

        # 3. Explicit saves: one checkpoint per action, never a duplicate Run.
        before_state = _api(page_a, "sessions/" + session)
        revision_before = before_state["data"]["revision"]
        page_a.locator("#session-stepper [data-session-goto]").filter(has_text="Setup").first.click()
        page_a.locator('[data-session-panel="setup"]').wait_for(state="visible")
        page_a.locator("#session-save-setup").click()
        page_a.wait_for_function(
            "rev => document.getElementById('session-revision').textContent !== rev",
            arg=revision_before, timeout=20000)
        if page_a.locator("#session-interaction [name=content]").input_value() != \
                "UXR05 unsaved interaction content":
            raise AssertionError("Saving one Run step discarded unsaved input in another step")
        page_a.locator("#session-stepper [data-session-goto]").filter(
            has_text="Interactions").first.click()
        page_a.locator("#session-add-interaction").click()
        page_a.wait_for_function(
            "() => document.querySelectorAll('#session-timeline details').length === 1",
            timeout=20000)
        after_state = _api(page_a, "sessions/" + session)
        if len(after_state["data"]["state"]["interactions"]) != 1:
            raise AssertionError("Interaction checkpoint did not persist exactly once")
        sessions_list = _api(page_a, f"campaigns/{campaign}/sessions")
        if len(sessions_list["data"]["results"]) != 1:
            raise AssertionError("Stepper/save flow generated a phantom session")
        runs = _api(page_a, f"runs?campaign_id={campaign}")
        if runs["data"]["results"]:
            raise AssertionError("Step navigation created an unintended Run")

        # 4. A second contributor cannot write alice's active Run, but can start their own.
        page_b.goto(base_url + "/?mode=server&workspace=workgroup&section=benchmark&view=editor",
                    wait_until="domcontentloaded")
        page_b.locator(f'[data-id="{campaign}"][data-action="sessions"]').wait_for(
            state="visible", timeout=30000)
        page_b.locator(f'[data-id="{campaign}"][data-action="sessions"]').click()
        page_b.locator(f'[data-open-session="{session}"]').click()
        page_b.locator("#session-stepper").wait_for(state="visible", timeout=30000)
        checkpoints_before = _api(page_b, "sessions/" + session + "/checkpoints")
        page_b.locator("#session-save-setup").click()
        page_b.locator("#session-status").filter(
            has_text="one experimenter").wait_for(state="visible", timeout=20000)
        checkpoints_after = _api(page_b, "sessions/" + session + "/checkpoints")
        if len(checkpoints_before["data"]["checkpoints"]) != \
                len(checkpoints_after["data"]["checkpoints"]):
            raise AssertionError("A refused co-worker write appended a checkpoint")
        denied = _api(page_b, "sessions/" + session + "/setup", "PATCH",
                      {"expected_revision": after_state["data"]["revision"], "notes": "tamper"})
        if denied["status"] != 403:
            raise AssertionError("Backend accepted a foreign Run write: " +
                                 str(denied["status"]))
        capture(page_b, artifacts, "server-uxr05-run-ownership-" + str(viewport["width"]))
        # Dismiss the promoted Run dialog before starting a separate own session.
        page_b.get_by_role("button", name="Close dialog").click()
        page_b.locator("#session-create").click()
        page_b.wait_for_function(
            "() => document.querySelectorAll('[data-open-session]').length === 2",
            timeout=25000)
        own = _api(page_b, f"campaigns/{campaign}/sessions")
        if len(own["data"]["results"]) != 2:
            raise AssertionError("A co-worker could not start a separate permitted Run session")

        # 5. Concurrent Campaign edit: 409 with the draft intact and no overwrite.
        page_b.goto(base_url + "/?mode=server&workspace=workgroup&section=benchmark&view=editor",
                    wait_until="domcontentloaded")
        page_b.locator(f'[data-id="{campaign}"][data-action="edit"]').wait_for(
            state="visible", timeout=30000)
        page_b.locator(f'[data-id="{campaign}"][data-action="edit"]').click()
        editor = page_b.locator("#campaign-form")
        editor.wait_for(state="visible")
        editor.locator('[name="name"]').fill("UXR05 Bob concurrent edit")
        editor.locator('[name="objective"]').fill("Bob unsaved concurrent change")
        page_b.locator('[data-draft-banner="campaign"]').filter(
            has_text="Unsaved draft on this device").wait_for(state="visible", timeout=10000)
        # Alice commits the newer revision from her own authenticated session.
        page_a.goto(base_url + "/?mode=server&workspace=workgroup&section=benchmark&view=editor",
                    wait_until="domcontentloaded")
        page_a.locator(f'[data-id="{campaign}"][data-action="edit"]').wait_for(
            state="visible", timeout=30000)
        page_a.locator(f'[data-id="{campaign}"][data-action="edit"]').click()
        alice_editor = page_a.locator("#campaign-form")
        alice_editor.wait_for(state="visible")
        alice_name = "UXR05 alice revision " + fixtures["stamp"]
        alice_editor.locator('[name="name"]').fill(alice_name)
        alice_editor.locator('button[type="submit"]').click()
        page_a.locator("#campaign-status").filter(
            has_text="new immutable Server revision").wait_for(state="visible", timeout=25000)
        latest = _api(page_a, "campaigns/" + campaign)
        new_revision = _row(latest["data"])["revision"]
        editor.locator('button[type="submit"]').click()
        notice = page_b.locator(".shared-conflict-notice")
        notice.wait_for(state="visible", timeout=25000)
        text = notice.inner_text()
        for expected in ["changed since you opened it", new_revision, "preserved"]:
            if expected not in text:
                raise AssertionError("409 conflict notice missing " + expected + ": " + text[:240])
        if editor.locator('[name="name"]').input_value() != "UXR05 Bob concurrent edit":
            raise AssertionError("A 409 overwrote the collaborator's unsaved Campaign draft")
        authoritative = _api(page_a, "campaigns/" + campaign)
        if _row(authoritative["data"])["name"] != alice_name:
            raise AssertionError("A stale write replaced the newer Campaign revision")
        capture(page_b, artifacts, "server-uxr05-conflict-" + str(viewport["width"]))
        notice.get_by_role("button", name="Reload latest").click()
        editor = page_b.locator("#campaign-form")
        editor.wait_for(state="visible")
        page_b.wait_for_function(
            "name => document.querySelector('#campaign-form [name=name]').value === name",
            arg=alice_name, timeout=25000)
        if "Copy my unsaved text" not in page_b.locator(
                '[data-draft-banner="campaign"]').inner_text():
            raise AssertionError("Reload latest discarded the unsaved draft without recovery")
        if errors:
            raise AssertionError("Server JS runtime error(s): " + "; ".join(errors[:3]))
        return {"run_stepper": "local-only", "session_checkpoints": 2,
                "conflict": "409 retained draft", "ownership": "creator-only writes"}
    finally:
        if traced:
            alice.tracing.stop(path=str(artifacts / ("server-uxr05-alice-" +
                                                     str(viewport["width"]) + ".zip")))
            bob.tracing.stop(path=str(artifacts / ("server-uxr05-bob-" +
                                                   str(viewport["width"]) + ".zip")))
        alice.close(); bob.close()


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
                run(f"Standalone Demo draft/Run-stepper {width}",
                    lambda v=viewport: demo_draft_stepper_journey(browser, demo_url, directory, v))
                run(f"Standalone Demo workgroup {width}",
                    lambda v=viewport: demo_journey(browser, demo_url, directory, "u1", "workgroup", v))
                run(f"Standalone Demo engineer {width}",
                    lambda v=viewport: demo_journey(browser, demo_url, directory, "u2", "engineer", v))
                run(f"Standalone Demo management {width}",
                    lambda v=viewport: demo_journey(browser, demo_url, directory, "u3", "management", v))
                # UX-R07 §13-07/§13-19: reader/contributor publication boundary in Demo.
                run(f"Standalone Demo publication boundary {width}",
                    lambda v=viewport: demo_checks.demo_publication_boundary(
                        browser, demo_url, directory, v))
                run(f"Authenticated Server draft/stepper/conflict/ownership {width}",
                    lambda v=viewport: server_draft_stepper_conflict_journey(
                        browser, base_url, creds, directory, v))
                run(f"Standalone Demo multi-role persona journeys {width}",
                    lambda v=viewport: demo_persona_journey(browser, demo_url, directory, v))
                for role in ROLES:
                    run(f"Authenticated Server {role} {width}",
                        lambda k=role, v=viewport: server_journey(
                            browser, base_url, creds, directory, k, v))
                # UX-R07 §13-08/§13-17/§13-18: role grants and URL/API fail-closed.
                run(f"Authenticated Server authorization fail-closed {width}",
                    lambda v=viewport: server_checks.server_fail_closed_index(
                        browser, base_url, creds, directory, v))
                # UX-R07 §13-08: one session switches every granted workspace.
                run(f"Authenticated Server multi-role workspace switching {width}",
                    lambda v=viewport: server_checks.server_multirole_switch(
                        browser, base_url, creds, directory, v))
                # UX-R07 §13-07: no internal Watch entry reaches a reader.
                run(f"Authenticated Server publication boundary {width}",
                    lambda v=viewport: server_checks.server_publication_boundary(
                        browser, base_url, creds, directory, v))
                # UX-R07 §13-14: real stale-save 409 keeps the draft, no overwrite.
                run(f"Authenticated Server revision conflict 409 {width}",
                    lambda v=viewport: server_checks.server_revision_conflict(
                        browser, base_url, creds, directory, v))
                # UX-R07 §13-19: an unavailable Server never renders Demo fixtures.
                run(f"Authenticated Server offline isolation {width}",
                    lambda v=viewport: server_checks.server_no_fallback(
                        browser, base_url, creds, directory, v))
                # UX-R07 §13-13/§13-19: the real draft cache never crosses modes/accounts.
                run(f"Demo/Server draft isolation contract {width}",
                    lambda v=viewport: demo_checks.demo_draft_isolation(
                        browser, demo_url, directory, v))
                if "reviewer" in creds:
                    run(f"Server Recommendation review/withdraw lifecycle {width}",
                        lambda v=viewport: recommendation_lifecycle(
                            browser, base_url, creds, directory, v))
                    run(f"Server Run correction/withdrawal {width}",
                        lambda v=viewport: run_correction_withdrawal(
                            browser, base_url, creds, directory, v))
                    run(f"Server Test Case fork + denial {width}",
                        lambda v=viewport: test_case_fork_and_denial(
                            browser, base_url, creds, directory, v))
                # Runs last: it publishes real disposable synthetic evidence.
                run(f"Authenticated Server published persona journeys {width}",
                    lambda v=viewport: server_publication_journey(
                        browser, base_url, creds, directory, v))
                # §13 #4/#17 deep persona journeys on real seeded Server records.
                run(f"Authenticated Server Engineer feedback and Management drill-down {width}",
                    lambda v=viewport: server_persona_deep_journey(
                        browser, base_url, creds, directory, v))
        finally:
            browser.close()
    findings = [finding for record in records
                for finding in (record.get("details") or {}).get("findings", [])
                if isinstance(record.get("details"), dict)]
    report = report_render.build(records, findings, time.monotonic() - start, SUITE)
    report["known_ux_findings"] = debts
    return report_render.write(directory, report)


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
