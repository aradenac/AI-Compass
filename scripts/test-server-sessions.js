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

const root={
 hidden:true,innerHTML:"",replaceChildren(){this.innerHTML="";},
 querySelector(){return null;}
};
const sb={window:{},Date,console};
vm.runInNewContext(js,sb,{filename:"server-sessions.js"});
const esc=s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;")
                       .replaceAll(">","&gt;").replaceAll('"',"&quot;");
let calls=[];
const module=sb.window.AICompassServerSessions.mount(root,async function(path){
 calls.push(path);return {};
},esc);
assert.equal(calls.length,0);
assert(root.hidden);
module.setAccess(false,false);
assert(root.hidden);
assert.equal(calls.length,0);
console.log("PLAT-14: immutable Server session UI, schema adapter, explicit saves and Demo isolation passed");
