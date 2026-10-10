#!/usr/bin/env node
"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const w={};
vm.runInNewContext(fs.readFileSync("shared-workgroup.js","utf8"),{window:w,URLSearchParams});
const ui=w.AICompassWorkgroup;
assert(ui&&ui.ZONES.length===5);
const blocks=ui.ZONES.flatMap(z=>z.blocks.map(b=>b[0]));
assert.equal(new Set(blocks).size,blocks.length);
for(const required of ["feedback","watch","catalog","tasks","testdesign","forecasts","benchmark","results","recommendations","guides","opportunities","deployment","engineer"])assert(blocks.includes(required));
const grants=["business_read","business_write"];
assert(ui.canVisit("watch",grants,"server",true));
assert(!ui.canVisit("watch",["maintenance_view"],"server",false));
assert(!ui.canVisit("deployment",grants,"server",true));
assert(!ui.canVisit("benchmark",[],"demo",false));
assert(ui.canVisit("benchmark",[],"demo",true));
assert.equal(ui.attention("watch",[{status:"draft"}]),null);
assert.equal(ui.attention("feedback",[{status:"draft"}]),null);
assert.equal(ui.attention("benchmark",[{status:"under_review"},{status:"planned"},{status:"under_review",archived:true}]),1);
assert.equal(ui.attention("forecasts",[{status:"staged"},{status:"published"}]),1);
assert.equal(ui.attention("recommendations",[{status:"in_review"},{status:"review_needed"}]),2);
assert.equal(ui.attention("benchmark",null),null);
const map=ui.renderMap("server",{},grants,true,{benchmark:1,feedback:99});
assert(map.includes("1 requiring review")&&!map.includes("99 requiring review"));
assert(ui.href("demo","tasks").startsWith("?mode=demo"));
assert(ui.href("server","tasks").startsWith("/?mode=server"));
assert(ui.breadcrumbs("server","watch","<unsafe>").includes("&lt;unsafe&gt;"));
const fixture={watch:[{id:"w1",title:"<untrusted>",publication:"published"},{id:"w2",title:"private",publication:"draft"}],
  proposals:[{id:"f1",name:"Experimental"}],guides:[{id:"g1",title:"Published",status:"published"},{id:"g2",title:"Private",status:"draft"}],
  feedback:[{id:"d1",title:"Voice"}],events:[{id:"e1",text:"visible"},{id:"e2",text:"internal",internal:true}]};
(async()=>{
  const demo=ui.demoProvider(fixture,()=>false);
  assert.equal((await demo.list("watch")).length,1);
  assert.equal((await demo.list("guides")).length,1);
  assert.equal((await demo.list("activity")).length,1);
  assert.equal((await ui.demoProvider(fixture,()=>true).list("guides")).length,2);
  const fetched=[];
  const server=ui.serverProvider({request:async path=>{
    fetched.push(path);return {results:[{id:"w1",title:"<untrusted>",publication:"published"}]};}});
  const serverRows=await server.list("watch");
  assert.equal(fetched[0],"/api/v1/watch-entries");
  assert.equal(ui.renderList(serverRows,"watch","server"),ui.renderList(await demo.list("watch"),"watch","demo"));
  const markup=ui.renderList(serverRows,"watch","server");
  assert(markup.includes("&lt;untrusted&gt;")&&!markup.includes("<untrusted>"));
  await assert.rejects(ui.serverProvider({request:async()=>{throw Error("403");}}).list("guides"),/403/);
  await assert.rejects(ui.serverProvider({request:async()=>({not_results:[]})}).list("guides"),/Invalid Server list/);
  const html=fs.readFileSync("prototype.html","utf8");
  const source=html.match(/<script>\s*("use strict";[\s\S]*?)<\/script>/);
  assert(source);new vm.Script(source[1]);
  const mode=fs.readFileSync("server-mode.js","utf8");new vm.Script(mode);
  assert(html.includes('<script src="shared-workgroup.js"></script>'));
  assert(mode.includes('group.renderMap("server"'));
  assert(mode.includes("group.canVisit"));
  console.log("FUT-04 Workgroup shared map, role filters, honest badges, data isolation: PASS");
})().catch(e=>{console.error(e);process.exitCode=1;});
