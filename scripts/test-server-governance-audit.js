#!/usr/bin/env node
"use strict";
/* FUT-17: no Demo state, read-only maintenance, strict authorization gate. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const src=fs.readFileSync("server-governance-audit.js","utf8");
const runtime=fs.readFileSync("server-mode.js","utf8");
const html=fs.readFileSync("prototype.html","utf8");
const urls=fs.readFileSync("backend/config/urls.py","utf8");
assert(html.includes('<script src="server-governance-audit.js"></script>'));
assert(runtime.includes('id="server-governance-audit"'));
assert(runtime.includes('governanceAudit.setAccess(maintenanceWorkspace && grants.includes("audit_view"))'));
assert(runtime.includes('var governanceAudit = window.AICompassServerAudit.mount('));
assert(src.includes('"/api/v1/maintenance/audit"'));
assert(src.includes('credentials:"same-origin"'));
assert(src.includes('cache:"no-store"'));
assert(!src.includes("localStorage")&&!src.includes('method:"POST"')&&!src.includes('method:"PATCH"'));
assert(urls.includes('path("api/v1/maintenance/audit/export"'));
const win={};vm.runInNewContext(src,{window:win,Error,JSON,Promise});
assert.equal(typeof win.AICompassServerAudit.mount,"function");
console.log("FUT-17 maintenance audit isolation and read-only frontend wiring OK");
