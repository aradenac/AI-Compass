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
    for item in page.locator('input[type="password"]').all():
        item.fill("")
    page.screenshot(path=str(directory / (name + ".png")), full_page=True,
                    animations="disabled")


def demo_journey(browser, demo_url, artifacts, role, label, viewport):
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
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
        if not page.locator(".content").is_visible():
            raise AssertionError("Demo did not render primary content")
        if api_calls:
            raise AssertionError("Standalone Demo unexpectedly contacted API: " + str(api_calls))
        capture(page, artifacts, "demo-" + label + "-" + str(viewport["width"]))
        if errors:
            raise AssertionError("Demo JS runtime error(s): " + "; ".join(errors[:3]))
    finally:
        context.close()


def server_journey(browser, base_url, creds, artifacts, role, viewport):
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
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
        page.locator("#server-account").wait_for(state="visible", timeout=25000)
        if page.locator("#server-account-name").inner_text() != creds[role]["username"]:
            raise AssertionError("Authenticated user does not match the fixture")
        if role in ("workgroup", "multi_role"):
            page.locator("#server-workgroup-home").wait_for(state="visible", timeout=20000)
        elif role == "engineer":
            page.locator("#server-engineer").wait_for(state="visible", timeout=20000)
        elif role == "management":
            page.locator("#server-management-insights").wait_for(state="visible", timeout=20000)
        elif role == "maintenance":
            page.locator("#server-governance-audit").wait_for(state="visible", timeout=20000)
        capture(page, artifacts, "server-" + role + "-" + str(viewport["width"]))
        if errors:
            raise AssertionError("Server JS runtime error(s): " + "; ".join(errors[:3]))
        # Known pre-UX-R02 defects are measured and reported, not silently
        # declared compliant and not converted into a misleading golden baseline.
        selectors = "#server-model-catalog, #server-task-tree, #server-test-cases, " \
                    "#server-guides, #server-campaigns, #server-results, " \
                    "#server-users, #server-planning, #server-environment-profile"
        count = page.locator(selectors).filter(visible=True).count()
        return {"visible_legacy_domains": count, "legacy_stack_observed": count > 1}
    finally:
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
            viewports = [{"width": 1366, "height": 900}, {"width": 390, "height": 844}]
            for viewport in viewports:
                width = viewport["width"]
                run(f"Standalone Demo workgroup {width}",
                    lambda v=viewport: demo_journey(browser, demo_url, directory, "u1", "workgroup", v))
                run(f"Standalone Demo engineer {width}",
                    lambda v=viewport: demo_journey(browser, demo_url, directory, "u2", "engineer", v))
                for role in ROLES:
                    run(f"Authenticated Server {role} {width}",
                        lambda k=role, v=viewport: server_journey(
                            browser, base_url, creds, directory, k, v))
        finally:
            browser.close()
    failed = [record for record in records if record["result"] == "FAIL"]
    report = {
        "version": 1,
        "suite": "UX-R01 Chromium infrastructure + diagnostic baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAIL" if failed else "PASS",
        "ui_conformance": "NOT_CERTIFIED: UX-R02/#115 and UX-R03/#116 required",
        "production_approval": "NO-GO: separate operational gates",
        "checks": records,
        "known_ux_findings": debts,
        "duration_seconds": round(time.monotonic() - start, 2),
    }
    (directory / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = ["# UI QA — " + report["status"], "",
             f"Chromium journeys: **{len(records) - len(failed)}/{len(records)} passed**.",
             "**UX conformance not certified** pending #115/#116; production remains NO-GO.",
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
