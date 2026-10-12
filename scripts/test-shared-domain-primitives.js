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

/* One observation matrix: same rows/columns/counts in both modes, unknown
   comparisons explicit, and record routing validated. */
const matrixProjection={rowAxis:"Test Case",columnAxis:"AI Solution",
  columnLabels:[{key:"s1",label:"Solution A"},{key:"s2",label:"Solution B"}],
  counts:[{label:"published Run(s)",value:2}],
  policy:"observed results only",
  rows:[{key:"c1",label:"Driver challenge",detail:"Driver integration",
    rowAction:{label:"Open Test Case",attributes:{"data-act":"caseDetail","data-id":"c1"}},
    columns:[{key:"s1",observations:2,value:"94/100",hint:"2 run(s)",tone:"",
      ids:[{id:"run-1",href:"/results?record=run-1"}]}]},
   {key:"c2",label:"IRQ behaviour",columns:[{key:"s1",observations:0}]}],
  footerRow:{label:"Coverage",columns:[{key:"s1",value:"1/2 cases"}]},
  notices:["Missing comparisons are unknown, not zero."]};
const matrixHtml=ui.renderObservationMatrix(matrixProjection,{mode:"server",
  domain:"results",emptyRowText:"Not tested"});
assert(matrixHtml.includes('data-shared-observation-matrix="results"'));
assert(matrixHtml.includes('data-observation-mode="server"'));
assert(matrixHtml.includes("2 published Run(s)"));
assert.equal((matrixHtml.match(/data-observation-row=/g)||[]).length,2);
assert.equal((matrixHtml.match(/data-observation-label=/g)||[]).length,2);
assert(matrixHtml.includes("94/100")&&matrixHtml.includes("2 run(s)"));
assert(matrixHtml.includes("Not tested"),"An unobserved cell stays explicitly unknown");
assert(matrixHtml.includes('data-observation-count="0"'));
assert(matrixHtml.includes('data-observation-footer="1"')&&matrixHtml.includes("1/2 cases"));
assert(matrixHtml.includes('href="/results?record=run-1"'));
assert(matrixHtml.includes('data-act="caseDetail"'));
const demoMatrix=ui.renderObservationMatrix(matrixProjection,{mode:"demo",
  domain:"results",emptyRowText:"Not tested"});
assert.equal(demoMatrix.replace(/demo/g,"MODE"),matrixHtml.replace(/server/g,"MODE"),
  "Equivalent rows must render the same observation matrix in both modes");
const emptyMatrix=ui.renderObservationMatrix({rowAxis:"Test Case",columnAxis:"AI Solution",
  columnLabels:[],rows:[],counts:[]},{mode:"server",emptyText:"No persisted results"});
assert(emptyMatrix.includes("No persisted results")&&
  emptyMatrix.includes("data-observation-empty-matrix"));
assert.throws(()=>ui.renderObservationMatrix({rowAxis:"T",columnLabels:[],rows:[{key:"r",
  label:"R",columns:[]}]},{mode:"demo"}),/requires column labels/);
assert.throws(()=>ui.renderObservationMatrix({columnLabels:[{key:"a",label:"A"}],
  rows:[{key:"r",label:"R",columns:[{key:"missing",observations:1}]}]},{mode:"demo"}),
  /unknown column/);
assert.throws(()=>ui.renderObservationMatrix({columnLabels:[{key:"a",label:"A"}],
  rows:[{key:"r",label:"R",columns:[{key:"a",observations:"many"}]}]},{mode:"demo"}),
  /non-negative integer/);
assert.throws(()=>ui.renderObservationMatrix({columnLabels:[{key:"a",label:"A"}],
  rows:[{key:"r",label:"R",columns:[{key:"a",observations:1,ids:[{}]}]}]},{mode:"server"}),
  /stable public ID/);
assert.throws(()=>ui.renderObservationMatrix({columnLabels:[{key:"a",label:"A"}],
  rows:[{key:"r",label:"R",columns:[{key:"a",observations:1,
    ids:[{id:"x",href:"https://evil.example/x"}]}]}]},{mode:"server"}),/same-origin/);
