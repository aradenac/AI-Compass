#!/usr/bin/env node
"use strict";
/* PLAT-23 shared frontend: Server-only real API and no Demo data import. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const src=fs.readFileSync("server-discussions.js","utf8");
const server=fs.readFileSync("server-mode.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
new vm.Script(src,{filename:"server-discussions.js"});
new vm.Script(server,{filename:"server-mode.js"});
assert(page.includes('<script src="server-discussions.js"></script>'));
assert(page.indexOf("server-discussions.js")<page.indexOf("server-mode.js"));
assert(server.includes("AICompassServerDiscussions.mount"));
assert(server.includes("discussions.setAccess(false, false, false)"));
assert(server.includes('grants.includes("business_read")'));
assert(fs.readFileSync("compose.yaml","utf8").includes(
    "./server-discussions.js:/srv/frontend/server-discussions.js:ro"));
assert(fs.readFileSync("staging/compose.yaml","utf8").includes(
    "../server-discussions.js:/srv/frontend/server-discussions.js:ro"));
assert(!src.includes("localStorage")&&!src.includes("sessionStorage"));
for(const needed of ["Feedback & Discussions","chronological",
  "POST","public","internal","X-CSRFToken","attachments","FormData",
  "expected_revision","edit_reason","parent_id","/revisions",
  "Server discussion","discussion-new-form","discussion-reply-form",
  "discussion-correction-form"]){
    assert(src.includes(needed),"Missing frontend Discussion control: "+needed);
}
const nodes=new Map();
function $(key){
  if(!nodes.has(key))nodes.set(key,{
    hidden:true,value:"",innerHTML:"",textContent:"",listeners:{},
    addEventListener(type,handler){this.listeners[type]=handler;},
    querySelector:$,querySelectorAll(){return [];}
  });
  return nodes.get(key);
}
const root={hidden:true,innerHTML:"",querySelector:$,
  replaceChildren(){this.innerHTML="";}};
const requests=[];
const sandbox={window:{},fetch:async(url,options)=>{
  requests.push(url);
  assert(url.startsWith("/api/v1/"));
  assert.equal(options.credentials,"same-origin");
  assert.equal(options.cache,"no-store");
  return {ok:true,json:async()=>url.includes("auth/me")?
    {authenticated:true,username:"engineer"}:{results:[]}};
}};
vm.runInNewContext(fs.readFileSync("shared-workgroup.js","utf8"),sandbox,{filename:"shared-workgroup.js"});
vm.runInNewContext(src,sandbox,{filename:"server-discussions.js"});
const ui=sandbox.window.AICompassServerDiscussions.mount(root,()=>"csrf",String);
ui.setAccess(false,false,false);
assert(root.hidden);assert.equal(requests.length,0);
ui.setAccess(true,false,false);
setImmediate(()=>{
  assert(!root.hidden);
  assert.equal(requests.length,2);
  assert(requests.includes("/api/v1/auth/me"),
    "the shared feedback view must read the real /api/v1/auth/me identity endpoint");
  assert(!src.includes("Demo fallback")||src.includes("no Demo fallback"));
  assert($("#discussion-threads").innerHTML.includes("No real Server feedback"));
  assert(root.innerHTML.includes("Feedback & Discussions"));
  ui.setAccess(false,false,false);
  assert(root.hidden);
  console.log("PLAT-23 shared Server feedback: no seeded data, two real account API requests, perms & Demo isolation pass");
});
