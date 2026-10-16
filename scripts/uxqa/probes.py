"""Mutation probes: prove the gate actually rejects representative regressions."""

from .accessibility import assert_dialog_focus
from .support import (assert_conflict_surfaced, assert_exactly_one_view,
                      assert_modal_form, assert_no_horizontal_overflow,
                      assert_no_privileged_view, assert_return_path, expect_failure)

FOCUS_FIXTURE = """<style>.ux-dialog-backdrop{position:fixed;inset:0;background:#2229}
  .ux-dialog-panel{position:fixed;inset:10% 20%;background:white;padding:24px}</style>
  <button id="open" type="button">Open editor</button>
  <div class="ux-dialog-backdrop"></div>
  <div id="dialog" class="ux-dialog-panel" role="dialog" aria-modal="true" aria-label="Editor">
    <div class="ux-dialog-heading"><strong>Editor</strong>
      <button type="button" class="ux-dialog-close" aria-label="Close dialog">×</button></div>
    <form><input name="a" value=""><textarea name="b"></textarea>
      <button type="submit">Save</button></form>
  </div>
  <script>
    var dialog = document.getElementById("dialog");
    var trigger = document.getElementById("open");
    function close() { dialog.style.display = "none"; trigger.focus(); }
    dialog.querySelector(".ux-dialog-close").addEventListener("click", close);
    (dialog.querySelector("input,select,textarea,button") || dialog).focus();
    %TRAP%
  </script>"""

TRAP = """document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") { event.preventDefault(); return; }
      if (event.key !== "Tab") return;
      var focusable = Array.from(dialog.querySelectorAll("button,input,textarea,select"));
      var first = focusable[0], last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }, true);"""


def mutation_probes(browser, artifacts):
    """Independent tests prove the gate rejects representative intentional regressions."""
    page = browser.new_page(viewport={"width": 1366, "height": 900})
    checks = {}
    try:
        page.set_content('<main><section class="uxqa-domain">Catalog</section>'
                         '<section class="uxqa-domain">Unrelated Users</section></main>')
        expect_failure("stacked workspaces", lambda: assert_exactly_one_view(page, ".uxqa-domain"))
        page.set_content('<main><section class="uxqa-domain">Catalog</section></main>')
        assert_exactly_one_view(page, ".uxqa-domain")
        checks["single_active_view"] = True

        # §13-08: a privileged surface rendered for the wrong visitor must fail.
        page.set_content('<main><section id="server-planning">Planning</section></main>')
        expect_failure("authorization visibility",
                       lambda: assert_no_privileged_view(page, "#server-planning", "probe"))
        page.set_content('<main><section id="server-engineer">My AI Workspace</section></main>')
        assert_no_privileged_view(page, "#server-planning", "probe")
        checks["authorization_visibility"] = True

        page.set_content('<form><input placeholder="Editor"></form>')
        expect_failure("missing modal", lambda: assert_modal_form(page))
        modal = """<style>.modal-backdrop{position:fixed;inset:0;background:#2229;
            display:grid;place-items:center}.modal{background:white;padding:30px}</style>
            <div class="modal-backdrop"><div role="dialog" aria-label="Editor" class="modal">
            <button aria-label="Close dialog" onclick="this.closest('.modal-backdrop').remove()">×</button>
            <form><input value="draft"></form></div></div>"""
        page.set_content(modal)
        assert_modal_form(page)
        page.set_content(modal +
                         "<script>document.querySelector('.modal-backdrop').onclick=()=>"
                         "document.querySelector('.modal-backdrop').remove()</script>")
        expect_failure("backdrop discards draft", lambda: assert_modal_form(page))
        checks["modal_draft_preserved"] = True

        # NFR-UX-001/002 plus keyboard containment and focus return.
        page.set_content(FOCUS_FIXTURE.replace("%TRAP%", TRAP))
        assert_dialog_focus(page, "probe modal")
        assert_dialog_focus_broken(page, "untrapped dialog",
                                   FOCUS_FIXTURE.replace("%TRAP%", ""))
        assert_dialog_focus_broken(
            page, "escape dismisses the form",
            FOCUS_FIXTURE.replace("%TRAP%",
                                  TRAP + 'document.addEventListener("keydown", function (event) '
                                  '{ if (event.key === "Escape") { close(); } });'))
        assert_dialog_focus_broken(
            page, "focus is not returned",
            FOCUS_FIXTURE.replace("%TRAP%", TRAP).replace(
                'function close() { dialog.style.display = "none"; trigger.focus(); }',
                'function close() { dialog.style.display = "none"; }'))
        checks["dialog_focus_contract"] = True

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
        checks["return_path"] = True

        page.set_content('<div style="width:2000px;height:20px">overflow</div>')
        expect_failure("overflow", lambda: assert_no_horizontal_overflow(page))
        page.set_content('<div style="max-width:100%;height:20px">inside</div>')
        assert_no_horizontal_overflow(page)
        checks["no_overflow"] = True

        # §13-14: a client that treats a refused stale save as success must fail.
        expect_failure("silent revision conflict",
                       lambda: assert_conflict_surfaced("Guide saved."))
        assert_conflict_surfaced("Guide not saved: 409: authoritative revision changed")
        checks["conflict_surfaced"] = True

        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.evaluate("() => { setTimeout(() => { throw new Error('uxqa deliberate script error') }, 0) }")
        page.wait_for_timeout(150)
        if not any("uxqa deliberate script error" in error for error in errors):
            raise AssertionError("JavaScript runtime exception was not captured")
        checks["console_capture"] = True
        page.screenshot(path=str(artifacts / "mutation-fixtures.png"))
        return checks
    finally:
        page.close()


def assert_dialog_focus_broken(page, label, markup):
    page.set_content(markup)
    try:
        assert_dialog_focus(page, label)
    except AssertionError:
        return True
    raise AssertionError("Mutation " + label + " was NOT detected by the focus assertion")
