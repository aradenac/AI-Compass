/* FUT-13: shared prospective opportunity view; no Demo→Server data transfer. */
(function(root){
"use strict";
function E(value){return String(value==null?"":value).replace(/[&<>"']/g,function(x){
return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[x];});}
function serverProvider(fetcher,csrf){
  var api=root.AICompassRuntime.ServerTransport(fetcher,csrf).request;
  return {
    bootstrap:async function(){
      var rows=await Promise.all([
        api("/api/v1/planning/profiles"),
        api("/api/v1/planning/tasks"),
        api("/api/v1/planning/opportunities/candidates"),
        api("/api/v1/planning/opportunities")]);
      return {profiles:rows[0].results,tasks:rows[1].results,
              candidates:rows[2].results,scenarios:rows[3].results};},
    preview:function(profile,scenario){return api("/api/v1/planning/opportunities/preview","POST",
        {profile_id:profile,scenario:scenario});},
    create:function(profile,scenario){return api("/api/v1/planning/opportunities","POST",
        {profile_id:profile,scenario:scenario});},
    detail:function(id){return api("/api/v1/planning/opportunities/"+encodeURIComponent(id));},
    revisions:function(id){return api("/api/v1/planning/opportunities/"+encodeURIComponent(id)+"/revisions");}
  };
}
function demoProvider(db){
  var scenarios=[];
  return {
    bootstrap:async function(){
      return {profiles:[{id:"wlp-demo",name:"Fictional two-person demo cohort",kind:"cohort",
        headcount:2,revision:"r001"}],
        tasks:db.tasks.map(function(t){return {id:t.id,name:t.name,parent_id:t.parent};}),
        candidates:db.solutions.filter(function(s){return db.runs.some(function(r){
            return r.status==="published"&&r.solution===s.id;});
        }).flatMap(function(s){return db.cases.filter(function(c){return db.runs.some(
          function(r){return r.status==="published"&&r.solution===s.id&&r.case===c.id;});})
          .map(function(c){return {task_id:c.task,candidate_id:s.id,kind:"benchmark",
            name:s.name,label:"Fictional published Demo Run"};});})
        .concat(db.proposals.filter(function(p){return p.status==="published";}).map(
          function(p){return {task_id:p.task,candidate_id:p.id,kind:"forecast",
            name:p.name,label:"Fictional theoretical Demo hypothesis"};})),
        scenarios:scenarios.map(function(s){return {id:s.id,profile_id:s.profile_id,
          latest_revision:"r001"};})};},
    preview:async function(profile,scenario){
      var cells=scenario.choices.map(function(choice){
        var source=db.runs.filter(function(r){
          return r.status==="published"&&r.solution===choice.candidate_id&&
            db.cases.some(function(c){return c.id===r.case&&c.task===choice.task_id;});});
        var status=choice.kind==="benchmark"&&(source.length!==1||!source[0].accepted)?
          "unquantifiable":"quantified_annual_potential";
        var task=db.tasks.find(function(t){return t.id===choice.task_id;});
        var assumptions={annual_occurrences:60,baseline_human_hours:4,
          hourly_rate_eur:65,assisted_human_hours:1.5,marginal_ai_cost_eur:2};
        var gain=status==="quantified_annual_potential"?
          (assumptions.baseline_human_hours-assumptions.assisted_human_hours)*
            assumptions.hourly_rate_eur-assumptions.marginal_ai_cost_eur:null;
        var total=gain==null?null:(gain*assumptions.annual_occurrences*2).toFixed(2);
        var theoretical=choice.kind==="forecast";
        return {task_id:choice.task_id,task_name:task&&task.name,
          candidate_id:choice.candidate_id,kind:choice.kind,
          evidence_class:theoretical?"theoretical":"measured",status:status,
          reasons:status==="unquantifiable"?["failed_or_ambiguous_demo_Run"]:[],
          economic:gain==null?null:{annual_eur:total,
            marginal_reference_ai_cost_eur:"2.00",
            formula:"Fictional 60 occurrences × 2 people × ((4 h - 1.5 h) × €65 - €2)"},
          slices:total==null?null:{
            activated_potential_eur:"0.00",
            benchmarked_opportunity_eur:theoretical?"0.00":total,
            forecast_opportunity_eur:theoretical?total:"0.00"},
          source_workload:{fictional_assumptions:assumptions}};
      });
      var total=function(key){return cells.reduce(function(n,c){
        return n+Number(c.slices&&c.slices[key]||0);},0).toFixed(2);};
      var act=total("activated_potential_eur"),bench=total("benchmarked_opportunity_eur"),
          future=total("forecast_opportunity_eur");
      return {algorithm:"dap-opportunity-demo-fixture-v1",scenario_name:scenario.name,
        profile_id:profile,headcount:2,period:"annual",currency:"EUR",
        interpretation:"fictional_assumptions_not_realized_cash_savings",
        activation_status:"never_verified_in_demo",
        benchmark_weight:scenario.benchmark_weight,
        totals:{activated_potential_eur:act,benchmarked_opportunity_eur:bench,
          forecast_opportunity_eur:future,
          positive_modeled_total_eur:(Number(act)+Number(bench)+Number(future)).toFixed(2)},
        unquantifiable_count:cells.filter(function(c){return !c.economic;}).length,
        cells:cells};
    },
    create:async function(profile,scenario){
      var result=await this.preview(profile,scenario);
      var row={id:"opp-demo-"+(scenarios.length+1),profile_id:profile,
        revision:"r001",snapshot:result,current:result,scenario:scenario,source_changed:false};
      scenarios.push(row);return row;},
    detail:async function(id){return scenarios.find(function(s){return s.id===id;});},
    revisions:async function(id){return {revisions:scenarios.filter(function(s){return s.id===id;})
      .map(function(s){return {revision:"r001",totals:s.snapshot.totals};})};}
  };
}
function mount(root,provider,mode){
  var active=false,write=false,profiles=[],tasks=[],candidates=[],scenarios=[],
      selected=[],profile="",weight="0.8",name="",generation=0,rendered=null,
      status="",inspection=null;
  function info(text){status=text||"";var node=root.querySelector("[data-opp-status]");
    if(node)node.textContent=status;}
  function surface(){
    root.innerHTML='<section class="server-card" aria-label="Annual opportunity scenarios">'+
      '<h2>Annual Opportunity Scenarios</h2>'+
      '<p class="muted small">Projected capacity value in EUR/year, never realized cash savings. '+
      'One chosen alternative per Task. Activated requires independently verified access and first use '+
      '(not available until Deployment & Access).</p>'+
      (mode==="demo"?'<p><strong>Fictional Demo:</strong> explicit synthetic 60 annual occurrences, '+
        'two people, €65/hour, 4h baseline, 1.5h assisted, €2 usage per case. No Server data.</p>':'')+
      '<p data-opp-status role="status"></p><div data-opp-body></div></section>';
  }
  function selectOptions(rows,value,label){
    return '<option value="">'+E(label||"Choose…")+'</option>'+rows.map(function(x){
      return '<option value="'+E(x.id)+'"'+(x.id===value?' selected':'')+'>'+
        E((x.name||x.id))+'</option>';}).join("");
  }
  function rows(){
    return selected.map(function(c,i){
      var choices=candidates.filter(function(o){return o.task_id===c.task_id;});
      return '<div class="list-row" data-opp-line="'+i+'">'+
        '<label>Task <select data-opp-task="'+i+'">'+
        selectOptions(tasks,c.task_id,"Select a Task")+'</select></label>'+
        '<label>One chosen configuration (measured or theoretical) <select data-opp-candidate="'+i+'">'+
        '<option value="">Select candidate (not automatic)</option>'+
        choices.map(function(o){var key=o.kind+"|"+o.candidate_id;
          return '<option value="'+E(key)+'"'+(
            key===c.kind+"|"+c.candidate_id?' selected':'')+'>'+
            E(o.name)+' · '+E(o.kind)+'</option>';}).join("")+'</select></label>'+
        '<button data-opp-delete="'+i+'" type="button">Remove</button></div>';
    }).join("");
  }
  function report(value){
    if(!value)return "";
    var totals=value.totals||{};
    var labels=[["activated_potential_eur","Activated Potential (verified use only)"],
      ["benchmarked_opportunity_eur","Benchmarked Opportunity"],
      ["forecast_opportunity_eur","Forecast Opportunity"]];
    return '<div class="server-card"><h3>Annual prospective distribution</h3>'+
      '<p><strong>Positive modeled potential: €'+E(totals.positive_modeled_total_eur||"0.00")+
      '/year</strong> · '+E(value.algorithm)+' · '+E(value.interpretation)+'</p>'+
      '<table><thead><tr><th>Exclusive slice</th><th>EUR/year</th></tr></thead><tbody>'+
      labels.map(function(row){return '<tr><td>'+E(row[1])+'</td><td>'+
        E(totals[row[0]]||"0.00")+'</td></tr>';}).join("")+
      '</tbody></table><p class="muted small">Unquantifiable: '+E(value.unquantifiable_count)+
      ' · Activated state: '+E(value.activation_status)+
      '. Negative gains are not summed as positive opportunities.</p>'+
      '<h4>Task × chosen configuration / provenance</h4>'+
      (value.cells||[]).map(function(c,i){return '<details><summary>'+
        E(c.task_name||c.task_id)+' → '+E(c.candidate_id)+' · '+E(c.evidence_class)+
        ' · '+E(c.status)+(c.economic?' · '+E(c.economic.annual_eur)+' EUR/year':'')+
        '</summary><p>'+E((c.reasons||[]).join("; ")||"Source backed")+'</p>'+
        '<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+
        E(JSON.stringify({method:value.algorithm,formula:c.economic&&c.economic.formula,
          source_workload:c.source_workload,measured_reference:c.measured_reference,
          forecast_reference:c.forecast_reference,measured_economics:c.measured_economics,
          theoretical_economics:c.theoretical_economics,blended:c.blended,
          confidence:c.confidence,slices:c.slices},null,2))+
        '</pre></details>';}).join("")+'</div>';
  }
  function render(){
    var body=root.querySelector("[data-opp-body]");
    body.innerHTML='<label>Population profile <select data-opp-profile>'+
      selectOptions(profiles,profile,"Select versioned workload profile")+'</select></label>'+
      '<label>Scenario name <input data-opp-name maxlength="160" value="'+E(name)+
      '" placeholder="e.g. embedded pilot comparison"></label>'+
      '<label>Benchmark weight for comparable linked Forecast <input data-opp-weight '+
      'type="number" min=".51" max=".99" step=".01" value="'+E(weight)+'"></label>'+
      '<p class="muted small">Benchmark/Forecast blending requires exact same Task and pinned setup. '+
      'No default candidate ranking or provisional access verification.</p>'+
      '<div data-opp-lines>'+rows()+'</div>'+
      '<button type="button" data-opp-add>Add Task selection</button>'+
      '<button type="button" data-opp-preview'+(!write?' disabled':'')+'>Calculate current</button>'+
      '<button type="button" data-opp-save'+(!write?' disabled':'')+'>Save immutable scenario revision</button>'+
      '<h3>Saved scenarios</h3>'+
      (scenarios.map(function(s){return '<button type="button" data-opp-open="'+
        E(s.id)+'">'+E(s.id)+' · '+E(s.latest_revision||"r001")+'</button>';}).join("")||
        '<p class="muted small">No saved scenarios.</p>')+
      '<div data-opp-result>'+report(rendered)+'</div>';
    body.querySelector("[data-opp-profile]").onchange=function(){profile=this.value;};
    body.querySelector("[data-opp-name]").oninput=function(){name=this.value;};
    body.querySelector("[data-opp-weight]").oninput=function(){weight=this.value;};
    body.querySelector("[data-opp-add]").onclick=function(){if(selected.length<100){
      selected.push({task_id:"",kind:"",candidate_id:""});render();}};
    body.querySelectorAll("[data-opp-task]").forEach(function(el){el.onchange=function(){
      var i=Number(el.dataset.oppTask);selected[i]={task_id:el.value,kind:"",candidate_id:""};
      render();};});
    body.querySelectorAll("[data-opp-candidate]").forEach(function(el){el.onchange=function(){
      var i=Number(el.dataset.oppCandidate),parts=el.value.split("|");
      selected[i].kind=parts[0]||"";selected[i].candidate_id=parts[1]||"";};});
    body.querySelectorAll("[data-opp-delete]").forEach(function(el){el.onclick=function(){
      selected.splice(Number(el.dataset.oppDelete),1);render();};});
    body.querySelector("[data-opp-preview]").onclick=function(){run(false);};
    body.querySelector("[data-opp-save]").onclick=function(){run(true);};
    body.querySelectorAll("[data-opp-open]").forEach(function(el){el.onclick=function(){
      open(el.dataset.oppOpen);};});
    info(status);
  }
  function payload(){
    if(!profile||!name.trim()||!selected.length||selected.some(function(c){
      return !c.task_id||!c.candidate_id||!c.kind;}))
      throw Error("Choose population, scenario name and explicit Task configurations.");
    var ids=selected.map(function(x){return x.task_id;});
    if(new Set(ids).size!==ids.length)throw Error("Only one candidate per Task.");
    return {name:name.trim(),choices:selected.map(function(x){return {
      task_id:x.task_id,kind:x.kind,candidate_id:x.candidate_id};}),
      benchmark_weight:weight};
  }
  async function run(save){
    var token=++generation;
    try{var data=payload();info(save?"Saving frozen scenario…":"Recalculating current potential…");
      var value=save?await provider.create(profile,data):await provider.preview(profile,data);
      if(token!==generation||!active)return;
      rendered=value.current||value;info(save?"Saved scenario "+value.id:"Current source-backed projection");
      if(save){scenarios=(await provider.bootstrap()).scenarios;}render();
    }catch(error){if(token!==generation)return;info("Projection unavailable: "+error.message);}
  }
  async function open(id){
    var token=++generation;info("Loading saved immutable scenario and fresh source status…");
    try{var data=await provider.detail(id),hist=await provider.revisions(id);
      if(token!==generation||!active)return;
      rendered=data.current||data.snapshot;
      profile=data.profile_id;name=data.scenario.name;weight=data.scenario.benchmark_weight;
      selected=data.scenario.choices.map(function(x){return {
        task_id:x.task_id,kind:x.kind,candidate_id:x.candidate_id};});
      info((data.source_changed?"Underlying evidence changed since snapshot. ":"")+
        "Frozen revision "+data.revision+" · "+
        (hist.revisions||[]).map(function(x){return x.revision;}).join(", "));
      render();
    }catch(error){if(token!==generation)return;info(error.message);}
  }
  async function refresh(){
    if(!active)return;var token=++generation;
    info("Loading authorized planning inputs…");
    try{var data=await provider.bootstrap();
      if(token!==generation||!active)return;
      profiles=data.profiles||[];tasks=data.tasks||[];
      candidates=data.candidates||[];scenarios=data.scenarios||[];
      if(!profile&&profiles.length===1)profile=profiles[0].id;
      render();info("Versioned planning data loaded. No money is computed without explicit selections.");
    }catch(error){if(token!==generation)return;info(
      "Planning API unavailable; no Demo fallback: "+error.message);}
  }
  function setAccess(canRead,canWrite){
    active=!!canRead;write=!!canWrite;++generation;rendered=null;
    root.hidden=!active;
    if(active){surface();refresh();}
    else root.replaceChildren();
  }
  root.hidden=true;return {setAccess:setAccess,refresh:refresh};
}
root.AICompassOpportunities={mount:mount,serverProvider:serverProvider,demoProvider:demoProvider};
})(window);
