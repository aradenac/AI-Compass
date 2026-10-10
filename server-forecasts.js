/* PLAT-20: Server-only theoretical forecasts, deliberately distinct from measured runs. */
(function(){
"use strict";
function mount(root,csrf,escapeHtml){
  var enabled=false,writer=false,reviewer=false,ticket=0,forecasts=[],watch=[],tasks=[],catalog={};
  var listTypes=["model","provider","harness"];
  function $(q){return root.querySelector(q);}
  function esc(v){return escapeHtml(v==null?"":String(v));}
  async function api(path,method,data){
    var opts={method:method||"GET",credentials:"same-origin",cache:"no-store"};
    if(method&&method!=="GET"){
      opts.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
      opts.body=JSON.stringify(data||{});
    }
    var r=await fetch("/api/v1/"+path,opts),body=await r.json().catch(function(){return {};});
    if(!r.ok)throw Error(body.detail||body.error||"HTTP "+r.status);
    return body;
  }
  function status(message,bad){
    var node=$("#forecast-status");
    if(node){node.textContent=message;node.className=bad?"server-status server-error":"server-status";}
  }
  function option(id,label,selected){
    return '<option value="'+esc(id)+'"'+(selected?" selected":"")+'>'+esc(label)+'</option>';
  }
  function shell(){
    root.innerHTML='<div class="server-model-toolbar"><div><h2>Technology Watch · Theoretical Forecasts</h2>'+
      '<p class="muted small">Hypotheses and estimated numbers · NOT measured AI Solutions, runs or qualification evidence</p></div>'+
      '<button type="button" id="forecast-refresh">Refresh</button></div>'+
      '<p id="forecast-status" class="server-status" role="status"></p>'+
      (writer?'<button type="button" id="forecast-create">+ Draft forecast</button>':"")+
      '<label>Task filter<select id="forecast-task-filter">'+option("","All tasks",true)+'</select></label>'+
      '<h3>Forecasts · theoretical / unmeasured</h3><div id="forecast-list" class="server-card"></div>'+
      '<section id="forecast-form-panel" class="server-card" hidden></section>'+
      '<section id="forecast-detail-panel" class="server-card" hidden></section>'+
      '<h3>Empirical evidence · independently measured</h3>'+
      '<p class="muted small">Measured solutions and original Run data are available in Benchmark Workspace. Forecast numbers are never aggregated into those scores.</p>'+
      '<button type="button" id="forecast-compare">Show empirical Run catalog (separate)</button>'+
      '<pre id="forecast-measured" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>';
    $("#forecast-refresh").addEventListener("click",refresh);
    $("#forecast-task-filter").addEventListener("change",render);
    if(writer)$("#forecast-create").addEventListener("click",function(){form(null);});
    $("#forecast-list").addEventListener("click",function(event){
      var button=event.target.closest("button[data-forecast]");
      if(!button)return;
      var row=forecasts.find(function(f){return f.id===button.dataset.forecast;});
      if(!row)return;
      if(button.dataset.action==="inspect")return inspect(row);
      if(button.dataset.action==="edit"&&writer)return form(row);
      if(button.dataset.action==="review"&&(writer||reviewer))return lifecycle(row);
      if(button.dataset.action==="campaign"&&writer)return campaign(row);
    });
    $("#forecast-compare").addEventListener("click",async function(){
      var node=$("#forecast-measured");
      node.textContent="Loading actual controlled runs…";
      try{
        var result=await api("runs");
        node.textContent=JSON.stringify((result.results||[]).map(function(r){
          return {id:r.id,kind:r.kind,outcome:r.outcome,solution_id:r.solution_id,
                  framework_id:r.framework_id,metrics:r.metrics,scope:"MEASURED"};
        }),null,2);
      }catch(err){node.textContent="Measured results unavailable: "+err.message;}
    });
  }
  async function refresh(){
    if(!enabled)return;
    var run=++ticket;status("Loading real Server theoretical forecasts and references…");
    try{
      var rows=await Promise.all([api("forecasts"),api("watch-entries"),api("tasks")].concat(
        listTypes.map(function(k){return api("catalog/"+k);})
      ));
      if(!enabled||run!==ticket)return;
      forecasts=rows[0].results||[];watch=rows[1].results||[];tasks=rows[2].results||[];
      listTypes.forEach(function(k,i){catalog[k]=rows[3+i].results||[];});
      var filter=$("#forecast-task-filter").value;
      $("#forecast-task-filter").innerHTML=option("","All tasks",!filter)+tasks.map(function(t){
        return option(t.id,t.name,filter===t.id);
      }).join("");
      render();status(forecasts.length+" persisted theoretical forecast(s); no Demo records imported.");
    }catch(err){
      if(!enabled||run!==ticket)return;
      forecasts=[];watch=[];tasks=[];listTypes.forEach(function(k){catalog[k]=[];});
      render();status("Server Forecasts unavailable — no Demo fallback: "+err.message,true);
    }
  }
  function render(){
    var list=$("#forecast-list");if(!list)return;
    var task=$("#forecast-task-filter").value;
    var rows=forecasts.filter(function(f){return !task||f.task_id===task;});
    list.innerHTML=rows.length?rows.map(function(f){
      var p=f.properties||{};
      return '<div class="list-row" style="padding:10px;border-bottom:1px solid #e2e8f0">'+
        '<strong>'+esc(f.name)+'</strong><p class="muted small">'+esc(f.id)+' · '+esc(f.revision)+
        ' · '+esc(f.status)+' · '+esc(f.task_id)+' · THEORETICAL · '+esc(p.confidence)+' confidence</p>'+
        '<p>Expected quality: '+esc(p.predicted_metrics&&p.predicted_metrics.quality_score!=null?
                                  p.predicted_metrics.quality_score:"unknown")+
        ' / 100 · Projected cost: '+esc(p.predicted_metrics&&p.predicted_metrics.ai_cost_eur!=null?
                                          p.predicted_metrics.ai_cost_eur:"unknown")+
        ' EUR · '+esc(f.watch_links.length)+' exact Watch signals</p>'+
        '<button type="button" data-forecast="'+esc(f.id)+'" data-action="inspect">Inspect immutable versions</button>'+
        (writer?'<button type="button" data-forecast="'+esc(f.id)+'" data-action="edit">Edit (resets review)</button>':'')+
        ((reviewer||writer)?'<button type="button" data-forecast="'+esc(f.id)+'" data-action="review">Stage / review / publish</button>':'')+
        (writer&&["staged","reviewed","published"].includes(f.status)?
          '<button type="button" data-forecast="'+esc(f.id)+'" data-action="campaign">Validate as new campaign</button>':'')+
        '</div>';
    }).join(""):"No forecasts in the selected Server task scope.";
  }
  function form(f){
    if(!writer)return;
    var p=f&&f.properties||{},node=$("#forecast-form-panel");
    node.hidden=false;
    node.innerHTML='<h3>'+(f?"Revise":"Draft")+' theoretical configuration</h3>'+
      '<form id="forecast-form">'+
      '<label>Title<input name="name" required maxlength="160" value="'+esc(f&&f.name||"")+'"></label>'+
      '<label>Engineering task<select name="task_id">'+tasks.map(function(t){
        return option(t.id,t.name,f&&f.task_id===t.id);}).join("")+'</select></label>'+
      listTypes.map(function(k){
        return '<label>'+k+'<select name="'+k+'">'+(catalog[k]||[]).map(function(x){
          return option(x.id,x.name,f&&f.component_ids[k]===x.id);}).join("")+'</select></label>';
      }).join("")+
      '<label>Configuration / parameters / tools JSON<textarea name="configuration">'+
         esc(JSON.stringify(f?f.configuration:{},null,2))+'</textarea></label>'+
      '<label>Assumptions (JSON)<textarea name="assumptions">'+
         esc(JSON.stringify(p.assumptions||{},null,2))+'</textarea></label>'+
      '<label>Theoretical predicted metrics (JSON, unknown=null)<textarea name="predicted_metrics">'+
         esc(JSON.stringify(p.predicted_metrics||{
           quality_score:null,acceptance_probability:null,autonomy_score:null,
           human_minutes:null,ai_cost_eur:null,tokens:null},null,2))+'</textarea></label>'+
      '<label>Rationale<textarea name="rationale" required maxlength="10000">'+esc(p.rationale||"")+'</textarea></label>'+
      '<label>Uncertainty / missing evidence<textarea name="uncertainty" maxlength="10000">'+esc(p.uncertainty||"")+'</textarea></label>'+
      '<label>Confidence<select name="confidence">'+["unknown","low","medium","high"].map(function(k){
        return option(k,k,p.confidence===k);}).join("")+'</select></label>'+
      '<label>Exact Watch signals (multi-select)<select name="watch_links" multiple size="6">'+watch.map(function(w){
        return option(w.id,w.name+" · "+w.revision,!!f&&f.watch_links.some(function(p){return p.id===w.id;}));
      }).join("")+'</select></label>'+
      '<p class="muted small">This is a forecast, never a measured solution. Editing any material field creates a new Draft revision.</p>'+
      '<button type="submit">Save theoretical version</button> <button type="button" id="forecast-cancel">Cancel</button>'+
      '</form>';
    $("#forecast-cancel").addEventListener("click",function(){node.hidden=true;});
    $("#forecast-form").addEventListener("submit",async function(event){
      event.preventDefault();var form=event.target,b=form.querySelector('[type="submit"]');
      b.disabled=true;
      try{
        var config=JSON.parse(form.elements.configuration.value||"{}");
        var assumptions=JSON.parse(form.elements.assumptions.value||"{}");
        var predicted=JSON.parse(form.elements.predicted_metrics.value||"{}");
        if([config,assumptions,predicted].some(function(x){return !x||Array.isArray(x)||typeof x!=="object";}))
          throw Error("Configuration, assumptions and metrics must be JSON objects");
        var existing=new Map((f&&f.watch_links||[]).map(function(x){return [x.id,x.revision];}));
        var data={
          name:form.elements.name.value,task_id:form.elements.task_id.value,
          component_ids:Object.fromEntries(listTypes.map(function(k){return [k,form.elements[k].value];})),
          configuration:config,
          watch_links:Array.from(form.elements.watch_links.selectedOptions).map(function(x){
            var current=watch.find(function(w){return w.id===x.value;});
            return {id:x.value,revision:existing.get(x.value)||current.revision};
          }),
          properties:{rationale:form.elements.rationale.value,
                      uncertainty:form.elements.uncertainty.value,
                      confidence:form.elements.confidence.value,
                      predicted_metrics:predicted,assumptions:assumptions}
        };
        if(f)data.expected_revision=f.revision;
        await api("forecasts"+(f?"/"+encodeURIComponent(f.id):""),f?"PATCH":"POST",data);
        if(!enabled)return;
        node.hidden=true;await refresh();status("Theoretical Forecast stored, prior review and evidence preserved.");
      }catch(err){status("Forecast not saved: "+err.message,true);}
      finally{b.disabled=false;}
    });
  }
  async function inspect(f){
    var current=ticket,node=$("#forecast-detail-panel");node.hidden=false;node.textContent="Loading immutable original…";
    try{
      var result=await api("forecasts/"+encodeURIComponent(f.id)+"/revisions");
      if(!enabled||current!==ticket)return;
      node.innerHTML='<h3>'+esc(f.name)+' · THEORY / never measured</h3>'+
        (result.revisions||[]).map(function(v){
          return '<details><summary>'+esc(v.revision)+' · '+esc(v.status)+' · '+esc(v.created_by)+
            '</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';
        }).join("");
      node.querySelectorAll("details pre").forEach(function(pre,i){
        pre.textContent=JSON.stringify(result.revisions[i],null,2);
      });
    }catch(err){status("History unavailable: "+err.message,true);}
  }
  function lifecycle(f){
    var p=f.properties,node=$("#forecast-form-panel");
    var actions=f.status==="draft"&&writer?["stage"]:
      f.status==="staged"?["review","rework"]:
      f.status==="reviewed"?["publish"]:
      f.status==="published"?["unpublish"]:[];
    actions=actions.filter(function(k){return ["review","publish","unpublish"].includes(k)?reviewer:writer;});
    node.hidden=false;
    node.innerHTML='<h3>Forecast review · '+esc(f.name)+'</h3>'+
      '<p>Current '+esc(f.status)+' · changes in assumptions require a fresh review cycle.</p>'+
      (actions.includes("review")?
        '<label>Required reviewer justification<textarea id="forecast-review-notes" maxlength="10000"></textarea></label>':"")+
      actions.map(function(k){return '<button type="button" data-stage-action="'+esc(k)+'">'+esc(k)+'</button>';}).join("");
    node.querySelectorAll("[data-stage-action]").forEach(function(btn){
      btn.addEventListener("click",async function(){
        btn.disabled=true;
        try{
          var data={expected_revision:f.revision};
          if(btn.dataset.stageAction==="review")data.review_notes=$("#forecast-review-notes").value;
          await api("forecasts/"+encodeURIComponent(f.id)+"/actions/"+btn.dataset.stageAction,"POST",data);
          node.hidden=true;await refresh();
        }catch(err){status("Transition blocked: "+err.message,true);btn.disabled=false;}
      });
    });
  }
  function campaign(f){
    if(!writer||!["staged","reviewed","published"].includes(f.status))return;
    var node=$("#forecast-form-panel");node.hidden=false;
    node.innerHTML='<h3>Start controlled validation from exact '+esc(f.id)+' · '+esc(f.revision)+'</h3>'+
      '<p class="muted small">Preserves original hypothesis, task and Watch revisions as THEORETICAL provenance; no measured Run is created.</p>'+
      '<form id="forecast-new-campaign">'+
      '<label>Campaign title<input name="name" required maxlength="160" value="'+esc("Validate "+f.name)+'"></label>'+
      '<label>Objective<textarea name="objective" required>Validate predicted assumptions using original Test Cases and real evidence</textarea></label>'+
      '<label>Optional setup Guide<select name="guide_id"><option value="">None</option></select></label>'+
      '<p class="muted small">Add exact Test Cases in the normal campaign editor after creation.</p>'+
      '<button type="submit">Create planned validation campaign</button></form>';
    $("#forecast-new-campaign").addEventListener("submit",async function(ev){
      ev.preventDefault();var frm=ev.target,b=frm.querySelector('[type="submit"]');b.disabled=true;
      try{
        var created=await api("forecasts/"+encodeURIComponent(f.id)+"/campaigns","POST",{
          forecast_revision:f.revision,name:frm.elements.name.value,
          objective:frm.elements.objective.value});
        status("Created real Server campaign "+created.id+" · "+created.revision+
          " with frozen forecast "+created.forecast_origin.revision+
          " and "+created.forecast_origin.watch_links.length+" preselected Watch signals.");
        node.hidden=true;
      }catch(err){status("Campaign creation refused: "+err.message,true);b.disabled=false;}
    });
  }
  function setAccess(read,write,review){
    ++ticket;enabled=!!read;writer=enabled&&!!write;reviewer=enabled&&!!review;
    forecasts=[];watch=[];tasks=[];catalog={};
    root.replaceChildren();root.hidden=!enabled;
    if(enabled){shell();refresh();}
  }
  root.hidden=true;
  return {setAccess:setAccess,refresh:refresh};
}
window.AICompassServerForecasts={mount:mount};
})();
