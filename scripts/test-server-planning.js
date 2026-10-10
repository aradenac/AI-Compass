#!/usr/bin/env node
"use strict";
/* DAP-01: confidential Server planning, no Demo fallback. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const code = fs.readFileSync("server-planning.js", "utf8");
const mode = fs.readFileSync("server-mode.js", "utf8");
const html = fs.readFileSync("prototype.html", "utf8");
assert(html.includes('<script src="server-planning.js"></script>'));
assert(html.indexOf("server-planning.js") < html.indexOf("server-mode.js"));
assert(mode.includes('planning.setAccess(!maintenanceWorkspace && grants.includes("planning_view"), !maintenanceWorkspace && grants.includes("planning_manage"))'));
assert(!code.includes("localStorage"));
const elements = new Map();
function child(key) {
  if (!elements.has(key)) elements.set(key, {
    innerHTML:"",textContent:"",hidden:true,disabled:false,
    addEventListener(){},replaceChildren(){this.innerHTML="";},querySelector(){return null}
  });
  return elements.get(key);
}
const root={hidden:true,innerHTML:"",querySelector:child};
const urls=[];
const records=[{id:"wlp-calm-blue-fox",name:"<script>unsafe</script>",kind:"role",revision:"r001",
  workloads:[],role_id:null,specialty_id:null,headcount:1,hourly_rate_eur:null}];
const taskRows=[{id:"tsk-calm-blue-fox",name:"Driver",parent_id:null}];
const sandbox={window:{},fetch:async(url,options)=>{
  urls.push(url);
  assert(url.startsWith("/api/v1/planning/"));
  assert.equal(options.credentials,"same-origin");
  if(url.endsWith("profiles"))return {ok:true,json:async()=>({results:records})};
  if(url.endsWith("tasks"))return {ok:true,json:async()=>({results:taskRows})};
  return {ok:true,json:async()=>({workloads:[],headcount:1,hourly_rate_source:null,warnings:[]})};
}};
function escape(s){return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");}
vm.runInNewContext(code,sandbox,{filename:"server-planning.js"});
const ui=sandbox.window.AICompassServerPlanning.mount(root,()=>"csrf",escape);
assert.equal(urls.length,0);
ui.setAccess(false,false);
assert(root.hidden);
assert.equal(urls.length,0);
ui.setAccess(true,false);
setImmediate(()=>{
  assert.equal(urls.length,2);
  assert(!root.hidden);
  assert(child("#planning-list").innerHTML.includes("&lt;script&gt;"));
  assert(!child("#planning-list").innerHTML.includes("<script>"));
  assert(child("#planning-new").hidden);
  ui.setAccess(false,false);
  assert(root.hidden);
  assert.equal(child("#planning-list").innerHTML,"");
  console.log("DAP-01 Server planning authorization and XSS smoke passed");
});
