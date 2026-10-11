"""Offline standalone Demo Chromium journeys (no Server, no API calls)."""
import re

from .accessibility import PageWatch, assert_accessible
from .support import assert_no_horizontal_overflow, capture

DRAFT_ISOLATION_JS = r"""
({ protourl }) => new Promise(async (resolve) => {
  const result = {checks: {}, failures: []};
  const fail = (name, detail) => result.failures.push(name + ": " + detail);
  const script = document.createElement("script");
  script.src = protourl.replace(/[^/]*$/, "") + "shared-drafts.js";
  document.head.appendChild(script);
  await new Promise((r) => { script.onload = r; script.onerror = r; });
  const drafts = window.AICompassDrafts;
  if (!drafts) { fail("bootstrap", "shared-drafts.js did not expose AICompassDrafts"); return resolve(result); }
  const form = document.createElement("form");
  form.innerHTML = '<input name="title"><textarea name="body"></textarea>' +
    '<input name="api_key" value=""><input name="password" type="password">' +
    '<input type="hidden" name="hiddenField">';
  document.body.appendChild(form);
  const scope = {mode: "demo", account: "demo-user", kind: "guide", id: "g1", revision: "r002", schema: "guide-v1"};
  const handle = drafts.attach(form, scope);
  form.querySelector('input[name="title"]').value = "local draft";
  form.querySelector('textarea[name="body"]').value = "unsaved";
  form.dispatchEvent(new Event("input", {bubbles: true}));
  const stored = drafts.read(scope);
  result.checks.isolated_scope = !!stored &&
    Object.keys(stored.data).sort().join(",") === "body,title";
  if (!result.checks.isolated_scope)
    fail("isolation", "draft must persist allowed fields and omit password/api_key/hidden: " +
      JSON.stringify(stored && stored.data));
  result.checks.mode_isolation = !drafts.read({mode: "server", account: "demo-user",
    kind: "guide", id: "g1", revision: "r002", schema: "guide-v1"});
  if (!result.checks.mode_isolation) fail("mode_isolation", "demo draft leaked into the server scope");
  result.checks.account_isolation = !drafts.read({mode: "demo", account: "other-account",
    kind: "guide", id: "g1", revision: "r002", schema: "guide-v1"});
  if (!result.checks.account_isolation) fail("account_isolation", "draft leaked across accounts");
  form.remove();
  // An incompatible authoritative revision/schema must never be replayed silently.
  const oldForm = document.createElement("form");
  oldForm.innerHTML = '<input name="title" value="stale">';
  document.body.appendChild(oldForm);
  const bannerText = [];
  const oldScope = {mode: "demo", account: "demo-user", kind: "guide", id: "g2",
    revision: "r005", schema: "guide-v1"};
  window.localStorage.setItem(drafts.key(oldScope), JSON.stringify({format: 1,
    scope: drafts.scope(oldScope), schema: "guide-v1", revision: "r004",
    savedAt: Date.now(), data: {title: "old revision draft"}}));
  const oldHandle = drafts.attach(oldForm, oldScope);
  const banner = oldForm.previousElementSibling;
  bannerText.push(banner ? banner.textContent : "");
  result.checks.incompatible_not_applied = oldForm.querySelector("input").value === "stale" &&
    /NOT applied/.test(bannerText.join(" "));
  if (!result.checks.incompatible_not_applied)
    fail("incompatible", "stale revision draft was applied or not reported: " +
      oldForm.querySelector("input").value + " / " + bannerText.join(" "));
  const discard = banner.querySelector("button");
  if (!discard) fail("discard", "no explicit discard control on an incompatible draft");
  else {
    discard.click();
    result.checks.discard_clears = !drafts.read(oldScope);
    if (!result.checks.discard_clears) fail("discard", "discard did not clear the incompatible draft");
  }
  // Expired local drafts are pruned and out-of-format entries are refused.
  const expiredScope = {mode: "demo", account: "demo-user", kind: "guide", id: "g3",
    revision: "r001", schema: "guide-v1"};
  window.localStorage.setItem(drafts.key(expiredScope), JSON.stringify({format: 1,
    scope: drafts.scope(expiredScope), schema: "guide-v1", revision: "r001",
    savedAt: Date.now() - 8 * 86400000, data: {title: "expired"}}));
  drafts.prune();
  result.checks.expired_pruned = !drafts.read(expiredScope);
  if (!result.checks.expired_pruned) fail("expiry", "an 8-day-old draft was still readable");
  oldHandle.dispose();
  resolve(result);
})
"""


