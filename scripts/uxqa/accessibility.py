"""Minimal, automatable accessibility and runtime-error gates (UX-R07 #126).

Only deterministic, offline checks are enforced: semantic headings, accessible
control/action names, unique ids, dialog naming and focus behaviour, a single
active view with one current navigation entry, a document language and clean
console/network state. Contrast and screen-reader interaction remain manual
review items and are never asserted here.

Heading-level skips and views without a top-level heading are *audited
findings*: they are reported with element evidence for the UX-R07 coverage
matrix instead of being silently accepted as a pass.
"""
AUDIT_JS = r"""() => {
  const shown = (el) => !!el.getClientRects().length;
  const txt = (el) => (el.textContent || "").replace(/\s+/g, " ").trim();
  const labelled = (el) => {
    if ((el.getAttribute("aria-label") || "").trim()) return true;
    if ((el.getAttribute("aria-labelledby") || "").trim()) return true;
    if (el.id && document.querySelector('label[for="' + CSS.escape(el.id) + '"]')) return true;
    if (el.closest("label")) return true;
    if ((el.getAttribute("title") || "").trim()) return true;
    return false;
  };
  const controls = Array.from(document.querySelectorAll("input,select,textarea"))
    .filter((el) => shown(el) && el.type !== "hidden");
  const actions = Array.from(document.querySelectorAll("button,a[href]")).filter(shown);
  const named = (el) => !!(txt(el) || (el.getAttribute("aria-label") || "").trim() ||
    (el.getAttribute("title") || "").trim() || el.querySelector("img[alt]:not([alt=''])" ));
  const ids = {};
  const duplicates = [];
  Array.from(document.querySelectorAll("[id]")).filter(shown).forEach((el) => {
    if (ids[el.id]) { if (duplicates.indexOf(el.id) < 0) duplicates.push(el.id); }
    else ids[el.id] = 1;
  });
  const headings = Array.from(document.querySelectorAll("h1,h2,h3,h4,h5,h6"))
    .filter(shown)
    .map((el) => ({level: Number(el.tagName.slice(1)), text: txt(el).slice(0, 70)}));
  const skips = [];
  headings.forEach((heading, index) => {
    if (index === 0) return;
    if (heading.level > headings[index - 1].level + 1)
      skips.push(headings[index - 1].level + "→" + heading.level + " (" + heading.text + ")");
  });
  const dialogs = Array.from(document.querySelectorAll('[role="dialog"]')).filter(shown)
    .map((el) => ({name: (el.getAttribute("aria-label") || "").trim() ||
      (el.getAttribute("aria-labelledby") || "").trim(),
      modal: el.getAttribute("aria-modal"), hasForm: !!el.querySelector("form")}));
  const currents = Array.from(document.querySelectorAll('[aria-current="page"]')).filter(shown);
  const landmarks = Array.from(document.querySelectorAll("main,[role=main]")).filter(shown).length;
  return {
    lang: (document.documentElement.getAttribute("lang") || "").trim(),
    title: document.title,
    controls: controls.length,
    controls_without_name: controls.filter((el) => !labelled(el))
      .map((el) => el.outerHTML.slice(0, 130)),
    actions_without_name: actions.filter((el) => !named(el))
      .map((el) => el.outerHTML.slice(0, 130)),
    duplicate_ids: duplicates,
    headings,
    heading_skips: skips,
    h1: headings.filter((h) => h.level === 1).length,
    dialogs,
    dialogs_without_name: dialogs.filter((d) => !d.name).length,
    aria_current: currents.map((el) => (el.getAttribute("href") || "").slice(0, 120)),
    landmarks,
    live_regions: Array.from(document.querySelectorAll('[role="status"],[role="alert"],[aria-live]'))
      .filter(shown).length
  };
}"""


def audit(page):
    return page.evaluate(AUDIT_JS)


