/* FUT-16: shared budget interaction; Server strictly persisted/authorized, Demo fictional local state. */
(function (root) {
  "use strict";
  function E(x) {
    return String(x == null ? "" : x).replace(/[&<>"']/g, function (c) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
  }
  function serverProvider(fetcher, csrf) {
    async function call(path, method, payload) {
      var res = await fetcher("/api/v1/planning/budgets" + (path || ""), {
        method: method || "GET", credentials: "same-origin", cache: "no-store",
        headers: Object.assign({"Accept":"application/json"},
          method && method !== "GET" ? {"Content-Type":"application/json",
            "X-CSRFToken":typeof csrf === "function" ? csrf() : csrf} : {}),
        body: payload == null ? undefined : JSON.stringify(payload)
      });
      var data = await res.json();
      if (!res.ok) throw Error(data.detail || data.error || "Budget API " + res.status);
      return data;
    }
    return {options:function(){return call("/options");},
      list:function(){return call("");},
      preview:function(d){return call("/preview","POST",d);},
      create:function(d){return call("","POST",d);},
      update:function(id,d){return call("/"+encodeURIComponent(id),"PATCH",d);},
      detail:function(id){return call("/"+encodeURIComponent(id));},
      history:function(id){return call("/"+encodeURIComponent(id)+"/revisions");},
      export:function(id){return call("/"+encodeURIComponent(id)+"/export");}};
  }
  function demoProvider(db, persist) {
    var saved = db.demoResourceBudgets || (db.demoResourceBudgets = []);
    function candidates() {
      var task = (db.tasks || [])[0] || {id:"tsk-demo",name:"Fictional task"};
      return [{kind:"forecast",task_id:task.id,candidate_id:"fct-demo-budget",
        name:"Fictional forecast / unmeasured pilot",
        components:{"root:model":"mdl-demo","root:provider":"prv-demo","root:harness":"hrn-demo"}}];
    }
    async function options() {
      var targets=[];
      if(root.AICompassDemoDeployments) {
        var data=await root.AICompassDemoDeployments.provider(db,persist)("deployments","GET");
        targets=data.results.filter(function(t){return t.kind==="benchmark";});
      } else {
        targets=(db.demoDeploymentTargets||[]).filter(function(t){return t.kind==="benchmark";})
          .map(function(t){return {id:t.id,task_id:t.task_id,kind:t.kind,
            candidate_id:t.candidate_id,profile_id:t.profile_id,
            status:"selected",ready_count:0,activated_count:0};});
      }
      return {profiles:[{id:"wlp-demo",name:"Fictional Demo cohort",kind:"cohort"}],
        candidates:candidates(),targets:targets,offers:[
          {id:"off-demo-sample",revision_id:"fictional-revision",component_id:"prv-demo",
            name:"Fictional Demo tariff (not real)",currency:"EUR",complete:true}]};
    }
    async function preview(req) {
      var p=req.plan, m=Number(p.period_months||3),margin=Number(p.margin_pct||0);
      var items=p.items||[], segments=[],quantities=[],charges=[],gaps=[],variable=0;
      var targets=(await options()).targets;
      for (var item of items) {
        var pilot=item.purpose==="pilot",target=targets.find(function(t){
          return t.id===item.target_id;});
        var count=pilot?Number(item.pilot_headcount):Math.max(0,2-(target?target.ready_count:0));
        if(!pilot && !target)gaps.push("fictional_rollout_target_unknown");
        var allocations=[{purpose:item.purpose,headcount:count}];
        if(!pilot && p.include_active)allocations.push({purpose:"active",
          headcount:target?target.activated_count:0});
        for(var allocation of allocations){
          var total=Number((allocation.headcount * 12 * m/12 * (1+margin/100)).toFixed(2));
          segments.push({purpose:allocation.purpose,
            task_id:item.task_id||(target?target.task_id:"tsk-demo"),
            headcount:allocation.headcount,estimated_task_occurrences:String(total),
            evidence_class:pilot?"fictional_forecast":"fictional_benchmark"});
          if(pilot && !(item.offer_pins||[]).length)gaps.push("fictional_pilot_offer_unselected");
          else {
            var amount=total*0.1;variable+=amount;
            charges.push({charge_type:"variable",native_currency:"EUR",amount:amount.toFixed(2),
              charge_id:"fictional_usage"});
            quantities.push({meter:"requests",quantity:String(total),unit:"requests"});
          }
        }
      }
      return {algorithm:"fictional-demo-resource-v1",fictional_demo_only:true,
        profile_id:req.profile_id,period_months:m,segments:segments,quantities:quantities,
        charges:charges,amounts_by_native_currency:{EUR:{fixed:"0.00",
          variable:variable.toFixed(2),total:variable.toFixed(2)}},
        gaps:gaps,ready_for_request:!gaps.length,
        purpose:"fictional_example_not_real_quote",no_fx_wallet_iam_or_procurement:true};
    }
    async function latest(b) {
      var r=b.revisions[b.revisions.length-1];
      return {id:b.id,profile_id:b.profile_id,revision:"r"+String(r.number).padStart(3,"0"),
        revision_id:"fictional-"+r.number,plan:r.plan,snapshot:r.projection,
        current:await preview({profile_id:b.profile_id,plan:r.plan}),fictional_demo_only:true,
        source_changed:false};
    }
    function get(id) {var b=saved.find(function(x){return x.id===id;});
      if(!b)throw Error("Unknown fictional Demo budget");return b;}
    async function revision(b,plan) {
      var frozen=await preview({profile_id:b.profile_id,plan:plan});
      b.revisions.push({number:b.revisions.length+1,plan:JSON.parse(JSON.stringify(plan)),
        projection:frozen});
      if(persist)persist();
    }
    return {options:options,list:async function(){return {results:saved.map(function(b){
      return {id:b.id,profile_id:b.profile_id,
        revision:"r"+String(b.revisions.length).padStart(3,"0")};})};},
      preview:preview,
      create:async function(req){
        if(!req||!req.plan||!req.profile_id)throw Error("Invalid Demo request");
        var b={id:"bdg-demo-"+(saved.length+1),profile_id:req.profile_id,revisions:[]};
        saved.push(b);
        try{await revision(b,req.plan);}catch(err){saved.pop();throw err;}
        return latest(b);
      },
      update:async function(id,req){var b=get(id);
        if(req.expected_revision!=="r"+String(b.revisions.length).padStart(3,"0"))
          throw Error("Stale Demo revision");
        await revision(b,req.plan);return latest(b);},
      detail:async function(id){return latest(get(id));},
      history:async function(id){return {revisions:get(id).revisions.map(function(r){
        return {revision:"r"+String(r.number).padStart(3,"0"),
          ready_for_request:r.projection.ready_for_request,source_frozen:true};})};},
      export:async function(id){return {type:"resource_request_summary",fictional_demo_only:true,
        budget:await latest(get(id))};}};
  }
  function mount(host, provider, mode) {
    if (!host) return {setAccess:function(){}};
    var allowed=false,canWrite=false,options=null,saved=null,editing=null;
    host.innerHTML='<section class="server-card" aria-label="Budget and Resource Planning">'+
      '<h2>Budget & Resource Planning</h2><p>Forecast pilot · measured rollout · optional active capacity. '+
      'Native offer units and currencies; incomplete assumptions are explicit. '+
      (mode==="demo"?"<strong>Fictional Demo only — no real quotes.</strong>":
       "No automated subscription, procurement or external access grant.")+'</p>'+
      '<p class="server-status" id="budget-state" role="status"></p>'+
      '<form id="budget-form" hidden>'+
      '<label>Budget name <input required name="name" maxlength="160" value="Resource request"></label> '+
      '<label>Population <select name="profile" required></select></label> '+
      '<label>Purpose <select name="purpose"><option value="pilot">Experimental pilot</option>'+
      '<option value="rollout">Measured rollout</option></select></label> '+
      '<label>Candidate / selected deployment <select name="candidate" required></select></label> '+
      '<label class="budget-pilot">Pilot seats <input name="seats" type="number" min="1" max="100000" value="2"></label> '+
      '<label>Horizon (months) <input name="months" type="number" min="1" max="24" value="3"></label> '+
      '<label>Capacity margin (%) <input name="margin" type="number" min="0" max="200" step="0.1" value="0"></label> '+
      '<label>Include active capacity <input type="checkbox" name="active"></label>'+
      '<div id="budget-offers"></div>'+
      '<details class="budget-pilot"><summary>Exceptional qualified per-task usage assumptions (JSON, optional)</summary>'+
      '<p>Source-keyed exact meters, e.g. {"root:provider":{"requests":"2"}}. '+
      'A total Forecast token count is not an input/output split.</p>'+
      '<textarea name="meters" rows="2" placeholder="{}">{}</textarea></details>'+
      '<p><button type="button" id="budget-preview">Preview resources</button> '+
      '<button type="submit">Save immutable version</button> '+
      '<button type="button" id="budget-reset">New plan</button></p></form>'+
      '<div id="budget-summary"></div><h3>Saved resource requests</h3>'+
      '<button type="button" id="budget-refresh">Refresh</button><div id="budget-list"></div></section>';
    var state=host.querySelector("#budget-state"),form=host.querySelector("#budget-form"),
        summary=host.querySelector("#budget-summary"),list=host.querySelector("#budget-list");
    function tell(message,bad){state.textContent=message;state.className=bad?"server-status server-error":"server-status";}
    function opt(id,text){return '<option value="'+E(id)+'">'+E(text)+'</option>';}
    function selectCandidates(){
      if(!options)return;
      var profile=form.elements.profile.value,purpose=form.elements.purpose.value,
          choices=(purpose==="pilot"?options.candidates.filter(function(c){return c.kind==="forecast";}):
          options.targets.filter(function(t){return t.profile_id===profile && t.status!=="retired";}));
      form.elements.candidate.innerHTML=choices.map(function(c){
        return opt(purpose==="pilot"?c.candidate_id+"|"+c.task_id:c.id,
          purpose==="pilot"?(c.name+" · "+c.task_id):
           (c.task_id+" · "+c.candidate_id+" · ready "+c.ready_count));
      }).join("");
      host.querySelectorAll(".budget-pilot").forEach(function(el){el.hidden=purpose!=="pilot";});
      selectOffers();
    }
    function selectOffers(){
      var section=host.querySelector("#budget-offers");
      if(form.elements.purpose.value!=="pilot"){section.innerHTML="";return;}
      var candidate=(options.candidates||[]).find(function(c){
        return c.kind==="forecast" &&
          c.candidate_id+"|"+c.task_id===form.elements.candidate.value;});
      if(!candidate){section.textContent="No published Forecast candidate";return;}
      section.innerHTML='<p>Choose explicit offer revisions for billable components; missing tariffs stay visible as gaps.</p>'+
        Object.keys(candidate.components||{}).map(function(key){
          var component=candidate.components[key],offers=options.offers.filter(function(o){
            return o.component_id===component;});
          return '<label>'+E(key)+' ('+E(component)+') <select class="budget-offer" data-key="'+E(key)+'">'+
            opt("","Unknown / unselected — budget incomplete")+
            offers.map(function(o){return opt(o.id+"|"+o.revision_id,o.name+
              " · "+o.currency+(o.complete?"":" · incomplete"));}).join("")+
            '</select></label> ';
        }).join("");
    }
    function payload(){
      var purpose=form.elements.purpose.value, candidate=form.elements.candidate.value,
          item,offers=[],meters={};
      if(!candidate)throw Error("Select a published candidate or selected rollout target");
      if(purpose==="pilot"){
        host.querySelectorAll(".budget-offer").forEach(function(el){
          if(!el.value)return;var parts=el.value.split("|");
          offers.push({source_key:el.getAttribute("data-key"),
            offer_id:parts[0],offer_revision_id:parts[1]});});
        try{meters=JSON.parse(form.elements.meters.value||"{}");}
        catch(_){throw Error("Qualified meter assumptions must be valid JSON");}
        var parts=candidate.split("|");
        item={purpose:"pilot",task_id:parts[1],candidate_id:parts[0],
          pilot_headcount:Number(form.elements.seats.value),
          offer_pins:offers,meter_overrides:meters};
      }else item={purpose:"rollout",target_id:candidate};
      return {profile_id:form.elements.profile.value,plan:{
        name:form.elements.name.value,period_months:Number(form.elements.months.value),
        margin_pct:String(form.elements.margin.value),
        include_active:form.elements.active.checked,items:[item]}};
    }
    function display(data){
      var gaps=data.gaps||[],amounts=data.amounts_by_native_currency||{};
      summary.innerHTML='<h3>Resource request preview</h3>'+
        '<p><strong>'+E(data.ready_for_request?"Complete quote":"Incomplete estimate")+'</strong> · '+
        E(data.period_months)+' months · '+E(data.profile_id)+'</p>'+
        '<h4>Separate purposes</h4><ul>'+(data.segments||[]).map(function(s){
          return '<li>'+E(s.purpose)+' — '+E(s.task_id)+' — '+E(s.headcount)+' people; '+
            E(s.estimated_task_occurrences||"unknown")+' Task occurrences</li>';}).join("")+'</ul>'+
        '<h4>Provider-native requirements</h4><ul>'+(data.quantities||[]).map(function(q){
          return '<li>'+E(q.billing_owner||"fictional")+' / '+E(q.meter)+' ('+
            E(q.credit_namespace||"native units")+'): '+E(q.quantity==null?"unknown":q.quantity)+
            ' · '+E(q.offer_id||"Demo")+'</li>';}).join("")+'</ul>'+
        '<h4>Commercial request (no currency conversion)</h4><ul>'+
        Object.keys(amounts).map(function(c){return '<li>'+E(c)+': fixed '+
          E(amounts[c].fixed)+' + variable '+E(amounts[c].variable)+' = '+
          E(amounts[c].total)+'</li>';}).join("")+'</ul>'+
        '<h4>Missing evidence / commercial gaps</h4>'+
        (gaps.length?'<ul>'+gaps.map(function(g){return '<li>'+E(g)+'</li>';}).join("")+'</ul>':
          '<p>None recorded for this projection.</p>')+
        '<p><small>Annual frequencies are uniformly distributed; source pins are frozen '+
        'when saved. These are forecasts, not invoiced spend or realized savings.</small></p>';
    }
    async function refresh(){
      if(!allowed)return;
      try{
        var all=await Promise.all([provider.options(),provider.list()]);
        options=all[0];saved=all[1].results;
        form.hidden=!canWrite;
        form.elements.profile.innerHTML=options.profiles.map(function(p){
          return opt(p.id,p.name+" ("+p.kind+")");}).join("");
        selectCandidates();
        list.innerHTML=saved.length?saved.map(function(b){
          return '<p><button class="budget-open" type="button" data-id="'+E(b.id)+'">'+
            E(b.id)+'</button> · '+E(b.revision)+' · '+E(b.profile_id)+'</p>';}).join(""):
          '<p>No saved resource requests.</p>';
        tell("Authorized "+mode+" budgets loaded.");
      }catch(err){tell("Budget planning unavailable: "+err.message,true);}
    }
    form.elements.profile.addEventListener("change",selectCandidates);
    form.elements.purpose.addEventListener("change",selectCandidates);
    form.elements.candidate.addEventListener("change",selectOffers);
    host.querySelector("#budget-preview").addEventListener("click",async function(){
      try{var doc=await provider.preview(payload());display(doc);tell("Preview only — nothing saved.");}
      catch(err){tell(err.message,true);}
    });
    form.addEventListener("submit",async function(event){
      event.preventDefault();if(!canWrite)return;
      try{
        var request=payload(),result=editing?await provider.update(editing.id,{
          expected_revision:editing.revision,plan:request.plan}):await provider.create(request);
        editing=result;display(result.snapshot);tell("Immutable budget "+result.id+" "+result.revision+" saved.");
        await refresh();form.elements.profile.value=result.profile_id;
      }catch(err){tell(err.message,true);}
    });
    host.querySelector("#budget-reset").addEventListener("click",function(){
      editing=null;form.reset();summary.innerHTML="";selectCandidates();tell("New resource plan.");
    });
    host.querySelector("#budget-refresh").addEventListener("click",refresh);
    list.addEventListener("click",async function(event){
      var id=event.target.getAttribute("data-id");if(!id)return;
      try{
        var doc=await provider.detail(id);editing=doc;
        var p=doc.plan;
        form.elements.profile.value=doc.profile_id;
        form.elements.name.value=p.name;
        form.elements.months.value=p.period_months;
        form.elements.margin.value=p.margin_pct;
        form.elements.active.checked=p.include_active;
        form.elements.purpose.value=p.items[0].purpose;selectCandidates();
        if(p.items[0].purpose==="pilot"){
          form.elements.candidate.value=p.items[0].candidate_id+"|"+p.items[0].task_id;
          form.elements.seats.value=p.items[0].pilot_headcount;
          form.elements.meters.value=JSON.stringify(p.items[0].meter_overrides||{});
          selectOffers();host.querySelectorAll(".budget-offer").forEach(function(el){
            var match=(p.items[0].offer_pins||[]).find(function(x){
              return x.source_key===el.getAttribute("data-key");});
            if(match)el.value=match.offer_id+"|"+match.offer_revision_id;
          });
        }else form.elements.candidate.value=p.items[0].target_id;
        display(doc.snapshot);
        var h=await provider.history(id);
        var ex=await provider.export(id);
        var extras=host.querySelector("#budget-summary");
        extras.insertAdjacentHTML("beforeend",
          '<p>Frozen history: '+E(h.revisions.map(function(r){return r.revision;}).join(", "))+
          ' <button type="button" id="budget-copy-export">Copy request JSON</button></p>');
        extras.querySelector("#budget-copy-export").addEventListener("click",function(){
          if(navigator.clipboard)navigator.clipboard.writeText(JSON.stringify(ex,null,2))
            .then(function(){tell("Request summary copied.");})
            .catch(function(){tell("Clipboard unavailable; use browser permission.",true);});
        });
        tell("Frozen snapshot shown. Current eligibility may have changed.");
      }catch(err){tell(err.message,true);}
    });
    return {setAccess:function(view,write){allowed=!!view;canWrite=!!write;
      host.hidden=!allowed;if(allowed)refresh();}};
  }
  root.AICompassBudgets={mount:mount,serverProvider:serverProvider,demoProvider:demoProvider};
})(window);
