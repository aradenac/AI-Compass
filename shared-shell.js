/* UX-R02: one presentation shell and one route-selected visible domain in both runtimes.
 * Pure UI coordination: roles remain enforced by Django; no data-provider fallback. */
(function (root) {
  "use strict";
  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
  }
  function render(opts) {
    opts = opts || {};
    return '<div class="app ux-shell ux-mode-' + esc(opts.mode || "demo") + '">' +
      '<aside class="sidebar ux-sidebar" aria-label="Primary navigation">' +
      '<div class="brand"><div class="brand-mark" aria-hidden="true">✦</div>' +
      '<div><div class="brand-name">AI Compass</div><div class="brand-note">Evidence workspace</div></div></div>' +
      '<nav class="nav-area ux-sidebar-nav" aria-label="Business navigation">' +
      (opts.sidebar || "") + '</nav>' +
      '<div class="side-foot">' + (opts.footer || "") + '</div></aside>' +
      '<section class="main ux-main"><header class="topbar ux-topbar">' +
      '<div class="top-label"><span class="crumb">Workspace</span>' +
      '<span class="muted" aria-hidden="true">/</span><strong id="ux-page-title">' +
      esc(opts.title || "AI Compass") + '</strong></div>' +
      '<div class="top-actions">' + (opts.account || "") + '</div></header>' +
      '<main class="content ux-content" id="ux-main-content">' + (opts.content || "") +
      '</main></section></div>' + (opts.extras || "");
  }
  function selectScreen(host, id) {
    if (!host) throw new Error("Active business screen host missing");
    var next = Array.from(host.children).find(function (n) { return n.id === id; });
    if (!next) throw new Error("Unknown business screen " + id);
    Array.from(host.children).forEach(function (el) {
      el.setAttribute("data-ux-screen", "");
      var active = el === next;
      if (active) {
        el.setAttribute("data-ux-active", "");
        el.hidden = false;
      } else {
        el.removeAttribute("data-ux-active");
        el.hidden = true;
      }
    });
    host.dataset.uxCurrent = id;
    return next;
  }
  function serverNav(persona, grants, section, maintenance) {
    grants = grants || [];
    var sections = [];
    var prefix = maintenance ? "/maintenance?mode=server" :
      "/?mode=server&workspace=" + encodeURIComponent(persona || "workgroup");
    function item(slug, label, permitted) {
      if (!permitted) return;
      sections.push('<a class="nav-link' + (section === slug ? ' active' : '') +
        '" href="' + esc(prefix + "&section=" + encodeURIComponent(slug)) +
        '"' + (section === slug ? ' aria-current="page"' : "") + '>' +
        esc(label) + '</a>');
    }
    if (maintenance) {
      item("audit", "Audit & Changes", grants.includes("audit_view"));
      item("health", "Data health", grants.includes("maintenance_view"));
    } else if (persona === "workgroup") {
      item("studio", "Workgroup Studio", grants.includes("business_write"));
      var group = root.AICompassWorkgroup;
      if (group) group.ZONES.forEach(function (zone) {
        sections.push('<div class="nav-label">' + esc(zone.name) + '</div>');
        zone.blocks.forEach(function (block) {
          item(block[0], block[1], group.canVisit(block[0], grants, "server", true));
        });
      });
    } else if (persona === "engineer") {
      item("home", "My AI Workspace", grants.includes("business_read"));
      item("tasks", "Task explorer", grants.includes("business_read"));
      item("catalog", "Technology catalog", grants.includes("business_read"));
      item("results", "Benchmark results", grants.includes("business_read"));
      item("guides", "Guides & charter", grants.includes("business_read"));
      item("environment", "My OS environment", grants.includes("business_read"));
    } else if (persona === "management") {
      item("home", "Management Insights", grants.includes("planning_view"));
      item("planning", "Planning & resources", grants.includes("planning_view"));
    }
    if (!maintenance && grants.includes("users_manage")) item("users", "Users & Access", true);
    item("account", "My account", true);
    return sections.join("");
  }
  function attachDialogs(host) {
    // Editors stay under their original controller root: event listeners, scoped
    // selectors, draft values and existing API/CSRF semantics are preserved.
    var selector = '[data-common-editor], [id$="-editor"], #forecast-form-panel, #discussion-compose, #server-user-create-panel';
    var current = null, timer = false;
    function closeCurrent() {
      if (!current) return;
      var old = current;
      current = null;
      old.node.classList.remove("ux-dialog-panel");
      old.node.removeAttribute("role");
      old.node.removeAttribute("aria-modal");
      old.node.removeAttribute("aria-label");
      if (old.heading.isConnected) old.heading.remove();
      if (old.backdrop.isConnected) old.backdrop.remove();
      document.body.classList.remove("ux-dialog-open");
      if (old.restoreFocus && old.restoreFocus.isConnected &&
          typeof old.restoreFocus.focus === "function") old.restoreFocus.focus();
    }
    function eligible(node) {
      return node.isConnected && !node.hidden && node.querySelector("form") &&
        node.getClientRects().length && node.closest('[data-ux-active]');
    }
    function sync() {
      timer = false;
      if (current && !eligible(current.node)) closeCurrent();
      if (current) return;
      var nodes = Array.from(host.querySelectorAll(selector));
      var node = nodes.find(eligible);
      if (!node) return;
      var trigger = document.activeElement;
      var backdrop = document.createElement("div");
      backdrop.className = "ux-dialog-backdrop";
      backdrop.setAttribute("aria-hidden", "true");
      // Form dialogs do not dismiss on backdrop click (NFR-UX-001).
      backdrop.addEventListener("click", function (event) { event.preventDefault(); });
      var heading = document.createElement("div");
      heading.className = "ux-dialog-heading";
      var title = node.querySelector("h2,h3") ? node.querySelector("h2,h3").textContent : "Edit record";
      var label = document.createElement("strong");
      label.textContent = title;
      var closer = document.createElement("button");
      closer.type = "button";
      closer.className = "ux-dialog-close";
      closer.setAttribute("aria-label", "Close dialog");
      closer.textContent = "×";
      heading.appendChild(label); heading.appendChild(closer);
      node.insertBefore(heading, node.firstChild);
      node.classList.add("ux-dialog-panel");
      node.setAttribute("role", "dialog");
      node.setAttribute("aria-modal", "true");
      node.setAttribute("aria-label", title);
      document.body.appendChild(backdrop);
      document.body.classList.add("ux-dialog-open");
      current = {node:node,heading:heading,backdrop:backdrop,restoreFocus:trigger};
      closer.addEventListener("click", function () {
        var cancel = Array.from(node.querySelectorAll('button[type="button"],button:not([type])')).find(
          function (b) { return /cancel|close|annuler/i.test(b.textContent) &&
            !b.classList.contains("ux-dialog-close"); });
        if (cancel) cancel.click();
        node.hidden = true;
        closeCurrent();
      });
      var control = node.querySelector('input:not([type="hidden"]),select,textarea,button');
      if (control && typeof control.focus === "function") control.focus();
    }
    function schedule() {
      if (timer) return;
      timer = true;
      Promise.resolve().then(sync);
    }
    var observer = new MutationObserver(schedule);
    observer.observe(host, {subtree:true,childList:true,attributes:true,attributeFilter:["hidden","data-ux-active"]});
    document.addEventListener("keydown", function (event) {
      if (!current) return;
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopImmediatePropagation();
      } else if (event.key === "Tab") {
        var focusable = Array.from(current.node.querySelectorAll(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]'
        )).filter(function (n) { return n.getClientRects().length; });
        if (!focusable.length) return;
        var first=focusable[0], last=focusable[focusable.length-1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus();
        }
      }
    }, true);
    schedule();
    return {sync:schedule, disconnect:function () { observer.disconnect(); closeCurrent(); }};
  }
  root.AICompassShell = {render:render,selectScreen:selectScreen,
    serverNav:serverNav,attachDialogs:attachDialogs};
})(window);