def assert_accessible(page, label, expect_current=True, expect_heading=True,
                      require_landmark=True, review=None):
    """Enforce the deterministic accessibility gate and return the audit record."""
    data = audit(page)
    problems = []
    if not data["lang"]:
        problems.append("document has no lang")
    if data["controls_without_name"]:
        problems.append("visible form controls without an accessible name: " +
                        "; ".join(data["controls_without_name"][:4]))
    if data["actions_without_name"]:
        problems.append("visible buttons/links without an accessible name: " +
                        "; ".join(data["actions_without_name"][:4]))
    if data["duplicate_ids"]:
        problems.append("duplicate element ids in the rendered view: " +
                        ", ".join(data["duplicate_ids"][:6]))
    if data["dialogs_without_name"]:
        problems.append("visible dialog without an accessible name")
    if len(data["dialogs"]) > 1:
        problems.append("more than one visible dialog at a time")
    if expect_heading and not data["headings"]:
        problems.append("rendered view exposes no semantic heading")
    if data["h1"] > 1:
        problems.append("more than one h1 in the rendered view: " + str(data["h1"]))
    if expect_current and len(data["aria_current"]) != 1:
        problems.append("expected exactly one aria-current=page navigation entry, found " +
                        str(len(data["aria_current"])))
    if require_landmark and data["landmarks"] != 1:
        problems.append("expected exactly one visible main landmark, found " +
                        str(data["landmarks"]))
    if problems:
        raise AssertionError(f"{label}: accessibility regression: " + " | ".join(problems))
    findings = []
    if data["heading_skips"]:
        findings.append({"label": label, "kind": "heading_level_skip",
                         "detail": data["heading_skips"]})
    if not data["h1"]:
        findings.append({"label": label, "kind": "no_h1",
                         "detail": data["headings"][:3]})
    if review is not None:
        review.extend(findings)
    return data


def assert_dialog_focus(page, label):
    """NFR-UX-001/002 plus focus containment and focus return on a form dialog."""
    dialog = page.locator('[role="dialog"]').filter(visible=True)
    if dialog.count() != 1 or not dialog.is_visible():
        raise AssertionError(f"{label}: a single visible form dialog is required")
    if not dialog.locator("form").count():
        raise AssertionError(f"{label}: dialog does not contain the editable form")
    if not (dialog.get_attribute("aria-modal") == "true"):
        raise AssertionError(f"{label}: editable dialog is not announced as modal")
    if not ((dialog.get_attribute("aria-label") or "").strip() or
            (dialog.get_attribute("aria-labelledby") or "").strip()):
        raise AssertionError(f"{label}: dialog has no accessible name")
    inside = "() => !!document.activeElement.closest('[role=dialog]')"
    if not page.evaluate(inside):
        raise AssertionError(f"{label}: opening the dialog did not move focus inside it")
    escaped = False
    for _ in range(18):
        page.keyboard.press("Tab")
        if not page.evaluate(inside):
            escaped = True
            break
    if escaped:
        raise AssertionError(f"{label}: Tab left the modal dialog (focus not contained)")
    page.keyboard.press("Escape")
    if not dialog.is_visible():
        raise AssertionError(f"{label}: Escape dismissed a form dialog")
    dialog.get_by_role("button", name="Close dialog").click()
    dialog.wait_for(state="hidden")
    returned = page.evaluate("""() => {
      const el = document.activeElement;
      return !!(el && el.isConnected && el.getClientRects().length && !el.closest('[role=dialog]'));
    }""")
    if not returned:
        raise AssertionError(f"{label}: closing the dialog did not return focus to a visible control")


class PageWatch:
    """Collect page errors, unexpected HTTP failures and API traffic per context."""

    def __init__(self, page, allowed_responses=()):
        self.page_errors = []
        self.unexpected = []
        self.api_requests = []
        self.responses = []
        self.allowed = tuple(allowed_responses)
        page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        page.on("request", lambda request: self.api_requests.append(request.url)
                if "/api/v1/" in request.url else None)
        page.on("response", self._response)

    def _response(self, response):
        status = response.status
        if status < 400:
            return
        url = response.url
        self.responses.append((status, url))
        if any(status == code and fragment in url for code, fragment in self.allowed):
            return
        if status >= 500 or (status in (401, 403, 404, 409, 422) and "/api/v1/" in url):
            self.unexpected.append(f"{status} {url.split('?')[0]}")

    def assert_clean(self, label, allow_unexpected=0):
        if self.page_errors:
            raise AssertionError(f"{label}: JavaScript exception(s): " +
                                 " | ".join(self.page_errors[:3]))
        if len(self.unexpected) > allow_unexpected:
            raise AssertionError(f"{label}: unexpected HTTP failure(s): " +
                                 " | ".join(sorted(set(self.unexpected))[:4]))

    def observed(self, status, fragment):
        return any(code == status and fragment in url for code, url in self.responses)

    def as_dict(self):
        return {"page_errors": self.page_errors[:5],
                "unexpected_http": sorted(set(self.unexpected))[:5],
                "api_requests": len(self.api_requests)}
