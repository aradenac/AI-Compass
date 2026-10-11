#!/usr/bin/env node
"use strict";
/* FUT-14 protected Server provider vs independently fictional Demo heatmap. */
const fs=require("node:fs"),assert=require("node:assert/strict"),vm=require("node:vm");
const src=fs.readFileSync("shared-opportunity-heatmap.js","utf8");
const html=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-mode.js","utf8");
const compose=fs.readFileSync("compose.yaml","utf8");
const staging=fs.readFileSync("staging/compose.yaml","utf8");
new vm.Script(src,{filename:"shared-opportunity-heatmap.js"});
assert(html.includes('<script src="shared-opportunity-heatmap.js"></script>'));
assert(html.indexOf('shared-opportunities.js')<html.indexOf('shared-opportunity-heatmap.js'));
assert(html.indexOf('shared-opportunity-heatmap.js')<html.indexOf('server-mode.js'));
assert(server.includes("AICompassHeatmap.mount"));
assert(server.includes('personaId === "management"'));
assert(server.includes('grants.includes("planning_view") && personaId === "management"'));
assert(compose.includes("./shared-opportunity-heatmap.js:/srv/frontend/shared-opportunity-heatmap.js:ro"));
assert(staging.includes("../shared-opportunity-heatmap.js:/srv/frontend/shared-opportunity-heatmap.js:ro"));
assert(!src.includes("localStorage")&&!src.includes("sessionStorage"));
const requests=[];
const existing=fs.readFileSync("shared-opportunities.js","utf8");
const window={AICompassRuntime:{ServerTransport:()=>({
  request:(path,method,body)=>{requests.push({path,method,body});return Promise.resolve({results:[]});}
})}};
vm.runInNewContext(existing,{window,Set,Map,Date,Object,JSON,Number},{
 filename:"shared-opportunities.js"});
vm.runInNewContext(src,{window,Set,Map,Date,Object,JSON,Number},{
 filename:"shared-opportunity-heatmap.js"});
const api=window.AICompassHeatmap.serverProvider(()=>{},()=> "");
const demo=window.AICompassHeatmap.demoProvider({
 tasks:[{id:"t1",name:"Sample task",parent:null}],
 cases:[{id:"tc1",task:"t1"}],
 runs:[{id:"r1",case:"tc1",solution:"s1",status:"published",accepted:true}],
 solutions:[{id:"s1",name:"Fake demo agent",accessible:true}],
 proposals:[]
});
(async()=>{
 const boot=await api.bootstrap();
 assert.equal(requests.length,2);
 assert.equal(requests[0].path,"/api/v1/planning/profiles");
 assert.equal(requests[1].path,"/api/v1/planning/opportunities");
 await api.heatmap({profile_id:"wlp-x",scenario_id:"opp-x",row_page:2});
 assert(requests[2].path.includes("/api/v1/planning/heatmap?"));
 assert(requests[2].path.includes("row_page=2"));
 await api.insights({profile_id:"wlp-x",revision:"r001"});
 assert(requests[3].path.includes("/api/v1/planning/insights?"));
 await api.explain({profile_id:"wlp-x",scenario_id:"opp-x",
   task_id:"tsk-x",kind:"benchmark",candidate_id:"sol-x"});
 assert(requests[4].path.includes("/api/v1/planning/insights/explain?"));
 await api.suggestions({profile_id:"wlp-x",limit:20});
 assert(requests[5].path.includes("/api/v1/planning/insights/suggestions?"));
 const fixtures=await demo.bootstrap();
 assert.equal(fixtures.profiles[0].id,"wlp-demo");
 assert.equal(fixtures.scenarios.length,1);
 const m=await demo.heatmap({profile_id:"wlp-demo",scenario_id:"opp-demo-insights",
   row_page:0,column_page:0,row_size:8,column_size:8});
 assert.equal(m.total_rows,1);
 assert.equal(m.total_columns,1);
 assert.equal(m.cells.length,1);
 assert.equal(m.cells[0].maturity,"B");
 assert.equal(m.cells[0].selected,true);
 assert.equal(m.period,"annual");
 const current=await demo.insights({profile_id:"wlp-demo",scenario_id:"opp-demo-insights"});
 const frozen=await demo.insights({profile_id:"wlp-demo",
   scenario_id:"opp-demo-insights",revision:"r001"});
 assert.equal(current.snapshots.length,2);
 assert.equal(frozen.historical,true);
 assert(Number(current.portfolio.totals.positive_modeled_total_eur)>
        Number(frozen.portfolio.totals.positive_modeled_total_eur));
 const explained=await demo.explain({profile_id:"wlp-demo",scenario_id:"opp-demo-insights",
   task_id:"t1",kind:"benchmark",candidate_id:"s1",revision:"r001"});
 assert.equal(explained.historical,true);
 assert.equal(requests.length,6,"fictional Demo made unauthorized Server requests");
 assert.equal(m.cells[0].maturity,"B");
 console.log("FUT-14 Management heatmap current/historical projections and strict Demo/Server separation passed");
})().catch(e=>{console.error(e);process.exitCode=1;});
