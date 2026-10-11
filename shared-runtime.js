/* FUT-03. Shared bootstrap, typed transport and persona navigation — no persistence. */
(function (root) {
  "use strict";
  var MODES = Object.freeze({demo: "demo", server: "server"});
  function modeFromLocation(location) {
    var params = new URLSearchParams(location.search || "");
    return params.get("mode") === "server" ||
      (location.pathname === "/maintenance" && params.get("mode") !== "demo") ?
      MODES.server : MODES.demo;
  }
  function error(status, payload) {
    var code = payload && payload.error;
    if (code && typeof code === "object") code = code.code;
    if (typeof code !== "string") code = "http_" + status;
    var details = (payload && (payload.detail || (payload.error && payload.error.detail))) || code;
    var messages = {401: "Authentication required", 403: "Access denied",
      409: "Revision conflict: reload authoritative data before retrying",
      422: "Invalid fields", 503: "Server unavailable. No Demo fallback"};
    var e = new Error((messages[status] || details) + " (" + code + ")");
    e.status = status; e.code = code;
    return e;
  }
  /* UX-R05: preserve the authoritative detail so 409/403 can be shown as a
   * first-class conflict notice instead of a generic failure line. */
  function httpError(status, payload) {
    var e = error(status, payload);
    e.detail = (payload && (payload.detail || (payload.error && payload.error.detail))) || e.message;
    e.payload = payload || {};
    e.conflict = status === 409;
    e.denied = status === 403 || status === 401;
    return e;
  }
  /* Normalize anything thrown by a module's own fetch wrapper or the shared
   * transport into the same shape, without assuming a particular module. */
  function failureInfo(cause) {
    var error_ = cause || {};
    var payload = error_.payload || {};
    return {
      status: Number(error_.status) || 0,
      code: error_.code || (payload.error && payload.error.code) || null,
      detail: error_.detail || (payload.detail) || error_.message || String(cause),
      baseRevision: payload.expected_revision || payload.base_revision || null,
      latestRevision: payload.revision || payload.latest_revision || null,
      objectId: payload.id || payload.public_id || null,
      conflict: Number(error_.status) === 409,
      denied: Number(error_.status) === 403 || Number(error_.status) === 401
    };
  }
  function ServerTransport(fetcher, csrf) {
    async function request(path, method, payload) {
      if (typeof path !== "string" || !path.startsWith("/api/v1/"))
        throw new Error("Only same-origin versioned API paths are permitted");
      var verb = method || "GET";
      var opts = {method: verb, credentials: "same-origin", cache: "no-store"};
      if (verb !== "GET") {
        opts.headers = {"Content-Type": "application/json", "X-CSRFToken": csrf()};
        opts.body = JSON.stringify(payload || {});
      }
      var response;
      try { response = await fetcher(path, opts); }
      catch (_) { throw error(503, {error: "network_unavailable"}); }
      var data;
      try { data = await response.json(); }
      catch (_) { throw error(response.status, {error: "invalid_server_json"}); }
      if (!response.ok) throw httpError(response.status, data);
      return data;
    }
    return {request: request};
  }
  var PERSONAS = [
    {id: "engineer", label: "My AI Workspace", permission: "business_read", route: "/?workspace=engineer"},
    {id: "workgroup", label: "AI Workgroup Studio", permission: "business_write", route: "/?workspace=workgroup"},
    {id: "management", label: "Management Insights", permission: "planning_view", route: "/?workspace=management"},
    {id: "maintenance", label: "Maintenance & Governance", permission: "maintenance_view", route: "/maintenance?mode=server"}
  ];
  function availablePersonas(identity, mode) {
    if (mode === MODES.demo) {
      var simulated = identity && identity.role;
      return PERSONAS.filter(function (p) {
        return p.id === (simulated === "reader" ? "engineer" : simulated);
      });
    }
    var permissions = identity && identity.permissions || [];
    return PERSONAS.filter(function (p) { return permissions.includes(p.permission); });
  }
  function choosePersona(identity, mode, requested) {
    var choices = availablePersonas(identity, mode);
    return choices.find(function (p) { return p.id === requested; }) || choices[0] || null;
  }
  function renderPersonaLinks(identity, mode, requested) {
    var esc = root.AICompassModels && root.AICompassModels.escapeHtml ||
      function (v) { return String(v); };
    var choices = availablePersonas(identity, mode);
    return '<nav class="shared-personas" aria-label="Workspaces">' +
      choices.map(function (p) {
        var href = mode === MODES.demo ? "/?mode=demo&workspace=" + p.id :
          (p.id === "maintenance" ? "/maintenance?mode=server" : "/?mode=server&workspace=" + p.id);
        return '<a href="' + esc(href) + '" data-persona="' + p.id + '"' +
          (p.id === requested ? ' aria-current="page"' : "") + '>' + esc(p.label) + '</a>';
      }).join(" · ") + '</nav>';
  }
  function createProviders(mode, demo, server) {
    if (mode === MODES.demo && !demo) throw new Error("Demo provider missing");
    if (mode === MODES.server && !server) throw new Error("Server provider missing");
    // Exactly one provider selected at startup. Never silently switch modes.
    return Object.freeze({mode: mode, data: mode === MODES.demo ? demo : server});
  }
  root.AICompassRuntime = {
    MODES: MODES, modeFromLocation: modeFromLocation, ServerTransport: ServerTransport,
    error: error, httpError: httpError, failureInfo: failureInfo,
    availablePersonas: availablePersonas, choosePersona: choosePersona,
    renderPersonaLinks: renderPersonaLinks, createProviders: createProviders
  };
})(window);