assert.throws(()=>ui.renderObservationMatrix({columnLabels:[]},{mode:"wat"}),
  /mode required/);

/* One composed pinned-module reader: identical sections and readiness in both
   modes, only authorized sections, explicit coverage gaps and a fail-closed
   URL policy that never links an unsupported scheme. */
const composed=ui.renderComposedSetup({title:"Driver setup",revision:"r003",ready:true,
  sections:[{name:"OS baseline",revision:"r002",text:"kernel 6.6",
    url:"https://docs.example/os"},
   {name:"Toolchain",revision:"r007",url:"ftp://legacy.example/toolchain"},
   {name:"Runtime",revision:"r011",text:"no link"}],
  missing:[]},{mode:"server",domain:"guides"});
assert(composed.includes('data-shared-composed-setup="guides"'));
assert(composed.includes('data-composed-mode="server"')&&composed.includes('data-composed-ready="true"'));
assert(composed.includes("Composed setup · Driver setup · r003"));
assert(composed.includes("All declared modules are applicable for this configuration."));
assert(composed.includes("No declared coverage gap reported by the source."));
assert.equal((composed.match(/data-shared-composed-section|shared-composed-section/g)||[]).length,3);
assert(composed.includes('href="https://docs.example/os"'));
assert(composed.includes("Unsupported URL — link withheld."),
  "An unsupported scheme must never become a link");
assert(!composed.includes("ftp://legacy.example/toolchain<"),"The withheld URL must not be linked");
assert(composed.includes("Revision-pinned preview"),
  "The standing applicability notice must survive composition");
const incomplete=ui.renderComposedSetup({title:"Driver setup",ready:false,
  sections:[{name:"OS baseline",revision:"r002"}],
  missing:["Runtime <unpinned>","OS baseline r009"]},{mode:"demo",domain:"guides"});
assert(incomplete.includes('data-composed-ready="false"'));
assert(incomplete.includes("Incomplete or ambiguous recipe"));
assert(incomplete.includes("Missing coverage: Runtime &lt;unpinned&gt;; OS baseline r009"),
  "Every declared coverage gap must be listed and escaped");
assert(!incomplete.includes("Runtime <unpinned>"));
const composedDemo=ui.renderComposedSetup({title:"Driver setup",revision:"r003",ready:false,
  sections:[{name:"OS baseline",revision:"r002",text:"kernel 6.6"}],
  missing:["Runtime r999"]},{mode:"demo",domain:"guides"});
const composedServer=ui.renderComposedSetup({title:"Driver setup",revision:"r003",ready:false,
  sections:[{name:"OS baseline",revision:"r002",text:"kernel 6.6"}],
  missing:["Runtime r999"]},{mode:"server",domain:"guides"});
assert.equal(composedDemo.replace(/demo/g,"MODE"),composedServer.replace(/server/g,"MODE"),
  "Equivalent composed setups must render the same reader in both modes");
const emptyComposed=ui.renderComposedSetup({title:"Empty",sections:[{}],missing:[]},
  {mode:"server",domain:"guides"});
assert(!emptyComposed.includes("shared-composed-section"),
  "A section with no name/revision/text must not render an empty block");
assert.throws(()=>ui.renderComposedSetup({sections:[]},{mode:"server"}),
  /source record title/);
assert.throws(()=>ui.renderComposedSetup({title:"x",sections:{}},{mode:"server"}),
  /sections must be a list/);
assert.throws(()=>ui.renderComposedSetup({title:"x",missing:"gap"},{mode:"server"}),
  /gaps must be a list/);
assert.throws(()=>ui.renderComposedSetup(null,{mode:"server"}),/projection required/);
assert.throws(()=>ui.renderComposedSetup({title:"x"},{mode:null}),/Explicit Demo or Server/);

/* Numeric metrics keep the historical Demo field contract: fractions are
   valid and negative measurements are refused (review regression). */
