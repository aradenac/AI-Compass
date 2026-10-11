#!/usr/bin/env node
"use strict";
/* UX-R04: shared form/detail/stepper/status primitives used by both modes. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const context={window:{},Map,Set};
vm.runInNewContext(fs.readFileSync("shared-workgroup.js","utf8"),context,
  {filename:"shared-workgroup.js"});
const ui=context.window.AICompassWorkgroup;

const DOMAINS={
  watchSource:ui.WATCH_SOURCE_FIELDS,watchEntry:ui.WATCH_ENTRY_FIELDS,
  forecast:ui.FORECAST_FIELDS,feedbackThread:ui.FEEDBACK_THREAD_FIELDS,
  feedbackReply:ui.FEEDBACK_REPLY_FIELDS,recommendation:ui.RECOMMENDATION_FIELDS,
  evaluation:ui.EVALUATION_FIELDS
};
const MODES=["demo","server"];

/* Every authorization specification is complete and stays data-attribute safe. */
for(const [domain,spec] of Object.entries(DOMAINS)) {
  assert(Array.isArray(spec)&&spec.length,"Empty field specification: "+domain);
  const keys=new Set();
  for(const entry of spec) {
    assert(entry.key&&entry.label,"Specification entry without key/label in "+domain);
    assert(!keys.has(entry.key),"Duplicate specification key "+entry.key+" in "+domain);
    keys.add(entry.key);
    for(const candidate of [entry.key,entry.demoKey,entry.serverKey].filter(Boolean))
      assert(/^[a-zA-Z][a-zA-Z0-9_-]*$/.test(candidate),
        "Unsafe field name "+candidate+" in "+domain);
    for(const mode of entry.modes||MODES)
      assert(MODES.includes(mode),"Unknown mode "+mode+" in "+domain);
    for(const kind of [entry.kind,entry.demoKind,entry.serverKind].filter(Boolean))
      assert(["text","textarea","url","number","select","multi","checkbox"].includes(kind),
        "Unknown field kind "+kind+" in "+domain);
  }
}

