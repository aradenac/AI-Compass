#!/usr/bin/env node
"use strict";
/* PLAT-20: actual Server forecast UI; all predicted numbers clearly unmeasured. */
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const src=fs.readFileSync("server-forecasts.js","utf8");
const page=fs.readFileSync("prototype.html","utf8");
const server=fs.readFileSync("server-mode.js","utf8");
new vm.Script(src,{filename:"server-forecasts.js"});
new vm.Script(server,{filename:"server-mode.js"});
assert(page.includes('<script src="server-forecasts.js"></script>'));
assert(page.indexOf("server-forecasts.js")<page.indexOf("server-mode.js"));
assert(server.includes("AICompassServerForecasts.mount"));
assert(server.includes("forecasts.setAccess(false, false, false)"));
assert(server.includes('grants.includes("publication_review")'));
assert(fs.readFileSync("compose.yaml","utf8").includes(
    "./server-forecasts.js:/srv/frontend/server-forecasts.js:ro"));
assert(fs.readFileSync("staging/compose.yaml","utf8").includes(
    "../server-forecasts.js:/srv/frontend/server-forecasts.js:ro"));
assert(!src.includes("localStorage")&&!src.includes("sessionStorage"));
for(const marker of ["THEORETICAL","never measured","predicted_metrics",
    "forecast_revision:f.revision","watch_links","review_notes",
    "/campaigns","api(\"runs\")","expected_revision","csrf()",
    'credentials:"same-origin"']){
    assert(src.includes(marker),"Missing forecast UI contract: "+marker);
}
const nodes=new Map();
function find(k){
    if(!nodes.has(k))nodes.set(k,{
        value:"",innerHTML:"",textContent:"",hidden:true,listeners:{},
        addEventListener(type,callback){this.listeners[type]=callback;},
        querySelector:find,querySelectorAll(){return [];}
    });
    return nodes.get(k);
}
const root={hidden:true,innerHTML:"",querySelector:find,
    replaceChildren(){this.innerHTML="";}};
const calls=[];
const sandbox={window:{},fetch:async(url,opts)=>{
    calls.push(url);
    assert(url.startsWith("/api/v1/"));
    assert.equal(opts.credentials,"same-origin");
    assert.equal(opts.cache,"no-store");
    return {ok:true,json:async()=>({results:[]})};
}};
vm.runInNewContext(src,sandbox,{filename:"server-forecasts.js"});
const ui=sandbox.window.AICompassServerForecasts.mount(root,()=>"csrf",String);
ui.setAccess(false,false,false);
assert(root.hidden);assert.equal(calls.length,0);
ui.setAccess(true,false,false);
setImmediate(()=>{
    assert(!root.hidden);
    assert.equal(calls.length,6);
    assert(!root.innerHTML.includes("+ Draft forecast"));
    assert(find("#forecast-list").innerHTML.includes("No forecasts"));
    ui.setAccess(false,false,false);
    assert(root.hidden);
    console.log("PLAT-20: real Server Forecast UI, separated measured results, Demo isolation pass");
});
