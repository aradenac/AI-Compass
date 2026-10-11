#!/usr/bin/env node
"use strict";
/* PLAT-21 Server mode Results Explorer uses real endpoint data, no Demo storage. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const source=fs.readFileSync("server-results.js","utf8");
const server=fs.readFileSync("server-mode.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
new vm.Script(source,{filename:"server-results.js"});
new vm.Script(server,{filename:"server-mode.js"});
assert(page.includes('<script src="server-results.js"></script>'));
assert(page.indexOf('server-results.js')<page.indexOf('server-mode.js'));
assert(server.includes("AICompassServerResults.mount"));
assert(server.includes("resultsExplorer.setAccess(false, false)"));
assert(server.includes('grants.includes("business_read")'));
assert(fs.readFileSync("compose.yaml","utf8").includes(
    "./server-results.js:/srv/frontend/server-results.js:ro"));
assert(fs.readFileSync("staging/compose.yaml","utf8").includes(
    "../server-results.js:/srv/frontend/server-results.js:ro"));
assert(!source.includes("localStorage")&&!source.includes("sessionStorage"));
assert(source.includes('writer?"workgroup":"engineer"'),
  "Results deep links must preserve the read-only Engineer role without escalating to Workgroup");
for(const marker of ["results/explorer?",'api("evaluations")',
  "experimental_method_version","No automatic averages",
  "THEORETICAL FORECAST","MEASURED ","Unknown / not measured",
  "evidence_class","comparison_basis","expected_revision",
  "evaluation-form","assessment","cost_eur",'/revisions',"csrf()"]){
    assert(source.includes(marker),"Missing Results UI workflow "+marker);
}
const nodes=new Map();
function find(k){
  if(!nodes.has(k))nodes.set(k,{
    textContent:"",innerHTML:"",value:"",hidden:false,listeners:{},
    addEventListener(type,fn){this.listeners[type]=fn;},
    replaceChildren(){this.innerHTML="";this.textContent="";},
    querySelector:find,querySelectorAll(){return [];},
    style:{},
  });
  return nodes.get(k);
}
const formElements={view:{value:"task"},kind:{value:"all"},
                    task_id:{value:""},solution_id:{value:""},campaign_id:{value:""}};
find("#results-filter").elements=formElements;
const root={hidden:true,innerHTML:"",querySelector:find,replaceChildren(){
  this.innerHTML="";
},};
const calls=[];
const sandbox={window:{location:{pathname:"/",search:"?mode=server&workspace=engineer&section=results",hash:"",origin:"http://localhost"},
 history:{replaceState(){}}},URL,URLSearchParams,fetch:async(url,opts)=>{
  calls.push(url);
  assert(url.startsWith("/api/v1/"));
  assert.equal(opts.credentials,"same-origin");
  assert.equal(opts.cache,"no-store");
  let result={results:[]};
  if(url.includes("results/explorer"))result={
    view:"task",row_axis:"task",column_axis:"candidate",matrix:[],
    results:[],counts:{individual_runs:0,composite_workflows:0,theoretical_forecasts:0},
    scoring_policy:"no invented averages"};
  return {ok:true,json:async()=>result};
}};
vm.runInNewContext(source,sandbox,{filename:"server-results.js"});
const ui=sandbox.window.AICompassServerResults.mount(root,()=>"csrf",String);
ui.setAccess(false,false);
assert(root.hidden);
assert.equal(calls.length,0);
ui.setAccess(true,false);
setImmediate(()=>{
  assert.equal(calls.length,5);
  assert(!root.hidden);
  assert(root.innerHTML.includes("Results Explorer"));
  assert(!root.innerHTML.includes("+ Save evaluation"));
  assert(find("#results-matrix").innerHTML.includes("0 individual"));
  ui.setAccess(false,false);
  assert(root.hidden);
  console.log("PLAT-21 Server Results matrix, role scoped controls and Demo isolation passed");
});
