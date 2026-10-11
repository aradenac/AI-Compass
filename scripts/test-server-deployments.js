#!/usr/bin/env node
"use strict";
/* FUT-15: no secret/client-side entitlement authority and no Demo data crossover. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const src=fs.readFileSync("server-deployments.js","utf8");
const planning=fs.readFileSync("server-planning.js","utf8");
const html=fs.readFileSync("prototype.html","utf8");
assert(html.includes('<script src="server-deployments.js"></script>'));
assert(html.indexOf("server-deployments.js")<html.indexOf("server-planning.js"));
assert(planning.includes("AICompassServerDeployments.mount"));
assert(!src.includes("localStorage")&&!src.includes("sessionStorage"));
assert(src.includes("credentials:\"same-origin\""));
assert(src.includes("\"X-CSRFToken\":csrf()"));
const nodes=new Map();
function node(key){
  if(!nodes.has(key))nodes.set(key,{innerHTML:"",textContent:"",className:"",
    hidden:true,disabled:false,addEventListener(){},replaceChildren(){
      this.innerHTML="";
    },querySelector(){return null;}});
  return nodes.get(key);
}
const container={hidden:true,innerHTML:"",querySelector:node};
const urls=[];
const sandbox={window:{},fetch:async function(url,opts){
  urls.push(url);
  assert(url.startsWith("/api/v1/planning/"));
  assert.equal(opts.credentials,"same-origin");
  if(url.endsWith("/deployments"))return {ok:true,json:async()=>({results:[]})};
  if(url.endsWith("/profiles"))return {ok:true,json:async()=>({results:[]})};
  if(url.endsWith("/opportunities/candidates"))return {ok:true,json:async()=>({results:[]})};
  throw new Error("Unexpected API "+url);
}};
vm.runInNewContext(src,sandbox,{filename:"server-deployments.js"});
const ui=sandbox.window.AICompassServerDeployments.mount(container,()=>"dummy",s=>
  String(s).replaceAll("<","&lt;").replaceAll(">","&gt;"));
assert.equal(urls.length,0,"Mount alone must not fetch private planning data");
ui.setAccess(false,false);
assert(container.hidden);
assert.equal(urls.length,0,"No private fetch without planning capability");
ui.setAccess(true,false);
setImmediate(function(){
  assert.equal(urls.length,3,"Authorized view requires all three real Server sources");
  assert(!container.hidden);
  assert(node("#deployment-new").hidden,"Read-only view cannot create external targets");
  ui.setAccess(false,false);
  assert(container.hidden);
  assert.equal(node("#deployment-targets").innerHTML,"");
  console.log("FUT-15 Server deployment access gate, no Demo crossover and CSRF smoke passed");
});
