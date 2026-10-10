/* PLAT-14: browser-independent Server-only session draft workspace. No browser-side persistence. */
(function(){
"use strict";
function mount(root,api,escapeHtml){
  var canRead=false,canWrite=false,active=null,ticket=0,availableEvidence=[],session=null;
  function $(q){return root.querySelector(q);}
  function esc(v){return escapeHtml(v==null?"":String(v));}
  function note(message,error){
    var el=$("#session-status");
    if(el){el.textContent=message;el.className=error?"server-status server-error":"server-status";}
  }
  function option(value,label,selected){
    return '<option value="'+esc(value)+'"'+(selected?' selected':'')+'>'+esc(label)+'</option>';
  }
  function selectEvidence(selected){
    var ids=Array.isArray(selected)?selected:[];
    return '<select multiple size="3" data-evidence style="width:100%">'+
      availableEvidence.map(function(x){return option(x.id,x.filename+' · '+x.sha256.slice(0,12),
                                           ids.includes(x.id));}).join("")+
      '</select><small class="muted">Select pre-uploaded immutable campaign/Test Case evidence (Ctrl/Command). No binary upload in this step.</small>';
  }
  function selected(node){return Array.from(node.selectedOptions||[]).map(function(x){return x.value;});}
  function json(value,name){
    var result=JSON.parse(value||"{}");
    if(!result||Array.isArray(result)||typeof result!=="object")throw Error(name+" must be a JSON object");
    return result;
  }
  function optionalMinutes(value){
    if(value==="")return null;
    var number=Number(value);
    if(!Number.isFinite(number)||number<0||number>10080)throw Error("Duration must be between 0 and 10080 minutes");
    return number;
  }
  function selectedTime(value){return value?new Date(value).toISOString():null;}
  function timeValue(value){
    if(!value)return "";
    var date=new Date(value);
    // Display in the browser's local timezone; submit an explicit ISO timestamp.
    var offset=date.getTimezoneOffset()*60000;
    return new Date(date.getTime()-offset).toISOString().slice(0,16);
  }
  function latestStatus(name,revision){note(name+" saved in PostgreSQL · "+revision+" · confirmed");}
  async function submit(path,method,payload,name){
    note("Saving "+name+" to Server…");
    try{
      payload.expected_revision=session.revision;
      var result=await api(path,method,payload);
      session=result;
      await renderSession();
      latestStatus(name,result.revision);
    }catch(error){
      note(name+" NOT saved: "+error.message+". Review your entries or reload the Server revision.",true);
    }
  }
  function panel(){
    root.hidden=false;
    root.innerHTML='<h3>Resumable Test Case sessions · Server only</h3>'+
      '<p class="muted small">Actions save one immutable checkpoint immediately. Navigate away only after the server-confirmed revision appears. Nothing is saved to browser storage.</p>'+
      '<p id="session-status" role="status" class="server-status"></p>'+
      '<div id="session-collection"></div><div id="session-editor" class="server-card" hidden></div>'+
      '<button type="button" id="session-close">Close session workspace</button>';
    $("#session-close").addEventListener("click",function(){
      ticket++;active=null;session=null;root.hidden=true;root.replaceChildren();
    });
  }
  async function openCampaign(row){
    if(!canRead)return;
    active=row;session=null;var current=++ticket;
    panel();
    note("Loading real Server session drafts…");
    try{
      var results=await Promise.all([
        api("campaigns/"+encodeURIComponent(row.id)+"/sessions"),
        api("runs?campaign_id="+encodeURIComponent(row.id)),
        ...(row.mode==="task_centred"&&!row.framework_id?
          ["model","provider","harness"].map(function(k){return api("catalog/"+k);}):[])
      ]);
      if(current!==ticket||!canRead)return;
      var result=results[0],runs=results[1].results||[],catalogResults=results.slice(2);
      var target=$("#session-collection");
      target.innerHTML='<h4>'+esc(row.name)+' · '+esc(row.revision)+'</h4>'+
        (result.results.length?result.results.map(function(s){
          return '<p><strong>'+esc(s.id)+'</strong> · '+esc(s.test_case_id)+
            ' · '+esc(s.revision)+' · by '+esc(s.created_by)+
            ' <button type="button" data-open-session="'+esc(s.id)+'">Open / resume</button></p>';
        }).join(""):'<p>No Server drafts for this campaign.</p>')+
        '<h4>Immutable measured runs · '+runs.length+'</h4>'+
        (runs.length?runs.map(function(r){return '<p>'+esc(r.id)+' · '+esc(r.outcome)+
           ' · '+(r.kind==="composite"?"Composite · Framework "+esc(r.framework_id)+
            " · "+(r.participants||[]).length+" participants":
            "Individual · Solution "+esc(r.solution_id))+' <button type="button" data-open-run="'+esc(r.id)+
           '">Read original run</button></p>';}).join(""):'<p>No completed runs yet.</p>')+
        '<pre id="session-run-detail" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>'+
        (canWrite&&row.status==="in_progress"&&!row.archived?
          '<fieldset><legend>Start a new Test Case execution</legend>'+
          '<label>Test Case<select id="session-new-case">'+(row.test_case_ids||[]).map(function(id){
            return option(id,id,false);}).join("")+'</select></label>'+
          '<label>Setup Guide<select id="session-new-guide">'+
          option("","No guide",!row.guide_id)+
          (row.guide_id?option(row.guide_id,row.guide_id,true):"")+'</select></label>'+
          (row.framework_id?
            '<label>Framework participants (one or more)<select id="session-new-participants" multiple size="4">'+
            (row.participants||[]).map(function(p){return option(p.id,p.label+" · "+p.role,true);}).join("")+
            '</select></label>':'')+
          (row.mode==="task_centred"&&!row.framework_id?
            '<p class="muted small">Define the exact solution setup before this controlled trial; all three components are version-pinned now.</p>'+
            ["model","provider","harness"].map(function(k,i){
              return '<label>'+esc(k)+'<select required data-new-component="'+k+'">'+
                (catalogResults[i]&&catalogResults[i].results||[]).map(function(x){
                   return option(x.id,x.name||x.id,false);}).join("")+'</select></label>';
            }).join("")+
            '<label>Configuration version<input id="session-new-configuration-version" value="1"></label>'+
            '<label>Model/runtime settings (JSON object)<textarea id="session-new-settings">{}</textarea></label>'+
            '<label>Tool access and capabilities (JSON object)<textarea id="session-new-properties">{}</textarea></label>':'')+
          '<button type="button" id="session-create">Start & save session</button></fieldset>':
          '<p class="muted small">Start the campaign to create sessions. Existing sessions remain inspectable.</p>');
      target.querySelectorAll("[data-open-session]").forEach(function(button){
        button.addEventListener("click",function(){openSession(button.dataset.openSession);});
      });
      target.querySelectorAll("[data-open-run]").forEach(function(button){
        button.addEventListener("click",async function(){
          try{
            var run=await api("runs/"+encodeURIComponent(button.dataset.openRun));
            $("#session-run-detail").textContent=JSON.stringify(run,null,2);
            note("Read-only original Run "+run.id+" · "+run.outcome+" · "+run.solution_id);
          }catch(error){note("Run detail unavailable: "+error.message,true);}
        });
      });
      var add=$("#session-create");
      if(add)add.addEventListener("click",async function(){
        add.disabled=true;
        try{
          var payload={test_case_id:$("#session-new-case").value,
                      guide_id:$("#session-new-guide").value||null};
          if(row.framework_id)payload.selected_participant_ids=selected($("#session-new-participants"));
          if(row.mode==="task_centred"&&!row.framework_id){
            payload.component_ids={};
            target.querySelectorAll("[data-new-component]").forEach(function(x){
              if(!x.value)throw Error("Each component of the individual solution is required");
              payload.component_ids[x.dataset.newComponent]=x.value;
            });
            payload.configuration_version=$("#session-new-configuration-version").value;
            payload.settings=json($("#session-new-settings").value,"Settings");
            payload.properties=json($("#session-new-properties").value,"Capabilities");
          }
          var created=await api("campaigns/"+encodeURIComponent(row.id)+"/sessions","POST",payload);
          await openCampaign(row);await openSession(created.id);
        }catch(error){note("Session not created: "+error.message,true);}
        finally{add.disabled=false;}
      });
      note(result.results.length+" persistent draft session(s) found.");
    }catch(error){if(current===ticket)note("Session list unavailable: "+error.message,true);}
  }
  async function openSession(id){
    if(!canRead||!active)return;
    var current=++ticket;
    note("Loading last server-confirmed checkpoint…");
    try{
      var result=await Promise.all([
        api("sessions/"+encodeURIComponent(id)),
        api("catalog/items/"+encodeURIComponent(active.id)+"/evidence")
      ]);
      if(current!==ticket)return;
      session=result[0];
      var caseLinks=await api("catalog/items/"+encodeURIComponent(session.test_case_id)+"/evidence");
      if(current!==ticket)return;
      availableEvidence=(result[1].results||[]).concat(caseLinks.results||[]).filter(function(x){
        return x.integrity==="ok";
      });
      await renderSession();
      note("Resumed "+session.id+" at Server checkpoint "+session.revision+".");
    }catch(error){if(current===ticket)note("Cannot resume session: "+error.message,true);}
  }
  async function renderSession(){
    var target=$("#session-editor");
    if(!target||!session)return;
    var s=session,steps=s.method_descriptor.steps||[],state=s.state,
        isComposite=s.selected_participant_ids.length>=2,
        editable=canWrite&&state.status==="in_progress";
    target.hidden=false;
    target.innerHTML='<h4>Session '+esc(s.id)+' · '+esc(s.revision)+'</h4>'+
      '<p class="muted small">Frozen campaign '+esc(s.campaign_id)+' '+esc(s.campaign_revision)+
      ' · Test Case '+esc(s.test_case_id)+' · method v'+esc(s.method_version)+
      ' · '+esc(s.created_by)+' · '+esc(state.status||"in_progress")+'</p>'+
      (canWrite&&state.status!=="closed"?'<button type="button" id="session-lifecycle">'+
        (state.status==="paused"?"Resume session":"Pause session")+'</button>':'')+
      '<details><summary>Original method descriptor & evidence provenance</summary>'+
      '<pre id="session-method-json" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>'+
      '<p>'+s.evidence.length+' pinned evidence link(s), unchanged SHA-256 hashes.</p></details>'+
      '<fieldset id="session-setup"><legend>1. Installation and environment · explicit save</legend>'+
      '<label>Installation started at<input type="datetime-local" name="started_at" value="'+
        esc(timeValue(state.setup.started_at))+'"></label>'+
      '<label>Human installation duration (minutes; blank = unknown)<input type="number" step="any" min="0" name="installation_duration_minutes" value="'+
        esc(state.setup.installation_duration_minutes) +'"></label>'+
      '<label>Environment / deployed options (JSON object)<textarea name="environment">'+
        esc(JSON.stringify(state.setup.environment,null,2))+'</textarea></label>'+
      '<label>Installation notes<textarea name="notes">'+esc(state.setup.notes)+'</textarea></label>'+
      '<label>Additional setup properties (JSON object)<textarea name="extensions">'+
        esc(JSON.stringify(state.setup.extensions,null,2))+'</textarea></label>'+
      '<label>Supporting evidence'+selectEvidence(state.setup.evidence_link_ids)+'</label>'+
      (editable?'<button type="button" id="session-save-setup">Save installation checkpoint</button>':'')+
      '</fieldset>'+
      '<h4>2. Method-guided progress · saved one step at a time</h4>'+
      '<p class="muted small">Steps and fields come from the original frozen method definition, not the current campaign schema.</p>'+
      '<div id="session-steps">'+steps.map(function(step){
        var values=state.steps[step.key]||{},fields=(s.method_descriptor.fields||[]).filter(function(f){
          return !f.step||f.step===step.key;
        });
        return '<fieldset data-session-step="'+esc(step.key)+'" style="padding:12px;margin:12px 0;border:1px solid #d6dfed">'+
          '<legend>'+esc(step.label||step.key)+' · '+esc(step.key)+'</legend>'+
          '<label>Status<select name="status">'+
             ["pending","in_progress","done"].map(function(x){
               return option(x,x,values.status===x);}).join("")+'</select></label>'+
          fields.map(function(f){
            var v=(values.values||{})[f.key],type=f.type||"text";
            var key=esc(f.key),label=esc(f.label||f.key);
            if(type==="boolean")return '<label>'+label+'<input type="checkbox" data-step-field="'+key+'" data-type="boolean"'+
              (v===true?' checked':'')+'></label>';
            if(type==="number")return '<label>'+label+'<input type="number" step="any" data-step-field="'+key+
              '" data-type="number" value="'+esc(v)+'"></label>';
            return '<label>'+label+'<textarea data-step-field="'+key+'" data-type="text">'+esc(v)+'</textarea></label>';
          }).join("")+
          '<label>Step notes<textarea name="notes">'+esc(values.notes||"")+'</textarea></label>'+
          '<label>Human step duration, minutes (blank = unknown)<input type="number" min="0" step="any" name="duration_minutes" value="'+
           esc(values.duration_minutes) +'"></label>'+
          '<label>Extensible step metadata (JSON object)<textarea name="extensions">'+
           esc(JSON.stringify(values.extensions||{},null,2))+'</textarea></label>'+
          '<label>Evidence'+selectEvidence(values.evidence_link_ids)+'</label>'+
          (editable?'<button type="button" data-save-step="'+esc(step.key)+'">Save this step</button>':'')+
          '</fieldset>';
      }).join("")+'</div>'+
      '<fieldset id="session-interaction"><legend>3. Timed interaction · append immediately</legend>'+
      '<label>Type<select name="type">'+["human_prompt","agent_response","tool_action","review","note","other"].map(function(x){
        return option(x,x,false);}).join("")+'</select></label>'+
      '<label>Prompt / response / action<textarea name="content" placeholder="First prompt, follow-up, observed result…" required></textarea></label>'+
      '<label>Occurred at (blank = server timestamp)<input type="datetime-local" name="occurred_at"></label>'+
      '<label>Human minutes (blank = unknown)<input type="number" min="0" step="any" name="human_minutes"></label>'+
      '<label>Agent minutes (blank = unknown)<input type="number" min="0" step="any" name="agent_minutes"></label>'+
      '<label>Notes<textarea name="notes"></textarea></label>'+
      '<label>Unknown or future interaction metadata (JSON object)<textarea name="extensions">{}</textarea></label>'+
      (s.selected_participant_ids.length?'<label>Responsible participant<select name="participant_id">'+
        option("","Coordinator / unspecified",true)+s.selected_participant_ids.map(function(id){
          return option(id,id,false);}).join("")+'</select></label>':'')+
      '<label>Interim artefact links'+selectEvidence([])+'</label>'+
      (editable?'<button type="button" id="session-add-interaction">Append interaction & save now</button>':'')+
      '</fieldset>'+
      '<h4>Recorded interactions · '+state.interactions.length+'</h4>'+
      '<p class="muted small">Summed human time: '+(state.measurements.human_total_minutes===null?
        "unknown":esc(state.measurements.human_total_minutes)+" minutes")+
      ' · summed agent time: '+(state.measurements.agent_total_minutes===null?
        "unknown":esc(state.measurements.agent_total_minutes)+" minutes")+'</p>'+
      '<div id="session-timeline">'+state.interactions.map(function(x){
        return '<details><summary>#'+(x.order+1)+' · '+esc(x.type)+' · '+esc(x.occurred_at)+
          ' · human '+esc(x.human_minutes===null?"unknown":x.human_minutes)+
          ' / agent '+esc(x.agent_minutes===null?"unknown":x.agent_minutes)+' min</summary>'+
          '<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+esc(x.content)+'</pre>'+
          '<p>'+esc(x.notes)+' · '+(x.evidence_link_ids||[]).length+' evidence attachment(s)</p>'+
          '</details>';
      }).join("")+'</div>'+
      '<button type="button" id="session-history">View immutable checkpoint history</button>'+
      '<div id="session-history-content"></div>'+
      (state.status==="closed"?
        '<p class="muted small">Closed as immutable run · metrics and evidence can no longer be edited.</p>':
        editable&&(s.individual_setup||isComposite)?
        '<fieldset id="session-results"><legend>4. Results / Close '+
        (isComposite?"Framework composite run":"individual run")+' permanently</legend>'+
        (isComposite?'<p class="muted small"><strong>Workflow-wide result only:</strong> '+
          esc(s.selected_participant_ids.length)+' version-pinned participant roles. Quality, cost, tokens and time will not be assigned to any individual AI Solution.</p>':'')+
        '<p class="muted small">DoD is mandatory. Unknown numeric values stay unknown, not zero. Run closure is irreversible.</p>'+
        '<label>Definition of Done outcome<select name="outcome">'+
         option("accepted","Accepted",false)+option("failed","Failed",false)+'</select></label>'+
        '<label>Quality (0–100; blank = unmeasured)<input type="number" min="0" max="100" step="any" name="quality_score"></label>'+
        '<label>Quality rationale<textarea name="quality_evaluation"></textarea></label>'+
        '<label>Information utility (0–100; blank = unmeasured)<input type="number" min="0" max="100" step="any" name="information_utility_score"></label>'+
        '<label>Information utility rationale<textarea name="information_utility_evaluation"></textarea></label>'+
        '<label>Known tokens (blank = unknown)<input type="number" min="0" step="1" name="tokens_count"></label>'+
        '<label>Token multiplier<select name="tokens_multiplier">'+
         [1,10,100,1000,1000000].map(function(n){return option(n,n+"×",n===1);}).join("")+'</select></label>'+
        '<label>Run cost classification<select name="cost_mode">'+
         option("unknown","Unknown",true)+option("flat_rate","Flat-rate / subscription",false)+
         option("amount","Run-specific EUR amount",false)+'</select></label>'+
        '<label>Run-specific EUR amount (only with Amount)<input type="number" name="cost_eur" min="0" step="any"></label>'+
        '<label>Final human review minutes (blank = unknown)<input type="number" name="human_review_minutes" min="0" step="any"></label>'+
        '<label>Final human correction minutes (blank = unknown)<input type="number" name="human_correction_minutes" min="0" step="any"></label>'+
        '<label>Produced code, reports, paths and artifacts (required)<textarea name="produced_outputs" required></textarea></label>'+
        '<label>Additional notes<textarea name="notes"></textarea></label>'+
        '<label>Extensible measured evidence (JSON object)<textarea name="extensions">{}</textarea></label>'+
        '<label>Additional immutable evidence links'+selectEvidence([])+'</label>'+
        '<button type="button" id="session-close-run">Close as permanent Run</button></fieldset>':
        !s.individual_setup?'<p class="muted small">This legacy draft lacks a pinned AI setup and cannot be closed. Start a new session with explicit components.</p>':'');
    $("#session-method-json").textContent=JSON.stringify(s.method_descriptor,null,2);
    if(canWrite&&state.status!=="closed"){
      $("#session-lifecycle").addEventListener("click",function(){
        var action=state.status==="paused"?"resume":"pause";
        submit("sessions/"+encodeURIComponent(s.id)+"/actions/"+action,
          "POST",{},"Session "+action);
      });
    }
    if(editable&&(s.individual_setup||isComposite)){
      $("#session-close-run").addEventListener("click",async function(){
        var f=$("#session-results"),button=$("#session-close-run");
        button.disabled=true;
        try{
          var cost_mode=f.querySelector('[name="cost_mode"]').value;
          var tokens=f.querySelector('[name="tokens_count"]').value;
          var payload={
            expected_revision:s.revision,
            outcome:f.querySelector('[name="outcome"]').value,
            quality_score:optionalMinutes(f.querySelector('[name="quality_score"]').value),
            quality_evaluation:f.querySelector('[name="quality_evaluation"]').value,
            information_utility_score:optionalMinutes(f.querySelector('[name="information_utility_score"]').value),
            information_utility_evaluation:f.querySelector('[name="information_utility_evaluation"]').value,
            tokens_count:tokens===""?null:Number(tokens),
            tokens_multiplier:tokens===""?1:Number(f.querySelector('[name="tokens_multiplier"]').value),
            cost_mode:cost_mode,
            cost_eur:cost_mode==="amount"?optionalMinutes(f.querySelector('[name="cost_eur"]').value):null,
            human_review_minutes:optionalMinutes(f.querySelector('[name="human_review_minutes"]').value),
            human_correction_minutes:optionalMinutes(f.querySelector('[name="human_correction_minutes"]').value),
            produced_outputs:f.querySelector('[name="produced_outputs"]').value,
            notes:f.querySelector('[name="notes"]').value,
            extensions:json(f.querySelector('[name="extensions"]').value,"Run extensions"),
            evidence_link_ids:selected(f.querySelector("[data-evidence]"))
          };
          if(tokens!==""&&!Number.isSafeInteger(payload.tokens_count))
            throw Error("Total token count must be an integer");
          if(cost_mode==="amount"&&f.querySelector('[name="cost_eur"]').value==="")
            throw Error("Amount cost requires an EUR value");
          if(!payload.produced_outputs.trim())throw Error("Produced outputs are required");
          note("Closing as an immutable run…");
          var run=await api("sessions/"+encodeURIComponent(s.id)+"/close","POST",payload);
          session=await api("sessions/"+encodeURIComponent(s.id));
          await renderSession();
          note("Permanent "+(run.kind==="composite"?"composite Framework":"individual")+
            " Run "+run.id+" saved · "+run.outcome+
            (run.kind==="composite"?" · global metrics only":" · measured solution "+run.solution_id));
          // The frozen run detail is independently retrievable by readers.
          var original=await api("runs/"+encodeURIComponent(run.id));
          var editor=$("#session-editor");
          var pre=editor.querySelector("#session-closed-run");
          if(!pre){pre=document.createElement("pre");pre.id="session-closed-run";editor.appendChild(pre);}
          pre.textContent=JSON.stringify(original,null,2);
        }catch(error){note("Run closure refused: "+error.message,true);button.disabled=false;}
      });
    }
    if(editable){
      $("#session-save-setup").addEventListener("click",function(){
        var f=$("#session-setup");
        try{
          submit("sessions/"+encodeURIComponent(s.id)+"/setup","PATCH",{
            started_at:selectedTime(f.querySelector('[name="started_at"]').value),
            installation_duration_minutes:optionalMinutes(f.querySelector('[name="installation_duration_minutes"]').value),
            environment:json(f.querySelector('[name="environment"]').value,"Environment"),
            notes:f.querySelector('[name="notes"]').value,
            extensions:json(f.querySelector('[name="extensions"]').value,"Setup extensions"),
            evidence_link_ids:selected(f.querySelector("[data-evidence]"))
          },"Installation");
        }catch(error){note("Installation NOT saved: "+error.message,true);}
      });
      target.querySelectorAll("[data-save-step]").forEach(function(button){
        button.addEventListener("click",function(){
          var f=button.closest("[data-session-step]"),values={};
          try{
            f.querySelectorAll("[data-step-field]").forEach(function(field){
              if(field.dataset.type==="boolean")values[field.dataset.stepField]=field.checked;
              else if(field.dataset.type==="number")values[field.dataset.stepField]=field.value===""?null:Number(field.value);
              else values[field.dataset.stepField]=field.value;
            });
            submit("sessions/"+encodeURIComponent(s.id)+"/steps/"+encodeURIComponent(button.dataset.saveStep),
              "PATCH",{status:f.querySelector('[name="status"]').value,
                values:values,notes:f.querySelector('[name="notes"]').value,
                duration_minutes:optionalMinutes(f.querySelector('[name="duration_minutes"]').value),
                extensions:json(f.querySelector('[name="extensions"]').value,"Step extensions"),
                evidence_link_ids:selected(f.querySelector("[data-evidence]")),
                schema_version:String(s.method_version)},"Step "+button.dataset.saveStep);
          }catch(error){note("Step NOT saved: "+error.message,true);}
        });
      });
      $("#session-add-interaction").addEventListener("click",function(){
        var f=$("#session-interaction");
        try{
          var data={type:f.querySelector('[name="type"]').value,
            content:f.querySelector('[name="content"]').value,
            human_minutes:optionalMinutes(f.querySelector('[name="human_minutes"]').value),
            agent_minutes:optionalMinutes(f.querySelector('[name="agent_minutes"]').value),
            notes:f.querySelector('[name="notes"]').value,
            extensions:json(f.querySelector('[name="extensions"]').value,"Interaction extensions"),
            evidence_link_ids:selected(f.querySelector("[data-evidence]")),
            schema_version:String(s.method_version)};
          if(f.querySelector('[name="occurred_at"]').value)
            data.occurred_at=selectedTime(f.querySelector('[name="occurred_at"]').value);
          var responsible=f.querySelector('[name="participant_id"]');
          if(responsible&&responsible.value)data.participant_id=responsible.value;
          if(!data.content.trim())throw Error("Enter the prompt, response or action before saving");
          submit("sessions/"+encodeURIComponent(s.id)+"/interactions","POST",data,"Interaction");
        }catch(error){note("Interaction NOT saved: "+error.message,true);}
      });
    }
    $("#session-history").addEventListener("click",async function(){
      var area=$("#session-history-content");
      area.textContent="Loading original checkpoints…";
      try{
        var result=await api("sessions/"+encodeURIComponent(s.id)+"/checkpoints");
        area.innerHTML=result.checkpoints.map(function(x){
          return '<details><summary>'+esc(x.revision)+' · '+esc(x.action)+' · '+esc(x.saved_at)+
           ' · '+esc(x.actor)+'</summary><pre data-checkpoint="'+esc(x.revision)+
           '" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';
        }).join("");
        area.querySelectorAll("details").forEach(function(details){
          details.addEventListener("toggle",async function(){
            if(!details.open)return;
            var pre=details.querySelector("pre");
            if(pre.textContent)return;
            var number=Number(pre.dataset.checkpoint.slice(1));
            try{
              var version=await api("sessions/"+encodeURIComponent(s.id)+"/checkpoints/"+number);
              pre.textContent=JSON.stringify(version,null,2);
            }catch(error){pre.textContent="Original checkpoint unavailable: "+error.message;}
          });
        });
      }catch(error){area.textContent="History unavailable: "+error.message;}
    });
  }
  function setAccess(read,write){
    ticket++;canRead=!!read;canWrite=!!write&&canRead;active=null;session=null;
    root.hidden=true;root.replaceChildren();
  }
  root.hidden=true;
  return {setAccess:setAccess,openCampaign:openCampaign};
}
window.AICompassServerSessions={mount:mount};
})();