const numeric=ui.renderDomainFields(ui.FORECAST_FIELDS,{aiCost:"0.50",humanMinutes:"12.5"},'demo');
for(const name of ["aiCost","humanMinutes"]) {
  const rendered=numeric.match(new RegExp('name="'+name+'"[^>]*'))[0];
  assert(rendered.includes('type="number"'),name+" must stay a number input");
  assert(rendered.includes('step="any"'),name+" must accept fractional values");
  assert(rendered.includes('min="0"'),name+" must refuse negative measurements");
}
const bounded=ui.renderDomainFields([{key:"ratio",label:"Ratio",kind:"number",min:0,max:1,step:"0.1"}],
  {ratio:"0.5"},"demo");
assert(bounded.includes('step="0.1"')&&bounded.includes('min="0"')&&bounded.includes('max="1"'),
  "Explicit numeric bounds must override the defaults");
assert(ui.renderDomainFields([{key:"offset",label:"Offset",kind:"number",min:-5}],{},"server")
  .includes('min="-5"'),"An explicit negative bound must be preserved");

/* One discussion-thread presentation for Demo and Server. */
const thread=ui.renderThread([
  {id:"msg-1",author:"Author & <b>",at:"2026-10-11T09:00",revision:"r002",
   visibility:"internal",body:"<script>alert(1)</script>"},
  {id:"msg-2",author:"Reader",visibility:"public",body:"Public reply",
   attachments:[{href:"/api/v1/discussions/messages/msg-2/attachments/1",
     filename:"evidence.pdf",sha256:"abc123"}]}
],{mode:"server",emptyText:"No message yet.",
   actions:message=>[{label:"Reply",attributes:{"data-message":message.id,"data-action":"reply"}}]});
assert(thread.includes('data-shared-thread="server"'));
assert.equal((thread.match(/data-message-id=/g)||[]).length,2);
assert(thread.includes('data-message-visibility="internal"'));
assert(!thread.includes("<script>alert(1)</script>")&&thread.includes("&lt;script&gt;"));
assert(thread.includes("Author &amp; &lt;b&gt;"));
assert(thread.includes("SHA-256 abc123")&&thread.includes('href="/api/v1/discussions/messages/msg-2/attachments/1"'));
assert(thread.includes('data-action="reply"'));
assert(ui.renderThread([],{mode:"demo",emptyText:"No replies yet."}).includes("No replies yet."));
assert.throws(()=>ui.renderThread([{id:"x",visibility:"secret"}],{mode:"server"}),
  /Unsupported thread message visibility/);
assert.throws(()=>ui.renderThread([{}],{mode:"server"}),/stable ID/);
assert.throws(()=>ui.renderThread([{id:"x",attachments:[{filename:"a.pdf"}]}],{mode:"server"}),
  /immutable location/);
assert.throws(()=>ui.renderThread([{id:"x",attachments:[{href:"https://evil.example/a"}]}],
  {mode:"demo"}),/same-origin/);
assert.throws(()=>ui.renderThread([{id:"x"}],{mode:"server",actions:()=>({})}),
  /Invalid thread message actions/);

/* One measured-Run presentation: provenance marker, recorded metrics only,
   and an explicit refusal to substitute a pinned original. */
const measured=ui.renderMeasuredRunDetail({id:"run-1",kind:"individual",revision:"r004",
  outcome:"DoD accepted",title:"Driver challenge",taskName:"Driver integration",
  testCaseName:"Driver challenge",testCaseRevision:"r002",
  metrics:[{label:"Quality /100",value:94,hint:"rubric"},
    {label:"Cost EUR",value:null},{label:"Human time (minutes)",value:""}]},{mode:"server"});
assert(measured.includes('data-run-provenance="measured"'));
assert(measured.includes("MEASURED RUN")&&!measured.includes("THEORETICAL"));
assert(measured.includes("<strong>94</strong>"));
assert(!measured.includes("Cost EUR")&&!measured.includes("Human time"),
  "Unknown metrics must stay unknown, never rendered as zero");
assert(measured.includes("pinned r002"));
const theoretical=ui.renderMeasuredRunDetail({id:"forecast-1",kind:"theoretical",
  status:"staged",title:"Projected setup"},{mode:"demo"});
