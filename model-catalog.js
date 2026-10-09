/* PLAT-05: Shared Models UI lane and explicit data-provider contract.
 * Loaded in both modes; NEVER accesses localStorage or imports Demo records itself.
 * The Demo adapter uses its existing in-memory/localStorage persistence callbacks.
 * The Server adapter uses only authenticated, revisioned Django endpoints. */
(function (root) {
  "use strict";

  function escapeHtml(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (character) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[character];
    });
  }

  function badge(value) {
    var text = String(value || "");
    var kind = /^(published|active|accessible)$/i.test(text) ? "green"
      : /^(draft|watching)$/i.test(text) ? "amber"
      : /^(retired|not accessible)$/i.test(text) ? "red" : "";
    return '<span class="tag ' + kind + '">' + escapeHtml(text) + "</span>";
  }

  function modelFromApi(row) {
    if (!row || row.type !== "model" || !row.id || !row.revision ||
        !row.properties || typeof row.properties !== "object" || Array.isArray(row.properties)) {
      throw new Error("The Server returned an invalid Model record.");
    }
    var p = row.properties;
    return {
      id: row.id, name: row.name, type: "model", version: p.version || "",
      url: p.url || "", details: p.details || "", publication: p.publication || "draft",
      status: p.status || "active", accessible: p.accessible === true,
      properties: p, revision: row.revision, schema_version: row.schema_version,
      created_at: row.created_at, created_by: row.created_by
    };
  }

  /* Same domain methods: list/get/create/revise/revisions.
   * Demo callbacks perform native browser persistence, no fake Server API calls. */
  function LocalStorageDataProvider(operations) {
    return {
      list: function () { return operations.list(); },
      get: function (id) { return operations.get(id); },
      create: function (model) { return operations.create(model); },
      revise: function (id, model) { return operations.revise(id, model); },
      revisions: function (id) { return operations.revisions ? operations.revisions(id) : []; }
    };
  }

  function ApiDataProvider(csrfToken) {
    async function request(path, method, payload) {
      var options = {method: method || "GET", credentials: "same-origin", cache: "no-store"};
      if (method === "POST") {
        options.headers = {"Content-Type": "application/json", "X-CSRFToken": csrfToken()};
        options.body = JSON.stringify(payload);
      }
      var response;
      try {
        response = await root.fetch("/api/v1/models" + (path || ""), options);
      } catch (error) {
        throw new Error("Server unavailable. No Demo fallback or local save occurred.");
      }
      var result;
      try { result = await response.json(); }
      catch (error) { throw new Error("Server returned an invalid response (HTTP " + response.status + ")."); }
      if (!response.ok) {
        var reason = result.detail || result.error || ("HTTP " + response.status);
        var failure = new Error(String(reason) + " (HTTP " + response.status + ")");
        failure.status = response.status;
        failure.code = result.error || "";
        throw failure;
      }
      return result;
    }
    function pathFor(id) { return "/" + encodeURIComponent(id); }
    return {
      list: async function () {
        var result = await request("");
        if (!Array.isArray(result.results)) throw new Error("Invalid Server Model list.");
        return result.results.map(modelFromApi);
      },
      get: async function (id) { return modelFromApi(await request(pathFor(id))); },
      create: async function (model) {
        return modelFromApi(await request("", "POST", {
          name: model.name, properties: model.properties
        }));
      },
      revise: async function (id, model) {
        return modelFromApi(await request(pathFor(id) + "/revisions", "POST", {
          name: model.name, properties: model.properties,
          expected_revision: model.expected_revision
        }));
      },
      revisions: async function (id) {
        var result = await request(pathFor(id) + "/revisions");
        if (!Array.isArray(result.revisions)) throw new Error("Invalid Server revision list.");
        return result.revisions.map(modelFromApi);
      }
    };
  }

  /* Used by BOTH frontends, with identical cards and buttons. */
  function renderLane(models, options) {
    options = options || {};
    var canWrite = options.canWrite !== false;
    var list = models.slice().sort(function (a, b) { return a.name.localeCompare(b.name); });
    var intro = "Versioned engines and capabilities";
    return '<section class="card component-lane" data-catalog="model">' +
      '<div class="card-head"><div><div class="eyebrow">model</div><h2>Models</h2></div>' +
      (canWrite ? '<button class="btn sm" data-act="newComponentType" data-id="model">+ Add</button>' : "") +
      '</div><p class="muted small" style="margin-bottom:14px">' + intro + '</p><div class="list">' +
      (list.length ? list.map(function (model) {
        var docLink = /^https?:\/\//i.test(model.url || "") ?
          '<p class="small"><a href="' + escapeHtml(model.url) +
          '" target="_blank" rel="noopener noreferrer">Documentation ↗</a></p>' : "";
        return '<div class="list-row"><div class="short"><strong>' + escapeHtml(model.name) +
          '</strong><div class="muted small">' + escapeHtml(model.version || "Version not set") +
          ' · ' + escapeHtml(model.testedCount || 0) + ' tested combinations</div>' +
          '<div class="tags" style="margin-top:5px">' +
          badge(model.publication || "published") + badge(model.status || "active") +
          badge(model.accessible ? "Accessible" : "Not accessible") + '</div>' +
          '<p class="muted small">' + escapeHtml((model.details || "").slice(0, 180)) + '</p>' +
          docLink + (options.showRevisions && model.revision ?
            '<div class="muted small">' + escapeHtml(model.id) + ' · ' +
            escapeHtml(model.revision) + '</div>' : "") +
          '</div><div class="server-model-actions">' +
          (canWrite ? '<button class="btn sm" data-act="editComponent" data-id="' +
            escapeHtml(model.id) + '">Edit</button>' : "") +
          (options.showRevisions ? '<button class="btn sm" data-act="modelHistory" data-id="' +
            escapeHtml(model.id) + '">History</button>' : "") + '</div></div>';
      }).join("") : '<div class="empty">No Models yet. ' +
          (canWrite ? 'Create the first real Model to begin.' : 'Models will appear when a contributor adds one.') +
          '</div>') + '</div></section>';
  }

  root.AICompassModels = {
    LocalStorageDataProvider: LocalStorageDataProvider,
    ApiDataProvider: ApiDataProvider,
    modelFromApi: modelFromApi,
    renderLane: renderLane,
    escapeHtml: escapeHtml
  };
})(window);
