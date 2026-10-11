#!/usr/bin/env node
"use strict";
/* FUT-08: fake offline Demo matrix semantics and Server view integration. */
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
const db={campaignTrials:[],runs:[]};
const sandbox={db,rec:(kind,id)=>{
  if(kind==="tasks")return {id,name:"Driver task"};
  if(kind==="cases")return {id,title:"TC1"};
  return null;
},E:s=>String(s),badge:s=>String(s),btn:()=>"",
 canEdit:()=>false};
vm.runInNewContext(code,sandbox,{filename:"demo-campaign-matrix.js"});
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[0]).state,"pending");
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[1]).state,"waived");
assert(sandbox.demoMatrixMarkup(campaignData).includes("Pending: 1"));
assert(sandbox.demoMatrixMarkup(campaignData).includes("Waived: 1"));
db.campaignTrials.push({campaign:"cmp-demo",evaluationId:"ev-a",status:"in_progress"});
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[0]).state,"in_progress");
db.runs.push({campaignId:"cmp-demo",accepted:false,
  initialSetup:{evaluationId:"ev-a"},outcome:"failed"});
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[0]).state,"evaluated");
assert.equal(sandbox.demoMatrixStatus(campaignData,campaignData.matrixPlan.cells[1]).state,"waived");
assert(campaign.includes('api("campaigns/"+encodeURIComponent(row.id)+"/matrix"'));
assert(campaign.includes('"/matrix/edit"'));
assert(campaign.includes('data-matrix-decision'));
assert(sessions.includes("payload.evaluation_id=evaluationPicker.value"));
assert(sessions.includes('"/matrix"'));
assert(!campaign.includes("localStorage"),"Server campaigns must never access Demo storage");
assert(!sessions.includes("localStorage"),"Server sessions must never access Demo storage");
console.log("FUT-08: Demo plan/observations are distinct; Server matrix UI and Run link present");
