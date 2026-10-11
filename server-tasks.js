/* FUT-03: one Task tree/editor/history presentation in both modes; provider is selected at bootstrap. */
(function () {
  "use strict";

  function mount(root, csrf, escapeHtml, provider) {
    var rows = [], canRead = false, canWrite = false, generation = 0;
    var state = root.querySelector("#server-task-state");
    var tree = root.querySelector("#server-task-list");
    var editor = root.querySelector("#server-task-editor");
    var history = root.querySelector("#server-task-history");
    var E = escapeHtml;

    // One shared loading/read/refused presentation in Demo and Server.
    function report(message, error) {
      if (!state) return;
      state.className = error ? "server-status server-error" : "server-status";
      state.innerHTML = window.AICompassWorkgroup.renderDomainStatus({
        mode: provider ? "demo" : "server",
        state: error ? "error" : "ok",
        message: message == null ? "" : String(message)
      });
    }

    async function api(url, method, data) {
      if (provider) return provider.tasks.request(url, method, data);
      if (window.AICompassRuntime) {
        return window.AICompassRuntime.ServerTransport(fetch, csrf)
          .request("/api/v1/tasks" + url, method, data);
      }
      var opts = {method: method || "GET", credentials: "same-origin", cache: "no-store"};
      if (method && method !== "GET") {
        opts.headers = {"Content-Type": "application/json", "X-CSRFToken": csrf()};
        opts.body = JSON.stringify(data);
      }
      var response = await fetch("/api/v1/tasks" + url, opts);
      var payload = await response.json().catch(function () { return {}; });
      if (!response.ok) {
        var error = new Error(payload.detail || payload.error || "HTTP " + response.status);
        error.status = response.status;
        throw error;
      }
      return payload;
    }

    function siblingRows(parent) {
      return rows.filter(function (node) { return node.parent_id === parent; })
        .sort(function (a, b) { return a.position - b.position || a.id.localeCompare(b.id); });
    }

    function subtreeContains(id, candidate) {
      var cursor = rows.find(function (row) { return row.id === candidate; }), seen = new Set();
      while (cursor && !seen.has(cursor.id)) {
        if (cursor.id === id) return true;
        seen.add(cursor.id);
        cursor = rows.find(function (row) { return row.id === cursor.parent_id; });
      }
      return false;
    }

    function treeHtml(parent, depth, seen) {
      return siblingRows(parent).map(function (node) {
        if (seen.has(node.id)) return "";
        var branch = new Set(seen); branch.add(node.id);
        var siblings = siblingRows(parent), index = siblings.findIndex(function (n) { return n.id === node.id; });
        return '<div class="server-task-node" style="margin-left:' + (depth * 20) +
          'px;padding:9px 5px;border-bottom:1px solid #e3e8f0">' +
          '<strong>' + E(node.name) + '</strong> <small>' + E(node.id) + " · " + E(node.revision) +
          '</small><div class="server-model-actions">' +
          '<button type="button" data-task-action="select" data-id="' + E(node.id) + '">Inspect</button>' +
          '<button type="button" data-task-action="history" data-id="' + E(node.id) + '">History</button>' +
          (canWrite ?
            '<button type="button" data-task-action="edit" data-id="' + E(node.id) + '">Edit / move</button>' +
            '<button type="button" data-task-action="add" data-id="' + E(node.id) + '">+ Child</button>' +
            (index > 0 ? '<button type="button" data-task-action="up" data-id="' + E(node.id) + '">↑</button>' : "") +
            (index < siblings.length - 1 ? '<button type="button" data-task-action="down" data-id="' + E(node.id) + '">↓</button>' : "")
            : "") + '</div></div>' +
          treeHtml(node.id, depth + 1, branch);
      }).join("");
    }

    function render() {
      tree.innerHTML = rows.length ? treeHtml(null, 0, new Set()) :
        '<p>No real task nodes exist yet. Create the first root section in Server.</p>';
      root.querySelector("#server-task-add-root").hidden = !canWrite;
    }

    async function refresh() {
      if (!canRead) return;
      var ticket = ++generation;
      report("Loading " + (provider ? "fictional Demo" : "authoritative Server") + " tasks…");
      try {
        var result = await api("");
        if (ticket !== generation || root.hidden) return;
        if (!Array.isArray(result.results)) throw Error("Invalid Server task response");
        rows = result.results;
        render();
        report(rows.length + " task node(s). Each identity and revision is retained.");
      } catch (error) {
        if (ticket !== generation) return;
        rows = []; tree.replaceChildren();
        report("Task tree unavailable: " + error.message + ". No cross-mode fallback.", true);
      }
    }

    function editorForm(item, parentId) {
      if (!canWrite) return;
      history.hidden = true;
      var p = item ? item.properties : {};
      var other = {};
      Object.keys(p).forEach(function (key) {
        if (!["phase", "domain", "baseline", "status", "desc", "criteria"].includes(key))
          other[key] = p[key];
      });
      var excluded = rows.filter(function (row) { return item && subtreeContains(item.id, row.id); });
      var options = [{id: "", name: "Top-level section"}].concat(rows.filter(function (node) {
        return !excluded.some(function (e) { return e.id === node.id; });
      }));
      editor.hidden = false;
      editor.innerHTML = '<h3>' + (item ? "Edit / reparent" : "Create") + ' task</h3>' +
        '<p class="muted small">A saved change appends an immutable history entry. Unknown JSON properties are retained.</p>' +
        '<form id="server-task-form">' +
        '<label>Name<input name="name" maxlength="160" required value="' + E(item ? item.name : "") + '"></label>' +
        '<label>Parent node<select name="parent_id">' + options.map(function (row) {
          return '<option value="' + E(row.id) + '"' +
            (row.id === (item ? item.parent_id || "" : parentId || "") ? " selected" : "") +
            '>' + E(row.name) + (row.id ? " (" + E(row.id) + ")" : "") + '</option>';
        }).join("") + '</select></label>' +
        '<label>Engineering phase<input name="phase" value="' + E(p.phase || "") + '"></label>' +
        '<label>Domain<input name="domain" value="' + E(p.domain || "") + '"></label>' +
        '<label>Baseline (minutes)<input name="baseline" type="number" min="0" value="' +
        E(p.baseline == null ? "0" : p.baseline) + '"></label>' +
        '<label>Lifecycle<select name="status"><option value="active"' +
        (p.status === "retired" ? "" : " selected") + '>Active</option><option value="retired"' +
        (p.status === "retired" ? " selected" : "") + '>Retired</option></select></label>' +
        '<label>Description<textarea name="desc">' + E(p.desc || "") + '</textarea></label>' +
        '<label>Definition of Done<textarea name="criteria">' + E(p.criteria || "") + '</textarea></label>' +
        '<label>Other original properties (JSON)<textarea name="extra">' + E(JSON.stringify(other, null, 2)) +
        '</textarea></label><button type="submit">Save task revision</button>' +
        '<button type="button" id="server-task-cancel">Cancel</button></form>';
      editor.querySelector("#server-task-cancel").onclick = function () { editor.hidden = true; };
      editor.querySelector("form").onsubmit = async function (event) {
        event.preventDefault();
        var form = event.currentTarget, button = form.querySelector('button[type="submit"]');
        button.disabled = true;
        try {
          var values = Object.fromEntries(new FormData(form).entries());
          var extras = JSON.parse(values.extra || "{}");
          if (!extras || typeof extras !== "object" || Array.isArray(extras))
            throw Error("Other properties must be a JSON object");
          var properties = Object.assign({}, extras, {
            phase: values.phase, domain: values.domain, baseline: Number(values.baseline),
            status: values.status, desc: values.desc, criteria: values.criteria
          });
          var request = {name: values.name, properties: properties};
          if (item) {
            request.expected_revision = item.revision;
            if ((values.parent_id || null) !== item.parent_id) {
              request.parent_id = values.parent_id || null;
              request.before = null; // append under newly selected parent
            }
            await api("/" + encodeURIComponent(item.id), "PATCH", request);
          } else {
            request.parent_id = values.parent_id || null;
            await api("", "POST", request);
          }
          editor.hidden = true;
          await refresh();
        } catch (error) {
          report("Save rejected: " + error.message +
            ". Reload the current tree; the rejected revision was not applied.", true);
        } finally { button.disabled = false; }
      };
    }

    async function reorder(id, direction) {
      if (!canWrite) return;
      var node = rows.find(function (n) { return n.id === id; });
      if (!node) return;
      var siblings = siblingRows(node.parent_id), index = siblings.findIndex(function (n) { return n.id === id; });
      var before = direction === "up" ? (index > 0 && siblings[index - 1].id) :
        (index < siblings.length - 2 ? siblings[index + 2].id : null);
      if (direction === "up" && !before) return;
      try {
        await api("/" + encodeURIComponent(id), "PATCH", {
          expected_revision: node.revision, parent_id: node.parent_id, before: before
        });
        await refresh();
      } catch (error) {
        // The refusal must survive the refresh: reporting first made the
        // reload erase the conflict message before the user could read it.
        await refresh();
        report("Reorder refused: " + error.message +
          ". Reload the current tree; the rejected revision was not applied.", true);
      }
    }

    root.querySelector("#server-task-refresh").onclick = refresh;
    root.querySelector("#server-task-add-root").onclick = function () { editorForm(null, null); };
    tree.onclick = async function (event) {
      var button = event.target.closest("button[data-task-action]");
      if (!button) return;
      var node = rows.find(function (r) { return r.id === button.dataset.id; });
      if (!node) return;
      if (button.dataset.taskAction === "select") {
        history.hidden = false;
        history.textContent = JSON.stringify({id: node.id, name: node.name,
          revision: node.revision, parent_id: node.parent_id,
          properties: node.properties}, null, 2);
        if (provider && typeof provider.tasks.select === "function")
          provider.tasks.select(node.id);
      }
      if (button.dataset.taskAction === "edit") editorForm(node, node.parent_id);
      if (button.dataset.taskAction === "add") editorForm(null, node.id);
      if (["up", "down"].includes(button.dataset.taskAction)) await reorder(node.id, button.dataset.taskAction);
      if (button.dataset.taskAction === "history") {
        history.hidden = false; history.textContent = "Loading task history…";
        try {
          var result = await api("/" + encodeURIComponent(node.id) + "/revisions");
          history.textContent = JSON.stringify(result.revisions, null, 2);
        } catch (error) { history.textContent = "History unavailable: " + error.message; }
      }
    };

    return {
      setAccess: function (read, write) {
        canRead = !!read; canWrite = !!(read && write);
        root.hidden = !canRead;
        ++generation; rows = []; tree.replaceChildren();
        editor.hidden = true; history.hidden = true;
        if (canRead) refresh();
      }
    };
  }

  window.AICompassServerTasks = {mount: mount};
})();