/* Both modes render one ordered presentation; only keys/options differ. */
function labelledFields(html) {
  return Array.from(html.matchAll(/<label for="[^"]+">([^<]*)<\/label>/g)).map(m=>m[1]);
}
for(const [domain,spec] of Object.entries(DOMAINS)) {
  const rendered={};
  for(const mode of MODES) {
    rendered[mode]=ui.renderDomainFields(spec,{},mode,{idPrefix:domain});
    for(const entry of spec) {
      const visible=!entry.modes||entry.modes.includes(mode);
      const name=String(mode==="demo"?(entry.demoKey||entry.key):(entry.serverKey||entry.key));
      const present=rendered[mode].includes('data-shared-field="'+name+'"');
      assert.equal(present,visible,domain+" field "+name+" visibility is wrong in "+mode);
    }
  }
  const demoLabels=labelledFields(rendered.demo),serverLabels=labelledFields(rendered.server);
  const sharedLabels=spec.filter(e=>!e.modes).map(e=>e.label);
  for(const label of sharedLabels) {
    assert(demoLabels.includes(label)&&serverLabels.includes(label),
      "Shared label missing in one mode: "+domain+" / "+label);
  }
  const order=sharedLabels.map(l=>demoLabels.indexOf(l));
  assert(order.every((value,index)=>index===0||value>order[index-1]),
    "Field order diverges between modes in "+domain);
}

/* Mode-specific keys keep their exact historical field names. */
const sourceDemo=ui.renderDomainFields(ui.WATCH_SOURCE_FIELDS,
  {title:"T",assessment:"A",type:"Research paper"},"demo",{idPrefix:"watch-source"});
assert(sourceDemo.includes('name="title"')&&sourceDemo.includes('name="assessment"'));
assert(!sourceDemo.includes('name="claim"')&&!sourceDemo.includes('name="published_on"'));
const sourceServer=ui.renderDomainFields(ui.WATCH_SOURCE_FIELDS,
  {name:"T",claim:"A",published_on:"2026-01-01"},"server");
assert(sourceServer.includes('name="name"')&&sourceServer.includes('name="claim"')&&
  sourceServer.includes('name="published_on"'));
assert(!sourceServer.includes('name="title"'),"Server must not use Demo key names");
assert(sourceServer.includes(" required"),"Server keeps its native required validation");
assert(!sourceDemo.includes(" required"),"Demo keeps its own validation messages");
assert(ui.renderDomainFields(ui.FEEDBACK_REPLY_FIELDS,{},"server").includes('name="body"'),
  "Feedback reply keeps the Server message body name");
assert(ui.renderDomainFields(ui.FEEDBACK_REPLY_FIELDS,{},"demo").includes('name="reply"'),
  "Feedback reply keeps the Demo reply name");
assert(ui.renderDomainFields(ui.FEEDBACK_THREAD_FIELDS,{},"server")
  .includes('placeholder="tsk-… or sol-…"'),"Server catalog reference stays a free ID input");
assert(ui.renderDomainFields(ui.RECOMMENDATION_FIELDS,{},"server").includes('name="name" type="text"'),
  "Server recommendation title stays a text input");

/* Values are escaped, locked fields never leak an editable control, and
   unknown or absent input fails closed instead of inventing a control. */
const hostile=ui.renderDomainFields(ui.WATCH_ENTRY_FIELDS,
  {name:'" onfocus="steal()',hypothesis:"<img src=x>"},"demo");
assert(!hostile.includes("<img src=x>")&&hostile.includes("&lt;img src=x&gt;"));
assert(!hostile.includes('onfocus="steal()"'));
const locked=ui.renderDomainFields(ui.FEEDBACK_REPLY_FIELDS,{visibility:"internal",reply:"x"},
  "demo",{locked:{visibility:"public"}});
assert(locked.includes('<input type="hidden" name="visibility" value="public">'));
assert(!locked.includes('name="visibility" aria')&&!locked.includes("<select"));
const chosen=ui.renderDomainFields(ui.FEEDBACK_THREAD_FIELDS,{kind:"idea"},"server",
  {choices:{kind:[["idea","Idea"]]}});
assert(chosen.includes('<option value="idea" selected>Idea</option>'));
assert(!chosen.includes("question"),"Caller choices must replace the static vocabulary");
assert.throws(()=>ui.renderDomainFields(ui.WATCH_ENTRY_FIELDS,{},null),/Explicit Demo or Server/);
assert.throws(()=>ui.renderDomainFields([{key:"k",label:"L",kind:"magic"}],{},"demo"),
  /Unsupported domain field kind/);
assert.throws(()=>ui.renderDomainFields([{label:"L"}],{},"demo"),
  /requires key and label/);
assert.throws(()=>ui.renderDomainFields(ui.WATCH_ENTRY_FIELDS,{},"demo",
  {choices:{name:"not-a-list"}}),/choices/);

/* Generic domain detail keeps identity, provenance notices and same-origin links. */
const detail=ui.renderDomainDetail({title:"Driver decision",identity:["rec-1","r002"],
  sections:[{label:"Rationale",value:"Measured & documented"},{label:"Empty",value:""}],
  notices:["Held by the author until review."],
  links:[{href:"/results/rec-1",label:"Open measured Runs"}]},{mode:"server",domain:"recommendations"});
assert(detail.includes('data-shared-domain-detail="recommendations"'));
assert(detail.includes("Driver decision")&&detail.includes("Measured &amp; documented"));
assert(!detail.includes("<h4>Empty</h4>"),"Empty sections must not be rendered");
assert(detail.includes('href="/results/rec-1"'));
assert.throws(()=>ui.renderDomainDetail({title:""},{mode:"demo",domain:"feedback"}),
  /requires a title/);
assert.throws(()=>ui.renderDomainDetail({title:"x"},{mode:"demo",domain:"Feedback"}),/domain/);
assert.throws(()=>ui.renderDomainDetail({title:"x",links:[{href:"https://evil.example"}]},
  {mode:"server",domain:"feedback"}),/same-origin/);

/* One campaign lifecycle presentation, mapped by each mode. */
const mid=ui.campaignLifecycleSteps("in_progress");
assert.equal(mid.map(s=>s.state).join(","),"done,current,todo,todo");
assert.equal(ui.campaignLifecycleSteps("published").every(s=>s.state!=="todo"),true);
assert.throws(()=>ui.campaignLifecycleSteps("active"),/Unsupported campaign lifecycle status/);
const stepper=ui.renderStepper(ui.campaignLifecycleSteps("under_review"),
  {mode:"demo",domain:"campaign"});
assert(stepper.includes('data-shared-stepper="campaign"')&&stepper.includes('data-stepper-mode="demo"'));
assert.equal((stepper.match(/data-step-state=/g)||[]).length,4);
assert.throws(()=>ui.renderStepper([{label:"x",state:"almost"}],{mode:"demo",domain:"campaign"}),
  /Unsupported stepper state/);
assert.throws(()=>ui.renderStepper([],{mode:"demo",domain:"campaign"}),/steps required/);

/* Shared loading/error/denied presentation. */
assert(ui.renderDomainStatus({mode:"demo",state:"loading",message:"Loading fictional Demo…"})
  .includes('role="status"'));
assert(ui.renderDomainStatus({mode:"server",state:"denied",message:"No grant"})
  .includes('role="alert"')&&ui.renderDomainStatus({mode:"server",state:"error",message:"<boom>"})
  .includes("&lt;boom&gt;"));
assert.throws(()=>ui.renderDomainStatus({mode:"server",state:"exploded"}),/Unsupported status state/);

/* Both modes must consume these primitives; duplicated local primitives stay gone. */
const page=fs.readFileSync("prototype.html","utf8");
const servers={
  "server-watch.js":["WATCH_SOURCE_FIELDS","WATCH_ENTRY_FIELDS"],
  "server-forecasts.js":["FORECAST_FIELDS"],
  "server-discussions.js":["FEEDBACK_THREAD_FIELDS","FEEDBACK_REPLY_FIELDS"],
  "server-recommendations.js":["RECOMMENDATION_FIELDS"],
  "server-results.js":["EVALUATION_FIELDS"],
  "server-campaigns.js":["renderCampaignMatrix","renderStepper"]
};
assert(page.includes("renderDomainFields(")&&page.includes("renderStepper("));
for(const [file,markers] of Object.entries(servers)) {
  const source=fs.readFileSync(file,"utf8");
  for(const marker of markers)
    assert(source.includes(marker),file+" must use the shared "+marker);
  assert(source.includes("renderDomainStatus("),file+" must use the shared status presentation");
}
assert(!fs.readFileSync("server-watch.js","utf8").includes("function formRow("),
  "Server Watch must not keep its own duplicate field primitive");
assert(!fs.readFileSync("server-recommendations.js","utf8").includes("  function field("),
  "Server Recommendations must not keep its own duplicate field primitive");
assert(!page.includes('field("hypothesis","Reasoned hypothesis'),
  "Demo Watch must render its fields through the shared specification");
console.log("UX-R04 shared domain primitives: Demo/Server field parity, escaping, "+
  "locked fields, lifecycle stepper and fail-closed input PASS");
