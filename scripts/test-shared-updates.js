#!/usr/bin/env node
"use strict";
/* UX-R06: published-only Workgroup Updates presenter and providers. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const source=fs.readFileSync("shared-updates.js","utf8");
const html=fs.readFileSync("prototype.html","utf8");
const compose=fs.readFileSync("compose.yaml","utf8");
const stage=fs.readFileSync("staging/compose.yaml","utf8");
const serverMode=fs.readFileSync("server-mode.js","utf8");
new vm.Script(source,{filename:"shared-updates.js"});
assert(html.includes('<script src="shared-updates.js"></script>'));
assert(html.indexOf("shared-updates.js")<html.indexOf("server-mode.js"));
assert(compose.includes("./shared-updates.js:/srv/frontend/shared-updates.js:ro"));
assert(stage.includes("../shared-updates.js:/srv/frontend/shared-updates.js:ro"));
assert(serverMode.includes("AICompassUpdates.mount"));
assert(!source.includes("localStorage")&&!source.includes("sessionStorage"));
assert(!source.includes("innerHTML=JSON"));

const w={location:{origin:"http://localhost",protocol:"http:",pathname:"/prototype.html",
  search:"?mode=demo&workspace=workgroup",hash:""}};
vm.runInNewContext(fs.readFileSync("shared-runtime.js","utf8"),
  {window:w,URLSearchParams,Set,Map,Array,Object,String,Number,Promise,Error});
vm.runInNewContext(source,{window:w,URLSearchParams,Set,Map,Array,Object,String,Number,
  Promise,Error});
const ui=w.AICompassUpdates;
assert(ui&&typeof ui.present==="function");

const db={
  tasks:[{id:"t1",name:"Task A"}],
  cases:[{id:"c1",task:"t1"}],
  solutions:[{id:"s1",name:"Solution A",publication:"published",
    recommendation:"Recommended for embedded work",lastReviewed:"2026-09-01"},
    {id:"s2",name:"Solution B",publication:"draft",recommendation:"Draft opinion"}],
  runs:[{id:"r1",case:"c1",solution:"s1",status:"published",accepted:true,date:"2026-10-01",
    revision:"r002"},
    {id:"r2",case:"c1",solution:"s1",status:"published",accepted:false,date:"2026-10-02"},
    {id:"r3",case:"c1",solution:"s2",status:"draft",accepted:true,date:"2026-10-03"}],
  campaigns:[{id:"b1",title:"Published <campaign>",status:"published",stage:"published",
    updated:"2026-10-04"},
    {id:"b2",title:"Draft campaign",status:"planned",stage:"planned",updated:"2026-10-05"}],
  guides:[{id:"g1",title:"Published guide",status:"published",type:"Guide",date:"2026-09-30"},
    {id:"g2",title:"Draft guide",status:"draft",type:"Guide",date:"2026-09-30"}],
  watch:[{id:"w1",title:"Reviewed signal",publication:"published",summary:"Signal",
    date:"2026-09-29"},
    {id:"w2",title:"Internal hypothesis",publication:"internal",summary:"Hidden"}],
  components:[{id:"h1",type:"harness",name:"Harness A",publication:"published"},
    {id:"h2",type:"harness",name:"Harness draft",publication:"draft"}],
  proposals:[{id:"f1",name:"Forecast",status:"draft"},{id:"f2",name:"Published forecast",
    status:"published"}]
};
const routePrefix="http://localhost";  /* route() must return a same-origin route */
const route=(mode,workspace,section,params)=>{
  const query=new URLSearchParams(Object.assign({mode,workspace,section},params||{}));
  return "/?"+query.toString();
};
const provider=ui.demoProvider(db);

