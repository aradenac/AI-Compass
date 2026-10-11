#!/usr/bin/env node
"use strict";
/* UX-R04: common Test Design projection and safe mode-specific actions. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const shared=fs.readFileSync("shared-workgroup.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-test-cases.js","utf8");
const context={window:{},Map,Set};
vm.runInNewContext(shared,context,{filename:"shared-workgroup.js"});
const ui=context.window.AICompassWorkgroup;
const render=ui.renderCases;
assert.equal(typeof render,"function");
assert(page.includes("AICompassWorkgroup.renderCases(visible,db.tasks"));
assert(server.includes("AICompassWorkgroup.renderCases(cases,tasks"));
assert(page.indexOf('<script src="shared-workgroup.js"></script>') <
       page.indexOf('<script>\n"use strict";'));
const demo=[
 {id:"tc-a",task:"task-a",title:"<script>bad</script>",version:"1.0",objective:"Safe & sound"},
 {id:"tc-b",task:"task-a",title:"Child",version:"1.0.1",parentCaseId:"tc-a"},
 {id:"tc-cycle1",task:"task-a",title:"Cycle one",version:"2",parentCaseId:"tc-cycle2"},
 {id:"tc-cycle2",task:"task-a",title:"Cycle two",version:"2.1",parentCaseId:"tc-cycle1"}
];
const serverRecords=demo.map(r=>({
 id:r.id,task_id:r.task,name:r.title,case_version:r.version,
 fork_parent_id:r.parentCaseId||null,revision:"r001",
 properties:{objective:r.objective||""}
}));
const tasks=[{id:"task-a",name:"<Primary> Task"}];
const a=render(demo,tasks,{mode:"demo",canWrite:true,publishedRunCounts:{"tc-a":2}});
const b=render(serverRecords,tasks,{mode:"server",canWrite:false});
assert(a.includes("&lt;script&gt;bad&lt;/script&gt;")&&!a.includes("<script>"));
assert(b.includes("&lt;Primary&gt; Task")&&!b.includes("<Primary>"));
for(const id of ["tc-a","tc-b","tc-cycle1","tc-cycle2"]){
 const match=new RegExp('data-shared-case="'+id+'"',"g");
 assert.equal((a.match(match)||[]).length,1,id+" Demo rendered exactly once");
 assert.equal((b.match(match)||[]).length,1,id+" Server rendered exactly once");
}
assert(a.includes("2 published run(s)")&&!b.includes("published run(s)"));
assert(a.includes('data-act="caseDetail"'));
assert(b.includes('data-action="history"')&&!b.includes('data-action="edit"'));
const writer=render(serverRecords,tasks,{mode:"server",canWrite:true});
assert(writer.includes('data-action="edit"')&&writer.includes('data-action="fork"'));
assert(!render([],tasks,{mode:"server"}).includes('data-action="edit"'));
assert.throws(()=>render(null,tasks,{mode:"server"}),/Authorized Test Cases/);
assert.throws(()=>render(demo,tasks,{mode:"invalid"}),/Explicit Demo or Server/);

const demoDetail=ui.renderCaseDetail(demo[0],"demo",{taskName:"Task"});
const serverDetail=ui.renderCaseDetail(serverRecords[0],"server",{taskName:"Task"});
assert(demoDetail.includes('data-shared-case-detail="demo"'));
assert(serverDetail.includes('data-shared-case-detail="server"'));
assert(demoDetail.includes("&lt;script&gt;bad&lt;/script&gt;")&&!demoDetail.includes("<script>"));
assert(demoDetail.includes("Safe &amp; sound")&&serverDetail.includes("Safe &amp; sound"));
const fields=ui.renderCaseFields({objective:"<input>",dod:"finish"},["objective","dod"]);
assert(fields.includes("&lt;input&gt;")&&!fields.includes("<input>"));
assert(fields.includes('name="objective"')&&fields.includes('name="dod"'));
assert(!fields.includes('name="environment"'));
assert.throws(()=>ui.renderCaseFields({},["danger"]),/Unknown Test Case/);
assert(page.includes("AICompassWorkgroup.renderCaseFields(from"));
assert(page.includes("constraints:d.constraints") && page.includes("expected_outputs:d.expected_outputs") && page.includes("environment:d.environment"));
assert(page.includes("renderCaseDetail(c,\"demo\""));
assert(server.includes("AICompassWorkgroup.renderCaseFields(p)"));


// Shared business collection contracts cover both modes and never accept
// unescaped action attributes or cross-origin navigation.
const records=[{id:"obj-1",title:"<unsafe>",revision:"r002",status:"draft",
  description:"Evidence & rationale",facts:["source"],notices:["Review needed"],
  actions:[{label:"Read",attributes:{"data-act":"detail","data-id":"obj-1"}}]}];
const rd=ui.renderRecords(records,{domain:"guides",mode:"demo"});
const rs=ui.renderRecords(records,{domain:"guides",mode:"server"});
assert(rd.includes('data-business-record="obj-1"'));
assert(rs.includes('data-business-record="obj-1"'));
assert(rd.includes("&lt;unsafe&gt;")&&!rd.includes("<unsafe>"));
assert(rd.includes("Evidence &amp; rationale"));
assert(rd.includes('data-act="detail"')&&!rd.includes("javascript:"));
assert(!ui.renderRecords([],{domain:"watch",mode:"demo"}).includes('data-business-record='));
assert.throws(()=>ui.renderRecords(null,{domain:"watch",mode:"server"}),/Authorized business/);
assert.throws(()=>ui.renderRecords(records,{domain:"watch",mode:"invalid"}),/Explicit business/);
assert.throws(()=>ui.renderRecords([{id:"x",actions:[{label:"Go",attributes:{onclick:"alert(1)"}}]}],
 {domain:"watch",mode:"server"}),/Invalid business action/);
assert.throws(()=>ui.renderRecords([{id:"x",links:[{href:"https://evil.example"}]}],
 {domain:"watch",mode:"server"}),/same-origin/);


const guideDemo={id:"g1",title:"<Guide>",body:"Steps & details",url:"https://example.test/setup?a=1&b=2",
  description:"Keep <original> references",type:"Installation",revision:"r004",status:"published"};
const guideServer={id:"g1",name:guideDemo.title,type:"setup_guide",revision:"r004",
  properties:{text:guideDemo.body,url:guideDemo.url,description:guideDemo.description}};
for(const [row,mode,fields] of [
  [guideDemo,"demo",["title","body","url","description"]],
  [guideServer,"server",["name","text","url","description"]]
]) {
  const markup=ui.renderGuideFields(row,mode);
  assert(markup.includes('data-shared-guide-fields="'+mode+'"'));
  for(const name of fields)assert(markup.includes('name="'+name+'"'));
  assert(markup.includes("&lt;Guide&gt;")&&!markup.includes("<Guide>"));
  const detail=ui.renderGuideDetail(row,mode);
  assert(detail.includes("&lt;Guide&gt;"));
  assert(detail.includes("Steps &amp; details"));
  assert(detail.includes('rel="noopener noreferrer"'));
  assert(detail.includes('data-shared-guide-detail="'+mode+'"'));
}
assert(!ui.renderGuideDetail({...guideDemo,url:"invalid-url"},"demo").includes('href="invalid-url"'));
assert.throws(()=>ui.renderGuideDetail(guideDemo,"other"),/Explicit authorized Guide/);
assert(page.includes('renderGuideFields(g||{},"demo")'));
assert(page.includes('renderGuideDetail(g,"demo")'));
assert(page.includes("description:d.description"));


const watchDemo={id:"w1",title:"Research <hypothesis>",hypothesis:"New & uncertain",
  assumptions:"No benchmark yet",kind:"Research",status:"reviewed",publication:"published"};
const watchServer={id:"w1",name:watchDemo.title,revision:"r001",status:"reviewed",
  properties:{hypothesis:watchDemo.hypothesis,assumptions:watchDemo.assumptions,
   visibility:"published",review_state:"reviewed"}};
for(const [row,mode] of [[watchDemo,"demo"],[watchServer,"server"]]) {
 const d=ui.renderKnowledgeDetail(row,{domain:"watch",mode});
 assert(d.includes('data-knowledge-domain="watch"'));
 assert(d.includes("New &amp; uncertain"));
 assert(d.includes("&lt;hypothesis&gt;")&&!d.includes("<hypothesis>"));
}
const forecastDemo={id:"f1",name:"Projected <setup>",status:"staged",
  confidence:"low",rationale:"External & speculative",
  quality:null,aiCost:null,uncertainty:"Not tested"};
const forecastServer={id:"f1",name:forecastDemo.name,revision:"r001",status:"staged",
  properties:{confidence:"low",rationale:forecastDemo.rationale,
    uncertainty:forecastDemo.uncertainty,predicted_metrics:{}}};
for(const [row,mode] of [[forecastDemo,"demo"],[forecastServer,"server"]]) {
 const d=ui.renderKnowledgeDetail(row,{domain:"forecasts",mode});
 assert(d.includes("THEORETICAL")&&d.includes("NOT measured Run evidence"));
 assert(d.includes("External &amp; speculative"));
 assert(!d.includes("Predicted quality / 100</h4>"),"Missing metrics must not become zero");
}
const source=ui.renderKnowledgeDetail({id:"src1",name:"External paper",
  properties:{url:"Citation reference",claim:"Independent <finding>",citation:"Published 2026",assessment:"Preliminary"}},{domain:"sources",mode:"server"});
assert(source.includes("External source material is not controlled"));
assert(source.includes("Independent &lt;finding&gt;") && source.includes("Published 2026"));
assert.throws(()=>ui.renderKnowledgeDetail(watchDemo,{domain:"runs",mode:"demo"}),/Explicit authorized/);
assert(page.includes('renderKnowledgeDetail(w,{domain:"watch",mode:"demo"})'));
assert(page.includes('renderKnowledgeDetail(p,{domain:"forecasts",mode:"demo"})'));

console.log("UX-R04 shared Test Design tree: Demo, Server, forks, roles, escaping PASS");
