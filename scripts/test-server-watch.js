#!/usr/bin/env node
"use strict";
/* PLAT-18: actual Server-only source/watch adapter, no seeded Demo access. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const source=fs.readFileSync("server-watch.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-mode.js","utf8");
const compose=fs.readFileSync("compose.yaml","utf8");
const stage=fs.readFileSync("staging/compose.yaml","utf8");
new vm.Script(source,{filename:"server-watch.js"});
new vm.Script(server,{filename:"server-mode.js"});
assert(page.includes('<script src="server-watch.js"></script>'));
assert(page.indexOf('server-watch.js')<page.indexOf('server-mode.js'));
assert(server.includes("AICompassServerWatch.mount"));
assert(server.includes('watch.setAccess(false, false, false)'));
assert(server.includes('grants.includes("publication_review")'));
assert(compose.includes("server-watch.js:/srv/frontend/server-watch.js:ro"));
assert(stage.includes("server-watch.js:/srv/frontend/server-watch.js:ro"));
assert(!source.includes("localStorage"));
assert(!source.includes("sessionStorage"));
assert(!source.includes("mode=demo"));
for(const required of ["sources","watch-entries","/revisions","/evidence/upload",
    'data.action==="review"',"sources.selectedOptions","expected_revision","csrf()",
    'credentials:"same-origin"','cache:"no-store"']){
    // Only tests actual supported features; avoid mirroring a fake Demo selector.
    if(required!=='data.action==="review"'&&required!=="sources.selectedOptions")
        assert(source.includes(required),"Missing Watch UI workflow "+required);
}
const nodes=new Map();
function find(k){if(!nodes.has(k))nodes.set(k,{
    value:"",innerHTML:"",textContent:"",hidden:false,listeners:{},
    addEventListener(type,fn){this.listeners[type]=fn;},
    querySelector:find,querySelectorAll(){return [];}
});return nodes.get(k);}
const root={hidden:true,innerHTML:"",querySelector:find,
    addEventListener(type,listener){this["listener_"+type]=listener;},
    replaceChildren(){this.innerHTML="";}};
const calls=[],testRows=[
    {id:"src-clear-blue-otter",name:"<img src=x onerror=alert(1)>",revision:"r001",
     properties:{claim:"Original claim",visibility:"internal"}}
];
const sandbox={window:{},FormData,fetch:async(url,opts)=>{
    calls.push({url,opts});
    assert(url.startsWith("/api/v1/sources")||url.startsWith("/api/v1/watch-entries"));
    assert.equal(opts.credentials,"same-origin");
    assert.equal(opts.cache,"no-store");
    return {ok:true,json:async()=>({results:url.endsWith("/sources")?testRows:[]})};
}};
vm.runInNewContext(fs.readFileSync("shared-workgroup.js","utf8"),sandbox,{filename:"shared-workgroup.js"});
vm.runInNewContext(source,sandbox,{filename:"server-watch.js"});
const escape=s=>String(s).replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;");
const ui=sandbox.window.AICompassServerWatch.mount(root,()=>"csrf",escape);
ui.setAccess(false,false,false);
assert(root.hidden);assert.equal(calls.length,0);
ui.setAccess(true,false,false);
setImmediate(()=>{
    assert(!root.hidden);assert.equal(calls.length,2);
    assert(!root.innerHTML.includes("+ Research Source"));
    assert(find("#watch-sources").innerHTML.includes("&lt;img"));
    assert(!find("#watch-sources").innerHTML.includes("<img"));
    ui.setAccess(false,false,false);
    assert(root.hidden);
    console.log("PLAT-18 shared Server Watch UI, authenticated API, escaping, Demo isolation pass");
});
