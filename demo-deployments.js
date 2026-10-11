/* FUT-15: standalone fictional adapter for the shared deployment UI; never calls Server. */
(function(root){
"use strict";
function copy(v){return JSON.parse(JSON.stringify(v));}
const ACTIONS=["requested","approved","rejected","provisioned","verified","revoked"];
const NEXT={empty:["requested"],requested:["approved","rejected","revoked"],
  approved:["provisioned","rejected","revoked"],provisioned:["verified","revoked"],
  verified:["revoked"],rejected:["requested"],revoked:["requested"]};
function provider(db,persist){
  var targets=db.demoDeploymentTargets||(db.demoDeploymentTargets=[]);
  var source=root.AICompassOpportunities.demoProvider(db);
  function current(t){return t.revisions[t.revisions.length-1];}
  function selected(rev){return rev.selection;}
  function components(id){return ["model","provider","harness"].map(function(kind){
    return {id:kind+"-fictional-"+id,type:kind,revision_id:"fictional-r001"};
  });}
  function beneficiary(t,seat){
    var rev=current(t),selection=selected(rev),status={},setup=false,used=false;
    t.events.filter(function(e){return e.revision===rev.number&&e.seat_key===seat.key;})
      .forEach(function(e){
        if(e.component_id){
          status[e.component_id]=e.action;
          if(["revoked","rejected"].includes(e.action)){setup=false;used=false;}
        }else if(e.action==="setup_verified")setup=true;
        else if(e.action==="setup_revoked"){setup=false;used=false;}
        else if(e.action==="first_use")used=true;
        else if(e.action==="first_use_revoked")used=false;
      });
    var os=seat.available_os||[];
    var blockers=[];
    if(!os.some(function(x){return x==="windows"||x==="linux";}))
      blockers.push("fictional_environment_unknown_or_unsupported");
    selection.components.forEach(function(c){
      if(status[c.id]!=="verified")blockers.push("entitlement_unverified:"+c.id);
    });
    if(!selection.guide_revision_id)blockers.push("fictional_guide_missing");
    if(!setup)blockers.push("setup_not_verified");
    if(selection.status!=="selected")blockers.push("target_retired");
    var ready=!blockers.length;
    return {key:seat.key,person_profile_id:seat.person_profile_id||null,entitlements:status,
      os:blockers.some(function(x){return x.startsWith("fictional_environment");})?
        "unknown":"compatible",
      setup_verified:setup,ready:ready,first_use_confirmed:used,
      activated:ready&&used,blockers:blockers};
  }
  function view(t,privateView){
    var r=current(t),ss=r.selection.seats.map(function(s){return beneficiary(t,s);});
    var doc={id:t.id,profile_id:t.profile_id,task_id:t.task_id,
      candidate_id:t.candidate_id,kind:t.kind,revision:"r"+String(r.number).padStart(3,"0"),
      revision_id:"fictional-demo-"+r.number,status:r.selection.status,
      source:r.selection.source,components:r.selection.components,
      guide_revision_id:r.selection.guide_revision_id,origin_snapshot_id:null,
      selected_count:ss.length,ready_count:ss.filter(function(s){return s.ready;}).length,
      activated_count:ss.filter(function(s){return s.activated;}).length,
      population_headcount:2,derived_at_read_time:true,fictional_demo_only:true};
    if(privateView){
      doc.beneficiaries=ss;
      doc.events=t.events.map(function(e){return {id:e.id,seat_key:e.seat_key,
        component_id:e.component_id,action:e.action,reference:e.evidence_reference,
        actor:"Fictional Demo planner",at:e.at};});
    }
    return doc;
  }
  function validateSelection(data,original){
    if(!data||!Array.isArray(data.seats)||data.seats.length<1||data.seats.length>2)
      throw Error("Demo cohort has exactly two possible fictional seats");
    var keys=new Set();
    var seats=data.seats.map(function(s){
      if(!s||typeof s.key!=="string"||!/^[A-Za-z0-9_-]{1,64}$/.test(s.key)||keys.has(s.key))
        throw Error("Unique fictional seat key required");
      keys.add(s.key);
      var os=s.available_os;
      if(os!=null&&(!Array.isArray(os)||os.some(function(x){
        return !["windows","linux","macos"].includes(x);})||!os.length))
        throw Error("Invalid fictional OS declaration");
      return {key:s.key,person_profile_id:s.person_profile_id||null,available_os:os||null};
    });
    var status=data.status||"selected";
    if(!["selected","retired"].includes(status))throw Error("Invalid status");
    var guide=data.guide_revision_id===undefined?
      (original&&original.guide_revision_id||"gui-fictional-demo-r001"):
      data.guide_revision_id;
    return {status:status,seats:seats,
      components:original?copy(original.components):[],
      source:original?copy(original.source):null,guide_revision_id:guide||null};
  }
  function save(){if(typeof persist==="function")persist();}
  var api=async function(path,method,data){
    method=method||"GET";
    if(path==="profiles"&&method==="GET")return {
      results:(await source.bootstrap()).profiles};
    if(path==="opportunities/candidates"&&method==="GET")return {
      results:(await source.bootstrap()).candidates};
    if(path==="deployments"&&method==="GET")return {
      results:targets.map(function(t){return view(t,false);})};
    if(path==="deployments"&&method==="POST"){
      var opts=(await source.bootstrap());
      if(!data||data.profile_id!=="wlp-demo"||!opts.candidates.some(function(c){
        return c.task_id===data.task_id&&c.candidate_id===data.candidate_id&&
          c.kind===data.kind;}))
        throw Error("Choose a fictional published Task and candidate");
      if(data.scenario_id)throw Error("Demo scenario links are not authoritative");
      if(targets.some(function(t){return t.task_id===data.task_id&&
        t.kind===data.kind&&t.candidate_id===data.candidate_id;}))
        throw Error("Revise the existing Demo target instead");
      var selection=validateSelection(data.selection);
      selection.components=components(data.candidate_id);
      selection.source={type:"fictional_"+data.kind,id:data.candidate_id,
        revision_id:"fictional-r001"};
      var t={id:"dpt-fictional-"+(targets.length+1),task_id:data.task_id,
        candidate_id:data.candidate_id,kind:data.kind,profile_id:data.profile_id,
        revisions:[{number:1,selection:copy(selection),at:new Date().toISOString()}],
        events:[]};
      targets.push(t);save();return view(t,true);
    }
    var match=path.match(/^deployments\/(dpt-fictional-\d+)(?:\/(events|revisions))?$/);
    if(!match)throw Error("Unknown Demo planning endpoint");
    var t=targets.find(function(x){return x.id===match[1];});
    if(!t)throw Error("Unknown fictional target");
    var r=current(t),rev="r"+String(r.number).padStart(3,"0");
    if(method==="GET"&&match[2]==="revisions")
      return {id:t.id,revisions:t.revisions.map(function(x){return {
        revision:"r"+String(x.number).padStart(3,"0"),
        selection:copy(x.selection),actor:"Fictional Demo planner",
        revision_id:"fictional-demo-"+x.number,created_at:x.at};})};
    if(method==="GET"&&!match[2])return view(t,true);
    if(!data||data.expected_revision!==rev)throw Error("Stale fictional target revision");
    if(method==="PATCH"&&!match[2]){
      t.revisions.push({number:r.number+1,
        selection:validateSelection(data.selection,r.selection),at:new Date().toISOString()});
      save();return view(t,true);
    }
    if(method!=="POST"||match[2]!=="events")throw Error("Unsupported Demo operation");
    var seat=r.selection.seats.find(function(s){return s.key===data.seat_key;});
    if(!seat||r.selection.status!=="selected")throw Error("Unknown or retired fictional seat");
    var action=data.action,component=data.component_id,reference=data.evidence_reference||"";
    var state=beneficiary(t,seat);
    if(ACTIONS.includes(action)){
      if(!r.selection.components.some(function(c){return c.id===component;})||
        !NEXT[state.entitlements[component]||"empty"].includes(action))
        throw Error("Invalid fictional entitlement transition");
    }else if(["setup_verified","setup_revoked","first_use","first_use_revoked"].includes(action)){
      if(component!==null)throw Error("Usage and setup cannot claim component grants");
      if(action==="setup_verified"&&(state.setup_verified||state.blockers.some(function(x){
        return x!=="setup_not_verified";})))throw Error("Missing fictional rights, OS or guide");
      if(action==="first_use"&&(!state.ready||state.first_use_confirmed))
        throw Error("External access and setup required before fictional first use");
      if(action==="setup_revoked"&&!state.setup_verified)
        throw Error("Fictional setup not verified");
      if(action==="first_use_revoked"&&!state.first_use_confirmed)
        throw Error("Fictional first use not confirmed");
    }else throw Error("Unknown fictional action");
    if(["verified","setup_verified","first_use"].includes(action)&&reference.trim().length<8)
      throw Error("Use a non-secret fictional evidence reference");
    t.events.push({id:"evt-fictional-"+(t.events.length+1),revision:r.number,
      seat_key:seat.key,component_id:component,action:action,
      evidence_reference:reference,at:new Date().toISOString()});
    save();return {event_id:t.events[t.events.length-1].id,target:view(t,true)};
  };
  api.activatedCount=function(profile,task,kind,candidate){
    var target=targets.find(function(x){return x.profile_id===profile&&x.task_id===task&&
      x.kind===kind&&x.candidate_id===candidate;});
    return target?view(target,false).activated_count:0;
  };
  api.mine=function(userId){
    var own=[];
    targets.forEach(function(target){
      view(target,true).beneficiaries.filter(function(x){
        return x.person_profile_id==="demo-person-"+userId;
      }).forEach(function(x){own.push({target_id:target.id,task_id:target.task_id,
        candidate_id:target.candidate_id,kind:target.kind,ready:x.ready,
        first_use_confirmed:x.first_use_confirmed,blockers:x.blockers,
        entitlements:x.entitlements});});
    });
    return {results:own};
  };
  return api;
}
root.AICompassDemoDeployments={provider:provider,
  activatedCount:function(db,profile,task,kind,candidate){
    return provider(db).activatedCount(profile,task,kind,candidate);
  }};
})(window);
