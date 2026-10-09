/* PLAT-27: isolated maintenance-only Data Health workspace. No Demo state. */
(function () {
  "use strict";
  function mount(root, csrf, escapeHtml) {
    var allowed = false, canTriage = false, ticket = 0, page = 1, filter = "open", selected = null;
    function el(s) { return root.querySelector(s); }
    function notice(s, error) {
      var node = el("#health-status");
      if (node) { node.textContent = s; node.className = error ? "server-status server-error" : "server-status"; }
    }
    async function req(path, method, data) {
      var options = {method: method || "GET", cache: "no-store", credentials: "same-origin"};
      if (method && method !== "GET") {
        options.headers = {"Content-Type":"application/json","X-CSRFToken":csrf()};
        options.body = JSON.stringify(data || {});
      }
      var response = await fetch("/api/v1/maintenance/" + path, options);
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok) throw Error(payload.error || "HTTP " + response.status);
      return payload;
    }
    function build() {
      root.innerHTML =
        '<div class="server-model-toolbar"><div><h2>Maintenance & Governance · Data Health</h2>' +
        '<p class="muted small">Independent read-only diagnostics of current Server records. ' +
        'No business data editing or original evidence downloads here.</p></div>' +
        '<button type="button" id="health-refresh">Refresh</button></div>' +
        '<p id="health-status" class="server-status" role="status"></p>' +
        '<section id="health-summary" class="server-card" style="margin:14px 0"></section>' +
        '<div class="server-card" style="margin:14px 0"><div class="server-model-toolbar">' +
        '<h3>Detected issues</h3>' +
        (canTriage ? '<button type="button" id="health-scan">Run checks now</button>' : "") +
        '</div><label>Status filter <select id="health-filter">' +
        ["open","exception","resolved","all"].map(function (s) {
          return '<option value="' + s + '"' + (s === filter ? " selected" : "") + '>' + s + '</option>';
        }).join("") + '</select></label><div id="health-list"></div>' +
        '<div class="server-actions"><button id="health-prev" type="button">Previous</button> ' +
        '<span id="health-page"></span> <button id="health-next" type="button">Next</button></div></div>' +
        '<section id="health-detail" class="server-card" style="margin:14px 0" hidden></section>' +
        '<div class="server-card" style="margin-top:14px"><h3>Schema migration</h3>' +
        '<p>Migration previews are operator-driven and remain gated by accepted staging ' +
        'inspection and a verified recovery point. No production apply is exposed here.</p>' +
        '<button type="button" id="health-migrations">View migration prerequisites</button>' +
        '<pre id="health-migration-info" style="white-space:pre-wrap"></pre></div>';
      el("#health-refresh").addEventListener("click", refresh);
      el("#health-filter").addEventListener("change", function () {
        filter = this.value; page = 1; refresh();
      });
      el("#health-prev").addEventListener("click", function () { if (page > 1) { page--; refresh(); } });
      el("#health-next").addEventListener("click", function () { page++; refresh(); });
      if (canTriage) el("#health-scan").addEventListener("click", async function () {
        this.disabled = true;
        notice("Scanning current Server records. No business mutations are performed.");
        try { await req("scan","POST",{}); await refresh(); }
        catch (e) { notice("Scan failed: " + e.message, true); }
        finally { if (allowed && el("#health-scan")) el("#health-scan").disabled = false; }
      });
      el("#health-list").addEventListener("click", function (event) {
        var button = event.target.closest("button[data-health]");
        if (button) detail(button.dataset.health);
      });
      el("#health-migrations").addEventListener("click",async function() {
        try {
          var data = await req("migrations");
          if (allowed && el("#health-migration-info")) {
            el("#health-migration-info").textContent = JSON.stringify(data,null,2);
          }
        } catch(e) { notice("Migration prerequisites unavailable: "+e.message,true); }
      });
    }
    function line(row) {
      return '<div class="list-row" style="display:flex;justify-content:space-between;gap:12px">' +
        '<div><strong>' + escapeHtml(row.id) + '</strong> · ' +
        escapeHtml(row.severity) + ' · ' + escapeHtml(row.status) +
        '<div>' + escapeHtml(row.summary) + '</div>' +
        '<div class="muted small">' + escapeHtml(row.category) + ' · ' +
        escapeHtml(row.subject_type) + ' · ' +
        escapeHtml(row.subject_id || "restricted reference") +
        ' · detected ' + escapeHtml(row.detection_count) + ' time(s)</div></div>' +
        '<button type="button" data-health="' + escapeHtml(row.id) + '">Inspect</button></div>';
    }
    async function refresh() {
      if (!allowed) return;
      var current = ++ticket;
      notice("Loading Data Health…");
      try {
        var results = await Promise.all([req("health"),req("issues?status=" + filter + "&page=" + page)]);
        if (!allowed || current !== ticket) return;
        var totals = results[0], data = results[1];
        el("#health-summary").innerHTML =
          '<strong>' + escapeHtml(totals.open) + ' open · ' +
          escapeHtml(totals.exceptions) + ' exceptions · ' +
          escapeHtml(totals.resolved) + ' resolved</strong>' +
          '<div class="muted small">' + escapeHtml(totals.total) + ' tracked issues</div>';
        el("#health-list").innerHTML = data.results.length ?
          data.results.map(line).join("") : "<p>No issues matching these filters.</p>";
        el("#health-page").textContent = "Page " + page + " · " + data.total + " matching";
        el("#health-prev").disabled = page === 1;
        el("#health-next").disabled = page * data.page_size >= data.total;
        notice("Live maintenance records loaded.");
      } catch(e) {
        if (!allowed || current !== ticket) return;
        el("#health-list").textContent = "No authorized maintenance records available.";
        notice("Maintenance unavailable: " + e.message,true);
      }
    }
    async function detail(id) {
      var current = ticket;
      var container = el("#health-detail");
      container.hidden = false; container.textContent = "Loading issue history…";
      try {
        var payload = await req("issues/" + encodeURIComponent(id));
        if (!allowed || ticket !== current || !el("#health-detail")) return;
        var i = payload.issue; selected = id;
        container = el("#health-detail");
        container.innerHTML = '<h3>' + escapeHtml(i.id) + '</h3>' +
          '<p>' + escapeHtml(i.summary) + '</p>' +
          '<p class="muted small">' + escapeHtml(i.category) + ' · ' +
          escapeHtml(i.severity) + ' · ' + escapeHtml(i.status) + '</p>' +
          '<p>Assignee: ' + escapeHtml(i.assigned_to || "Unassigned") + '</p>' +
          (i.exception_rationale ? '<p>Exception: ' + escapeHtml(i.exception_rationale) +
            ' · review ' + escapeHtml(i.review_after) + '</p>' : "") +
          (canTriage ? '<form id="health-triage">' +
            '<label>Status <select name="status">' +
            ["open","resolved","exception"].map(function(s){
              return '<option value="' + s + '"' + (s === i.status ? " selected" : "") + '>' + s + '</option>';
            }).join("") + '</select></label>' +
            '<label>Assign to active maintainer (username, blank clears)<input name="assigned_to" ' +
            'maxlength="150" value="' + escapeHtml(i.assigned_to || "") + '"></label>' +
            '<label>Exception rationale<input name="rationale" maxlength="1200" ' +
            'value="' + escapeHtml(i.exception_rationale || "") + '"></label>' +
            '<label>Review on (exception only)<input name="review_after" type="date" ' +
            'value="' + escapeHtml(i.review_after || "") + '"></label>' +
            '<button type="submit">Save disposition</button></form>' : "") +
          '<h4>Immutable event history</h4><pre id="health-history" ' +
          'style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>';
        el("#health-history").textContent = payload.history.map(function(event){
          return event.at + " · " + event.actor + " · " + event.action +
            " · " + JSON.stringify(event.detail);
        }).join("\n") || "No events";
        if (canTriage) el("#health-triage").addEventListener("submit",async function(event) {
          event.preventDefault();
          var f = event.target, button = f.querySelector('button[type="submit"]');
          var data = {status:f.elements.status.value,
            assigned_to:f.elements.assigned_to.value.trim() || null};
          if (data.status === "exception") {
            data.rationale = f.elements.rationale.value.trim();
            data.review_after = f.elements.review_after.value;
          }
          button.disabled = true;
          try {
            await req("issues/"+encodeURIComponent(id)+"/triage","PATCH",data);
            await refresh(); await detail(id);
          } catch(e) { notice("Disposition refused: "+e.message,true); }
          finally { button.disabled = false; }
        });
      } catch(e) {
        if (allowed && current === ticket && el("#health-detail"))
          el("#health-detail").textContent = "Detail unavailable: " + e.message;
      }
    }
    function setAccess(canView, canEdit) {
      ++ticket;
      allowed = !!canView;
      canTriage = !!canView && !!canEdit;
      page = 1; filter = "open"; selected = null;
      root.replaceChildren();
      root.hidden = !allowed;
      if (allowed) { build(); refresh(); }
    }
    root.hidden = true;
    return {setAccess:setAccess};
  }
  window.AICompassServerDataHealth = {mount:mount};
})();
