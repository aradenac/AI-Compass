/* PLAT-05: real authenticated Server workspace for the shared Models catalog.
 * The Demo runtime is owned by prototype.html and is NEVER read here. */
(function () {
  "use strict";
  var serverMode = new URLSearchParams(window.location.search).get("mode") === "server";
  if (!serverMode) {
    var link = document.createElement("a");
    link.href = "?mode=server";
    link.textContent = "Server sign-in";
    link.title = "Switch explicitly to the server-backed identity workspace";
    link.id = "server-mode-switch";
    link.style.cssText = "position:fixed;right:12px;bottom:12px;z-index:100;background:#111e35;color:white;padding:9px 14px;border-radius:9px;box-shadow:0 4px 18px #172c4633;font:600 12px system-ui";
    document.body.appendChild(link);
    return;
  }

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
    '<a href="?mode=demo">Return to independent Demo mode</a>',
    '<p style="margin-top:25px;font-size:12px">Real technology records are stored in PostgreSQL; fake Demo records are never copied.</p>',
    '</aside>',
    '<main class="server-main"><h1>Technology catalog</h1>',
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
    '<div class="note" style="margin-top:14px">Frameworks describe orchestration and are not benchmarked AI Solutions.</div>',
    '</section></main></div>'
  ].join("");

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
  var cachedModels = [];
  var TYPES = ["model","provider","harness","framework"];
  var adapters = Object.fromEntries(TYPES.map(function (type) {
    return [type, modelsUi.ApiDataProvider(csrfFromCookie, type)];
  }));
  var grants = [];
  var refreshGeneration = 0;
  var adapter = modelsUi.ApiDataProvider(csrfFromCookie);
  var escapeHtml = modelsUi.escapeHtml;

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

  async function authRequest(path, method, body) {
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
    if (!data.authenticated) {
      grants = [];
      cachedModels = [];
      modelList.replaceChildren();
      catalog.hidden = true;
      account.hidden = true;
      form.hidden = false;
      status("Signed out. Use a real Server account created by the operator.", false);
      return;
    }
    grants = data.permissions || [];
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
    catalog.hidden = !grants.includes("business_read");
    if (!catalog.hidden) refreshModels();
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
    if (act === "modelRaw") {
      var record = cachedModels.find(function (item) { return item.id === id; });
      if (record) showRaw(record);
    }
  });
  document.getElementById("server-model-refresh").addEventListener("click", function () {
    editor.hidden = true;
    history.hidden = true;
    raw.hidden = true;
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
      await authRequest("csrf");
      displayIdentity(await authRequest("me"));
    } catch (error) {
      account.hidden = true;
      form.hidden = true;
      catalog.hidden = true;
      status("Server unavailable. Demo data will NOT be loaded automatically. " + error.message, true);
    }
  })();
})();
