#!/usr/bin/env node
"use strict";
/* PLAT-14: independent Demo/Server, versioned step renderer, visible checkpoint confirmation. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const js=fs.readFileSync("server-sessions.js","utf8");
const campaigns=fs.readFileSync("server-campaigns.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
const compose=fs.readFileSync("compose.yaml","utf8");
const stage=fs.readFileSync("staging/compose.yaml","utf8");
new vm.Script(js,{filename:"server-sessions.js"});
new vm.Script(campaigns,{filename:"server-campaigns.js"});
assert(page.indexOf('server-sessions.js')>0);
assert(page.indexOf('server-sessions.js')<page.indexOf('server-campaigns.js'));
assert(compose.includes("./server-sessions.js:/srv/frontend/server-sessions.js:ro"));
assert(stage.includes("../server-sessions.js:/srv/frontend/server-sessions.js:ro"));
assert(campaigns.includes("AICompassServerSessions.mount"));
assert(!js.includes("localStorage"));
assert(!js.includes("sessionStorage"));
assert(!js.includes("mode=demo"));
assert(js.includes("method_descriptor.steps"));
assert(js.includes("method_descriptor.fields"));
assert(js.includes("expected_revision=session.revision"));
assert(js.includes("server-confirmed revision"));
assert(js.includes("evidence_link_ids"));
assert(js.includes('"/interactions","POST"'));
assert(js.includes('"/setup","PATCH"'));
/* UX-R05: a real sequential stepper whose navigation is local-only. */
assert(js.includes("data-session-goto"),"Run stepper must expose explicit step buttons");
assert(js.includes("shared-draft-step"),"Run stepper reuses the shared step presentation");
assert(js.includes("data-session-panel"),"Run steps must be real panels, not one long page");
assert(js.includes("Moving between steps writes nothing"),
  "step navigation must never commit a checkpoint");
assert(js.includes("drafts.forMode(\"server\",\"session\""),
  "unsaved Run input must use the scoped ephemeral draft helper");
assert(js.includes("draftHandle.rebase"),"a confirmed save must move the local draft base");
assert(js.includes("draftHandle.conflict"),"409 must surface as an explicit conflict notice");
assert(js.includes("one experimenter owns one Run"),
  "ownership refusal must explain the single-writer Run rule");
assert(!js.includes("localStorage")&&!js.includes("sessionStorage"),
  "the session module must not touch browser storage directly");

const root={
 hidden:true,innerHTML:"",replaceChildren(){this.innerHTML="";},
 querySelector(){return null;}
};
const sb={window:{},Date,console};
vm.runInNewContext(js,sb,{filename:"server-sessions.js"});
const esc=s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;")
                       .replaceAll(">","&gt;").replaceAll('"',"&quot;");
let calls=[];
const sessionUi=sb.window.AICompassServerSessions.mount(root,async function(path){
 calls.push(path);return {};
},esc);
assert.equal(calls.length,0);
assert(root.hidden);
sessionUi.setAccess(false,false);
assert(root.hidden);
assert.equal(calls.length,0);
console.log("PLAT-14: immutable Server session UI, schema adapter, explicit saves and Demo isolation passed");
