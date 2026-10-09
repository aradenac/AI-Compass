#!/usr/bin/env node
"use strict";
/* Server Test Design must not query Demo or fetch while signed out. */
const assert=require("node:assert/strict"), fs=require("node:fs"), vm=require("node:vm");
const source=fs.readFileSync("server-test-cases.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
const mode=fs.readFileSync("server-mode.js","utf8");
assert(page.includes('<script src="server-test-cases.js"></script>'));
assert(mode.includes("AICompassServerTestCases.mount"));
assert(mode.includes('testCases.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"))'));
assert(!source.includes("localStorage"));
const elements=new Map();
function node(key) {
  if(!elements.has(key))elements.set(key,{
    hidden:false,innerHTML:"",textContent:"",disabled:false,
    addEventListener(){},querySelector(){return node(key+":child");},
    querySelectorAll(){return [];},
  });
  return elements.get(key);
}
const root={hidden:true,innerHTML:"",querySelector:node,
  replaceChildren(){this.innerHTML="";}};
let requests=[];
const sandbox={window:{},console,URLSearchParams,fetch:async(url,options)=>{
  requests.push(url);
  assert.equal(options.credentials,"same-origin");
  if(url==="/api/v1/test-cases")
    return {ok:true,json:async()=>({results:[{
      id:"tcs-golden-blue-otter",name:"<untrusted>",revision:"r001",
      task_id:"tsk-calm-blue-tree",case_version:"1.0",
      properties:{objective:"Test",dod:"Pass"},
      fork_parent_id:null,revision_id:"mockuuid",task_revision_at_creation:"mock",
    }]})};
  if(url==="/api/v1/tasks")
    return {ok:true,json:async()=>({results:[{
      id:"tsk-calm-blue-tree",name:"Driver task",
    }]})};
  throw Error("unexpected "+url);
}};
vm.runInNewContext(source,sandbox,{filename:"server-test-cases.js"});
const escape=s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
const ui=sandbox.window.AICompassServerTestCases.mount(root,()=> "csrf",escape);
assert.equal(requests.length,0);
ui.setAccess(false,false);
assert.equal(requests.length,0);
assert(root.hidden);
ui.setAccess(true,false);
setImmediate(()=>{
  assert.equal(requests.length,2);
  assert(!root.hidden);
  assert(node("#case-list").innerHTML.includes("&lt;untrusted&gt;"));
  assert(!node("#case-list").innerHTML.includes("<untrusted>"));
  assert(!root.innerHTML.includes("New Test Case"));
  ui.setAccess(false,false);
  assert(root.hidden);
  assert.equal(root.innerHTML,"");
  console.log("PLAT-10: Server Test Design mount, read scope, escaping and Demo separation passed");
});
