/* PLAT-22: Server-only Recommendations under Knowledge & Collaboration.
   Real REST/CSRF only. Independent seeded Demo remains unchanged. */
(function(){
"use strict";
function mount(root,csrf,escapeHtml){
  var active=false,writer=false,reviewer=false,generation=0,activeDraft=null;
  var recommendations=[],tasks=[],solutions=[],runs=[],evaluations=[];
  function $(q){return root.querySelector(q);}
  function esc(value){return escapeHtml(value==null?"":String(value));}
  function option(id,label,selected){
    return '<option value="'+esc(id)+'"'+(selected?' selected':'')+'>'+esc(label)+'</option>';
  }
  async function api(path,method,payload){
    var options={method:method||"GET",credentials:"same-origin",cache:"no-store"};
    if(method&&method!=="GET"){
      options.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
      options.body=JSON.stringify(payload||{});
    }
    var response=await fetch("/api/v1/"+path,options);
    var result=await response.json().catch(function(){return {};});
    if(!response.ok)throw(window.AICompassRuntime&&window.AICompassRuntime.httpError?
      window.AICompassRuntime.httpError(response.status,result):
      Error(result.detail||result.error||"HTTP "+response.status));
    return result;
  }
  function failure(error){
    return window.AICompassRuntime&&window.AICompassRuntime.failureInfo?
      window.AICompassRuntime.failureInfo(error):{conflict:false,detail:error&&error.message};
  }
  function status(message,error){
    var node=$("#rec-status");
    if(node){
      node.className=error?"server-status server-error":"server-status";
      node.innerHTML=window.AICompassWorkgroup.renderDomainStatus({
        mode:"server",state:error?"error":"ok",message:message==null?"":String(message)});
    }
  }
  function init(){
    root.innerHTML='<div class="server-model-toolbar"><div>'+
      '<h2>Knowledge & Collaboration · Recommendations</h2>'+
      '<p class="muted small">Decisions based on real measured individual Runs. New evidence requires explicit review; revisions and old published decisions remain immutable.</p></div>'+
      '<button type="button" id="rec-refresh">Refresh</button></div>'+
      '<p id="rec-status" role="status" class="server-status"></p>'+
      (writer?'<button type="button" id="rec-create">+ Draft recommendation</button>':'')+
      '<label>Filter engineering Task<select id="rec-task-filter">'+option("","All Tasks",true)+'</select></label>'+
      '<label>Filter measured Solution<select id="rec-solution-filter">'+option("","All Solutions",true)+'</select></label>'+
      '<div id="rec-list" class="server-card"></div>'+
      '<section id="rec-editor" class="server-card" hidden></section>'+
      '<section id="rec-detail" class="server-card" hidden></section>';
    $("#rec-refresh").addEventListener("click",refresh);
    $("#rec-task-filter").addEventListener("change",render);
    $("#rec-solution-filter").addEventListener("change",render);
    if(writer)$("#rec-create").addEventListener("click",function(){form(null);});
    $("#rec-list").addEventListener("click",function(event){
      var button=event.target.closest("button[data-recommendation]");
      if(!button)return;
      var row=recommendations.find(function(x){return x.id===button.dataset.recommendation;});
      if(!row)return;
      var action=button.dataset.action;
      if(action==="history")detail(row);
      if(action==="edit"&&writer)form(row);
      if(action==="submit"&&writer)transition(row,"submit");
      if(action==="publish"&&reviewer)transition(row,"publish");
      if(action==="unpublish"&&reviewer)transition(row,"unpublish");
    });
  }
  async function refresh(){
    if(!active)return;
    var ticket=++generation;
    status("Loading authoritative Server recommendations and original references…");
    try{
      var responses=await Promise.all([api("recommendations"),api("tasks"),
        api("solutions"),api("runs"),api("evaluations")]);
      if(!active||ticket!==generation)return;
      recommendations=responses[0].results||[];
      tasks=responses[1].results||[];
      solutions=responses[2].results||[];
      runs=(responses[3].results||[]).filter(function(x){return x.kind==="individual";});
      evaluations=responses[4].results||[];
      [["rec-task-filter",tasks,"All Tasks"],["rec-solution-filter",solutions,"All Solutions"]]
        .forEach(function(group){
          var field=$("#"+group[0]),selected=field.value;
          field.innerHTML=option("",group[2],selected==="")+
            group[1].map(function(x){return option(x.id,x.name||x.id,selected===x.id);}).join("");
        });
      render();status(recommendations.length+" real persisted recommendation(s), no Demo data imported.");
    }catch(error){
      if(!active||ticket!==generation)return;
      recommendations=[];tasks=[];solutions=[];runs=[];evaluations=[];
      render();status("Real Server recommendations unavailable: "+error.message,true);
    }
  }
  function render(){
    var task=$("#rec-task-filter")&&$("#rec-task-filter").value;
    var solution=$("#rec-solution-filter")&&$("#rec-solution-filter").value;
    var shown=recommendations.filter(function(x){
      return (!task||x.task_id===task)&&(!solution||x.solution_id===solution);
    });
    // Canonical transition wording comes from the shared lifecycle labels so a
    // future Demo workflow cannot drift from the authenticated Server.
    var lifecycle=window.AICompassWorkgroup.LIFECYCLE_ACTION_LABELS.recommendations;
    $("#rec-list").innerHTML=window.AICompassWorkgroup.renderRecords(shown.map(function(r){
      var p=r.properties||{},actions=[
        {label:lifecycle.history,
         attributes:{"data-recommendation":r.id,"data-action":"history"}}
      ];
      if(writer)actions.push({label:lifecycle.revise,
        attributes:{"data-recommendation":r.id,"data-action":"edit"}});
      if(writer&&r.state==="draft")actions.push({label:lifecycle.submit,
        attributes:{"data-recommendation":r.id,"data-action":"submit"}});
      if(reviewer&&r.state==="in_review")actions.push({label:lifecycle.publish,
        attributes:{"data-recommendation":r.id,"data-action":"publish"}});
      if(reviewer&&r.state!=="unpublished")actions.push({label:lifecycle.unpublish,
        attributes:{"data-recommendation":r.id,"data-action":"unpublish"}});
      var notices=[];
      if(r.review_needed)notices.push("Review required: "+r.reason+". "+
        (r.new_run_ids||[]).length+" new controlled Run(s), "+
        (r.contradictory_run_ids||[]).length+" failed. Published decision remains frozen.");
      if(r.eligible_for_current_suitability===false)
        notices.push("Not currently qualified by active published evidence. Evidence freshness: "+
          (r.evidence_freshness||"unknown")+". Source evidence withdrawn or superseded.");
      else notices.push("Qualification inputs current as of last review.");
      return {id:r.id,title:r.name,revision:r.revision,status:r.state,
        description:p.rationale||"",facts:[p.decision,r.task_id,r.solution_id,
          (r.run_refs||[]).length+" original Run(s)",
          "Reviewer: "+(r.reviewed_by||"awaiting review")],
        notices:notices,actions:actions};
    }),{domain:"recommendations",mode:"server",
        emptyText:"No permitted recommendations in Server. Drafts are workgroup-only."});
  }

  function form(row){
    if(!writer)return;
    var p=row&&row.properties||{},area=$("#rec-editor");area.hidden=false;
    if(activeDraft&&activeDraft.dispose)activeDraft.dispose();
    activeDraft=null;
    area.innerHTML='<h3>'+(row?"Revise original recommendation":"Draft a new recommendation")+'</h3>'+
      '<form id="rec-form">'+
      window.AICompassWorkgroup.renderDomainFields(
        window.AICompassWorkgroup.RECOMMENDATION_FIELDS,{
          name:row&&row.name||"",task_id:row&&row.task_id||"",
          solution_id:row&&row.solution_id||"",decision:p.decision||"recommended",
          rationale:p.rationale||"",limitations:p.limitations||"",
          run_ids:(row&&row.run_refs||[]).map(function(reference){return reference.id;}),
          evaluation_id:row&&row.evaluation_id||""
        },"server",{idPrefix:"recommendation",choices:{
          task_id:tasks.map(function(task){return [task.id,task.name||task.id];}),
          solution_id:solutions.map(function(solution){return [solution.id,solution.name||solution.id];}),
          run_ids:runs.map(function(run){return [run.id,run.id+" · "+run.outcome+" · "+
            (run.metrics.quality_score==null?"unknown":run.metrics.quality_score)];}),
          evaluation_id:evaluations.map(function(evaluation){
            return [evaluation.id,evaluation.name+" · "+evaluation.revision];})}})+
      '<p class="muted small">Only genuine individual Runs for the selected Task and Solution are valid. Composite Framework totals cannot support an individual recommendation.</p>'+
      '<p class="muted small">Uses the exact saved Evaluation revision. Existing revisions are never silently re-pinned.</p>'+
      '<button type="submit">Save immutable draft</button> <button type="button" id="rec-cancel">Cancel</button>'+
      '</form>';
    $("#rec-cancel").addEventListener("click",function(){area.hidden=true;});
    var drafts=window.AICompassDrafts,
        scope=drafts&&drafts.forMode?drafts.forMode("server","recommendation",{
          id:row?row.id:"new",revision:row?row.revision:"new",schema:"recommendation-v1",
          label:row?row.name:"New editorial recommendation",guardUnload:true,
          onConflictReload:function(info){reloadLatest(row,info);}}):null;
    activeDraft=scope?drafts.attach($("#rec-form"),scope):null;
    $("#rec-form").addEventListener("submit",async function(event){
      event.preventDefault();var f=event.target,button=f.querySelector('[type="submit"]');button.disabled=true;
      try{
        var selected=Array.from(f.elements.run_ids.selectedOptions).map(function(x){return x.value;});
        var evaluation=f.elements.evaluation_id.value;
        var record={name:f.elements.name.value,task_id:f.elements.task_id.value,
          solution_id:f.elements.solution_id.value,run_ids:selected,
          properties:{decision:f.elements.decision.value,
                      rationale:f.elements.rationale.value,limitations:f.elements.limitations.value}};
        if(evaluation){
          record.evaluation_id=evaluation;
          var current=evaluations.find(function(x){return x.id===evaluation;});
          record.evaluation_revision=row&&row.evaluation_id===evaluation?row.evaluation_revision:current.revision;
        }
        if(row)record.expected_revision=row.revision;
        var response=await api("recommendations"+(row?"/"+encodeURIComponent(row.id):""),
                               row?"PATCH":"POST",record);
        if(!active)return;
        if(activeDraft&&activeDraft.clear)activeDraft.clear();
        activeDraft=null;
        area.hidden=true;await refresh();
        status("Saved "+(response.record||response).revision+
               "; previous published recommendation remains visible until withdrawal.");
      }catch(error){
        var info=failure(error);
        if(activeDraft&&info.conflict){
          var latest=null;
          if(row){try{latest=await api("recommendations/"+encodeURIComponent(row.id));}catch(_){}}
          activeDraft.conflict({label:row?row.name:"New editorial recommendation",
            baseRevision:row?row.revision:"new",
            latestRevision:latest?latest.revision:"unknown",message:info.detail});
        }
        status("Recommendation NOT saved"+(info.conflict?" (409 revision conflict)":
          info.denied?" (not authorized)":"")+": "+info.detail,true);
      }
      finally{button.disabled=false;}
    });
  }
  /* Reload the newest authoritative recommendation; never reapply the draft. */
  async function reloadLatest(row,info){
    if(!row)return;
    var ticket=++generation;
    try{
      var fresh=await api("recommendations/"+encodeURIComponent(row.id));
      if(!active||ticket!==generation)return;
      var record=fresh.record||fresh;
      form(record);
      status("Reloaded recommendation "+record.id+" at Server revision "+record.revision+
        ". Your unsaved draft stays on this device for manual reapplication.");
    }catch(error){
      if(active&&ticket===generation)status("Could not reload the latest recommendation: "+
        failure(error).detail,true);
    }
  }
  async function transition(row,action){
    if(action==="submit"&&!writer)return;
    if(action!=="submit"&&!reviewer)return;
    var note="";
    if(action!=="submit"){
      note=window.prompt(action==="publish"?
        "Review decision and explain measured evidence / limitations:":
        "Why must this previously published decision be withdrawn?");
      if(note===null)return;
      if(!note.trim())return status("Reviewer justification required.",true);
    }
    try{
      var payload={expected_revision:row.revision};
      if(action!=="submit")payload.review_note=note;
      await api("recommendations/"+encodeURIComponent(row.id)+"/actions/"+action,
                "POST",payload);
      await refresh();status("Recommendation "+action+" action recorded as an immutable, attributable revision.");
    }catch(error){
      var info=failure(error);
      var host=$("#rec-list");
      if(info.conflict&&host&&window.AICompassDrafts&&window.AICompassDrafts.notice){
        window.AICompassDrafts.notice(host,{kind:"recommendation-conflict",tone:"error",
          title:"Conflict: recommendation "+row.id+" changed since it was opened",
          message:info.detail+" Nothing was overwritten or merged; review the latest revision and reapply manually.",
          actions:[
            {label:"Reload latest",primary:true,onClick:function(){
              refresh().then(function(){status("Reloaded the latest recommendation revision.");});}},
            {label:"Copy my review note",onClick:function(){
              if(note)window.AICompassDrafts.copyText(note);}},
            {label:"Discard my note",onClick:function(){
              status("Unsaved review note discarded. Server data was never overwritten.");}}
          ]});
      }
      status("Review action refused"+(info.conflict?" (409 revision conflict)":
        info.denied?" (not authorized)":"")+": "+info.detail,true);
    }
  }
  /* One shared Recommendation detail projection: exact immutable revisions,
   * decision/rationale/limitations and the original measured Run references.
   * Presentation is the common renderDomainDetail; only authorized data differs. */
  function recommendationDetailProjection(row,revisions,routeRun){
    var list=Array.isArray(revisions)?revisions:[];
    function pinnedRuns(record){
      return (record&&record.run_refs||[]).filter(function(reference){
        return reference&&reference.id;
      });
    }
    var sections=list.map(function(record){
      var source=record||{},properties=source.properties||{};
      var runRefs=pinnedRuns(source);
      var parts=[];
      if(properties.decision)parts.push("Decision: "+properties.decision);
      if(properties.rationale)parts.push(String(properties.rationale));
      if(properties.limitations)parts.push("Limitations: "+properties.limitations);
      if(runRefs.length)parts.push("Original measured Runs: "+runRefs.map(function(reference){
        return reference.id;}).join(", "));
      else if((source.run_refs||[]).length)parts.push(
        "Original measured Run evidence is unavailable in this projection; no substitute is shown.");
      else parts.push("No original measured Run attached.");
      return {label:[source.revision||"revision",source.state||"unknown",
          "by "+(source.created_by||"unknown"),
          "reviewed by "+(source.reviewed_by||"not reviewed")].join(" \u00b7 "),
        value:parts.join(" \u2014 ")};
    });
    var rowRefs=pinnedRuns(row),totalRefs=(row&&row.run_refs||[]).length;
    return {title:(row&&row.name)||"Recommendation",
      identity:[(row&&row.revision)||"",(row&&row.state)||"",
        (row&&row.task_id)||"",(row&&row.solution_id)||"",
        totalRefs+" original measured Run(s)"].filter(function(value){return value!=="";}),
      sections:sections,
      notices:["Immutable, attributable publication history. The current decision is never substituted for a chosen revision." +
        " Raw source inspection remains an explicitly requested advanced view."],
      links:rowRefs.map(function(reference){
        return {href:routeRun(reference),label:"Open original measured Run "+reference.id};
      })};
  }
  async function detail(row){
    var ticket=generation,area=$("#rec-detail");area.hidden=false;
    area.textContent="Loading attributable revision history\u2026";
    try{
      var response=await api("recommendations/"+encodeURIComponent(row.id)+"/revisions");
      if(!active||ticket!==generation)return;
      var routeRun=function(reference){
        if(window.AICompassContext&&window.AICompassContext.route)
          return window.AICompassContext.route("server","workgroup","results",{record:reference.id});
        return "/?mode=server&workspace=workgroup&section=results&record="+
          encodeURIComponent(reference.id);
      };
      area.innerHTML=window.AICompassWorkgroup.renderDomainDetail(
        recommendationDetailProjection(row,response.revisions||[],routeRun),
        {mode:"server",domain:"recommendations"});
    }catch(error){status("Historical recommendation unavailable: "+error.message,true);}
  }
  function setAccess(read,write,review){
    ++generation;active=!!read;writer=active&&!!write;reviewer=active&&!!review;
    recommendations=[];tasks=[];solutions=[];runs=[];evaluations=[];
    if(activeDraft&&activeDraft.dispose)activeDraft.dispose();
    activeDraft=null;
    root.replaceChildren();root.hidden=!active;
    if(active){init();refresh();}
  }
  root.hidden=true;
  return {setAccess:setAccess,refresh:refresh,
    recommendationDetailProjection:recommendationDetailProjection};
}
window.AICompassServerRecommendations={mount:mount};
})();
