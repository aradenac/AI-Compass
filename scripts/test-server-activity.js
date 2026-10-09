#!/usr/bin/env node
"use strict";
/* No Demo data or Server request without an actual role grant. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const script = fs.readFileSync("server-activity.js", "utf8");
const page = fs.readFileSync("prototype.html", "utf8");
const mode = fs.readFileSync("server-mode.js", "utf8");
assert(page.includes('<script src="server-activity.js"></script>'));
assert(mode.includes("AICompassServerActivity.mount"));
assert(mode.includes('activity.setAccess(grants.includes("business_read"), grants.includes("users_manage"))'));
assert(!script.includes("localStorage"), "Server feed must never read Demo state");

const nodes = new Map();
function node(selector) {
  if (!nodes.has(selector)) nodes.set(selector, {
    hidden:false, textContent:"", innerHTML:"", disabled:false, href:"",
    elements: {from:{value:""},to:{value:""}},
    addEventListener() {},
  });
  return nodes.get(selector);
}
const root = {
  hidden:true, innerHTML:"",
  querySelector:node,
  replaceChildren() { this.innerHTML = ""; },
};
let calls = 0;
const sandbox = {
  window:{}, URLSearchParams,
  fetch:async (url, opts) => {
    calls++;
    assert(url.startsWith("/api/v1/activity?"));
    assert.equal(opts.credentials, "same-origin");
    return {ok:true,json:async () => ({results:[{
      id:"ff47ac19-79e9-4788-ac0e-5743c744420a",
      operation:"created",object_type:"model",object_name:"<unsafe>",
      actor:"engineer",occurred_at:"2026-10-09T22:00:00Z",revision:"r001",
    }],has_more:false,limited:false})};
  },
};
vm.runInNewContext(script,sandbox,{filename:"server-activity.js"});
const ui=sandbox.window.AICompassServerActivity.mount(root,s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;"));
assert.equal(calls,0);
ui.setAccess(false,false);
assert.equal(calls,0);
assert.equal(root.hidden,true);
ui.setAccess(true,false);
assert.equal(root.hidden,false);
setImmediate(() => {
  assert.equal(calls,1);
  assert(node("#activity-list").innerHTML.includes("&lt;unsafe&gt;"),"HTML escaped");
  assert(!node("#activity-list").innerHTML.includes("<unsafe>"),"No HTML injection");
  assert(node("#activity-export-csv").href.includes("format=csv"));
  ui.setAccess(false,false);
  assert.equal(root.hidden,true);
  assert.equal(root.innerHTML,"");
  console.log("PLAT-24 Server Activity Feed isolation and export-links smoke passed");
});
