/* PLAT-22: Server-only Recommendations under Knowledge & Collaboration.
   Real REST/CSRF only. Independent seeded Demo remains unchanged. */
(function(){
"use strict";
function mount(root,csrf,escapeHtml){
  var active=false,writer=false,reviewer=false,generation=0;
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
    if(!response.ok)throw Error(result.detail||result.error||"HTTP "+response.status);
    return result;
  }
  function status(message,error){
    var node=$("#rec-status");
    if(node){
      node.textContent=message;
      node.className=error?"server-status server-error":"server-status";
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
    $("#rec-list").innerHTML=window.AICompassWorkgroup.renderRecords(shown.map(function(r){
      var p=r.properties||{},actions=[
        {label:"Original history / evidence",
         attributes:{"data-recommendation":r.id,"data-action":"history"}}
      ];
      if(writer)actions.push({label:"New draft revision",
        attributes:{"data-recommendation":r.id,"data-action":"edit"}});
      if(writer&&r.state==="draft")actions.push({label:"Submit for review",
        attributes:{"data-recommendation":r.id,"data-action":"submit"}});
      if(reviewer&&r.state==="in_review")actions.push({label:"Review and publish",
        attributes:{"data-recommendation":r.id,"data-action":"publish"}});
      if(reviewer&&r.state!=="unpublished")actions.push({label:"Withdraw publication",
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

  function field(name,label,value,required,multi){
    return '<label>'+label+(multi?'<textarea name="'+name+'" '+(required?"required":"")+'>'+esc(value||"")+'</textarea>':
      '<input name="'+name+'" value="'+esc(value||"")+'" '+(required?"required":"")+'>')+'</label>';
  }
  function form(row){
    if(!writer)return;
    var p=row&&row.properties||{},area=$("#rec-editor");area.hidden=false;
    area.innerHTML='<h3>'+(row?"Revise original recommendation":"Draft a new recommendation")+'</h3>'+
      '<form id="rec-form">'+field("name","Decision title",row&&row.name,true)+
      '<label>Engineering Task<select name="task_id">'+tasks.map(function(t){
        return option(t.id,t.name||t.id,row&&row.task_id===t.id);}).join("")+'</select></label>'+
      '<label>Measured individual AI Solution<select name="solution_id">'+solutions.map(function(s){
        return option(s.id,s.name||s.id,row&&row.solution_id===s.id);}).join("")+'</select></label>'+
      '<label>Decision<select name="decision">'+["recommended","conditional","not_recommended"].map(function(x){
        return option(x,x,p.decision===x);}).join("")+'</select></label>'+
      field("rationale","Engineering rationale",p.rationale,true,true)+
      field("limitations","Limitations / uncertain scope",p.limitations,false,true)+
      '<label>Exact original individual Runs (multi-select)<select name="run_ids" multiple size="6">'+
      runs.map(function(r){return option(r.id,r.id+" · "+r.outcome+
        " · "+(r.metrics.quality_score==null?"unknown":r.metrics.quality_score),
        !!row&&row.run_refs.some(function(x){return x.id===r.id;}));}).join("")+
      '</select></label>'+
      '<p class="muted small">Only genuine individual Runs for the selected Task and Solution are valid. Composite Framework totals cannot support an individual recommendation.</p>'+
      '<label>Optional saved Evaluation<select name="evaluation_id">'+option("","No evaluation",!row||!row.evaluation_id)+
      evaluations.map(function(e){return option(e.id,e.name+" · "+e.revision,
                         row&&row.evaluation_id===e.id);}).join("")+'</select></label>'+
      '<p class="muted small">Uses the exact saved Evaluation revision. Existing revisions are never silently re-pinned.</p>'+
      '<button type="submit">Save immutable draft</button> <button type="button" id="rec-cancel">Cancel</button>'+
      '</form>';
    $("#rec-cancel").addEventListener("click",function(){area.hidden=true;});
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
        if(!active)return;area.hidden=true;await refresh();
        status("Saved "+(response.record||response).revision+
               "; previous published recommendation remains visible until withdrawal.");
      }catch(error){status("Recommendation NOT saved: "+error.message,true);}
      finally{button.disabled=false;}
    });
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
    }catch(error){status("Review action refused: "+error.message,true);}
  }
  async function detail(row){
    var ticket=generation,area=$("#rec-detail");area.hidden=false;
    area.textContent="Loading attributable revision history…";
    try{
      var response=await api("recommendations/"+encodeURIComponent(row.id)+"/revisions");
      if(!active||ticket!==generation)return;
      area.innerHTML='<h3>'+esc(row.name)+' · publication and evidence history</h3>'+
        response.revisions.map(function(record){
          return '<details><summary>'+esc(record.revision)+' · '+esc(record.state)+
            ' · '+esc(record.created_by)+' · '+esc(record.reviewed_by||"not reviewed")+
            '</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>'+
            '<p>'+record.run_refs.map(function(r){
              return '<a href="/api/v1/runs/'+encodeURIComponent(r.id)+'">'+esc(r.id)+
                ' (original measured Run)</a>';
            }).join(", ")+'</p></details>';
        }).join("");
      area.querySelectorAll("details pre").forEach(function(pre,index){
        pre.textContent=JSON.stringify(response.revisions[index],null,2);
      });
    }catch(error){status("Historical recommendation unavailable: "+error.message,true);}
  }
  function setAccess(read,write,review){
    ++generation;active=!!read;writer=active&&!!write;reviewer=active&&!!review;
    recommendations=[];tasks=[];solutions=[];runs=[];evaluations=[];
    root.replaceChildren();root.hidden=!active;
    if(active){init();refresh();}
  }
  root.hidden=true;
  return {setAccess:setAccess,refresh:refresh};
}
window.AICompassServerRecommendations={mount:mount};
})();
