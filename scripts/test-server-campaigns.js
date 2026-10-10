#!/usr/bin/env node
"use strict";
/* PLAT-12: syntactic and authorization/isolation smoke for shared Server UI. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const source=fs.readFileSync("server-campaigns.js","utf8");
const mode=fs.readFileSync("server-mode.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
new vm.Script(source,{filename:"server-campaigns.js"});
new vm.Script(mode,{filename:"server-mode.js"});
assert(page.includes('<script src="server-campaigns.js"></script>'));
assert(page.indexOf('server-campaigns.js')<page.indexOf('server-mode.js'));
assert(mode.includes("AICompassServerCampaigns.mount"));
assert(mode.includes('grants.includes("publication_review")'));
assert(!source.includes("localStorage"));
assert(!source.includes("sessionStorage"));
assert(!source.includes("mode=demo"));
const nodes=new Map();
function node(key){
  if(!nodes.has(key))nodes.set(key,{innerHTML:"",textContent:"",className:"",hidden:false,
    addEventListener(){},replaceChildren(){this.innerHTML="";this.textContent="";},
    querySelector(){return node(key+":child")},querySelectorAll(){return []}});
  return nodes.get(key);
}
const root={hidden:true,innerHTML:"",querySelector:node,replaceChildren(){this.innerHTML="";}};
const rows={campaigns:{results:[{id:"cmp-calm-blue-tree",name:"<unsafe campaign>",
  revision:"r001",status:"planned",archived:false,owner:"contributor",
  mode:"task_centred",test_case_ids:["tcs-calm-blue-tree"],
  properties:{objective:"<unsafe objective>"}}]},
  "campaign-methods":{results:[]},tasks:{results:[]},
  "test-cases":{results:[]},guides:{results:[]},
  "catalog/model":{results:[]},"catalog/provider":{results:[]},"catalog/harness":{results:[]},
  "catalog/framework":{results:[]}};
let calls=[];
const sandbox={window:{},console,URLSearchParams,fetch:async(url,opts)=>{
  assert(url.startsWith("/api/v1/"));
  assert.equal(opts.credentials,"same-origin");
  calls.push(url);
  const key=url.slice("/api/v1/".length);
  if(!rows[key])throw Error("Unknown "+url);
  return {ok:true,json:async()=>rows[key]};
}};
vm.runInNewContext(source,sandbox,{filename:"server-campaigns.js"});
const escape=s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
const ui=sandbox.window.AICompassServerCampaigns.mount(root,()=> "csrf",escape);
assert.equal(calls.length,0,"signed-out Server must make zero API requests");
ui.setAccess(false,false,false);
assert(root.hidden);
assert.equal(calls.length,0);
ui.setAccess(true,false,false);
setImmediate(()=>{
  assert.equal(calls.length,9,"read-only user loads Server endpoints only");
  assert(!root.hidden);
  assert(node("#campaign-list").innerHTML.includes("&lt;unsafe campaign&gt;"));
  assert(!node("#campaign-list").innerHTML.includes("<unsafe campaign>"));
  assert(!node("#campaign-list").innerHTML.includes("Archive</button>"));
  assert(!node("#campaign-list").innerHTML.includes("Edit</button>"));
  ui.setAccess(false,false,false);
  assert(root.hidden);
  assert.equal(root.innerHTML,"");
  console.log("PLAT-12: Server campaign mounting, no Demo fallback, escaping and read-scoped controls passed");
});
