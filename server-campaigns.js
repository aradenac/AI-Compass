/* PLAT-12: persistent Server campaigns. No Demo storage or runtime fallback. */
(function () {
  "use strict";
  var MODE_LABELS={task_centred:"Compare solutions on one task",solution_centred:"Evaluate one solution across tasks"};
  var STATES=["planned","in_progress","under_review","published"];
  var NEXT={
    planned:[["start","Start campaign"]],
    in_progress:[["close","Close for review"]],
    under_review:[["rework","Request rework"],["publish","Publish plan"],["reopen","Reopen"]],
    published:[["unpublish","Unpublish"],["reopen","Reopen"]]
  };
  function mount(root, csrf, escapeHtml) {
    var allowed=false,canWrite=false,canReview=false,ticket=0,campaigns=[],methods=[],tasks=[],cases=[],guides=[];
    var catalog={model:[],provider:[],harness:[],framework:[]},offers=[],sessionWorkspace=null;
    function el(selector){return root.querySelector(selector);}
    function esc(value){return escapeHtml(value==null?"":String(value));}
    function status(message,error){
      var node=el("#campaign-status");
      if(node){node.textContent=message;node.className=error?"server-status server-error":"server-status";}
    }
    async function api(path,method,payload){
      var opts={method:method||"GET",credentials:"same-origin",cache:"no-store"};
      if(method&&method!=="GET"){
        opts.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
        opts.body=JSON.stringify(payload);
      }
      var response=await fetch("/api/v1/"+path,opts);
      var body=await response.json().catch(function(){return {};});
      if(!response.ok)throw Error(body.detail||body.error||"HTTP "+response.status);
      return body;
    }
    function build(){
      root.innerHTML='<div class="server-model-toolbar"><div><h2>Benchmark Workspace · Campaigns</h2>'+
        '<p class="muted small">Shared planning, immutable revisions and controlled lifecycle · PostgreSQL only</p></div>'+
        '<button type="button" id="campaign-refresh">Refresh</button></div>'+
        '<p id="campaign-status" class="server-status" role="status"></p>'+
        '<h3>Workgroup pipeline · read only</h3><div id="campaign-pipeline"></div>'+
        '<h3>Campaign management</h3>'+
        (canWrite?'<button type="button" id="campaign-add">+ Create campaign</button>':'')+
        '<div id="campaign-list" class="server-card"></div>'+
        '<section id="campaign-editor" class="server-card" hidden></section>'+
        '<section id="campaign-detail" class="server-card" hidden></section>'+
        '<section id="campaign-session-area" class="server-card" hidden></section>';
      sessionWorkspace=window.AICompassServerSessions.mount(el("#campaign-session-area"),api,esc);
      sessionWorkspace.setAccess(allowed,canWrite);
      el("#campaign-refresh").addEventListener("click",refresh);
      if(canWrite)el("#campaign-add").addEventListener("click",function(){editor(null);});
      el("#campaign-list").addEventListener("click",function(e){
        var btn=e.target.closest("button[data-id]");
        if(!btn)return;
        var row=campaigns.find(function(c){return c.id===btn.dataset.id;});
        if(!row)return;
        if(btn.dataset.action==="matrix")showMatrix(row);
        else if(btn.dataset.action==="sessions"&&sessionWorkspace)sessionWorkspace.openCampaign(row);
        else if(btn.dataset.action==="history")history(row);
        else if(canWrite&&btn.dataset.action==="edit")editor(row);
        else if(canWrite&&btn.dataset.action)transition(row,btn.dataset.action);
      });
    }
    function render(){
      var lane=el("#campaign-pipeline"),list=el("#campaign-list");
      var active=campaigns.filter(function(c){return !c.archived;});
      lane.innerHTML='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px">'+
        STATES.map(function(s){
          var rows=active.filter(function(x){return x.status===s;});
          return '<section class="server-card" style="padding:12px"><h4>'+esc(s.replaceAll("_"," "))+
            ' ('+rows.length+')</h4>'+ (rows.length?rows.map(function(x){
              return '<p><strong>'+esc(x.name)+'</strong><br>'+esc(x.owner)+' · '+esc(x.mode)+
                ' · '+x.test_case_ids.length+' Test Case(s)</p>';
            }).join(""):'<p class="muted small">No campaigns</p>')+'</section>';
        }).join("")+'</div>';
      list.innerHTML=campaigns.length?campaigns.map(function(x){
        var commands=x.archived?[["restore","Restore archive"]]:
          (NEXT[x.status]||[]).concat([["archive","Archive"]]);
        return '<div class="list-row" style="padding:14px 0;border-bottom:1px solid #e3e8f0">'+
          '<strong>'+esc(x.name)+'</strong><p class="muted small">'+esc(x.id)+' · '+esc(x.revision)+
          ' · '+esc(x.status)+(x.archived?' · archived':'')+' · owner '+esc(x.owner)+
          ' · '+x.test_case_ids.length+' Test Case(s)'+
          (x.framework_id?' · Framework '+esc(x.framework_id)+' · '+(x.participants||[]).length+' participant(s)':'')+'</p>'+
          '<p>'+esc(x.properties.objective)+'</p>'+
          '<p class="muted">Pricing · '+esc(x.pricing_readiness&&x.pricing_readiness.complete?
             "complete / exact offer pins":(x.pricing_readiness&&x.pricing_readiness.requires_session_pricing?
             "tariffs selected per Test Case session":"INCOMPLETE / new metered session blocked")) +'</p>'+
          '<button type="button" data-id="'+esc(x.id)+'" data-action="matrix">Evaluation matrix</button>'+
          '<button type="button" data-id="'+esc(x.id)+'" data-action="sessions">Sessions / resume</button>'+
          '<button type="button" data-id="'+esc(x.id)+'" data-action="history">Details / history</button>'+
          (canWrite&&!x.archived&&["planned","in_progress"].includes(x.status)?
            '<button type="button" data-id="'+esc(x.id)+'" data-action="edit">Edit</button>':'')+
          (commands.filter(function(k){
            return ["publish","unpublish"].includes(k[0])?canReview:canWrite;
          }).map(function(k){return '<button type="button" data-id="'+esc(x.id)+
            '" data-action="'+esc(k[0])+'">'+esc(k[1])+'</button>';}).join("") )+'</div>';
      }).join(""):'No real Server campaigns yet. Create tasks/Test Cases and, for solution-centred campaigns, catalog components first.';
    }
    async function refresh(){
      if(!allowed)return;
      var run=++ticket;
      status("Loading shared Server campaigns and reference catalogs…");
      try{
        var responses=await Promise.all([
          api("campaigns"),api("campaign-methods"),api("tasks"),api("test-cases"),
          api("guides"),api("catalog/model"),api("catalog/provider"),api("catalog/harness"),
          api("catalog/framework"),api("pricing/offers")
        ]);
        if(!allowed||run!==ticket)return;
        campaigns=responses[0].results; methods=responses[1].results;
        tasks=responses[2].results; cases=responses[3].results; guides=responses[4].results;
        ["model","provider","harness","framework"].forEach(function(k,i){catalog[k]=responses[i+5].results;});
        offers=responses[9].results;
        render();status(campaigns.length+" campaign(s) persisted in Server. Pipeline shows plans, not measured results.");
      }catch(error){
        if(!allowed||run!==ticket)return;
        campaigns=[];offers=[];el("#campaign-list").textContent="Campaigns unavailable; no Demo fallback.";
        el("#campaign-pipeline").replaceChildren();
        status("Server campaign request failed: "+error.message,true);
      }
    }
    function options(rows,selected,blank){
      var result=blank?'<option value="">— None —</option>':"";
      return result+rows.map(function(x){
        return '<option value="'+esc(x.id)+'"'+(x.id===selected?' selected':'')+'>'+
          esc(x.name)+' ('+esc(x.id)+')</option>';
      }).join("");
    }
    function editor(source){
      if(!allowed||!canWrite)return;
      var target=el("#campaign-editor"),mode=source?source.mode:"task_centred";
      target.hidden=false;el("#campaign-detail").hidden=true;
      var versions=methods.filter(function(x){return x.mode===mode;});
      target.innerHTML='<h3>'+(source?"Edit campaign · "+esc(source.revision):"Create campaign")+'</h3>'+
        '<form id="campaign-form">'+
        '<label>Title<input name="name" maxlength="160" required value="'+esc(source?source.name:"")+'"></label>'+
        '<label>Objective<textarea name="objective" maxlength="4000" required>'+esc(source?source.properties.objective:"")+'</textarea></label>'+
        '<label>Notes<textarea name="notes" maxlength="20000">'+esc(source?source.properties.notes||"":"")+'</textarea></label>'+
        '<label>Owner (Server username)<input name="owner" maxlength="150" value="'+esc(source?source.owner:"")+'" placeholder="Defaults to current user"></label>'+
        '<label>Comparison mode<select name="mode">'+Object.keys(MODE_LABELS).map(function(k){
          return '<option value="'+k+'"'+(mode===k?' selected':'')+'>'+esc(MODE_LABELS[k])+'</option>';
        }).join("")+'</select></label>'+
        '<label>Experimental method version<select name="method_version">'+versions.map(function(x){
          return '<option value="'+x.version+'"'+(source&&source.method_version===x.version?' selected':'')+
            '>Version '+x.version+'</option>';}).join("")+'</select></label>'+
        '<section id="campaign-method-details" class="muted small"></section>'+
        '<div id="campaign-task-row"><label>Fixed engineering task<select name="task_id">'+
          options(tasks,source?source.task_id:null,true)+'</select></label></div>'+
        '<label>Optional Framework<select name="framework_id">'+
          options(catalog.framework,source?source.framework_id:null,true)+'</select></label>'+
        '<section id="campaign-participants-row" class="server-card" hidden>'+
          '<h4>Framework participants · individually pinned trios</h4>'+
          '<p class="muted small">Each participant has a stable ID, role, own Model / Provider / Harness and versioned settings. No agents are executed here.</p>'+
          '<div id="campaign-participant-list"></div>'+
          '<button type="button" id="campaign-participant-add">+ Add participant</button>'+
        '</section>'+
        '<div id="campaign-solution-row">'+["model","provider","harness"].map(function(k){
          return '<label>Fixed '+esc(k)+'<select name="'+k+'">'+options(catalog[k],
            source?(source.component_ids||{})[k]:null,true)+'</select></label>';
        }).join("")+'</div>'+
        '<label>Reusable Setup Guide<select name="guide_id">'+options(guides,source?source.guide_id:null,true)+'</select></label>'+
        '<label>Recipe preview environment (JSON)<textarea name="preview_environment">{}</textarea></label>'+
        '<button type="button" id="campaign-preview-guide">Preview selected guide</button>'+
        '<pre id="campaign-guide-preview" class="muted small" style="white-space:pre-wrap"></pre>'+
        '<div><button type="button" id="campaign-inline-guide">+ Create reusable Setup Guide</button></div>'+
        '<div id="campaign-guide-form" hidden><label>Guide title<input name="guide_name" maxlength="160"></label>'+
        '<label>Setup procedure text<textarea name="guide_text"></textarea></label>'+
        '<label>HTTP(S) guide URL<input name="guide_url" maxlength="2048"></label>'+
        '<label>Reusable pinned modules (Ctrl/Command to select)<select name="guide_modules" multiple size="5">'+
        guides.map(function(g){return '<option value="'+esc(g.id)+'">'+esc(g.name)+' · '+esc(g.revision)+'</option>';}).join("")+
        '</select></label>'+
        '<label>Recipe JSON (optional: OS/runtime applicability, dependencies, variants)<textarea name="guide_recipe" rows="7"></textarea></label>'+
        '<button type="button" id="campaign-save-guide">Save Guide to knowledge base</button></div>'+
        '<section id="campaign-pricing" class="server-card"></section>'+ 
        '<label>Linked Test Cases (Ctrl/Command to select multiple)'+
        '<select name="test_case_ids" multiple size="6">'+cases.map(function(c){
          return '<option value="'+esc(c.id)+'"'+(source&&source.test_case_ids.includes(c.id)?" selected":"")+
            '>'+esc(c.name)+' ('+esc(c.task_id)+')</option>';
        }).join("")+'</select></label>'+
        '<label>Fixed configuration and parameters (JSON object)<textarea name="configuration">'+
          esc(JSON.stringify(source?source.configuration:{},null,2))+'</textarea></label>'+
        (source?'<label><input name="repin" type="checkbox" style="display:inline;width:auto"> Re-pin unchanged linked records to their latest revisions</label>':'')+
        '<button type="submit">Save '+(source?"new revision":"campaign")+'</button>'+
        '<button type="button" id="campaign-cancel">Cancel</button></form>';
      var form=el("#campaign-form");
      var pricingPicker=null;
      var workingParticipants=(source&&Array.isArray(source.participants)?source.participants:[]).map(function(p){
        return {id:p.id,label:p.label,role:p.role,configuration_version:p.configuration_version,
          component_ids:Object.assign({},p.component_ids),settings:JSON.stringify(p.settings||{},null,2),
          properties:JSON.stringify(p.properties||{},null,2)};
      });
      function participantOptions(kind,value){
        return options(catalog[kind],value,true);
      }
      function readParticipants(){
        var container=el("#campaign-participant-list");
        if(!container||container.hidden)return;
        workingParticipants=Array.from(container.querySelectorAll("[data-participant-row]")).map(function(node){
          var fields=node.querySelectorAll("[data-field]");
          var values={id:node.dataset.participantId||null,component_ids:{}};
          fields.forEach(function(field){
            var k=field.dataset.field;
            if(["model","provider","harness"].includes(k))values.component_ids[k]=field.value;
            else values[k]=field.value;
          });
          return values;
        });
      }
      function drawParticipants(){
        var target=el("#campaign-participant-list");
        target.innerHTML=workingParticipants.map(function(p,i){
          return '<fieldset data-participant-row data-participant-id="'+esc(p.id||"")+
            '" style="border:1px solid #d6dfed;border-radius:9px;padding:12px;margin:10px 0">'+
            '<legend>Participant '+(i+1)+' · '+esc(p.id||"new identity on save")+'</legend>'+
            '<label>Label<input data-field="label" maxlength="160" required value="'+esc(p.label||"")+'"></label>'+
            '<label>Role<input data-field="role" maxlength="160" required value="'+esc(p.role||"")+'"></label>'+
            '<label>Configuration version<input data-field="configuration_version" maxlength="160" required value="'+esc(p.configuration_version||"1")+'"></label>'+
            ["model","provider","harness"].map(function(k){
              return '<label>'+esc(k)+'<select data-field="'+k+'" required>'+
                participantOptions(k,(p.component_ids||{})[k])+'</select></label>';
            }).join("")+
            '<label>Settings / runtime parameters (JSON object)<textarea data-field="settings">'+
              esc(p.settings||"{}")+'</textarea></label>'+
            '<label>Tools / access / capabilities / extensible metadata (JSON object)<textarea data-field="properties">'+
              esc(p.properties||"{}")+'</textarea></label>'+
            '<button type="button" data-participant-action="up" data-index="'+i+'"'+(i===0?' disabled':'')+'>Move up</button>'+
            '<button type="button" data-participant-action="down" data-index="'+i+'"'+(i===workingParticipants.length-1?' disabled':'')+'>Move down</button>'+
            '<button type="button" data-participant-action="remove" data-index="'+i+'">Remove</button>'+
            '</fieldset>';
        }).join("");
      }
      el("#campaign-participant-add").addEventListener("click",function(){
        readParticipants();
        workingParticipants.push({label:"",role:"",configuration_version:"1",
          component_ids:{model:"",provider:"",harness:""},settings:"{}",properties:"{}"});
        drawParticipants();
      });
      el("#campaign-participant-list").addEventListener("click",function(event){
        var btn=event.target.closest("button[data-participant-action]");
        if(!btn)return;
        readParticipants();
        var index=Number(btn.dataset.index),action=btn.dataset.participantAction;
        if(index<0||index>=workingParticipants.length)return;
        if(action==="remove")workingParticipants.splice(index,1);
        if(action==="up"&&index>0)
          [workingParticipants[index-1],workingParticipants[index]]=[workingParticipants[index],workingParticipants[index-1]];
        if(action==="down"&&index+1<workingParticipants.length)
          [workingParticipants[index+1],workingParticipants[index]]=[workingParticipants[index],workingParticipants[index+1]];
        drawParticipants();
      });
      function syncFramework(){
        var hasFramework=!!form.elements.framework_id.value;
        el("#campaign-participants-row").hidden=!hasFramework;
        el("#campaign-solution-row").hidden=hasFramework||form.elements.mode.value!=="solution_centred";
      }
      form.elements.framework_id.addEventListener("change",function(){
        if(el("#campaign-participants-row").hidden===false)readParticipants();
        // Selecting a different Framework never implicitly adopts old participant identities.
        if(!source||form.elements.framework_id.value!==source.framework_id)
          workingParticipants=[];
        drawParticipants();
        syncFramework();
      });
      drawParticipants();
      function syncMode(){
        var chosen=form.elements.mode.value;
        el("#campaign-task-row").hidden=chosen!=="task_centred";
        syncFramework();
        var matching=methods.filter(function(m){return m.mode===chosen;});
        var last=form.elements.method_version.value;
        form.elements.method_version.innerHTML=matching.map(function(m){
          return '<option value="'+m.version+'">Version '+m.version+'</option>';
        }).join("");
        if(matching.some(function(m){return String(m.version)===last;}))form.elements.method_version.value=last;
        else if(source&&source.mode===chosen)form.elements.method_version.value=String(source.method_version);
        showMethod();
      }
      function showMethod(){
        var method=methods.find(function(x){return x.mode===form.elements.mode.value&&
          String(x.version)===form.elements.method_version.value;});
        var node=el("#campaign-method-details");
        node.textContent=method?"Method v"+method.version+" · "+
          (method.descriptor.steps||[]).map(function(x){return x.label||x.key;}).join(" → "):"No registered method for this mode";
      }
      form.elements.mode.addEventListener("change",syncMode);
      form.elements.method_version.addEventListener("change",showMethod);
      syncMode();
      el("#campaign-cancel").addEventListener("click",function(){target.hidden=true;});
      el("#campaign-preview-guide").addEventListener("click",async function(){
        var output=el("#campaign-guide-preview"),button=this;button.disabled=true;
        try{
          var guide=guides.find(function(g){return g.id===form.elements.guide_id.value;});
          if(!guide)throw Error("Select a registered guide");
          var configuration=JSON.parse(form.elements.preview_environment.value||"{}");
          if(!configuration||Array.isArray(configuration)||typeof configuration!=="object")
            throw Error("Environment must be a JSON object");
          if(form.elements.framework_id.value){
            readParticipants();
            configuration.framework=form.elements.framework_id.value;
            configuration.participants=workingParticipants.map(function(p){
              return {id:p.id||"planned",model:p.component_ids.model,
                provider:p.component_ids.provider,harness:p.component_ids.harness,
                configuration_version:p.configuration_version};
            });
          }else{
            ["model","provider","harness"].forEach(function(k){
              if(form.elements[k]&&form.elements[k].value)
                configuration[k]=form.elements[k].value;
            });
          }
          var result=await api("guides/render","POST",{
            guide_id:guide.id,revision:guide.revision,configuration:configuration});
          output.textContent=(result.ready?"Declared coverage matched":"Missing or ambiguous coverage")+
            "\n"+JSON.stringify({missing:result.missing,sections:result.sections},null,2);
        }catch(error){output.textContent="Unable to preview: "+error.message;}
        finally{button.disabled=false;}
      });
      el("#campaign-inline-guide").addEventListener("click",function(){
        el("#campaign-guide-form").hidden=false;
      });
      el("#campaign-save-guide").addEventListener("click",async function(){
        var button=this;button.disabled=true;
        try{
          var props={},txt=form.elements.guide_text.value.trim(),url=form.elements.guide_url.value.trim();
          if(txt)props.text=txt;if(url)props.url=url;
          var chosen=Array.from(form.elements.guide_modules.selectedOptions).map(function(x){
            return guides.find(function(g){return g.id===x.value;});
          }).filter(Boolean);
          var raw=form.elements.guide_recipe.value.trim();
          if(raw||chosen.length){
            var recipe=raw?JSON.parse(raw):{modules:[],required:[]};
            if(!recipe||Array.isArray(recipe)||typeof recipe!=="object"||
               !Array.isArray(recipe.modules))throw Error("Recipe must have a modules array");
            chosen.forEach(function(g){
              if(!recipe.modules.some(function(m){return m.id===g.id&&m.revision===g.revision;}))
                recipe.modules.push({id:g.id,revision:g.revision});
            });
            props.recipe=recipe;
          }
          var saved=await api("guides","POST",{name:form.elements.guide_name.value,properties:props});
          guides.push(saved);
          form.elements.guide_id.innerHTML=options(guides,saved.id,true);
          el("#campaign-guide-form").hidden=true;
          status("Guide "+saved.id+" saved; campaign will pin its current revision when saved.");
        }catch(error){status("Guide creation refused: "+error.message,true);}
        finally{button.disabled=false;}
      });
      // Future Metered Runs (FUT-09) consume exact selections from this shared
      // read/write contract, never independently guessed unit prices.
      pricingPicker=window.AICompassPricingSelection.mount(
        el("#campaign-pricing"),form,offers,source&&source.pricing_selections,
        function(){return workingParticipants;});
      form.addEventListener("change",function(event){
        if(["mode","framework_id","model","provider","harness"].includes(event.target.name))
          pricingPicker.render();
      });
      el("#campaign-participant-list").addEventListener("change",function(){
        readParticipants();pricingPicker.render();
      });
      form.addEventListener("submit",async function(e){
        e.preventDefault();var button=form.querySelector('button[type="submit"]');
        button.disabled=true;
        try{
          var selectedMode=form.elements.mode.value;
          var config=JSON.parse(form.elements.configuration.value);
          if(!config||Array.isArray(config)||typeof config!=="object")throw Error("Configuration must be a JSON object");
          var selected=Array.from(form.elements.test_case_ids.selectedOptions).map(function(x){return x.value;});
          var payload={
            name:form.elements.name.value, objective:form.elements.objective.value,
            notes:form.elements.notes.value, mode:selectedMode,
            method_version:Number(form.elements.method_version.value),
            test_case_ids:selected, guide_id:form.elements.guide_id.value||null,
            configuration:config,pricing_selections:pricingPicker.selections()
          };
          if(form.elements.owner.value.trim())payload.owner=form.elements.owner.value.trim();
          var chosenFramework=form.elements.framework_id.value||null;
          payload.framework_id=chosenFramework;
          if(chosenFramework){
            readParticipants();
            if(!workingParticipants.length)throw Error("Add at least one Framework participant");
            payload.participants=workingParticipants.map(function(p){
              var row={label:p.label,role:p.role,configuration_version:p.configuration_version,
                component_ids:p.component_ids,settings:JSON.parse(p.settings),properties:JSON.parse(p.properties)};
              if(p.id)row.id=p.id;
              if(!row.settings||Array.isArray(row.settings)||typeof row.settings!=="object")
                throw Error("Participant settings must be a JSON object");
              if(!row.properties||Array.isArray(row.properties)||typeof row.properties!=="object")
                throw Error("Participant properties must be a JSON object");
              return row;
            });
          }else{
            payload.participants=[];
          }
          if(selectedMode==="task_centred")payload.task_id=form.elements.task_id.value;
          else if(!chosenFramework)payload.component_ids=Object.fromEntries(["model","provider","harness"].map(function(k){
            return [k,form.elements[k].value];}));
          if(source){
            payload.expected_revision=source.revision;
            payload.repin=form.elements.repin.checked;
          }
          var saved=source?await api("campaigns/"+encodeURIComponent(source.id),"PATCH",payload):
            await api("campaigns","POST",payload);
          target.hidden=true;await refresh();
          status("Saved "+(saved.campaign||saved).id+" as a new immutable Server revision.");
        }catch(error){status("Campaign save refused: "+error.message,true);}
        finally{button.disabled=false;}
      });
    }
    async function transition(row,action){
      if(!allowed||(["publish","unpublish"].includes(action)?!canReview:!canWrite))return;
      var run=++ticket;
      status("Applying "+action+" to "+row.id+"…");
      try{
        var result=await api("campaigns/"+encodeURIComponent(row.id)+"/actions/"+encodeURIComponent(action),
          "POST",{expected_revision:row.revision});
        if(!allowed||run!==ticket)return;
        await refresh();
        status("Campaign "+result.campaign.id+" · "+result.campaign.revision+
          " · "+result.campaign.status+(result.campaign.archived?" (archived)":""));
      }catch(error){if(allowed&&run===ticket)status("Transition refused: "+error.message,true);}
    }

    async function showMatrix(row,filter){
      if(!allowed)return;
      var target=el("#campaign-detail");
      target.hidden=false;target.textContent="Loading versioned evaluation matrix…";
      try{
        var matrix=await api("campaigns/"+encodeURIComponent(row.id)+"/matrix");
        var byId=Object.fromEntries((matrix.configurations||[]).map(function(c){return [c.id,c];}));
        var configRows=matrix.configurations||[],cells=matrix.cells||[];
        var taskIds=Array.from(new Set(configRows.map(function(c){return c.task_id;})));
        var editable=canWrite&&!row.archived&&["planned","in_progress"].includes(row.status);
        var chosenTask=taskIds.includes(filter)?filter:"";
        function taskName(id){var t=tasks.find(function(x){return x.id===id;});return t?t.name:id;}
        function tcName(id){var t=cases.find(function(x){return x.id===id;});return t?t.name:id;}
        var counts=matrix.summary||{};
        var html='<h3>'+esc(row.name)+' · Evaluation Matrix · '+esc(matrix.revision)+'</h3>'+
          '<p class="muted small">Task-associated configurations only · each pair has a stable evaluation ID. Candidate planning is distinct from immutable measured Runs.</p>'+
          '<p><strong>Full plan: '+(counts.full_plan_complete?"fulfilled":"outstanding")+'</strong>'+
          ' · '+(counts.candidates||0)+' candidates · '+(counts.evaluated||0)+' evaluated · '+
          (counts.pending||0)+' pending · '+(counts.in_progress||0)+' in progress · '+
          (counts.waived||0)+' waived · '+(counts.not_selected||0)+' not selected · '+
          (counts.measured_runs||0)+' measured Run(s)</p>'+
          '<p class="muted small">Experimental coverage: '+(counts.evaluated||0)+' / '+
          (counts.selected_obligations||0)+' selected combinations. Waived/Not Selected are not measured evidence. Pending cells do not invalidate independent eligible Runs.</p>'+
          '<label>Task filter<select id="matrix-task-filter"><option value="">All tasks</option>'+
          taskIds.map(function(id){return '<option value="'+esc(id)+'"'+(id===chosenTask?" selected":"")+'>'+esc(taskName(id))+'</option>';}).join("")+
          '</select></label>'+
          '<div id="matrix-tables" style="overflow-x:auto">';
        taskIds.filter(function(id){return !chosenTask||id===chosenTask;}).forEach(function(taskId){
          var cols=configRows.filter(function(x){return x.task_id===taskId;});
          var rows=Array.from(new Set(cells.filter(function(x){return byId[x.configuration_id]?.task_id===taskId;}).map(function(x){return x.test_case_id;})));
          html+='<h4>'+esc(taskName(taskId))+' · '+cols.length+' configurations</h4>'+
            '<table style="width:100%;border-collapse:collapse"><thead><tr><th>Test Case</th>'+
            cols.map(function(x){return '<th>'+esc(x.label)+'<div class="muted small">'+esc(x.kind)+' · '+esc(x.id)+'</div></th>';}).join("")+
            '</tr></thead><tbody>';
          rows.forEach(function(testCaseId){
            html+='<tr><th style="text-align:left">'+esc(tcName(testCaseId))+'</th>'+
              cols.map(function(cfg){
                var cell=cells.find(function(x){return x.test_case_id===testCaseId&&x.configuration_id===cfg.id;});
                if(!cell)return '<td>—</td>';
                var muted=cell.status==="not_selected"?'opacity:.55;':"";
                return '<td style="border:1px solid #e3e8f0;padding:8px;'+muted+'">'+
                  '<button type="button" data-matrix-cell="'+esc(cell.id)+'">'+esc(cell.status.replaceAll("_"," "))+
                  '</button><div class="muted small">'+cell.runs.length+' Run(s)'+
                  (cell.waiver?'<p>Waiver: '+esc(cell.waiver.reason)+'</p>':"")+'</div></td>';
              }).join("")+'</tr>';
          });
          html+='</tbody></table>';
        });
        html+='</div><section id="matrix-cell-details" class="server-card" hidden></section>';
        if(editable){
          html+='<details><summary>+ Add Task-associated AI configuration</summary><form id="matrix-add-form">'+
            '<label>Task<select name="task_id">'+tasks.map(function(t){return '<option value="'+esc(t.id)+'">'+esc(t.name)+'</option>';}).join("")+'</select></label>'+
            '<label>Configuration label<input name="label" maxlength="160" required placeholder="Model + Provider + Harness"></label>'+
            '<label>Column type<select name="kind"><option value="individual">Individual AI configuration</option>'+
            (row.framework_id?'<option value="framework">Framework workflow</option>':"")+'</select></label>'+
            '<div id="matrix-trio-fields">'+["model","provider","harness"].map(function(k){
              return '<label>'+esc(k)+'<select name="'+k+'">'+options(catalog[k],null,false)+'</select></label>';
            }).join("")+
            '<label>Configuration version<input name="configuration_version" value="1"></label>'+
            '<label>Settings (JSON)<textarea name="settings">{}</textarea></label></div>'+
            (row.framework_id?'<label id="matrix-participants" hidden>Framework participants<select name="participant_ids" multiple size="5">'+
            (row.participants||[]).map(function(p){return '<option value="'+esc(p.id)+'">'+esc(p.label||p.id)+'</option>';}).join("")+
            '</select></label>':"")+
            '<label>Relevant Test Cases for Task (Ctrl/Command to select)<select name="test_case_ids" multiple size="6"></select></label>'+
            '<button type="submit">Add configuration and planned evaluation cells</button></form></details>'+
            '<details><summary>+ Offer new Test Cases to all configurations of a Task</summary>'+
            '<form id="matrix-add-cases"><label>Configuration<select name="configuration_id">'+
            configRows.map(function(x){return '<option value="'+esc(x.id)+'">'+esc(x.label)+' · '+esc(taskName(x.task_id))+'</option>';}).join("")+
            '</select></label><label>Test Cases<select name="test_case_ids" multiple size="5"></select></label>'+
            '<button type="submit">Add Test Cases, preserving existing decisions</button></form></details>';
        }
        html+='<p><button type="button" id="matrix-close">Close matrix</button></p>';
        target.innerHTML=html;
        target.querySelector("#matrix-close").addEventListener("click",function(){target.hidden=true;});
        target.querySelector("#matrix-task-filter").addEventListener("change",function(){showMatrix(row,this.value);});
        function choose(id){return cells.find(function(x){return x.id===id;});}
        target.querySelectorAll("[data-matrix-cell]").forEach(function(button){
          button.addEventListener("click",function(){
            var cell=choose(button.dataset.matrixCell),cfg=byId[cell.configuration_id];
            var detail=target.querySelector("#matrix-cell-details");detail.hidden=false;
            detail.innerHTML='<h4>'+esc(tcName(cell.test_case_id))+' × '+esc(cfg.label)+'</h4>'+
              '<p>'+esc(cell.id)+' · '+esc(cell.status)+' · '+esc(cell.decision)+'</p>'+
              '<p>Attempts in progress: '+cell.active_attempts+' · Closed measured Runs: '+cell.runs.length+'</p>'+
              (cell.waiver?'<p>Waived by '+esc(cell.waiver.actor)+' at '+esc(cell.waiver.at)+
              ' — '+esc(cell.waiver.reason)+'</p>':"")+
              '<pre style="white-space:pre-wrap;overflow-wrap:anywhere"></pre>'+
              (editable?'<label>Waiver explanation (mandatory when waiving)<textarea id="matrix-waiver-reason" maxlength="4000"></textarea></label>'+
                [["selected","Select / reinstate"],["not_selected","Not Selected"],["waived","Waive"]].map(function(x){
                  return '<button type="button" data-matrix-decision="'+x[0]+'">'+x[1]+'</button>';
                }).join(" "):"")+
              '<button type="button" id="matrix-open-sessions">Open Test Run workspace</button>';
            detail.querySelector("pre").textContent=JSON.stringify({runs:cell.runs,history:cell.history,
               configuration:cfg},null,2);
            detail.querySelector("#matrix-open-sessions").addEventListener("click",function(){
              if(sessionWorkspace)sessionWorkspace.openCampaign(row);
            });
            detail.querySelectorAll("[data-matrix-decision]").forEach(function(action){
              action.disabled=action.dataset.matrixDecision===cell.decision;
              action.addEventListener("click",function(){
                change({action:"decide",evaluation_id:cell.id,
                  decision:action.dataset.matrixDecision,
                  reason:action.dataset.matrixDecision==="waived"?
                    detail.querySelector("#matrix-waiver-reason").value:""});
              });
            });
          });
        });
        async function change(operation){
          if(!editable)return;
          status("Saving immutable evaluation plan revision…");
          try{
            var saved=await api("campaigns/"+encodeURIComponent(row.id)+"/matrix/edit",
              "PATCH",{expected_revision:row.revision,operation:operation});
            Object.assign(row,saved.campaign);
            await refresh();
            await showMatrix(row,chosenTask);
            status("Matrix updated: "+row.id+" · "+row.revision+" (previous revisions preserved).");
          }catch(error){status("Matrix change refused: "+error.message,true);}
        }
        if(!editable)return;
        var form=target.querySelector("#matrix-add-form");
        function matchingCases(task){return cases.filter(function(x){return x.task_id===task;});}
        function refreshCandidates(){
          form.elements.test_case_ids.innerHTML=matchingCases(form.elements.task_id.value).map(function(x){
            return '<option value="'+esc(x.id)+'" selected>'+esc(x.name)+'</option>';
          }).join("");
          var framework=form.elements.kind.value==="framework";
          form.querySelector("#matrix-trio-fields").hidden=framework;
          if(form.querySelector("#matrix-participants"))form.querySelector("#matrix-participants").hidden=!framework;
        }
        form.elements.task_id.addEventListener("change",refreshCandidates);
        form.elements.kind.addEventListener("change",refreshCandidates);
        refreshCandidates();
        form.addEventListener("submit",function(e){
          e.preventDefault();
          try{
            var kind=form.elements.kind.value,
                data={action:"add_configuration",task_id:form.elements.task_id.value,
                  kind:kind,label:form.elements.label.value,
                  test_case_ids:Array.from(form.elements.test_case_ids.selectedOptions).map(function(x){return x.value;})};
            if(kind==="framework"){
              data.participant_ids=Array.from(form.elements.participant_ids.selectedOptions).map(function(x){return x.value;});
            }else{
              data.component_ids=Object.fromEntries(["model","provider","harness"].map(function(k){return [k,form.elements[k].value];}));
              data.configuration_version=form.elements.configuration_version.value;
              data.settings=JSON.parse(form.elements.settings.value||"{}");
            }
            change(data);
          }catch(error){status("Invalid matrix configuration: "+error.message,true);}
        });
        var add=target.querySelector("#matrix-add-cases");
        function refreshCasePicker(){
          var config=byId[add.elements.configuration_id.value];
          add.elements.test_case_ids.innerHTML=matchingCases(config?config.task_id:"").map(function(x){
            return '<option value="'+esc(x.id)+'">'+esc(x.name)+'</option>';
          }).join("");
        }
        add.elements.configuration_id.addEventListener("change",refreshCasePicker);
        refreshCasePicker();
        add.addEventListener("submit",function(e){
          e.preventDefault();
          change({action:"add_cases",configuration_id:add.elements.configuration_id.value,
            test_case_ids:Array.from(add.elements.test_case_ids.selectedOptions).map(function(x){return x.value;})});
        });
      }catch(error){target.textContent="Evaluation matrix unavailable: "+error.message;}
    }
    async function history(row){
      var run=ticket,target=el("#campaign-detail");
      target.hidden=false;target.textContent="Loading historical snapshots and evidence…";
      try{
        var result=await Promise.all([
          api("campaigns/"+encodeURIComponent(row.id)+"/revisions"),
          api("catalog/items/"+encodeURIComponent(row.id)+"/evidence")
        ]);
        if(!allowed||run!==ticket)return;
        var versions=result[0].revisions,links=result[1].results||[];
        target.innerHTML='<h3>'+esc(row.name)+' · original campaign revisions</h3>'+
          '<p>'+links.length+' immutable evidence link(s) from the shared evidence store.</p>'+
          versions.map(function(r){
            return '<details><summary>'+esc(r.revision)+' · '+esc(r.created_at)+
              ' · '+esc(r.created_by)+' · '+esc(r.status)+(r.archived?' (archived)':'')+
              '</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';
          }).join("")+
          '<button type="button" id="campaign-close-detail">Close details</button>';
        target.querySelectorAll("details pre").forEach(function(node,i){
          node.textContent=JSON.stringify(versions[i],null,2);
        });
        el("#campaign-close-detail").addEventListener("click",function(){target.hidden=true;});
      }catch(error){if(allowed&&run===ticket)target.textContent="History unavailable: "+error.message;}
    }
    function setAccess(read,write,review){
      ++ticket;allowed=!!read;canWrite=!!write&&allowed;canReview=!!review&&allowed;
      campaigns=[];methods=[];root.replaceChildren();root.hidden=!allowed;
      if(allowed){build();refresh();}
    }
    root.hidden=true;
    return {setAccess:setAccess,refresh:refresh};
  }
  window.AICompassServerCampaigns={mount:mount};
})();