def demo_journey(browser, demo_url, artifacts, role, label, viewport):
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    page.set_default_timeout(12000)
    watch = PageWatch(page)
    findings = []
    try:
        # Each browser context is clean; no server identity or database is available.
        page.goto(demo_url + "?mode=demo&workspace=" + label, wait_until="domcontentloaded")
        page.locator(f'[data-act="login"][data-id="{role}"]').wait_for(state="visible")
        assert_accessible(page, "demo sign-in " + label, expect_current=False,
                          require_landmark=False, review=findings)
        page.locator(f'[data-act="login"][data-id="{role}"]').click()
        page.locator(".app").wait_for(state="visible", timeout=20000)
        if not page.locator(".ux-shell .ux-content").is_visible() or not page.locator(".ux-shell .ux-sidebar").is_visible():
            raise AssertionError("Demo did not render the common shell")
        if page.locator(".ux-shell").count() != 1:
            raise AssertionError("Demo has competing application shells")
        assert_no_horizontal_overflow(page)
        assert_accessible(page, "demo " + label + " entry", review=findings)
        if watch.api_requests:
            raise AssertionError("Standalone Demo unexpectedly contacted API: " + str(watch.api_requests))
        capture(page, artifacts, "demo-" + label + "-" + str(viewport["width"]))
        if role == "u1":
            # UX-R04: inspect actual shared business surfaces, not source text.
            for section, domain in [
                ("knowledge", "guides"), ("watch", "watch"),
                ("feedback", "feedback"), ("recommendations", "recommendations"),
                ("benchmark", "campaigns"), ("testdesign", "cases")
            ]:
                page.locator(f'[data-act="nav"][data-id="{section}"]').first.click()
                if domain == "cases":
                    surface = page.locator('.shared-case-tree[data-shared-cases="demo"]')
                else:
                    surface = page.locator(
                        f'.shared-business-list[data-business-domain="{domain}"]')
                surface.wait_for(state="visible", timeout=20000)
                if surface.locator('[data-business-record]').count() == 0 and domain != "cases":
                    raise AssertionError("Seeded Demo lacks real shared " + domain + " record cards")
                assert_no_horizontal_overflow(page)
                assert_accessible(page, "demo workgroup " + domain, review=findings)
                if domain in ("guides", "campaigns", "cases"):
                    capture(page, artifacts, "demo-shared-" + domain + "-" + str(viewport["width"]))
            page.locator(".shared-case-tree button[data-act=caseDetail]").first.click()
            detail = page.locator('.shared-case-detail[data-shared-case-detail="demo"]')
            detail.wait_for(state="visible")
            if detail.locator("h3").count() != 1:
                raise AssertionError("Shared Test Case detail lacks semantic heading")
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()

        if role == "u1":
            # UX-R04: real Demo form -> local save -> same semantic Guide read view.
            page.locator('[data-act="nav"][data-id="knowledge"]').first.click()
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
            page.locator('[data-act="nav"][data-id="watch"]').first.click()
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
            page.get_by_role("dialog").get_by_role("button", name="Close dialog").click()
        if role == "u1":
            # The actual Demo form must honor the same NFR modal contract.
            page.locator('[data-act="nav"][data-id="testdesign"]').first.click()
            page.locator('[data-act="newCase"]').first.click()
            demo_dialog = page.get_by_role("dialog")
            demo_dialog.wait_for(state="visible", timeout=12000)
            if demo_dialog.locator("form").count() != 1:
                raise AssertionError("Demo Test Case form missing from dialog")
            original = demo_dialog.locator("input:not([type=hidden])").first
            original.fill("Preserve this unfinished Demo draft")
            page.locator("#backdrop").click(position={"x": 2, "y": 2}, force=True)
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
            # Workgroup map: five zones, modeled counters only, real deep link.
            page.locator('[data-act="nav"][data-id="studio"]').first.click()
            page.locator(".shared-studio-zone").first.wait_for(state="visible", timeout=20000)
            zones = page.locator(".shared-studio-zone")
            if zones.count() != 5:
                raise AssertionError("Workgroup map must expose exactly five zones, found " +
                                     str(zones.count()))
            for zone in ["Sources", "Formalisation", "Expérimentation", "Capitalisation",
                         "Mise à disposition"]:
                if not page.locator(".shared-studio-zone").filter(has_text=zone).count():
                    raise AssertionError("Workgroup map lost zone: " + zone)
            opportunity = page.locator('[data-studio-section="opportunities"]')
            if opportunity.count() != 1:
                raise AssertionError("Profitability -> Technology Catalog opportunity link missing")
            if "section=opportunities" not in (opportunity.get_attribute("href") or ""):
                raise AssertionError("Opportunity block does not deep link to the authorized view")
            if page.locator('[data-studio-section="watch"] .shared-attention').count():
                raise AssertionError(
                    "Technology Watch exposes an attention count without a modeled resolution state")
            badges = page.locator('[data-studio-section="benchmark"] .shared-attention')
            if badges.count() > 1:
                raise AssertionError("Under-review Campaigns must expose a single count")
            if badges.count():
                if not re.match(r"^\s*\d+\s+requiring review\s*$", badges.first.inner_text()):
                    raise AssertionError("Campaign attention count is not a single integer count")
            assert_accessible(page, "demo workgroup studio map", review=findings)
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-workgroup-map-" + str(viewport["width"]))

        if role == "u1":
            # Real seeded Workgroup path: Studio -> Watch -> selected record -> origin
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
            assert_accessible(page, "demo workgroup record detail", review=findings)
            detail_url = page.url
            # Stable deep link: the exact record survives a full reload.
            page.reload(wait_until="domcontentloaded")
            page.locator(".ux-context-detail").wait_for(state="visible", timeout=20000)
            if page.url != detail_url:
                raise AssertionError("Reload changed the exact record deep link")
            # Browser Back returns to the filtered origin, Forward to the record.
            page.go_back(wait_until="domcontentloaded")
            page.locator('[data-ux-list-filter]').wait_for(state="visible", timeout=20000)
            if page.locator('[data-ux-list-filter]').input_value() != "agent":
                raise AssertionError("Browser Back lost the filtered Workgroup origin")
            if page.locator(".ux-context-detail").count():
                raise AssertionError("Browser Back kept displaying the selected record")
            page.go_forward(wait_until="domcontentloaded")
            page.locator(".ux-context-detail").wait_for(state="visible", timeout=20000)
            if page.url != detail_url:
                raise AssertionError("Browser Forward did not restore the exact record location")
            page.locator("#ux-context-navigation .ux-return-link").click()
            page.locator('[data-ux-list-filter]').wait_for(state="visible", timeout=20000)
            if page.locator('[data-ux-list-filter]').input_value() != "agent":
                raise AssertionError("Return to origin lost Workgroup filter")
            if page.locator(".ux-context-detail").count():
                raise AssertionError("Back from detail still displays selected record")
            # The same location survives a plain reload without the filter.
            page.reload(wait_until="domcontentloaded")
            page.locator('[data-ux-list-filter]').wait_for(state="visible", timeout=20000)
            if page.locator('[data-ux-list-filter]').input_value() != "agent":
                raise AssertionError("Reload lost the filtered Workgroup list")
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-workgroup-return-" + str(viewport["width"]))
        if role == "u2":
            # Engineer Task/Tool -> Solution detail -> measured Run -> contextual return.
            page.locator("[data-engineer-view=tool]").click()
            page.locator("[data-engineer-view=task]").click()
            body = page.locator("[data-engineer-body]").inner_text()
            if "not_configured" not in body and "Profile" not in body:
                raise AssertionError("Engineer landing hides its explicit profile state")
            page.locator("[data-engineer-detail]").first.click()
            page.locator("#ux-engineer-setup").wait_for(state="visible", timeout=20000)
            page.locator("#ux-engineer-feedback").wait_for(state="visible")
            if not page.locator("[data-engineer-home]").is_visible():
                raise AssertionError("Engineer detail has no discoverable origin")
            assert_accessible(page, "demo engineer solution detail", review=findings)
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
            assert_accessible(page, "demo management insight inspector", review=findings)
            assert_no_horizontal_overflow(page)
            capture(page, artifacts, "demo-management-inspector-" + str(viewport["width"]))
        watch.assert_clean("Standalone Demo " + label)
        return {"visible_active_screens": 1, "shared_shell": True, "findings": findings}
    finally:
        context.tracing.stop(path=str(artifacts / ("demo-" + label + "-" +
                                                   str(viewport["width"]) + ".zip")))
        context.close()


