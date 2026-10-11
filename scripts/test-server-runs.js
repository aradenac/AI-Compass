#!/usr/bin/env node
"use strict";
/* PLAT-15: Server-only Run UI and permanent measured solution semantics. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const sessions=fs.readFileSync("server-sessions.js","utf8");
const campaigns=fs.readFileSync("server-campaigns.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
new vm.Script(sessions,{filename:"server-sessions.js"});
new vm.Script(campaigns,{filename:"server-campaigns.js"});
assert(page.indexOf('server-sessions.js')>0);
assert(page.indexOf('server-sessions.js')<page.indexOf('server-campaigns.js'));
assert(!sessions.includes("localStorage"));
assert(!sessions.includes("sessionStorage"));
assert(!sessions.includes("mode=demo"));
for(const text of [
  'api("catalog/"+k)',
  'payload.component_ids',
  's.individual_setup',
  'session-new-settings',
  'data-new-component',
  '"sessions/"+encodeURIComponent(s.id)+"/close","POST"',
  'payload.expected_revision=session.revision',
  'api("runs/"+encodeURIComponent(run.id))',
  'api("runs?campaign_id="+encodeURIComponent(row.id))',
  'produced_outputs',
  'cost_mode',
  'tokens_count',
  'information_utility_score',
  'quality_score',
  'evidence_link_ids',
  'JSON.stringify(original,null,2)',
  'state.status!=="closed"',
]){
  assert(sessions.includes(text),"Missing individual Run UI contract: "+text);
}
assert(campaigns.includes("AICompassServerSessions.mount"));
assert(!campaigns.includes("localStorage"));
const sandbox={window:{},Date,console};
vm.runInNewContext(sessions,sandbox,{filename:"server-sessions.js"});
const root={hidden:true,innerHTML:"",replaceChildren(){this.innerHTML="";},
            querySelector(){return null;}};
let calls=[];
const sessionUi=sandbox.window.AICompassServerSessions.mount(root,async path=>{
  calls.push(path);return {};
},v=>String(v).replaceAll("<","&lt;"));
assert(root.hidden);
assert.equal(calls.length,0,"Signed-out Server uses no backend and no Demo fallback");
sessionUi.setAccess(false,false);
assert(root.hidden);
assert.equal(calls.length,0);
console.log("PLAT-15: Server Run close/result UI, source-trio inputs, original Run reading and Demo independence pass");
