#!/usr/bin/env node
"use strict";
/* FUT-16: isolated fictional Demo, explicit Server-only network, frozen revision. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const src=fs.readFileSync("shared-budgets.js","utf8");
const html=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-planning.js","utf8");
assert(html.includes('<script src="shared-budgets.js"></script>'));
assert(html.includes('demoBudgetSection.id="demo-budgets"'));
assert(server.includes('id="planning-budgets"'));
assert(server.includes('budgets.setAccess(canView,canWrite)'));
const window={};vm.runInNewContext(src,{window,JSON,Number,Math,Date,Object,String,Array,Error,Promise});
(async()=>{
  const calls=[];
  const api=window.AICompassBudgets.serverProvider(async (url,opts)=>{
    calls.push({url,opts});
    return {ok:true,json:async()=>({results:[]})};
  },()=> "fake-csrf-for-test");
  await api.list();
  await api.preview({profile_id:"wlp-test",plan:{}});
  assert.equal(calls[0].url,"/api/v1/planning/budgets");
  assert.equal(calls[0].opts.credentials,"same-origin");
  assert.equal(calls[0].opts.cache,"no-store");
  assert.equal(calls[1].opts.headers["X-CSRFToken"],"fake-csrf-for-test");
  const db={tasks:[{id:"tsk-fake",name:"Fictional task"}]},saved=[];
  const demo=window.AICompassBudgets.demoProvider(db,()=>saved.push("saved"));
  assert.equal((await demo.list()).results.length,0);
  const req={profile_id:"wlp-demo",plan:{name:"Fictional pilot",
    period_months:3,margin_pct:"0",include_active:false,
    items:[{purpose:"pilot",task_id:"tsk-fake",candidate_id:"fct-demo-budget",
      pilot_headcount:2,offer_pins:[{source_key:"root:provider",
        offer_id:"off-demo-sample",offer_revision_id:"fictional-revision"}]}]}};
  const a=await demo.create(req);
  assert.equal(a.fictional_demo_only,true);
  assert.equal(a.revision,"r001");
  assert.equal(saved.length,1);
  const after=await demo.update(a.id,{expected_revision:"r001",plan:req.plan});
  assert.equal(after.revision,"r002");
  assert.equal((await demo.history(a.id)).revisions.length,2);
  assert.equal((await demo.export(a.id)).fictional_demo_only,true);
  assert.equal((await demo.options()).profiles[0].id,"wlp-demo");
  assert(!src.includes("localStorage") && !src.includes("/api/v1/engineer"));
  console.log("FUT-16 Server and isolated Demo adapters OK");
})().catch(e=>{console.error(e);process.exitCode=1;});
