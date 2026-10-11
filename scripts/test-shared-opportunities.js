#!/usr/bin/env node
"use strict";
/* FUT-13: shared Demo and Server adapter isolation, no implicit economics. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const src=fs.readFileSync("shared-opportunities.js","utf8");
const html=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-planning.js","utf8");
const compose=fs.readFileSync("compose.yaml","utf8");
const stage=fs.readFileSync("staging/compose.yaml","utf8");
new vm.Script(src,{filename:"shared-opportunities.js"});
assert(html.includes('<script src="shared-opportunities.js"></script>'));
assert(html.includes("window.AICompassOpportunities.demoProvider(db)"));
assert(server.includes("window.AICompassOpportunities.serverProvider"));
assert(compose.includes("./shared-opportunities.js:/srv/frontend/shared-opportunities.js:ro"));
assert(stage.includes("../shared-opportunities.js:/srv/frontend/shared-opportunities.js:ro"));
assert(!src.includes("localStorage")&&!src.includes("sessionStorage"));
const calls=[];
const window={AICompassRuntime:{ServerTransport:()=>({request:(path,method,body)=>{
 calls.push({path,method,body});return Promise.resolve({results:[]});}})}};
vm.runInNewContext(src,{window,Set,Map,Date,Object,JSON,Number}, {filename:"shared-opportunities.js"});
const api=window.AICompassOpportunities.serverProvider(()=>{},()=> "");
const scenario={name:"What if",choices:[{task_id:"tsk-x",kind:"benchmark",
 candidate_id:"sol-x"}],benchmark_weight:"0.8"};
const db={tasks:[{id:"t1",name:"Fake Task",parent:null}],
 cases:[{id:"c1",task:"t1"}],
 solutions:[{id:"s1",name:"Fake tool",accessible:true}],
 runs:[{id:"r1",case:"c1",solution:"s1",status:"published",accepted:true}],
 proposals:[]};
const demo=window.AICompassOpportunities.demoProvider(db);
Promise.resolve().then(async()=>{
 await api.bootstrap();
 assert.equal(calls.length,4);
 assert.equal(calls[2].path,"/api/v1/planning/opportunities/candidates");
 await api.preview("wlp-x",scenario);
 assert.equal(calls[4].path,"/api/v1/planning/opportunities/preview");
 assert.equal(calls[4].method,"POST");
 const fixture=await demo.bootstrap();
 assert.equal(fixture.profiles[0].id,"wlp-demo");
 assert.equal(fixture.candidates[0].kind,"benchmark");
 const projected=await demo.preview("wlp-demo",{name:"Fictional",benchmark_weight:"0.8",
   choices:[{task_id:"t1",kind:"benchmark",candidate_id:"s1"}]});
 assert.equal(projected.activation_status,"never_verified_in_demo");
 assert.equal(projected.totals.activated_potential_eur,"0.00");
 assert(Number(projected.totals.benchmarked_opportunity_eur)>0);
 assert.equal(calls.length,5,"Demo must not call a Server endpoint");
 assert.equal(db.runs.length,1,"Demo scenario must not rewrite evidence");
 console.log("FUT-13 opportunity Demo/Server isolation and non-activated scenario passed");
}).catch(error=>{console.error(error);process.exitCode=1;});