assert(theoretical.includes('data-run-provenance="theoretical"'));
assert(theoretical.includes("THEORETICAL")&&theoretical.includes("never measured"));
const mismatched=ui.renderMeasuredRunDetail({id:"run-1",kind:"individual",revision:"r004",
  outcome:"DoD accepted",title:"Run",metrics:[{label:"Quality /100",value:94}]},
  {mode:"server",pinnedRevision:"r999"});
assert(mismatched.includes("data-run-pin-mismatch"));
assert(!mismatched.includes("<strong>94</strong>"),
  "A mismatched pinned revision must not show current metrics");
assert.throws(()=>ui.renderMeasuredRunDetail({id:"x",kind:"wat"},{mode:"demo"}),
  /Unsupported Run kind/);
assert.throws(()=>ui.renderMeasuredRunDetail({},{mode:"demo"}),/stable public ID/);
assert.throws(()=>ui.renderMeasuredRunDetail({id:"x",metrics:{}},{mode:"demo"}),
  /metrics must be a list/);
assert.throws(()=>ui.renderMeasuredRunDetail({id:"x",links:[{href:"https://evil.example"}]},
  {mode:"server"}),/same-origin/);

/* Descriptor-driven step fields and the unbounded numeric opt-out. */
assert.equal(ui.renderDomainFields([{key:"m",label:"M",kind:"number",min:null}],
  {m:"-3"},"server").includes("min="),false,
  "min:null must leave a descriptor-driven measurement unbounded");
assert(ui.renderDomainFields([{key:"m",label:"M",kind:"number"}],{},"server")
  .includes('min="0"'),"metrics keep their non-negative default");
assert(ui.renderDomainFields([{key:"flag",label:"Flag",kind:"checkbox"}],{flag:true},"server")
  .includes("checked"),"a boolean descriptor field stays a checked checkbox");
const sessionSource=fs.readFileSync("server-sessions.js","utf8");
assert(sessionSource.includes("renderDomainFields(")&&
  !sessionSource.includes("data-step-field"),
  "Server step fields must use the shared field primitive");
assert.equal(typeof ui.LIFECYCLE_ACTION_LABELS.recommendations,"object");
assert.equal(ui.LIFECYCLE_ACTION_LABELS.recommendations.unpublish,"Withdraw publication");
const recommendationSource=fs.readFileSync("server-recommendations.js","utf8");
for(const key of ["submit","publish","unpublish","revise","history"])
  assert(recommendationSource.includes("lifecycle."+key),
    "Recommendation "+key+" must use the canonical shared wording");

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

/* One review/publication action bar with canonical labels in both modes. */
const reviewBar=ui.renderLifecycleActions([
  {key:"review",attributes:{"data-stage-action":"review"}},
  {key:"rework",attributes:{"data-stage-action":"rework"}}
],{mode:"server",domain:"forecasts",notice:"Current staged"});
assert(reviewBar.includes('data-shared-lifecycle="forecasts"'));
assert(reviewBar.includes(">Mark reviewed</button>")&&reviewBar.includes(">Request rework</button>"));
assert(reviewBar.includes("Current staged"));
assert(ui.renderLifecycleActions([],{mode:"demo",domain:"forecasts",emptyText:"None permitted"})
  .includes("None permitted"));
assert(ui.renderLifecycleActions([{key:"stage",attributes:{"data-act":"stageForecast"}}],
  {mode:"demo",domain:"forecasts"}).includes(">Stage forecast</button>"));
assert.throws(()=>ui.renderLifecycleActions([{key:"invent",attributes:{"data-act":"x"}}],
  {mode:"demo",domain:"forecasts"}),/Unknown lifecycle action key/);
assert.throws(()=>ui.renderLifecycleActions([{attributes:{}}],{mode:"demo",domain:"forecasts"}),
  /requires its exact key/);
assert.throws(()=>ui.renderLifecycleActions([{key:"stage",attributes:{onclick:"x"}}],
  {mode:"demo",domain:"forecasts"}),/Invalid matrix attribute/);
assert.throws(()=>ui.renderLifecycleActions([],{mode:"demo",domain:"Forecasts"}),/lifecycle domain/);

/* Campaign transitions and labels are offered identically in both modes. */
assert.equal(ui.campaignLifecycleActionKeys("planned").join(","),"start,archive");
assert.equal(ui.campaignLifecycleActionKeys("in_progress").join(","),
  "close,close_partial,archive");
