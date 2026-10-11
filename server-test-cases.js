/* PLAT-10: Server Test Design, strictly isolated from fake Demo records. */
(function () {
  "use strict";
  var FIELDS = [
    ["objective","Objective / challenge"],
    ["inputs","Starting inputs / source context"],
    ["constraints","Constraints / conditions"],
    ["expected_outputs","Expected outputs"],
    ["dod","Definition of Done"],
    ["environment","Environment / setup"],
  ];
  function mount(root, csrf, escapeHtml) {
    var allowed=false, canWrite=false, ticket=0, cases=[], tasks=[], editing=null, mode="create",
      activeDraft=null;
    function el(query) { return root.querySelector(query); }
    function status(message,error) {
      var node=el("#case-status");
      if(node) {node.textContent=message;node.className=error?"server-status server-error":"server-status";}
    }
    async function api(path, method, payload) {
      var options={method:method||"GET",credentials:"same-origin",cache:"no-store"};
      if(method && method!=="GET") {
        options.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
        options.body=JSON.stringify(payload);
      }
      var response=await fetch("/api/v1/"+path,options);
      var data=await response.json().catch(function(){return {};});
      if(!response.ok) throw(window.AICompassRuntime&&window.AICompassRuntime.httpError?
        window.AICompassRuntime.httpError(response.status,data):
        Error(data.detail || data.error || "HTTP "+response.status));
      return data;
    }
    function failure(error){
      return window.AICompassRuntime&&window.AICompassRuntime.failureInfo?
        window.AICompassRuntime.failureInfo(error):{conflict:false,detail:error&&error.message};
    }
    function label(row) {return row.name+" ("+row.id+")";}
    function build() {
      root.innerHTML=
        '<div class="server-model-toolbar"><div><h2>Test Design</h2>' +
        '<p class="muted small">Reusable engineering challenges · immutable revisions · explicit parent/fork lineage</p></div>' +
        '<button type="button" id="case-refresh">Refresh</button></div>' +
        '<p id="case-status" role="status" class="server-status"></p>' +
        (canWrite ? '<button type="button" id="case-new" disabled>+ New Test Case</button>' : '') +
        '<div id="case-list" class="server-card" style="margin:14px 0"></div>' +
        '<section id="case-editor" class="server-card" hidden></section>' +
        '<section id="case-detail" class="server-card" hidden style="margin-top:14px"></section>';
      el("#case-refresh").addEventListener("click",refresh);
      if(canWrite) el("#case-new").addEventListener("click",function(){ editor(null,"create"); });
      el("#case-list").addEventListener("click",function(event){
        var button=event.target.closest("button[data-case]");
        if(!button)return;
        var row=cases.find(function(x){return x.id===button.dataset.case;});
        if(!row)return;
        if(button.dataset.action==="history") details(row);
        else if(canWrite && button.dataset.action==="edit") editor(row,"edit");
        else if(canWrite && button.dataset.action==="fork") editor(row,"fork");
      });
    }
    function render() {
      var list=el("#case-list");
      if(!list)return;
      list.innerHTML=window.AICompassWorkgroup.renderCases(cases,tasks,{
        mode:"server",canWrite:canWrite,
        emptyText:"No real Server Test Cases yet. Create an engineering task first."
      });
    }

    async function refresh(){
      if(!allowed)return;
      // The editor's Task selector is built from this response. Prevent an
      // early click from opening an incomplete, misleading empty selector.
      if(canWrite&&el("#case-new"))el("#case-new").disabled=true;
      var run=++ticket;
      status("Loading persisted Test Cases and task IDs…");
      try{
        var response=await Promise.all([api("test-cases"),api("tasks")]);
        if(!allowed||run!==ticket)return;
        cases=response[0].results;tasks=response[1].results;
        if(canWrite&&el("#case-new"))el("#case-new").disabled=false;
        render();
        status(cases.length+" Test Case(s), "+tasks.length+" real engineering task(s).");
      }catch(error){
        if(!allowed||run!==ticket)return;
        cases=[];tasks=[];el("#case-list").textContent="Server records are unavailable.";
        if(canWrite&&el("#case-new"))el("#case-new").disabled=true;
        status("Test Design unavailable: "+error.message,true);
      }
    }
    function editor(source,nextMode){
      mode=nextMode;editing=source;
      var container=el("#case-editor"),p=(source&&source.properties)||{};
      if(activeDraft&&activeDraft.dispose)activeDraft.dispose();
      activeDraft=null;
      container.hidden=false;el("#case-detail").hidden=true;
      var name=source?source.name:"",taskId=source?source.task_id:"";
      var taskSelector=mode==="create" ?
        '<label>Engineering task<select name="task_id" required>'+
        '<option value="">Select a registered Server task</option>'+
        tasks.map(function(t){return '<option value="'+escapeHtml(t.id)+'">'+escapeHtml(label(t))+'</option>';}).join("")+
        '</select></label>' :
        '<p><strong>Task:</strong> '+escapeHtml(taskId)+'</p>';
      container.innerHTML=
        '<h3>'+(mode==="fork"?"Fork Test Case":mode==="edit"?"Revise Test Case":"Create Test Case")+'</h3>'+
        (mode==="fork"?'<p>Source '+escapeHtml(source.id)+' · '+escapeHtml(source.case_version)+
          ' · '+escapeHtml(source.revision)+'. Child version is allocated on save.</p>':"")+
        '<form id="case-form"><label>Title<input name="name" required maxlength="160" value="'+escapeHtml(name)+'"></label>'+
        taskSelector+
        window.AICompassWorkgroup.renderCaseFields(p)+
        '<button type="submit">Save '+(mode==="fork"?"fork":mode==="edit"?"revision":"Test Case")+'</button>'+
        '<button type="button" id="case-cancel">Cancel</button></form>';
      if(mode==="create"&&taskId)container.querySelector('select[name="task_id"]').value=taskId;
      el("#case-cancel").addEventListener("click",function(){container.hidden=true;});
      var drafts=window.AICompassDrafts,
          scope=drafts&&drafts.forMode?drafts.forMode("server","test-case-"+mode,{
            id:source?source.id:"new",revision:source?source.revision:"new",
            schema:"test-case-v1",label:source?source.name:"New Test Case",
            guardUnload:true,
            onConflictReload:function(info){reloadLatestCase(source,info);}}):null;
      var draft=scope?drafts.attach(el("#case-form"),scope):null;
      activeDraft=draft;
      el("#case-form").addEventListener("submit",async function(event){
        event.preventDefault();
        if(!allowed||!canWrite)return;
        var form=event.target,button=form.querySelector('button[type="submit"]');
        var props={};
        FIELDS.forEach(function(f){props[f[0]]=form.elements[f[0]].value;});
        var payload={name:form.elements.name.value,properties:props};
        button.disabled=true;
        try{
          var result;
          if(mode==="create"){
            payload.task_id=form.elements.task_id.value;
            result=await api("test-cases","POST",payload);
          }else if(mode==="edit"){
            payload.expected_revision=source.revision;
            result=await api("test-cases/"+encodeURIComponent(source.id),"PATCH",payload);
          }else{
            payload.expected_parent_revision=source.revision;
            result=await api("test-cases/"+encodeURIComponent(source.id)+"/fork","POST",payload);
          }
          if(draft)draft.clear();
          activeDraft=null;
          container.hidden=true;
          await refresh();
          status("Saved "+result.id+" · "+result.case_version+" · "+result.revision);
          var created=cases.find(function(x){return x.id===result.id;});
          if(created) details(created);
        }catch(error){
          var info=failure(error);
          if(draft&&info.conflict){
            var latest=null;
            if(source&&mode==="edit"){
              try{latest=await api("test-cases/"+encodeURIComponent(source.id));}catch(_){}
            }
            draft.conflict({label:source?source.name:"New Test Case",
              baseRevision:source?source.revision:"new",
              latestRevision:latest?latest.revision:"unknown",message:info.detail});
          }
          status("Test Case save refused"+(info.conflict?" (409 revision conflict)":
            info.denied?" (not authorized)":"")+": "+info.detail,true);
        }
        finally{button.disabled=false;}
      });
    }
    /* Reload the newest authoritative Test Case revision; never reapply the draft. */
    async function reloadLatestCase(source,info){
      if(!source)return;
      var run=++ticket;
      try{
        var fresh=await api("test-cases/"+encodeURIComponent(source.id));
        if(!allowed||run!==ticket)return;
        editor(fresh,"edit");
        status("Reloaded Test Case "+fresh.id+" at Server revision "+fresh.revision+
          ". Your unsaved draft stays on this device for manual reapplication.");
      }catch(error){
        if(allowed&&run===ticket)status("Could not reload the latest Test Case: "+
          failure(error).detail,true);
      }
    }
    async function details(row){
      var generation=ticket,target=el("#case-detail");
      target.hidden=false;target.textContent="Loading original revision history…";
      try{
        var responses=await Promise.all([
          api("test-cases/"+encodeURIComponent(row.id)+"/revisions"),
          api("catalog/items/"+encodeURIComponent(row.id)+"/evidence")
        ]);
        if(!allowed||generation!==ticket)return;
        var revisions=responses[0].revisions,evidence=responses[1].results||[];
        target.innerHTML=window.AICompassWorkgroup.renderCaseDetail(row,"server")+
          '<p>Task revision at creation: '+escapeHtml(row.task_revision_at_creation)+
          ' · Immutable fork source revision: '+escapeHtml(row.fork_source_revision_id||"none")+'</p>'+
          window.AICompassWorkgroup.renderRevisionHistory(
            revisions.map(function(x){
              return {revision:x.revision, by:x.created_by, at:x.created_at,
                body:JSON.stringify(x.properties,null,2),
                reason:"Retained Test Case revision"};
            }),{mode:"server",domain:"cases",heading:"Immutable revision history"})+
          '<h4>Original evidence attachments</h4><p>'+escapeHtml(evidence.length)+
          ' attachment(s) linked through the shared evidence store.</p>'+
          '<p class="muted small">Uploads use the existing authorized evidence API; '+
          'each object and version retains its original blob hashes.</p>';
      }catch(error){
        if(allowed&&generation===ticket&&el("#case-detail"))
          el("#case-detail").textContent="History unavailable: "+error.message;
      }
    }
    function setAccess(read,write){
      ++ticket;allowed=!!read;canWrite=!!write&&allowed;
      if(activeDraft&&activeDraft.dispose)activeDraft.dispose();
      activeDraft=null;
      cases=[];tasks=[];editing=null;root.replaceChildren();root.hidden=!allowed;
      if(allowed){build();refresh();}
    }
    root.hidden=true;
    return {setAccess:setAccess,refresh:refresh};
  }
  window.AICompassServerTestCases={mount:mount};
})();
