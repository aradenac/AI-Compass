/* PLAT-24: Server-only Activity Feed. Never accesses Demo storage. */
(function () {
  "use strict";

  function mount(root, escapeHtml) {
    var allowed = false, business = false, users = false, ticket = 0, page = 1;
    var filters = {type:"all", actor:"", action:"", from:"", to:""};
    var events = [];

    function el(selector) { return root.querySelector(selector); }
    function status(message, error) {
      var box = el("#activity-status");
      if (box) { box.textContent = message; box.className = error ? "server-status server-error" : "server-status"; }
    }
    function query() {
      var params = new URLSearchParams();
      Object.keys(filters).forEach(function (k) {
        if (filters[k] && !(k === "type" && filters[k] === "all"))
          params.set(k, filters[k]);
      });
      return params;
    }
    async function request(path) {
      var response = await fetch("/api/v1/activity" + path,
        {credentials:"same-origin", cache:"no-store"});
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok) throw new Error(data.error || "HTTP " + response.status);
      return data;
    }
    function option(value, label) {
      return '<option value="' + escapeHtml(value) + '"' +
        (filters.type === value ? ' selected' : '') + '>' + escapeHtml(label) + '</option>';
    }
    function build() {
      root.innerHTML =
        '<div class="server-model-toolbar"><div><h2>Activity Feed</h2>' +
        '<p class="muted small">Persistent, attributed backend events. Newest first; no Demo records.</p></div>' +
        '<button id="activity-refresh" type="button">Refresh</button></div>' +
        '<form id="activity-filters" class="server-card" style="margin-bottom:12px">' +
        '<label>Object type<select name="type">' +
        option("all", "All permitted events") +
        (business ? ["model","provider","harness","framework","task"].map(function(x){return option(x,x);}).join("") : "") +
        (users ? option("access", "Account administration") : "") +
        '</select></label>' +
        '<label>Actor (exact username)<input name="actor" maxlength="150" value="' + escapeHtml(filters.actor) + '"></label>' +
        '<label>Operation (optional)<input name="action" maxlength="32" value="' + escapeHtml(filters.action) + '"></label>' +
        '<div style="display:flex;flex-wrap:wrap;gap:14px">' +
        '<label>From (UTC)<input name="from" type="datetime-local"></label>' +
        '<label>To (UTC)<input name="to" type="datetime-local"></label></div>' +
        '<button type="submit">Apply filters</button></form>' +
        '<p id="activity-status" role="status" class="server-status"></p>' +
        '<div id="activity-list" class="server-card"></div>' +
        '<div class="server-actions"><button id="activity-prev" type="button">Previous</button>' +
        '<span id="activity-page"></span> <button id="activity-next" type="button">Next</button></div>' +
        '<div class="server-actions"><a id="activity-export-json" href="#">Export filtered JSON</a> · ' +
        '<a id="activity-export-csv" href="#">Export filtered CSV</a></div>' +
        '<pre id="activity-detail" class="server-card" hidden style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>';

      el("#activity-filters").elements.from.value = filters.from ? filters.from.slice(0,16) : "";
      el("#activity-filters").elements.to.value = filters.to ? filters.to.slice(0,16) : "";
      el("#activity-refresh").addEventListener("click", refresh);
      el("#activity-filters").addEventListener("submit", function (event) {
        event.preventDefault();
        var form = event.target;
        filters = {
          type: form.elements.type.value,
          actor: form.elements.actor.value.trim(),
          action: form.elements.action.value.trim(),
          from: form.elements.from.value ? form.elements.from.value + ":00Z" : "",
          to: form.elements.to.value ? form.elements.to.value + ":00Z" : "",
        };
        page = 1; refresh();
      });
      el("#activity-prev").addEventListener("click", function () {
        if (page > 1) { page--; refresh(); }
      });
      el("#activity-next").addEventListener("click", function () { page++; refresh(); });
      el("#activity-list").addEventListener("click", async function(event) {
        var button = event.target.closest("button[data-event]");
        if (!button) return;
        var id = button.dataset.event, generation = ticket;
        var target = el("#activity-detail");
        target.hidden = false; target.textContent = "Loading source event…";
        try {
          var data = await request("/" + encodeURIComponent(id));
          if (!allowed || generation !== ticket) return;
          target.textContent = JSON.stringify(data, null, 2);
        } catch (error) {
          if (generation !== ticket || !allowed) return;
          target.textContent = "Event unavailable: " + error.message;
        }
      });
      updateExportLinks();
    }
    function updateExportLinks() {
      ["json","csv"].forEach(function(format) {
        var params = query(); params.set("format", format);
        el("#activity-export-" + format).href = "/api/v1/activity/export?" + params.toString();
      });
    }
    async function refresh() {
      if (!allowed) return;
      var generation = ++ticket;
      status("Loading real Server audit records…");
      el("#activity-detail").hidden = true;
      updateExportLinks();
      var params = query(); params.set("page", String(page));
      try {
        var data = await request("?" + params.toString());
        if (!allowed || generation !== ticket) return;
        events = data.results || [];
        el("#activity-list").innerHTML = events.length ? events.map(function(e) {
          return '<div class="list-row" style="display:flex;justify-content:space-between;gap:12px">' +
            '<div><strong>' + escapeHtml(e.operation) + '</strong> · ' +
            escapeHtml(e.object_type) + ' · ' + escapeHtml(e.object_name || e.object_id) +
            '<div class="muted small">' + escapeHtml(e.actor) + ' · ' + escapeHtml(e.occurred_at) +
            ' · ' + escapeHtml(e.revision || "no revision") + '</div></div>' +
            '<button type="button" data-event="' + escapeHtml(e.id) + '">Details</button></div>';
        }).join("") : "<p>No matching activity records.</p>";
        el("#activity-page").textContent = " Page " + page;
        el("#activity-prev").disabled = page <= 1;
        el("#activity-next").disabled = !data.has_more;
        status(events.length + " event(s) on this page" +
          (data.limited ? ". Narrow filters for events beyond the 1,000-entry window." : "") + ".");
      } catch (error) {
        if (!allowed || generation !== ticket) return;
        events = [];
        el("#activity-list").textContent = "No authorized Server records available.";
        el("#activity-next").disabled = true;
        status("Activity unavailable: " + error.message, true);
      }
    }
    function setAccess(readBusiness, manageUsers) {
      ticket++;
      business = !!readBusiness;
      users = !!manageUsers;
      allowed = business || users;
      events = [];
      root.replaceChildren();
      root.hidden = !allowed;
      filters = {type:"all", actor:"", action:"", from:"", to:""};
      page = 1;
      if (allowed) { build(); refresh(); }
    }
    root.hidden = true;
    return {setAccess:setAccess};
  }
  window.AICompassServerActivity = {mount:mount};
})();
