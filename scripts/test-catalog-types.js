#!/usr/bin/env node
/* PLAT-06: source-level mode contract plus typed adapter and shared lane smoke. */
"use strict";
const fs = require("fs");
const vm = require("vm");
const assert = require("node:assert/strict");

async function main() {
  const db = {"model": [], "provider": [], "harness": [], "framework": []};
  const calls = [];
  let down = false;
  function resolve(url) {
    if (url.startsWith("/api/v1/models")) return ["model", url.slice("/api/v1/models".length)];
    const match = /^\/api\/v1\/catalog\/(provider|harness|framework)(.*)$/.exec(url);
    if (!match) throw Error("unregistered path: " + url);
    return [match[1], match[2]];
  }
  async function fetch(url, options) {
    calls.push({url, options});
    if (down) throw Error("network disconnected");
    const [type, path] = resolve(url);
    const rows = db[type];
    const method = options.method || "GET";
    const body = options.body ? JSON.parse(options.body) : {};
    let out, status = 200;
    if (!path && method === "GET") out = {results: rows};
    else if (!path && method === "POST") {
      const prefix = {model:"mdl",provider:"prv",harness:"hrn",framework:"frm"}[type];
      const result = {id: prefix + "-calm-blue-fox", type, name: body.name,
        properties: body.properties, revision: "r001", schema_version: 1,
        compatibility: {status: "current", read_only: false}};
      rows.push(result);out = result;status=201;
    } else if (path.endsWith("/revisions") && method === "POST") {
      const original = rows.find(x => "/" + x.id + "/revisions" === path);
      if (!original) throw Error("unknown item");
      if (original.revision !== body.expected_revision) {
        out = {error:"revision_conflict"};status=409;
      } else {
        out = {...original, name:body.name,properties:body.properties,revision:"r002"};
        rows.splice(rows.indexOf(original),1,out);status=201;
      }
    } else if (path.endsWith("/revisions") && method==="GET") {
      const found = rows.find(x => "/" + x.id + "/revisions" === path);
      out={revisions: found?[found]:[]};
    } else out=rows.find(x => "/" + x.id === path);
    return {ok:status<400,status,async json(){return out;}};
  }
  const sandbox={window:{fetch}};
  vm.runInNewContext(fs.readFileSync("model-catalog.js","utf8"),sandbox);
  const lib=sandbox.window.AICompassModels;
  for (const kind of ["provider","harness","framework"]) {
    const adapter=lib.ApiDataProvider(()=>"csrf-token",kind);
    assert.equal((await adapter.list()).length,0);
    const record=await adapter.create({name:kind,properties:{version:"1",custom:{none:null}}});
    assert.equal(record.type,kind);
    assert.equal(record.compatibility.status,"current");
    assert.equal((await adapter.list())[0].id,record.id);
    const html=lib.renderLane([record],{type:kind,canWrite:true,showRevisions:true});
    assert(html.includes('data-catalog="'+kind+'"'));
    assert(html.includes('data-act="editComponent"'));
    assert(html.includes('data-act="modelHistory"'));
    assert(html.includes('data-act="newComponentType" data-id="'+kind+'"'));
    const next=await adapter.revise(record.id,{name:kind+" new",properties:record.properties,expected_revision:"r001"});
    assert.equal(next.revision,"r002");
    assert.equal(next.properties.custom.none,null);
    await assert.rejects(adapter.revise(record.id,{name:"stale",properties:{},expected_revision:"r001"}), e=>e.status===409);
    assert.equal((await adapter.revisions(record.id)).length,1);
  }
  assert.equal(db.model.length,0);
  assert(calls.filter(x=>x.options.method==="POST").every(x=>x.options.headers["X-CSRFToken"]==="csrf-token"));
  assert(calls.every(x=>x.options.credentials==="same-origin"));
  const sample={id:"frm-calm-blue-fox",type:"framework",name:"<script>alert(1)</script>",
    properties:{process:"Agent pipeline",stages:["plan","review"]},compatibility:{status:"current",read_only:false}};
  const rendered=lib.renderLane([lib.modelFromApi(sample)],{type:"framework",showRevisions:true});
  assert(!rendered.includes("<script>"));
  assert(rendered.includes("&lt;script&gt;"));
  const viewer=lib.renderLane([sample],{type:"framework",canWrite:false});
  assert(!viewer.includes('data-act="editComponent"'));
  const demo=lib.LocalStorageDataProvider({list:()=>[{type:"framework",name:"Demo only"}],get:()=>null});
  assert(demo.list()[0].name==="Demo only");
  assert.equal(db.framework.length,1,"Demo operations must never write to backend");
  down=true;
  await assert.rejects(lib.ApiDataProvider(()=>"csrf","provider").list(),/No Demo fallback/);
  const page=fs.readFileSync("prototype.html","utf8"),server=fs.readFileSync("server-mode.js","utf8");
  assert(page.includes('demoCatalogProviders[type].list()'));
  assert(page.includes('AICompassModels.renderLane(rows,{type:type,canWrite:true})'));
  assert(server.includes('Promise.all(TYPES.map'));
  assert(server.includes('adapters[type].list()'));
  assert(server.includes('typedAdapter.create(next)'));
  assert(server.includes('typedAdapter.revise(original.id, next)'));
  assert(!/\blocalStorage\b/.test(server));
  const inline=page.match(/<script>\s*([\s\S]*?)<\/script>/);
  assert(inline);
  new vm.Script(inline[1],{filename:"prototype.html"});
  new vm.Script(server,{filename:"server-mode.js"});
  console.log("PLAT-06 all typed API providers, shared Demo/Server lanes and failures PASS");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
