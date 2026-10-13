#!/usr/bin/env node
/* UX-R03: deterministic safety and revision-navigation assertions.
 * Browser acceptance is in scripts/ux_qa.py; this test guards URL contracts. */
"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const source=fs.readFileSync("shared-context.js","utf8");
function context(path,search,protocol){
  const local=protocol==="file:";
  const location={origin:local?"null":"http://localhost",protocol:protocol||"http:",
    pathname:path||"/",search:search||"",hash:"",
    href:(local?"file://":"http://localhost")+(path||"/")+(search||"")};
  const window={location};
  vm.runInNewContext(source,{window,URL,URLSearchParams});
  return {ctx:window.AICompassContext,location};
}
{
  const {ctx,location}=context("/","?mode=server&workspace=workgroup&section=watch&q=agent");
  const target=ctx.route("server","workgroup","watch",{record:"w1",revision:"r003"});
  assert(target.startsWith("/?mode=server&workspace=workgroup&section=watch"));
  assert(target.includes("record=w1") && target.includes("revision=r003"));
  const back=new URL(target,"http://localhost").searchParams.get("from");
  assert(back.includes("q=agent"),"origin and filter lost");
  assert.equal(ctx.normalizeOrigin("https://example.com/steal","server"),null);
  assert.equal(ctx.normalizeOrigin("//example.com/","server"),null);
  assert.equal(ctx.normalizeOrigin("/?mode=demo&workspace=workgroup","server"),null);
  assert.equal(ctx.normalizeOrigin("/maintenance?mode=server","server"),"/maintenance?mode=server");
  assert.equal(ctx.normalizeOrigin("/untrusted?mode=server","server"),null);
  assert(!target.includes("https%3A"));
  location.search=new URL(target,"http://localhost").search;
  assert(ctx.returnTo("server","/")?.includes("q=agent"));
  assert(ctx.breadcrumb("server","workgroup","watch","w1","r003").includes("r003"));
  assert(ctx.route("server","engineer","results",{record:"r1"}).includes("record=r1"));
  // A Management drill-down from a later Task/configuration page must keep the
  // authorized pagination so the exact cell is still reachable on return.
  const heat=ctx.route("server","management","home",
    {profile:"wlp-1",scenario:"opp-1",row_page:"2",column_page:"1"});
  assert(heat.includes("row_page=2") && heat.includes("column_page=1"),
    "heatmap context must preserve the authorized pagination");
  assert.throws(()=>ctx.route("invalid","workgroup","watch"),/Invalid/);
  assert.throws(()=>ctx.route("server","root-admin","users"),/Invalid/);
  const record=ctx.recordDetails({id:"watch-1",name:"<script>bad</script>",
    revision:"r002",summary:"A safe technical summary",status:"published"},
    "watch","server","");
  assert(record.html.includes("&lt;script&gt;bad&lt;/script&gt;"));
  assert(!record.html.includes("<script>bad</script>"));
  assert(record.html.includes("<dl") && record.html.includes("A safe technical summary"));
  assert(record.html.includes("ux-advanced-source")&&record.raw);
  const stale=ctx.recordDetails({id:"watch-1",name:"v2",revision:"r002",
    summary:"Current not historic"},"watch","server","r001");
  assert(stale.html.includes("cannot be verified"));
  assert(!stale.html.includes("Current not historic"));
  assert.equal(stale.raw,null);
}
{
  const {ctx}=context("/prototype.html","?mode=demo&workspace=engineer");
  const run=ctx.route("demo","engineer","results",{record:"r1",revision:"r001"});
  assert(run.startsWith("/prototype.html?mode=demo"));
  assert(run.includes("record=r1"));
  assert(run.includes("workspace=engineer"),"Demo deep link must retain persona");
  assert(ctx.route("demo","workgroup","watch",{record:"w1"}).includes("workspace=workgroup"),"Demo Workgroup context must survive navigation");
  assert(!run.includes("mode=server"));
}
{
  const {ctx}=context("/home/user/ai-compass/prototype.html",
    "?mode=demo&workspace=workgroup","file:");
  const link=ctx.route("demo","workgroup","watch",{record:"w1"});
  assert(link.startsWith("?mode=demo"),"file:// Demo links must be relative");
  assert(!link.includes("http:"),"offline route attempted network use");
}
console.log("UX-R03 same-origin/mode-safe navigation, pinned revisions, structured detail: PASS");
