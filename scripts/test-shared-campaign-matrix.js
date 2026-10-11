#!/usr/bin/env node
"use strict";
/* UX-R04: one campaign evaluation matrix presentation for Demo and Server. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const shared=fs.readFileSync("shared-workgroup.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-campaigns.js","utf8");
const context={window:{},Map,Set};
vm.runInNewContext(shared,context,{filename:"shared-workgroup.js"});
const ui=context.window.AICompassWorkgroup;

for(const fn of ["renderCampaignMatrix","renderMatrixCellDetail","renderMatrixDecisionFields",
  "normalizeMatrixPlan","matrixTotals"]) {
  assert.equal(typeof ui[fn],"function","Shared matrix component missing "+fn);
}
// Both modes must consume the shared component, never their own duplicate grid.
for(const source of [page,server]) {
  for(const call of ["renderCampaignMatrix(","renderMatrixCellDetail(","renderMatrixDecisionFields("])
    assert(source.includes(call),"Missing shared matrix call "+call);
}
assert(!page.includes('demoMatrixStatus(c,cell).state]++'),
    "Demo matrix totals must come from the shared component");
assert(!server.includes("data-matrix-decision"),
    "Server matrix decisions must use the shared decision fields");
assert(!server.includes('cell.status.replaceAll("_"," ")'),
    "Server matrix cells must be rendered by the shared component");
assert(page.indexOf('<script src="shared-workgroup.js"></script>') <
       page.indexOf('<script>\n"use strict";'));

/* Equivalent authorized rows in both modes must produce the same presentation. */
const demoProjection={
  revision:"r003",
  tasks:[{id:"task-a",name:"Driver integration"}],
  testCases:[{id:"tcs-a",name:"Driver challenge",revision:"version 2.0"}],
  configurations:[
    {id:"cfg-a",taskId:"task-a",label:"Model A + Provider A",kind:"individual"},
    {id:"cfg-b",taskId:"task-a",label:"Model B + Provider B",kind:"framework"}],
  cells:[
    {id:"evl-a",configurationId:"cfg-a",testCaseId:"tcs-a",status:"evaluated",decision:"selected",
      runs:[{id:"run-a",kind:"individual",outcome:"DoD accepted"}]},
    {id:"evl-b",configurationId:"cfg-b",testCaseId:"tcs-a",status:"waived",decision:"waived",
      activeAttempts:1,testCaseRevision:"r007",introducedRevision:"r003",
      waiver:{reason:"Limited value for this task",actor:"operator",at:"2026-10-11T09:00:00Z"},
      runs:[]}]
};
const serverProjection={revision:"r003",
  tasks:[{id:"task-a",name:"Driver integration"}],
  testCases:[{id:"tcs-a",name:"Driver challenge",revision:"version 2.0"}],
  configurations:[
    {id:"cfg-a",taskId:"task-a",label:"Model A + Provider A",kind:"individual"},
    {id:"cfg-b",taskId:"task-a",label:"Model B + Provider B",kind:"framework"}],
  cells:[
    {id:"evl-a",configurationId:"cfg-a",testCaseId:"tcs-a",status:"evaluated",decision:"selected",
      runs:[{id:"run-a",kind:"individual",outcome:"DoD accepted"}]},
    {id:"evl-b",configurationId:"cfg-b",testCaseId:"tcs-a",status:"waived",decision:"waived",
      activeAttempts:1,testCaseRevision:"r007",introducedRevision:"r003",
      waiver:{reason:"Limited value for this task",actor:"operator",at:"2026-10-11T09:00:00Z"},
      runs:[]}]
};
const routing=cell=>({"data-matrix-cell":cell.id});
const demoHtml=ui.renderCampaignMatrix(demoProjection,{mode:"demo",cellAttributes:routing});
const serverHtml=ui.renderCampaignMatrix(serverProjection,{mode:"server",cellAttributes:routing});
assert.equal(demoHtml.replace(/demo/g,"MODE"),serverHtml.replace(/server/g,"MODE"),
    "Equivalent rows must render the same matrix component in both modes");
for(const html of [demoHtml,serverHtml]) {
  assert(html.includes('data-shared-matrix="'),"Shared matrix root marker missing");
  assert.equal((html.match(/data-shared-matrix-cell=/g)||[]).length,2);
  assert(html.includes("Pending: 0")&&html.includes("Waived: 1")&&html.includes("Evaluated: 1"));
  assert(html.includes("Candidate cells: 2"));
  assert(html.includes("<strong>Full plan: complete</strong>"));
  assert(html.includes("never measured evidence"));
  assert(html.includes('data-matrix-state="not_selected"')===false);
  assert(!html.includes("undefined"),"Undefined value rendered into the matrix");
}
assert(ui.renderCampaignMatrix({...demoProjection,
  cells:[{id:"evl-a",configurationId:"cfg-a",testCaseId:"tcs-a",status:"pending"}]},
  {mode:"demo"}).includes("<strong>Full plan: outstanding</strong>"));
assert(ui.renderCampaignMatrix({...demoProjection,cells:[]},{mode:"server",emptyText:"No cells yet"})
  .includes("No cells yet"));

