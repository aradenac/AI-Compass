#!/usr/bin/env node
"use strict";
/* FUT-12: shared provider and safety contracts without any network in Demo. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const source=fs.readFileSync("shared-engineer.js","utf8");
const html=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-mode.js","utf8");
const compose=fs.readFileSync("compose.yaml","utf8");
const stage=fs.readFileSync("staging/compose.yaml","utf8");
new vm.Script(source,{filename:"shared-engineer.js"});
assert(html.includes('<script src="shared-engineer.js"></script>'));
assert(html.indexOf("shared-engineer.js")<html.indexOf("server-mode.js"));
assert(server.includes('server-engineer'));
assert(server.includes("AICompassEngineer.mount"));
assert(server.includes('personaId === "engineer"'));
assert(compose.includes("./shared-engineer.js:/srv/frontend/shared-engineer.js:ro"));
assert(stage.includes("../shared-engineer.js:/srv/frontend/shared-engineer.js:ro"));
assert(!source.includes("localStorage")&&!source.includes("sessionStorage"));
const calls=[];
const window={AICompassRuntime:{ServerTransport:(fetch,csrf)=>({
  request:(path,method,body)=>{calls.push({path,method,body});return Promise.resolve({});
}})}};
vm.runInNewContext(source,{window,URLSearchParams,Set,Map,Date,Object}, {filename:"shared-engineer.js"});
const provider=window.AICompassEngineer.serverProvider(()=>{},()=> "CSRF");
provider.list("task",false);
provider.detail("sol-alpha","tsk-alpha");
provider.feedback("request","sol-alpha","Interested in access");
assert.equal(calls.length,3);
assert.equal(calls[0].path,"/api/v1/engineer/workspace?view=task&all_tasks=false");
assert.equal(calls[1].path,"/api/v1/engineer/solutions/sol-alpha?task_id=tsk-alpha");
assert.equal(calls[2].path,"/api/v1/engineer/feedback");
assert.equal(calls[2].method,"POST");
assert.equal(calls[2].body.kind,"request");
const db={tasks:[{id:"t1",parent:null,name:"Coding",desc:"C"}],
 solutions:[{id:"s1",name:"Agent",accessible:true,description:"No proof beyond sample"}],
 cases:[{id:"c1",task:"t1"}],
 runs:[{id:"r1",case:"c1",solution:"s1",status:"published",accepted:false},
       {id:"r2",case:"c1",solution:"s1",status:"draft",accepted:true}],
 guides:[],feedback:[]};
let saved=0;
/* UX-R06: Windows-only person with a Linux-only measured alternative and an
 * unclassified configuration. Synthetic Demo fixtures only, no scoring. */
const osDb={
  tasks:[{id:"t1",parent:null,name:"Coding",desc:"C"}],
  components:[{id:"h-linux",type:"harness",name:"Linux-only harness",
    properties:{supported_os:["linux"]}},
   {id:"h-both",type:"harness",name:"Cross-platform harness",
    properties:{supported_os:["windows","linux"]}},
   {id:"h-unknown",type:"harness",name:"Unclassified harness",properties:{}}],
  solutions:[
   {id:"s-linux",name:"Linux candidate",accessible:true,publication:"published",
    componentRefs:{harness:"h-linux"}},
   {id:"s-both",name:"Windows candidate",accessible:true,publication:"published",
    componentRefs:{harness:"h-both"}},
   {id:"s-unknown",name:"Unclassified candidate",accessible:true,publication:"published",
    componentRefs:{harness:"h-unknown"}}],
  cases:[{id:"c1",task:"t1"}],
  runs:[{id:"r1",case:"c1",solution:"s-linux",status:"published",accepted:true},
        {id:"r2",case:"c1",solution:"s-both",status:"published",accepted:true},
        {id:"r3",case:"c1",solution:"s-unknown",status:"published",accepted:true}],
  guides:[],feedback:[],environmentHistory:[]};
const osWindow={};
vm.runInNewContext(fs.readFileSync("shared-environment.js","utf8"),
  {window:osWindow,URLSearchParams,Set,Map,Date,Object,Array,Promise,Error});
vm.runInNewContext(source,{window:osWindow,URLSearchParams,Set,Map,Date,Object,Array,
  Promise,Error},{filename:"shared-engineer.js"});
const windowsOnlyActor={id:"u-win",role:"engineer"};
osDb.environmentHistory.push({user:"u-win",number:1,available_os:["windows"],
  at:"2026-10-01T00:00:00Z"});
const osDemo=osWindow.AICompassEngineer.demoProvider(osDb,windowsOnlyActor,()=>{});
const demo=window.AICompassEngineer.demoProvider(db,{id:"u",role:"engineer"},()=>{saved++;});
Promise.resolve().then(async()=>{
  const results=await demo.list("task",true);
  assert.equal(results.tasks.length,1);
  assert.equal(results.tasks[0].configurations[0].outcome_status,"failed_only");
  assert.equal(results.tasks[0].configurations[0].accepted_run_count,0);
  assert.equal(results.tasks[0].configurations[0].scoring.score,null);
  assert(!JSON.stringify(results).includes("r2"));
  assert.equal(calls.length,3,"Demo must never call Server");
  const detail=await demo.detail("s1","t1");
  assert.equal(detail.entitlement,"unknown_unverified");
  await demo.feedback("idea","t1","Please add a new relevant test case");
  assert.equal(db.feedback.length,1);
  assert.equal(saved,1);
  assert.equal(calls.length,3);
  const osView=await osDemo.list("task",true);
  const configs=osView.tasks[0].configurations;
  const linux=configs.find(x=>x.solution_id==="s-linux");
  const both=configs.find(x=>x.solution_id==="s-both");
  const unknown=configs.find(x=>x.solution_id==="s-unknown");
  assert.equal(both.suitability,"supported_observation");
  assert.equal(both.os.status,"compatible");
  assert.equal(linux.suitability,"other_os_observation",
    "a Linux-only measured tool stays discoverable as a secondary alternative");
  assert.equal(linux.os.requires_os.join(","),"linux");
  assert(linux.os.reason.includes("still discoverable")||
    linux.os.reason.includes("Still discoverable"));
  assert.equal(unknown.suitability,"unverified_or_not_suitable");
  assert.equal(unknown.os.status,"unknown");
  assert.equal(osView.user_os.configured,true);
  const unconfigured=osWindow.AICompassEngineer.demoProvider(
    {...osDb,environmentHistory:[]},{id:"u-none",role:"engineer"},()=>{});
  const unconfiguredView=await unconfigured.list("task",true);
  assert.equal(unconfiguredView.user_os.configured,false);
  assert(unconfiguredView.tasks[0].configurations.every(
    x=>["unconfigured_user","unknown"].includes(x.os.status)),
    "an undeclared OS stays explicitly unconfigured/unknown instead of guessed");
  assert(!unconfiguredView.tasks[0].configurations.some(
    x=>x.os.status==="compatible"),
    "no compatibility is invented before the person declares an OS");
  assert(unconfiguredView.tasks[0].configurations.every(
    x=>x.suitability!=="supported_observation"),
    "no primary shortlist is invented without a declared OS");
  assert(osView.tasks[0].configurations.every(
    x=>x.scoring.score===null&&x.scoring.rank===null),
    "no invented numeric score or rank may appear in the OS projection");
  console.log("FUT-12 shared Engineer Demo/Server projections and no invented scoring passed");
}).catch(error=>{console.error(error);process.exitCode=1;});
