#!/usr/bin/env node
"use strict";
/* PLAT-16: shared Server UI has explicit composite lifecycle and no attributed team scores. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const sessions=fs.readFileSync("server-sessions.js","utf8");
const campaigns=fs.readFileSync("server-campaigns.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
new vm.Script(sessions,{filename:"server-sessions.js"});
new vm.Script(campaigns,{filename:"server-campaigns.js"});
for(const required of [
    "isComposite=s.selected_participant_ids.length>=2",
    "editable&&(s.individual_setup||isComposite)",
    "Results / Close ",
    "Framework composite run",
    "Workflow-wide result only",
    "global metrics only",
    "r.kind===\"composite\"",
    "api(\"runs?campaign_id=\"",
    "api(\"runs/\"",
    "session-close-run",
    "expected_revision:s.revision",
    "evidence_link_ids"
]){
    assert(sessions.includes(required),"Missing composite Results/Close UI: "+required);
}
assert(!sessions.includes("localStorage"));
assert(!sessions.includes("sessionStorage"));
assert(!sessions.includes("mode=demo"));
assert(page.indexOf('server-sessions.js')>=0);
assert(page.indexOf('server-sessions.js')<page.indexOf('server-campaigns.js'));
const sandbox={window:{},Date,console};
vm.runInNewContext(sessions,sandbox,{filename:"server-sessions.js"});
const root={hidden:true,innerHTML:"",replaceChildren(){this.innerHTML="";},
    querySelector(){return null;}};
let requests=0;
const ui=sandbox.window.AICompassServerSessions.mount(root,async()=>{requests++;return {};},String);
ui.setAccess(false,false);
assert(root.hidden);
assert.equal(requests,0,"Inactive Server UI must not query or import Demo");
console.log("PLAT-16 Server composite Results, read-only scope labels and Demo isolation passed");
