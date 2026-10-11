#!/usr/bin/env node
"use strict";
/* UX-R04: common Test Design projection and safe mode-specific actions. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const shared=fs.readFileSync("shared-workgroup.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-test-cases.js","utf8");
const context={window:{},Map,Set};
vm.runInNewContext(shared,context,{filename:"shared-workgroup.js"});
const render=context.window.AICompassWorkgroup.renderCases;
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
console.log("UX-R04 shared Test Design tree: Demo, Server, forks, roles, escaping PASS");
