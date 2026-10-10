#!/usr/bin/env node
"use strict";
/* FUT-06: same OS classification/profiles in independent Demo and Server,
 * no guessing from the browser OS and no cross-mode fallback. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const sandbox={window:{},Date,Promise};
vm.runInNewContext(fs.readFileSync("shared-environment.js","utf8"),sandbox,
  {filename:"shared-environment.js"});
const E=sandbox.window.AICompassEnvironment;
const os=(id,type,supported_os)=>({id,type,name:id,revision:"r001",
  revision_id:id+"-revision",properties:supported_os?{supported_os}:{}});
const win=os("h-win","harness",["windows"]);
const linux=os("h-linux","harness",["linux"]);
const both=os("h-both","harness",["windows","linux"]);
const framework=os("f-linux","framework",["linux"]);
const unknown=os("f-legacy","framework");
assert.equal(E.normalize(["windows","linux"]).join(","),"windows,linux");
assert.equal(E.normalize(["linux","linux"]),null);
assert.equal(E.normalize([]),null);
assert.equal(E.record(unknown).status,"unknown");
assert.equal(E.compose([both],["windows"]).status,"compatible");
assert.equal(E.compose([win],["linux"]).status,"other_os");
assert.equal(E.compose([linux],["windows"]).requires_os.join(","),"linux");
assert.equal(E.compose([both],null).status,"unconfigured_user");
assert.equal(E.compose([win,framework],["windows"]).status,"unsupported_combination");
assert.equal(E.compose([both,framework],["linux"]).status,"compatible");
assert.equal(E.compose([both,framework],["windows"]).status,"other_os");
assert.equal(E.compose([unknown,both],["windows"]).status,"unknown");
assert.equal(E.compose([both,win,framework],["windows","linux"]).status,
 "unsupported_combination");
assert.equal(E.compose([both,framework],["windows"],"distributed_unknown").status,"unknown_topology");

const db={components:[win,linux,both,framework,unknown]};
let user="u1",saves=0;
const demo=E.demoProvider(db,()=>user,()=>{saves++;});
(async()=>{
  assert.equal((await demo.profile()).available_os,null);
  let first=await demo.save(null,["windows"]);
  assert.equal(first.revision,"r001");
  assert.equal(first.available_os.join(","),"windows");
  assert.equal(saves,1);
  let stale;
  try{await demo.save(null,["linux"])}catch(e){stale=e;}
  assert.equal(stale.status,409);
  assert.equal((await demo.save("r001",["windows","linux"])).revision,"r002");
  assert.equal((await demo.profile()).available_os.join(","),"windows,linux");
  user="u2";
  assert.equal((await demo.profile()).configured,false);
  assert.equal((await demo.save(null,["linux"])).revision,"r001");
  user="u1";
  assert.equal((await demo.profile()).revision,"r002");
  assert.equal((await demo.sources()).length,5);
  assert.equal((await demo.evaluate([both,framework],["windows"])).status,"other_os");
  // Server contract always calls only versioned real endpoints; never local data.
  const calls=[];
  sandbox.window.AICompassRuntime={ServerTransport:()=>({request:async(path,method,body)=>{
    calls.push({path,method,body});
    if(path==="/api/v1/profile/environment")return {configured:false,available_os:null,revision:null};
    if(path.startsWith("/api/v1/catalog/"))return {results:[]};
    return {status:"unknown",sources:[]};
  }})};
  const server=E.serverProvider(()=>{},()=> "csrf");
  await server.profile();
  await server.save(null,["windows"]);
  await server.sources();
  await server.evaluate([both,framework]);
  assert.equal(calls[0].path,"/api/v1/profile/environment");
  assert.equal(calls[1].method,"PATCH");
  assert.equal(calls[1].body.expected_revision,null);
  assert.equal(calls[4].path,"/api/v1/environment/compatibility");
  assert.equal(calls[4].body.components[0].revision_id,both.revision_id);
  assert(!fs.readFileSync("server-mode.js","utf8").includes("localStorage"));
  const page=fs.readFileSync("prototype.html","utf8");
  assert(page.includes('<script src="shared-environment.js"></script>'));
  const inline=page.match(/<script>\s*("use strict";[\s\S]*?)<\/script>/);
  assert(inline);new vm.Script(inline[1],{filename:"demo-inline.js"});
  new vm.Script(fs.readFileSync("server-mode.js","utf8"));
  new vm.Script(fs.readFileSync("shared-catalog.js","utf8"));
  assert(page.includes("demoEnvironment=window.AICompassEnvironment.demoProvider"));
  assert(fs.readFileSync("shared-catalog.js","utf8").includes("data-os-fields"));
  console.log("FUT-06 OS profile isolation, Windows/Linux/Both/unknown, intersection, exact Server refs: PASS");
})().catch(e=>{console.error(e);process.exitCode=1;});
