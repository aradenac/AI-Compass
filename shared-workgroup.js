/* FUT-04: one shared, categorized Workgroup map + mode-neutral knowledge summaries.
 * This is navigation, NEVER a synthetic task queue or a second data store. */
(function (root) {
  "use strict";
  var ZONES = Object.freeze([
    {name:"Sources & Référentiels", blocks:[
      ["feedback","Needs & Feedback","needs and chronological discussions"],
      ["watch","Technology Watch","provenance and signals"],
      ["catalog","Technology Catalog","Models, Providers, Harnesses, Frameworks"]]},
    {name:"Formalisation & Études",blocks:[
      ["tasks","Tasks","versioned engineering taxonomy"],
      ["testdesign","Test Design","reusable Test Cases and forks"],
      ["forecasts","Theoretical Forecasts","hypotheses, not measured Runs"]]},
    {name:"Expérimentation & Analyse",blocks:[
      ["benchmark","Benchmark Workspace","Campaigns and owned sessions"],
      ["results","Results Explorer","measured evidence only"]]},
    {name:"Capitalisation & Décision",blocks:[
      ["recommendations","AI Solutions & Recommendations","evidence-grounded editorial context"],
      ["guides","Guides & Charter","documentation and reproducibility"],
      ["opportunities","Profitability & Opportunities","authorized projections"]]},
    {name:"Mise à disposition",blocks:[
      ["deployment","Deployment & Resources","authorized planning"],
      ["engineer","Engineer Workspace","published guidance and discovery"]]}
  ]);
  var CORE = ["catalog","tasks","testdesign","benchmark","results"];
  var SECTION_TO_DEMO = Object.freeze({feedback:"feedback",watch:"watch",catalog:"solutions",
    tasks:"tasks",testdesign:"testdesign",forecasts:"watch",benchmark:"benchmark",
    results:"results",recommendations:"recommendations",guides:"knowledge",
    opportunities:"management",deployment:"management",engineer:"tasks",activity:"activity",
    updates:"updates"});
  var SECTION_TO_SERVER = Object.freeze({feedback:"server-discussions",watch:"server-watch",
    catalog:"server-model-catalog",tasks:"server-task-tree",testdesign:"server-test-cases",
    forecasts:"server-forecasts",benchmark:"server-campaigns",results:"server-results",
    recommendations:"server-recommendations",guides:"server-guides",
    opportunities:"server-planning",deployment:"server-planning",engineer:"server-engineer",
    activity:"server-activity",updates:"server-updates"});
  var STABLE = Object.freeze({
    feedback:{api:"discussions",local:"feedback",title:"Feedback & Discussions"},
    watch:{api:"watch-entries",local:"watch",title:"Technology Watch"},
    testdesign:{api:"test-cases",local:"cases",title:"Test Design"},
    forecasts:{api:"forecasts",local:"proposals",title:"Theoretical Forecasts"},
    guides:{api:"guides",local:"guides",title:"Guides & Charter"},
    activity:{api:"activity",local:"events",title:"Activity Feed"}
  });
  function escape(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g,function(char){
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char];
    });
  }
  function canVisit(section, grants, mode, canWrite) {
    if (!SECTION_TO_SERVER[section]) return false;
    if (mode === "demo") {
      return !["testdesign","benchmark","opportunities","deployment"].includes(section) || !!canWrite;
    }
    grants = grants || [];
    if (["opportunities","deployment"].includes(section))return grants.includes("planning_view");
    if (section === "activity")return grants.includes("business_read")||grants.includes("users_manage");
    if (section === "updates")return grants.includes("business_read");
    return grants.includes("business_read");
  }
  function href(mode, section, identity) {
    return root.AICompassContext.route(mode,"workgroup",section);
  }
  // A count is displayed ONLY for the explicit lifecycle states whose exit
  // is modeled. Failed/denied data means NO count, not zero or a fabricated ToDo.
  function attention(section, rows) {
    if (!Array.isArray(rows))return null;
    var states={benchmark:["under_review"],forecasts:["staged"],recommendations:["in_review","review_needed"]};
    if (!states[section])return null;
    var n=rows.filter(function(x){return !x.archived && states[section].includes(x.status);}).length;
    return n>0?n:null;
  }
  function renderMap(mode, identity, grants, canWrite, counts) {
    counts=counts||{};
    return '<div class="shared-studio" data-workgroup-map>'+
      '<div class="shared-studio-intro"><h2>AI Workgroup Studio</h2>'+
      '<p>One connected knowledge map. Open any module directly; arrows explain evidence relationships, not mandatory stages or assigned tasks.</p></div>'+
      ZONES.map(function(zone,i) {
        return '<section class="shared-studio-zone" aria-label="'+escape(zone.name)+'">'+
          '<h3>'+(i+1)+'. '+escape(zone.name)+'</h3><div class="shared-studio-grid">'+
          zone.blocks.filter(function(b){return canVisit(b[0],grants,mode,canWrite);}).map(function(b){
            // Fail closed even if an upstream caller accidentally supplies a
            // spurious count for a domain without a modeled resolution state.
            var n=["benchmark","forecasts","recommendations"].includes(b[0]) ?
              counts[b[0]] : null;
            var attentionLink=Number.isInteger(n)&&n>0 ?
              '<a class="shared-attention" data-attention-filter="'+escape(b[0])+'"'+
                ' aria-label="Filter '+escape(b[1])+' to the '+n+
                ' record(s) requiring review" href="'+escape(href(mode,b[0],identity))+
                (b[0]==="benchmark"?(href(mode,b[0],identity).includes("?")?"&":"?")+
                  "status=awaiting_publication":"")+
                '">'+
                n+' requiring review</a>' : "";
            return '<div class="shared-studio-block'+(CORE.includes(b[0])?" shared-studio-core":"")+
              '"><a class="shared-studio-link" data-studio-section="'+escape(b[0])+
              '" href="'+escape(href(mode,b[0],identity))+
              '"><strong>'+escape(b[1])+'</strong><small>'+escape(b[2])+'</small></a>'+
              attentionLink+'</div>';
          }).join("")+'</div>'+
          (zone.name==="Capitalisation & Décision" ?
            '<p class="shared-studio-gap"><a data-studio-gap="catalog" href="'+
            escape(root.AICompassContext.route(mode,"workgroup","catalog",{gap:"1"}))+
            '">Profitability &amp; Opportunities → Technology Catalog: explore uncovered Tasks '+
            'and candidate technologies</a> — knowledge discovery only; no Catalog entry, Task, '+
            'Forecast or Campaign is created automatically.</p>' : "")+'</section>';
      }).join("")+
      '<p class="shared-studio-published"><a data-studio-published="updates" href="'+
        escape(href(mode,"updates",identity))+'">Workgroup Updates · What\'s New</a> — '+
        'globally published measured results, campaigns, guides, technologies and editorial '+
        'context, kept separate from the privileged Activity Feed and audit log.</p>'+
      '<p class="shared-studio-relations">Needs → Tasks → Test Design → Campaign Runs → Results → Recommendations and Guides → User adoption → Feedback. Technology Watch and Forecasts inform studies without manufacturing measured evidence.</p>'+
      '<a href="'+escape(href(mode,"activity",identity))+'">Activity Feed · historical changes</a></div>';
  }
  function breadcrumbs(mode,section,detail) {
    return root.AICompassContext.breadcrumb(mode,"workgroup",section,detail);
  }
  function coverageGapNotice(mode, parameters) {
    /* Explicit knowledge-discovery link from Profitability/Opportunities. It
     * states the gap without inventing a candidate, Forecast or Catalog entry. */
    var params=parameters||new URLSearchParams(root.location.search);
    if(params.get("gap")!=="1")return "";
    var task=String(params.get("task")||"").slice(0,120);
    var workspace=params.get("workspace");
    if(!["workgroup","engineer","management"].includes(workspace))
      workspace="workgroup";
    return '<section class="shared-gap-notice" data-coverage-gap role="note">'+
      '<h3>Coverage-gap exploration</h3>'+
      '<p>The Technology Catalog holds versioned Model, Provider, Harness and Framework '+
      'components. A blank Profitability cell or an uncovered Task means no current '+
      'effective published measured configuration exists there yet; it is not a hidden '+
      'candidate, a Forecast or an obligation.</p>'+
      (task?'<p>Task context requested: <strong>'+escape(task)+'</strong>. Task membership '+
        'and suitability are only claimed from real authorized records.</p>':'')+
      '<p>Nothing is created automatically by this navigation. Candidate selection, '+
      'Forecast and Campaign stay explicit Workgroup decisions.</p>'+
      '<p><a href="'+escape(root.AICompassContext.route(mode,workspace,"catalog",{}))+
      '">Clear the coverage-gap filter</a>'+
      (workspace==="management"?' · <a href="'+
        escape(root.AICompassContext.route(mode,"management","home",{}))+
        '">Back to Management Insights</a>':"")+'</p></section>';
  }
  function serverProvider(transport) {
    if (!transport || typeof transport.request !== "function")
      throw Error("Authenticated Server transport required");
    return {list:async function(section) {
      var endpoint=STABLE[section];
      if (!endpoint)throw Error("Unsupported stable view");
      var result=await transport.request("/api/v1/"+endpoint.api,"GET");
      if (!result || !Array.isArray(result.results))throw Error("Invalid Server list");
      return result.results;
    }};
  }
  function demoProvider(db, canWrite) {
    if (!db)throw Error("Fictional Demo data required");
    return {list:async function(section) {
      var spec=STABLE[section];
      if (!spec)throw Error("Unsupported stable view");
      var rows=(db[spec.local]||[]).slice();
      if (!canWrite() && section==="guides")rows=rows.filter(function(x){return x.status==="published";});
      if (!canWrite() && section==="watch")rows=rows.filter(function(x){return x.publication==="published";});
      if (!canWrite() && section==="feedback")rows=rows.filter(function(x){return !x.internal && x.visibility!=="internal";});
      if (!canWrite() && section==="activity")rows=rows.filter(function(x){return !x.internal;});
      return rows;
    }};
  }
  function summary(row,section) {
    // Common immutable read projection; keep identifiers and source revisions.
    var props=row.properties||{};
    var title=row.name||row.title||row.text||row.id||"Untitled";
    var id=row.id||"",rev=row.revision||row.case_version||"";
    var status=row.status||row.review_state||props.review_state||row.publication||"";
    return {id:id,title:title,revision:rev,status:status,
      kind:section==="forecasts"?"theoretical (not measured)":section==="activity"?"audit event":section};
  }
  function renderList(rows, section, mode, detailLink, options) {
    if (!Array.isArray(rows)) throw Error("Untrusted list shape");
    options=options||{};
    var spec=STABLE[section],query=String(options.q||"").toLocaleLowerCase();
    var authorized=rows.filter(function(x){
      return !query || String(x.name||x.title||x.text||x.id||"").toLowerCase().includes(query) ||
        String(x.id||"").toLowerCase().includes(query);
    });
    return '<section class="shared-list" data-shared-list="'+escape(section)+'">'+
      '<h3>'+escape(spec.title)+'</h3>'+
      '<label class="ux-context-filter">Find authorized records <input aria-label="Filter authorized records"'+
      ' data-ux-list-filter value="'+escape(options.q||"")+'" placeholder="Search name or ID"></label>'+
      '<p class="muted">Current authorized entries, with exact object IDs. Original immutable revisions'+
      ' and editing remain available in the domain workspace.</p>'+
      (authorized.length?authorized.map(function(original) {
        var r=summary(original,section),to=detailLink&&detailLink(r.id);
        return '<article class="shared-list-row"><strong>'+escape(r.title)+'</strong>'+
          '<p class="muted">'+escape(r.id)+(r.revision?' · '+escape(r.revision):"")+
          (r.status?' · '+escape(r.status):"")+' · '+escape(r.kind)+'</p>'+
          (to?'<a href="'+escape(to)+'">View record details</a>':'')+'</article>';
      }).join(""):'<p>No matching authorized '+escape(spec.title)+' records.</p>')+
      '</section>';
  }
  function mountSummary(node,provider,section,mode,options) {
    if (!node || !STABLE[section])throw Error("Stable section and DOM mount required");
    var generation=0;
    options=options||{};
    var params=new URLSearchParams(root.location.search);
    var q=params.get("q")||"";
    function attachFilter(data) {
      var input=node.querySelector("[data-ux-list-filter]");
      if(!input)return;
      input.addEventListener("input",function(){
        q=this.value.slice(0,150);
        var url=new URL(root.location.href);
        if(q)url.searchParams.set("q",q);
        else url.searchParams.delete("q");
        root.history.replaceState(root.history.state,"",url.pathname+url.search+url.hash);
        // No new API request and no loss of selected record on filtering.
        showData(data);
        var focused=node.querySelector("[data-ux-list-filter]");
        if(focused){focused.focus();focused.setSelectionRange(q.length,q.length);}
      });
    }
    function showData(data) {
      var selected=options.recordId && data.find(function(x){return x.id===options.recordId;});
      node.innerHTML=renderList(data,section,mode,options.link,{q:q});
      if(options.recordId){
        var detail=root.document.createElement("section");
        if(selected){
          var rendered=root.AICompassContext.recordDetails(selected,section,mode,options.revision||"");
          detail.innerHTML=rendered.html;
          if(rendered.raw){
            var pre=detail.querySelector(".ux-advanced-source pre");
            if(pre)pre.textContent=JSON.stringify(rendered.raw,null,2);
          }
        } else {
          detail.className="ux-history-warning";
          detail.setAttribute("role","alert");
          detail.textContent="Object unavailable, withdrawn or not authorized. No Demo or current-version fallback.";
        }
        node.insertBefore(detail,node.firstChild);
      }
      attachFilter(data);
    }
    async function show() {
      var token=++generation;
      node.textContent="Loading "+(mode==="demo"?"fictional Demo":"real Server")+" records…";
      try{
        var data=await provider.list(section);
        if(token!==generation)return;
        showData(data);
        return data;
      }catch(err){
        if(token!==generation)return;
        node.replaceChildren();
        node.textContent="Cannot load "+section+": "+err.message+". No cross-mode fallback.";
        throw err;
      }
    }
    return {show:show,dispose:function(){generation++;node.replaceChildren();}};
  }

  // UX-R04 shared read projection; no data provider or privilege is inferred.
  function renderCases(cases,tasks,options) {
    if(!Array.isArray(cases)||!Array.isArray(tasks))throw Error("Authorized Test Cases and tasks required");
    options=options||{};
    var mode=options.mode;
    if(mode!=="demo"&&mode!=="server")throw Error("Explicit Demo or Server mode required");
    if(!cases.length)return '<p class="muted" data-shared-case-empty>'+
      escape(options.emptyText||"No Test Cases defined.")+'</p>';
    var names=new Map(tasks.map(function(t){return [String(t.id),t.name||t.title||t.id];}));
    var groups=new Map(),visited=new Set(),result="";
    function task(r){return String(mode==="demo"?r.task||"":r.task_id||"");}
    function parent(r){return mode==="demo"?r.parentCaseId:r.fork_parent_id;}
    function version(r){return String(mode==="demo"?r.version||"":r.case_version||"");}
    function sort(a,b){return version(a).localeCompare(version(b),undefined,{numeric:true});}
    cases.forEach(function(c){var t=task(c);if(!groups.has(t))groups.set(t,[]);groups.get(t).push(c);});
    function item(c,group) {
      if(visited.has(c.id))return "";
      visited.add(c.id);
      var id=escape(c.id),title=escape(mode==="demo"?c.title:c.name),
          revision=c.revision?' · '+escape(c.revision):"",
          summary=mode==="demo"?c.objective:(c.properties||{}).objective,
          label=summary?escape(summary)+" · ":"";
      var counts=options.publishedRunCounts||{};
      if(mode==="demo"&&Object.prototype.hasOwnProperty.call(counts,c.id))
        label+=escape(counts[c.id])+" published run(s) · ";
      var actions=mode==="demo"?
        '<button type="button" data-act="caseDetail" data-id="'+id+'">Inspect</button>':
        '<button type="button" data-case="'+id+'" data-action="history">Details / history</button>'+
        (options.canWrite?'<button type="button" data-case="'+id+'" data-action="edit">Edit</button>'+
        '<button type="button" data-case="'+id+'" data-action="fork">Fork</button>':"");
      var children=group.filter(function(x){return x.id!==c.id&&parent(x)===c.id;}).sort(sort);
      return '<div class="case-tree-item shared-case-item" data-shared-case="'+id+'">'+
        '<div class="case-main"><div class="case-meta"><strong>'+title+'</strong>'+
        '<span class="case-version">v'+escape(version(c))+'</span>'+
        (parent(c)?'<span class="muted small">Fork</span>':"")+'</div>'+
        '<div class="case-subtitle">'+label+id+revision+'</div></div>'+
        '<div class="server-model-actions">'+actions+'</div></div>'+
        (children.length?'<div class="case-branch">'+children.map(function(x){return item(x,group);}).join("")+'</div>':"");
    }
    groups.forEach(function(group,t){
      var ids=new Set(group.map(function(c){return c.id;}));
      var roots=group.filter(function(c){return !parent(c)||!ids.has(parent(c))||parent(c)===c.id;}).sort(sort);
      var html=roots.map(function(c){return item(c,group);}).join("");
      // Broken historical cycles remain visible, never automatically reparented.
      html+=group.filter(function(c){return !visited.has(c.id);}).sort(sort)
        .map(function(c){return item(c,group);}).join("");
      result+='<section class="shared-case-group" data-shared-case-task="'+escape(t)+'">'+
        '<div class="case-tree-task"><strong>'+escape(names.get(t)||t||"Unknown task")+
        '</strong><span class="muted small"> · '+group.length+' Test Case(s)</span></div>'+html+'</section>';
    });
    return '<div class="shared-case-tree" data-shared-cases="'+mode+'">'+result+'</div>';
  }


  var CASE_FIELDS=Object.freeze([
    ["objective","Objective / challenge"],["inputs","Starting inputs / source context"],
    ["constraints","Constraints / conditions"],["expected_outputs","Expected outputs"],
    ["dod","Definition of Done"],["environment","Environment / setup"]
  ]);
  function normalizeCase(row,mode) {
    if(!row||(mode!=="demo"&&mode!=="server"))throw Error("Explicit Test Case and mode required");
    return {id:row.id,title:mode==="demo"?row.title:row.name,
      version:mode==="demo"?row.version:row.case_version,
      revision:row.revision||"",
      parent:mode==="demo"?row.parentCaseId:row.fork_parent_id,
      task:mode==="demo"?row.task:row.task_id,
      fields:mode==="demo"?row:(row.properties||{})};
  }
  function renderCaseFields(values,selection) {
    selection=selection||CASE_FIELDS.map(function(f){return f[0];});
    if(!Array.isArray(selection)||selection.some(function(k){return !CASE_FIELDS.some(function(f){return f[0]===k;});}))
      throw Error("Unknown Test Case field");
    values=values||{};
    return CASE_FIELDS.filter(function(f){return selection.includes(f[0]);}).map(function(f){
      return '<div class="field span2 shared-case-field"><label for="shared-tc-'+f[0]+'">'+
        escape(f[1])+'</label><textarea id="shared-tc-'+f[0]+'" name="'+f[0]+'" rows="3">'+
        escape(values[f[0]]||"")+'</textarea></div>';
    }).join("");
  }
  function renderCaseDetail(row,mode,options) {
    var r=normalizeCase(row,mode),p=r.fields;
    options=options||{};
    var fields=options.fields||CASE_FIELDS.map(function(f){return f[0];});
    var contents=CASE_FIELDS.filter(function(f){return fields.includes(f[0])&&p[f[0]];}).map(function(f){
      return '<section class="shared-case-detail-field"><h4>'+escape(f[1])+'</h4>'+
        '<p style="white-space:pre-wrap">'+escape(p[f[0]])+'</p></section>';
    }).join("");
    return '<div class="shared-case-detail" data-shared-case-detail="'+mode+'">'+
      '<h3>'+escape(r.title)+'</h3><p class="muted small">ID '+escape(r.id)+
      ' · Version '+escape(r.version)+(r.revision?' · Revision '+escape(r.revision):"")+
      ' · Task '+escape(options.taskName||r.task||"Unknown")+
      (r.parent?' · Fork of '+escape(r.parent):"")+'</p>'+
      (contents||'<p class="muted">No documented challenge fields.</p>')+'</div>';
  }


  /* UX-R04 campaign evaluation matrix: one presentation component for Demo and
   * Server. Adapters supply an authorized, presentation-only projection of one
   * exact matrix revision; this component never fetches, decides, persists or
   * promotes a candidate planning cell into measured evidence. */
  var MATRIX_STATES=Object.freeze(["pending","in_progress","evaluated","waived","not_selected"]);
  var MATRIX_STATE_TAG=Object.freeze({pending:"amber",in_progress:"blue",evaluated:"green",
    waived:"purple",not_selected:"red"});
  var MATRIX_STATE_LABEL=Object.freeze({pending:"Pending",in_progress:"In progress",
    evaluated:"Evaluated",waived:"Waived",not_selected:"Not selected"});
  var MATRIX_DECISIONS=Object.freeze([["selected","Selected / Pending"],
    ["not_selected","Not Selected"],["waived","Waived"]]);
  var MATRIX_NOT_MEASURED="Waived, Not Selected and Pending cells are never measured evidence; "+
    "a failed Definition-of-Done Run counts as a completed attempt, not a successful outcome.";

  function matrixMode(mode) {
    if(mode!=="demo"&&mode!=="server")throw Error("Explicit Demo or Server matrix mode required");
    return mode;
  }
  function matrixAttribute(name,value) {
    if(!/^data-[a-z][a-z0-9-]*$/.test(name))throw Error("Invalid matrix attribute");
    return ' '+name+'="'+escape(value)+'"';
  }
  function matrixAttributes(attributes) {
    var keys=Object.keys(attributes||{});
    if(!keys.length)throw Error("Matrix action without routing");
    return keys.map(function(key){return matrixAttribute(key,attributes[key]);}).join("");
  }
  function matrixCommand(action) {
    if(!action||!action.label)throw Error("Missing matrix action label");
    return '<button type="button"'+matrixAttributes(action.attributes)+'>'+
      escape(action.label)+'</button>';
  }
  function matrixHref(item) {
    var url=String(item&&item.href||"");
    if(!((url.startsWith("/")&&!url.startsWith("//"))||url.startsWith("?")))
      throw Error("Matrix record link must be same-origin");
    return '<a href="'+escape(url)+'">'+escape(item.label||"Open record")+'</a>';
  }
  function indexMatrixRows(rows,label) {
    if(!Array.isArray(rows))throw Error("Matrix projection requires "+label);
    var map=new Map();
    rows.forEach(function(row){
      if(!row||!row.id)throw Error("Matrix "+label+" require stable public IDs");
      var key=String(row.id);
      if(map.has(key))throw Error("Duplicate matrix "+label+" identity");
      map.set(key,row);
    });
    return map;
  }
  // Only data access, display names and permissible routing differ per mode.
  function normalizeMatrixPlan(plan,mode) {
    matrixMode(mode);
    if(!plan||typeof plan!=="object"||Array.isArray(plan))
      throw Error("Authorized matrix projection required");
    if(typeof plan.revision!=="string"||!plan.revision)
      throw Error("Matrix projection requires its exact revision");
    var tasks=indexMatrixRows(plan.tasks,"tasks"),
        testCases=indexMatrixRows(plan.testCases,"Test Cases"),
        configurations=indexMatrixRows(plan.configurations,"configurations");
    configurations.forEach(function(configuration){
      if(!configuration.label)throw Error("Matrix configuration requires a label");
      if(!tasks.has(String(configuration.taskId||"")))
        throw Error("Matrix configuration requires its Task");
    });
    if(!Array.isArray(plan.cells))throw Error("Matrix projection requires cells");
    var seen=new Set();
    plan.cells.forEach(function(cell){
      if(!cell||!cell.id)throw Error("Matrix cell requires a stable evaluation ID");
      var id=String(cell.id);
      if(seen.has(id))throw Error("Duplicate matrix evaluation identity");
      seen.add(id);
      if(!MATRIX_STATES.includes(cell.status))throw Error("Unsupported matrix cell state");
      if(!configurations.has(String(cell.configurationId||"")))
        throw Error("Matrix cell requires its configuration");
      if(!testCases.has(String(cell.testCaseId||"")))
        throw Error("Matrix cell requires its Test Case");
      if(cell.decision&&!["selected","not_selected","waived"].includes(cell.decision))
        throw Error("Unsupported matrix decision");
      if(cell.waiver&&!String(cell.waiver.reason||"").trim())
        throw Error("A recorded waiver must keep its reason");
    });
    return {revision:plan.revision,tasks:tasks,testCases:testCases,
      configurations:configurations,cells:plan.cells};
  }
  function matrixTotals(read) {
    var totals={candidates:read.cells.length,pending:0,in_progress:0,evaluated:0,waived:0,
      not_selected:0,measured_runs:0,active_attempts:0};
    read.cells.forEach(function(cell){
      totals[cell.status]++;
      totals.measured_runs+=(cell.runs||[]).length;
      totals.active_attempts+=Number.isInteger(cell.activeAttempts)?cell.activeAttempts:0;
    });
    totals.selected_obligations=totals.pending+totals.in_progress+totals.evaluated;
    totals.outstanding=totals.pending+totals.in_progress;
    totals.full_plan_complete=totals.candidates>0&&totals.outstanding===0;
    return totals;
  }
  function matrixStateTag(status) {
    return '<span class="tag '+MATRIX_STATE_TAG[status]+
      '" data-matrix-state-label="'+escape(status)+'">'+escape(MATRIX_STATE_LABEL[status])+
      '</span>';
  }
  function matrixCell(read,cellId) {
    var cell=read.cells.find(function(x){return String(x.id)===String(cellId);});
    if(!cell)throw Error("Matrix cell is not part of this authorized revision");
    return cell;
  }
  function renderCampaignMatrix(plan, options) {
    options=options||{};
    var mode=matrixMode(options.mode),read=normalizeMatrixPlan(plan,mode);
    var totals=matrixTotals(read);
    var cellAttributes=options.cellAttributes||function(cell){return {"data-matrix-cell":cell.id};};
    var head='<section class="shared-matrix" data-shared-matrix="'+escape(mode)+
      '" data-matrix-mode="'+escape(mode)+'" data-matrix-revision="'+escape(read.revision)+'">'+
      '<h3>Campaign Evaluation Matrix</h3>';
    if(!totals.candidates)
      return head+'<p class="muted" data-matrix-empty>'+escape(options.emptyText||
        "No Task-associated evaluation cell is planned yet. Candidate planning never creates measured evidence.")+
        '</p>'+(options.footer||"")+'</section>';
    var taskFilter=String(options.taskFilter||"");
    var taskIds=Array.from(new Set(Array.from(read.configurations.values()).map(function(configuration){
      return String(configuration.taskId);})));
    var body=taskIds.filter(function(taskId){
      return !taskFilter||taskId===taskFilter;}).map(function(taskId){
      var task=read.tasks.get(taskId);
      var configurations=Array.from(read.configurations.values()).filter(function(configuration){
        return String(configuration.taskId)===taskId;});
      var configurationIds=new Set(configurations.map(function(configuration){return String(configuration.id);}));
      var rowIds=Array.from(new Set(read.cells.filter(function(cell){
        return configurationIds.has(String(cell.configurationId));}).map(function(cell){
        return String(cell.testCaseId);})));
      return '<div class="shared-matrix-task" data-shared-matrix-task="'+escape(taskId)+'">'+
        '<h4>'+escape(task?task.name:taskId)+' <span class="muted small">· '+
        configurations.length+' configuration(s) · '+rowIds.length+' Test Case(s)</span></h4>'+
        '<div class="shared-matrix-scroll"><table class="shared-matrix-grid"><thead><tr>'+
        '<th scope="col">Test Case</th>'+
        configurations.map(function(configuration){
          return '<th scope="col" data-shared-matrix-configuration="'+escape(configuration.id)+'">'+
            escape(configuration.label)+'<span class="muted small shared-matrix-identifier"> '+
            escape(configuration.kind||"individual")+' · '+escape(configuration.id)+'</span></th>';
        }).join("")+
        '</tr></thead><tbody>'+
        rowIds.map(function(testCaseId){
          var testCase=read.testCases.get(testCaseId);
          return '<tr><th scope="row">'+escape(testCase?testCase.name:testCaseId)+
            '<span class="muted small shared-matrix-identifier">'+escape(testCaseId)+
            (testCase&&testCase.revision?' · '+escape(testCase.revision):"")+'</span></th>'+
            configurations.map(function(configuration){
              var cell=read.cells.find(function(x){
                return String(x.configurationId)===String(configuration.id)&&
                  String(x.testCaseId)===testCaseId;});
              if(!cell)return '<td class="shared-matrix-absent" data-shared-matrix-absent="'+
                escape(configuration.id+"|"+testCaseId)+'">—</td>';
              var runs=cell.runs||[];
              return '<td class="shared-matrix-cell" data-shared-matrix-cell="'+escape(cell.id)+
                '" data-matrix-state="'+escape(cell.status)+'">'+matrixStateTag(cell.status)+
                '<button type="button"'+matrixAttributes(cellAttributes(cell))+
                '>Open evaluation cell</button>'+
                '<span class="muted small">'+runs.length+' Run(s)'+
                (cell.activeAttempts?' · '+cell.activeAttempts+' attempt(s) in progress':'')+
                (cell.introducedRevision===read.revision?' · New':"")+'</span>'+
                (cell.waiver?'<p class="muted small">Waiver: '+escape(cell.waiver.reason)+'</p>':"")+
                '</td>';
            }).join("")+'</tr>';
        }).join("")+'</tbody></table></div></div>';
    }).join("");
    return head+
      '<p class="small shared-matrix-summary" data-shared-matrix-summary>'+
        'Candidate cells: '+totals.candidates+' · Evaluated: '+totals.evaluated+
        ' · Pending: '+totals.pending+' · In Progress: '+totals.in_progress+
        ' · Waived: '+totals.waived+' · Not Selected: '+totals.not_selected+'</p>'+
      '<p class="small shared-matrix-notice"><strong>Full plan: '+
        (totals.full_plan_complete?"complete":"outstanding")+'</strong> · '+
        escape(MATRIX_NOT_MEASURED)+'</p>'+
      '<p class="muted small">Plan revision '+escape(read.revision)+' · measured Runs: '+
        totals.measured_runs+' · selected obligations still open: '+totals.outstanding+'</p>'+
      body+(options.footer||"")+'</section>';
  }
  function renderMatrixCellDetail(plan, cellId, options) {
    options=options||{};
    var mode=matrixMode(options.mode),read=normalizeMatrixPlan(plan,mode);
    var cell=matrixCell(read,cellId);
    var configuration=read.configurations.get(String(cell.configurationId));
    var testCase=read.testCases.get(String(cell.testCaseId));
    var task=read.tasks.get(String(configuration.taskId));
    function section(label,body) {
      return body?'<section class="shared-matrix-property"><h4>'+escape(label)+'</h4>'+
        body+'</section>':"";
    }
    function line(value) {
      return '<p class="shared-matrix-value">'+escape(value)+'</p>';
    }
    var runs=(cell.runs||[]).length?cell.runs.map(function(run){
      var routing=run.href?matrixHref({href:run.href,label:"Open measured Run provenance"}):
        run.action?matrixCommand(run.action):"";
      return '<li>'+escape(run.label||("Measured "+(run.kind||"")+" Run "+run.id))+
        (run.revision?'<span class="muted small"> · '+escape(run.revision)+'</span>':"")+
        (run.outcome?'<span class="muted small"> · '+escape(run.outcome)+'</span>':"")+
        (routing?' '+routing:"")+'</li>';
    }).join(""):'<li class="muted">No measured Run is attached to this evaluation yet.</li>';
    return '<article class="shared-matrix-cell-detail" data-matrix-cell-detail="'+escape(cell.id)+
      '" data-matrix-mode="'+escape(mode)+'" data-matrix-state="'+escape(cell.status)+'">'+
      '<h3>'+escape(testCase?testCase.name:cell.testCaseId)+' × '+escape(configuration.label)+'</h3>'+
      '<p class="muted small">'+[cell.id,MATRIX_STATE_LABEL[cell.status],cell.decision]
        .filter(function(value){return value!=null&&value!=="";}).map(escape).join(' · ')+'</p>'+
      section("Task",line(task?task.name:configuration.taskId))+
      section("Test Case",line(String(cell.testCaseId)+
        (cell.testCaseRevision?" · pinned revision "+cell.testCaseRevision:"")+
        (testCase&&testCase.revision?" · version "+testCase.revision:""))+
        (cell.testCaseHref?
          '<p>'+matrixHref({href:cell.testCaseHref,label:"Open Test Case context"})+'</p>':
         cell.testCaseAction?'<p>'+matrixCommand(cell.testCaseAction)+'</p>':
         testCase&&testCase.href?
          '<p>'+matrixHref({href:testCase.href,label:"Open Test Case context"})+'</p>':""))+
      section("Configuration",line(configuration.label+' · '+
        (configuration.kind||"individual")+' · '+configuration.id))+
      section("Recorded state",line(MATRIX_STATE_LABEL[cell.status]+
        (cell.introducedRevision?" · introduced in "+cell.introducedRevision:"")+
        " · "+cell.activeAttempts+" active attempt(s)"))+
      section("Waiver",cell.waiver?line(cell.waiver.reason)+
        '<p class="muted small">'+[cell.waiver.actor,cell.waiver.at].filter(Boolean).map(escape).join(' · ')+
        '</p>':"")+
      '<section class="shared-matrix-property"><h4>Measured Runs ('+(cell.runs||[]).length+
      ')</h4><ul class="shared-matrix-runs">'+runs+'</ul></section>'+
      '<p class="muted small">'+escape(MATRIX_NOT_MEASURED)+'</p></article>';
  }
  function renderMatrixDecisionFields(plan, cellId, mode) {
    var read=normalizeMatrixPlan(plan,matrixMode(mode));
    var cell=matrixCell(read,cellId);
    var current=cell.decision||"selected";
    return '<div class="shared-matrix-decision" data-shared-matrix-decision="'+escape(mode)+'">'+
      '<div class="field"><label for="matrix-decision-'+escape(mode)+'">Decision</label>'+
      '<select id="matrix-decision-'+escape(mode)+'" name="decision">'+
      MATRIX_DECISIONS.map(function(decision){
        return '<option value="'+escape(decision[0])+'"'+
          (decision[0]===current?' selected':'')+'>'+escape(decision[1])+'</option>';}).join("")+
      '</select></div>'+
      '<div class="field"><label for="matrix-reason-'+escape(mode)+
      '">Waiver explanation (required only when waived)</label>'+
      '<textarea id="matrix-reason-'+escape(mode)+'" name="reason" maxlength="4000" rows="3"></textarea>'+
      '</div><p class="muted small">Waiver is a deliberate release from an existing obligation, not a '+
      'failed Test Run. Only a waiver accepts a reason, and completed Runs remain immutable.</p></div>';
  }

  /* UX-R04 shared interaction primitives: form fields, blocking status,
   * generic record detail and lifecycle steppers. Adapters supply authorized
   * values, options and routing; nothing here persists, authorizes or invents
   * data, and unknown input fails closed. */
  var DOMAIN_FIELD_KINDS=Object.freeze(["text","textarea","url","number","select","multi","checkbox"]);
  var DOMAIN_STATUS_STATES=Object.freeze(["loading","empty","error","denied","ok"]);
  var STEPPER_STATES=Object.freeze(["done","current","todo","blocked"]);

  function domainMode(mode) {
    if(mode!=="demo"&&mode!=="server")throw Error("Explicit Demo or Server mode required");
    return mode;
  }
  function domainFieldVisible(entry,mode) {
    return !entry.modes||entry.modes.includes(mode);
  }
  function domainFieldName(entry,mode) {
    return String(mode==="demo"?(entry.demoKey||entry.key):(entry.serverKey||entry.key));
  }
  function domainFieldChoices(entry,mode) {
    var choices=(mode==="demo"&&entry.demoOptions)||entry.options||[];
    return choices.map(function(choice){
      var pair=Array.isArray(choice)?choice:[choice,choice];
      return {value:String(pair[0]),label:String(pair[1])};});
  }
  function domainFieldKind(entry,mode) {
    return (mode==="demo"&&entry.demoKind)||(mode==="server"&&entry.serverKind)||entry.kind||"text";
  }
  function domainFieldPlaceholder(entry,mode) {
    return (mode==="demo"&&entry.demoPlaceholder)||(mode==="server"&&entry.serverPlaceholder)||
      entry.placeholder||"";
  }
  function domainFieldRequired(entry,mode) {
    if(mode==="demo"&&entry.demoRequired!==undefined)return !!entry.demoRequired;
    if(mode==="server"&&entry.serverRequired!==undefined)return !!entry.serverRequired;
    return !!entry.required;
  }
  function domainFieldValues(values,name) {
    if(values&&Object.prototype.hasOwnProperty.call(values,name))return values[name];
    return "";
  }
  // One field presentation for Demo and Server; only names/options differ.
  function renderDomainFields(spec, values, mode, options) {
    domainMode(mode);
    options=options||{};
    if(!Array.isArray(spec))throw Error("Authorized field specification required");
    Object.keys(options.choices||{}).forEach(function(key){
      if(!Array.isArray(options.choices[key]))throw Error("Field choices must be an array");
    });
    return spec.filter(function(entry){return domainFieldVisible(entry,mode);}).map(function(entry){
      if(!entry||!entry.key||!entry.label)throw Error("Field specification requires key and label");
      var kind=domainFieldKind(entry,mode);
      if(!DOMAIN_FIELD_KINDS.includes(kind))throw Error("Unsupported domain field kind");
      var name=domainFieldName(entry,mode),value=domainFieldValues(values,name),
          id=escape(options.idPrefix||"shared")+"-"+escape(mode)+"-"+escape(name),
          attrs=(entry.maxlength?' maxlength="'+escape(entry.maxlength)+'"':"")+
            (domainFieldRequired(entry,mode)?" required":"")+
            (domainFieldPlaceholder(entry,mode)?
              ' placeholder="'+escape(domainFieldPlaceholder(entry,mode))+'"':"");
      var control;
      var locked=options.locked&&Object.prototype.hasOwnProperty.call(options.locked,name);
      if(locked)
        control='<input type="hidden" name="'+escape(name)+'" value="'+
          escape(options.locked[name])+'">';
      else if(kind==="textarea")
        control='<textarea id="'+id+'" name="'+escape(name)+'" rows="'+escape(entry.rows||3)+'"'+
          attrs+'>'+escape(value)+'</textarea>';
      else if(kind==="select"||kind==="multi") {
        var override=options.choices&&options.choices[name];
        if(override!==undefined&&!Array.isArray(override))
          throw Error("Field choices must be an array");
        var choices=override?override.map(function(choice){
          var pair=Array.isArray(choice)?choice:[choice,choice];
          return {value:String(pair[0]),label:String(pair[1])};}):domainFieldChoices(entry,mode);
        var blank=entry.blankLabel!==undefined?entry.blankLabel:
          (options.blankLabels&&options.blankLabels[name]!==undefined?
            options.blankLabels[name]:undefined);
        if(kind==="select"&&blank!==undefined)
          choices=[{value:"",label:blank}].concat(choices);
        var selected=kind==="multi"?(Array.isArray(value)?value.map(String):[]):[String(value==null?"":value)];
        control='<select id="'+id+'" name="'+escape(name)+'"'+
          (kind==="multi"?' multiple size="'+escape(entry.size||6)+'"':"")+attrs+'>'+
          choices.map(function(choice){
            return '<option value="'+escape(choice.value)+'"'+
              (selected.includes(choice.value)?' selected':'')+'>'+escape(choice.label)+'</option>';}).join("")+
          '</select>';
      }
      else if(kind==="checkbox")
        control='<input id="'+id+'" name="'+escape(name)+'" type="checkbox" value="yes"'+
          (value===true||value==="yes"||value==="on"?' checked':'')+'>';
      else {
        // Numeric metrics keep the historical Demo contract: fractions are
        // valid (step="any") and negative measurements are refused (min="0").
        if(kind==="number")attrs+=' step="'+escape(entry.step||"any")+'"'+
          // min="0" is the historical Demo metric contract; an explicit
          // min:null keeps an unbounded descriptor-driven measurement.
          (entry.min===undefined?' min="0"':entry.min===null?"":
            ' min="'+escape(entry.min)+'"')+
          (entry.max==null?"":' max="'+escape(entry.max)+'"');
        control='<input id="'+id+'" name="'+escape(name)+'" type="'+
          escape(kind==="number"?"number":"text")+'" value="'+escape(value)+'"'+attrs+'>';
      }
      if(locked)return control;
      return '<div class="field shared-domain-field'+(entry.span?' span2':"")+
        '" data-shared-field="'+escape(name)+'"><label for="'+id+'">'+escape(entry.label)+'</label>'+
        control+(entry.help?'<p class="helper">'+escape(entry.help)+'</p>':"")+'</div>';
    }).join("");
  }
  // Same-origin record link, refused otherwise.
  function recordLink(item) {
    var url=String(item&&item.href||"");
    if(!((url.startsWith("/")&&!url.startsWith("//"))||url.startsWith("?")))
      throw Error("Record link must be same-origin");
    return '<a href="'+escape(url)+'">'+escape(item.label||"Open record")+'</a>';
  }
  function renderDomainDetail(projection, options) {
    options=options||{};
    var mode=domainMode(options.mode),domain=String(options.domain||"");
    if(!/^[a-z][a-z0-9-]*$/.test(domain))
      throw Error("Explicit business domain required");
    if(!projection||typeof projection!=="object"||Array.isArray(projection))
      throw Error("Authorized record projection required");
    if(!String(projection.title||"").trim())throw Error("Record detail requires a title");
    var identity=(projection.identity||[]).filter(function(v){return v!=null&&v!=="";}),
        sections=projection.sections||[],notices=projection.notices||[],links=projection.links||[];
    if(!Array.isArray(sections)||!Array.isArray(notices)||!Array.isArray(links))
      throw Error("Invalid record projection");
    return '<article class="shared-domain-detail" data-shared-domain-detail="'+escape(domain)+
      '" data-domain-mode="'+escape(mode)+'"><h3>'+escape(projection.title)+'</h3>'+
      (identity.length?'<p class="muted small">'+identity.map(escape).join(' · ')+'</p>':"")+
      sections.filter(function(section){
        return section&&section.label&&section.value!=null&&String(section.value)!=="";})
        .map(function(section){
          return '<section class="shared-domain-property"><h4>'+escape(section.label)+'</h4>'+
            '<p class="shared-domain-value">'+escape(section.value)+'</p></section>';}).join("")+
      notices.filter(function(notice){return notice!=null&&notice!=="";})
        .map(function(notice){return '<p class="muted small">'+escape(notice)+'</p>';}).join("")+
      links.map(function(link){return '<p>'+recordLink(link)+'</p>';}).join("")+
      '</article>';
  }
  // Campaign lifecycle and session steps share one presentation too. An
  // interactive stepper turns the label into a local navigation button; it
  // never persists anything, it only reveals the matching panel.
  function renderStepper(steps, options) {
    options=options||{};
    var mode=domainMode(options.mode),domain=String(options.domain||"workflow");
    if(!/^[a-z][a-z0-9-]*$/.test(domain))throw Error("Explicit stepper domain required");
    if(!Array.isArray(steps)||!steps.length)throw Error("Authorized stepper steps required");
    return '<ol class="shared-stepper'+(options.interactive?' shared-draft-step':'')+'"'+
      (options.id?' id="'+escape(options.id)+'"':'')+
      ' data-shared-stepper="'+escape(domain)+
      '" data-stepper-mode="'+escape(mode)+'">'+steps.map(function(step,index){
        if(!step||!step.label)throw Error("Stepper step requires a label");
        var state=step.state||"todo";
        if(!STEPPER_STATES.includes(state))throw Error("Unsupported stepper state");
        var current=options.interactive&&state==="current";
        return '<li data-step-state="'+escape(state)+'" data-step-index="'+escape(index)+'"'+
          (current?' aria-current="step"':'')+'>'+
          (step.action? matrixCommand(step.action):
            '<strong>'+escape((index+1)+". "+step.label)+'</strong>')+
          (step.detail?' <span class="muted small">'+escape(step.detail)+'</span>':"")+
          '</li>';
      }).join("")+'</ol>';
  }
  // Loading, empty, refused and denied states read the same in both modes.
  /* One discussion-thread presentation: chronological messages, explicit
   * public/internal visibility, immutable revision and pinned original
   * attachments. Adapters supply authorized messages and permitted actions. */
  function renderThread(messages, options) {
    options=options||{};
    var mode=domainMode(options.mode);
    if(!Array.isArray(messages))throw Error("Authorized thread messages required");
    var permitted=options.actions||function(){return [];};
    return '<div class="shared-thread" data-shared-thread="'+escape(mode)+'">'+
      (messages.length?messages.map(function(message){
        if(!message||!message.id)throw Error("Thread message requires a stable ID");
        var visibility=String(message.visibility||"public");
        if(!["public","internal"].includes(visibility))
          throw Error("Unsupported thread message visibility");
        var allowed=permitted(message)||[];
        if(!Array.isArray(allowed))throw Error("Invalid thread message actions");
        var meta=[message.at,message.id,message.revision,
          message.parentId?"reply to "+message.parentId:""]
          .filter(function(value){return value!=null&&value!=="";}).map(escape);
        return '<article class="shared-thread-message" data-message-id="'+escape(message.id)+
          '" data-message-visibility="'+escape(visibility)+'">'+
          '<div class="shared-thread-meta"><strong>'+escape(message.author||"Unknown author")+
          '</strong> <span class="tag '+(visibility==="internal"?"amber":"blue")+'">'+
          escape(visibility==="internal"?"INTERNAL · workgroup only":"PUBLIC")+'</span> '+
          '<span class="muted small">'+meta.join(' · ')+'</span></div>'+
          '<div class="shared-thread-body">'+escape(message.body==null?"":message.body)+'</div>'+
          (message.attachments||[]).map(function(attachment){
            if(!attachment||!attachment.href)
              throw Error("Thread attachment requires its immutable location");
            return '<p class="muted small">Original attachment: '+
              recordLink({href:attachment.href,label:attachment.filename||"attachment"})+
              (attachment.sha256?' · SHA-256 '+escape(attachment.sha256):"")+'</p>';
          }).join("")+
          (allowed.length?'<div class="shared-thread-actions">'+
            allowed.map(matrixCommand).join("")+'</div>':"")+
          '</article>';
      }).join(""):'<p class="muted" data-shared-thread-empty>'+
        escape(options.emptyText||"No messages in this conversation yet.")+'</p>')+
      '</div>';
  }

  /* One revision-history reader: every retained revision of a corrected record,
   * the wording it superseded and why. Historical revisions are immutable and
   * always shown, never collapsed away or replaced by the current value. */
  function renderRevisionHistory(revisions, options) {
    options=options||{};
    var mode=domainMode(options.mode);
    if(!Array.isArray(revisions))throw Error("Authorized revision history required");
    return '<div class="shared-revision-history" data-shared-revision-history="'+
      escape(options.domain||"discussions")+'" data-revision-mode="'+escape(mode)+'">'+
      (options.heading?'<h3>'+escape(options.heading)+'</h3>':"")+
      (revisions.length?revisions.map(function(entry){
        if(!entry||entry.revision==null||!String(entry.revision).trim())
          throw Error("Revision entry requires its exact revision");
        var visibility=String(entry.visibility||"public");
        if(!["public","internal"].includes(visibility))
          throw Error("Unsupported revision visibility");
        var meta=[entry.by,entry.at,visibility]
          .filter(function(value){return value!=null&&value!=="";}).map(escape);
        return '<details data-shared-revision="'+escape(entry.revision)+
          '" data-revision-visibility="'+escape(visibility)+'"><summary>'+
          escape(entry.revision)+(meta.length?' · '+meta.join(' · '):"")+'</summary>'+
          '<p class="shared-revision-body" style="white-space:pre-wrap;overflow-wrap:anywhere">'+
          escape(entry.body==null?"":entry.body)+'</p>'+
          '<p class="shared-revision-reason">Reason: '+
          escape(entry.reason||"Original message")+'</p></details>';
      }).join(""):'<p class="muted" data-shared-revision-empty>'+
        escape(options.emptyText||"No retained revision yet.")+'</p>')+
      (options.notice?'<p class="muted small">'+escape(options.notice)+'</p>':"")+
      '</div>';
  }

  function renderDomainStatus(options) {
    options=options||{};
    var mode=domainMode(options.mode),state=options.state;
    if(!DOMAIN_STATUS_STATES.includes(state))throw Error("Unsupported status state");
    var alert=state==="error"||state==="denied";
    return '<p class="shared-domain-status" data-shared-status="'+escape(state)+
      '" data-status-mode="'+escape(mode)+'" role="'+(alert?"alert":"status")+'">'+
      escape(options.message||"")+'</p>';
  }
  /* One composed-setup reader: pinned module revisions resolved for one exact
   * configuration, the remaining coverage gaps stated explicitly, and no claim
   * that a recipe was validated for an OS or runtime it never declared. */
  function renderComposedSetup(projection, options) {
    options=options||{};
    var mode=domainMode(options.mode);
    if(!projection||typeof projection!=="object"||Array.isArray(projection))
      throw Error("Authorized composed-setup projection required");
    if(!String(projection.title||"").trim())
      throw Error("Composed setup requires the source record title");
    var sections=projection.sections||[],missing=projection.missing||[];
    if(!Array.isArray(sections))throw Error("Composed setup sections must be a list");
    if(!Array.isArray(missing))throw Error("Composed setup gaps must be a list");
    var safeUrl=function(url){return /^https?:\/\/[^\s<>]+$/i.test(String(url||"").trim());};
    return '<section class="shared-composed-setup" data-shared-composed-setup="'+
      escape(options.domain||"guides")+'" data-composed-mode="'+escape(mode)+
      '" data-composed-ready="'+(projection.ready===false?"false":"true")+'">'+
      '<h4>Composed setup · '+escape(projection.title)+
      (projection.revision?' · '+escape(projection.revision):"")+'</h4>'+
      '<p class="small" data-composed-readiness>'+(projection.ready===false?
        "Incomplete or ambiguous recipe — declared coverage is not satisfied.":
        "All declared modules are applicable for this configuration.")+'</p>'+
      '<div data-composed-gaps>'+(missing.length?
        '<p class="small">Missing coverage: '+missing.map(escape).join('; ')+'</p>':
        '<p class="small">No declared coverage gap reported by the source.</p>')+'</div>'+
      sections.filter(function(section){
        return section&&(section.name||section.revision||section.text);}).map(function(section){
        var url=String(section.url||"").trim();
        return '<details class="shared-composed-section" open><summary>'+
          escape(section.name||section.revision||"Module")+
          (section.revision?' · '+escape(section.revision):"")+'</summary>'+
          (section.text?'<pre class="text-block" style="white-space:pre-wrap">'+
            escape(section.text)+'</pre>':"")+
          (safeUrl(url)?'<p class="small"><a target="_blank" rel="noopener noreferrer" href="'+
            escape(url)+'">'+escape(url)+'</a></p>':
            url?'<p class="muted small">Unsupported URL — link withheld.</p>':"")+
          '</details>';}).join("")+
      '<p class="muted small">'+escape(options.notice||
        "Revision-pinned preview: it does not validate exact OS, runtime or setup "+
        "applicability, and unknown coverage is never assumed.")+'</p>'+
      '</section>';
  }

  /* One observation matrix (Task × candidate or Test Case × Solution): the
   * same rows, columns, observation counts and record routing in both modes.
   * Missing comparisons stay explicitly unknown; nothing is averaged here. */
  function renderObservationMatrix(projection, options) {
    options=options||{};
    var mode=domainMode(options.mode);
    if(!projection||typeof projection!=="object"||Array.isArray(projection))
      throw Error("Authorized observation matrix required");
    if(!Array.isArray(projection.columnLabels))
      throw Error("Observation matrix requires its column labels");
    if(!Array.isArray(projection.rows))throw Error("Observation matrix requires rows");
    // An empty matrix is legitimate (no persisted observation): only a matrix
    // that actually renders rows needs column labels.
    if(projection.rows.length&&!projection.columnLabels.length)
      throw Error("Observation matrix with rows requires column labels");
    var columns=new Map();
    projection.columnLabels.forEach(function(column){
      if(!column||column.key==null||!column.label)throw Error("Column requires key and label");
      columns.set(String(column.key),column);});
    // Fail closed on inconsistent projections: a cell that references an
    // undeclared column would otherwise hide its observations silently.
    function checkColumns(holder) {
      (holder.columns||[]).forEach(function(entry){
        if(!entry||!columns.has(String(entry.key)))
          throw Error("Observation cell references an unknown column");
      });
    }
    projection.rows.forEach(function(row){
      if(!row||row.key==null)throw Error("Observation row requires its key");
      checkColumns(row);
    });
    if(projection.footerRow)checkColumns(projection.footerRow);
    function cell(column,cellOptions) {
      var key=String(column.key);
      if(!columns.has(key))throw Error("Observation cell references an unknown column");
      var observations=column.observations===undefined?0:column.observations;
      if(!Number.isInteger(observations)||observations<0)
        throw Error("Observation count must be a non-negative integer");
      var body;
      if(!observations&&column.value==null)
        body='<span class="muted" data-observation-empty>'+
          escape(cellOptions.emptyRowText||"Not recorded")+'</span>';
      else
        body=(column.value!=null?'<strong class="shared-observation-value'+
          (column.tone?' tone-'+escape(column.tone):"")+'">'+escape(column.value)+'</strong>':'')+
          (column.hint?'<div class="muted small">'+escape(column.hint)+'</div>':"");
      (column.ids||[]).forEach(function(record){
        if(!record||!record.id)throw Error("Observation record requires its stable public ID");
        if(record.href)body+='<p class="small">'+recordLink({href:record.href,
          label:record.label||record.id})+'</p>';
        else if(record.action)body+='<p class="small">'+matrixCommand({
          label:record.action.label||record.id,attributes:record.action.attributes})+'</p>';
        else body+='<p class="muted small">'+escape(record.id)+'</p>';
      });
      return '<td data-observation-column="'+escape(key)+
        '" data-observation-count="'+escape(observations)+'">'+body+'</td>';
    }
    function rowCells(row,cellOptions) {
      return columns.keys() ? projection.columnLabels.map(function(column){
        var match=(row.columns||[]).find(function(entry){
          return String(entry.key)===String(column.key);});
        return cell(match?Object.assign({},match,{key:column.key}):
          {key:column.key,observations:0},cellOptions);
      }).join("") : "";
    }
    var counts=projection.counts||[];
    if(!Array.isArray(counts))throw Error("Observation counts must be a list");
    var visibleCounts=counts.filter(function(entry){
      return entry&&entry.label&&entry.value!=null&&entry.value!=="";});
    return '<section class="shared-observation-matrix" data-shared-observation-matrix="'+
      escape(options.domain||"observations")+'" data-observation-mode="'+escape(mode)+'">'+
      (visibleCounts.length?'<p class="small" data-observation-counts>'+
        visibleCounts.map(function(entry){
          return escape(String(entry.value))+" "+escape(entry.label);}).join(' · ')+'</p>':"")+
      (projection.rows.length?
        '<div class="shared-matrix-scroll"><table class="shared-observation-table"><thead><tr>'+
        '<th scope="col">'+escape(projection.rowAxis||"Row")+'</th>'+
        projection.columnLabels.map(function(column){
          return '<th scope="col" data-observation-label="'+escape(column.key)+'">'+
            escape(column.label)+'</th>';}).join("")+
        '</tr></thead><tbody>'+
        projection.rows.map(function(row){
          return '<tr data-observation-row="'+escape(row.key)+'"><th scope="row">'+
            escape(row.label||row.key)+
            (row.detail?'<div class="muted small">'+escape(row.detail)+'</div>':"")+
            (row.rowAction?'<div class="shared-row-action">'+matrixCommand(row.rowAction)+'</div>':
             row.rowHref?'<div class="shared-row-action">'+recordLink(row.rowHref)+'</div>':"")+
            '</th>'+rowCells(row,options)+'</tr>';}).join("")+
        (projection.footerRow?'<tr data-observation-footer="1"><th scope="row">'+
          escape(projection.footerRow.label||"")+'</th>'+
          rowCells(projection.footerRow,options)+'</tr>':"")+
        '</tbody></table></div>':
        '<p class="muted" data-observation-empty-matrix>'+
          escape(options.emptyText||"No persisted observation matches this filter.")+'</p>')+
      (projection.policy?'<p class="muted small">'+escape(projection.policy)+'</p>':"")+
      (projection.notices||[]).filter(function(value){return value!=null&&value!=="";})
        .map(function(value){return '<p class="muted small">'+escape(value)+'</p>';}).join("")+
      '</section>';
  }

  /* One measured-Run presentation: identity, provenance and only the metrics
   * the authorized source actually recorded. Unknown values stay unknown and a
   * theoretical forecast is never presented as a measured Run. */
  var RUN_KINDS=Object.freeze(["individual","framework","theoretical"]);
  function renderMeasuredRunDetail(projection, options) {
    options=options||{};
    var mode=domainMode(options.mode);
    if(!projection||typeof projection!=="object"||Array.isArray(projection))
      throw Error("Authorized Run projection required");
    if(!projection.id)throw Error("Run projection requires its stable public ID");
    var kind=String(projection.kind||"individual");
    if(!RUN_KINDS.includes(kind))throw Error("Unsupported Run kind");
    var theoretical=kind==="theoretical"||projection.theoretical===true;
    var revision=projection.revision?String(projection.revision):"";
    var pinned=options.pinnedRevision?String(options.pinnedRevision):"";
    var mismatch=!!pinned&&(!revision||revision!==pinned);
    if(!Array.isArray(projection.metrics||[]))throw Error("Run metrics must be a list");
    var metrics=(projection.metrics||[]).filter(function(metric){
      return metric&&metric.label&&metric.value!==null&&metric.value!==undefined&&
        String(metric.value)!=="";});
    var identity=[projection.id,revision,projection.outcome||projection.status]
      .filter(function(value){return value!=null&&value!=="";}).map(escape);
    var context=[projection.taskName||projection.taskId,projection.testCaseName||projection.testCaseId,
      projection.testCaseRevision?"pinned "+projection.testCaseRevision:"",
      projection.configurationLabel].filter(function(value){return value!=null&&value!=="";}).map(escape);
    return '<article class="shared-run-detail" data-shared-run-detail="'+escape(kind)+
      '" data-run-mode="'+escape(mode)+'" data-run-provenance="'+
      (theoretical?"theoretical":"measured")+'">'+
      '<p class="muted small"><span class="tag '+(theoretical?"purple":"green")+'">'+
      (theoretical?"THEORETICAL — never measured":"MEASURED RUN")+'</span> '+
      identity.join(' · ')+'</p>'+
      '<h3>'+escape(projection.title||projection.testCaseName||projection.id)+'</h3>'+
      (context.length?'<p class="muted small">'+context.join(' · ')+'</p>':"")+
      (mismatch?
        '<p role="alert" class="ux-history-warning" data-run-pin-mismatch>Requested historical '+
        'revision '+escape(pinned)+' cannot be verified from this projection. The current '+
        'metrics are not substituted for the pinned original.</p>':
        (metrics.length?'<div class="shared-run-metrics">'+metrics.map(function(metric){
          return '<div><span class="muted small">'+escape(metric.label)+'</span><strong>'+
            escape(metric.value)+'</strong>'+
            (metric.hint?'<span class="muted small">'+escape(metric.hint)+'</span>':"")+'</div>';
        }).join("")+'</div>':'<p class="muted" data-run-metrics-unknown>No metric was recorded '+
          'for this Run; unknown values are not estimated.</p>'))+
      '<p class="muted small">'+(theoretical?
        "A theoretical forecast is a projection, never measured Run evidence.":
        "Metrics come from the recorded Run; unavailable fields stay unknown.")+'</p>'+
      (projection.links||[]).map(function(link){return '<p>'+recordLink(link)+'</p>';}).join("")+
      (projection.notices||[]).filter(function(value){return value!=null&&value!=="";})
        .map(function(value){return '<p class="muted small">'+escape(value)+'</p>';}).join("")+
      '</article>';
  }

  /* One review/publication action bar: the reviewer or writer sees the same
   * labels and ordering in both modes; each mode supplies only the transitions
   * its own authorization and business rules permit. */
  var LIFECYCLE_ACTION_LABELS=Object.freeze({
    forecasts:Object.freeze({stage:"Stage forecast",review:"Mark reviewed",
      publish:"Publish as theoretical",unpublish:"Unpublish",rework:"Request rework",
      fork:"Create new revision"}),
    recommendations:Object.freeze({submit:"Submit for review",
      publish:"Review and publish",unpublish:"Withdraw publication",
      revise:"New draft revision",history:"Original history / evidence"}),
    campaigns:Object.freeze({start:"Start / open campaign",close:"Close full plan",
      close_partial:"Close partial review",rework:"Request rework",
      publish:"Review / publish selected Runs",reopen:"Reopen",
      unpublish:"Unpublish to review",archive:"Archive campaign",restore:"Restore archive"})
  });
  /* Which transitions each canonical campaign status permits. Permissions stay
   * with each adapter: this list only keeps the offered lifecycle identical. */
  var CAMPAIGN_TRANSITIONS=Object.freeze({
    planned:["start"],in_progress:["close","close_partial"],
    under_review:["rework","publish","reopen"],published:["unpublish","reopen"]
  });
  function campaignLifecycleActionKeys(status) {
    var key=String(status||"");
    if(key==="archived")return ["restore"];
    var keys=CAMPAIGN_TRANSITIONS[key];
    if(!keys)throw Error("Unsupported campaign lifecycle status");
    return keys.concat(["archive"]);
  }
  function renderLifecycleActions(actions, options) {
    options=options||{};
    var mode=domainMode(options.mode),domain=String(options.domain||"");
    if(!/^[a-z][a-z0-9-]*$/.test(domain))
      throw Error("Explicit lifecycle domain required");
    if(!Array.isArray(actions))throw Error("Authorized lifecycle actions required");
    return '<div class="shared-lifecycle" data-shared-lifecycle="'+escape(domain)+
      '" data-lifecycle-mode="'+escape(mode)+'">'+
      (options.notice?'<p class="muted small">'+escape(options.notice)+'</p>':"")+
      actions.map(function(action){
        if(!action||!action.key)throw Error("Lifecycle action requires its exact key");
        var domainLabels=LIFECYCLE_ACTION_LABELS[domain];
        if(!domainLabels)throw Error("Unknown lifecycle domain labels");
        var label=action.label||domainLabels[action.key];
        if(!label)throw Error("Unknown lifecycle action key");
        return matrixCommand({label:label,attributes:action.attributes});
      }).join("")+
      (actions.length?"":'<p class="muted small" data-shared-lifecycle-empty>'+
        escape(options.emptyText||"No lifecycle transition is permitted for this record.")+
        '</p>')+'</div>';
  }

  /* One campaign lifecycle presentation; each mode maps its own status names. */
  var CAMPAIGN_LIFECYCLE=Object.freeze([
    {key:"planned",label:"Planned"},
    {key:"in_progress",label:"In progress / running"},
    {key:"under_review",label:"Under review"},
    {key:"published",label:"Published"}
  ]);
  function campaignLifecycleSteps(status) {
    var key=String(status||"");
    var index=CAMPAIGN_LIFECYCLE.findIndex(function(step){return step.key===key;});
    if(index<0)throw Error("Unsupported campaign lifecycle status");
    return CAMPAIGN_LIFECYCLE.map(function(step,i){
      return {label:step.label,state:i<index?"done":(i===index?"current":"todo")};});
  }

  /* Authorized field specifications per domain. A specification is shared
   * presentation only: mode-specific keys, vocabularies and mode-only inputs
   * stay explicit here instead of being re-declared in each controller. */
  var WATCH_SOURCE_FIELDS=Object.freeze([
    {key:"name",demoKey:"title",label:"Title",kind:"text",maxlength:160,span:true,
     serverRequired:true,demoRequired:false},
    {key:"claim",demoKey:"assessment",label:"Original claim / observation",kind:"textarea",
     rows:4,maxlength:10000,span:true,serverRequired:true,demoRequired:false,
     help:"External claims and estimates are never reproduced experiments."},
    {key:"citation",demoKey:"source",label:"Citation / publication reference",kind:"text",
     maxlength:2000,span:true},
    {key:"url",label:"Source URL (optional)",kind:"url",maxlength:2048,span:true},
    {key:"source_type",demoKey:"type",label:"Source type",kind:"select",
     options:[["research","research"],["provider_notice","provider_notice"],
       ["benchmark","benchmark"],["documentation","documentation"],["other","other"]],
     demoOptions:[["Independent benchmark","Independent benchmark"],["Vendor claim","Provider/vendor claim"],
       ["Research paper","Research paper"],["Expert estimate","Workgroup estimate"],["Other","Other literature"]]},
    {key:"confidence",label:"Confidence",kind:"select",
     options:[["unknown","unknown"],["low","low"],["medium","medium"],["high","high"]],
     demoOptions:[["low","Low / unverified"],["medium","Medium"],["high","High"]]},
    {key:"publication",modes:["demo"],label:"Source visibility",kind:"select",
     options:[["draft","Workgroup only"],["published","Published / shareable"]]},
    {key:"signal",modes:["demo"],label:"Related technology watch signal",kind:"select",
     options:[],blankLabel:"None"},
    {key:"component",modes:["demo"],label:"Related catalog component",kind:"select",
     options:[],blankLabel:"Not linked"},
    {key:"published_on",modes:["server"],label:"Publication date ISO YYYY-MM-DD (optional)",
     kind:"text",maxlength:40},
    {key:"retrieved_on",modes:["server"],label:"Retrieval date ISO YYYY-MM-DD (optional)",
     kind:"text",maxlength:40},
    {key:"limitations",label:"Limitations / caveats",kind:"textarea",rows:3,maxlength:10000,span:true},
    {key:"extensions",modes:["server"],label:"Unknown / future metadata (JSON object)",
     kind:"textarea",rows:4,span:true,help:"Preserve unknown properties; never invent values."}
  ]);
  var WATCH_ENTRY_FIELDS=Object.freeze([
    {key:"name",demoKey:"title",label:"Signal or hypothesis title",kind:"text",maxlength:160,
     span:true,serverRequired:true,demoRequired:false},
    {key:"kind",modes:["demo"],label:"Technology theme",kind:"select",
     options:[["Model","Model"],["Provider","Provider"],["Harness","Harness"],
       ["Configuration","Configuration / combination"],["Tool","Tools and integrations"],
       ["Research","Research finding"]]},
    {key:"status",modes:["demo"],label:"Evidence collection status",kind:"select",
     options:[["watching","Under review"],["pending","Collecting evidence"],["reviewed","Documented"]]},
    {key:"publication",modes:["demo"],label:"Watch evidence visibility",kind:"select",
     options:[["draft","Workgroup only — Draft"],["published","Published to readers"]]},
    {key:"hypothesis",label:"Reasoned hypothesis / intuition",kind:"textarea",rows:3,
     maxlength:10000,span:true,serverRequired:true,demoRequired:false,
     help:"A hypothesis is a reasoned hypothesis, never measured evidence."},
    {key:"assumptions",label:"Assumptions and conditions for engineering use",kind:"textarea",
     rows:3,maxlength:10000,span:true},
    {key:"notes",modes:["server"],label:"Notes",kind:"textarea",rows:3,maxlength:10000,span:true},
    {key:"potential",modes:["demo"],label:"Expected benefit / engineering activities to investigate",
     kind:"textarea",rows:3,maxlength:10000,span:true},
    {key:"sources",modes:["server"],label:"Attach existing exact Research Source revision(s)",
     kind:"multi",size:6,span:true,options:[],
     help:"Reusing a source never duplicates or deletes its original bytes; existing revision pins stay unchanged."},
    {key:"extensions",modes:["server"],label:"Unknown / future metadata (JSON object)",
     kind:"textarea",rows:4,span:true}
  ]);
  var FORECAST_FIELDS=Object.freeze([
    {key:"name",label:"Theoretical forecast title",kind:"text",maxlength:160,span:true,
     serverRequired:true,demoRequired:false,
     help:"A theoretical configuration, never a measured result."},
    {key:"task_id",demoKey:"task",label:"Engineering task receiving this expected performance",
     kind:"select",options:[],span:true},
    {key:"watch_links",modes:["server"],label:"Supporting exact Watch signals (multi-select)",
     kind:"multi",size:6,span:true,options:[]},
    {key:"model",demoKey:"modelComponent",label:"Model (theoretical)",kind:"select",options:[]},
    {key:"provider",demoKey:"providerComponent",label:"Provider (theoretical)",kind:"select",options:[]},
    {key:"harness",demoKey:"harnessComponent",label:"Harness (theoretical)",kind:"select",options:[]},
    {key:"configuration",demoKey:"config",label:"Assumed configuration, tools, versions and constraints",
     kind:"textarea",rows:4,span:true,serverRequired:true,demoRequired:false},
    {key:"assumptions",modes:["server"],label:"Assumptions (JSON object)",kind:"textarea",
     rows:4,span:true},
    {key:"predicted_metrics",modes:["server"],label:"Theoretical predicted metrics (JSON, unknown=null)",
     kind:"textarea",rows:6,span:true,help:"Never present a predicted value as a measured one."},
    {key:"quality",modes:["demo"],label:"Estimated quality /100",kind:"number"},
    {key:"acceptance",modes:["demo"],label:"Estimated DoD acceptance (%)",kind:"number"},
    {key:"autonomy",modes:["demo"],label:"Estimated agent autonomy /100",kind:"number"},
    {key:"humanMinutes",modes:["demo"],label:"Estimated human involvement (minutes)",kind:"number"},
    {key:"aiCost",modes:["demo"],label:"Expected model and tooling cost (€)",kind:"number"},
    {key:"confidence",label:"Confidence level",kind:"select",
     options:[["unknown","unknown"],["low","low"],["medium","medium"],["high","high"]],
     demoOptions:[["low","Low"],["medium","Medium"],["high","High"]]},
    {key:"rationale",label:"Inference and justification: why these metrics?",kind:"textarea",
     rows:4,span:true,serverRequired:true,demoRequired:false},
    {key:"uncertainty",label:"Uncertainty, caveats, what still needs validation",kind:"textarea",
     rows:3,span:true},
    {key:"hourlyRate",modes:["demo"],label:"Assumed engineer hourly cost (€)",kind:"number",min:0},
    {key:"revision",modes:["demo"],label:"Projection revision",kind:"text",maxlength:40},
    {key:"reviewNotes",modes:["demo"],label:"Reviewer notes (recorded for future review)",
     kind:"textarea",rows:3,span:true}
  ]);
  var FEEDBACK_THREAD_FIELDS=Object.freeze([
    {key:"title",label:"Short title",kind:"text",maxlength:160,span:true,serverRequired:true,demoRequired:false},
    {key:"kind",demoKey:"type",label:"Kind",kind:"select",
     options:[["feedback","feedback"],["question","question"],["idea","idea"],
       ["request","request"],["discussion","discussion"]],
     demoOptions:[["Experience","Real-use feedback"],["Idea","New idea"],
       ["Need","Missing capability / unmet need"]]},
    {key:"scope",modes:["server"],label:"Visibility",kind:"select",
     options:[["public","Public"],["internal","Workgroup only"]]},
    {key:"context_id",demoKey:"target",label:"Related catalog object reference",
     kind:"select",serverKind:"text",options:[],span:true,blankLabel:"General / unspecified",
     serverPlaceholder:"tsk-… or sol-…",
     help:"Only public task, solution and technology catalog references can be linked; the exact revision is pinned."},
    {key:"body",label:"Feedback / first message",kind:"textarea",rows:5,maxlength:16000,
     span:true,serverRequired:true,demoRequired:false}
  ]);
  var FEEDBACK_REPLY_FIELDS=Object.freeze([
    {key:"visibility",label:"Visibility",kind:"select",
     options:[["public","Public"],["internal","Workgroup only"]],
     demoOptions:[["public","Public reply"],["internal","Workgroup-only note"]]},
    {key:"reply",serverKey:"body",label:"Response",kind:"textarea",rows:4,maxlength:16000,
     span:true,serverRequired:true,demoRequired:false,demoPlaceholder:"Write a reply…"}
  ]);
  var RECOMMENDATION_FIELDS=Object.freeze([
    {key:"name",demoKey:"recommendation",label:"Recommendation / suitable usage",
     kind:"textarea",demoKind:"textarea",serverKind:"text",rows:4,span:true,
     serverRequired:true,demoRequired:false},
    {key:"task_id",modes:["server"],label:"Engineering Task",kind:"select",options:[]},
    {key:"solution_id",modes:["server"],label:"Measured individual AI Solution",kind:"select",options:[]},
    {key:"decision",modes:["server"],label:"Decision",kind:"select",
     options:[["recommended","recommended"],["conditional","conditional"],
       ["not_recommended","not_recommended"]]},
    {key:"rationale",modes:["server"],label:"Engineering rationale",kind:"textarea",rows:3,
     span:true,serverRequired:true},
    {key:"limitations",label:"Limitations and conditions",kind:"textarea",rows:3,span:true},
    {key:"run_ids",modes:["server"],label:"Exact original individual Runs (multi-select)",
     kind:"multi",size:6,span:true,options:[],
     help:"Only genuine individual Runs can support an individual recommendation."},
    {key:"evaluation_id",modes:["server"],label:"Optional saved Evaluation",kind:"select",
     options:[],blankLabel:"No evaluation"},
    {key:"supersededBy",modes:["demo"],label:"Replacement / successor solution",kind:"select",
     options:[],span:true,blankLabel:"No successor selected"},
    {key:"publication",modes:["demo"],label:"Record publication status",kind:"select",
     options:[["draft","Draft"],["published","Published"],["superseded","Superseded"],
       ["retired","Retired"]]}
  ]);
  var GUIDE_RECIPE_FIELDS=Object.freeze([
    {key:"recipe_modules",modes:["server"],label:"Reusable modules (Ctrl/Command to select)",
     kind:"multi",size:5,span:true,options:[],
     help:"Reuse exact guide revisions; adding a module never rewrites the original."},
    {key:"recipe_spec",modes:["server"],label:"Recipe (JSON; optional)",kind:"textarea",rows:8,
     span:true,help:"OS/versions and variants. An empty value retires the recipe in a new immutable revision."}
  ]);
  var EVALUATION_FIELDS=Object.freeze([
    {key:"name",modes:["server"],label:"Evaluation title",kind:"text",maxlength:160,span:true,required:true},
    {key:"run_ids",modes:["server"],label:"Original measured Run IDs",kind:"textarea",rows:5,span:true,required:true,
     help:"One run-* ID per line. Theoretical forecast-* predictions are not measured Runs."},
    {key:"assessment",modes:["server"],label:"Interpretation",kind:"select",
     options:[["inconclusive","inconclusive"],["supported","supported"],["unsupported","unsupported"]]},
    {key:"selected_metrics",modes:["server"],label:"Measured metric fields to inspect",kind:"multi",size:6,
     span:true,options:[]},
    {key:"notes",modes:["server"],label:"Notes",kind:"textarea",rows:3,span:true},
    {key:"limitations",modes:["server"],label:"Limitations",kind:"textarea",rows:3,span:true}
  ]);

  // UX-R04: shared, text-only presentation boundary for business record lists.
  // Adapters supply authorized rows and permissible actions. Nothing here
  // fetches, persists, invents revisions, or interprets a business decision.
  function renderRecords(rows, options) {
    if(!Array.isArray(rows))throw Error("Authorized business records required");
    options=options||{};
    var domain=options.domain,mode=options.mode;
    if(!/^[a-z][a-z0-9-]*$/.test(domain||"")||!["demo","server"].includes(mode))
      throw Error("Explicit business domain and Demo/Server mode required");
    function attr(name,value){
      if(!/^data-[a-z][a-z0-9-]*$/.test(name))throw Error("Invalid business action attribute");
      return ' '+name+'="'+escape(value)+'"';
    }
    function command(action) {
      if(!action || !action.label)throw Error("Missing business action label");
      var attrs=action.attributes||{};
      var keys=Object.keys(attrs);
      if(!keys.length)throw Error("Business action without routing");
      return '<button type="button"'+keys.map(function(k){return attr(k,attrs[k]);}).join("")+
        '>'+escape(action.label)+'</button>';
    }
    function link(item){
      var url=String(item.href||"");
      if(!(url.startsWith("/")&&!url.startsWith("//"))&&!url.startsWith("?"))
        throw Error("Business link must be same-origin");
      return '<a href="'+escape(url)+'">'+escape(item.label||"Open detail")+'</a>';
    }
    if(!rows.length)return '<p class="muted" data-business-empty="'+escape(domain)+'">'+
      escape(options.emptyText||"No matching authorized records.")+'</p>';
    return '<div class="shared-business-list" data-business-domain="'+escape(domain)+'" data-business-mode="'+mode+'">'+
      rows.map(function(r){
        if(!r||!r.id)throw Error("Missing authorized record identity");
        var facts=(r.facts||[]).filter(function(v){return v!=null&&v!=="";});
        var notices=(r.notices||[]).filter(function(v){return v!=null&&v!=="";});
        var actions=r.actions||[],links=r.links||[];
        if(!Array.isArray(facts)||!Array.isArray(notices)||!Array.isArray(actions)||!Array.isArray(links))
          throw Error("Invalid record presentation");
        return '<article class="shared-business-record list-row" data-business-record="'+escape(r.id)+'">'+
          '<div class="shared-business-content"><h3>'+escape(r.title||r.id)+'</h3>'+
          '<p class="muted small shared-business-meta">'+
          [r.id,r.revision,r.status].concat(facts).filter(function(v){return v!=null&&v!=="";})
            .map(escape).join(' · ')+'</p>'+
          (r.description?'<p class="shared-business-description">'+escape(r.description)+'</p>':"")+
          notices.map(function(v){return '<p class="shared-business-note">'+escape(v)+'</p>';}).join("")+
          '</div><div class="shared-business-actions">'+links.map(link).join("")+actions.map(command).join("")+'</div></article>';
      }).join("")+'</div>';
  }


  function normalizedGuide(row,mode) {
    if (!row || (mode!=="demo" && mode!=="server"))
      throw Error("Explicit authorized Guide and mode required");
    var props=mode==="demo"?row:(row.properties||{});
    return {id:row.id||"",name:mode==="demo"?row.title:row.name,
      text:mode==="demo"?row.body:props.text,url:props.url||"",
      description:props.description||"",type:row.type,revision:row.revision||"",
      status:row.status||""};
  }
  function renderGuideFields(row,mode) {
    var g=normalizedGuide(row||{},mode),demo=mode==="demo";
    var keys=demo?["title","body"]:["name","text"];
    function field(name,label,value,kind,max,required) {
      var id="ux-guide-"+mode+"-"+name;
      var control=kind==="textarea"?
        '<textarea id="'+id+'" name="'+name+'" maxlength="'+max+'" rows="4">'+
          escape(value||"")+'</textarea>':
        '<input id="'+id+'" name="'+name+'" type="'+kind+'" maxlength="'+max+
          '" value="'+escape(value||"")+'"'+(required?" required":"")+'>';
      return '<div class="field span2 shared-guide-field"><label for="'+id+'">'+
        escape(label)+'</label>'+control+'</div>';
    }
    return '<div class="span2 shared-guide-fields" data-shared-guide-fields="'+mode+'">'+
      field(keys[0],"Guide title",g.name,"text",160,true)+
      field(keys[1],"Procedure text (optional if URL present)",g.text,"textarea",32768,false)+
      field("url","Setup URL (HTTP or HTTPS; optional if text present)",g.url,"url",2048,false)+
      field("description","Notes / description",g.description,"textarea",4000,false)+'</div>';
  }
  function renderGuideDetail(row,mode) {
    var g=normalizedGuide(row,mode),url=String(g.url||"").trim();
    var safe=/^https?:\/\/[^\s<>]+$/i.test(url);
    function field(label,value) {
      return value?'<section class="shared-guide-detail-field"><h4>'+escape(label)+'</h4>'+
        '<p style="white-space:pre-wrap;overflow-wrap:anywhere">'+escape(value)+'</p></section>':"";
    }
    return '<article class="shared-guide-detail" data-shared-guide-detail="'+mode+'">'+
      '<h3>'+escape(g.name||"Untitled guide")+'</h3><p class="muted small">'+
      [g.id,g.revision,g.type,g.status].filter(Boolean).map(escape).join(" · ")+'</p>'+
      field("Procedure",g.text)+field("Notes",g.description)+
      (safe?'<p>Setup reference: <a target="_blank" rel="noopener noreferrer" href="'+
        escape(url)+'">'+escape(url)+'</a></p>':
        url?'<p class="muted">Unsupported URL — link withheld.</p>':"")+'</article>';
  }


  // UX-R04 knowledge-domain details: explicit, text-only projection of
  // authorized Watch/source/Forecast records; never promotes hypotheses to Runs.
  function renderKnowledgeDetail(record, options) {
    options=options||{};
    var mode=options.mode,domain=options.domain;
    if(!record||!["demo","server"].includes(mode)||
       !["watch","sources","forecasts"].includes(domain))
      throw Error("Explicit authorized knowledge domain and mode required");
    var p=mode==="demo"?record:(record.properties||{});
    var title=mode==="demo"?(record.title||record.name):record.name;
    var fields=[],notes=[],facts=[];
    function add(label,value) {
      if(value!==undefined&&value!==null&&String(value)!=="")
        fields.push([label,value]);
    }
    if(domain==="forecasts") {
      facts.push("THEORETICAL — never measured");
      add("Confidence",p.confidence);
      add("Task",mode==="demo"?record.task:record.task_id);
      var metrics=mode==="demo"?{
        quality_score:record.quality, ai_cost_eur:record.aiCost,
        human_minutes:record.humanMinutes,acceptance:record.acceptance
      }:(p.predicted_metrics||{});
      add("Predicted quality / 100",metrics.quality_score);
      add("Estimated AI cost (EUR)",metrics.ai_cost_eur);
      add("Predicted human minutes",metrics.human_minutes);
      add("Rationale",p.rationale);
      add("Uncertainty",p.uncertainty);
      notes.push("Forecast values are projections, NOT measured Run evidence.");
    }else if(domain==="watch") {
      add("Hypothesis and expected benefit",p.hypothesis||p.summary);
      add("Potential activities",p.potential);
      add("Assumptions",p.assumptions);
      add("Notes",p.notes);
      add("Review state",p.review_state||record.status);
      add("Visibility",p.visibility||record.publication);
    }else {
      add("Source / reference",p.url||p.source);
      add("Original claim / observation",p.claim);
      add("Citation / publication",p.citation);
      add("Assessment",p.assessment);
      add("Uncertainty and limitations",p.limitations);
      add("Confidence",p.confidence);
      notes.push("External source material is not controlled experimental Run evidence.");
    }
    function section(label,value){
      return '<section class="shared-knowledge-property"><h4>'+escape(label)+'</h4>'+
        '<p style="white-space:pre-wrap;overflow-wrap:anywhere">'+escape(value)+'</p></section>';
    }
    return '<article class="shared-knowledge-detail" data-knowledge-domain="'+domain+
      '" data-knowledge-mode="'+mode+'"><h3>'+escape(title||"Unnamed record")+'</h3>'+
      '<p class="muted small">'+[record.id,record.revision,record.status||record.publication]
        .concat(facts).filter(function(v){return v!==undefined&&v!==null&&v!=="";})
        .map(escape).join(" · ")+'</p>'+
      fields.map(function(k){return section(k[0],k[1]);}).join("")+
      notes.map(function(n){return '<p class="muted small">'+escape(n)+'</p>';}).join("")+
      '</article>';
  }

  root.AICompassWorkgroup={ZONES:ZONES,STABLE:STABLE,SECTION_TO_DEMO:SECTION_TO_DEMO,
    SECTION_TO_SERVER:SECTION_TO_SERVER,canVisit:canVisit,renderMap:renderMap,
    breadcrumbs:breadcrumbs,attention:attention,href:href,renderList:renderList,
    serverProvider:serverProvider,demoProvider:demoProvider,mountSummary:mountSummary,renderCases:renderCases,renderCaseFields:renderCaseFields,renderCaseDetail:renderCaseDetail,
    renderRecords:renderRecords,renderGuideFields:renderGuideFields,
    renderGuideDetail:renderGuideDetail,renderKnowledgeDetail:renderKnowledgeDetail,
    MATRIX_STATES:MATRIX_STATES,normalizeMatrixPlan:normalizeMatrixPlan,
    matrixTotals:matrixTotals,renderCampaignMatrix:renderCampaignMatrix,
    renderMatrixCellDetail:renderMatrixCellDetail,
    renderMatrixDecisionFields:renderMatrixDecisionFields,
    renderDomainFields:renderDomainFields,renderDomainDetail:renderDomainDetail,
    renderDomainStatus:renderDomainStatus,renderStepper:renderStepper,renderThread:renderThread,
    renderRevisionHistory:renderRevisionHistory,
    CAMPAIGN_LIFECYCLE:CAMPAIGN_LIFECYCLE,campaignLifecycleSteps:campaignLifecycleSteps,
    LIFECYCLE_ACTION_LABELS:LIFECYCLE_ACTION_LABELS,
    RUN_KINDS:RUN_KINDS,renderMeasuredRunDetail:renderMeasuredRunDetail,
    renderObservationMatrix:renderObservationMatrix,
    renderComposedSetup:renderComposedSetup,
    campaignLifecycleActionKeys:campaignLifecycleActionKeys,
    renderLifecycleActions:renderLifecycleActions,
    WATCH_SOURCE_FIELDS:WATCH_SOURCE_FIELDS,WATCH_ENTRY_FIELDS:WATCH_ENTRY_FIELDS,
    FORECAST_FIELDS:FORECAST_FIELDS,FEEDBACK_THREAD_FIELDS:FEEDBACK_THREAD_FIELDS,
    FEEDBACK_REPLY_FIELDS:FEEDBACK_REPLY_FIELDS,
    RECOMMENDATION_FIELDS:RECOMMENDATION_FIELDS,EVALUATION_FIELDS:EVALUATION_FIELDS,
    GUIDE_RECIPE_FIELDS:GUIDE_RECIPE_FIELDS,
    coverageGapNotice:coverageGapNotice};
})(window);