assert.equal(ui.campaignLifecycleActionKeys("under_review").join(","),
  "rework,publish,reopen,archive");
assert.equal(ui.campaignLifecycleActionKeys("published").join(","),"unpublish,reopen,archive");
assert.equal(ui.campaignLifecycleActionKeys("archived").join(","),"restore");
assert.throws(()=>ui.campaignLifecycleActionKeys("active"),/Unsupported campaign lifecycle status/);
const campaignKeys=ui.campaignLifecycleActionKeys("in_progress");
const campaignLabels=campaignKeys.map(key=>ui.LIFECYCLE_ACTION_LABELS.campaigns[key]);
assert(campaignLabels.includes("Close full plan")&&campaignLabels.includes("Archive campaign"),
  "Campaign transitions must keep their canonical labels");
const demoBar=ui.renderLifecycleActions(campaignKeys.map(key=>({key:key,
  attributes:{"data-act":key}})),{mode:"demo",domain:"campaigns"});
const serverBar=ui.renderLifecycleActions(campaignKeys.map(key=>({key:key,
  attributes:{"data-action":key}})),{mode:"server",domain:"campaigns"});
for(const label of campaignLabels) {
  assert(demoBar.includes(label)&&serverBar.includes(label),
    "Campaign label missing in one mode: "+label);
}
assert(demoBar.indexOf("Close full plan")<demoBar.indexOf("Archive campaign"),
  "Offered transitions must keep the same order in both modes");
assert(!demoBar.includes("Request rework"),"Offered transitions must match the status");
assert.throws(()=>ui.renderLifecycleActions([{key:"start",attributes:{"data-act":"x"}}],
  {mode:"demo",domain:"watch"}),/Unknown lifecycle domain labels/);

/* Drift guard: the offered action label must carry the exact canonical wording
   pinned here (not merely agree with the frozen object it was read from), and
   no mode can offer a key outside that vocabulary — the wording drift already
   flagged in server-recommendations.js must never reappear. */
const PINNED_LIFECYCLE_LABELS={
  forecasts:{stage:"Stage forecast",review:"Mark reviewed",publish:"Publish as theoretical",
    unpublish:"Unpublish",rework:"Request rework",fork:"Create new revision"},
  recommendations:{submit:"Submit for review",publish:"Review and publish",
    unpublish:"Withdraw publication",revise:"New draft revision",history:"Original history / evidence"},
  campaigns:{start:"Start / open campaign",close:"Close full plan",
    close_partial:"Close partial review",rework:"Request rework",
    publish:"Review / publish selected Runs",reopen:"Reopen",
    unpublish:"Unpublish to review",archive:"Archive campaign",restore:"Restore archive"}
};
for(const [domain,vocab] of Object.entries(PINNED_LIFECYCLE_LABELS)) {
  assert.equal(Object.keys(ui.LIFECYCLE_ACTION_LABELS[domain]).sort().join(","),
    Object.keys(vocab).sort().join(","), domain+" lifecycle vocabulary drifted");
  for(const [key,label] of Object.entries(vocab)) {
    assert.equal(ui.LIFECYCLE_ACTION_LABELS[domain][key],label,
      domain+"."+key+" canonical wording drifted from '"+label+"'");
    const rendered=ui.renderLifecycleActions([{key:key,attributes:{"data-action":key}}],
      {mode:"server",domain:domain});
    assert(rendered.includes(">"+label+"</button>"),"Offered "+domain+" "+key+
      " must render its canonical wording '"+label+"'");
    assert(rendered.includes('data-action="'+key+'"'),
      "Offered "+domain+" action "+key+" must keep its delegated attribute");
    assert(!rendered.includes(">Submit</button>")||domain!=="recommendations"||key==="submit",
      "A drifted Recommendation wording must not be offered");
  }
  assert.throws(()=>ui.renderLifecycleActions([{key:"invented_action",attributes:{}}],
    {mode:"server",domain:domain}),/Unknown lifecycle action key/,
    domain+" must refuse a lifecycle key outside the frozen vocabulary");
}
const recommendationSource2=fs.readFileSync("server-recommendations.js","utf8");
assert(!/"(Submit|Publish|Withdraw|New draft|Original history)/.test(recommendationSource2),
  "Server Recommendations must not hard-code lifecycle wording instead of the shared labels");

