#!/usr/bin/env node
"use strict";
/* FUT-03: pure runtime, provider isolation, shared Catalog/Task rendering,
 * API classification and both script bootstraps without extra dependencies. */
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const html = fs.readFileSync("prototype.html", "utf8");
const demoScript = html.match(/<script>\s*("use strict";[\s\S]*?)<\/script>/);
assert(demoScript, "Demo bootstrap must remain an inline, standalone static script");
new vm.Script(demoScript[1], {filename: "demo-inline.js"});
new vm.Script(fs.readFileSync("server-mode.js", "utf8"), {filename: "server-mode.js"});
assert(html.indexOf('<script src="shared-runtime.js"></script>') <
  html.indexOf(demoScript[0]), "Demo provider is selected only after shared runtime loaded");
assert(html.indexOf('<script src="server-tasks.js"></script>') <
  html.indexOf(demoScript[0]), "Demo's Task presenter must already be available");
assert(html.includes('id="shared-demo-tasks"') && html.includes('shared-demo-catalog'));
assert(html.includes('var demoDomain=window.AICompassRuntime.createProviders("demo"'));
const modeCode = fs.readFileSync("server-mode.js", "utf8");
assert(modeCode.includes('AICompassRuntime.createProviders("server"'));
assert(modeCode.includes('AICompassSharedCatalog.mount('));
assert(modeCode.includes('AICompassServerTasks.mount('));

const win = {location: {search: "", pathname: "/"}, URLSearchParams};
const sandbox = {window: win, URLSearchParams, console, Set, Promise};
for (const file of ["model-catalog.js", "shared-runtime.js", "shared-workgroup.js",
  "shared-catalog.js", "server-tasks.js"])
  vm.runInNewContext(fs.readFileSync(file, "utf8"), sandbox, {filename: file});
const rt = win.AICompassRuntime;
assert.equal(rt.modeFromLocation({search: "?mode=server", pathname: "/"}), "server");
assert.equal(rt.modeFromLocation({search: "", pathname: "/maintenance"}), "server");
assert.equal(rt.modeFromLocation({search: "?mode=demo", pathname: "/maintenance"}), "demo");
assert.equal(rt.modeFromLocation({search: "", pathname: "/"}), "demo");
const fake = {catalog: {}}, remote = {catalog: {}};
assert.equal(rt.createProviders("demo", fake, remote).data, fake);
assert.equal(rt.createProviders("server", fake, remote).data, remote);
assert.throws(() => rt.createProviders("server", fake, null), /Server provider missing/);
assert.throws(() => rt.createProviders("demo", null, remote), /Demo provider missing/);
const engineer = {role: "engineer"}, contributor = {permissions: ["business_read", "business_write"]},
  maintainer = {permissions: ["maintenance_view"]};
assert.deepEqual(Array.from(rt.availablePersonas(engineer, "demo"), p => p.id), ["engineer"]);
assert.deepEqual(Array.from(rt.availablePersonas(contributor, "server"), p => p.id),
  ["engineer", "workgroup"]);
assert.deepEqual(Array.from(rt.availablePersonas(maintainer, "server"), p => p.id), ["maintenance"]);
assert.equal(rt.choosePersona(contributor, "server", "maintenance").id, "engineer");
assert(!rt.renderPersonaLinks(contributor, "server", "engineer").includes("Maintenance & Governance"));
assert(rt.renderPersonaLinks(maintainer, "server", "maintenance").includes("/maintenance?mode=server"));

