/* PLAT-12: persistent Server campaigns. No Demo storage or runtime fallback. */
(function () {
  "use strict";
  var MODE_LABELS={task_centred:"Compare solutions on one task",solution_centred:"Evaluate one solution across tasks"};
  var STATES=["planned","in_progress","under_review","published"];
  var NEXT={
    planned:[["start","Start campaign"]],
    in_progress:[["close","Close full plan"],["close_partial","Close partial review"]],
    under_review:[["rework","Request rework"],["publish","Review / publish selected Runs"],["reopen","Reopen"]],
    published:[["unpublish","Unpublish"],["reopen","Reopen"]]
  };
  function mount(root, csrf, escapeHtml) {
    var allowed=false,canWrite=false,canReview=false,ticket=0,campaigns=[],methods=[],tasks=[],cases=[],guides=[];
    var catalog={model:[],provider:[],harness:[],framework:[]},offers=[],sessionWorkspace=null,
      activeDraft=null,extraDrafts=[];
    function el(selector){return root.querySelector(selector);}
    function esc(value){return escapeHtml(value==null?"":String(value));}
    function status(message,error){
      var node=el("#campaign-status");
      if(node){
        node.className=error?"server-status server-error":"server-status";
        node.innerHTML=window.AICompassWorkgroup.renderDomainStatus({
          mode:"server",state:error?"error":"ok",message:message==null?"":String(message)});
      }
    }
    async function api(path,method,payload){
      var opts={method:method||"GET",credentials:"same-origin",cache:"no-store"};
      if(method&&method!=="GET"){
        opts.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
        opts.body=JSON.stringify(payload);
      }
      var response=await fetch("/api/v1/"+path,opts);
      var body=await response.json().catch(function(){return {};});
      /* UX-R05: keep the HTTP status so 409/403 become explicit conflict UI. */
      if(!response.ok)throw(window.AICompassRuntime&&window.AICompassRuntime.httpError?
        window.AICompassRuntime.httpError(response.status,body):
        Error(body.detail||body.error||"HTTP "+response.status));
      return body;
    }
    function drafts(){return window.AICompassDrafts;}
    function disposeExtras(){
      extraDrafts.forEach(function(handle){if(handle&&handle.dispose)handle.dispose();});
      extraDrafts=[];
    }
    /* Secondary long-lived forms in the same screen (matrix builders) get their
     * own bounded local draft so unsaved input survives navigation or reload. */
    function attachDraftForm(form,kind,options){
      var d=drafts();
      if(!d||!d.forMode||!form)return null;
      var scope=d.forMode("server",kind,options||{});
      if(!scope)return null;
      var handle=d.attach(form,scope);
      extraDrafts.push(handle);
      return handle;
    }
    function failure(error){
      return window.AICompassRuntime&&window.AICompassRuntime.failureInfo?
        window.AICompassRuntime.failureInfo(error):{conflict:false,detail:error&&error.message};
    }
    function build(){
      root.innerHTML='<div class="server-model-toolbar"><div><h2>Benchmark Workspace · Campaigns</h2>'+
        '<p class="muted small">Shared planning, immutable revisions and controlled lifecycle · PostgreSQL only</p></div>'+
        '<button type="button" id="campaign-refresh">Refresh</button></div>'+
        '<p id="campaign-status" class="server-status" role="status"></p>'+
        '<h3>Workgroup pipeline · read only</h3><div id="campaign-pipeline"></div>'+
        '<h3>Campaign management</h3>'+
        (canWrite?'<button type="button" id="campaign-add">+ Create campaign</button>':'')+
        '<div id="campaign-context-view"></div>'+
        '<div id="campaign-list" class="server-card"></div>'+
        '<section id="campaign-editor" class="server-card" hidden></section>'+
        '<section id="campaign-detail" class="server-card" hidden></section>'+
        '<section id="campaign-session-area" class="server-card" hidden></section>';
      sessionWorkspace=window.AICompassServerSessions.mount(el("#campaign-session-area"),api,esc);
      sessionWorkspace.setAccess(allowed,canWrite);
      el("#campaign-refresh").addEventListener("click",refresh);
      if(canWrite)el("#campaign-add").addEventListener("click",function(){editor(null);});
      el("#campaign-list").addEventListener("click",function(e){
        if(e.target.closest("#campaign-focus-clear")){
          var focusUrl=new URL(window.location.href);
          focusUrl.searchParams.delete("status");
          window.history.replaceState(window.history.state,"",
            focusUrl.pathname+focusUrl.search+focusUrl.hash);
          render();return;
        }
        var btn=e.target.closest("button[data-id]");
        if(btn)dispatch(btn);
      });
      // The shared lifecycle bar of the detail panel routes through the same
      // dispatch, so a transition means exactly the same thing wherever it is
      // offered.
      el("#campaign-detail").addEventListener("click",function(e){
        var btn=e.target.closest("button[data-action][data-id]");
        if(btn)dispatch(btn);
      });
    }
    function dispatch(button){
      var row=campaigns.find(function(c){return c.id===button.dataset.id;});
      if(!row)return;
      var action=button.dataset.action;
      if(action==="matrix")showMatrix(row);
      else if(action==="publication")showPublication(row);
      else if(action==="sessions"&&sessionWorkspace)sessionWorkspace.openCampaign(row);
      else if(action==="history")history(row);
      else if(canWrite&&action==="edit")editor(row);
      else if(action&&(["publish","unpublish"].includes(action)?canReview:canWrite))
        transition(row,action);
    }
    // Same offered transitions and labels as the offline Demo campaign detail.
    function campaignLifecycleBar(row){
      var keys=window.AICompassWorkgroup.campaignLifecycleActionKeys(
        row.archived?"archived":row.status).filter(function(key){
          return ["publish","unpublish"].includes(key)?canReview:canWrite;});
      return window.AICompassWorkgroup.renderLifecycleActions(keys.map(function(key){
        return {key:key,attributes:{"data-id":row.id,"data-action":key}};}),
        {mode:"server",domain:"campaigns",
         notice:"Every transition appends an immutable campaign revision; archived history stays readable."});
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
      var route=new URLSearchParams(window.location.search),focusId=route.get("record");
      var statusFocus=["planned","in_progress","under_review","published"].includes(
        route.get("status"))?route.get("status"):"";
      var awaitingFocus=route.get("status")==="awaiting_publication";
      var focused=focusId&&campaigns.find(function(x){return x.id===focusId;});
      var context=el("#campaign-context-view");
      if(focusId){
        if(!focused){
          context.innerHTML='<p class="ux-history-warning" role="alert">Campaign unavailable or not authorized. No current record substituted.</p>';
        }else{
          var requested=route.get("revision"),current=focused.revision||"";
          context.innerHTML=window.AICompassContext.recordDetails(focused,"benchmark","server",requested).html+
            '<p><a href="'+esc(window.AICompassContext.route("server","workgroup","benchmark",{from:""}))+
            '">Show all authorized Campaigns</a></p>';
          var source=context.querySelector(".ux-advanced-source pre");
          if(source)source.textContent=JSON.stringify(focused,null,2);
        }
      }else context.replaceChildren();
      var listed=focused?[focused]:focusId?[]:campaigns.filter(function(x){
        if(awaitingFocus)return x.status==="under_review"&&!x.effective_publication;
        return !statusFocus||x.status===statusFocus;});
      var focusNote="";
      if(statusFocus||awaitingFocus){
        var focusCount=listed.length;
        focusNote='<p class="muted small" data-campaign-status-focus role="status">Focused on '+
          esc((awaitingFocus?"awaiting a review decision":statusFocus.replaceAll("_"," ")))+
          ' campaigns ('+focusCount+' of '+
          (focused?1:campaigns.length)+'). This is a read-only derived filter from the Studio '+
          'count, not a personal assignment. <button type="button" id="campaign-focus-clear">'+
          'Show all campaigns</button></p>';
      }
      list.innerHTML=focusNote+window.AICompassWorkgroup.renderRecords(
        listed.map(function(x){
          var commands=x.archived?[["restore","Restore archive"]]:
            (NEXT[x.status]||[]).concat([["archive","Archive"]]);
          var actions=["matrix","sessions","history","publication"].map(function(k,i){
            return {label:["Evaluation matrix","Sessions / resume","Details / history","Published evidence"][i],
              attributes:{"data-id":x.id,"data-action":k}};
          });
          if(canWrite&&!x.archived&&["planned","in_progress"].includes(x.status))
            actions.push({label:"Edit",attributes:{"data-id":x.id,"data-action":"edit"}});
          commands.forEach(function(k){
            if(["publish","unpublish"].includes(k[0])?canReview:canWrite)
              actions.push({label:k[1],attributes:{"data-id":x.id,"data-action":k[0]}});
          });
          var pricing=x.pricing_readiness||{};
          var readiness=pricing.complete?"complete / exact offer pins":
            (pricing.requires_session_pricing?"tariffs selected per Test Case session":
             "INCOMPLETE / new metered session blocked");
          var notes=["Pricing · "+readiness];
          if(x.effective_publication){
            var pub=x.effective_publication,coverage=pub.coverage||{};
            notes.push("Effective publication · "+pub.revision+" · "+pub.included_runs+
              " Run(s) · "+(coverage.plan==="matrix"&&!coverage.full_plan_complete?
                  "partial coverage":"reviewed subset"));
          }
          return {id:x.id,title:x.name,status:x.status,revision:x.revision,
            description:(x.properties||{}).objective||"",
            facts:["Owner: "+x.owner,(x.test_case_ids||[]).length+" Test Case(s)"].concat(
              x.framework_id?["Framework "+x.framework_id,
                (x.participants||[]).length+" participant(s)"]:[]).concat(x.archived?["archived"]:[]),
            notices:notes,
            links:[{label:"Open Campaign detail",
              href:window.AICompassContext.contextualLink("server","workgroup","benchmark",x.id)}],
            actions:actions};
        }),{domain:"campaigns",mode:"server",emptyText:focusId?
          "Campaign unavailable or not authorized.":"No real Server campaigns yet. Create Tasks and Test Cases first."});

    }
    async function refresh(){
      if(!allowed)return;
      var run=++ticket;
      status("Loading shared Server campaigns and reference catalogs…");
      try{
        var responses=await Promise.all([
          api("campaigns"),api("campaign-methods"),api("tasks"),api("test-cases"),
          api("guides"),api("models"),api("catalog/provider"),api("catalog/harness"),
          api("catalog/framework"),api("pricing/offers")
        ]);
        if(!allowed||run!==ticket)return;
        campaigns=responses[0].results; methods=responses[1].results;
        tasks=responses[2].results; cases=responses[3].results; guides=responses[4].results;
        ["model","provider","harness","framework"].forEach(function(k,i){catalog[k]=responses[i+5].results;});
        offers=responses[9].results;
        render();status(campaigns.length+" campaign(s) persisted in Server. Pipeline shows plans, not measured results.");
        var route=new URLSearchParams(window.location.search);
        if(route.get("view")==="matrix"&&route.get("record")){
          var focus=campaigns.find(function(c){return c.id===route.get("record");});
          if(focus)showMatrix(focus,route.get("task"),route.get("revision"));
        }
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
    /* Adapter only: authorized Server rows and same-origin routing. The grid,
     * counters, cell detail and decision fields come from the shared component. */
    function matrixProjection(matrix,row){
      var configurations=matrix.configurations||[],cells=matrix.cells||[];
      var taskIds=Array.from(new Set(configurations.map(function(x){return x.task_id;})));
      var caseIds=Array.from(new Set(cells.map(function(x){return x.test_case_id;})));
      function name(list,id,key){var found=list.find(function(x){return x.id===id;});return found?(found[key]||id):id;}
      return {revision:matrix.revision||row.revision,
        tasks:taskIds.map(function(id){return {id:id,name:name(tasks,id,"name")};}),
        // No current-revision Test Case link: each cell pins its own revision.
        testCases:caseIds.map(function(id){return {id:id,name:name(cases,id,"name")};}),
        configurations:configurations.map(function(x){
          return {id:x.id,taskId:x.task_id,label:x.label,kind:x.kind};}),
        cells:cells.map(function(cell){
          return {id:cell.id,configurationId:cell.configuration_id,
            testCaseId:cell.test_case_id,testCaseRevision:cell.test_case_revision||"",
            status:cell.status,decision:cell.decision,activeAttempts:cell.active_attempts||0,
            introducedRevision:cell.introduced_revision||"",
            // The exact evaluated Test Case source, never the current version.
            testCaseHref:window.AICompassContext.route("server","workgroup","testdesign",{
              record:cell.test_case_id,revision:cell.test_case_revision||""}),
            waiver:cell.waiver?{reason:cell.waiver.reason,actor:cell.waiver.actor,at:cell.waiver.at}:null,
            runs:(cell.runs||[]).map(function(run){
              return {id:run.id,kind:run.kind||"",revision:run.effective_revision||"",
                outcome:run.outcome||"",
                href:window.AICompassContext.route("server","workgroup","results",{
                  record:run.id,revision:run.effective_revision||"",task:cell.task_id||""})};})};})};
    }
    function editor(source){
      if(!allowed||!canWrite)return;
      var target=el("#campaign-editor"),mode=source?source.mode:"task_centred";
      /* One live draft handle at a time: re-rendering the editor must not leak
       * listeners or leave a stale handle reporting unsaved changes. */
      if(activeDraft&&activeDraft.dispose)activeDraft.dispose();
      activeDraft=null;
      disposeExtras();
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
      var campaignDraftScope=drafts()&&drafts().forMode?drafts().forMode(
        "server","campaign",{id:source?source.id:"new",
          revision:source?source.revision:"new",schema:"campaign-form-v2",
          label:source?source.name:"New campaign",guardUnload:true,
          onConflictReload:function(info,entry){
            reloadLatestCampaign(source,info,entry);
          }}):null;
      activeDraft=campaignDraftScope?drafts().attach(form,campaignDraftScope):null;
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
          if(activeDraft&&activeDraft.clear)activeDraft.clear();
          activeDraft=null;
          target.hidden=true;await refresh();
          status("Saved "+(saved.campaign||saved).id+" as a new immutable Server revision.");
        }catch(error){
          var info=failure(error);
          if(activeDraft&&info.conflict){
            var latest=null;
            if(source){
              try{var detail=await api("campaigns"+"/"+encodeURIComponent(source.id));
                latest=detail.campaign||detail;}catch(_){}
            }
            activeDraft.conflict({label:source?source.name:"New campaign",
              baseRevision:source?source.revision:"new",
              latestRevision:latest?latest.revision:"unknown",
              message:info.detail});
          }
          status("Campaign save refused"+(info.conflict?" (409 revision conflict)":
            info.denied?" (not authorized)":"")+": "+info.detail,true);
        }
        finally{button.disabled=false;}
      });
    }
    /* 409 reload: show the newest authoritative campaign, keep the unsaved draft
     * on this device, and never reapply or merge it automatically. */
    async function reloadLatestCampaign(source,info,entry){
      if(!source)return;
      var run=++ticket;
      try{
        var detail=await api("campaigns"+"/"+encodeURIComponent(source.id));
        if(!allowed||run!==ticket)return;
        var fresh=detail.campaign||detail;
        editor(Object.assign({},source,fresh));
        status("Reloaded campaign "+source.id+" at Server revision "+fresh.revision+
          ". Your unsaved draft stays on this device for manual reapplication.");
      }catch(error){
        if(allowed&&run===ticket)status("Could not reload the latest campaign: "+
          failure(error).detail,true);
      }
    }
    async function transition(row,action){
      if(!allowed||(["publish","unpublish"].includes(action)?!canReview:!canWrite))return;
      if(action==="publish"){showPublication(row);return;}
      var run=++ticket;
      status("Applying "+action+" to "+row.id+"…");
      try{
        var isPartial=action==="close_partial";
        var result=await api("campaigns/"+encodeURIComponent(row.id)+"/actions/"+
          encodeURIComponent(isPartial?"close":action),
          "POST",{expected_revision:row.revision,...(isPartial?{partial_review:true}:{})});
        if(!allowed||run!==ticket)return;
        await refresh();
        status("Campaign "+result.campaign.id+" · "+result.campaign.revision+
          " · "+result.campaign.status+(result.campaign.archived?" (archived)":""));
      }catch(error){
        if(!allowed||run!==ticket)return;
        var info=failure(error);
        if(info.conflict&&drafts()&&drafts().notice){
          /* A campaign-wide list/plan change must never be merged automatically. */
          drafts().notice(el("#campaign-list"),{kind:"campaign-transition-conflict",tone:"error",
            title:"Conflict: Campaign "+row.id+" changed since it was opened",
            message:info.detail+" Server revision "+(info.latestRevision||"unknown")+
              "; your base "+row.revision+". Nothing was published, closed or repinned.",
            actions:[{label:"Reload latest campaign",primary:true,onClick:function(){
              refresh().then(function(){status("Reloaded the latest Campaign revision.");});
            }}]});
        }
        status("Transition refused"+(info.conflict?" (409 revision conflict)":
          info.denied?" (not authorized)":"")+": "+info.detail,true);
      }
    }


    async function showPublication(row){
      if(!allowed)return;
      var target=el("#campaign-detail");
      target.hidden=false;
      target.textContent="Loading effective publication and private review…";
      try{
        var allowedPreview=canReview||canWrite;
        var responses=await Promise.all([
          api("campaigns/"+encodeURIComponent(row.id)+"/publication"),
          allowedPreview?api("campaigns/"+encodeURIComponent(row.id)+"/publication/review"):Promise.resolve(null)
        ]);
        var effective=responses[0].publication,review=responses[1];
        var selected=new Set(effective?(effective.runs||[]).map(function(x){return x.id;}):[]);
        var candidates=review?review.candidates:[];
        var html='<h3>'+esc(row.name)+' · Publication</h3>'+
          '<p class="muted small">Published selection is immutable. Reopening keeps the latest published subset visible; new Runs stay private until explicitly selected and republished.</p>'+
          (effective?'<p>Effective '+esc(effective.campaign_revision)+' · '+effective.runs.length+
            ' published Run(s) · reviewed by '+esc(effective.reviewed_by)+'</p>'+
            '<details class="ux-advanced-source"><summary>Advanced: immutable publication coverage data</summary>'+
            '<pre style="white-space:pre-wrap">'+esc(JSON.stringify(effective.coverage,null,2))+'</pre></details>':
            '<p>No effective publication.</p>');
        if(review){
          html+='<h4>Private Run-by-Run guide and eligibility review</h4>'+
            '<p class="muted small">Only fully closed, documented Runs can be published. Failed DoD remains negative evidence; pending and waived evaluations are not evidence. Selection explicitly replaces the old published set.</p>'+
            '<div id="publication-selections">'+(candidates.length?candidates.map(function(c){
              return '<label style="display:block;padding:6px;border-bottom:1px solid #eee">'+
                '<input type="checkbox" data-run-id="'+esc(c.id)+'"'+
                (selected.has(c.id)&&c.eligible?' checked':'')+(c.eligible?'':' disabled')+'>'+
                ' '+esc(c.id)+' · '+esc(c.kind)+' · '+esc(c.outcome)+
                (c.eligible?' · eligible':' · blocked: '+esc(c.blockers.join(", ")))+
                '</label>';
            }).join(""):'<p>No completed Runs yet.</p>')+'</div>';
          if(canReview&&row.status==="under_review"&&!row.archived){
            html+='<label>Reason for removing previously published Runs (if applicable)'+
              '<textarea id="publication-removal-reason" rows="2" maxlength="2000"></textarea></label>'+
              '<button type="button" id="publication-commit">Publish selected eligible Runs</button>';
          }else{
            html+='<p class="muted small">Publication requires review status and publication_review permission.</p>';
          }
        }
        if(effective&&canReview&&!row.archived){
          html+='<button type="button" id="publication-withdraw">Withdraw effective publication</button>';
        }
        html+='<button type="button" id="publication-close">Close</button>';
        target.innerHTML=html;
        target.querySelector("#publication-close").addEventListener("click",function(){target.hidden=true;});
        var withdraw=target.querySelector("#publication-withdraw");
        if(withdraw)withdraw.addEventListener("click",async function(){
          if(!window.confirm("Withdraw all currently published evidence for this campaign? Historical records remain intact."))return;
          withdraw.disabled=true;
          try{
            await api("campaigns/"+encodeURIComponent(row.id)+"/publication/withdraw",
                      "POST",{expected_revision:row.revision});
            target.hidden=true;
            await refresh();
            status("Effective publication withdrawn; historical evidence preserved.");
          }catch(error){status("Withdrawal refused: "+error.message,true);}
          finally{withdraw.disabled=false;}
        });
        var button=target.querySelector("#publication-commit");
        if(button)button.addEventListener("click",async function(){
          var ids=Array.from(target.querySelectorAll("input[data-run-id]:checked")).map(function(e){return e.dataset.runId;});
          if(!ids.length){status("Select at least one eligible Run.",true);return;}
          button.disabled=true;
          try{
            var result=await api("campaigns/"+encodeURIComponent(row.id)+"/publication/publish",
              "POST",{expected_revision:row.revision,run_ids:ids,
              removal_reason:target.querySelector("#publication-removal-reason").value});
            target.hidden=true;
            await refresh();
            status("Published "+result.publication.runs.length+
              " eligible Run(s) at "+result.campaign.revision+".");
          }catch(error){status("Publication rejected: "+error.message,true);}
          finally{button.disabled=false;}
        });
      }catch(error){
        target.textContent="Publication review unavailable: "+error.message;
      }
    }

    async function showMatrix(row,filter,revision){
      if(!allowed)return;
      if(activeDraft&&activeDraft.dispose)activeDraft.dispose();
      activeDraft=null;
      disposeExtras();
      var route=new URL(window.location.href);
      route.searchParams.set("record",row.id);
      route.searchParams.set("view","matrix");
      if(filter)route.searchParams.set("task",filter);else route.searchParams.delete("task");
      if(revision)route.searchParams.set("revision",revision);else route.searchParams.delete("revision");
      window.history.replaceState(window.history.state,"",route.pathname+route.search+route.hash);
      var ctx=document.getElementById("ux-context-navigation");
      if(ctx)window.AICompassContext.syncContext(ctx,"server","workgroup","benchmark");
      var target=el("#campaign-detail");
      target.hidden=false;target.textContent="Loading versioned evaluation matrix…";
      try{
        var responses=await Promise.all([
          api("campaigns/"+encodeURIComponent(row.id)+"/matrix"+
            (revision?"?revision="+encodeURIComponent(revision):"")),
          api("campaigns/"+encodeURIComponent(row.id)+"/revisions")
        ]);
        var matrix=responses[0],revisions=responses[1].revisions||[];
        var byId=Object.fromEntries((matrix.configurations||[]).map(function(c){return [c.id,c];}));
        var configRows=matrix.configurations||[],cells=matrix.cells||[];
        var taskIds=Array.from(new Set(configRows.map(function(c){return c.task_id;})));
        var editable=canWrite&&!row.archived&&["planned","in_progress"].includes(row.status)&&
          (!revision||revision===row.revision);
        var chosenTask=taskIds.includes(filter)?filter:"";
        function taskName(id){var t=tasks.find(function(x){return x.id===id;});return t?t.name:id;}
        var html='<h3>'+esc(row.name)+' · Evaluation Matrix · '+esc(matrix.revision)+'</h3>'+
          window.AICompassWorkgroup.renderStepper(
            window.AICompassWorkgroup.campaignLifecycleSteps(row.status),
            {mode:"server",domain:"campaign"})+
          ((!revision||revision===row.revision)?campaignLifecycleBar(row):
            '<p class="muted small" data-shared-lifecycle-empty>Historical plan revision '+
            esc(matrix.revision)+' — lifecycle transitions are offered on the current '+
            'campaign revision only.</p>')+
          (row.archived?'<p class="muted small" role="status">This campaign revision is archived; '+
            'the lifecycle above is historical.</p>':"")+
          '<p class="muted small">Task-associated configurations only · each pair has a stable evaluation ID. Candidate planning is distinct from immutable measured Runs. Historical decisions are frozen; attempt counts are the live observed projection.</p>'+
          '<label>Plan revision<select id="matrix-revision">'+
          revisions.map(function(r){return '<option value="'+esc(r.revision)+'"'+
            (r.revision===matrix.revision?' selected':'')+'>'+esc(r.revision)+
            ' · '+esc(r.status)+' · '+esc(r.created_by)+'</option>';}).join("")+
          '</select></label>'+
          '<label>Task filter<select id="matrix-task-filter"><option value="">All tasks</option>'+
          taskIds.map(function(id){return '<option value="'+esc(id)+'"'+(id===chosenTask?" selected":"")+'>'+esc(taskName(id))+'</option>';}).join("")+
          '</select></label>';
        var footer="";
        if(editable){
          footer+='<details><summary>+ Add Task-associated AI configuration</summary><form id="matrix-add-form">'+
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
        // One shared matrix presentation; this controller only supplies the
        // authorized projection, exact revision and permissible routing.
        var projection=matrixProjection(matrix,row);
        html+=window.AICompassWorkgroup.renderCampaignMatrix(projection,{
          mode:"server",taskFilter:chosenTask,
          cellAttributes:function(cell){return {"data-matrix-cell":cell.id};},
          footer:footer});
        html+='<section id="matrix-cell-details" class="server-card" hidden></section>';
        html+='<p><button type="button" id="matrix-close">Close matrix</button></p>';
        target.innerHTML=html;
        target.querySelector("#matrix-close").addEventListener("click",function(){
          target.hidden=true;
          var url=new URL(window.location.href);
          url.searchParams.delete("view");
          url.searchParams.delete("task");
          url.searchParams.delete("revision");
          window.history.replaceState(window.history.state,"",url.pathname+url.search+url.hash);
          var ctx=document.getElementById("ux-context-navigation");
          if(ctx)window.AICompassContext.syncContext(ctx,"server","workgroup","benchmark");
        });
        target.querySelector("#matrix-task-filter").addEventListener("change",function(){
          showMatrix(row,this.value,revision);
        });
        target.querySelector("#matrix-revision").addEventListener("change",function(){
          showMatrix(row,chosenTask,this.value);
        });
        function choose(id){return cells.find(function(x){return x.id===id;});}
        /* Test Case display name for a cell's ephemeral waiver draft label: the
         * merged grid (renderCampaignMatrix) renders names itself, so this
         * adapter only needs the lookup for the local draft descriptor. */
        function tcName(id){var t=cases.find(function(x){return x.id===id;});return t?t.name:id;}
        target.querySelectorAll("[data-matrix-cell]").forEach(function(button){
          button.addEventListener("click",function(){
            var cell=choose(button.dataset.matrixCell);
            var detail=target.querySelector("#matrix-cell-details");detail.hidden=false;
            if(activeDraft&&activeDraft.dispose)activeDraft.dispose();
            activeDraft=null;
            detail.innerHTML=window.AICompassWorkgroup.renderMatrixCellDetail(
                projection,cell.id,{mode:"server"})+
              (editable?'<form id="matrix-decision-form" class="server-card">'+
                window.AICompassWorkgroup.renderMatrixDecisionFields(projection,cell.id,"server")+
                '<button type="submit">Save evaluation decision</button></form>':
                '<p class="muted small">A write grant on a planned or in-progress campaign is required '+
                'to change an evaluation decision.</p>')+
              '<p><button type="button" id="matrix-open-sessions">Open Test Run workspace</button></p>'+
              '<details class="ux-advanced-source"><summary>Advanced: immutable matrix cell source</summary>'+
                '<pre style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';
            if(editable){
              var cfg=byId[cell.configuration_id];
              var cellScope=drafts()&&drafts().forMode?drafts().forMode("server",
                "campaign-matrix-waiver",{id:cell.id,revision:row.revision,
                  schema:"campaign-matrix-v1",label:tcName(cell.test_case_id)+" × "+(cfg?cfg.label:cell.configuration_id),
                  guardUnload:true,
                  onConflictReload:function(){showMatrix(row,chosenTask,revision);}}):null;
              activeDraft=cellScope?drafts().attach(detail.querySelector("#matrix-decision-form"),
                cellScope):null;
            }
            detail.querySelector("pre").textContent=JSON.stringify({runs:cell.runs,history:cell.history,
               configuration:byId[cell.configuration_id]},null,2);
            detail.querySelector("#matrix-open-sessions").addEventListener("click",function(){
              if(sessionWorkspace)sessionWorkspace.openCampaign(row,cell.id);
            });
            var decisionForm=detail.querySelector("#matrix-decision-form");
            if(decisionForm)decisionForm.addEventListener("submit",function(event){
              event.preventDefault();
              try{
                change({action:"decide",evaluation_id:cell.id,
                  decision:decisionForm.elements.decision.value,
                  reason:decisionForm.elements.reason.value});
              }catch(error){status("Matrix decision refused: "+error.message,true);}
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
            if(activeDraft&&activeDraft.clear)activeDraft.clear();
            activeDraft=null;
            disposeExtras();
            await refresh();
            await showMatrix(row,chosenTask);
            status("Matrix updated: "+row.id+" · "+row.revision+" (previous revisions preserved).");
          }catch(error){
            var info=failure(error);
            if(info.conflict){
              /* Never merge or repin: show the newer plan and keep the local text. */
              var host=target.querySelector("#matrix-cell-details:not([hidden])")||target;
              var reasonField=target.querySelector("#matrix-reason-server");
              var pendingText=reasonField?reasonField.value:"";
              drafts().notice(host,{kind:"matrix-conflict",tone:"error",
                title:"Conflict: Campaign "+row.id+" plan changed since it was opened",
                message:info.detail+" Your base revision "+row.revision+
                  "; latest Server revision "+(info.latestRevision||"unknown")+
                  ". Nothing was overwritten, merged or repinned. Reapply a waiver manually after reloading.",
                actions:[
                  {label:"Reload latest plan",primary:true,onClick:function(){
                    var url=new URL(window.location.href);
                    if(activeDraft&&activeDraft.dispose)activeDraft.dispose();
                    activeDraft=null;
                    refresh().then(function(){
                      var fresh=campaigns.find(function(c){return c.id===row.id;});
                      if(fresh)showMatrix(fresh,chosenTask);
                    });
                    status("Reloaded the latest Campaign plan. Waiver text stays in the local draft for manual reapplication.");
                  }},
                  {label:"Copy my waiver text",onClick:function(){
                    if(pendingText)drafts().copyText(pendingText);
                    var pre=document.createElement("pre");
                    pre.className="shared-draft-recovery";
                    pre.textContent=pendingText||"No waiver text was entered.";
                    host.appendChild(pre);
                  }},
                  {label:"Discard my waiver text",onClick:function(){
                    if(activeDraft&&activeDraft.clear)activeDraft.clear();
                    activeDraft=null;
                    status("Unsaved waiver text discarded. Server data was never overwritten.");
                  }}
                ]});
            }
            status("Matrix change refused"+(info.conflict?" (409 revision conflict)":"")+
              ": "+info.detail,true);
          }
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
        attachDraftForm(form,"campaign-matrix-configuration",{id:row.id,
          revision:row.revision,schema:"campaign-matrix-add-v1",
          label:"New configuration on "+row.name,guardUnload:true});
        attachDraftForm(add,"campaign-matrix-cases",{id:row.id,revision:row.revision,
          schema:"campaign-matrix-add-v1",label:"Offer Test Cases on "+row.name,
          guardUnload:true});
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
        target.innerHTML=window.AICompassWorkgroup.renderRevisionHistory(
          versions.map(function(r){
            return {revision:r.revision,by:r.created_by,at:r.created_at,
              body:JSON.stringify(r,null,2),
              reason:"Retained campaign revision · "+r.status+(r.archived?" (archived)":"")};
          }),{mode:"server",domain:"campaigns",
            heading:row.name+" · original campaign revisions"})+
          '<p>'+links.length+' immutable evidence link(s) from the shared evidence store.</p>'+
          '<button type="button" id="campaign-close-detail">Close details</button>';
        el("#campaign-close-detail").addEventListener("click",function(){target.hidden=true;});
      }catch(error){if(allowed&&run===ticket)target.textContent="History unavailable: "+error.message;}
    }
    function setAccess(read,write,review){
      ++ticket;allowed=!!read;canWrite=!!write&&allowed;canReview=!!review&&allowed;
      /* Dropping the workspace must not leave a live draft handle reporting
       * unsaved changes for a form that no longer exists. */
      if(activeDraft&&activeDraft.dispose)activeDraft.dispose();
      activeDraft=null;disposeExtras();
      campaigns=[];methods=[];root.replaceChildren();root.hidden=!allowed;
      if(allowed){build();refresh();}
    }
    root.hidden=true;
    return {setAccess:setAccess,refresh:refresh};
  }
  window.AICompassServerCampaigns={mount:mount};
})();
