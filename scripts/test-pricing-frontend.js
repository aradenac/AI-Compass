#!/usr/bin/env node
"use strict";
/* FUT-05: dual-mode pricing markup/adapter and explicit campaign pin contract. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const scripts=["shared-pricing.js","server-pricing-selection.js","server-campaigns.js","server-mode.js"];
for(const file of scripts)new vm.Script(fs.readFileSync(file,"utf8"),{filename:file});
const html=fs.readFileSync("prototype.html","utf8");
const script=html.match(/<script>\s*("use strict";[\s\S]*?)<\/script>/);
assert(script,"Demo inline script must remain valid and static/offline");
new vm.Script(script[1],{filename:"demo-inline.js"});
assert(html.includes('<script src="shared-pricing.js"></script>'));
assert(html.includes('<script src="server-pricing-selection.js"></script>'));
assert(html.includes("var demoPricingAdapter="));
assert(!fs.readFileSync("server-mode.js","utf8").includes("localStorage"));
const log=[],win={AICompassRuntime:{ServerTransport(){
  return {request:async function(path,method,data){
    log.push([path,method||"GET",data]);
    if(path==="/api/v1/pricing/offers")return {results:[]};
    if(path.endsWith("/revisions"))return {revisions:[]};
    if(path.startsWith("/api/v1/catalog/"))return {results:[]};
    return {ok:true};
  }};
}}};
vm.runInNewContext(fs.readFileSync("shared-pricing.js","utf8"),{window:win,Date,console},
{filename:"shared-pricing.js"});
vm.runInNewContext(fs.readFileSync("server-pricing-selection.js","utf8"),{window:win},
{filename:"server-pricing-selection.js"});
const pricing=win.AICompassPricing;
const example=pricing.sample("mdl-demo-test");
assert.equal(example.component_id,"mdl-demo-test");
assert(Array.isArray(example.lines)&&example.lines[0].meter==="input_tokens");
assert.equal(example.status,"unknown","No auto-claim of pricing completeness");
const form={elements:{
  framework_id:{value:""},
  mode:{value:"solution_centred"},
  model:{value:"mdl-pinned"},
  provider:{value:"prv-pinned"},
  harness:{value:"hrn-pinned"}
}};
const host={innerHTML:"",addEventListener(){},
 querySelectorAll(){return []}};
const selection=win.AICompassPricingSelection.mount(host,form,[
 {id:"off-test",revision_id:"00000000-0000-4000-8000-000000000001",
  revision:"r001",name:"A",readiness:{complete:true},
  properties:{component_id:"mdl-pinned",currency:"EUR"}}],[],()=>[]);
assert.equal(selection.rows().length,3);
assert(host.innerHTML.includes("off-test|00000000-0000-4000-8000-000000000001"));
assert(host.innerHTML.includes("Select offer revision"));
assert.deepEqual(Array.from(selection.selections()),[],"Never auto-select a first offer");
form.elements.framework_id.value="frm-test";
assert.equal(selection.rows().length,1);
const adapter=pricing.serverAdapter(()=>{},()=>"");
(async()=>{
 await adapter.offers();
 await adapter.components();
 await adapter.access({id:"mdl-real",type:"model",revision:"r003"},"restricted");
 assert(log.some(x=>x[0]==="/api/v1/pricing/access/model/mdl-real"&&
   x[1]==="PATCH"&&x[2].expected_revision==="r003"));
 assert(log.some(x=>x[0]==="/api/v1/pricing/offers"));
 const server=fs.readFileSync("server-campaigns.js","utf8");
 assert(server.includes("pricing_selections:pricingPicker.selections()"));
 assert(server.includes("AICompassPricingSelection.mount"));
 assert(server.includes("pricing_readiness"));
 console.log("FUT-05 shared pricing editors, no default selection, exact pins, bootstrap: PASS");
})().catch(e=>{console.error(e);process.exitCode=1;});
