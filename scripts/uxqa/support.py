"""Low-level Chromium assertions shared by the Demo and Server journeys."""
import json
import re
from pathlib import Path


def visible(page, selector):
    """Return the locator for the visible matches of a selector."""
    return page.locator(selector).filter(visible=True)


def assert_exactly_one_view(page, selector):
    visible_count = page.locator(selector).filter(visible=True).count()
    if visible_count != 1:
        raise AssertionError(
            f"Expected exactly one active business view; found {visible_count}: {selector}")


def assert_no_privileged_view(page, selector, label):
    """Fail closed: an unauthorized/absent surface must never be rendered."""
    found = page.locator(selector).filter(visible=True).count()
    if found:
        raise AssertionError(
            f"Unauthorized or unrelated view was rendered ({label}); found {found} match(es) "
            f"for {selector}")


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


def assert_conflict_surfaced(*texts):
    """A refused optimistic-concurrency save must be reported, never silent."""
    joined = " ".join(text or "" for text in texts)
    if not re.search(r"409|conflict", joined, re.IGNORECASE):
        raise AssertionError("Revision conflict was not surfaced to the user: " +
                             joined[:200])
    return True


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


def capture(page, directory, name):
    """Retain a desktop screenshot; never retain credentials or auth form content."""
    page.evaluate("""() => document.querySelectorAll('input[type="password"]')
        .forEach(input => { input.value = ''; })""")
    Path(directory).mkdir(parents=True, exist_ok=True)
    target = Path(directory) / (name + ".png")
    dialog = page.locator('[role="dialog"]').filter(visible=True)
    if dialog.count() == 1:
        # A fixed dialog is painted at the viewport despite a full-page capture.
        # Review the modal itself: top of its own scroll, viewport-sized image.
        dialog.first.evaluate("el => { el.scrollTop = 0; }")
        page.screenshot(path=str(target), animations="disabled")
        return
    page.screenshot(path=str(target), full_page=True, animations="disabled")
