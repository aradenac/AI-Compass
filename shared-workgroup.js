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
    opportunities:"management",deployment:"management",engineer:"tasks",activity:"activity"});
  var SECTION_TO_SERVER = Object.freeze({feedback:"server-discussions",watch:"server-watch",
    catalog:"server-model-catalog",tasks:"server-task-tree",testdesign:"server-test-cases",
    forecasts:"server-forecasts",benchmark:"server-campaigns",results:"server-results",
    recommendations:"server-recommendations",guides:"server-guides",
    opportunities:"server-planning",deployment:"server-planning",engineer:"server-engineer",
    activity:"server-activity"});
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
            return '<a class="shared-studio-block'+(CORE.includes(b[0])?" shared-studio-core":"")+
              '" data-studio-section="'+escape(b[0])+'" href="'+escape(href(mode,b[0],identity))+
              '"><strong>'+escape(b[1])+'</strong>'+
              (Number.isInteger(n)&&n>0?'<span class="shared-attention" aria-label="'+n+
                ' unresolved records">'+n+' requiring review</span>':"")+
              '<small>'+escape(b[2])+'</small></a>';
          }).join("")+'</div></section>';
      }).join("")+
      '<p class="shared-studio-relations">Needs → Tasks → Test Design → Campaign Runs → Results → Recommendations and Guides → User adoption → Feedback. Technology Watch and Forecasts inform studies without manufacturing measured evidence.</p>'+
      '<a href="'+escape(href(mode,"activity",identity))+'">Activity Feed · historical changes</a></div>';
  }
  function breadcrumbs(mode,section,detail) {
    return root.AICompassContext.breadcrumb(mode,"workgroup",section,detail);
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
            escape(configuration.label)+'<span class="muted small"> '+
            escape(configuration.kind||"individual")+' · '+escape(configuration.id)+'</span></th>';
        }).join("")+
        '</tr></thead><tbody>'+
        rowIds.map(function(testCaseId){
          var testCase=read.testCases.get(testCaseId);
          return '<tr><th scope="row">'+escape(testCase?testCase.name:testCaseId)+
            '<span class="muted small">'+escape(testCaseId)+
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
        (testCase&&testCase.href?'<p>'+matrixHref({href:testCase.href,label:"Open Test Case context"})+'</p>':""))+
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
    renderMatrixDecisionFields:renderMatrixDecisionFields};
})(window);
