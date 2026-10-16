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
  window.localStorage.setItem(drafts.key(oldScope), JSON.stringify({format: drafts.FORMAT,
    scope: drafts.scope(oldScope), schema: "guide-v1", revision: "r004",
    savedAt: Date.now(), data: {title: "old revision draft"}}));
  const oldHandle = drafts.attach(oldForm, oldScope);
  // The merged draft engine (#124) renders the resume/stale offer on an explicit
  // reoffer(); a controller re-rendering around an attached form calls it.
  if (typeof oldHandle.reoffer === "function") oldHandle.reoffer();
  const banner = oldForm.previousElementSibling;
  bannerText.push(banner ? banner.textContent : "");
  result.checks.incompatible_not_applied = oldForm.querySelector("input").value === "stale" &&
    /NOT applied/.test(bannerText.join(" "));
  if (!result.checks.incompatible_not_applied)
    fail("incompatible", "stale revision draft was applied or not reported: " +
      oldForm.querySelector("input").value + " / " + bannerText.join(" "));
  const discard = Array.from(banner.querySelectorAll("button")).find(function(button){
    return /discard/i.test(button.textContent); });
  if (!discard) fail("discard", "no explicit discard control on an incompatible draft");
  else {
    discard.click();
    result.checks.discard_clears = !drafts.read(oldScope);
    if (!result.checks.discard_clears) fail("discard", "discard did not clear the incompatible draft");
  }
  // Expired local drafts are pruned and out-of-format entries are refused.
  const expiredScope = {mode: "demo", account: "demo-user", kind: "guide", id: "g3",
    revision: "r001", schema: "guide-v1"};
  window.localStorage.setItem(drafts.key(expiredScope), JSON.stringify({format: drafts.FORMAT,
    scope: drafts.scope(expiredScope), schema: "guide-v1", revision: "r001",
    savedAt: Date.now() - 8 * 86400000, data: {title: "expired"}}));
  drafts.prune();
  result.checks.expired_pruned = !drafts.read(expiredScope);
  if (!result.checks.expired_pruned) fail("expiry", "an 8-day-old draft was still readable");
  oldHandle.dispose();
  resolve(result);
})
"""


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
