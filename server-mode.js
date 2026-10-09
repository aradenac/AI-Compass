/* PLAT-02: Authenticated shell for the SAME prototype.html frontend.
 * Demo and Server intentionally never share a data store, user or fallback. */
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

  var root = document.getElementById("app");
  var style = document.createElement("style");
  style.textContent = ".server-card{background:white;border:1px solid #e3e8f0;border-radius:14px;padding:24px;max-width:740px;box-shadow:0 8px 32px #1227470d}.server-page{min-height:100vh;background:#f4f6fa;display:grid;grid-template-columns:245px minmax(0,1fr)}.server-sidebar{background:#111e35;color:#dce5f7;padding:30px 20px}.server-sidebar a{color:#b4e3ff}.server-main{padding:clamp(18px,5vw,55px)}.server-main h1{margin-bottom:12px}.server-card p{margin:9px 0}.server-card label{display:block;margin:12px 0 6px;font-weight:600}.server-card input{display:block;width:100%;max-width:390px;padding:11px;border:1px solid #c4cedd;border-radius:8px}.server-card button{padding:10px 15px;margin:12px 8px 0 0;background:#3159d7;color:white;border:0;border-radius:8px}.server-card button:disabled{opacity:.55}.server-actions{margin-top:14px}.server-status{white-space:pre-wrap;margin:12px 0;color:#394b66}.server-error{color:#ac303d}.server-badge{display:inline-block;padding:4px 9px;border-radius:6px;background:#e8f7f4;color:#096a70;margin:4px 4px 4px 0}.server-card [hidden]{display:none!important}@media(max-width:700px){.server-page{display:block}.server-sidebar{padding:16px}.server-main{padding:18px}}";
  document.head.appendChild(style);

  root.innerHTML = [
    '<div class="server-page">',
    ' <aside class="server-sidebar"><div style="font-size:23px;font-weight:750;margin-bottom:12px">AI Compass</div>',
    '  <strong>Server mode</strong><p style="margin:14px 0">Authenticated shared backend</p>',
    '  <a href="?mode=demo">Return to independent Demo mode</a>',
    '  <p style="margin-top:25px;font-size:12px">The Demo catalog is intentionally not loaded or copied here.</p>',
    ' </aside>',
    ' <main class="server-main"><h1>Server workspace</h1>',
    '  <p style="margin-bottom:20px;color:#64748b">Real Django session · independent role permissions · PostgreSQL</p>',
    '  <div class="server-card">',
    '   <p id="server-state" class="server-status" role="status" aria-live="polite">Connecting to backend…</p>',
    '   <form id="server-login-form" hidden>',
    '    <h2>Sign in</h2>',
    '    <label for="server-username">Username</label><input id="server-username" autocomplete="username" maxlength="150" required>',
    '    <label for="server-password">Password</label><input id="server-password" type="password" autocomplete="current-password" required>',
    '    <button type="submit">Sign in to Server</button>',
    '   </form>',
    '   <section id="server-account" hidden>',
    '    <h2>Signed-in account</h2><p id="server-account-name"></p>',
    '    <p><strong>Roles</strong></p><div id="server-roles"></div>',
    '    <p><strong>Capabilities</strong></p><div id="server-capabilities"></div>',
    '    <p style="font-size:12px;color:#64748b">Only identity and permission-protected demonstration endpoints exist in PLAT-02. Catalog data APIs arrive in later increments.</p>',
    '    <div class="server-actions" id="server-actions"></div>',
    '    <button id="server-logout">Sign out</button>',
    '   </section>',
    '  </div>',
    ' </main>',
    '</div>'
  ].join("");

  var state = document.getElementById("server-state");
  var form = document.getElementById("server-login-form");
  var account = document.getElementById("server-account");
  var actions = document.getElementById("server-actions");

  function status(message, isError) {
    state.textContent = message;
    state.className = isError ? "server-status server-error" : "server-status";
  }

  function csrfFromCookie() {
    var row = document.cookie.split("; ").find(function (v) { return v.startsWith("csrftoken="); });
    return row ? decodeURIComponent(row.substring("csrftoken=".length)) : "";
  }

  async function apiRequest(path, method, body) {
    var options = {method: method || "GET", credentials: "same-origin", cache: "no-store"};
    if (method === "POST") {
      options.headers = {"Content-Type": "application/json", "X-CSRFToken": csrfFromCookie()};
      options.body = JSON.stringify(body || {});
    }
    var response = await fetch("/api/v1/auth/" + path, options);
    var data;
    try { data = await response.json(); }
    catch (error) { throw new Error("The server returned a non-JSON response."); }
    if (!response.ok) {
      var code = (data && data.error) || "HTTP " + response.status;
      throw new Error(code + " (" + response.status + ")");
    }
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
      try {
        var result = await apiRequest(path, method || "GET");
        status(JSON.stringify(result, null, 2), false);
      } catch (error) {
        status("Request refused: " + error.message, true);
      } finally {
        button.disabled = false;
      }
    });
    actions.appendChild(button);
  }

  function displayIdentity(data) {
    if (!data.authenticated) {
      account.hidden = true;
      form.hidden = false;
      status("Signed out. Use a real Server account created by the operator.", false);
      return;
    }
    form.hidden = true;
    account.hidden = false;
    document.getElementById("server-account-name").textContent = data.username;
    addBadges(document.getElementById("server-roles"), data.roles);
    addBadges(document.getElementById("server-capabilities"), data.permissions);
    actions.replaceChildren();
    var grants = data.permissions || [];
    if (grants.includes("business_read")) action("Read protected example", "sandbox", "GET");
    if (grants.includes("business_write")) action("Write to private session example", "sandbox/write", "POST");
    if (grants.includes("maintenance_view")) action("Maintenance dashboard", "maintenance", "GET");
    if (grants.includes("users_manage")) action("User administration check", "user-admin", "GET");
    if (grants.includes("platform_view")) action("Platform operations", "platform", "GET");
    status("Authenticated. Actions and API routes are enforced by Django, not the menu.", false);
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var button = form.querySelector("button");
    button.disabled = true;
    try {
      await apiRequest("csrf");
      var data = await apiRequest("login", "POST", {
        username: document.getElementById("server-username").value,
        password: document.getElementById("server-password").value
      });
      document.getElementById("server-password").value = "";
      await apiRequest("csrf"); // Django rotates CSRF tokens on login.
      displayIdentity(data);
    } catch (error) {
      status("Sign in failed: " + error.message, true);
    } finally { button.disabled = false; }
  });

  document.getElementById("server-logout").addEventListener("click", async function () {
    try {
      await apiRequest("csrf");
      await apiRequest("logout", "POST");
      document.getElementById("server-password").value = "";
      displayIdentity({authenticated: false});
    } catch (error) { status("Sign out failed: " + error.message, true); }
  });

  (async function boot() {
    try {
      await apiRequest("csrf");
      displayIdentity(await apiRequest("me"));
    } catch (error) {
      account.hidden = true;
      form.hidden = true;
      status("Server unavailable. Backend sign-in is required; Demo data will NOT be loaded automatically. " + error.message, true);
    }
  })();
})();
