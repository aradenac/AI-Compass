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
// Transition wording is canonical in the shared labels, not duplicated here.
const sharedLabels=fs.readFileSync("shared-workgroup.js","utf8");
for(const label of ["Submit for review","Review and publish","Withdraw publication",
  "New draft revision","Original history / evidence"])
  assert(sharedLabels.includes(label),"Missing canonical transition label "+label);
for(const required of ["Knowledge & Collaboration","review_needed",
  "contradictory_run_ids","real persisted","evidence","publish","unpublish",
  "expected_revision","evaluation_revision","run_ids",
  'credentials:"same-origin"',"X-CSRFToken","/revisions",
  "lifecycle.revise","LIFECYCLE_ACTION_LABELS.recommendations","no Demo data imported"]){
  assert(script.includes(required),"Missing recommendation workflow "+required);
}
assert(script.includes("renderDomainDetail"),"Server recommendation detail must use the shared detail primitive");
assert(page.includes("AICompassWorkgroup.renderDomainDetail(projection"),"Demo recommendation detail must use the shared detail primitive");
assert(page.includes("function recommendationDetail("),"Demo recommendation detail entry point missing");
assert(page.includes(String.raw`"data-act":"recommendationDetail"`),"Demo recommendation detail action missing");
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
// The detail projection is pure and shared: exact revision, decision and Run provenance.
const detailProjection=ui.recommendationDetailProjection(
  {name:"Driver decision",revision:"r002",state:"in_review",task_id:"task-1",solution_id:"sol-1",
   run_refs:[{id:"run-1"}]},
  [{revision:"r001",state:"draft",created_by:"alice",reviewed_by:"",
    properties:{decision:"recommended",rationale:"Measured <ok>",limitations:"none"},
    run_refs:[{id:"run-1"}]}],
  reference=>"/?mode=server&workspace=workgroup&section=results&record="+reference.id);
assert.equal(detailProjection.sections.length,1);
assert(detailProjection.sections[0].label.includes("r001"));
assert(detailProjection.sections[0].value.includes("Measured <ok>"));
const sharedDetail=sandbox.window.AICompassWorkgroup.renderDomainDetail(detailProjection,
  {mode:"server",domain:"recommendations"});
assert(sharedDetail.includes('data-shared-domain-detail="recommendations"'));
assert(sharedDetail.includes("Measured &lt;ok&gt;")&&!sharedDetail.includes("Measured <ok>"));
assert(sharedDetail.includes('href="/?mode=server'));
// Reader projections can expose an unavailable Run pin with no id: fail closed,
// never fabricate a Run link and never render "undefined".
const unavailable=ui.recommendationDetailProjection(
  {name:"Public decision",revision:"r003",state:"published",
   run_refs:[{kind:"individual",status:"unavailable"}]},
  [{revision:"r003",state:"published",created_by:"alice",reviewed_by:"bob",
    properties:{decision:"recommended",rationale:"Kept after review"},
    run_refs:[{kind:"individual",status:"unavailable"}]}],
  reference=>"/?record="+reference.id);
assert.equal(unavailable.links.length,0,"Unavailable Run pins must not fabricate links");
assert(unavailable.sections[0].value.includes("unavailable in this projection"));
const unavailableDetail=sandbox.window.AICompassWorkgroup.renderDomainDetail(unavailable,
  {mode:"server",domain:"recommendations"});
assert(!unavailableDetail.includes("undefined"),"Unavailable Run pins must not render undefined ids");
assert(!unavailableDetail.includes('href="/?record='),"Unavailable Run pins must not link");
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
