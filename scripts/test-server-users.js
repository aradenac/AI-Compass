#!/usr/bin/env node
"use strict";
/* PLAT-28 smoke: Server-only component and a denied-role bootstrap are inert. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("server-users.js", "utf8");
const html = fs.readFileSync("prototype.html", "utf8");
const mode = fs.readFileSync("server-mode.js", "utf8");
assert(html.includes('<script src="server-users.js"></script>'));
assert(mode.includes("AICompassServerUsers.mount"));
assert(mode.includes('grants.includes("users_manage")'));
assert(!source.includes("localStorage"), "Never read local Demo records");
const elements = new Map();
function node(name) {
  if (!elements.has(name)) {
    elements.set(name, {
      textContent: "", className: "", innerHTML: "", hidden: true,
      addEventListener() {}, replaceChildren() {}, scrollIntoView() {},
    });
  }
  return elements.get(name);
}
const root = {
  hidden:true, innerHTML:"", replaceChildren() { this.innerHTML = ""; },
  querySelector: node,
};
let fetches = 0;
const sandbox = {window: {}, fetch: async (url, options) => {
  fetches++;
  assert(url.startsWith("/api/v1/admin/users"));
  assert.equal(options.credentials, "same-origin");
  return {ok:true,json:async () => ({results:[],total:0,page_size:50,available_roles:["user"]})};
}};
vm.runInNewContext(source, sandbox, {filename:"server-users.js"});
const ui = sandbox.window.AICompassServerUsers.mount(root, () => "csrf", String);
assert.equal(fetches, 0, "No unauthorized or Demo request");
ui.setAccess(false, false);
assert(root.hidden);
assert.equal(fetches, 0, "No request without users_manage");
ui.setAccess(true, false);
assert(!root.hidden);
assert(root.innerHTML.includes("Users & Access"));
setImmediate(() => {
  assert.equal(fetches, 1, "Authorized account list loads once");
  ui.setAccess(false, false);
  assert(root.hidden);
  assert.equal(root.innerHTML, "", "Account content is cleared on sign-out");
  console.log("PLAT-28 user administration client isolation passed");
});