(async()=>{
  const payload=await provider.load();
  assert.equal(payload.scope,"published_only");
  const kinds=new Set(payload.items.map(x=>x.kind));
  assert(kinds.has("measured_result")&&kinds.has("campaign_published"));
  assert(kinds.has("recommendation_published")&&kinds.has("guide_published"));
  assert(kinds.has("watch_published")&&kinds.has("technology_available"));
  const ids=new Set(payload.items.map(x=>x.source.object_id));
  assert(!ids.has("b2")&&!ids.has("g2")&&!ids.has("w2")&&!ids.has("h2"),"drafts must be excluded");
  assert(!payload.items.some(x=>x.source.object_id==="f2"),
    "theoretical forecasts must never be published knowledge here");
  assert(payload.excluded.theoretical_forecasts==="never included");
  const failed=payload.items.find(x=>x.source.object_id==="r2");
  assert(failed.summary.includes("failed Definition of Done"));
  assert(failed.notice.includes("never an endorsement"));
  const measured=payload.items.find(x=>x.source.object_id==="r1");
  assert.equal(measured.source.revision,"r002");
  const markup=ui.present(payload,{mode:"demo",workspace:"workgroup",route});
  assert(markup.includes("&lt;campaign&gt;"),"hostile titles must be escaped");
  assert(!markup.includes("<campaign>"));
  assert(markup.includes('data-shared-updates="demo"'));
  assert(markup.includes("never included"));
  assert(markup.includes("data-updates-group"));
  assert.equal((markup.match(/data-updates-id="r1"/g)||[]).length,1);

  /* A reader whose persona cannot open the source workspace gets provenance
   * text, never an unreachable deep link. */
  const reader=ui.present(payload,{mode:"demo",workspace:"engineer",
    sections:["results","guides"],route});
  assert(reader.includes("data-updates-source-denied"));
  assert(reader.includes("is not available to this account"));

  assert.throws(()=>ui.present({scope:"private",items:[]},{mode:"demo",route}),
    /published-only/);
  assert.throws(()=>ui.present(payload,{mode:"demo"}),/route builder/);
  const server=ui.serverProvider(async(path,options)=>{
    assert.equal(path,"/api/v1/updates");
    assert.equal(options.method,"GET");
    assert.equal(options.credentials,"same-origin");
    return {ok:true,status:200,json:async()=>({scope:"published_only",items:[],
      counts:{},excluded:{},notes:[]})};},()=>"csrf");
  await server.load();
  const wgSections=ui.serverSections("workgroup",["business_write"]);
  assert(wgSections.includes("benchmark")&&wgSections.includes("results"));
  assert(ui.serverSections("engineer",[]).includes("results"));
  assert(!ui.serverSections("engineer",[]).includes("benchmark"));
  assert.equal(ui.serverSections("management",["planning_view"]).length,0);

  /* With the real Workgroup module loaded the persona scope is exactly its
   * registered sections. */
  const w2={location:{origin:"http://localhost",protocol:"http:",pathname:"/prototype.html",
    search:"?mode=server&workspace=workgroup",hash:""}};
  const scope2={window:w2,URL,URLSearchParams,Set,Map,Array,Object,String,Number,Promise,Error};
  vm.runInNewContext(fs.readFileSync("shared-context.js","utf8"),scope2);
  vm.runInNewContext(fs.readFileSync("shared-workgroup.js","utf8"),scope2);
  vm.runInNewContext(source,scope2,{filename:"shared-updates.js"});
  assert.equal(
    scope2.window.AICompassUpdates.serverSections("workgroup",["business_write"]).sort()
      .join(","),
    Object.keys(scope2.window.AICompassWorkgroup.SECTION_TO_SERVER).sort().join(","));

  const target={hidden:true,innerHTML:"",querySelector:()=>null,replaceChildren(){
    this.innerHTML="";}};
  const mounted=ui.mount(target,{load:async()=>({scope:"published_only",items:[],
    counts:{},excluded:{},notes:[]})},"server",{route,workspace:"engineer"});
  mounted.setAccess(false);
  assert(target.hidden);
  mounted.setAccess(true);
  await new Promise(resolve=>setTimeout(resolve,10));
  assert(!target.hidden);
  assert(target.innerHTML.includes("No published knowledge yet"));
  const failingTarget={hidden:true,innerHTML:"",querySelector:()=>null,replaceChildren(){}};
  const failing=ui.mount(failingTarget,{load:async()=>{throw Error("403");}},"server",{route});
  failing.setAccess(true);
  await new Promise(resolve=>setTimeout(resolve,10));
  assert(failingTarget.innerHTML.includes("No drafts, Demo records or cross-mode fallback"));
  console.log("UX-R06 published Workgroup updates presenter, providers and read boundaries: PASS");
})().catch(error=>{console.error(error);process.exitCode=1;});
