/* UX-R03: safe, version-aware contextual links used by both frontends.
 * Navigation state is ephemeral browser UI only; no access grant, no data store,
 * and never any remote URL or cross-mode fallback. */
(function (root) {
  "use strict";
  var validWorkspaces = ["workgroup","engineer","management","maintenance"];
  var labels = {studio:"Workgroup Studio",feedback:"Feedback & Discussions",
    watch:"Technology Watch",catalog:"Technology Catalog",tasks:"Tasks",
    testdesign:"Test Design",forecasts:"Theoretical Forecasts",
    benchmark:"Benchmark Workspace",results:"Results Explorer",
    recommendations:"Recommendations",guides:"Setup Guides",activity:"Activity Feed",
    opportunities:"Opportunities",deployment:"Deployment & Resources",
    engineer:"Engineer Workspace",home:"Overview",environment:"OS Environment",
    planning:"Planning & Resources",users:"Users & Access",account:"Account",
    audit:"Audit & Changes",health:"Data Health"};
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g,function(c){
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
  }
  function modeOf(url) {
    var params=url.searchParams;
    return params.get("mode")==="server" ||
      (url.pathname==="/maintenance" && params.get("mode")!=="demo") ? "server":"demo";
  }
  function normalizeOrigin(raw, mode) {
    if(typeof raw!=="string" || !raw.startsWith("/") || raw.startsWith("//") ||
       raw.length>1800 || /[\u0000-\u001f]/.test(raw))return null;
    try {
      var u=new URL(raw,root.location.origin);
      if(u.origin!==root.location.origin || !["/","/maintenance"].includes(u.pathname) ||
         modeOf(u)!==mode)return null;
      // Never nest origins and never route to a foreign mode, protocol or host.
      u.searchParams.delete("from");
      return u.pathname+u.search+u.hash;
    } catch (_) {return null;}
  }
  function currentRelative() {return root.location.pathname+root.location.search+root.location.hash;}
  function route(mode,workspace,section,params) {
    if(!["demo","server"].includes(mode))throw Error("Invalid UI mode");
    if(!validWorkspaces.includes(workspace))throw Error("Invalid workspace");
    var path=workspace==="maintenance" && mode==="server"?"/maintenance":"/";
    var u=new URL(path,root.location.origin);
    u.searchParams.set("mode",mode);
    if(path==="/")u.searchParams.set("workspace",workspace);
    if(section)u.searchParams.set("section",section);
    params=params||{};
    ["record","revision","task","solution","view","q","profile","scenario"].forEach(function(k){
      if(params[k]!=null && String(params[k])!=="")
        u.searchParams.set(k,String(params[k]).slice(0,400));
    });
    var origin=params.from==null?normalizeOrigin(currentRelative(),mode):
      normalizeOrigin(params.from,mode);
    if(origin && origin!==u.pathname+u.search)
      u.searchParams.set("from",origin);
    return u.pathname+u.search;
  }
  function returnTo(mode,fallback) {
    var params=new URLSearchParams(root.location.search);
    return normalizeOrigin(params.get("from"),mode) || fallback;
  }
  function breadcrumb(mode,workspace,section,record,revision) {
    var home=route(mode,workspace,workspace==="workgroup"?"studio":"home",{from:""});
    var self=route(mode,workspace,section||"home",{from:""});
    var from=returnTo(mode,home);
    var label=labels[section]||section||"Overview";
    var html='<nav class="ux-context-breadcrumbs" aria-label="Breadcrumb">' +
      '<a href="'+esc(home)+'">'+esc(workspace==="workgroup"?"Workgroup Studio":
        workspace==="maintenance"?"Maintenance & Governance":
        workspace==="engineer"?"My AI Workspace":"Management Insights")+'</a>';
    if(section && section!=="home" && section!=="studio" && section!=="audit"){
      html+=' <span aria-hidden="true">›</span> <a href="'+esc(self)+'">'+esc(label)+'</a>';
    }
    if(record){
      html+=' <span aria-hidden="true">›</span> <span class="ux-context-record">' +
        esc(record)+'</span>';
    }
    if(revision){
      html+=' <span class="ux-pinned-revision" aria-label="Requested pinned revision">' +
        'Requested revision '+esc(revision)+' (verify exact history)</span>';
    }
    if(from && from!==self && from!==home)
      html+=' <a class="ux-return-link" href="'+esc(from)+'">← Return to origin</a>';
    return html+"</nav>";
  }
  function syncContext(host,mode,workspace,section) {
    if(!host)return;
    var params=new URLSearchParams(root.location.search);
    host.innerHTML=breadcrumb(mode,workspace,section,
      params.get("record"),params.get("revision"));
  }
  function contextualLink(mode,workspace,section,id,revision) {
    return route(mode,workspace,section,{record:id,revision:revision});
  }
  function formatFields(row) {
    // Current record description, never an inferred historical revision.
    var properties=row && row.properties||{};
    var rows=[],keys=[
      ["description","Description"],["summary","Summary"],["objective","Objective"],
      ["rationale","Rationale"],["decision","Decision"],["limitations","Limitations"],
      ["source_url","Source URL"],["url","Reference URL"],["owner","Owner"],
      ["author","Author"],["visibility","Visibility"],["publication","Publication"],
      ["review_state","Review"],["status","Status"],["task_id","Task ID"],
      ["solution_id","Solution ID"],["campaign_id","Campaign ID"],
      ["test_case_id","Test Case ID"],["created_at","Created"]];
    keys.forEach(function(pair){
      var k=pair[0],v=row[k]==null?properties[k]:row[k];
      if(typeof v==="string" && v.trim()){
        if(/_url$/.test(k)||k==="url"){
          var safe=/^https?:\/\//.test(v)?v:null;
          if(safe)rows.push('<dt>'+esc(pair[1])+'</dt><dd><a target="_blank" rel="noopener noreferrer" href="'+esc(safe)+'">'+esc(v)+'</a></dd>');
        }else rows.push('<dt>'+esc(pair[1])+'</dt><dd>'+esc(v.slice(0,2000))+'</dd>');
      }
    });
    return rows.length?'<dl class="ux-context-properties">'+rows.join("")+'</dl>':
      '<p class="muted">No descriptive fields supplied by the authorized record.</p>';
  }
  function recordDetails(row,section,mode,requestedRevision) {
    var props=row.properties||{};
    var id=row.id||"",rev=row.revision||row.case_version||"";
    var current=String(rev||"");
    var mismatched=requestedRevision && requestedRevision!==current;
    var title=row.name||row.title||row.text||row.id||"Untitled";
    var link=route(mode,"workgroup",section,{view:"editor",record:id,revision:requestedRevision||""});
    var html='<section class="ux-context-detail" aria-label="Selected record detail">' +
      '<h3>'+esc(title)+'</h3><p class="muted">'+esc(id)+
      (current?' · Current revision '+esc(current):"")+'</p>';
    if(mismatched) {
      html+='<p role="alert" class="ux-history-warning">Requested historical revision '+
        esc(requestedRevision)+' cannot be verified from the current list. '+
        'No current record is substituted. Open the authorized original history.</p>';
    } else {
      html+=formatFields(row);
      html+='<p class="muted small">Current authorized projection. Historical source '+
        'revisions are read only from the domain history, never assumed from this view.</p>';
    }
    html+='<a href="'+esc(link)+'">Open domain workspace / immutable revision history</a>';
    if(!mismatched)
      html+='<details class="ux-advanced-source"><summary>Advanced: inspect current source fields</summary>'+
        '<pre></pre></details>';
    html+='</section>';
    return {html:html,raw:mismatched?null:row};
  }
  root.AICompassContext={route:route,returnTo:returnTo,normalizeOrigin:normalizeOrigin,
    breadcrumb:breadcrumb,syncContext:syncContext,contextualLink:contextualLink,
    formatFields:formatFields,recordDetails:recordDetails,esc:esc,labels:labels};
})(window);
