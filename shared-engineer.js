/* FUT-12: one Engineer Task ↔ measured Solution experience; distinct Demo/Server adapters. */
(function(root){
"use strict";
function safe(text){return String(text==null?"":text).replace(/[&<>"']/g,function(x){
  return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[x];});}
function serverProvider(fetcher,csrf){
  var request=root.AICompassRuntime.ServerTransport(fetcher,csrf).request;
  return {
    list:function(view,all){return request("/api/v1/engineer/workspace?view="+
      encodeURIComponent(view)+"&all_tasks="+(all?"true":"false"));},
    detail:function(id,task){return request("/api/v1/engineer/solutions/"+
      encodeURIComponent(id)+(task?"?task_id="+encodeURIComponent(task):""));},
    feedback:function(kind,context,body){return request("/api/v1/engineer/feedback",
      "POST",{kind:kind,context_id:context,body:body});},
    accessStatus:function(){return request("/api/v1/engineer/deployments");}
  };
}
function demoProvider(db,actor,persist){
  /* Demo stays fictional, editable and entirely offline. No v1 API calls. */
  function declaredOs(){
    var rows=(db.environmentHistory||[]).filter(function(x){return actor&&x.user===actor.id;});
    var last=rows[rows.length-1];
    var value=last&&Array.isArray(last.available_os)&&last.available_os.length?
      last.available_os.slice():null;
    var composer=root.AICompassEnvironment;
    return composer&&typeof composer.normalize==="function"?
      composer.normalize(value):(value||null);
  }
  function configurationOs(solutionId){
    /* Synthetic Demo OS classification reuses the FUT-06 composer: never a new
     * scoring formula, and an unclassified component stays explicitly unknown. */
    var composer=root.AICompassEnvironment;
    if(!composer||typeof composer.compose!=="function")
      return {configured:false,value:{status:"unknown",supported_os:null,
        reason:"OS compatibility is not available in this host: state is Unknown"}};
    var solution=db.solutions.find(function(x){return x.id===solutionId;});
    if(!solution)return {configured:false,value:null};
    var refs=solution.componentRefs||{};
    var parts=Object.keys(refs).map(function(kind){
      return db.components.find(function(c){return c.id===refs[kind];});
    }).filter(Boolean);
    var available=declaredOs();
    return {configured:!!available,value:composer.compose(parts,available,"shared_os")};
  }
  function observations(){
    var result={},byCase=Object.fromEntries(db.cases.map(function(x){return [x.id,x];}));
    db.runs.filter(function(r){return r.status==="published"&&!r.withdrawn&&!r.frameworkAggregate;})
      .forEach(function(r){
        var c=byCase[r.case],s=db.solutions.find(function(x){return x.id===r.solution;});
        if(!c||!s)return;
        var key=c.task+"|"+s.id;
        (result[key]||(result[key]=[])).push(r);
      });
    return result;
  }
  function project(){
    var out={},group=observations();
    Object.keys(group).forEach(function(key){
      var parts=key.split("|"),tid=parts[0],sid=parts[1],rs=group[key];
      var s=db.solutions.find(function(x){return x.id===sid;});if(!s)return;
      var yes=rs.filter(function(r){return r.accepted;}).length;
      var no=rs.length-yes;
      var condition=!yes?"failed_only":no?"conflicting_evidence":"accepted_observed";
      var os=configurationOs(s.id).value;
      var access={status:s.accessible?"accessible":"not_accessible",
        personal_entitlement:"unknown_unverified",grant_provisioned:false};
      var compatible=os.status==="compatible";
      (out[tid]||(out[tid]=[])).push({
        task_id:tid,solution_id:sid,name:s.name,evidence_class:"measured_demo",
        outcome_status:condition,
        suitability:(condition==="accepted_observed"&&s.accessible&&compatible)?
          "supported_observation":(condition==="accepted_observed"&&s.accessible&&
          os.status==="other_os")?"other_os_observation":"unverified_or_not_suitable",
        published_run_count:rs.length,accepted_run_count:yes,failed_run_count:no,
        observed_test_case_count:new Set(rs.map(function(r){return r.case;})).size,
        scoring:{policy:"descriptive_only_v1",score:null,rank:null,
          reason:"No validated aggregate scoring method registered"},
        os:os,enterprise_access:access,
        evidence_refs:rs.map(function(r){return {id:r.id,revision:"r001",
          outcome:r.accepted?"accepted":"failed",test_case_id:r.case};})
      });
    });
    return out;
  }
  return {
    list:async function(view,all){
      var per=project();
      var relevant=actor&&actor.role==="engineer"?["t5","t6","t7"]:[],
          byId=Object.fromEntries(db.tasks.map(function(t){return [t.id,t];}));
      var visible=new Set(relevant);
      relevant.forEach(function(id){var p=byId[id]&&byId[id].parent;
        while(p&&byId[p]&&!visible.has(p)){visible.add(p);p=byId[p].parent;}});
      var rows=db.tasks.filter(function(t){return all||visible.has(t.id);})
        .map(function(t){return {id:t.id,parent_id:t.parent,name:t.name,
          description:t.desc,relevant:relevant.includes(t.id),
          configurations:per[t.id]||[]};});
      var tools={};
      rows.forEach(function(t){t.configurations.forEach(function(o){
        var item=tools[o.solution_id]||(tools[o.solution_id]={solution_id:o.solution_id,
          name:o.name,tasks:[]});
        item.tasks.push({task_id:t.id,task_name:t.name,relevant:t.relevant,observation:o});
      });});
      return {mode:"engineer_demo",view:view,all_tasks:all,
        profile:{status:relevant.length?"simulated_person_profile":"not_configured",
          source:"fictional_demo_only",relevant_task_ids:relevant},
        user_os:{configured:!!declaredOs(),available_os:declaredOs(),
          status:declaredOs()?"declared_fictional":"unconfigured"},
        tasks:rows,tools:Object.values(tools).sort(function(a,b){return a.name.localeCompare(b.name);}),
        scoring_policy:"descriptive_only_v1",theoretical:{mixed_with_measured:false,
          discover_in:"Demo Technology Watch"},message:"Fictional offline Demo evidence, not current Server publications"};
    },
    detail:async function(id,task){
      var rows=project(),s=db.solutions.find(function(x){return x.id===id;});
      if(!s)return null;
      var found=Object.keys(rows).filter(function(t){return !task||task===t;})
        .map(function(t){return rows[t].find(function(x){return x.solution_id===id;});}).filter(Boolean);
      if(!found.length)return null;
      var o=found[0],all=Object.keys(rows).filter(function(t){return rows[t].some(function(x){return x.solution_id===id;});});
      var guide=db.guides.find(function(g){return g.status==="published"&&g.type==="Guide"&&
        (s.id==="s2"?g.id==="g2":false);});
      return {id:id,name:s.name,task_id:o.task_id,overview:o,
        other_tasks:all.filter(function(t){return t!==o.task_id;}).map(function(t){return {id:t};}),
        guide:{status:guide?"demo_document_only":"no_current_published_guide",
          user_guide:"not_registered",
          current:guide?{source:{id:guide.id,revision:"demo",name:guide.title},
            ready:false,sections:[{name:guide.title,text:guide.body}]}:null},
        editorial:[{id:"demo",decision:s.recommendation,
          rationale:s.description,limitations:s.limitations,editorial_only:true}],
        entitlement:"unknown_unverified",feedback:{context_id:id,
          request_status:"not_provisioned"}};
    },
    accessStatus:async function(){
      return actor&&root.AICompassDemoDeployments?
        root.AICompassDemoDeployments.provider(db).mine(actor.id):{results:[]};
    },
    feedback:async function(kind,context,body){
      if(!body||!body.trim())throw Error("Please provide a concrete message.");
      if(kind==="feedback"&&!db.solutions.some(function(s){return s.id===context;}))
        throw Error("Feedback must reference a measured Solution.");
      if(kind==="idea"&&!db.tasks.some(function(t){return t.id===context;}))
        throw Error("Idea needs a Task context.");
      var row={id:"demo-feedback-"+Date.now(),author:actor.id,
        type:kind==="feedback"?"Experience":kind==="request"?"Access interest":"Idea",
        target:context,title:kind==="request"?"Expressed interest":kind==="idea"?"New need":"Usage feedback",
        body:body.trim(),status:"new",date:new Date().toISOString().slice(0,10)};
      db.feedback.push(row);persist();
      return {id:row.id,status:"demo_discussion_recorded_not_a_ticket",
        entitlement_granted:false};
    }
  };
}
function mount(container,provider,mode){
  var routeParams=new URLSearchParams(root.location.search);
  var active=false,view=routeParams.get("view")==="tool"?"tool":"task",
      all=routeParams.get("all_tasks")==="true",selected=null,opened={},
      generation=0,draft={kind:"feedback",body:""},latest=null,alert="";
  String(routeParams.get("collapsed")||"").split(",").slice(0,60).forEach(function(id){
    if(/^[a-zA-Z0-9_-]{1,70}$/.test(id))opened[id]=false;
  });
  function scopedLink(task,solution,extra) {
    var p={view:view,from:root.AICompassContext.returnTo(mode,"")};
    if(all)p.all_tasks="true";
    if(task)p.task=task;
    if(solution)p.solution=solution;
    var url=new URL(root.AICompassContext.route(mode,
      routeParams.get("workspace")==="workgroup"?"workgroup":"engineer",
      routeParams.get("workspace")==="workgroup"?"engineer":"home",p),root.location.origin);
    // view and expansion are ephemeral navigation filters only.
    if(all)url.searchParams.set("all_tasks","true");
    var closed=Object.keys(opened).filter(function(k){return opened[k]===false;}).slice(0,60);
    if(closed.length)url.searchParams.set("collapsed",closed.join(","));
    if(extra)Object.keys(extra).forEach(function(k){
      if(extra[k]==null)url.searchParams.delete(k);else url.searchParams.set(k,String(extra[k]));
    });
    return url.pathname+url.search;
  }
  function message(text){alert=text||"";var node=container.querySelector("[data-engineer-status]");
    if(node)node.textContent=alert;}
  function shell(){
    container.innerHTML='<div class="server-card"><div class="server-model-toolbar">'+
      '<div><h2>My AI Workspace</h2><p class="muted small">Task-first published measurement discovery'+
      (mode==="demo"?" · fictional offline Demo":" · current authorized Server evidence")+
      '</p></div><button type="button" data-engineer-refresh>Refresh</button></div>'+
      '<p role="status" data-engineer-status></p><div data-engineer-body></div></div>';
    container.querySelector("[data-engineer-refresh]").onclick=function(){refresh();};
  }
  function controls(){
    return '<div class="server-actions"><button type="button" data-engineer-view="task"'+
      (view==="task"?' disabled':'')+'>By Task</button>'+
      '<button type="button" data-engineer-view="tool"'+(view==="tool"?' disabled':'')+
      '>By Tool</button> <button type="button" data-engineer-all>'+
      (all?"Focus on my Tasks":"Explore all Tasks and solutions")+'</button></div>';
  }
  function badge(o){
    return '<span class="muted small">Measured · '+safe(o.outcome_status.replaceAll("_"," "))+
      ' · '+o.accepted_run_count+' accepted / '+o.failed_run_count+' failed'+
      ' · '+o.observed_test_case_count+' observed Test Case(s)</span>';
  }
  function osLabel(o){
    /* Unknown, unconfigured and other-OS states are stated explicitly; no
     * invented rank, eligibility or hidden removal of an interesting tool. */
    var os=o.os||{},status=os.status;
    if(status==="compatible")
      return {text:"OS compatible ("+osNames(os.supported_os,", ")+")",kind:"compatible"};
    if(status==="other_os")
      return {text:"Requires "+osNames(os.requires_os||os.supported_os)+
        " — alternative kept discoverable",kind:"other_os"};
    if(status==="unconfigured_user")
      return {text:"OS availability not configured on this account",kind:"unknown"};
    if(status==="unsupported_combination")
      return {text:"No common OS across this Harness/Framework configuration",kind:"unknown"};
    if(status==="unknown_topology")
      return {text:"Distributed topology unverified: OS compatibility unknown",kind:"unknown"};
    return {text:"OS support unknown — not classified for this configuration",kind:"unknown"};
  }
  function osNames(list,separator){
    return (list||[]).map(function(x){
      var value=String(x);
      return value.charAt(0).toUpperCase()+value.slice(1);
    }).join(separator||" or ");
  }
  function accessibility(o){
    var os=osLabel(o),access=o.enterprise_access||{};
    return '<p class="muted small">'+safe(os.text)+
      (os.kind==="other_os"?' <span class="ux-os-alternative">Requires '+
        safe(osNames(o.os.requires_os))+'</span>':"")+
      ' · Enterprise availability: '+safe(access.status||"unknown")+
      ' · Personal entitlement: '+safe(access.personal_entitlement||"unknown_unverified")+
      (access.grant_provisioned?' · Grant provisioned':' · No provisioned grant')+'</p>'+
      (o.os&&o.os.reason?'<p class="muted small">'+safe(o.os.reason)+'</p>':"");
  }
  function option(o,task){
    var positive=o.suitability==="supported_observation";
    return '<div class="list-row"><div><strong>'+safe(o.name)+'</strong>'+
      '<p>'+badge(o)+'</p>'+accessibility(o)+
      '<p class="muted small">'+(positive?
        "Observed accepted DoD — evidence coverage is shown, not a numeric rank":
        o.suitability==="other_os_observation"?
          "Not on your declared OS. Measured evidence is kept visible as a secondary alternative; changing your OS availability re-evaluates it.":
          "Not a verified positive recommendation; review applicability, unknown states and negative evidence")+
      '</p></div><button type="button" data-engineer-detail="'+safe(o.solution_id)+
      '" data-engineer-task="'+safe(task)+'">Inspect</button></div>';
  }
  function taskRows(){
    var byParent={},data=latest.tasks||[];
    data.forEach(function(t){(byParent[t.parent_id||"_"]||(byParent[t.parent_id||"_"]=[])).push(t);});
    function render(parent,depth,seen){
      if(depth>20)return "";
      return (byParent[parent]||[]).map(function(t){
        if(seen.includes(t.id))return "";
        var positive=t.configurations.filter(function(x){return x.suitability==="supported_observation";});
        var other=t.configurations.filter(function(x){return x.suitability!=="supported_observation";});
        var expanded=opened[t.id]!==false;
        var children=render(t.id,depth+1,seen.concat(t.id));
        var content='<div style="margin-left:12px">'+
          '<div class="server-model-toolbar"><button type="button" data-engineer-expand="'+safe(t.id)+
          '" aria-expanded="'+expanded+'">'+(expanded?"−":"+")+'</button>'+
          '<strong>'+safe(t.name)+'</strong>'+
          (t.relevant?'<span class="muted small">My relevant Task</span>':'')+'</div>'+
          (expanded?'<div>'+((positive.length?positive.slice(0,3).map(function(x){
            return option(x,t.id);}).join(""):"<p class='muted small'>No verified suitable "+
            "configuration for this Task under the current profile, OS and access state. "+
            "Alternatives below state their exact Unknown / unavailable state.</p>")+
          (positive.length>3?'<button type="button" data-engineer-more="'+safe(t.id)+
            '">More relevant options ('+(positive.length-3)+')</button>':'')+
          other.map(function(x){return option(x,t.id);}).join(""))+'</div>'+children:"")+'</div>';
        return content;
      }).join("");
    }
    return render("_",0,[]);
  }
  function toolRows(){
    return (latest.tools||[]).map(function(tool){
      return '<article class="list-row"><h3>'+safe(tool.name)+'</h3>'+
        tool.tasks.map(function(t){return '<div><strong>'+safe(t.task_name)+'</strong>'+
          option(t.observation,t.task_id)+'</div>';}).join("")+'</article>';
    }).join("")||'<p>No measured configurations for these Tasks.</p>';
  }
  function content(){
    if(!latest)return;
    var body=container.querySelector("[data-engineer-body]");
    if(selected){renderDetail();return;}
    var profileLabels={"configured":"configured from the authorized Server profile",
      "simulated_person_profile":"simulated fictional Demo profile"};
    var profileLabel=profileLabels[latest.profile.status] ||
      (latest.profile.status==="not_configured"?
        "Not configured — Task relevance is not inferred and no Task membership is invented":
        safe(latest.profile.status));
    body.innerHTML=controls()+
      '<p class="muted small">Workload profile: '+profileLabel+
      ' · Declared OS: '+safe((latest.user_os.available_os||[]).join(", ")||
        "not configured (Unknown)")+
      '. Enterprise availability does not prove personal entitlement. Accepted DoD does not prove general suitability.</p>'+
      (latest.user_os.configured===false?
        '<p class="muted small" data-engineer-os-unknown>OS availability is not configured: exactly which '+
        'Windows/Linux alternatives apply is Unknown until you declare it in "My OS environment".</p>':"")+
      (latest.message?'<p class="muted small">'+safe(latest.message)+'</p>':'')+
      '<details><summary>My external-tool access and first use ('+
      (latest.deployment_status||[]).length+')</summary>'+
      ((latest.deployment_status||[]).map(function(s){
        return '<p class="muted small">'+safe(s.candidate_id)+' · '+
          (s.ready?'Ready':'Not ready')+' · '+
          (s.first_use_confirmed?'First use confirmed':'First use unconfirmed')+
          ' · '+safe((s.blockers||[]).join("; "))+'</p>';}).join("")||
       '<p>No selected deployment linked to your person profile.</p>')+'</details>'+
      (view==="task"?taskRows():toolRows())+
      '<p class="muted small">Theoretical Forecasts are NOT measured results. '+
      'Use the separate Results Explorer / Technology Watch for experimental candidates.</p>';
    body.querySelectorAll("[data-engineer-view]").forEach(function(b){b.onclick=function(){
      root.location.assign(scopedLink(null,null,{view:b.dataset.engineerView}));};});
    body.querySelector("[data-engineer-all]").onclick=function(){
      root.location.assign(scopedLink(null,null,{all_tasks:all?null:"true"}));};
    body.querySelectorAll("[data-engineer-expand]").forEach(function(b){b.onclick=function(){
      opened[b.dataset.engineerExpand]=b.getAttribute("aria-expanded")==="true"?false:true;
      var u=new URL(root.location.href);
      var ids=Object.keys(opened).filter(function(id){return opened[id]===false;}).slice(0,60);
      if(ids.length)u.searchParams.set("collapsed",ids.join(","));
      else u.searchParams.delete("collapsed");
      root.history.replaceState(root.history.state,"",u.pathname+u.search+u.hash);
      content();};});
    body.querySelectorAll("[data-engineer-more]").forEach(function(b){b.onclick=function(){
      var task=b.dataset.engineerMore,t=latest.tasks.find(function(x){return x.id===task;});
      var options=t.configurations.filter(function(x){return x.suitability==="supported_observation";});
      b.outerHTML=options.slice(3).map(function(x){return option(x,task);}).join("");
      bindDetail();};});
    bindDetail();
  }
  function bindDetail(){
    container.querySelectorAll("[data-engineer-detail]").forEach(function(b){b.onclick=function(){
      root.location.assign(scopedLink(b.dataset.engineerTask,b.dataset.engineerDetail));};});
  }
  async function inspect(id,task){
    selected={id:id,task:task,record:null};
    content();message("Loading exact published source detail…");
    var at=++generation;
    try{
      var row=await provider.detail(id,task);
      if(at!==generation||!active)return;
      if(!row)throw Error("No active published Solution for this Task");
      selected.record=row;content();message("");
    }catch(error){if(at!==generation)return;selected=null;content();message(error.message);}
  }
  function renderDetail(){
    var body=container.querySelector("[data-engineer-body]");
    if(!selected.record){
      body.innerHTML='<button type="button" data-engineer-back>Back to discovery</button>'+
        '<p>Loading published details…</p>';
      body.querySelector("[data-engineer-back]").onclick=back;return;
    }
    var row=selected.record,o=row.overview,g=row.guide;
    var guide=g.current&&g.current.ready?
      '<h4>Currently applicable published Setup Guide · '+safe(g.current.source.revision)+'</h4>'+
      g.current.sections.map(section).join(""):
      '<p>No verified currently applicable published setup recipe. Do not reuse the recorded setup as a current installation guarantee.</p>';
    var historical=g.historical?
      '<details><summary>Historical setup used in measured Run · '+safe(g.historical.source.revision)+'</summary>'+
      g.historical.sections.map(section).join("")+'</details>':"";
    var notes=(row.editorial||[]).map(function(x){
      return '<div class="list-row"><p><strong>Editorial decision (not a score): '+
        safe(x.decision||"not specified")+'</strong> · '+safe(x.revision||"")+
        ' · '+safe(x.evidence_freshness||"not verified")+'</p>'+
        '<p>'+safe(x.rationale||"")+'</p><p>Limitations: '+safe(x.limitations||"")+'</p></div>';
    }).join("")||"<p>No published editorial Recommendation for this Task and configuration.</p>";
    body.innerHTML='<nav aria-label="Engineer breadcrumbs" class="ux-engineer-breadcrumbs"><a data-engineer-home href="'+safe(scopedLink(null,null,{task:null,solution:null}))+'">'+
      'My AI Workspace</a> › '+safe(row.task_id)+' › '+safe(row.name)+'</nav>'+
      '<h3>'+safe(row.name)+'</h3>'+
      '<p>'+badge(o)+'</p>'+accessibility(o)+
      '<h4>My verified deployment state</h4>'+
      ((latest.deployment_status||[]).filter(function(s){return s.candidate_id===row.id;})
        .map(function(s){return '<p>'+safe(s.task_id)+' · '+
          (s.ready?'Ready':'Not ready')+' · '+
          (s.first_use_confirmed?'First use confirmed':'Not confirmed')+
          ' · '+safe((s.blockers||[]).join("; "))+'</p>';}).join("")||
          '<p>No personally linked deployment.</p>')+
      '<p>Methodology: '+safe(o.scoring.policy)+
      ' · No numeric ranking until an authorized scoring policy is defined.</p>'+
      '<h4>Measured Test Case coverage and original sources</h4>'+
      (o.evidence_refs||[]).map(function(r){
        var uri=root.AICompassContext.route(mode,
          mode==="server"?"engineer":"engineer","results",{
          record:r.id,revision:r.revision,task:row.task_id,solution:row.id
        });
        return '<p>'+safe(r.test_case_id)+' · '+safe(r.id)+' · '+safe(r.revision)+
          ' · '+safe(r.outcome)+' · <a href="'+safe(uri)+'">Open measured Run and provenance</a></p>';
      }).join("")+
      '<section id="ux-engineer-setup"><h4>Setup Guide for this configuration</h4>'+guide+historical+'</section>'+
      '<p>User Guide / charter: '+safe(g.user_guide||"not_registered")+
      ' (separate from technical Setup Guide).</p>'+
      '<h4>Published editorial context</h4>'+notes+
      '<h4>Published contextual Workgroup updates / discussions</h4>'+
      (row.published_updates||[]).map(function(u){
        return '<details><summary>'+safe(u.title)+' · '+safe(u.context_id)+'</summary>'+
          '<p>'+safe(u.summary||u.body||"Published contextual discussion reference")+'</p>'+
          (mode==="server"?' <a href="/api/v1/discussions/'+
             encodeURIComponent(u.id)+'" target="_blank" rel="noopener noreferrer">Advanced: original authorized discussion source</a>':'')+
          '</details>';
      }).join("")+
      '<h4>Other measured Tasks</h4>'+
      (row.other_tasks||[]).map(function(t){return '<button type="button" data-engineer-other="'+safe(t.id)+
        '">'+safe(t.id)+'</button>';}).join("")+
      '<section id="ux-engineer-feedback"><h4>Feedback and unmet needs</h4>'+
      '<p class="muted small">Feedback is self-reported. Access interest is not a grant, approval, purchase or support ticket.</p>'+
      '<label>Purpose<select data-engineer-kind>'+
      '<option value="feedback">Feedback on actual use</option>'+
      '<option value="request">Express interest in access</option>'+
      '<option value="idea">Suggest an unmet need for this Task</option></select></label>'+
      '<label>Comment<textarea data-engineer-comment maxlength="16000"></textarea></label>'+
      '<button type="button" data-engineer-send>Record discussion</button></section>';
    var purpose=body.querySelector("[data-engineer-kind]"),
        comment=body.querySelector("[data-engineer-comment]");
    purpose.value=draft.kind;comment.value=draft.body;
    purpose.onchange=function(){draft.kind=purpose.value;};
    comment.oninput=function(){draft.body=comment.value;};
    body.querySelectorAll("[data-engineer-other]").forEach(function(b){
      b.onclick=function(){root.location.assign(scopedLink(b.dataset.engineerOther,row.id));};});
    body.querySelector("[data-engineer-send]").onclick=async function(){
      var kind=purpose.value,ctx=kind==="idea"?row.task_id:row.id;
      if(comment.value.trim().length<8){message("Add a meaningful comment (at least 8 characters).");return;}
      var submit=this;submit.disabled=true;
      try{var result=await provider.feedback(kind,ctx,comment.value);
        draft={kind:kind,body:""};comment.value="";
        message("Recorded "+result.id+" as a discussion; no entitlement or provisioning was granted.");
      }catch(error){message("Feedback not recorded: "+error.message);}
      finally{submit.disabled=false;}
    };
  }
  function section(row){
    var name=safe(row.name||row.id);
    return '<section class="list-row"><strong>'+name+' · '+safe(row.revision||"")+'</strong>'+
      (row.text?'<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+safe(row.text)+'</pre>':'')+
      (row.url&&/^https:\/\/|^http:\/\//.test(row.url)?
        '<p><a href="'+safe(row.url)+'" target="_blank" rel="noopener noreferrer">Read source guide</a></p>':'')+'</section>';
  }
  function back(){++generation;selected=null;content();}
  async function refresh(){
    if(!active)return;var at=++generation;
    message("Loading scoped Task and published evidence…");
    try{
      var responses=await Promise.all([provider.list(view,all),
        provider.accessStatus?provider.accessStatus():Promise.resolve({results:[]})]);
      if(!active||at!==generation)return;
      var data=responses[0];data.deployment_status=responses[1].results||[];
      selected=null;latest=data;content();message("");
      var sourceId=routeParams.get("solution"),taskId=routeParams.get("task");
      if(sourceId && taskId)inspect(sourceId,taskId);
    }
    catch(error){if(!active||at!==generation)return;latest=null;
      container.querySelector("[data-engineer-body]").textContent=
        "Published Engineer discovery unavailable. No Demo fallback.";
      message(error.message);}
  }
  function setAccess(enabled){
    active=!!enabled;++generation;selected=null;latest=null;
    container.replaceChildren();container.hidden=!active;
    if(active){shell();refresh();}
  }
  container.hidden=true;return {setAccess:setAccess,refresh:refresh};
}
root.AICompassEngineer={mount:mount,serverProvider:serverProvider,demoProvider:demoProvider};
})(window);