def demo_publication_boundary(browser, demo_url, artifacts, viewport):
    """§13-07/§13-19: a reader sees published knowledge only, never internal drafts."""
    def knowledge_texts(role, label):
        context = browser.new_context(viewport=viewport, reduced_motion="reduce")
        page = context.new_page()
        page.set_default_timeout(15000)
        watch = PageWatch(page)
        try:
            page.goto(demo_url + "?mode=demo&workspace=" + label, wait_until="domcontentloaded")
            page.locator(f'[data-act="login"][data-id="{role}"]').click()
            page.locator(".app").wait_for(state="visible", timeout=20000)
            page.locator('[data-act="nav"][data-id="knowledge"]').first.click()
            page.locator('.shared-business-list[data-business-domain="guides"]').wait_for(
                state="visible", timeout=20000)
            guides = page.locator('[data-business-domain="guides"]').inner_text()
            page.locator('[data-act="nav"][data-id="activity"]').first.click()
            page.locator("#ux-main-content h1").first.wait_for(state="visible", timeout=20000)
            page.wait_for_timeout(300)
            events = page.locator("#ux-main-content").inner_text()
            if watch.api_requests:
                raise AssertionError("Demo publication boundary check contacted the API")
            watch.assert_clean("Demo publication boundary")
            return guides, events
        finally:
            context.close()

    contributor_guides, contributor_events = knowledge_texts("u1", "workgroup")
    reader_guides, reader_events = knowledge_texts("u2", "engineer")
    if "Prepare a reproducible benchmark package" not in contributor_guides:
        raise AssertionError("Contributor cannot see the internal draft Guide fixture")
    internal_event = "Staged a Python backend benchmark run (draft)"
    if internal_event not in contributor_events:
        raise AssertionError("Contributor cannot see the internal Activity Feed fixture")
    if "Prepare a reproducible benchmark package" in reader_guides:
        raise AssertionError("Unpublished draft Guide leaked to a reader")
    if internal_event in reader_events:
        raise AssertionError("Internal Activity Feed event leaked to a reader")
    return {"contributor_guides_visible": True, "reader_internal_hidden": True}


def demo_draft_isolation(browser, demo_url, artifacts, viewport):
    """§13-13/§13-19: the real shared draft engine never crosses modes/accounts."""
    context = browser.new_context(viewport=viewport, reduced_motion="reduce")
    page = context.new_page()
    try:
        page.goto(demo_url, wait_until="domcontentloaded")
        result = page.evaluate(DRAFT_ISOLATION_JS, {"protourl": demo_url})
        if result["failures"]:
            raise AssertionError("Shared draft contract violated: " + " | ".join(result["failures"]))
        capture(page, artifacts, "demo-draft-contract-" + str(viewport["width"]))
        return result["checks"]
    finally:
        context.close()
