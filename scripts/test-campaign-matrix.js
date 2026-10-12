#!/usr/bin/env node
"use strict";
/* FUT-08/UX-R04: fake offline Demo matrix semantics on the shared component. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const html=fs.readFileSync("prototype.html","utf8");
const campaign=fs.readFileSync("server-campaigns.js","utf8");
const sessions=fs.readFileSync("server-sessions.js","utf8");
new vm.Script(campaign,{filename:"server-campaigns.js"});
new vm.Script(sessions,{filename:"server-sessions.js"});
const begin=html.indexOf("function demoMatrixStatus(c,cell){");
const end=html.indexOf("function dialogDemoMatrixAdd(id){",begin);
assert(begin>=0&&end>begin,"Offline campaign matrix renderer exists");
const code=html.slice(begin,end);
const campaignData={id:"cmp-demo",matrixPlan:{configurations:[
  {id:"cfg-one",taskId:"task-driver",label:"Solution A"},
  {id:"cfg-two",taskId:"task-driver",label:"Solution B"}
],cells:[
  {id:"ev-a",configurationId:"cfg-one",caseId:"tc-one",decision:"selected",history:[]},
  {id:"ev-b",configurationId:"cfg-two",caseId:"tc-one",decision:"waived",
   waiver:{reason:"Limited value",actor:"operator"},history:[]}
]}};
const db={campaignTrials:[],runs:[],revisions:[]};
const sandbox={window:{},Map,Set,db,rec:(kind,id)=>{
  if(kind==="tasks")return {id,name:"Driver task"};
  if(kind==="cases")return {id,title:"TC1"};
  return null;
},actor:id=>id,E:s=>String(s),btn:()=>"",canEdit:()=>false};
vm.runInNewContext(fs.readFileSync("shared-workgroup.js","utf8"),sandbox,
  {filename:"shared-workgroup.js"});
vm.runInNewContext(code,sandbox,{filename:"demo-campaign-matrix.js"});
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[0]).state,"pending");
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[1]).state,"waived");
const demoMatrix=sandbox.demoMatrixMarkup(campaignData);
assert(demoMatrix.includes("Pending: 1")&&demoMatrix.includes("Waived: 1"));
assert(demoMatrix.includes('data-shared-matrix="demo"'),
  "Demo campaign matrix must use the shared matrix component");
assert(demoMatrix.includes('data-matrix-mode="demo"'));
assert(demoMatrix.includes("never measured evidence"));
assert(demoMatrix.includes("Limited value"),"Recorded waiver reason stays visible");
assert(!demoMatrix.includes('<td style="opacity:.55"'),
  "The duplicated Demo matrix grid markup must be gone");
const projection=sandbox.demoMatrixProjection(campaignData);
assert.equal(projection.cells.length,2);
assert.equal(projection.cells[0].status,"pending");
assert.equal(projection.cells[1].waiver.reason,"Limited value");
assert.equal(projection.revision,"r001");
db.campaignTrials.push({campaign:"cmp-demo",evaluationId:"ev-a",status:"in_progress"});
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[0]).state,"in_progress");
assert(sandbox.demoMatrixMarkup(campaignData).includes("In Progress: 1"));
db.runs.push({campaignId:"cmp-demo",accepted:false,
  initialSetup:{evaluationId:"ev-a"},outcome:"failed"});
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[0]).state,"evaluated");
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[1]).state,"waived");
const scored=sandbox.demoMatrixMarkup(campaignData);
assert(scored.includes("Evaluated: 1")&&scored.includes("1 Run(s)"),
  "Measured Demo Runs are counted by the shared matrix component");
const scoredProjection=sandbox.demoMatrixProjection(campaignData);
const cellDetail=sandbox.window.AICompassWorkgroup.renderMatrixCellDetail(
  scoredProjection,"ev-a",{mode:"demo"});
assert(cellDetail.includes("DoD failed")&&cellDetail.includes("run_demo")===false,
  "The rejected Demo Run keeps its explicit non-success outcome in the shared cell detail");
assert(cellDetail.includes(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[0]).runs[0].id),
  "The shared cell detail keeps the exact measured Run identity");
assert(campaign.includes('api("campaigns/"+encodeURIComponent(row.id)+"/matrix"'));
assert(campaign.includes('"/matrix/edit"'));
assert(campaign.includes("renderCampaignMatrix(")&&campaign.includes("renderMatrixDecisionFields("),
  "Server must render the same shared matrix component and decision fields");
assert(!campaign.includes("data-matrix-decision"),
  "The obsolete duplicated Server decision buttons must be gone");
assert(!campaign.includes('cell.status.replaceAll("_"," ")'),
  "The obsolete duplicated Server matrix grid must be gone");
assert(sessions.includes("payload.evaluation_id=evaluationPicker.value"));
assert(sessions.includes('"/matrix"'));
assert(!campaign.includes("localStorage"),"Server campaigns must never access Demo storage");
assert(!sessions.includes("localStorage"),"Server sessions must never access Demo storage");
console.log("FUT-08/UX-R04: one shared matrix presentation; Demo plan and observations stay "+
  "distinct from Server evidence");
