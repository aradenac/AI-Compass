/* PLAT-28: Server-only Users & Access. No Demo data, no local persistence. */
(function () {
  "use strict";
  function mount(root, csrf, escapeHtml) {
    var enabled = false, platform = false, epoch = 0, page = 1, search = "", filter = "all";
    var rows = [], roles = ["user", "contributor", "reviewer", "data-maintainer", "user-admin", "platform-admin"];
    function el(selector) { return root.querySelector(selector); }
    function text(message, error) {
      var node = el("#server-users-state");
      if (node) { node.textContent = message; node.className = error ? "server-status server-error" : "server-status"; }
    }
    async function request(path, method, data) {
      var options = {method: method || "GET", credentials: "same-origin", cache: "no-store"};
      if (method && method !== "GET") {
        options.headers = {"Content-Type": "application/json", "X-CSRFToken": csrf()};
        options.body = JSON.stringify(data);
      }
      var response = await fetch("/api/v1/admin/users" + path, options);
      var body = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(body.error || "HTTP " + response.status);
      return body;
    }
    function checkboxes(selected) {
      return roles.map(function (role) {
        var disabled = role === "platform-admin" && !platform;
        return '<label style="display:inline-flex;align-items:center;gap:4px;margin:5px 12px 5px 0">' +
          '<input style="width:auto" type="checkbox" name="role" value="' + escapeHtml(role) + '"' +
          (selected.includes(role) ? ' checked' : '') +
          (disabled ? ' disabled' : '') + '>' + escapeHtml(role) + '</label>';
      }).join("");
    }
    function getRoles(form) {
      return Array.from(form.querySelectorAll('input[name="role"]:checked')).map(function (node) { return node.value; });
    }
    function render() {
      root.innerHTML = '<div class="server-model-toolbar"><h2>Maintenance · Users & Access</h2>' +
        '<button id="server-users-reload" type="button">Refresh accounts</button></div>' +
        '<p class="muted small">Server accounts only. Roles are independent; platform elevation requires additional authority.</p>' +
        '<p id="server-users-state" class="server-status" role="status"></p>' +
        '<form id="server-users-search" class="server-card" style="display:flex;flex-wrap:wrap;gap:10px;align-items:end">' +
        '<div><label for="server-user-query">Search username or email</label><input id="server-user-query" name="query" maxlength="100" value="' + escapeHtml(search) + '"></div>' +
        '<div><label for="server-user-filter">Status</label><select id="server-user-filter" name="status">' +
        ["all", "active", "inactive"].map(function (x) {
          return '<option value="' + x + '"' + (x === filter ? " selected" : "") + '>' + x + '</option>';
        }).join("") + '</select></div><button type="submit">Search</button></form>' +
        '<div id="server-users-list" class="server-card" style="margin:12px 0"></div>' +
        '<div id="server-users-editor" class="server-card" style="margin:12px 0" hidden></div>' +
        '<button id="server-user-open-create" type="button">+ Create account</button>' +
        '<section id="server-user-create-panel" class="server-card" style="margin:12px 0" hidden><h3>Create account · administrator-set credential</h3>' +
        '<p class="muted small">Provide a strong temporary password via a secure channel. It is never returned by this API.</p>' +
        '<form id="server-user-create"><label>Username<input name="username" maxlength="150" required autocomplete="off"></label>' +
        '<label>Email (optional)<input name="email" type="email" maxlength="254"></label>' +
        '<label>Initial password<input name="password" type="password" required autocomplete="new-password"></label>' +
        '<fieldset><legend>Initial roles</legend>' + checkboxes(["user"]) + '</fieldset>' +
        '<button type="submit">Create account</button><button id="server-user-create-cancel" type="button">Cancel</button></form></section>' +
        '<div class="server-card"><h3>Recent access audit (last 100 events)</h3>' +
        '<button type="button" id="server-users-audit">Show audit events</button>' +
        '<pre id="server-users-audit-log" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></div>';
      el("#server-user-open-create").addEventListener("click", function () {
        el("#server-user-create-panel").hidden = false;
      });
      el("#server-user-create-cancel").addEventListener("click", function () {
        el("#server-user-create-panel").hidden = true;
      });
      el("#server-users-reload").addEventListener("click", refresh);
      el("#server-users-search").addEventListener("submit", function (event) {
        event.preventDefault();
        var f = event.target; search = f.elements.query.value.trim();
        filter = f.elements.status.value; page = 1; refresh();
      });
      el("#server-user-create").addEventListener("submit", async function (event) {
        event.preventDefault();
        var f = event.target, button = f.querySelector('button[type="submit"]');
        button.disabled = true;
        try {
          await request("", "POST", {username: f.elements.username.value,
            email: f.elements.email.value, password: f.elements.password.value,
            roles: getRoles(f)});
          f.reset();
          el("#server-user-create-panel").hidden = true;
          text("Account created. Distribute its initial credential securely.", false);
          await refresh();
        } catch (error) { text("Create refused: " + error.message, true); }
        finally { button.disabled = false; f.elements.password.value = ""; }
      });
      el("#server-users-audit").addEventListener("click", async function () {
        var token = epoch;
        try {
          var data = await request("/audit");
          if (token !== epoch || !enabled) return;
          el("#server-users-audit-log").textContent = data.results.map(function (x) {
            return x.at + "  " + x.actor + " → " + x.subject + "  " + x.action + "  " + JSON.stringify(x.details);
          }).join("\n") || "No access changes yet.";
        } catch (error) { text("Audit unavailable: " + error.message, true); }
      });
      el("#server-users-list").addEventListener("click", function (event) {
        var button = event.target.closest("button[data-id]");
        if (!button) return;
        var row = rows.find(function (x) { return String(x.id) === button.dataset.id; });
        if (row) openEdit(row);
      });
    }
    function openEdit(row) {
      var editor = el("#server-users-editor");
      editor.hidden = false;
      editor.innerHTML = '<h3>Manage ' + escapeHtml(row.username) + '</h3>' +
        '<p class="muted small">Changes take effect on the next authenticated request.</p>' +
        '<form id="server-user-edit"><label><input style="display:inline;width:auto" type="checkbox" name="active"' +
        (row.active ? ' checked' : '') + '> Active account</label>' +
        '<fieldset><legend>Role grants</legend>' + checkboxes(row.roles) + '</fieldset>' +
        '<label>Reset credential (leave blank to preserve)<input name="password" type="password" autocomplete="new-password"></label>' +
        '<button type="submit">Save account changes</button><button id="server-user-cancel" type="button">Cancel</button></form>';
      el("#server-user-cancel").addEventListener("click", function () { editor.hidden = true; });
      el("#server-user-edit").addEventListener("submit", async function (event) {
        event.preventDefault();
        var f = event.target, button = f.querySelector('button[type="submit"]');
        var payload = {active: f.elements.active.checked, roles: getRoles(f)};
        if (f.elements.password.value) payload.password = f.elements.password.value;
        button.disabled = true;
        try {
          await request("/" + encodeURIComponent(row.id), "PATCH", payload);
          editor.hidden = true;
          await refresh();
        } catch (error) { text("Update refused: " + error.message, true); }
        finally { button.disabled = false; f.elements.password.value = ""; }
      });
      editor.scrollIntoView({block:"nearest", behavior:"smooth"});
    }
    async function refresh() {
      if (!enabled) return;
      var token = ++epoch;
      text("Loading accounts…", false);
      try {
        var data = await request("?search=" + encodeURIComponent(search) +
          "&status=" + encodeURIComponent(filter) + "&page=" + page);
        if (token !== epoch || !enabled) return;
        rows = data.results; roles = data.available_roles || roles;
        el("#server-users-list").innerHTML = '<h3>Accounts (' + data.total + ')</h3>' +
          (rows.length ? rows.map(function (user) {
            return '<div class="list-row" style="display:flex;justify-content:space-between;gap:10px;align-items:center">' +
              '<div><strong>' + escapeHtml(user.username) + '</strong> · ' +
              escapeHtml(user.active ? "active" : "disabled") +
              '<div class="muted small">' + escapeHtml(user.email || "") +
              ' · ' + escapeHtml(user.roles.join(", ") || "no roles") + '</div></div>' +
              '<button type="button" data-id="' + escapeHtml(user.id) + '">Manage</button></div>';
          }).join("") : '<p>No matching accounts.</p>') +
          '<div class="server-actions"><button type="button" id="server-users-prev"' +
          (page <= 1 ? " disabled" : "") + '>Previous</button><span> Page ' + page + '</span>' +
          '<button type="button" id="server-users-next"' +
          (page * data.page_size >= data.total ? " disabled" : "") + '>Next</button></div>';
        el("#server-users-prev").addEventListener("click", function () { page--; refresh(); });
        el("#server-users-next").addEventListener("click", function () { page++; refresh(); });
        text("Accounts loaded. All updates are audited.", false);
      } catch (error) {
        if (token !== epoch || !enabled) return;
        rows = [];
        el("#server-users-list").textContent = "Cannot load user records.";
        text("Access unavailable: " + error.message, true);
      }
    }
    function setAccess(canManage, canManagePlatform) {
      ++epoch;
      enabled = !!canManage;
      platform = !!canManagePlatform;
      root.hidden = !enabled;
      root.replaceChildren(); rows = [];
      if (enabled) { render(); refresh(); }
    }
    root.hidden = true;
    return {setAccess:setAccess};
  }
  window.AICompassServerUsers = {mount:mount};
})();
