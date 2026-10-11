#!/usr/bin/env node
"use strict";
/* PLAT-22: Server Recommendations are real API-only; Demo never synchronized. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const script=fs.readFileSync("server-recommendations.js","utf8");
const server=fs.readFileSync("server-mode.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
new vm.Script(script,{filename:"server-recommendations.js"});
new vm.Script(server,{filename:"server-mode.js"});
assert(page.includes('<script src="server-recommendations.js"></script>'));
assert(page.indexOf("server-recommendations.js")<page.indexOf("server-mode.js"));
assert(server.includes("AICompassServerRecommendations.mount"));
assert(server.includes("recommendations.setAccess(false, false, false)"));
assert(server.includes('grants.includes("publication_review")'));
assert(fs.readFileSync("compose.yaml","utf8").includes(
  "./server-recommendations.js:/srv/frontend/server-recommendations.js:ro"));
assert(fs.readFileSync("staging/compose.yaml","utf8").includes(
  "../server-recommendations.js:/srv/frontend/server-recommendations.js:ro"));
assert(!script.includes("localStorage")&&!script.includes("sessionStorage"));
for(const required of ["Knowledge & Collaboration","review_needed",
  "contradictory_run_ids","real persisted","evidence","publish","unpublish",
  "expected_revision","evaluation_revision","run_ids",
  'credentials:"same-origin"',"X-CSRFToken","/revisions",
  "New draft revision","no Demo data imported"]){
  assert(script.includes(required),"Missing recommendation workflow "+required);
}
const nodes=new Map();
function find(key){
  if(!nodes.has(key))nodes.set(key,{
    innerHTML:"",textContent:"",value:"",hidden:false,listeners:{},
    addEventListener(type,fn){this.listeners[type]=fn;},
    querySelector:find,querySelectorAll(){return [];},
  });
  return nodes.get(key);
}
const root={hidden:true,innerHTML:"",querySelector:find,
  replaceChildren(){this.innerHTML="";}};
const urls=[];
const sandbox={window:{},fetch:async(url,options)=>{
  urls.push(url);
  assert(url.startsWith("/api/v1/"));
  assert.equal(options.credentials,"same-origin");
  assert.equal(options.cache,"no-store");
  return {ok:true,json:async()=>({results:[]})};
}};
vm.runInNewContext(fs.readFileSync("shared-workgroup.js","utf8"),sandbox,{filename:"shared-workgroup.js"});
vm.runInNewContext(script,sandbox,{filename:"server-recommendations.js"});
const ui=sandbox.window.AICompassServerRecommendations.mount(root,()=>"csrf",String);
ui.setAccess(false,false,false);
assert(root.hidden);assert.equal(urls.length,0);
ui.setAccess(true,false,false);
setImmediate(()=>{
  assert(!root.hidden);
  assert.equal(urls.length,5);
  assert(!root.innerHTML.includes("+ Draft recommendation"));
  assert(find("#rec-list").innerHTML.includes("No permitted recommendations"));
  ui.setAccess(false,false,false);assert(root.hidden);
  console.log("PLAT-22: real Server Recommendations, role hiding and offline Demo isolation pass");
});
