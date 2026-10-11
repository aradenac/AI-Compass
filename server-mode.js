/* PLAT-05: real authenticated Server workspace for the shared Models catalog.
 * The Demo runtime is owned by prototype.html and is NEVER read here. */
(function () {
  "use strict";
  var serverMode = new URLSearchParams(window.location.search).get("mode") === "server" ||
    (window.location.pathname === "/maintenance" &&
     new URLSearchParams(window.location.search).get("mode") !== "demo");
  if (!serverMode) {
    var link = document.createElement("a");
    link.href = "?mode=server";
    link.textContent = "Server sign-in";
    link.title = "Switch explicitly to the server-backed identity workspace";
    link.id = "server-mode-switch";
    link.className = "ux-mode-link";
    var demoRoot = document.getElementById("app");
    function placeSwitch() {
      var actions = demoRoot && demoRoot.querySelector(".ux-topbar .top-actions");
      if (actions && link.parentElement !== actions) actions.appendChild(link);
    }
    if (demoRoot) new MutationObserver(placeSwitch).observe(demoRoot, {childList:true});
    placeSwitch();
    return;
  }

  var maintenanceWorkspace = window.location.pathname === "/maintenance";
  var modelsUi = window.AICompassModels;
  var root = document.getElementById("app");
  if (!modelsUi) {
    root.textContent = "Model catalog component is missing. Server data was not loaded.";
    return;
  }
  var style = document.createElement("style");
  style.textContent = ".server-card{background:white;border:1px solid #e3e8f0;border-radius:14px;padding:24px;max-width:1100px;box-shadow:0 8px 32px #1227470d}.server-page{min-height:100vh;background:#f4f6fa;display:grid;grid-template-columns:245px minmax(0,1fr)}.server-sidebar{background:#111e35;color:#dce5f7;padding:30px 20px}.server-sidebar a{color:#b4e3ff}.server-main{padding:clamp(18px,5vw,55px);min-width:0}.server-main h1{margin-bottom:12px}.server-card p{margin:9px 0}.server-card label{display:block;margin:12px 0 6px;font-weight:600}.server-card input,.server-card textarea,.server-card select{display:block;width:100%;max-width:620px;padding:11px;border:1px solid #c4cedd;border-radius:8px;background:white;font:inherit}.server-card textarea{min-height:90px}.server-card button{padding:10px 15px;margin:8px 8px 0 0;background:#3159d7;color:white;border:0;border-radius:8px;cursor:pointer}.server-card button:disabled{opacity:.55;cursor:not-allowed}.server-actions{margin-top:14px}.server-status{white-space:pre-wrap;margin:12px 0;color:#394b66}.server-error{color:#ac303d}.server-badge{display:inline-block;padding:4px 9px;border-radius:6px;background:#e8f7f4;color:#096a70;margin:4px 4px 4px 0}.server-card [hidden],[hidden]{display:none!important}.server-catalog{max-width:1100px;margin-top:20px}.server-catalog .component-lane{max-width:none}.server-model-actions{display:flex;gap:6px;align-items:flex-start;flex-wrap:wrap}.server-model-actions button{white-space:nowrap}.server-model-toolbar{display:flex;justify-content:space-between;align-items:center;gap:15px;flex-wrap:wrap;margin:12px 0}.server-model-toolbar .btn{background:#3159d7;color:white}.server-model-form{margin:12px 0 0}.server-model-form .form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.server-model-form .span2{grid-column:1/-1}.server-model-form .muted{font-size:12px}.server-model-history{max-height:450px;overflow:auto}.server-model-history pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6fa;padding:12px;border:1px solid #e3e8f0;border-radius:9px}.server-model-history details{margin:12px 0;border:1px solid #e3e8f0;padding:12px;border-radius:9px}.server-model-actions .btn{padding:6px 10px}.server-model-empty{padding:20px}@media(max-width:700px){.server-page{display:block}.server-sidebar{padding:16px}.server-main{padding:18px}.server-model-form .form-grid{grid-template-columns:1fr}}";
  document.head.appendChild(style);

  root.innerHTML = [
    '<div class="server-page">',
    '<aside class="server-sidebar"><div style="font-size:23px;font-weight:750;margin-bottom:12px">AI Compass</div>',
    '<strong>Server mode</strong><p style="margin:14px 0">Authenticated shared backend</p>',
    '<a href="/?mode=demo">Return to independent Demo mode</a>',
    '<p id="server-maintenance-nav" hidden><a href="/maintenance">Maintenance & Data Health</a></p>',
    '<p style="margin-top:25px;font-size:12px">Real technology records are stored in PostgreSQL; fake Demo records are never copied.</p>',
    '</aside>',
    '<main class="server-main"><h1>' +
      (window.location.pathname === "/maintenance" ? "Maintenance & Governance" : "Technology catalog") +
      '</h1>',
    '<div id="server-personas" class="server-card" style="margin:12px 0" hidden></div>',
    '<section id="server-environment-profile" class="server-catalog" hidden></section>',
    '<section id="server-engineer" class="server-catalog" hidden></section>',
    '<section id="server-workgroup-home" class="server-catalog" hidden></section>',
    '<section id="server-workgroup-summary" class="server-catalog" hidden></section>',
    '<p style="margin-bottom:20px;color:#64748b">Real Django session · persistent technology catalog · independent Demo</p>',
    '<div class="server-card">',
    '<p id="server-state" class="server-status" role="status" aria-live="polite">Connecting to backend…</p>',
    '<form id="server-login-form" hidden>',
    '<h2>Sign in</h2><label for="server-username">Username</label>',
    '<input id="server-username" autocomplete="username" maxlength="150" required>',
    '<label for="server-password">Password</label>',
    '<input id="server-password" type="password" autocomplete="current-password" required>',
    '<button type="submit">Sign in to Server</button></form>',
    '<section id="server-account" hidden><h2>Signed-in account</h2><p id="server-account-name"></p>',
    '<p><strong>Roles</strong></p><div id="server-roles"></div>',
    '<p><strong>Capabilities</strong></p><div id="server-capabilities"></div>',
    '<div class="server-actions" id="server-actions"></div><button id="server-logout">Sign out</button></section>',
    '</div>',
    '<section id="server-model-catalog" class="server-catalog" hidden>',
    '<div id="server-shared-catalog"></div>',
    '<section id="server-pricing" class="server-card" hidden></section>',
    '<div class="server-model-toolbar"><div><h2>Models · Providers · Harnesses · Frameworks</h2><p class="muted small">Persistent catalog · versions and original revisions</p></div>',
    '<button type="button" class="btn" id="server-model-refresh">Refresh from Server</button></div>',
    '<p id="server-model-state" class="server-status" role="status" aria-live="polite"></p>',
    '<div id="server-model-list"></div>',
    '<section id="server-model-editor" class="server-card" hidden></section>',
    '<section id="server-model-history" class="server-card server-model-history" hidden></section>',
    '<form id="server-inspect-catalog-form" class="server-card" style="margin-top:16px">',
    '<h3>Inspect original catalog record</h3>',
    '<p class="muted small">Authorized read-only inspection of unsupported types, schema versions and raw fields.</p>',
    '<label for="server-inspect-id">Permanent object ID</label>',
    '<input id="server-inspect-id" name="object_id" required maxlength="120" placeholder="mdl-word-word-word">',
    '<button type="submit">Inspect original record</button></form>',
    '<section id="server-catalog-raw" class="server-card" style="margin-top:12px" hidden></section>',
    '<section id="server-catalog-evidence" class="server-card" style="margin-top:12px" hidden></section>',
    '<div class="note" style="margin-top:14px">Frameworks describe orchestration and are not benchmarked AI Solutions.</div>',
    '</section>',
    '<section id="server-task-tree" class="server-catalog" hidden>',
    '<div class="server-model-toolbar"><div><h2>Task management</h2>',
    '<p class="muted small">Persistent engineering taxonomy · revisioned ancestry and order</p></div>',
    '<button id="server-task-refresh" type="button">Refresh tasks</button></div>',
    '<p id="server-task-state" class="server-status" role="status"></p>',
    '<button id="server-task-add-root" type="button" hidden>+ Create root section</button>',
    '<div id="server-task-list"></div>',
    '<section id="server-task-editor" class="server-card" hidden></section>',
    '<pre id="server-task-history" class="server-card" hidden style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>',
    '</section>',
    '<section id="server-test-cases" class="server-catalog" hidden></section>',
    '<section id="server-guides" class="server-catalog" hidden></section>',
    '<section id="server-watch" class="server-catalog server-card" hidden></section>',
    '<section id="server-forecasts" class="server-catalog server-card" hidden></section>',
    '<section id="server-campaigns" class="server-catalog" hidden></section>',
    '<section id="server-results" class="server-catalog" hidden></section>',
    '<section id="server-recommendations" class="server-catalog" hidden></section>',
    '<section id="server-discussions" class="server-catalog" hidden></section>',
    '<section id="server-users" class="server-catalog" hidden></section>',
    '<section id="server-activity" class="server-catalog" hidden></section>',
    '<section id="server-data-health" class="server-catalog" hidden></section>',
    '<section id="server-governance-audit" class="server-catalog" hidden></section>',
    '<section id="server-management-insights" class="server-catalog" hidden></section>',
    '<section id="server-planning" class="server-catalog" hidden></section>',
    '</main></div>'
  ].join("");

  // UX-R02: keep existing data-bound domain nodes, but mount them into the
  // *same* shell hierarchy as standalone Demo before controllers are attached.
  var originalMain = root.querySelector(".server-main");
  var originalPersonaLinks = document.getElementById("server-personas");
  var moved = document.createDocumentFragment();
  var overview = document.createElement("section");
  overview.id = "ux-workgroup-overview";
  var authPanel = null;
  Array.from(originalMain.children).forEach(function (child) {
    if (child === originalPersonaLinks || child.tagName === "H1" ||
        (child.tagName === "P" && !child.id)) return;
    if (child.id === "server-workgroup-home" ||
        child.id === "server-workgroup-summary") {
      overview.appendChild(child);
      return;
    }
    if (child.classList.contains("server-card") &&
        child.querySelector("#server-login-form")) {
      authPanel = child;
      child.id = "ux-auth-panel";
    }
    moved.appendChild(child);
  });
  if (!authPanel) throw new Error("Server login panel was not preserved by the shared shell");
  root.innerHTML = window.AICompassShell.render({
    mode: "server",
    title: maintenanceWorkspace ? "Maintenance & Governance" : "AI Compass",
    sidebar: '<div id="server-side-navigation"></div>',
    footer: '<p>Authenticated Server · persistent records</p>' +
      '<p id="server-maintenance-nav" hidden><a href="/maintenance?mode=server">Maintenance & Governance</a></p>' +
      '<a href="/?mode=demo">Switch to independent Demo</a>',
    content: '<div id="ux-screen-host"></div>'
  });
  var serverScreenHost = document.getElementById("ux-screen-host");
  var contextNav = document.createElement("div");
  contextNav.id = "ux-context-navigation";
  serverScreenHost.parentNode.insertBefore(contextNav,serverScreenHost);
  serverScreenHost.appendChild(overview);
  serverScreenHost.appendChild(moved);
  var topActions = root.querySelector(".ux-topbar .top-actions");
  originalPersonaLinks.className = "ux-persona-menu";
  originalPersonaLinks.removeAttribute("style");
  topActions.appendChild(originalPersonaLinks);
  var dialogCoordinator = window.AICompassShell.attachDialogs(serverScreenHost);

  var state = document.getElementById("server-state");
  var form = document.getElementById("server-login-form");
  var account = document.getElementById("server-account");
  var actions = document.getElementById("server-actions");
  var catalog = document.getElementById("server-model-catalog");
  var modelList = document.getElementById("server-model-list");
  var modelState = document.getElementById("server-model-state");
  var editor = document.getElementById("server-model-editor");
  var history = document.getElementById("server-model-history");
  var raw = document.getElementById("server-catalog-raw");
  var evidence = document.getElementById("server-catalog-evidence");
  var evidenceGeneration = 0;
  var cachedModels = [];
  var TYPES = ["model","provider","harness","framework"];
  var adapters = Object.fromEntries(TYPES.map(function (type) {
    return [type, modelsUi.ApiDataProvider(csrfFromCookie, type)];
  }));
  var grants = [];
  var refreshGeneration = 0;
  var adapter = modelsUi.ApiDataProvider(csrfFromCookie);
  var escapeHtml = modelsUi.escapeHtml;
  // FUT-03: exactly one provider for this runtime. Server never reads fictional
  // browser records or silently changes to Demo after an API/CSRF failure.
  var serverDomain = window.AICompassRuntime.createProviders("server", null, {
    catalog: adapters
  }).data;
  var sharedCatalog = window.AICompassSharedCatalog.mount(
    document.getElementById("server-shared-catalog"), serverDomain, {
      mode: "server",
      onRows: function (data) { cachedModels = data; },
      onRaw: function (record) { showRaw(record); },
      onEvidence: function (id) { showEvidence(id); }
    });
  var pricing = window.AICompassPricing.mount(
    document.getElementById("server-pricing"),
    window.AICompassPricing.serverAdapter(fetch, csrfFromCookie),
    {mode:"server"});
  // Legacy editor DOM remains solely for advanced record inspection and
  // existing regression boundaries, not as an additional displayed catalog.
  document.getElementById("server-model-list").hidden = true;
  document.getElementById("server-model-editor").hidden = true;
  document.getElementById("server-model-history").hidden = true;
  document.getElementById("server-model-refresh").parentElement.hidden = true;
  var environment = window.AICompassEnvironment.mount(
    document.getElementById("server-environment-profile"),
    window.AICompassEnvironment.serverProvider(fetch, csrfFromCookie),"server");
  var personas = document.getElementById("server-personas");
  var engineer = window.AICompassEngineer.mount(
    document.getElementById("server-engineer"),
    window.AICompassEngineer.serverProvider(fetch, csrfFromCookie), "server");

  var tasks = window.AICompassServerTasks.mount(document.getElementById("server-task-tree"), csrfFromCookie, escapeHtml);
  var testCases = window.AICompassServerTestCases.mount(document.getElementById("server-test-cases"), csrfFromCookie, escapeHtml);
  var guides = window.AICompassServerGuides.mount(document.getElementById("server-guides"), csrfFromCookie, escapeHtml);
  var watch = window.AICompassServerWatch.mount(document.getElementById("server-watch"), csrfFromCookie, escapeHtml);
  var forecasts = window.AICompassServerForecasts.mount(document.getElementById("server-forecasts"), csrfFromCookie, escapeHtml);
  var campaigns = window.AICompassServerCampaigns.mount(document.getElementById("server-campaigns"), csrfFromCookie, escapeHtml);
  var resultsExplorer = window.AICompassServerResults.mount(document.getElementById("server-results"), csrfFromCookie, escapeHtml);
  var recommendations = window.AICompassServerRecommendations.mount(document.getElementById("server-recommendations"), csrfFromCookie, escapeHtml);
  var discussions = window.AICompassServerDiscussions.mount(document.getElementById("server-discussions"), csrfFromCookie, escapeHtml);
  var users = window.AICompassServerUsers.mount(document.getElementById("server-users"), csrfFromCookie, escapeHtml);
  var activity = window.AICompassServerActivity.mount(document.getElementById("server-activity"), escapeHtml);
  var governanceAudit = window.AICompassServerAudit.mount(
    document.getElementById("server-governance-audit"), escapeHtml);
  var health = window.AICompassServerDataHealth.mount(document.getElementById("server-data-health"), csrfFromCookie, escapeHtml);
  var planning = window.AICompassServerPlanning.mount(document.getElementById("server-planning"), csrfFromCookie, escapeHtml);
  var managementInsights = window.AICompassHeatmap.mount(
    document.getElementById("server-management-insights"),
    window.AICompassHeatmap.serverProvider(fetch, csrfFromCookie), "server");

  function status(message, isError) {
    state.textContent = message;
    state.className = isError ? "server-status server-error" : "server-status";
  }
  function catalogStatus(message, isError) {
    modelState.textContent = message;
    modelState.className = isError ? "server-status server-error" : "server-status";
  }
  function csrfFromCookie() {
    var row = document.cookie.split("; ").find(function (value) { return value.startsWith("csrftoken="); });
    return row ? decodeURIComponent(row.substring("csrftoken=".length)) : "";
  }

  // FUT-01: negotiate additive v1 API contract BEFORE any authenticated
  // business request. Old v1 frontends keep using existing routes unchanged.
  function checkReleaseCompatibility(doc) {
    if (!doc || doc.schema !== "ai-compass/api-contract@1" ||
        doc.api_major !== 1 || !Array.isArray(doc.supported_client_api_majors) ||
        !doc.supported_client_api_majors.includes(1) ||
        (doc.min_client_api_major != null && doc.min_client_api_major > 1) ||
        (doc.max_client_api_major != null && doc.max_client_api_major < 1)) {
      throw new Error("Incompatible Server API contract; this frontend requires API major v1.");
    }
    return true;
  }

  var compatibleContract = false;

  async function ensureReleaseCompatibility() {
    var response = await fetch("/api/v1/contract", {
      method: "GET", credentials: "same-origin", cache: "no-store"
    });
    if (!response.ok) throw new Error("Server API contract unavailable (HTTP " + response.status + ").");
    var doc;
    try { doc = await response.json(); }
    catch (error) { throw new Error("Server API contract is not valid JSON."); }
    compatibleContract = checkReleaseCompatibility(doc);
    return compatibleContract;
  }

  async function authRequest(path, method, body) {
    // Also protect a login click racing the asynchronous startup handshake.
    if (!compatibleContract) await ensureReleaseCompatibility();
    var options = {method: method || "GET", credentials: "same-origin", cache: "no-store"};
    if (method === "POST") {
      options.headers = {"Content-Type": "application/json", "X-CSRFToken": csrfFromCookie()};
      options.body = JSON.stringify(body || {});
    }
    var response = await fetch("/api/v1/auth/" + path, options);
    var data;
    try { data = await response.json(); }
    catch (error) { throw new Error("The server returned a non-JSON response."); }
    if (!response.ok) throw new Error((data.error || "HTTP " + response.status) + " (" + response.status + ")");
    return data;
  }

  function addBadges(target, items) {
    target.replaceChildren();
    (items || []).forEach(function (value) {
      var span = document.createElement("span");
      span.className = "server-badge";
      span.textContent = value;
      target.appendChild(span);
    });
    if (!items || !items.length) target.textContent = "None";
  }

  function action(label, path, method) {
    var button = document.createElement("button");
    button.textContent = label;
    button.type = "button";
    button.addEventListener("click", async function () {
      button.disabled = true;
      try { status(JSON.stringify(await authRequest(path, method || "GET"), null, 2), false); }
      catch (error) { status("Request refused: " + error.message, true); }
      finally { button.disabled = false; }
    });
    actions.appendChild(button);
  }

  function renderModels() {
    modelList.innerHTML = TYPES.map(function (type) {
      return modelsUi.renderLane(cachedModels.filter(function (item) { return item.type === type; }), {
        type: type, canWrite: grants.includes("business_write"), showRevisions: true
      });
    }).join("");
  }

  async function refreshModels() {
    var generation = ++refreshGeneration;
    catalogStatus("Loading real Models from Server…", false);
    try {
      var rowsByType = await Promise.all(TYPES.map(function (type) { return adapters[type].list(); }));
      if (generation !== refreshGeneration || catalog.hidden) return;
      cachedModels = rowsByType.flat();
      renderModels();
      catalogStatus(cachedModels.length + " real catalog item(s) stored in PostgreSQL.", false);
    } catch (error) {
      if (generation !== refreshGeneration || catalog.hidden) return;
      cachedModels = [];
      modelList.replaceChildren(); // fail closed: never show stale items as if authoritative
      catalogStatus("Models unavailable: " + error.message, true);
    }
  }

  function displayIdentity(data) {
    ++refreshGeneration;
    editor.hidden = true;
    history.hidden = true;
    raw.hidden = true;
    evidence.hidden = true;
    ++evidenceGeneration;
    if (!data.authenticated) {
      grants = [];
      window.AICompassDraftAccount = "";
      document.getElementById("server-workgroup-home").hidden = true;
      document.getElementById("server-workgroup-summary").hidden = true;
      sharedCatalog.setAccess(false, false);
      environment.setAccess(false);
      engineer.setAccess(false);
      pricing.setAccess(false,false);
      personas.replaceChildren(); personas.hidden = true;
      tasks.setAccess(false, false);
      testCases.setAccess(false, false);
      guides.setAccess(false, false);
      watch.setAccess(false, false, false);
      forecasts.setAccess(false, false, false);
      campaigns.setAccess(false, false, false);
      resultsExplorer.setAccess(false, false);
      recommendations.setAccess(false, false, false);
      discussions.setAccess(false, false, false);
      users.setAccess(false, false);
      activity.setAccess(false, false);
      governanceAudit.setAccess(false);
      health.setAccess(false, false);
      planning.setAccess(false, false);
      document.getElementById("server-maintenance-nav").hidden = true;
      cachedModels = [];
      modelList.replaceChildren();
      catalog.hidden = true;
      account.hidden = true;
      form.hidden = false;
      document.getElementById("server-side-navigation").replaceChildren();
      document.getElementById("ux-page-title").textContent = "Server sign in";
      window.AICompassShell.selectScreen(serverScreenHost, "ux-auth-panel");
      status("Signed out. Use a real Server account created by the operator.", false);
      return;
    }
    grants = data.permissions || [];
    environment.setAccess(!maintenanceWorkspace && grants.includes("business_read"));
    window.AICompassDraftAccount = data.username;
    var requestedPersona = new URLSearchParams(window.location.search).get("workspace");
    var activePersona = window.AICompassRuntime.choosePersona(data, "server", requestedPersona);
    var personaId = maintenanceWorkspace ? "maintenance" : activePersona && activePersona.id;
    if (!maintenanceWorkspace && !requestedPersona && grants.includes("business_write"))
      personaId = "workgroup";
    personas.innerHTML = window.AICompassRuntime.renderPersonaLinks(data, "server", personaId);
    engineer.setAccess(!maintenanceWorkspace &&
      (personaId === "engineer" || (personaId === "workgroup" &&
        new URLSearchParams(window.location.search).get("section") === "engineer")) &&
      grants.includes("business_read"));
    personas.hidden = !personas.textContent.trim();
    pricing.setAccess(!maintenanceWorkspace &&
      ["engineer","workgroup"].includes(personaId) && grants.includes("business_read"),
      personaId==="workgroup" && grants.includes("business_write"));
    sharedCatalog.setAccess(!maintenanceWorkspace &&
      ["engineer", "workgroup"].includes(personaId) && grants.includes("business_read"),
      personaId === "workgroup" && grants.includes("business_write"));
    tasks.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"));
    testCases.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"));
    guides.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"));
    watch.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"), !maintenanceWorkspace && grants.includes("publication_review"));
    forecasts.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"), !maintenanceWorkspace && grants.includes("publication_review"));
    campaigns.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"), !maintenanceWorkspace && grants.includes("publication_review"));
    resultsExplorer.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"), !maintenanceWorkspace && grants.includes("publication_review"));
    recommendations.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"), !maintenanceWorkspace && grants.includes("publication_review"));
    discussions.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"), !maintenanceWorkspace && grants.includes("publication_review"));
    users.setAccess(!maintenanceWorkspace && grants.includes("users_manage"), !maintenanceWorkspace && grants.includes("platform_manage"));
    activity.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("users_manage"));
    governanceAudit.setAccess(maintenanceWorkspace && grants.includes("audit_view"));
    health.setAccess(maintenanceWorkspace && grants.includes("maintenance_view"), maintenanceWorkspace && grants.includes("maintenance_triage"));
    planning.setAccess(!maintenanceWorkspace && grants.includes("planning_view"), !maintenanceWorkspace && grants.includes("planning_manage"));
    managementInsights.setAccess(!maintenanceWorkspace &&
      grants.includes("planning_view") && personaId === "management");
    document.getElementById("server-maintenance-nav").hidden = !grants.includes("maintenance_view");
    form.hidden = true;
    account.hidden = false;
    document.getElementById("server-account-name").textContent = data.username;
    addBadges(document.getElementById("server-roles"), data.roles);
    addBadges(document.getElementById("server-capabilities"), grants);
    actions.replaceChildren();
    if (grants.includes("business_read")) action("Read protected example", "sandbox", "GET");
    if (grants.includes("business_write")) action("Write to private session example", "sandbox/write", "POST");
    if (grants.includes("maintenance_view")) action("Maintenance dashboard", "maintenance", "GET");
    if (grants.includes("users_manage")) action("User administration check", "user-admin", "GET");
    if (grants.includes("platform_view")) action("Platform operations", "platform", "GET");
    status("Authenticated as " + data.username + ". Permissions are enforced by Django.", false);
    catalog.hidden = maintenanceWorkspace || !grants.includes("business_read") ||
      personaId !== "workgroup";
    // Existing controllers retain full permission-aware API behavior. Persona
    // entry affects presentation only; the backend always enforces real grants.
    if (personaId === "management") {
      tasks.setAccess(false, false);
      ["server-test-cases","server-guides","server-watch","server-forecasts",
        "server-campaigns","server-recommendations","server-discussions",
        "server-users","server-activity"].forEach(function (id) {
        document.getElementById(id).hidden = true;
      });
    } else if (personaId === "engineer") {
      // Engineer starts with task and catalog discovery; advanced Workgroup
      // authoring stays in its dedicated entry rather than an extra shell.
      ["server-task-tree","server-test-cases","server-guides","server-watch",
        "server-forecasts","server-campaigns","server-recommendations",
        "server-discussions","server-users","server-data-health",
        "server-planning","server-activity"].forEach(function (id) {
        document.getElementById(id).hidden = true;
      });
    }
    if (!catalog.hidden) refreshModels();
    // FUT-04 one categorized Workgroup home and deep-linked context. The
    // legacy domain editors remain exactly the same authorized controllers.
    var group = window.AICompassWorkgroup;
    var home = document.getElementById("server-workgroup-home");
    var summary = document.getElementById("server-workgroup-summary");
    home.hidden = true; summary.hidden = true;
    if (!maintenanceWorkspace && personaId === "workgroup" &&
        grants.includes("business_write") && group) {
      var section = new URLSearchParams(window.location.search).get("section") || "studio";
      if (section !== "studio" && !["account","users"].includes(section) && !group.canVisit(section, grants, "server", true))
        section = "studio";
      var ids = Object.keys(group.SECTION_TO_SERVER).map(function(x){return group.SECTION_TO_SERVER[x];});
      ids.forEach(function(id){var el=document.getElementById(id);if(el)el.hidden = true;});
      catalog.hidden = true;
      home.hidden = false;
      function showHome(counts) {
        home.innerHTML = (section === "studio" ?
            group.renderMap("server", data, grants, true, counts) :
            '<div class="server-card"><h2>' + modelsUi.escapeHtml(section.replaceAll("-"," ")) +
            '</h2><p class="muted">Real Server data, exact revision history and authorized actions.</p>' +
            '<button type="button" id="workgroup-show-editor">Open full workspace / edit / history</button></div>');
        if (section !== "studio") {
          document.getElementById("workgroup-show-editor").onclick = function() {
            var next = new URL(window.location.href);
            next.searchParams.set("view", "editor");
            window.location.assign(next.href);
          };
        }
      }
      showHome({});
      if (section === "studio") {
        var api = window.AICompassRuntime.ServerTransport(fetch, csrfFromCookie);
        Promise.allSettled(["campaigns", "forecasts", "recommendations"].map(function(id) {
          return api.request("/api/v1/" + id);
        })).then(function(results){
          if(home.hidden)return;
          var counters={};
          ["benchmark", "forecasts", "recommendations"].forEach(function(section,i){
            var result=results[i];
            if(result.status==="fulfilled")
              counters[section]=group.attention(section,result.value.results);
          });
          showHome(counters);
        });
      } else {
        var target=document.getElementById(group.SECTION_TO_SERVER[section]);
        if(target && group.STABLE[section]) {
          summary.hidden=false;
          summary.innerHTML='<div id="server-shared-summary"></div>';
          var summaryProvider=group.serverProvider(
            window.AICompassRuntime.ServerTransport(fetch,csrfFromCookie));
          group.mountSummary(document.getElementById("server-shared-summary"),
            summaryProvider,section,"server",{
              recordId:new URLSearchParams(window.location.search).get("record"),
              revision:new URLSearchParams(window.location.search).get("revision"),
              link:function(id){return window.AICompassContext.contextualLink(
                "server","workgroup",section,id);}
            }).show().catch(function(){ /* visible error is already fail-closed */ });
        } else if(target) {
          target.hidden=false;
        }
      }
    }
    // Roles control capabilities, never how many business screens are stacked.
    // One route chooses one screen even for multi-role administrators.
    var route = new URLSearchParams(window.location.search);
    var currentSection = route.get("section") ||
      (maintenanceWorkspace ? "audit" : personaId === "workgroup" ? "studio" : "home");
    var screen = "";
    if (maintenanceWorkspace) {
      screen = currentSection === "health" && grants.includes("maintenance_view") ?
        "server-data-health" : grants.includes("audit_view") ? "server-governance-audit" :
        grants.includes("maintenance_view") ? "server-data-health" : "ux-auth-panel";
    } else if (currentSection === "users" && grants.includes("users_manage")) {
      screen = "server-users";
    } else if (currentSection === "account") {
      screen = "ux-auth-panel";
    } else if (personaId === "workgroup" && grants.includes("business_write")) {
      var sections = window.AICompassWorkgroup.SECTION_TO_SERVER;
      if (currentSection === "studio" || !sections[currentSection]) {
        screen = "ux-workgroup-overview";
        currentSection = "studio";
      } else if (window.AICompassWorkgroup.STABLE[currentSection] &&
                 route.get("view") !== "editor") {
        screen = "ux-workgroup-overview";
      } else {
        screen = sections[currentSection];
      }
    } else if (personaId === "engineer" && grants.includes("business_read")) {
      var engineerRoutes = {home:"server-engineer",tasks:"server-task-tree",
        catalog:"server-model-catalog",results:"server-results",
        guides:"server-guides",environment:"server-environment-profile"};
      screen = engineerRoutes[currentSection] || engineerRoutes.home;
    } else if (personaId === "management" && grants.includes("planning_view")) {
      screen = currentSection === "planning" ? "server-planning" : "server-management-insights";
    } else {
      screen = grants.includes("users_manage") ? "server-users" : "ux-auth-panel";
    }
    var sidebar = document.getElementById("server-side-navigation");
    sidebar.innerHTML = window.AICompassShell.serverNav(
      personaId, grants, currentSection, maintenanceWorkspace);
    window.AICompassShell.selectScreen(serverScreenHost, screen);
    window.AICompassContext.syncContext(contextNav,"server",
      maintenanceWorkspace?"maintenance":personaId,currentSection);
    var active = document.getElementById(screen);
    var label = active && active.querySelector("h2") ||
      active && active.querySelector("h1");
    document.getElementById("ux-page-title").textContent =
      label ? label.textContent.trim().slice(0,90) :
      maintenanceWorkspace ? "Maintenance & Governance" :
      personaId === "workgroup" ? "AI Workgroup Studio" :
      personaId === "management" ? "Management Insights" :
      personaId === "engineer" ? "My AI Workspace" : "Account";
    dialogCoordinator.sync();
  }

  function field(name, title, value, type, extra) {
    var nameHtml = escapeHtml(name), valueHtml = escapeHtml(value);
    var input = type === "textarea" ?
      '<textarea name="' + nameHtml + '" id="server-field-' + nameHtml + '">' + valueHtml + '</textarea>' :
      '<input name="' + nameHtml + '" id="server-field-' + nameHtml + '" type="' +
        escapeHtml(type || "text") + '" value="' + valueHtml + '"' +
        (name === "name" ? ' required maxlength="160"' : "") + '>';
    return '<div class="' + (extra === "full" ? "span2" : "") +
      '"><label for="server-field-' + nameHtml + '">' + escapeHtml(title) +
      '</label>' + input + '</div>';
  }
  function select(name, title, options, value) {
    return '<div><label for="server-field-' + escapeHtml(name) + '">' + escapeHtml(title) +
      '</label><select name="' + escapeHtml(name) + '" id="server-field-' + escapeHtml(name) + '">' +
      options.map(function (entry) {
        return '<option value="' + escapeHtml(entry[0]) + '"' +
          (entry[0] === value ? " selected" : "") + '>' + escapeHtml(entry[1]) + "</option>";
      }).join("") + "</select></div>";
  }

  function showEditor(item, requestedType) {
    if (!grants.includes("business_write")) return;
    if (item && item.readOnly) {
      showRaw(item);
      catalogStatus("Editing blocked: historical or unsupported catalog item requires schema review. Original data is preserved.", true);
      return;
    }
    history.hidden = true;
    evidence.hidden = true;
    var p = (item && item.properties) || {};
    var extras = {};
    Object.keys(p).forEach(function (key) {
      if (!["version", "url", "details", "publication", "status", "accessible",
        "hosting","access","pricing","endpoint","interface","integrations","process","orchestration","stages"].includes(key)) extras[key] = p[key];
    });
    editor.hidden = false;
    var type = item ? item.type : (requestedType || "model");
    if (!TYPES.includes(type)) throw new Error("Unsupported catalog component");
    var typeFields = {
      provider: [["hosting","Hosting"],["access","Access / API terms"],
        ["pricing","Pricing description"],["endpoint","Endpoint"]],
      harness: [["interface","Interface (cli / ide / web / agent / multi)"],
        ["integrations","Integrations (comma-separated)"]],
      framework: [["process","Process / methodology"],["orchestration","Orchestration design"],
        ["stages","Stages (comma-separated)"]]
    };
    var typedFields = (typeFields[type] || []).map(function (entry) {
      var value = p[entry[0]] == null ? "" : p[entry[0]];
      return field(entry[0], entry[1], Array.isArray(value) ? value.join(", ") : value);
    }).join("");
    editor.innerHTML = '<h2>' + (item ? "Edit " : "Create ") +
      escapeHtml(type.charAt(0).toUpperCase() + type.slice(1)) + '</h2>' +
      '<p class="muted small">' + (item ?
        'Editing ' + escapeHtml(item.id) + ' · ' + escapeHtml(item.revision) +
        '. Saving appends a new immutable revision.' :
        'Server creation starts from an empty real catalog; Demo records are not imported.') + '</p>' +
      '<p id="server-editor-status" class="server-status" role="status"></p>' +
      '<form id="server-model-form" class="server-model-form" data-id="' +
      escapeHtml(item ? item.id : "") + '"><div class="form-grid">' +
      field("name", "Component name", item ? item.name : "", "text", "full") +
      field("version", "Version / revision (if applicable)", p.version || "") +
      select("publication", "Publication status", [["draft","Draft"],["published","Published"]], p.publication || "published") +
      select("accessible", "Accessible to the company?", [["yes","Yes"],["no","No"]], p.accessible === false ? "no" : "yes") +
      select("status", "Technology lifecycle", [["active","Active"],["watching","Watch candidate"],["retired","Retired"]], p.status || "active") +
      field("url", "Official project URL (optional)", p.url || "", "url", "full") +
      field("details", "Notes, capabilities, limitations", p.details || "", "textarea", "full") +
      typedFields +
      field("extras", "Other schema properties (JSON object; preserved verbatim)", JSON.stringify(extras, null, 2), "textarea", "full") +
      '</div><button type="submit" id="server-model-save">Save Model to Server</button>' +
      '<button type="button" id="server-model-cancel">Cancel</button></form>';
    editor.querySelector("#server-model-cancel").addEventListener("click", function () {
      editor.hidden = true;
    });
    editor.querySelector("#server-model-form").addEventListener("submit", function (event) {
      event.preventDefault();
      submitModel(event.target, item, type);
    });
    editor.scrollIntoView({block: "nearest", behavior: "smooth"});
  }

  function modelProperties(formElement, previous, type) {
    var values = Object.fromEntries(new FormData(formElement).entries());
    var extras;
    try { extras = JSON.parse(values.extras || "{}"); }
    catch (error) { throw new Error("Other properties must be valid JSON."); }
    if (!extras || Array.isArray(extras) || typeof extras !== "object") {
      throw new Error("Other properties must be a JSON object.");
    }
    var p = Object.assign({}, previous ? previous.properties : {}, extras);
    var typeKeys = {provider: ["hosting","access","pricing","endpoint"],
      harness: ["interface","integrations"],
      framework: ["process","orchestration","stages"]};
    (typeKeys[type] || []).forEach(function (key) {
      if (["integrations","stages"].includes(key))
        p[key] = (values[key] || "").split(",").map(function (v) { return v.trim(); }).filter(Boolean);
      else if (values[key] !== undefined) p[key] = values[key];
    });
    p.version = values.version || "";
    p.details = values.details || "";
    p.url = values.url || "";
    p.publication = values.publication;
    p.status = values.status;
    p.accessible = values.accessible === "yes";
    if (p.url) {
      var parsed;
      try { parsed = new URL(p.url); } catch (error) { throw new Error("Official URL must be valid HTTP(S)."); }
      if (!["http:", "https:"].includes(parsed.protocol)) throw new Error("Official URL must be HTTP(S).");
    }
    if (!values.name || !values.name.trim()) throw new Error("Component name is required.");
    return {name: values.name.trim(), properties: p};
  }

  async function submitModel(formElement, original, type) {
    var saveButton = formElement.querySelector("#server-model-save");
    var message = editor.querySelector("#server-editor-status");
    saveButton.disabled = true;
    message.textContent = "Saving to Server…";
    message.className = "server-status";
    try {
      var next = modelProperties(formElement, original, type);
      var typedAdapter = adapters[type];
      if (original) {
        next.expected_revision = original.revision;
        await typedAdapter.revise(original.id, next);
      } else {
        await typedAdapter.create(next);
      }
      editor.hidden = true;
      await refreshModels();
    } catch (error) {
      message.textContent = error.status === 409 ?
        "Revision conflict: another user has updated this Model. Your draft was not overwritten. Review the latest version and retry." :
        "Save failed: " + error.message + " No local/Demo save was performed.";
      message.className = "server-status server-error";
    } finally { saveButton.disabled = false; }
  }

  async function showHistory(id) {
    editor.hidden = true;
    history.hidden = false;
    raw.hidden = true;
    evidence.hidden = true;
    history.classList.remove("server-error");
    history.textContent = "Loading immutable catalog revisions…";
    try {
      var item = cachedModels.find(function (row) { return row.id === id; });
      if (!item) throw new Error("Unknown catalog item");
      var versions = await adapters[item.type].revisions(id);
      if (history.hidden) return;
      history.innerHTML = '<h2>Model revision history</h2><p class="muted small">' +
        escapeHtml(id) + ' · ' + versions.length + ' revision(s) · read only</p>' +
        versions.map(function (row) {
          return '<details' + (row === versions[versions.length - 1] ? " open" : "") +
            '><summary><strong>' + escapeHtml(row.revision) + ' · ' +
            escapeHtml(row.name) + '</strong> · ' + escapeHtml(row.created_by) +
            ' · ' + escapeHtml(row.created_at) + '</summary><div class="muted small">Schema v' +
            escapeHtml(row.schema_version == null ? "unknown" : row.schema_version) +
            ' · ' + escapeHtml(row.compatibility && row.compatibility.status || "unsupported") +
            ' · ' + escapeHtml(row.compatibility && row.compatibility.reason || "") +
            '</div><pre>' +
            escapeHtml(JSON.stringify(row.properties, null, 2)) + '</pre></details>';
        }).join("") +
        '<button type="button" id="server-model-close-history">Close history</button>';
      history.querySelector("#server-model-close-history").addEventListener("click", function () {
        history.hidden = true;
      });
    } catch (error) {
      history.textContent = "History unavailable: " + error.message;
      history.classList.add("server-error");
    }
  }

  function showRaw(record) {
    editor.hidden = true;
    history.hidden = true;
    evidence.hidden = true;
    raw.hidden = false;
    var diagnostic = record.compatibility || {status: "unsupported", read_only: true};
    var metadata = {
      id: record.id, type: record.type, revision: record.revision,
      schema_version: record.schema_version,
      created_at: record.created_at, created_by: record.created_by,
      name: record.name, compatibility: diagnostic,
      original_properties: record.properties
    };
    raw.innerHTML = '<h2>Original catalog data — read only</h2>' +
      '<p class="muted small">No defaults or conversions are applied to this source snapshot.</p>' +
      '<pre style="white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6fa;padding:12px">' +
      escapeHtml(JSON.stringify(metadata, null, 2)) + '</pre>' +
      '<button type="button" id="server-close-raw">Close</button>';
    raw.querySelector("#server-close-raw").addEventListener("click", function () {
      raw.hidden = true;
    });
    raw.scrollIntoView({block: "nearest", behavior: "smooth"});
  }

  async function showEvidence(id) {
    if (!grants.includes("business_read")) return;
    var item = cachedModels.find(function (entry) { return entry.id === id; });
    if (!item) return;
    var ticket = ++evidenceGeneration;
    editor.hidden = true;
    history.hidden = true;
    raw.hidden = true;
    evidence.hidden = false;
    evidence.textContent = "Loading verified evidence attachments…";
    try {
      var response = await fetch("/api/v1/catalog/items/" + encodeURIComponent(id) + "/evidence", {
        credentials: "same-origin", cache: "no-store"
      });
      if (!response.ok) throw new Error("HTTP " + response.status);
      var payload = await response.json();
      if (ticket !== evidenceGeneration || evidence.hidden || catalog.hidden) return;
      var entries = payload.results || [];
      evidence.innerHTML = '<h2>Original evidence for ' + escapeHtml(item.name) + '</h2>' +
        '<p class="muted small">Immutable bytes · exact revision references · distinct provenance for each link.</p>' +
        (entries.length ? '<div class="list">' + entries.map(function (row) {
          // A listing is metadata-only. Byte checksum is verified at download.
          var download = row.integrity === "broken" ?
            '<strong>Integrity failure — original unavailable</strong>' :
            '<a href="' + escapeHtml(row.download) + '">Download original bytes (SHA-256 checked on request)</a>' +
            '<span class="muted small"> · Integrity ' + escapeHtml(row.integrity === "ok" ? "verified" : "not checked in listing") + '</span>';
          return '<div class="list-row"><div><strong>' + escapeHtml(row.filename) + '</strong>' +
            '<div class="muted small">SHA-256: ' + escapeHtml(row.sha256) + '</div>' +
            '<div class="muted small">Target: ' + escapeHtml(row.revision || "catalog item") +
            ' · Uploader: ' + escapeHtml(row.uploaded_by) +
            ' · Source: ' + escapeHtml(row.source || "not specified") + '</div>' +
            '<div class="muted small">' + escapeHtml(JSON.stringify(row.provenance)) +
            '</div>' + download + '</div></div>';
        }).join("") + '</div>' : '<p>No evidence attached to this record.</p>') +
        (grants.includes("business_write") ?
          '<form id="server-evidence-upload" enctype="multipart/form-data">' +
          '<h3>Attach immutable evidence</h3>' +
          '<label>Document (PDF, image, text, JSON or ZIP; max 16 MiB)</label>' +
          '<input type="file" name="file" required accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.md,.csv,.json,.zip">' +
          '<label>Exact revision (optional, e.g. r001; blank means record)</label>' +
          '<input name="revision" placeholder="' + escapeHtml(item.revision || "r001") + '">' +
          '<label>Source / provenance reference</label><input name="source" maxlength="600">' +
          '<label>Additional provenance JSON object</label>' +
          '<textarea name="provenance">{}</textarea>' +
          '<button type="submit">Upload immutable document</button>' +
          '<p id="server-evidence-upload-state" role="status"></p></form>' : "") +
        '<button type="button" id="server-close-evidence">Close evidence</button>';
      evidence.querySelector("#server-close-evidence").addEventListener("click", function () {
        evidence.hidden = true; ++evidenceGeneration;
      });
      var form = evidence.querySelector("#server-evidence-upload");
      if (form) form.addEventListener("submit", async function (event) {
        event.preventDefault();
        var message = evidence.querySelector("#server-evidence-upload-state");
        var button = form.querySelector('button[type="submit"]');
        button.disabled = true;
        message.textContent = "Uploading to private Server evidence store…";
        try {
          var multipart = new FormData(form);
          var parsed = JSON.parse(multipart.get("provenance") || "{}");
          if (!parsed || typeof parsed !== "object" || Array.isArray(parsed))
            throw new Error("Provenance must be a JSON object");
          var upload = await fetch("/api/v1/catalog/items/" + encodeURIComponent(id) +
            "/evidence/upload", {
            method: "POST", credentials: "same-origin", cache: "no-store",
            headers: {"X-CSRFToken": csrfFromCookie()}, body: multipart
          });
          if (!upload.ok) {
            var error = await upload.json().catch(function () { return {}; });
            throw new Error(error.detail || ("HTTP " + upload.status));
          }
          await showEvidence(id);
        } catch (error) {
          message.textContent = "Upload refused: " + error.message +
            ". No Demo data was saved.";
          button.disabled = false;
        }
      });
    } catch (error) {
      if (ticket !== evidenceGeneration || evidence.hidden) return;
      evidence.textContent = "Evidence unavailable: " + error.message;
      evidence.classList.add("server-error");
    }
  }

  document.getElementById("server-inspect-catalog-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    if (!grants.includes("business_read")) return;
    var target = document.getElementById("server-inspect-id").value.trim();
    if (!/^[A-Za-z0-9_-]{1,120}$/.test(target)) {
      catalogStatus("Invalid catalog identifier format.", true);
      return;
    }
    try {
      var response = await fetch("/api/v1/catalog/items/" + encodeURIComponent(target),
        {credentials: "same-origin", cache: "no-store"});
      if (!response.ok) throw new Error("Read denied or catalog record not found (HTTP " + response.status + ")");
      var row = await response.json();
      showRaw(modelsUi.modelFromApi(row));
      catalogStatus("Showing exact original catalog fields; unsupported schemas are read only.", false);
    } catch (error) {
      catalogStatus("Cannot inspect record: " + error.message, true);
    }
  });

  modelList.addEventListener("click", function (event) {
    var button = event.target.closest("button[data-act]");
    if (!button) return;
    var act = button.dataset.act, id = button.dataset.id;
    if (act === "newComponentType" && TYPES.includes(id)) showEditor(null, id);
    if (act === "editComponent") {
      var model = cachedModels.find(function (item) { return item.id === id; });
      if (model) showEditor(model);
    }
    if (act === "modelHistory") showHistory(id);
    if (act === "catalogEvidence") showEvidence(id);
    if (act === "modelRaw") {
      var record = cachedModels.find(function (item) { return item.id === id; });
      if (record) showRaw(record);
    }
  });
  document.getElementById("server-model-refresh").addEventListener("click", function () {
    editor.hidden = true;
    history.hidden = true;
    raw.hidden = true;
    evidence.hidden = true;
    ++evidenceGeneration;
    refreshModels();
  });

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var button = form.querySelector("button");
    button.disabled = true;
    try {
      await authRequest("csrf");
      var data = await authRequest("login", "POST", {
        username: document.getElementById("server-username").value,
        password: document.getElementById("server-password").value
      });
      document.getElementById("server-password").value = "";
      await authRequest("csrf"); // Django rotates CSRF on login.
      displayIdentity(data);
    } catch (error) { status("Sign in failed: " + error.message, true); }
    finally { button.disabled = false; }
  });

  document.getElementById("server-logout").addEventListener("click", async function () {
    try {
      await authRequest("csrf");
      await authRequest("logout", "POST");
      document.getElementById("server-password").value = "";
      displayIdentity({authenticated: false});
    } catch (error) { status("Sign out failed: " + error.message, true); }
  });

  (async function boot() {
    try {
      await ensureReleaseCompatibility();
      await authRequest("csrf");
      displayIdentity(await authRequest("me"));
    } catch (error) {
      account.hidden = true;
      form.hidden = true;
      catalog.hidden = true;
      document.getElementById("server-workgroup-home").hidden = true;
      document.getElementById("server-workgroup-summary").hidden = true;
      sharedCatalog.setAccess(false, false);
      tasks.setAccess(false, false);
      testCases.setAccess(false, false);
      guides.setAccess(false, false);
      campaigns.setAccess(false, false, false);
      users.setAccess(false, false);
      activity.setAccess(false, false);
      health.setAccess(false, false);
      document.getElementById("server-maintenance-nav").hidden = true;
      document.getElementById("server-side-navigation").replaceChildren();
      window.AICompassShell.selectScreen(serverScreenHost, "ux-auth-panel");
      status("Server unavailable. Demo data will NOT be loaded automatically. " + error.message, true);
    }
  })();
})();
