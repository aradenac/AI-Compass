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
    if (!row || typeof row !== "object" || !row.id || !row.type) {
      throw new Error("The Server returned invalid catalog metadata.");
    }
    var p = row.properties && typeof row.properties === "object" &&
      !Array.isArray(row.properties) ? row.properties : {};
    var compatibility = row.compatibility || {
      status: "unsupported", read_only: true, reason: "Compatibility metadata unavailable"
    };
    return {
      id: row.id, name: row.name == null ? "" : String(row.name), type: row.type,
      version: p.version, url: p.url, details: p.details,
      publication: p.publication, status: p.status, accessible: p.accessible,
      properties: row.properties, revision: row.revision,
      schema_version: row.schema_version, compatibility: compatibility,
      readOnly: compatibility.read_only === true,
      created_at: row.created_at, created_by: row.created_by
    };
  }

  function diagnosticSummary(model) {
    var c = model.compatibility || {};
    return [c.reason, c.incompatible_fields && c.incompatible_fields.length ?
      "Incompatible: " + c.incompatible_fields.join(", ") : null].filter(Boolean).join(" · ");
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

  function ApiDataProvider(csrfToken, typeSlug) {
    typeSlug = typeSlug || "model";
    if (!["model", "provider", "harness", "framework"].includes(typeSlug)) {
      throw new Error("Unregistered catalog adapter type");
    }
    var base = typeSlug === "model" ? "/api/v1/models" :
      "/api/v1/catalog/" + typeSlug;
    async function request(path, method, payload) {
      // FUT-03: the mode-neutral Server transport owns CSRF, status taxonomy
      // and network/offline refusal; older embedders retain their legacy API.
      if (root.AICompassRuntime) {
        return root.AICompassRuntime.ServerTransport(root.fetch.bind(root), csrfToken)
          .request(base + (path || ""), method, payload);
      }
      var options = {method: method || "GET", credentials: "same-origin", cache: "no-store"};
      if (method === "POST") {
        options.headers = {"Content-Type": "application/json", "X-CSRFToken": csrfToken()};
        options.body = JSON.stringify(payload);
      }
      var response;
      try {
        response = await root.fetch(base + (path || ""), options);
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
        if (!Array.isArray(result.results)) throw new Error("Invalid Server catalog list.");
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
    var list = models.slice().sort(function (a, b) { return String(a.name || "").localeCompare(String(b.name || "")); });
    var type = options.type || "model";
    var titles = {model: "Models", provider: "Providers",
      harness: "Harnesses", framework: "Frameworks"};
    var intros = {model: "Versioned engines and capabilities",
      provider: "Hosting, endpoints, access and pricing",
      harness: "CLI, web, IDE and agent tool integrations",
      framework: "Process and orchestration definitions; not measured AI Solutions"};
    if (!titles[type]) throw new Error("Unregistered catalog lane");
    var intro = intros[type];
    return '<section class="card component-lane" data-catalog="' + type + '">' +
      '<div class="card-head"><div><div class="eyebrow">' + type + '</div><h2>' + titles[type] + '</h2></div>' +
      (canWrite ? '<button class="btn sm" data-act="newComponentType" data-id="' + type + '">+ Add</button>' : "") +
      '</div><p class="muted small" style="margin-bottom:14px">' + intro + '</p><div class="list">' +
      (list.length ? list.map(function (model) {
        var docLink = /^https?:\/\//i.test(model.url || "") ?
          '<p class="small"><a href="' + escapeHtml(model.url) +
          '" target="_blank" rel="noopener noreferrer">Documentation ↗</a></p>' : "";
        var compat = model.compatibility || null;
        var rawOnly = (compat && compat.read_only) || model.type !== type;
        var diag = compat ? '<div class="muted small">Schema v' +
          escapeHtml(model.schema_version == null ? "unknown" : model.schema_version) +
          ' · ' + badge(compat.status || "unsupported") +
          (compat.missing_fields && compat.missing_fields.length ?
            ' · Missing: ' + escapeHtml(compat.missing_fields.join(", ")) : "") +
          (compat.null_fields && compat.null_fields.length ?
            ' · Null: ' + escapeHtml(compat.null_fields.join(", ")) : "") +
          (compat.unknown_fields && compat.unknown_fields.length ?
            ' · Extensions: ' + escapeHtml(compat.unknown_fields.join(", ")) : "") +
          '</div><div class="muted small">' + escapeHtml(diagnosticSummary(model)) + '</div>' : "";
        var facets = type === "provider" ? [model.properties && model.properties.hosting,
            model.properties && model.properties.access, model.properties && model.properties.pricing] :
          type === "harness" ? [model.properties && model.properties.interface,
            model.properties && model.properties.integrations] :
          type === "framework" ? [model.properties && model.properties.process,
            model.properties && model.properties.orchestration] : [];
        var facetText = facets.filter(function (value) { return value != null && value !== ""; })
          .map(function (value) { return typeof value === "object" ? JSON.stringify(value) : String(value); }).join(" · ");
        return '<div class="list-row"><div class="short"><strong>' + escapeHtml(model.name || "(unnamed)") +
          '</strong><div class="muted small">' + escapeHtml(model.version || "Version not set") +
          (type === "framework" ? ' · ' + escapeHtml(model.linkedCount || 0) + ' linked campaigns' :
            ' · ' + escapeHtml(model.testedCount || 0) + ' tested combinations') + '</div>' +
          (facetText ? '<div class="muted small">' + escapeHtml(facetText) + '</div>' : "") +
          '<div class="tags" style="margin-top:5px">' +
          (model.publication != null ? badge(model.publication) : "") +
          (model.status != null ? badge(model.status) : "") +
          (typeof model.accessible === "boolean" ? badge(model.accessible ? "Accessible" : "Not accessible") : "") + '</div>' +
          '<p class="muted small">' + escapeHtml(String(model.details == null ? "" : model.details).slice(0, 180)) + '</p>' +
          diag +
          docLink + (options.showRevisions && model.revision ?
            '<div class="muted small">' + escapeHtml(model.id) + ' · ' +
            escapeHtml(model.revision) + '</div>' : "") +
          '</div><div class="server-model-actions">' +
          (canWrite && !rawOnly ? '<button class="btn sm" data-act="editComponent" data-id="' +
            escapeHtml(model.id) + '">Edit</button>' : "") +
          (options.showRevisions ? '<button class="btn sm" data-act="modelHistory" data-id="' +
            escapeHtml(model.id) + '">History</button>' +
            '<button class="btn sm" data-act="modelRaw" data-id="' +
            escapeHtml(model.id) + '">Original data</button>' +
            '<button class="btn sm" data-act="catalogEvidence" data-id="' +
            escapeHtml(model.id) + '">Evidence</button>' : "") + '</div></div>';
      }).join("") : '<div class="empty">No ' + titles[type] + ' yet. ' +
          (canWrite ? 'Add the first catalog item.' : 'Items will appear when a contributor adds one.') +
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
