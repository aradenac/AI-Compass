#!/usr/bin/env node
"use strict";
/* PLAT-11: no Demo fallback; only authenticated Server guide lookups. */
const assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const source=fs.readFileSync("server-guides.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-mode.js","utf8");
assert(page.includes('<script src="server-guides.js"></script>'));
assert(server.includes('AICompassServerGuides.mount'));
assert(server.includes('guides.setAccess(!maintenanceWorkspace && grants.includes("business_read"), !maintenanceWorkspace && grants.includes("business_write"))'));
assert(!source.includes("localStorage"));
const elements=new Map();
function node(key) {
  if(!elements.has(key))elements.set(key,{
    innerHTML:"",textContent:"",hidden:true,value:"",disabled:false,
    listeners:{},addEventListener(type,fn){this.listeners[type]=fn;},
    querySelector:node,querySelectorAll(){return [];},replaceChildren(){this.innerHTML="";}
  });
  return elements.get(key);
}
const root={hidden:true,innerHTML:"",querySelector:node,replaceChildren(){this.innerHTML="";}};
let calls=[];
const id="gui-calm-blue-otter";
const fixture={id,name:"<script>unsafe</script>",type:"setup_guide",revision:"r001",
  revision_id:"7e000000-0000-7000-8000-000000000001",
  properties:{url:"https://example.org/docs"}};
const sandbox={window:{},fetch:async(url,opts)=>{
  calls.push({url,method:opts.method});
  assert(url.startsWith("/api/v1/guides"));
  assert.equal(opts.credentials,"same-origin");
  assert.equal(opts.cache,"no-store");
  return {ok:true,json:async()=>({results:[fixture]})};
}};
vm.runInNewContext(source,sandbox,{filename:"server-guides.js"});
const escape=s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;")
  .replaceAll(">","&gt;").replaceAll('"',"&quot;");
const ui=sandbox.window.AICompassServerGuides.mount(root,()=>"csrf",escape);
assert.equal(calls.length,0);
ui.setAccess(false,false);
assert(root.hidden);assert.equal(calls.length,0);
ui.setAccess(true,false);
setImmediate(()=>{
  assert(!root.hidden);
  assert(calls.length>=2);
  assert(!root.innerHTML.includes("+ Create reusable guide"));
  assert(node("#guide-list").innerHTML.includes("&lt;script&gt;unsafe&lt;/script&gt;"));
  assert(!node("#guide-list").innerHTML.includes("<script>"));
  ui.setAccess(false,false);
  assert(root.hidden);assert.equal(root.innerHTML,"");
  let selection=null;
  const picker={hidden:false,innerHTML:"",querySelector:node,replaceChildren(){this.innerHTML="";}};
  const inline=sandbox.window.AICompassServerGuides.mountInline(
    picker,()=>"csrf",escape,value=>{selection=value;},{canWrite:false,heading:"Pick guide"}
  );
  setImmediate(()=>{
    const select=node(".guide-inline-select");
    select.value=id;
    select.listeners.change.call(select);
    assert(selection);
    assert.equal(selection.id,id);
    assert.equal(selection.revision_id,fixture.revision_id);
    inline.setAccess(false,false);
    assert(picker.hidden);
    console.log("PLAT-11 Server guide isolation, lookups, escaping and revision pin passed");
  });
});
