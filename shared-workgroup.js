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

  root.AICompassWorkgroup={ZONES:ZONES,STABLE:STABLE,SECTION_TO_DEMO:SECTION_TO_DEMO,
    SECTION_TO_SERVER:SECTION_TO_SERVER,canVisit:canVisit,renderMap:renderMap,
    breadcrumbs:breadcrumbs,attention:attention,href:href,renderList:renderList,
    serverProvider:serverProvider,demoProvider:demoProvider,mountSummary:mountSummary,renderCases:renderCases};
})(window);
