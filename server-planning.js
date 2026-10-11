/* DAP-01: confidential Server-only workload planning. Demo never mounts. */
(function () {
  "use strict";
  function mount(root, csrf, E) {
    var canView = false, canWrite = false, profiles = [], tasks = [], generation = 0;
    root.innerHTML = '<div class="server-card"><h2>Deployment Planning · Workload foundations</h2>' +
      '<p>Annual role/specialty and cohort workload assumptions. No profit or observed savings are inferred.</p>' +
      '<p id="planning-state" role="status" class="server-status"></p>' +
      '<button id="planning-refresh" type="button">Refresh profiles</button>' +
      '<button id="planning-new" type="button">New profile</button>' +
      '<div id="planning-list"></div><div id="planning-editor" hidden></div>' +
      '<div id="planning-detail"></div><section id="planning-opportunities"></section></div>';
    var status = root.querySelector("#planning-state");
    var list = root.querySelector("#planning-list");
    var editor = root.querySelector("#planning-editor");
    var detail = root.querySelector("#planning-detail");
    var add = root.querySelector("#planning-new");
    var opportunities = window.AICompassOpportunities.mount(
      root.querySelector("#planning-opportunities"),
      window.AICompassOpportunities.serverProvider(fetch, csrf), "server");
    function tell(message, error) {
      status.textContent = message;
      status.className = error ? "server-status server-error" : "server-status";
    }
    async function api(path, method, body) {
      var options = {method: method || "GET", credentials: "same-origin", cache: "no-store"};
      if (body !== undefined) {
        options.headers = {"Content-Type": "application/json", "X-CSRFToken": csrf()};
        options.body = JSON.stringify(body);
      }
      var response = await fetch("/api/v1/planning/" + path, options);
      var data = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        var error = new Error(data.detail || data.error || "HTTP " + response.status);
        error.status = response.status;
        throw error;
      }
      return data;
    }
    function choice(rows, selected, empty) {
      return '<option value="">' + E(empty || "None") + '</option>' +
        rows.map(function (p) {
          return '<option value="' + E(p.id) + '"' + (p.id === selected ? ' selected' : '') +
            '>' + E(p.name) + ' · ' + E(p.id) + '</option>';
        }).join("");
    }
    function workloadLine(row) {
      row = row || {};
      return '<div class="planning-line" style="display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin:8px 0">' +
        '<label>Task <select name="task_id" required>' +
        choice(tasks, row.task_id, "Choose a Task") + '</select></label>' +
        '<label>Annual occurrences (empty = unknown)' +
        '<input name="frequency" inputmode="decimal" type="number" min="0" step=".01" value="' +
        E(row.annual_occurrences == null ? "" : row.annual_occurrences) + '"></label>' +
        '<label>Baseline human hours / occurrence' +
        '<input name="hours" inputmode="decimal" type="number" min="0" step=".01" value="' +
        E(row.baseline_human_hours == null ? "" : row.baseline_human_hours) + '"></label>' +
        '<label><input name="excluded" type="checkbox"' + (row.excluded ? " checked" : "") +
        '> Excluded</label>' +
        '<button class="planning-remove" type="button">Remove</button></div>';
    }
    function form(profile) {
      if (!canWrite) return;
      var original = profile || null;
      detail.replaceChildren();
      editor.hidden = false;
      var kind = original ? original.kind : "role";
      editor.innerHTML = '<form id="planning-form"><h3>' + (original ? "Revise" : "Create") +
        ' planning profile</h3>' +
        '<label>Type <select name="kind"' + (original ? " disabled" : "") + '>' +
        [["role","Job role"],["specialty","Specialty"],["person","Person"],["cohort","Cohort"]]
          .map(function (item) { return '<option value="' + item[0] + '"' +
            (item[0] === kind ? ' selected' : '') + '>' + item[1] + '</option>'; }).join("") +
        '</select></label>' +
        '<label>Display name<input name="name" required maxlength="160" value="' + E(original ? original.name : "") + '"></label>' +
        '<label>Inherit from Job role<select name="role_id">' +
        choice(profiles.filter(function (x) { return x.kind === "role"; }), original && original.role_id) +
        '</select></label>' +
        '<label>Inherit from Specialty<select name="specialty_id">' +
        choice(profiles.filter(function (x) { return x.kind === "specialty"; }), original && original.specialty_id) +
        '</select></label>' +
        '<label>Cohort headcount (person/role/specialty = 1)' +
        '<input name="headcount" type="number" min="1" max="100000" step="1" value="' +
        E(original ? String(original.headcount) : "1") + '"></label>' +
        '<label>Hourly labor valuation EUR (empty = unknown)<input name="rate" type="number" min="0" step=".01" value="' +
        E(original && original.hourly_rate_eur != null ? original.hourly_rate_eur : "") + '"></label>' +
        '<label>AI Compass account numeric ID (person only, optional)<input name="linked_user_id" type="number" min="1" step="1" value="' +
        E(original && original.linked_user_id != null ? String(original.linked_user_id) : "") + '"></label>' +
        '<h4>Task workloads</h4><p>Each row replaces an inherited Task. Unknown is empty; 0 is an explicit zero. No Tasks are summed automatically.</p>' +
        '<div id="planning-lines">' + ((original && original.workloads) || []).map(workloadLine).join("") + '</div>' +
        '<button type="button" id="planning-add-line">Add Task</button>' +
        '<button type="submit">Save version</button><button type="button" id="planning-cancel">Cancel</button></form>';
      var formElement = editor.querySelector("#planning-form");
      function updateOptions() {
        var selectedKind = formElement.elements.kind.value;
        formElement.elements.role_id.disabled = !["person", "cohort"].includes(selectedKind);
        formElement.elements.specialty_id.disabled = !["person", "cohort"].includes(selectedKind);
        formElement.elements.headcount.disabled = selectedKind !== "cohort";
        formElement.elements.linked_user_id.disabled = selectedKind !== "person";
      }
      formElement.elements.kind.addEventListener("change", updateOptions);
      updateOptions();
      editor.querySelector("#planning-add-line").addEventListener("click", function () {
        editor.querySelector("#planning-lines").insertAdjacentHTML("beforeend", workloadLine({}));
      });
      editor.querySelector("#planning-lines").addEventListener("click", function (event) {
        if (event.target.classList.contains("planning-remove")) event.target.closest(".planning-line").remove();
      });
      editor.querySelector("#planning-cancel").addEventListener("click", function () { editor.hidden = true; });
      formElement.addEventListener("submit", async function (event) {
        event.preventDefault();
        var values = Object.fromEntries(new FormData(formElement).entries());
        var lines = Array.from(formElement.querySelectorAll(".planning-line")).map(function (element) {
          var task = element.querySelector('[name="task_id"]').value;
          var frequency = element.querySelector('[name="frequency"]').value.trim();
          var hours = element.querySelector('[name="hours"]').value.trim();
          return {task_id: task, annual_occurrences: frequency === "" ? null : frequency,
                  baseline_human_hours: hours === "" ? null : hours,
                  excluded: element.querySelector('[name="excluded"]').checked};
        });
        var payload = {name: values.name, role_id: values.role_id || null,
          specialty_id: values.specialty_id || null,
          linked_user_id: values.linked_user_id ? Number(values.linked_user_id) : null,
          headcount: kind === "cohort" ? Number(values.headcount) : 1,
          hourly_rate_eur: values.rate === "" ? null : values.rate,
          workloads: lines, notes: original ? original.notes : {}};
        if (original) payload.expected_revision = original.revision;
        else payload.kind = values.kind;
        var submit = formElement.querySelector('button[type="submit"]');
        submit.disabled = true;
        try {
          var saved = await api("profiles" + (original ? "/" + original.id : ""),
                                original ? "PATCH" : "POST", payload);
          editor.hidden = true;
          await refresh(saved.id);
        } catch (error) {
          tell((error.status === 409 ? "Version conflict. " : "") +
               "Save refused: " + error.message, true);
        } finally { submit.disabled = false; }
      });
    }
    function table(effective) {
      var rows = effective.workloads;
      return '<h4>Effective annual Task workload</h4>' +
        '<p>Applied profile headcount: ' + E(String(effective.headcount)) +
        ' · hourly valuation: ' +
        E(effective.hourly_rate_source ? effective.hourly_rate_source.rate_eur + " EUR/h" : "unknown") +
        '. Prospective gains are not calculated yet.</p>' +
        '<div style="overflow-x:auto"><table style="width:100%;border-collapse:collapse">' +
        '<thead><tr><th>Task</th><th>Annual / person</th><th>Annual / cohort</th><th>Baseline hours</th><th>Source</th><th>State</th></tr></thead><tbody>' +
        rows.map(function (x) {
          return '<tr><td>' + E(x.task_name) + ' <small>' + E(x.task_id) + '</small></td>' +
            '<td>' + E(x.annual_occurrences === null ? "unknown" : x.annual_occurrences) +
            '</td><td>' + E(x.annual_person_occurrences === null ? "unknown" : x.annual_person_occurrences) +
            '</td><td>' + E(x.baseline_human_hours === null ? "unknown" : x.baseline_human_hours) +
            '</td><td>' + E(x.source) + '</td><td>' + E(x.status) +
            (x.overlaps_ancestor_task ? " · overlaps ancestor" : "") +
            '</td></tr>';
        }).join("") +
        '</tbody></table></div>' +
        '<p>' + E(effective.warnings.filter(Boolean).join("; ") || "No detected Task aggregation conflict") + '</p>';
    }
    async function select(id) {
      try {
        var profile = profiles.find(function (x) { return x.id === id; });
        var response = await Promise.all([
          api("profiles/" + id + "/effective"), api("profiles/" + id + "/revisions")]);
        if (!canView || !profiles.some(function (x) { return x.id === id; })) return;
        editor.hidden = true;
        detail.innerHTML = '<h3>' + E(profile.name) + ' · ' + E(profile.revision) + '</h3>' +
          (canWrite ? '<button id="planning-edit" type="button">Revise this profile</button>' : '') +
          '<button id="planning-history" type="button">Version history</button>' +
          table(response[0]) + '<pre id="planning-versions" hidden style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>';
        if (canWrite) detail.querySelector("#planning-edit").addEventListener("click", function () { form(profile); });
        detail.querySelector("#planning-history").addEventListener("click", function () {
          var target = detail.querySelector("#planning-versions");
          target.hidden = !target.hidden;
          target.textContent = JSON.stringify(response[1].revisions, null, 2);
        });
      } catch (error) { tell("Effective profile unavailable: " + error.message, true); }
    }
    function render() {
      list.innerHTML = profiles.length ?
        '<div style="display:flex;gap:8px;flex-wrap:wrap">' + profiles.map(function (x) {
          return '<button type="button" data-id="' + E(x.id) + '">' +
            E(x.kind + ": " + x.name + " · " + x.revision) + '</button>';
        }).join("") + '</div>' :
        '<p>No real planning profiles yet. Start by defining a Job Role or Specialty.</p>';
      add.hidden = !canWrite;
    }
    async function refresh(selected) {
      var token = ++generation;
      tell("Loading confidential Server planning data…", false);
      try {
        var results = await Promise.all([api("profiles"), api("tasks")]);
        if (token !== generation || !canView) return;
        profiles = results[0].results;
        tasks = results[1].results;
        render();
        tell(profiles.length + " versioned Server profiles loaded.", false);
        if (selected) select(selected);
      } catch (error) {
        if (token !== generation) return;
        profiles = []; tasks = []; list.replaceChildren(); detail.replaceChildren();
        tell("Planning unavailable: " + error.message + ". No Demo fallback.", true);
      }
    }
    root.querySelector("#planning-refresh").addEventListener("click", function () { refresh(); });
    add.addEventListener("click", function () { form(null); });
    list.addEventListener("click", function (event) {
      var target = event.target.closest("[data-id]");
      if (target) select(target.dataset.id);
    });
    return {setAccess: function (read, write) {
      canView = Boolean(read); canWrite = Boolean(write);
      opportunities.setAccess(canView,canWrite);
      root.hidden = !canView; generation++;
      if (canView) refresh();
      else {profiles = []; tasks = []; editor.hidden = true; list.replaceChildren();
            detail.replaceChildren(); tell("", false);}
    }};
  }
  window.AICompassServerPlanning = {mount: mount};
})();
