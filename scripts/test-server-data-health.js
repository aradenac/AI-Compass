#!/usr/bin/env node
"use strict";
/* PLAT-27: no Demo imports, no access/requests absent maintenance_view. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync("server-data-health.js","utf8");
const html = fs.readFileSync("prototype.html","utf8");
const mode = fs.readFileSync("server-mode.js","utf8");
assert(html.includes('<script src="server-data-health.js"></script>'));
assert(html.includes('window.location.pathname === "/maintenance"'));
assert(mode.includes('health.setAccess(grants.includes("maintenance_view"), grants.includes("maintenance_triage"))'));
assert(!source.includes("localStorage"));
const elements = new Map();
function node(key) {
  if (!elements.has(key)) elements.set(key,{
    innerHTML:"",textContent:"",hidden:true,disabled:false, addEventListener(){},
  });
  return elements.get(key);
}
const root={hidden:true,innerHTML:"",querySelector:node,
  replaceChildren(){this.innerHTML="";}};
let calls=0;
const sandbox={window:{},fetch:async(url,options)=>{
  calls++;
  assert(url.startsWith("/api/v1/maintenance/"));
  assert.equal(options.credentials,"same-origin");
  if(url.endsWith("health")) return {ok:true,json:async()=>({
      open:1,exceptions:0,resolved:0,total:1})};
  return {ok:true,json:async()=>({page:1,page_size:50,total:1,
    results:[{id:"mnt-calm-blue-lake",severity:"critical",status:"open",
      summary:"<script>unexpected</script>",category:"blob_missing",
      subject_type:"evidence-blob",subject_id:null,detection_count:2}]})};
}};
vm.runInNewContext(source,sandbox,{filename:"server-data-health.js"});
const ui=sandbox.window.AICompassServerDataHealth.mount(root,()=> "csrf",
 s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;"));
assert.equal(calls,0);
ui.setAccess(false,false);
assert(root.hidden);
assert.equal(calls,0);
ui.setAccess(true,false);
setImmediate(()=>{
  assert.equal(calls,2);
  assert(!root.hidden);
  assert(!root.innerHTML.includes("Run checks now"));
  assert(node("#health-list").innerHTML.includes("&lt;script&gt;"));
  assert(!node("#health-list").innerHTML.includes("<script>"));
  ui.setAccess(false,false);
  assert(root.hidden);
  assert.equal(root.innerHTML,"");
  console.log("PLAT-27 isolated maintenance UI and read-only role smoke passed");
});