/* One revision-history reader: every retained revision, its superseded wording
   and its reason, immutable and escaped, identical in both modes. */
const revisions=[
  {revision:"r001",by:"ana",at:"2026-10-11T09:00",visibility:"public",
   body:"Original <script>alert(1)</script> wording",reason:""},
  {revision:"r002",by:"ana",at:"2026-10-11T10:00",visibility:"internal",
   body:"Corrected wording",reason:"Tone & <scope>"}
];
const historyHtml=ui.renderRevisionHistory(revisions,{mode:"server",domain:"discussions",
  heading:"Immutable message history · msg-1"});
assert(historyHtml.includes('data-shared-revision-history="discussions"'));
assert(historyHtml.includes('data-revision-mode="server"'));
assert(historyHtml.includes("Immutable message history · msg-1"));
assert.equal((historyHtml.match(/data-shared-revision=/g)||[]).length,2,
  "Every retained revision must stay in the history");
assert(historyHtml.includes('data-shared-revision="r001"')&&historyHtml.includes("Original"));
assert(!historyHtml.includes("<script>alert(1)</script>")&&historyHtml.includes("&lt;script&gt;"));
assert(historyHtml.includes("Tone &amp; &lt;scope&gt;"),"The correction reason must be escaped");
assert(historyHtml.includes("Reason: Original message"),
  "A revision without a reason keeps the explicit original-message default");
assert(historyHtml.includes('data-revision-visibility="internal"'));
const historyDemo=ui.renderRevisionHistory(revisions,{mode:"demo",domain:"discussions"});
const historyServer=ui.renderRevisionHistory(revisions,{mode:"server",domain:"discussions"});
assert.equal(historyDemo.replace(/demo/g,"MODE"),historyServer.replace(/server/g,"MODE"),
  "Equivalent revisions must render the same reader in both modes");
assert(ui.renderRevisionHistory([],{mode:"demo",emptyText:"No revision retained."})
  .includes("No revision retained."));
const historyNote=ui.renderRevisionHistory(revisions,{mode:"server",domain:"discussions",
  notice:"Historical revisions are never rewritten."});
assert(historyNote.includes("Historical revisions are never rewritten."));
assert.throws(()=>ui.renderRevisionHistory([{revision:""}],{mode:"server"}),
  /exact revision/);
assert.throws(()=>ui.renderRevisionHistory([{revision:"r1",visibility:"secret"}],{mode:"server"}),
  /Unsupported revision visibility/);
assert.throws(()=>ui.renderRevisionHistory("nope",{mode:"server"}),/history required/);
assert.throws(()=>ui.renderRevisionHistory([],{mode:null}),/Explicit Demo or Server/);

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
  "server-discussions.js":["FEEDBACK_THREAD_FIELDS","FEEDBACK_REPLY_FIELDS","renderThread(",
    "renderRevisionHistory("],
  "server-recommendations.js":["RECOMMENDATION_FIELDS"],
  "server-results.js":["EVALUATION_FIELDS","renderMeasuredRunDetail(","renderObservationMatrix("],
  "server-guides.js":["GUIDE_RECIPE_FIELDS"],
  "server-sessions.js":["renderStepper("],
  "server-campaigns.js":["renderCampaignMatrix","renderStepper","campaignLifecycleBar","renderLifecycleActions("],
  "server-forecasts.js":["FORECAST_FIELDS","renderLifecycleActions("],
  "server-tasks.js":["renderDomainStatus("]
};
assert(page.includes("renderDomainFields(")&&page.includes("renderStepper(")&&
  page.includes("renderThread(")&&page.includes("renderLifecycleActions(")&&
  page.includes("renderObservationMatrix(")&&page.includes("renderMeasuredRunDetail(")&&
  page.includes('domain:"campaigns"'),
  "Demo must use the shared form, stepper, thread and campaign lifecycle primitives");
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
