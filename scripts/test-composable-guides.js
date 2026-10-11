#!/usr/bin/env node
"use strict";
/* FUT-07: offline Demo guide history, private revisions and composition plumbing. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const html=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-guides.js","utf8");
const campaign=fs.readFileSync("server-campaigns.js","utf8");
const sessions=fs.readFileSync("server-sessions.js","utf8");
for(const [path,script] of [["server-guides.js",server],
  ["server-campaigns.js",campaign],["server-sessions.js",sessions]]){
  new vm.Script(script,{filename:path});
}
const start=html.indexOf("function demoGuideRevision(id,number){");
const end=html.indexOf("function detailsGuide(id){",start);
assert(start>=0&&end>start,"Demo guide resolver must exist");
const code=html.slice(start,end);
const db={guides:[
  {id:"g-core",title:"Corrected module",status:"published",body:"NEW"},
  {id:"g-recipe",title:"Full recipe",status:"published",body:"End-to-end",recipe:{
    modules:[{id:"g-core",revision:"r001"},{id:"g-core",revision:"r001"}]}}
],revisions:[{type:"Guide",objectId:"g-core",
  before:{id:"g-core",title:"Original module",status:"published",body:"ORIGINAL"}}]};
const sandbox={db,rec:(type,id)=>db[type]?.find(x=>x.id===id),
  E:s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;")
      .replaceAll(">","&gt;"),canEdit:()=>false,
  validSetupUrl:url=>String(url).startsWith("https://")};
vm.runInNewContext(code,sandbox,{filename:"demo-composition.js"});
assert.equal(sandbox.demoGuideRevision("g-core","r001").body,"ORIGINAL");
assert.equal(sandbox.demoGuideRevision("g-core","r002").body,"NEW");
assert.equal(sandbox.demoGuideRevision("g-core","r003"),null);
const result=sandbox.demoComposedGuide(db.guides[1]);
assert(result.includes("ORIGINAL"),"Original immutable revision should be rendered");
assert(!result.includes("NEW"),"Current module cannot overwrite historical steps");
assert.equal(result.split("Original module").length,2,"Repeated shared sections must deduplicate");
db.guides[0].status="draft";db.revisions[0].before.status="draft";
assert(!sandbox.demoComposedGuide(db.guides[1]).includes("ORIGINAL"),
  "Unpublished module instructions must not be exposed to public reader");
assert(server.includes("GUIDE_RECIPE_FIELDS"),
  "Server guides must edit recipes through the shared field specification");
assert(fs.readFileSync("shared-workgroup.js","utf8").includes('key:"recipe_spec"'),
  "The shared recipe field must stay declared for both renderers");
assert(server.includes('"/render","POST"'),"Server guide renderer must query pinned API");
assert(campaign.includes("guide_modules"),"Campaign must capture reusable pinned modules");
assert(campaign.includes('api("guides/render","POST"'),"Campaign must offer preview");
assert(sessions.includes('"/guide"'),"Run must render its frozen guide");
assert(!server.includes("localStorage"),"Server guides must not use Demo storage");
console.log("FUT-07: offline immutable Demo modules, dedupe, public isolation and Server integration passed");
