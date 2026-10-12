/* PLAT-21: Server-only Results Explorer, no Demo storage or result aggregation. */
(function(){
"use strict";
function mount(root,csrf,escapeHtml){
  var enabled=false,writer=false,reviewer=false,ticket=0,results=[],evaluations=[],tasks=[],solutions=[],campaigns=[],current=null;
  var METRICS=["quality_score","information_utility_score","cost_eur",
               "tokens_total","human_total_minutes","interaction_agent_minutes"];
  function $(q){return root.querySelector(q);}
  function esc(s){return escapeHtml(s==null?"":String(s));}
  function status(message,error){
    var node=$("#results-status");
    if(node){
      node.className=error?"server-status server-error":"server-status";
      node.innerHTML=window.AICompassWorkgroup.renderDomainStatus({
        mode:"server",state:error?"error":"ok",message:message==null?"":String(message)});
    }
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
      '<div id="ux-results-context"></div>'+
      '<div id="results-matrix" class="server-card"></div>'+
      '<h3>Source observations · measured vs theoretical</h3>'+
      '<div id="results-rows" class="server-card"></div>'+
      '<h3>Versioned evaluations · interpretation only</h3>'+
      (writer?'<button type="button" id="results-new-evaluation">+ Save evaluation</button>':'')+
      '<div id="results-evaluations" class="server-card"></div>'+
      '<section id="results-editor" class="server-card" hidden></section>'+
      '<section id="results-detail" class="server-card" hidden></section>';
    var filtersFromUrl=new URLSearchParams(window.location.search);
    ["kind","view"].forEach(function(k){
      var v=filtersFromUrl.get(k),select=$("#results-filter").elements[k];
      if(v && Array.from(select.options).some(function(opt){return opt.value===v;}))
        select.value=v;
    });
    $("#results-refresh").addEventListener("click",refresh);
    $("#results-filter").addEventListener("submit",function(event){
      event.preventDefault();
      var next=new URL(window.location.href),fields=event.target.elements;
      ["task_id","solution_id","campaign_id","kind","view"].forEach(function(k){
        if(fields[k]&&fields[k].value)next.searchParams.set(k,fields[k].value);
        else next.searchParams.delete(k);
      });
      window.history.replaceState(window.history.state,"",next.pathname+next.search+next.hash);
      loadMatrix();
    });
    if(writer)$("#results-new-evaluation").addEventListener("click",function(){edit(null);});
    $("#results-rows").addEventListener("click",function(event){
      var button=event.target.closest("button[data-amend-run]");
      if(!button||!reviewer)return;
      amendRun(button.dataset.amendRun);
    });
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
      return [key,form.elements[key].value ||
        new URLSearchParams(window.location.search).get(key) || ""];
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
    var params=new URLSearchParams(window.location.search);
    var wanted=params.get("record"),pinned=params.get("revision");
    var selected=wanted&&(data.results||[]).find(function(r){return r.id===wanted;});
    var context=$("#ux-results-context");
    if(wanted){
      if(!selected){
        context.innerHTML='<p role="alert" class="ux-history-warning">Run not present in this authorized Results projection. Check the applied filters, publication scope and account permissions; no other version is substituted.</p>';
      }else{
        var revision=selected.revision||selected.run_revision||"";
        var metrics=selected.kind==="forecast"?selected.predicted_metrics:selected.metrics||{};
        // One shared measured-Run presentation; unknown fields stay unknown.
        var links=[];
        if(selected.kind!=="forecast")links.push({label:"Related measured AI Solution",
          href:window.AICompassContext.route("server","engineer","home",{
            task:selected.task_id,solution:selected.solution_id||selected.candidate})});
        if(writer&&selected.campaign_id)links.push({label:"Related Campaign",
          href:window.AICompassContext.route("server","workgroup","benchmark",{
            record:selected.campaign_id})});
        context.innerHTML=window.AICompassWorkgroup.renderMeasuredRunDetail({
          id:selected.id,
          kind:selected.kind==="forecast"?"theoretical":"individual",
          revision:revision,outcome:selected.outcome||selected.status,
          title:(selected.candidate||selected.id)+" · "+selected.task_id,
          taskName:selected.task_id,configurationLabel:selected.candidate,
          metrics:[
            {label:"Quality /100",value:metrics.quality_score},
            {label:"Cost EUR",value:metrics.cost_eur!=null?metrics.cost_eur:metrics.ai_cost_eur},
            {label:"Human time (minutes)",
             value:metrics.human_total_minutes!=null?metrics.human_total_minutes:metrics.human_minutes}
          ],
          links:links
        },{mode:"server",pinnedRevision:pinned})+
          (selected.detail?'<details class="ux-advanced-source"><summary>Advanced: open authorized '+
            'original Run record</summary><a href="'+esc(selected.detail)+'" target="_blank" '+
            'rel="noopener noreferrer">Open original API source</a></details>':"");
      }
    }else context.replaceChildren();
    // One shared observation matrix; only the authorized projection differs.
    var columnLabels=[];
    groups.forEach(function(row){
      row.columns.forEach(function(col){
        if(!columnLabels.some(function(entry){return entry.key===col.key;}))
          columnLabels.push({key:col.key,label:col.key});
      });
    });
    node.innerHTML=window.AICompassWorkgroup.renderObservationMatrix({
      rowAxis:data.row_axis,columnAxis:data.column_axis,columnLabels:columnLabels,
      counts:[
        {label:"individual Run(s)",value:data.counts.individual_runs},
        {label:"composite workflow(s)",value:data.counts.composite_workflows},
        {label:"THEORETICAL forecast(s)",value:data.counts.theoretical_forecasts}],
      policy:data.scoring_policy,
      rows:groups.map(function(row){
        return {key:row.key,label:row.key,
          columns:row.columns.map(function(col){
            return {key:col.key,observations:col.observations,
              hint:col.observations+" record(s)",
              ids:(col.observation_ids||[]).map(function(identifier){
                return {id:identifier,label:identifier,
                  href:window.AICompassContext.route("server","workgroup","results",
                    {record:identifier})};})};})};}),
      notices:["Empty is not a failed Test Case, and missing comparisons stay unknown."]
    },{mode:"server",domain:"results",
       emptyText:"No persisted results in this filter. Empty is not a failed Test Case."});
    $("#results-rows").innerHTML=window.AICompassWorkgroup.renderRecords(
      (data.results||[]).map(function(r){
        var forecast=r.kind==="forecast",metrics=(forecast?r.predicted_metrics:r.metrics)||{};
        var facts=[
          r.evidence_class,forecast?"THEORETICAL FORECAST":"MEASURED "+r.kind.toUpperCase(),
          "Task "+r.task_id,"Candidate "+r.candidate,
          "Quality: "+format(metrics.quality_score),
          "Cost EUR: "+format(forecast?metrics.ai_cost_eur:metrics.cost_eur),
          "Human min: "+format(forecast?metrics.human_minutes:metrics.human_total_minutes)
        ];
        if(r.experimental_method_version)facts.push("Experimental method v"+r.experimental_method_version);
        var notices=forecast?["Estimates only. Uncertainty: "+(r.uncertainty||"Unspecified")]:
          ["Unknown fields: "+(r.missing_fields||[]).join(", ")||"none"];
        var links=forecast?[]:[{label:"Open Run context",
          href:window.AICompassContext.route("server",writer?"workgroup":"engineer","results",{
            record:r.id,revision:r.revision||"",task:r.task_id,
            solution:r.solution_id||r.candidate})}];
        var actions=(!forecast&&reviewer)?[{label:"Correct / withdraw",
          attributes:{"data-amend-run":r.id}}]:[];
        return {id:r.id,title:forecast?"Theoretical forecast":"Measured Run",
          status:r.outcome||r.status||"",revision:r.revision||"",
          facts:facts,notices:notices,links:links,actions:actions};
      }),{domain:"results",mode:"server",emptyText:"No source observations."});

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
    $("#results-evaluations").innerHTML=window.AICompassWorkgroup.renderRecords(
      evaluations.map(function(r){
        var actions=[{label:"Details / immutable history",
          attributes:{"data-evaluation":r.id,"data-action":"history"}}];
        if(writer)actions.push({label:"New interpretation revision",
          attributes:{"data-evaluation":r.id,"data-action":"edit"}});
        return {id:r.id,title:r.name,status:"interpretation",revision:r.revision,
          facts:[(r.inputs||[]).length+" measured run(s)",(r.properties||{}).comparability||"not specified"],
          actions:actions};
      }),{domain:"evaluations",mode:"server",emptyText:"No saved evaluations."});
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
      window.AICompassWorkgroup.renderDomainFields(
        window.AICompassWorkgroup.EVALUATION_FIELDS,{
          name:row&&row.name||"",run_ids:existing.join("\n"),
          assessment:p.assessment||"inconclusive",notes:p.notes||"",
          limitations:p.limitations||"",
          selected_metrics:(row&&row.scoring_config||{}).selected_metrics||METRICS
        },"server",{idPrefix:"evaluation",choices:{selected_metrics:METRICS.map(function(metric){
          return [metric,metric];})}})+
      '<p class="muted small">Paste run-* IDs, one per line. Do not paste forecast-*; theoretical predictions are not measured runs.</p>'+
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
      node.innerHTML=window.AICompassWorkgroup.renderRevisionHistory(
        (history.revisions||[]).map(function(v){
          return {revision:v.revision,by:v.created_by,
            body:JSON.stringify(v,null,2),
            reason:"Retained interpretation · comparability "+v.properties.comparability+
              " · scoring method version "+v.scoring_method.version};
        }),{mode:"server",domain:"evaluations",
          heading:row.name+" · immutable interpretation history"});
    }catch(err){status("Evaluation history unavailable: "+err.message,true);}
  }

  async function amendRun(identifier){
    if(!reviewer)return;
    var node=$("#results-detail"),run;
    node.hidden=false;node.textContent="Loading Run revision…";
    try{run=await api("runs/"+encodeURIComponent(identifier));}
    catch(error){status("Run not accessible: "+error.message,true);return;}
    node.innerHTML='<h3>Correct or withdraw · '+esc(identifier)+'</h3>'+
      '<p class="muted small">Only declared measurements are superseded; frozen raw evidence, original Run and previous publication revisions remain.</p>'+
      '<p>Current revision: '+esc(run.revision)+' · '+esc(run.effective_status)+'</p>'+
      '<label>Action<select id="run-amend-action"><option value="corrected">Correct measurement</option>'+
      '<option value="withdrawn">Withdraw invalid Run</option></select></label>'+
      '<label>Mandatory justification (8–2000 characters)<textarea id="run-amend-reason" maxlength="2000"></textarea></label>'+
      '<label>Quality score (optional corrected 0–100)<input id="run-amend-quality" type="number" min="0" max="100" step="any" placeholder="'+esc(run.metrics.quality_score)+'"></label>'+
      '<label>Information utility score (optional corrected 0–100)<input id="run-amend-utility" type="number" min="0" max="100" step="any" placeholder="'+esc(run.metrics.information_utility_score)+'"></label>'+
      '<label>DoD outcome<select id="run-amend-outcome"><option value="">No change</option>'+
      '<option value="accepted">Accepted</option><option value="failed">Failed</option></select></label>'+
      '<button type="button" id="run-amend-save">Commit immutable Run revision</button>'+
      '<button type="button" id="run-amend-close">Close</button>';
    node.querySelector("#run-amend-close").addEventListener("click",function(){node.hidden=true;});
    node.querySelector("#run-amend-save").addEventListener("click",async function(){
      var action=node.querySelector("#run-amend-action").value;
      var reason=node.querySelector("#run-amend-reason").value.trim();
      var data={expected_revision:run.revision,reason:reason};
      if(action==="corrected"){
        var patch={};
        var quality=node.querySelector("#run-amend-quality").value;
        var utility=node.querySelector("#run-amend-utility").value;
        if(quality!=="")patch.quality_score=Number(quality);
        if(utility!=="")patch.information_utility_score=Number(utility);
        if(Object.keys(patch).length)data.metrics_patch=patch;
        var outcome=node.querySelector("#run-amend-outcome").value;
        if(outcome)data.outcome=outcome;
        if(!data.metrics_patch&&!data.outcome){
          status("Specify at least one measurement or outcome correction.",true);return;
        }
      }else if(!window.confirm("Withdraw this Run from all current published results? Historical evidence remains.")){
        return;
      }
      var button=node.querySelector("#run-amend-save");
      button.disabled=true;
      try{
        var response=await api("runs/"+encodeURIComponent(identifier)+"/actions/"+action,
                               "POST",data);
        status("Run "+identifier+" · "+response.current.revision+" · "+
               response.current.status+" committed.");
        node.hidden=true;
        await refresh();
      }catch(error){status("Run amendment rejected: "+error.message,true);}
      finally{button.disabled=false;}
    });
  }
  function setAccess(read,write,canReview){
    ++ticket;enabled=!!read;writer=enabled&&!!write;reviewer=enabled&&!!canReview;
    results=[];evaluations=[];tasks=[];solutions=[];campaigns=[];current=null;
    root.replaceChildren();root.hidden=!enabled;
    if(enabled){shell();refresh();}
  }
  root.hidden=true;
  return {setAccess:setAccess,refresh:refresh};
}
window.AICompassServerResults={mount:mount};
})();
