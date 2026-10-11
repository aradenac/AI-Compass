#!/usr/bin/env node
"use strict";
/* FUT-15 isolated fictional Demo provider: no Server, no shared real entitlement state. */
const vm=require("node:vm"),fs=require("node:fs"),assert=require("node:assert/strict");
const src=fs.readFileSync("demo-deployments.js","utf8");
const html=fs.readFileSync("prototype.html","utf8");
assert(html.includes('<script src="demo-deployments.js"></script>'));
assert(html.includes('demoDeploymentSection.id="demo-deployments"'));
assert(!src.includes("fetch(")&&!src.includes("credentials:"));
const w={AICompassOpportunities:{demoProvider(){return {bootstrap:async()=>({
  profiles:[{id:"wlp-demo",name:"Fictional cohort"}],
  candidates:[{task_id:"t1",kind:"benchmark",candidate_id:"s1",name:"Fictional run"}]
})};}}};
vm.runInNewContext(src,{window:w,Date,Set,JSON,Error});
(async()=>{
 const db={},saved=[];
 const api=w.AICompassDemoDeployments.provider(db,()=>saved.push(true));
 const targets=await api("deployments","GET");
 assert.equal(targets.results.length,0);
 let target=await api("deployments","POST",{profile_id:"wlp-demo",
  task_id:"t1",kind:"benchmark",candidate_id:"s1",
  selection:{seats:[{key:"fictional-01",available_os:["linux"]}]}});
 assert.equal(target.activated_count,0);
 assert.equal(target.fictional_demo_only,true);
 const status=async()=>api("deployments/"+target.id,"GET");
 const event=async(c,a,ref="")=>api("deployments/"+target.id+"/events","POST",{
  expected_revision:target.revision,seat_key:"fictional-01",component_id:c,
  action:a,evidence_reference:ref});
 await assert.rejects(event(null,"first_use","Fictional ticket 01"));
 for(const c of target.components){
  for(const a of ["requested","approved","provisioned","verified"])
   await event(c.id,a,"Fictional ticket 01");
 }
 await event(null,"setup_verified","Fictional setup verification");
 await event(null,"first_use","Fictional first use verification");
 assert.equal((await status()).activated_count,1);
 await event(target.components[0].id,"revoked");
 assert.equal((await status()).activated_count,0);
 for(const a of ["requested","approved","provisioned","verified"])
   await event(target.components[0].id,a,"Fictional repeat verification");
 assert.equal((await status()).activated_count,0);
 assert(saved.length>2,"Fictional changes persist independently");
 assert.equal(Object.keys(db).join(","),"demoDeploymentTargets");
 console.log("FUT-15 fictional Demo target, access and first use isolation passed");
})().catch(err=>{console.error(err);process.exitCode=1;});
