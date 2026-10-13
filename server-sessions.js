/* PLAT-14: browser-independent Server-only session draft workspace. No browser-side persistence. */
(function(){
"use strict";
function mount(root,api,escapeHtml){
  var canRead=false,canWrite=false,active=null,ticket=0,availableEvidence=[],session=null,
    draftHandle=null,sessionStep=null;
  function $(q){return root.querySelector(q);}
  function esc(v){return escapeHtml(v==null?"":String(v));}
  function note(message,error){
    var el=$("#session-status");
    if(el){
      el.className=error?"server-status server-error":"server-status";
      el.innerHTML=window.AICompassWorkgroup.renderDomainStatus({
        mode:"server",state:error?"error":"ok",message:message==null?"":String(message)});
    }
  }
  function option(value,label,selected){
    return '<option value="'+esc(value)+'"'+(selected?' selected':'')+'>'+esc(label)+'</option>';
  }
  function selectEvidence(selected,name){
    var ids=Array.isArray(selected)?selected:[];
    return '<select multiple size="3" '+(name?'name="'+esc(name)+'" ':'')+
      'data-evidence style="width:100%">'+
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
  function failure(error){
    return window.AICompassRuntime&&window.AICompassRuntime.failureInfo?
      window.AICompassRuntime.failureInfo(error):{conflict:false,detail:error&&error.message};
  }
  /* The Run workflow is intrinsically sequential: Setup, the frozen method
   * steps, Interactions, then Results. Navigating between them is purely local
   * and never writes a checkpoint: only an explicit Save button commits. */
  function stepKeys(s){
    var keys=["setup"];
    (s.method_descriptor.steps||[]).forEach(function(step){keys.push("step:"+step.key);});
    keys.push("interactions");
    if(s.individual_setup||(s.selected_participant_ids||[]).length>=2)keys.push("results");
    return keys;
  }
  function stepLabel(key,s){
    if(key==="setup")return "Setup";
    if(key==="interactions")return "Interactions";
    if(key==="results")return "Results";
    var found=(s.method_descriptor.steps||[]).filter(function(step){
      return "step:"+step.key===key;})[0];
    return found?(found.label||found.key):key;
  }
  function stepNav(s,keys,current){
    // One stepper presentation shared with the offline Demo and the campaign
    // lifecycle (UX-R04), rendered interactive for the Server Run (UX-R05).
    // Each step is a local navigation control: moving never writes a checkpoint.
    return '<p id="session-step-cue" class="muted small" role="status"></p>'+
      window.AICompassWorkgroup.renderStepper(keys.map(function(key,index){
        return {label:String(index+1)+". "+stepLabel(key,s),
          state:key===current?"current":"todo",
          action:{label:String(index+1)+". "+stepLabel(key,s),
            attributes:{"data-session-goto":key}}};
      }),{mode:"server",domain:"session",interactive:true,id:"session-stepper"});
  }
  function renderTimeline(){
    var state=session.state,node=$("#session-timeline");
    if(node)node.innerHTML=state.interactions.map(function(x){
      return '<details><summary>#'+(x.order+1)+' · '+esc(x.type)+' · '+esc(x.occurred_at)+
        ' · human '+esc(x.human_minutes===null?"unknown":x.human_minutes)+
        ' / agent '+esc(x.agent_minutes===null?"unknown":x.agent_minutes)+' min</summary>'+
        '<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+esc(x.content)+'</pre>'+
        '<p>'+esc(x.notes)+' · '+(x.evidence_link_ids||[]).length+' evidence attachment(s)</p>'+
        '</details>';
    }).join("");
    var title=$("#session-timeline-title");
    if(title)title.textContent="Recorded interactions · "+state.interactions.length;
    var totals=$("#session-measurements");
    if(totals)totals.textContent="Summed human time: "+
      (state.measurements.human_total_minutes===null?"unknown":
        state.measurements.human_total_minutes+" minutes")+
      " · summed agent time: "+(state.measurements.agent_total_minutes===null?"unknown":
        state.measurements.agent_total_minutes+" minutes");
  }
  /* Acknowledged save: update only the parts of the screen the Server confirmed,
   * so unsaved input in other steps survives and no extra write is triggered. */
  async function refreshAfterSave(name){
    var revision=$("#session-revision");
    if(revision)revision.textContent=session.revision;
    if(name==="Interaction"){
      renderTimeline();
      var panel=$("#session-interaction");
      if(panel)["content","occurred_at","human_minutes","agent_minutes","interaction_notes",
        "interaction_extensions"].forEach(function(field){
          var node=panel.querySelector('[name="'+field+'"]');
          if(node)node.value=field==="interaction_extensions"?"{}":"";
        });
    }
    var status2=$("#session-step-status");
    if(status2)status2.textContent="Last acknowledged Server checkpoint "+
      session.revision+(name?" (from "+name+")":"")+
      ". Nothing else has been written; unsaved entries remain on this device only.";
  }
  async function submit(path,method,payload,name){
    note("Saving "+name+" to Server…");
    try{
      payload.expected_revision=session.revision;
      var result=await api(path,method,payload);
      session=result;
      /* Keep the entered DOM values and move the local draft to the new base
       * revision: nothing else is written and no second Run can be created. */
      if(draftHandle&&draftHandle.rebase)draftHandle.rebase(session.revision);
      await refreshAfterSave(name);
      latestStatus(name,result.revision);
    }catch(error){
      var info=failure(error);
      if(draftHandle&&info.conflict){
        draftHandle.conflict({label:"Test Case session "+session.id,
          baseRevision:session.revision,latestRevision:info.latestRevision||"unknown",
          message:info.detail});
      }
      note(name+" NOT saved"+(info.conflict?" (409 revision conflict)":
        info.denied?" (one experimenter owns one Run; not authorized)":"")+": "+
        (info.detail||error.message)+
        ". Review your entries or reload the Server revision.",true);
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
      if(draftHandle&&draftHandle.dispose)draftHandle.dispose();
      draftHandle=null;
      ticket++;active=null;session=null;root.hidden=true;root.replaceChildren();
    });
  }
  async function openCampaign(row,preferredEvaluationId){
    if(!canRead)return;
    active=row;session=null;var current=++ticket;
    panel();
    note("Loading real Server session drafts…");
    try{
      var results=await Promise.all([
        api("campaigns/"+encodeURIComponent(row.id)+"/sessions"),
        api("runs?campaign_id="+encodeURIComponent(row.id)),
        ...(row.mode==="task_centred"&&!row.framework_id?
          ["model","provider","harness"].map(function(k){return api("catalog/"+k);}):[]),
        ...(row.mode==="task_centred"&&!row.framework_id&&
            row.pricing_policy==="offer_revisions_v1"?[api("pricing/offers")]:[]),
        api("guides"),
        api("campaigns/"+encodeURIComponent(row.id)+"/matrix")
      ]);
      if(current!==ticket||!canRead)return;
      var result=results[0],runs=results[1].results||[],catalogResults=results.slice(2),
          knownGuides=results[results.length-2].results||[],
          matrix=results[results.length-1],
          planned=(matrix.cells||[]).filter(function(x){return x.decision==="selected";}),
          matrixConfigs=Object.fromEntries((matrix.configurations||[]).map(function(x){return [x.id,x];}));
      var offered=(row.mode==="task_centred"&&!row.framework_id&&
        row.pricing_policy==="offer_revisions_v1")?(catalogResults[3].results||[]):[];
      var offersByComponent=function(component){
        return offered.filter(function(o){return o.properties.component_id===component;});
      };
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
          (matrix.configured?'<label>Planned evaluation<select id="session-new-evaluation">'+
            option("","Select a selected evaluation",true)+
            planned.map(function(x){var cfg=matrixConfigs[x.configuration_id];return option(x.id,
              x.test_case_id+" × "+(cfg&&cfg.label||x.configuration_id)+" · "+x.status,false);}).join("")+
            '</select></label>':'')+
          '<label>Setup Guide<select id="session-new-guide">'+
          option("","No guide",!row.guide_id)+
          knownGuides.map(function(g){return option(g.id,g.name+" · "+g.revision,g.id===row.guide_id);}).join("")+
          '</select></label>'+
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
            (row.pricing_policy==="offer_revisions_v1"?
              '<section id="session-tariff-picker" class="server-card">'+
              '<h4>Required tariffs · choose exact current offer revisions</h4>'+
              '<p class="muted small">Task-centred setups are selected at session creation, so prices are pinned here rather than guessed in the parent Campaign. No offer is selected by default.</p>'+
              '<div id="session-tariff-rows"></div></section>':"")+
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
      function renderSessionPrices(){
        var holder=$("#session-tariff-rows");if(!holder)return;
        holder.innerHTML=["model","provider","harness"].map(function(kind){
          var control=target.querySelector('[data-new-component="'+kind+'"]'),
              component=control&&control.value||"";
          var alternatives=offersByComponent(component);
          return '<label>'+esc(kind)+' · '+esc(component)+
            '<select data-session-offer="'+kind+'" data-component-id="'+esc(component)+'">'+
            '<option value="">— Select offer revision —</option>'+
            alternatives.map(function(o){
              return '<option value="'+esc(o.id+"|"+o.revision_id)+'">'+
                esc(o.name+" · "+o.revision+" · "+o.properties.currency+
                    (o.readiness.complete?"":" · INCOMPLETE"))+'</option>';
            }).join("")+'</select></label>';
        }).join("");
      }
      if($("#session-tariff-rows")){
        target.querySelectorAll("[data-new-component]").forEach(function(el){
          el.addEventListener("change",renderSessionPrices);
        });
        renderSessionPrices();
      }
      var evaluationPicker=$("#session-new-evaluation");
      if(evaluationPicker)evaluationPicker.addEventListener("change",function(){
        var cell=planned.find(function(x){return x.id===evaluationPicker.value;});
        if(!cell)return;
        var cfg=matrixConfigs[cell.configuration_id];
        $("#session-new-case").value=cell.test_case_id;
        if(cfg.kind==="framework"){
          var participants=$("#session-new-participants");
          if(participants)Array.from(participants.options).forEach(function(option){
            option.selected=(cfg.participant_ids||[]).includes(option.value);
          });
        }else{
          ["model","provider","harness"].forEach(function(kind){
            var control=target.querySelector('[data-new-component="'+kind+'"]');
            if(control)control.value=cfg.component_ids[kind];
          });
          var version=$("#session-new-configuration-version");
          if(version)version.value=cfg.configuration_version;
          var settings=$("#session-new-settings");
          if(settings)settings.value=JSON.stringify(cfg.settings||{},null,2);
          renderSessionPrices();
        }
      });
      if(evaluationPicker&&preferredEvaluationId&&planned.some(function(c){return c.id===preferredEvaluationId;})){
        evaluationPicker.value=preferredEvaluationId;
        evaluationPicker.dispatchEvent(new Event("change"));
      }
      var add=$("#session-create");
      if(add)add.addEventListener("click",async function(){
        add.disabled=true;
        try{
          var payload={test_case_id:$("#session-new-case").value,
                      guide_id:$("#session-new-guide").value||null};
          if(matrix.configured){
            if(!evaluationPicker||!evaluationPicker.value)
              throw Error("Select a planned evaluation");
            payload.evaluation_id=evaluationPicker.value;
          }
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
            if(row.pricing_policy==="offer_revisions_v1"){
              payload.pricing_selections=Array.from(
                target.querySelectorAll("[data-session-offer]")).map(function(select){
                if(!select.value)throw Error("Select a complete tariff for "+select.dataset.sessionOffer);
                var sep=select.value.indexOf("|");
                return {source_key:"root:"+select.dataset.sessionOffer,
                  component_id:select.dataset.componentId,
                  offer_id:select.value.slice(0,sep),
                  offer_revision_id:select.value.slice(sep+1)};
              });
            }
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
        editable=canWrite&&state.status==="in_progress",
        priced=!!s.metering,
        draft=state.results_draft||{},
        savedUsage=state.metering||{};
    target.hidden=false;
    var stepList=stepKeys(s),
        activeStep=(sessionStep&&stepList.indexOf(sessionStep)>=0)?sessionStep:stepList[0];
    target.innerHTML='<h4>Session '+esc(s.id)+' · Server revision <span id="session-revision">'+
      esc(s.revision)+'</span></h4>'+
      '<p class="muted small">Frozen campaign '+esc(s.campaign_id)+' '+esc(s.campaign_revision)+
      ' · Test Case '+esc(s.test_case_id)+' · method v'+esc(s.method_version)+
      ' · '+esc(s.created_by)+' · '+esc(state.status||"in_progress")+'</p>'+
      (canWrite&&state.status!=="closed"?'<button type="button" id="session-lifecycle">'+
        (state.status==="paused"?"Resume session":"Pause session")+'</button>':'')+
      '<details><summary>Original method descriptor & evidence provenance</summary>'+
      '<pre id="session-method-json" style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>'+
      '<p>'+s.evidence.length+' pinned evidence link(s), unchanged SHA-256 hashes.</p></details>'+
      stepNav(s,stepList,activeStep)+
      '<p id="session-step-status" class="muted small"></p>'+
      '<form id="session-form" novalidate>'+
      '<div data-session-panel="setup">'+
      '<fieldset id="session-setup"><legend>1. Installation and environment · explicit save</legend>'+
      '<p class="muted small">Guide previews use the frozen configuration and the last saved environment. Save changes before inspecting.</p>'+
      '<button type="button" id="session-show-guide">Show original pinned Setup Guide</button>'+
      '<div id="session-rendered-guide" role="status"></div>'+
      '<label>Installation started at<input type="datetime-local" name="started_at" value="'+
        esc(timeValue(state.setup.started_at))+'"></label>'+
      '<label>Human installation duration (minutes; blank = unknown)<input type="number" step="any" min="0" name="installation_duration_minutes" value="'+
        esc(state.setup.installation_duration_minutes) +'"></label>'+
      '<label>Environment / deployed options (JSON object)<textarea name="environment">'+
        esc(JSON.stringify(state.setup.environment,null,2))+'</textarea></label>'+
      '<label>Installation notes<textarea name="setup_notes">'+esc(state.setup.notes)+'</textarea></label>'+
      '<label>Additional setup properties (JSON object)<textarea name="setup_extensions">'+
        esc(JSON.stringify(state.setup.extensions,null,2))+'</textarea></label>'+
      '<label>Supporting evidence'+selectEvidence(state.setup.evidence_link_ids,"setup_evidence")+'</label>'+
      (editable?'<button type="button" id="session-save-setup">Save installation checkpoint</button>':'')+
      '</fieldset></div>'+
      '<h4 data-session-step-only>2. Method-guided progress · saved one step at a time</h4>'+
      '<p class="muted small" data-session-step-only>Steps and fields come from the original frozen method definition, not the current campaign schema.</p>'+
      '<div id="session-steps">'+steps.map(function(step){
        var values=state.steps[step.key]||{},fields=(s.method_descriptor.fields||[]).filter(function(f){
          return !f.step||f.step===step.key;
        });
        return '<div data-session-panel="step:'+esc(step.key)+'">'+
          '<fieldset data-session-step="'+esc(step.key)+'" style="padding:12px;margin:12px 0;border:1px solid #d6dfed">'+
          '<legend>'+esc(step.label||step.key)+' · '+esc(step.key)+'</legend>'+
          '<label>Status<select name="step:'+esc(step.key)+':status" data-step-status>'+
             ["pending","in_progress","done"].map(function(x){
               return option(x,x,values.status===x);}).join("")+'</select></label>'+
          // Same shared field presentation as every other domain; the fields
          // themselves still come from the frozen method definition.
          window.AICompassWorkgroup.renderDomainFields(
            fields.map(function(f){
              return {key:f.key,label:f.label||f.key,
                kind:f.type==="boolean"?"checkbox":f.type==="number"?"number":"textarea",
                rows:3,min:f.type==="number"?null:undefined};}),
            fields.reduce(function(accumulator,f){
              accumulator[f.key]=(values.values||{})[f.key];return accumulator;},{}),
            "server",{idPrefix:"session-step-"+step.key})+
          '<label>Step notes<textarea name="step:'+esc(step.key)+':notes" data-step-notes>'+esc(values.notes||"")+'</textarea></label>'+
          '<label>Human step duration, minutes (blank = unknown)<input type="number" min="0" step="any" name="step:'+esc(step.key)+
            ':duration_minutes" data-step-duration value="'+
           esc(values.duration_minutes) +'"></label>'+
          '<label>Extensible step metadata (JSON object)<textarea name="step:'+esc(step.key)+':extensions" data-step-extensions>'+
           esc(JSON.stringify(values.extensions||{},null,2))+'</textarea></label>'+
          '<label>Evidence'+selectEvidence(values.evidence_link_ids,
            "step:"+step.key+":evidence")+'</label>'+
          (editable?'<button type="button" data-save-step="'+esc(step.key)+'">Save this step</button>':'')+
          '</fieldset></div>';
      }).join("")+'</div>'+
      '<div data-session-panel="interactions">'+
      '<fieldset id="session-interaction"><legend>3. Timed interaction · append immediately</legend>'+
      '<label>Type<select name="type">'+["human_prompt","agent_response","tool_action","review","note","other"].map(function(x){
        return option(x,x,false);}).join("")+'</select></label>'+
      '<label>Prompt / response / action<textarea name="content" placeholder="First prompt, follow-up, observed result…" required></textarea></label>'+
      '<label>Occurred at (blank = server timestamp)<input type="datetime-local" name="occurred_at"></label>'+
      '<label>Human minutes (blank = unknown)<input type="number" min="0" step="any" name="human_minutes"></label>'+
      '<label>Agent minutes (blank = unknown)<input type="number" min="0" step="any" name="agent_minutes"></label>'+
      '<label>Notes<textarea name="interaction_notes"></textarea></label>'+
      '<label>Unknown or future interaction metadata (JSON object)<textarea name="interaction_extensions">{}</textarea></label>'+
      (s.selected_participant_ids.length?'<label>Responsible participant<select name="participant_id">'+
        option("","Coordinator / unspecified",true)+s.selected_participant_ids.map(function(id){
          return option(id,id,false);}).join("")+'</select></label>':'')+
      '<label>Interim artefact links'+selectEvidence([],"interaction_evidence")+'</label>'+
      (editable?'<button type="button" id="session-add-interaction">Append interaction & save now</button>':'')+
      '</fieldset>'+
      '<h4 id="session-timeline-title">Recorded interactions · '+state.interactions.length+'</h4>'+
      '<p class="muted small" id="session-measurements">Summed human time: '+(state.measurements.human_total_minutes===null?
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
      '</div>'+
      '<div data-session-panel="results">'+
      (priced?'<fieldset id="session-metering"><legend>4. Offer-driven usage · independently saved</legend>'+
        '<p class="muted small">Counters come from exact selected offer revisions. Blank means unknown, explicit 0 means measured zero. Shared pooled credits and fixed seats are never amortized.</p>'+
        (s.metering.schema.required_meters||[]).map(function(item){
          var previous=(savedUsage[item.source_key]||{})[item.meter];
          return '<label>'+esc(item.source_key)+' · '+esc(item.meter)+
            (item.namespace?' · '+esc(item.namespace):'')+
            '<input type="number" name="meter:'+esc(item.source_key)+':'+esc(item.meter)+
            '" data-meter-source="'+esc(item.source_key)+
            '" data-meter-name="'+esc(item.meter)+'" step="any" min="0" value="'+
            esc(previous==null?"":previous)+'"></label>';
        }).join("")+
        '<p>Fixed commitments: '+esc(JSON.stringify(s.metering.schema.fixed_commitments||[]))+'</p>'+
        '<p>Metering status: <strong>'+esc(s.metering.ready?"complete":"pending")+'</strong>'+
        (s.metering.missing||[]).map(function(m){return '<span> · '+esc(m)+'</span>';}).join("")+'</p>'+
        (s.metering.quote?'<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+
          esc(JSON.stringify(s.metering.quote.variable_reference_by_currency,null,2))+
          '</pre>':'')+
        (editable?'<button type="button" id="session-save-metering">Save observed meters</button>':'')+
        '</fieldset>':'')+
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
         option("","Choose observed DoD outcome",!draft.outcome)+
         option("accepted","Accepted",draft.outcome==="accepted")+
         option("failed","Failed",draft.outcome==="failed")+'</select></label>'+
        '<label>Quality (0–100; blank = unmeasured)<input type="number" min="0" max="100" step="any" name="quality_score" value="'+esc(draft.quality_score==null?"":draft.quality_score)+'"></label>'+
        '<label>Quality rationale<textarea name="quality_evaluation">'+esc(draft.quality_evaluation||"")+'</textarea></label>'+
        '<label>Information utility (0–100; blank = unmeasured)<input type="number" min="0" max="100" step="any" name="information_utility_score" value="'+esc(draft.information_utility_score==null?"":draft.information_utility_score)+'"></label>'+
        '<label>Information utility rationale<textarea name="information_utility_evaluation">'+esc(draft.information_utility_evaluation||"")+'</textarea></label>'+
        '<label>Known tokens (blank = unknown)<input type="number" min="0" step="1" name="tokens_count" value="'+esc(draft.tokens_count==null?"":draft.tokens_count)+'"></label>'+
        '<label>Token multiplier<select name="tokens_multiplier">'+
         [1,10,100,1000,1000000].map(function(n){return option(n,n+"×",n===1);}).join("")+'</select></label>'+
        (priced?'':'<label>Run cost classification<select name="cost_mode">'+
         option("unknown","Unknown",draft.cost_mode==="unknown"||!draft.cost_mode)+
         option("flat_rate","Flat-rate / subscription",draft.cost_mode==="flat_rate")+
         option("amount","Run-specific EUR amount",draft.cost_mode==="amount")+'</select></label>'+
        '<label>Run-specific EUR amount (only with Amount)<input type="number" name="cost_eur" min="0" step="any" value="'+
         esc(draft.cost_eur==null?"":draft.cost_eur)+'"></label>')+
        '<label>Final human review minutes (blank = unknown)<input type="number" name="human_review_minutes" min="0" step="any"></label>'+
        '<label>Final human correction minutes (blank = unknown)<input type="number" name="human_correction_minutes" min="0" step="any"></label>'+
        '<label>Produced code, reports, paths and artifacts (required)<textarea name="produced_outputs" required>'+esc(draft.produced_outputs||"")+'</textarea></label>'+
        '<label>Additional notes<textarea name="run_notes"></textarea></label>'+
        '<label>Extensible measured evidence (JSON object)<textarea name="run_extensions">{}</textarea></label>'+
        '<label>Additional immutable evidence links'+selectEvidence([],"run_evidence")+'</label>'+
        '<button type="button" id="session-save-results">Save pending results / DoD</button> '+
        '<button type="button" id="session-close-run">Close as permanent Run</button></fieldset>':
        !s.individual_setup?'<p class="muted small">This legacy draft lacks a pinned AI setup and cannot be closed. Start a new session with explicit components.</p>':'')+
      '</div></form>';
    /* Stepper: pure local navigation. It never writes a checkpoint, so a step
     * move cannot create a phantom Run or duplicate any session artifact. */
    function showStep(key,options){
      if(stepList.indexOf(key)===-1)key=stepList[0];
      sessionStep=key;
      var panels=target.querySelectorAll("[data-session-panel]"),
          buttons=target.querySelectorAll("[data-session-goto]"),panel=null;
      Array.prototype.forEach.call(panels,function(node){
        var mine=node.getAttribute("data-session-panel")===key;
        node.hidden=!mine;
        if(mine)panel=node;
      });
      Array.prototype.forEach.call(target.querySelectorAll("[data-session-step-only]"),function(node){
        node.hidden=key.indexOf("step:")!==0;
      });
      Array.prototype.forEach.call(buttons,function(button){
        var mine=button.getAttribute("data-session-goto")===key;
        if(mine)button.setAttribute("aria-current","step");
        else button.removeAttribute("aria-current");
      });
      var cue=$("#session-step-cue");
      if(cue)cue.textContent=stepLabel(key,s)+" · step "+(stepList.indexOf(key)+1)+
        " of "+stepList.length+". Moving between steps writes nothing; only an explicit "+
        "Save button appends a Server checkpoint.";
      if(draftHandle)draftHandle.setStep(key);
      if(!options||options.focus!==false){
        var first=panel&&panel.querySelector("input:not([type=hidden]),select,textarea,button");
        if(first&&first.focus){try{first.focus();}catch(_){/* focus is best effort */}
        }
      }
      return key;
    }
    Array.prototype.forEach.call(target.querySelectorAll("[data-session-goto]"),function(button){
      button.addEventListener("click",function(){showStep(button.getAttribute("data-session-goto"));});
    });
    /* Unsaved inputs and the active step stay on this device only, keyed by mode,
     * account, session and base revision; the Server checkpoint stays authoritative. */
    if(draftHandle&&draftHandle.dispose)draftHandle.dispose();
    draftHandle=null;
    var form=$("#session-form"),
        drafts=window.AICompassDrafts,
        scope=drafts&&drafts.forMode&&form?drafts.forMode("server","session",{
          id:s.id,revision:s.revision,schema:"session-form-v1",
          label:"Test Case session "+s.id,step:activeStep,steps:stepList,
          maxFields:120,maxLength:6000,guardUnload:true,
          onStep:function(key){showStep(key,{focus:false});}}):null;
    if(scope)draftHandle=drafts.attach(form,scope);
    if(form)form.addEventListener("submit",function(event){event.preventDefault();});
    showStep(activeStep,{focus:false});
    $("#session-method-json").textContent=JSON.stringify(s.method_descriptor,null,2);
    $("#session-show-guide").addEventListener("click",async function(){
      var display=$("#session-rendered-guide"),button=this;button.disabled=true;
      display.textContent="Resolving immutable guide…";
      try{
        var result=await api("sessions/"+encodeURIComponent(s.id)+"/guide");
        var html='<p>'+(result.ready?"Declared setup coverage complete":
          "Coverage incomplete or not validated")+'</p>'+
          '<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+
          esc(JSON.stringify(result.missing,null,2))+'</pre>';
        (result.sections||[]).forEach(function(section){
          html+='<details open><summary>'+esc(section.name)+' · '+esc(section.revision)+'</summary>'+
            '<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+esc(section.text||"")+'</pre>'+
            '<p>'+esc(section.url||"")+'</p></details>';
        });
        html+='<h5>Original configuration</h5><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+
          esc(JSON.stringify(result.configuration,null,2))+'</pre>';
        html+='<h5>Recorded deviations</h5><pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+
          esc(JSON.stringify(result.deviations,null,2))+'</pre>';
        display.innerHTML=html;
      }catch(error){display.textContent="Pinned guide unavailable: "+error.message;}
      finally{button.disabled=false;}
    });
    if(canWrite&&state.status!=="closed"){
      $("#session-lifecycle").addEventListener("click",function(){
        var action=state.status==="paused"?"resume":"pause";
        submit("sessions/"+encodeURIComponent(s.id)+"/actions/"+action,
          "POST",{},"Session "+action);
      });
    }
    function resultPayload(requireOutputs){
      var f=$("#session-results");
      var tokens=f.querySelector('[name="tokens_count"]').value;
      var payload={
        outcome:f.querySelector('[name="outcome"]').value,
        quality_score:optionalMinutes(f.querySelector('[name="quality_score"]').value),
        quality_evaluation:f.querySelector('[name="quality_evaluation"]').value,
        information_utility_score:optionalMinutes(f.querySelector('[name="information_utility_score"]').value),
        information_utility_evaluation:f.querySelector('[name="information_utility_evaluation"]').value,
        tokens_count:tokens===""?null:Number(tokens),
        tokens_multiplier:tokens===""?1:Number(f.querySelector('[name="tokens_multiplier"]').value),
        human_review_minutes:optionalMinutes(f.querySelector('[name="human_review_minutes"]').value),
        human_correction_minutes:optionalMinutes(f.querySelector('[name="human_correction_minutes"]').value),
        produced_outputs:f.querySelector('[name="produced_outputs"]').value,
        notes:f.querySelector('[name="run_notes"]').value,
        extensions:json(f.querySelector('[name="run_extensions"]').value,"Run extensions"),
        evidence_link_ids:selected(f.querySelector("[data-evidence]"))
      };
      if(!priced){
        payload.cost_mode=f.querySelector('[name="cost_mode"]').value;
        payload.cost_eur=payload.cost_mode==="amount"?
          optionalMinutes(f.querySelector('[name="cost_eur"]').value):null;
        if(payload.cost_mode==="amount"&&f.querySelector('[name="cost_eur"]').value==="")
          throw Error("Amount cost requires an EUR value");
      }
      if(tokens!==""&&!Number.isSafeInteger(payload.tokens_count))
        throw Error("Total token count must be an integer");
      if(requireOutputs&&!payload.produced_outputs.trim())
        throw Error("Produced outputs are required to finalize");
      if(requireOutputs&&!payload.outcome)
        throw Error("Choose the observed Definition of Done outcome");
      return payload;
    }
    if(editable&&priced){
      $("#session-save-metering").addEventListener("click",function(){
        var observations={},nodes=$("#session-metering").querySelectorAll("[data-meter-source]");
        nodes.forEach(function(input){
          var source=input.dataset.meterSource;
          if(!observations[source])observations[source]={};
          observations[source][input.dataset.meterName]=input.value===""?null:input.value;
        });
        submit("sessions/"+encodeURIComponent(s.id)+"/metering","PATCH",{
          consumption:observations},"Observed metering");
      });
    }
    if(editable&&(s.individual_setup||isComposite)){
      $("#session-save-results").addEventListener("click",function(){
        try{submit("sessions/"+encodeURIComponent(s.id)+"/results","PATCH",
                   resultPayload(false),"Pending experimental results");}
        catch(error){note("Results draft not saved: "+error.message,true);}
      });
      $("#session-close-run").addEventListener("click",async function(){
        var f=$("#session-results"),button=$("#session-close-run");
        button.disabled=true;
        try{
          var payload=resultPayload(true);
          if(priced){
            // Persist outcome and artifacts *before* attempting metering-gated
            // finalization. On 409, this is a resumable pending checkpoint.
            session=await api("sessions/"+encodeURIComponent(s.id)+"/results",
                              "PATCH",{expected_revision:session.revision,...payload});
          }
          payload.expected_revision=session.revision;
          note("Closing as an immutable run…");
          var run=await api("sessions/"+encodeURIComponent(s.id)+"/close","POST",payload);
          session=await api("sessions/"+encodeURIComponent(s.id));
          /* The Run is final: the ephemeral local draft is obsolete, and no
           * local cache is ever promoted into the measured evidence. */
          if(draftHandle&&draftHandle.clear)draftHandle.clear();
          draftHandle=null;
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
            notes:f.querySelector('[name="setup_notes"]').value,
            extensions:json(f.querySelector('[name="setup_extensions"]').value,"Setup extensions"),
            evidence_link_ids:selected(f.querySelector("[data-evidence]"))
          },"Installation");
        }catch(error){note("Installation NOT saved: "+error.message,true);}
      });
      target.querySelectorAll("[data-save-step]").forEach(function(button){
        button.addEventListener("click",function(){
          var f=button.closest("[data-session-step]"),values={};
          try{
            f.querySelectorAll("[data-shared-field] input, [data-shared-field] textarea, "+
              "[data-shared-field] select").forEach(function(field){
              if(field.type==="checkbox")values[field.name]=field.checked;
              else if(field.type==="number")values[field.name]=field.value===""?null:Number(field.value);
              else values[field.name]=field.value;
            });
            submit("sessions/"+encodeURIComponent(s.id)+"/steps/"+encodeURIComponent(button.dataset.saveStep),
              "PATCH",{status:f.querySelector("[data-step-status]").value,
                values:values,notes:f.querySelector("[data-step-notes]").value,
                duration_minutes:optionalMinutes(f.querySelector("[data-step-duration]").value),
                extensions:json(f.querySelector("[data-step-extensions]").value,"Step extensions"),
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
            notes:f.querySelector('[name="interaction_notes"]').value,
            extensions:json(f.querySelector('[name="interaction_extensions"]').value,"Interaction extensions"),
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
    if(draftHandle&&draftHandle.dispose)draftHandle.dispose();
    draftHandle=null;
    root.hidden=true;root.replaceChildren();
  }
  root.hidden=true;
  return {setAccess:setAccess,openCampaign:openCampaign};
}
window.AICompassServerSessions={mount:mount};
})();
