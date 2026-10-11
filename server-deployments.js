/* FUT-15: Server-only deliberate deployment & external entitlement workflow. */
(function () {
"use strict";
function mount(root, csrf, E) {
  var writable=false, visible=false, generation=0, targets=[], profiles=[], candidates=[], selected=null;
  root.innerHTML='<div class="server-card"><h2>Deployment &amp; External Access</h2>'+
    '<p>Targets are deliberate. Recording a status does not purchase, provision, grant AI Compass rights, or prove use.</p>'+
    '<p id="deployment-message" role="status"></p><button type="button" id="deployment-refresh">Refresh</button>'+
    '<button type="button" id="deployment-new">Select beneficiaries</button>'+
    '<div id="deployment-targets"></div><div id="deployment-form"></div><div id="deployment-details"></div></div>';
  var note=root.querySelector("#deployment-message");
  var items=root.querySelector("#deployment-targets");
  var form=root.querySelector("#deployment-form");
  var details=root.querySelector("#deployment-details");
  var add=root.querySelector("#deployment-new");
  async function api(path, method, data) {
    var opts={method:method||"GET",credentials:"same-origin",cache:"no-store"};
    if(data!==undefined) {
      opts.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
      opts.body=JSON.stringify(data);
    }
    var response=await fetch("/api/v1/planning/"+path,opts);
    var doc=await response.json().catch(function(){return {};});
    if(!response.ok) {
      var error=new Error(doc.detail||doc.error||"HTTP "+response.status);
      error.status=response.status;
      throw error;
    }
    return doc;
  }
  function tell(s, bad) {note.textContent=s;note.className=bad?"server-error":"";}
  function options(rows,id,caption) {
    return '<option value="">'+E(caption||"Choose")+'</option>'+rows.map(function(r){
      return '<option value="'+E(r.id)+'"'+(r.id===id?" selected":"")+'>'+E(
        r.name||r.id)+' · '+E(r.id)+'</option>';
    }).join("");
  }
  function seatsText(seats) {
    return seats.map(function(s){return [s.key,s.person_profile_id||"",
      (s.available_os||[]).join(",")].join(" | ");}).join("\n");
  }
  function readSeats(value) {
    return value.split("\n").map(function(s){return s.trim();}).filter(Boolean).map(function(line) {
      var bits=line.split("|").map(function(s){return s.trim();});
      if(bits.length>3)throw new Error("Use: seat-key | optional person profile ID | windows,linux");
      return {key:bits[0],person_profile_id:bits[1]||null,
        available_os:bits[2]?bits[2].split(",").map(function(s){return s.trim().toLowerCase();}):null};
    });
  }
  function renderList() {
    items.innerHTML=targets.length?'<p>Choose an explicit target to inspect its current verified coverage.</p>'+
      targets.map(function(t){return '<button type="button" data-target="'+E(t.id)+'">'+
        E(t.id)+' · '+E(t.candidate_id)+' · '+E(t.activated_count)+
        '/'+E(t.population_headcount)+' activated</button> ';}).join(""):
      '<p>No real Server deployment targets. No demonstration data is imported.</p>';
  }
  function chooseForm(item) {
    if(!writable)return;
    details.replaceChildren();
    selected=null;
    var edit=Boolean(item), saved=item||{}, seats=(saved.beneficiaries||[]).map(function(s){
      return {key:s.key,person_profile_id:s.person_profile_id,available_os:null};
    });
    // Existing seat declarations, including declared OS, are recovered from the
    // exact target revision endpoint rather than guessed from current readiness.
    function show(actualSeats) {
      form.innerHTML='<form id="deployment-select"><h3>'+
        (edit?"Revise selected deployment":"Select a deployment population")+'</h3>'+
        (edit?'<p>Existing target: '+E(item.id)+'</p>':
         '<label>Population <select name="population" required>'+options(profiles,null,"Choose population")+'</select></label>'+
         '<label>Candidate / Task <select name="candidate" required>'+options(
           candidates.map(function(c){return {id:c.task_id+"|"+c.kind+"|"+c.candidate_id,
            name:c.name+" ("+c.task_id+" · "+c.kind+")"};}),null,"Choose published Task candidate")+
         '</select></label><label>Originating scenario ID (optional)<input name="scenario"></label>')+
        '<label>Beneficiaries, one per line: key | optional person profile ID | optional Windows,Linux'+
        '<textarea name="seats" rows="4" required>'+E(seatsText(actualSeats))+'</textarea></label>'+
        '<label>Pinned setup guide revision UUID (optional; required for readiness)'+
        '<input name="guide" value="'+E(edit?saved.guide_revision_id||"":"")+'"></label>'+
        '<label>Status <select name="status"><option value="selected">Selected</option>'+
        '<option value="retired"'+(saved.status==="retired"?" selected":"")+'>Retired</option></select></label>'+
        '<button type="submit">Save immutable target revision</button>'+
        '<button type="button" id="deployment-cancel">Cancel</button></form>';
      var f=form.querySelector("form");
      form.querySelector("#deployment-cancel").addEventListener("click",function(){form.replaceChildren();});
      f.addEventListener("submit",async function(e){
        e.preventDefault();
        var values=Object.fromEntries(new FormData(f).entries());
        var selection;
        try {selection={seats:readSeats(values.seats),status:values.status};
          if(values.guide)selection.guide_revision_id=values.guide;
        }catch(err){tell(err.message,true);return;}
        var body;
        if(edit)body={expected_revision:item.revision,selection:selection};
        else {
          var parts=(values.candidate||"").split("|");
          if(parts.length!==3){tell("Choose a published candidate",true);return;}
          body={profile_id:values.population,task_id:parts[0],kind:parts[1],
            candidate_id:parts[2],selection:selection};
          if(values.scenario)body.scenario_id=values.scenario;
        }
        f.querySelector('[type="submit"]').disabled=true;
        try {
          var changed=await api(edit?"deployments/"+encodeURIComponent(item.id):"deployments",
                               edit?"PATCH":"POST",body);
          form.replaceChildren();await reload(changed.id);
        }catch(err){tell("Selection rejected: "+err.message,true);}
        finally {if(f.isConnected)f.querySelector('[type="submit"]').disabled=false;}
      });
    }
    if(edit){
      api("deployments/"+encodeURIComponent(item.id)+"/revisions").then(function(history){
        if(!visible)return;
        var last=history.revisions[history.revisions.length-1];
        show(last.selection.seats);
      }).catch(function(err){tell("Cannot read source pins: "+err.message,true);});
    }else show(seats);
  }
  async function inspect(id) {
    try{
      var entry=await api("deployments/"+encodeURIComponent(id));
      if(!visible)return;
      selected=entry;form.replaceChildren();
      var pins=entry.components.map(function(c){return c.id+" ("+c.type+")";}).join(", ");
      details.innerHTML='<h3>'+E(entry.id)+' — '+E(entry.revision)+'</h3>'+
        '<p>'+E(entry.activated_count)+'/'+E(entry.population_headcount)+
        ' confirmed activated; '+E(entry.ready_count)+' ready. Source: '+E(entry.source.id)+
        '. Components: '+E(pins)+'.</p>'+
        (writable?'<button id="deployment-revise" type="button">Revise target</button>':'')+
        '<div style="overflow-x:auto"><table><thead><tr><th>Beneficiary</th><th>Access</th>'+
        '<th>Environment</th><th>Setup</th><th>First use</th><th>Blockers</th></tr></thead><tbody>'+
        entry.beneficiaries.map(function(s){return '<tr><td>'+E(s.key)+'</td>'+
          '<td>'+E(Object.entries(s.entitlements).map(function(e){return e.join(": ");}).join("; ")||"Not requested")+'</td>'+
          '<td>'+E(s.os)+'</td><td>'+E(s.setup_verified?"Verified":"Pending")+'</td>'+
          '<td>'+E(s.first_use_confirmed?"Confirmed":"Not confirmed")+'</td>'+
          '<td>'+E(s.blockers.join("; "))+'</td></tr>';}).join("")+
        '</tbody></table></div>'+
        (writable?'<form id="deployment-event"><h4>Record manual external access or use</h4>'+
          '<label>Beneficiary<select name="seat">'+options(entry.beneficiaries.map(function(s){return {id:s.key,name:s.key};}),null,"Choose")+'</select></label>'+
          '<label>Component (leave empty for setup / first use)<select name="component">'+options(
            entry.components.map(function(c){return {id:c.id,name:c.type+" "+c.id};}),null,"No component")+'</select></label>'+
          '<label>Action<select name="action">'+[
            "requested","approved","rejected","provisioned","verified","revoked",
            "setup_verified","setup_revoked","first_use","first_use_revoked"
          ].map(function(s){return '<option value="'+s+'">'+E(s)+'</option>';}).join("")+'</select></label>'+
          '<label>Non-secret evidence reference<input name="reference" maxlength="300"></label>'+
          '<button type="submit">Record attributed event</button></form>':'')+
        '<details><summary>Recorded events</summary><pre style="white-space:pre-wrap">'+
          E(entry.events.map(function(e){return e.at+" · "+e.actor+" · "+e.seat_key+
           " · "+(e.component_id||"target")+" · "+e.action+" · "+e.reference;}).join("\n"))+
        '</pre></details>';
      if(writable){
        details.querySelector("#deployment-revise").addEventListener("click",function(){chooseForm(entry);});
        details.querySelector("#deployment-event").addEventListener("submit",async function(e){
          e.preventDefault();
          var values=Object.fromEntries(new FormData(e.target).entries());
          var data={expected_revision:entry.revision,seat_key:values.seat,
            component_id:values.component||null,action:values.action,
            evidence_reference:values.reference};
          var button=e.target.querySelector('[type="submit"]');
          button.disabled=true;
          try {await api("deployments/"+encodeURIComponent(entry.id)+"/events","POST",data);
            tell("Attributed event recorded",false);await reload(entry.id);
          }catch(err){tell("Action rejected: "+err.message,true);button.disabled=false;}
        });
      }
    }catch(err){tell("Target unavailable: "+err.message,true);}
  }
  async function reload(id) {
    var n=++generation;
    try {
      var data=await Promise.all([api("deployments"),api("profiles"),
        api("opportunities/candidates")]);
      if(!visible||n!==generation)return;
      targets=data[0].results;profiles=data[1].results;candidates=data[2].results;
      renderList();add.hidden=!writable;
      tell(targets.length+" selected deployment targets",false);
      if(id)await inspect(id);
    }catch(err){if(n!==generation)return;targets=[];items.replaceChildren();
      details.replaceChildren();tell("Server deployment data unavailable: "+err.message,true);}
  }
  root.querySelector("#deployment-refresh").addEventListener("click",function(){reload();});
  add.addEventListener("click",function(){chooseForm(null);});
  items.addEventListener("click",function(e){
    var el=e.target.closest("[data-target]");if(el)inspect(el.dataset.target);
  });
  return {setAccess:function(read,write) {
    visible=Boolean(read);writable=Boolean(write);
    root.hidden=!visible;generation++;
    if(visible)reload();
    else {targets=[];profiles=[];candidates=[];selected=null;
      form.replaceChildren();details.replaceChildren();items.replaceChildren();tell("",false);}
  }};
}
window.AICompassServerDeployments={mount:mount};
})();
