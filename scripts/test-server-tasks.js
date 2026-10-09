#!/usr/bin/env node
"use strict";
/* Server mount does not touch Demo; authenticated Server fetch is explicit. */
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const code = fs.readFileSync("server-tasks.js", "utf8");
const html = fs.readFileSync("prototype.html", "utf8");
const server = fs.readFileSync("server-mode.js", "utf8");
assert(html.includes('<script src="server-tasks.js"></script>'));
assert(server.includes('AICompassServerTasks.mount'));
assert(!code.includes("localStorage"), "Server taxonomy must not read Demo storage");
const events = [];
const nodes = new Map();
function element(id) {
  if (!nodes.has(id)) nodes.set(id, {
    hidden: false, textContent: "", innerHTML: "", replaceChildren() { this.innerHTML = ""; }
  });
  return nodes.get(id);
}
const root = {hidden: false, querySelector: element};
const rows = [{id: "tsk-blue-quiet-fox", name: "<unsafe>", revision: "r001",
  parent_id: null, position: 0, properties: {future: "kept"}}];
const sandbox = {window: {}, Set, console, fetch: async (url, options) => {
  events.push({url, options});
  assert.equal(options.credentials, "same-origin");
  return {ok: true, json: async () => ({results: rows})};
}};
vm.runInNewContext(code, sandbox, {filename: "server-tasks.js"});
const ui = sandbox.window.AICompassServerTasks;
assert(ui && typeof ui.mount === "function");
const escapeHtml = value => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const control = ui.mount(root, () => "csrf", escapeHtml);
assert.equal(events.length, 0, "Demo and signed-out Server should never fetch");
control.setAccess(false, false);
assert.equal(events.length, 0);
control.setAccess(true, false);
new Promise(resolve => setImmediate(resolve)).then(() => {
  assert.equal(events.length, 1);
  assert.equal(events[0].url, "/api/v1/tasks");
  assert(element("#server-task-list").innerHTML.includes("&lt;unsafe&gt;"));
  assert(!element("#server-task-list").innerHTML.includes("<unsafe>"));
  assert(!element("#server-task-list").innerHTML.includes('data-task-action="edit"'));
  control.setAccess(false, false);
  assert.equal(root.hidden, true);
  console.log("PLAT-09 client isolation and read-only task smoke passed");
}).catch(error => { console.error(error); process.exitCode = 1; });