const errors = [401, 403, 409, 422, 503];
(async () => {
  for (const status of errors) {
    const client = rt.ServerTransport(async (url, opt) => {
      assert(url.startsWith("/api/v1/"));
      assert.equal(opt.credentials, "same-origin");
      return {ok: false, status, json: async () => ({error: "forbidden"})};
    }, () => "token");
    await assert.rejects(client.request("/api/v1/tasks"), e =>
      e.status === status && e.code === "forbidden");
  }
  let outbound;
  const client = rt.ServerTransport(async (url, opts) => {
    outbound = {url, opts}; return {ok: true, status: 201, json: async () => ({id: "tsk-one"})};
  }, () => "csrf-rotated");
  assert.equal((await client.request("/api/v1/tasks", "POST", {name: "Valid"})).id, "tsk-one");
  assert.equal(outbound.opts.headers["X-CSRFToken"], "csrf-rotated");
  assert.equal(outbound.opts.cache, "no-store");
  await assert.rejects(rt.ServerTransport(() => {}, () => "").request("/evil"),
    /Only same-origin/);
  await assert.rejects(rt.ServerTransport(async () => {throw Error("offline");}, () => "")
    .request("/api/v1/tasks"), /No Demo fallback/);

  const catalogRow = {
    id: "mdl-white-fox", type: "model", name: "<untrusted>", version: "1.0",
    revision: "r001", properties: {context_window: 1234},
    compatibility: {status: "current", read_only: false}
  };
  function mockRoot() {
    const nodes = new Map();
    function element(selector) {
      if (!nodes.has(selector)) nodes.set(selector, {
        hidden: false, innerHTML: "", textContent: "", onclick: null,
        replaceChildren() { this.innerHTML = ""; },
        querySelector(sub) { return element(selector + " " + sub); }
      });
      return nodes.get(selector);
    }
    return {root: {hidden: false, innerHTML: "", classList: {add() {}},
      querySelector: element, addEventListener() {}}, element};
  }
  const source = {catalog: {}};
  for (const type of ["model", "provider", "harness", "framework"]) {
    source.catalog[type] = {list: async () => type === "model" ? [catalogRow] : [],
      revisions: async () => [catalogRow], create: async () => {}, revise: async () => {}};
  }
  const demo = mockRoot(), server = mockRoot();
  await win.AICompassSharedCatalog.mount(demo.root, source, {mode: "demo"}).setAccess(true, false);
  await win.AICompassSharedCatalog.mount(server.root, source, {mode: "server"}).setAccess(true, false);
  const markup = demo.element("[data-common-list]").innerHTML;
  assert.equal(markup, server.element("[data-common-list]").innerHTML,
    "Same Catalog presenter must render identical rows in Demo and Server");
  assert(markup.includes("&lt;untrusted&gt;") && !markup.includes("<untrusted>"));
  assert(!markup.includes('data-act="editComponent"'), "Read-only role cannot edit");
  const noCatalog = mockRoot();
  await win.AICompassSharedCatalog.mount(noCatalog.root, {
    catalog: Object.fromEntries(Object.keys(source.catalog).map(t => [t, {
      list: async () => { throw Error("backend unavailable"); }
    }]))
  }, {mode: "server"}).setAccess(true, false);
  assert(!noCatalog.element("[data-common-list]").innerHTML.includes("<untrusted>"),
    "Server outage must not render stale or local catalog items");

  function taskSurface() {
    const nodes = new Map();
    function element(selector) {
      if (!nodes.has(selector)) nodes.set(selector, {hidden: false, textContent: "",
        innerHTML: "", replaceChildren() {this.innerHTML = "";}, onclick: null});
      return nodes.get(selector);
    }
    return {root: {hidden: false, querySelector: element}, element};
  }
  const taskRows = [{id: "tsk-one", name: "<Danger>", revision: "r001",
    parent_id: null, position: 0, properties: {phase: "SWE"}}];
  const localTasks = {tasks: {request: async () => ({results: taskRows})}};
  const d = taskSurface(), s = taskSurface();
  const esc = win.AICompassModels.escapeHtml;
  win.AICompassServerTasks.mount(d.root, () => "", esc, localTasks).setAccess(true, false);
  sandbox.fetch = async () => ({ok: true, status: 200, json: async () => ({results: taskRows})});
  win.AICompassServerTasks.mount(s.root, () => "", esc, null).setAccess(true, false);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(d.element("#server-task-list").innerHTML, s.element("#server-task-list").innerHTML,
    "Same taxonomy tree/controller must work through local and Server providers");
  assert(d.element("#server-task-list").innerHTML.includes("&lt;Danger&gt;"));
  console.log("FUT-03 provider isolation, persona navigation, transports, Catalog and Task parity: PASS");
})().catch(error => {console.error(error); process.exitCode = 1;});
