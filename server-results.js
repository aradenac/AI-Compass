/* PLAT-21: Server-only Results Explorer, no Demo storage or result aggregation. */
(function(){
"use strict";
function mount(root,csrf,escapeHtml){
  var enabled=false,writer=false,ticket=0,results=[],evaluations=[],tasks=[],solutions=[],campaigns=[],current=null;
  var METRICS=["quality_score","information_utility_score","cost_eur",
               "tokens_total","human_total_minutes","interaction_agent_minutes"];
  function $(q){return root.querySelector(q);}
  function esc(s){return escapeHtml(s==null?"":String(s));}
  function status(message,error){
    var node=$("#results-status");
    if(node){node.textContent=message;node.className=error?"server-status server-error":"server-status";}
  }
  function option(value,label,selected){
    return '<option value="'+esc(value)+'"'+(selected?" selected":"")+'>'+esc(label)+'</option>';
  }
  function format(value){
    return value===null||value===undefined?"Unknown / not measured":esc(value);
  }
  async function api(path,method,payload){
    var options={method:method||"GET",credentials:"same-origin",cache:"no-store"};
    if(method&&method!=="GET"){
      options.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
      options.body=JSON.stringify(payload||{});
    }
    var response=await fetch("/api/v1/"+path,options);
    var json=await response.json().catch(function(){return {};});
    if(!response.ok)throw Error(json.detail||json.error||"HTTP "+response.status);
    return json;
  }
  function shell(){
    root.innerHTML='<div class="server-model-toolbar"><div><h2>Results Explorer · observed and theoretical</h2>'+
      '<p class="muted small">One row per real controlled Run. No automatic averages or participant attribution for composite workflows.</p></div>'+
      '<button type="button" id="results-refresh">Refresh</button></div>'+
      '<p id="results-status" role="status" class="server-status"></p>'+
      '<form id="results-filter"><label>Matrix orientation<select name="view">'+
      option("task","Task-centred",true)+option("solution","Solution / candidate-centred",false)+'</select></label>'+
      '<label>Evidence scope<select name="kind">'+
      option("all","All (shown separately)",true)+
      option("individual","Measured individual runs",false)+
      option("composite","Measured composite workflows",false)+
      option("theoretical","Theoretical forecasts only",false)+'</select></label>'+
      '<label>Task<select name="task_id"><option value="">All tasks</option></select></label>'+
      '<label>Measured AI Solution<select name="solution_id"><option value="">All solutions</option></select></label>'+
      '<label>Campaign<select name="campaign_id"><option value="">All campaigns</option></select></label>'+
      '<button type="submit">Apply filters</button></form>'+
      '<div id="results-matrix" class="server-card"></div>'+
      '<h3>Source observations · measured vs theoretical</h3>'+
      '<div id="results-rows" class="server-card"></div>'+
      '<h3>Versioned evaluations · interpretation only</h3>'+
      (writer?'<button type="button" id="results-new-evaluation">+ Save evaluation</button>':'')+
      '<div id="results-evaluations" class="server-card"></div>'+
      '<section id="results-editor" class="server-card" hidden></section>'+
      '<section id="results-detail" class="server-card" hidden></section>';
    $("#results-refresh").addEventListener("click",refresh);
    $("#results-filter").addEventListener("submit",function(event){
      event.preventDefault();loadMatrix();
    });
    if(writer)$("#results-new-evaluation").addEventListener("click",function(){edit(null);});
    $("#results-evaluations").addEventListener("click",function(event){
      var button=event.target.closest("button[data-evaluation]");
      if(!button)return;
      var row=evaluations.find(function(x){return x.id===button.dataset.evaluation;});
      if(!row)return;
      if(button.dataset.action==="history")inspect(row);
      else if(button.dataset.action==="edit"&&writer)edit(row);
    });
  }
  function filters(){
    var form=$("#results-filter"),data=new URLSearchParams();
    ["view","kind","task_id","solution_id","campaign_id"].forEach(function(key){
      var value=form.elements[key].value;
      if(value)data.set(key,value);
    });
    return data.toString();
  }
  function renderChoices(){
    var form=$("#results-filter");
    var old=Object.fromEntries(["task_id","solution_id","campaign_id"].map(function(key){
      return [key,form.elements[key].value];
    }));
    [["task_id",tasks,"All tasks"],["solution_id",solutions,"All solutions"],
     ["campaign_id",campaigns,"All campaigns"]].forEach(function(spec){
      var key=spec[0],list=spec[1],field=form.elements[key];
      field.innerHTML=option("",spec[2],!old[key])+list.map(function(x){
        return option(x.id,x.name||x.id,old[key]===x.id);
      }).join("");
    });
  }
  function renderMatrix(data){
    var node=$("#results-matrix");
    var groups=data.matrix||[];
    node.innerHTML='<p><strong>'+esc(data.view==="task"?"Task × candidate":"Candidate × task")+
      '</strong> · '+esc(data.counts.individual_runs)+' individual Run(s) · '+
      esc(data.counts.composite_workflows)+' composite workflow(s) · '+
      esc(data.counts.theoretical_forecasts)+' THEORETICAL forecast(s)</p>'+
      (groups.length?'<table><thead><tr><th>'+esc(data.row_axis)+'</th><th>'+
        esc(data.column_axis)+'</th><th>Source records</th></tr></thead><tbody>'+
        groups.map(function(row){
          return row.columns.map(function(col){
            return '<tr><td>'+esc(row.key)+'</td><td>'+esc(col.key)+'</td><td>'+
              esc(col.observations)+' · '+col.observation_ids.map(esc).join(", ")+'</td></tr>';
          }).join("");
        }).join("")+'</tbody></table>':
        '<p>No persisted results in this filter. Empty is not a failed Test Case.</p>')+
      '<p class="muted small">'+esc(data.scoring_policy)+'</p>';
    node.querySelectorAll("table").forEach(function(table){
      table.style.width="100%";
      table.style.overflowWrap="anywhere";
    });
    $("#results-rows").innerHTML=(data.results||[]).length?
      data.results.map(function(r){
        var forecast=r.kind==="forecast",metrics=forecast?r.predicted_metrics:r.metrics;
        return '<div class="list-row" style="border-bottom:1px solid #dae1ef;padding:12px 0">'+
          '<strong>'+esc(r.id)+'</strong> · '+esc(r.evidence_class)+' · '+
          (forecast?'<strong>THEORETICAL FORECAST</strong> · '+esc(r.status):
            '<strong>MEASURED '+esc(r.kind.toUpperCase())+'</strong> · '+esc(r.outcome))+
          '<p class="muted small">Task '+esc(r.task_id)+' · Candidate '+esc(r.candidate)+
          (r.experimental_method_version?" · Experimental method v"+esc(r.experimental_method_version):"")+'</p>'+
          '<p>Quality: '+format(metrics.quality_score)+' · Cost EUR: '+
            format(forecast?metrics.ai_cost_eur:metrics.cost_eur)+
            ' · Human min: '+format(forecast?metrics.human_minutes:metrics.human_total_minutes)+
          '</p>'+
          (forecast?'<p class="muted small">Estimates only · Uncertainty: '+
            esc(r.uncertainty||"Unspecified")+'</p>':
            '<p class="muted small">Unknown fields: '+esc((r.missing_fields||[]).join(", ")||"none")+
            ' · <a href="'+esc(r.detail)+'">Frozen source detail (JSON)</a></p>')+
          '</div>';
      }).join(""):'<p>No source observations.</p>';
  }
  async function loadMatrix(){
    if(!enabled)return;
    var version=++ticket;
    status("Loading original PostgreSQL results…");
    try{
      current=await api("results/explorer?"+filters());
      if(!enabled||version!==ticket)return;
      results=current.results||[];
      renderMatrix(current);status("Server Results Explorer loaded; measured / theoretical scope preserved.");
    }catch(err){
      if(!enabled||version!==ticket)return;
      current=null;results=[];
      $("#results-matrix").textContent="No authoritative results available.";
      $("#results-rows").textContent="";
      status("Results query rejected: "+err.message,true);
    }
  }
  function renderEvaluations(){
    $("#results-evaluations").innerHTML=evaluations.length?
      evaluations.map(function(row){
        return '<p><strong>'+esc(row.name)+'</strong> · '+esc(row.id)+' · '+esc(row.revision)+
          ' · interpretation · '+esc(row.inputs.length)+' measured run(s) · '+
          esc(row.properties.comparability)+
          ' <button type="button" data-evaluation="'+esc(row.id)+
          '" data-action="history">Details / immutable history</button>'+
          (writer?' <button type="button" data-evaluation="'+esc(row.id)+
          '" data-action="edit">New interpretation revision</button>':'')+'</p>';
      }).join(""):'<p>No saved evaluations.</p>';
  }
  async function refresh(){
    if(!enabled)return;
    var version=++ticket;
    try{
      var inputs=await Promise.all([api("evaluations"),api("tasks"),api("solutions"),
                                    api("campaigns")]);
      if(!enabled||version!==ticket)return;
      evaluations=inputs[0].results||[];tasks=inputs[1].results||[];
      solutions=inputs[2].results||[];campaigns=inputs[3].results||[];
      renderChoices();renderEvaluations();await loadMatrix();
    }catch(err){
      if(!enabled||version!==ticket)return;
      evaluations=[];tasks=[];solutions=[];campaigns=[];results=[];current=null;
      renderEvaluations();$("#results-rows").textContent="";
      status("Cannot retrieve Server Results: "+err.message,true);
    }
  }
  function edit(row){
    if(!writer)return;
    var area=$("#results-editor"),p=row&&row.properties||{};
    area.hidden=false;
    var existing=row?row.inputs.map(function(x){return x.run_id;}):[];
    area.innerHTML='<h3>'+(row?"Reinterpret · append revision":"New")+" saved evaluation</h3>"+
      '<p class="muted small">The scoring method is descriptive comparison v1 (no invented averages). Each measured Run and experimental protocol is pinned permanently.</p>'+
      '<form id="evaluation-form">'+
      '<label>Evaluation title<input name="name" maxlength="160" required value="'+esc(row&&row.name||"")+'"></label>'+
      '<label>Original measured Run IDs<textarea name="run_ids" required>'+esc(existing.join("\n"))+'</textarea></label>'+
      '<p class="muted small">Paste run-* IDs, one per line. Do not paste forecast-*; theoretical predictions are not measured runs.</p>'+
      '<label>Interpretation<select name="assessment">'+
      ["inconclusive","supported","unsupported"].map(function(x){
        return option(x,x,p.assessment===x);}).join("")+'</select></label>'+
      '<label>Notes<textarea name="notes">'+esc(p.notes||"")+'</textarea></label>'+
      '<label>Limitations<textarea name="limitations">'+esc(p.limitations||"")+'</textarea></label>'+
      '<label>Measured metric fields to inspect<select name="selected_metrics" multiple size="6">'+
      METRICS.map(function(k){
        return option(k,k,!row||(row.scoring_config.selected_metrics||[]).includes(k));
      }).join("")+'</select></label>'+
      '<p class="muted small">Unknown/unavailable fields and mixed experimental methods are reported automatically. Selecting a newer method creates a new revision.</p>'+
      '<button type="submit">Save immutable evaluation revision</button>'+
      '<button type="button" id="evaluation-cancel">Cancel</button></form>';
    $("#evaluation-cancel").addEventListener("click",function(){area.hidden=true;});
    $("#evaluation-form").addEventListener("submit",async function(event){
      event.preventDefault();var form=event.target,b=form.querySelector('[type="submit"]');
      b.disabled=true;
      try{
        var ids=form.elements.run_ids.value.split(/[\n, ]+/).map(function(x){return x.trim();}).filter(Boolean);
        var metrics=Array.from(form.elements.selected_metrics.selectedOptions).map(function(x){return x.value;});
        var payload={name:form.elements.name.value,run_ids:ids,
          scoring_method_version:1,
          scoring_config:{selected_metrics:metrics,comparison_basis:"descriptive_only"},
          properties:{assessment:form.elements.assessment.value,
                      notes:form.elements.notes.value,
                      limitations:form.elements.limitations.value}};
        if(row)payload.expected_revision=row.revision;
        var response=await api("evaluations"+(row?"/"+encodeURIComponent(row.id):""),
                              row?"PATCH":"POST",payload);
        if(!enabled)return;
        area.hidden=true;await refresh();
        status("Evaluation revision persisted separately from source Runs: "+
               (response.record||response).revision);
      }catch(err){status("Evaluation NOT saved: "+err.message,true);}
      finally{b.disabled=false;}
    });
  }
  async function inspect(row){
    var version=ticket,node=$("#results-detail");
    node.hidden=false;node.textContent="Loading exact historical evaluation revisions…";
    try{
      var history=await api("evaluations/"+encodeURIComponent(row.id)+"/revisions");
      if(!enabled||ticket!==version)return;
      node.innerHTML='<h3>'+esc(row.name)+' · immutable interpretation history</h3>'+
        (history.revisions||[]).map(function(v){
          return '<details><summary>'+esc(v.revision)+' · '+esc(v.created_by)+
            ' · '+esc(v.properties.comparability)+
            ' · '+esc(v.scoring_method.version)+' (scoring method version)</summary>'+
            '<pre style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';
        }).join("");
      node.querySelectorAll("details pre").forEach(function(pre,i){
        pre.textContent=JSON.stringify(history.revisions[i],null,2);
      });
    }catch(err){status("Evaluation history unavailable: "+err.message,true);}
  }
  function setAccess(read,write){
    ++ticket;enabled=!!read;writer=enabled&&!!write;
    results=[];evaluations=[];tasks=[];solutions=[];campaigns=[];current=null;
    root.replaceChildren();root.hidden=!enabled;
    if(enabled){shell();refresh();}
  }
  root.hidden=true;
  return {setAccess:setAccess,refresh:refresh};
}
window.AICompassServerResults={mount:mount};
})();
