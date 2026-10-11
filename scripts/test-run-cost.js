#!/usr/bin/env node
"use strict";
/* FUT-09: deterministic offline fixture and Server UI/Run separation checks. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const html=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-sessions.js","utf8");
const individual=fs.readFileSync("backend/config/run_services.py","utf8");
const composite=fs.readFileSync("backend/config/composite_run_services.py","utf8");
new vm.Script(server,{filename:"server-sessions.js"});
for(const block of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)){
 if(block[1].trim())new vm.Script(block[1],{filename:"prototype.html"});
}
const a=html.indexOf("function demoTariffCheck(spec){"),
 b=html.indexOf("function campaignTrialStart(campaignId,caseId){",a);
assert(a>0&&b>a);
const scope={};vm.runInNewContext(html.slice(a,b),scope);
const spec={
 revision:"r001",currency:"EUR",
 lines:[
 {source_key:"root:model",charge_id:"input",charge_type:"variable",
  meter:"input_tokens",unit_size:1000000,rate:"2.5"},
 {source_key:"root:model",charge_id:"requests",charge_type:"variable",
  meter:"requests",unit_size:1,tiers:[
   {up_to:10,rate:"0.1"},{up_to:null,rate:"0.2"}]},
 {source_key:"root:harness",charge_id:"subscription",
  charge_type:"fixed",rate:"39",period:"seat_month"}
]};
const checked=scope.demoTariffCheck(spec);
const incomplete=scope.demoTariffQuote(checked,{"root:model":{"input_tokens":0}});
assert.equal(incomplete.ready,false);
assert(incomplete.missing.includes("root:model/requests"));
assert.equal(incomplete.variable_charges[0].amount,0,"Explicit zero must stay zero");
const complete=scope.demoTariffQuote(checked,
 {"root:model":{"input_tokens":1000000,requests:15}});
assert.equal(complete.ready,true);
assert.equal(complete.variable_reference_cost,4.5);
assert.equal(complete.fixed_commitments.length,1);
assert(!complete.variable_charges.some(x=>x.charge_id==="subscription"));
const preserved=JSON.stringify(spec);
scope.demoTariffCheck(spec);
assert.equal(JSON.stringify(spec),preserved,"Validation cannot rewrite the original offer");
const credit={revision:"r002",currency:"USD",lines:[
 {source_key:"ptp-builder:provider",charge_id:"provider-credit",
  charge_type:"variable",meter:"provider_credits",
  provider_credit_namespace:"provider-A",unit_size:100,rate:"1.25"}]};
assert.equal(scope.demoTariffQuote(scope.demoTariffCheck(credit),
 {"ptp-builder:provider":{"provider_credits":200}}).variable_reference_cost,2.5);
for(const rate of [null,"",false,-1,Infinity]){
 assert.throws(()=>scope.demoTariffCheck({...spec,lines:[{...spec.lines[0],rate}]}));
}
assert.throws(()=>scope.demoTariffCheck({...spec,lines:[spec.lines[0],spec.lines[0]]}),
 "Duplicate invoice lines must be refused");
assert(server.includes('"/metering"')||server.includes('"/metering","PATCH"'));
assert(server.includes('"/results","PATCH"'));
assert(server.includes("payload.expected_revision=session.revision"));
assert(!server.includes("localStorage"),"Server cannot fall back to Demo");
assert(individual.includes('metrics["reference_cost"]'));
assert(composite.includes('metrics["reference_cost"]'));
assert(html.includes("session.pendingResults=")&&html.includes("t.calculatedCost"));
console.log("FUT-09: Demo tariff conversion, tiered charges, missing vs zero, and Server pending Runs passed");