/* Hostile authorized values stay inert text in every shared surface. */
const hostile={...demoProjection,
  tasks:[{id:"task-a",name:"<img src=x onerror=alert(1)>"}],
  testCases:[{id:"tcs-a",name:"Case & <b>bold</b>",revision:"version 1.0"}],
  configurations:[{id:"cfg-a",taskId:"task-a",label:'"quoted" & <script>',kind:"individual"}],
  cells:[{id:"evl-a",configurationId:"cfg-a",testCaseId:"tcs-a",status:"waived",
    decision:"waived",waiver:{reason:"<b>unsafe</b> & reason",actor:"a<b",at:"now"},
    runs:[{id:"run-a",kind:"individual",outcome:"DoD failed & <i>not</i> accepted"}]}]};
const hostileHtml=ui.renderCampaignMatrix(hostile,{mode:"demo",cellAttributes:routing});
for(const raw of ["<img src=x","<script>","<b>unsafe</b>"])
  assert(!hostileHtml.includes(raw),"Unescaped matrix value: "+raw);
assert(hostileHtml.includes("&lt;img src=x onerror=alert(1)&gt;"));
const hostileDetail=ui.renderMatrixCellDetail(hostile,"evl-a",{mode:"demo"});
assert(hostileDetail.includes("&lt;b&gt;unsafe&lt;/b&gt; &amp; reason"));
assert(!hostileDetail.includes("<b>unsafe</b>"));
assert(hostileDetail.includes("DoD failed &amp; &lt;i&gt;not&lt;/i&gt; accepted"));

/* Cell detail and decision fields keep provenance and refuse unsafe input. */
const detail=ui.renderMatrixCellDetail(serverProjection,"evl-b",{mode:"server"});
assert(detail.includes('data-matrix-cell-detail="evl-b"'));
assert(detail.includes("pinned revision r007"));
assert(detail.includes("Limited value for this task"));
assert(detail.includes("introduced in r003"));
assert(detail.includes("No measured Run is attached to this evaluation yet."));
assert(detail.includes("never measured evidence"));
const runDetail=ui.renderMatrixCellDetail({...serverProjection,
  cells:[{id:"evl-a",configurationId:"cfg-a",testCaseId:"tcs-a",status:"evaluated",
    decision:"selected",runs:[{id:"run-a",kind:"individual",revision:"r004",
    outcome:"DoD accepted",href:"/api/v1/x"}]}]},"evl-a",{mode:"server"});
assert(runDetail.includes("r004")&&runDetail.includes("DoD accepted"));
assert.throws(()=>ui.renderMatrixCellDetail({...serverProjection,
  cells:[{id:"evl-a",configurationId:"cfg-a",testCaseId:"tcs-a",status:"evaluated",
    runs:[{id:"run-a",href:"https://evil.example/x"}]}]},"evl-a",{mode:"server"}),
  /same-origin/, "External matrix run links must be refused");
const decisions=ui.renderMatrixDecisionFields(serverProjection,"evl-b","server");
assert(decisions.includes('data-shared-matrix-decision="server"'));
assert(decisions.includes('name="decision"')&&decisions.includes('name="reason"'));
assert(decisions.includes("Only a waiver accepts a reason"));
assert(decisions.includes('<option value="waived" selected>'));

/* Unknown or incomplete authorized projections fail closed instead of guessing. */
assert.throws(()=>ui.renderCampaignMatrix(demoProjection,{}),/mode required/);
assert.throws(()=>ui.renderCampaignMatrix(demoProjection,{mode:"live"}),/mode required/);
assert.throws(()=>ui.normalizeMatrixPlan({...demoProjection,revision:""},"demo"),
  /exact revision/);
assert.throws(()=>ui.renderCampaignMatrix({...demoProjection,
  cells:[{id:"evl-x",configurationId:"cfg-a",testCaseId:"tcs-a",status:"brilliant"}]},
  {mode:"demo"}),/Unsupported matrix cell state/);
assert.throws(()=>ui.renderCampaignMatrix({...demoProjection,
  cells:[{id:"evl-x",configurationId:"missing",testCaseId:"tcs-a",status:"pending"}]},
  {mode:"demo"}),/requires its configuration/);
assert.throws(()=>ui.renderCampaignMatrix({...demoProjection,
  cells:[{id:"evl-x",configurationId:"cfg-a",testCaseId:"missing",status:"pending"}]},
  {mode:"demo"}),/requires its Test Case/);
assert.throws(()=>ui.renderCampaignMatrix({...demoProjection,
  cells:[{id:"evl-x",configurationId:"cfg-a",testCaseId:"tcs-a",status:"pending",
    decision:"maybe"}]},{mode:"server"}),/Unsupported matrix decision/);
assert.throws(()=>ui.renderCampaignMatrix({...demoProjection,
  cells:[{id:"evl-x",configurationId:"cfg-a",testCaseId:"tcs-a",status:"waived",
    decision:"waived",waiver:{reason:"  "}}]},{mode:"demo"}),/keep its reason/);
assert.throws(()=>ui.renderCampaignMatrix(demoProjection,{mode:"demo",
  cellAttributes:()=>({onclick:"steal()"})}),/Invalid matrix attribute/);
assert.throws(()=>ui.renderMatrixCellDetail(demoProjection,"evl-missing",{mode:"demo"}),
  /not part of this authorized revision/);

/* Counter math is shared, never re-derived per mode. */
const totals=ui.matrixTotals(ui.normalizeMatrixPlan(demoProjection,"demo"));
assert.deepEqual({...totals},{candidates:2,pending:0,in_progress:0,evaluated:1,waived:1,
  not_selected:0,measured_runs:1,active_attempts:1,selected_obligations:1,outstanding:0,
  full_plan_complete:true});
console.log("UX-R04 shared campaign evaluation matrix: Demo/Server parity, escaping, "+
  "provenance and fail-closed projections PASS");
