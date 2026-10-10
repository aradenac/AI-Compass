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
    var allowed=false, canWrite=false, ticket=0, cases=[], tasks=[], editing=null, mode="create";
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
      if(!response.ok) throw Error(data.detail || data.error || "HTTP "+response.status);
      return data;
    }
    function label(row) {return row.name+" ("+row.id+")";}
    function build() {
      root.innerHTML=
        '<div class="server-model-toolbar"><div><h2>Test Design</h2>' +
        '<p class="muted small">Reusable engineering challenges · immutable revisions · explicit parent/fork lineage</p></div>' +
        '<button type="button" id="case-refresh">Refresh</button></div>' +
        '<p id="case-status" role="status" class="server-status"></p>' +
        (canWrite ? '<button type="button" id="case-new">+ New Test Case</button>' : '') +
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
      if(!cases.length){list.textContent="No real Server Test Cases yet. Create an engineering task first.";return;}
      var taskLabels=new Map(tasks.map(function(t){return [t.id,t.name];}));
      var byTask=new Map();
      cases.forEach(function(x){if(!byTask.has(x.task_id))byTask.set(x.task_id,[]);byTask.get(x.task_id).push(x);});
      var html="";
      byTask.forEach(function(group,taskId){
        var lookup=new Map(group.map(function(c){return [c.id,c];}));
        group.sort(function(a,b){return a.case_version.localeCompare(b.case_version,undefined,{numeric:true});});
        var ordered=[],seen=new Set();
        function walk(c,depth){
          if(seen.has(c.id))return;
          seen.add(c.id);ordered.push([c,depth]);
          group.filter(function(f){return f.fork_parent_id===c.id;}).forEach(function(child){walk(child,depth+1);});
        }
        group.filter(function(c){return !c.fork_parent_id || !lookup.has(c.fork_parent_id);}).forEach(function(c){walk(c,0);});
        group.forEach(function(c){walk(c,0);});
        html+='<h3>'+escapeHtml(taskLabels.get(taskId)||taskId)+'</h3>';
        html+=ordered.map(function(pair){
          var c=pair[0],depth=pair[1];
          return '<div class="list-row" style="padding:12px 0 12px '+Math.min(depth*24,144)+'px;border-bottom:1px solid #edf1f6">' +
            '<strong>'+escapeHtml(c.case_version)+' · '+escapeHtml(c.name)+'</strong>' +
            '<div class="muted small">'+escapeHtml(c.id)+' · '+escapeHtml(c.revision) +
            (c.fork_parent_id?' · fork of '+escapeHtml(c.fork_parent_id):' · original root')+'</div>' +
            '<button type="button" data-case="'+escapeHtml(c.id)+'" data-action="history">Details / history</button>' +
            (canWrite?'<button type="button" data-case="'+escapeHtml(c.id)+'" data-action="edit">Edit</button>'+
            '<button type="button" data-case="'+escapeHtml(c.id)+'" data-action="fork">Fork</button>':'')+
            '</div>';
        }).join("");
      });
      list.innerHTML=html;
    }
    async function refresh(){
      if(!allowed)return;
      var run=++ticket;
      status("Loading persisted Test Cases and task IDs…");
      try{
        var response=await Promise.all([api("test-cases"),api("tasks")]);
        if(!allowed||run!==ticket)return;
        cases=response[0].results;tasks=response[1].results;
        render();
        status(cases.length+" Test Case(s), "+tasks.length+" real engineering task(s).");
      }catch(error){
        if(!allowed||run!==ticket)return;
        cases=[];tasks=[];el("#case-list").textContent="Server records are unavailable.";
        status("Test Design unavailable: "+error.message,true);
      }
    }
    function editor(source,nextMode){
      mode=nextMode;editing=source;
      var container=el("#case-editor"),p=(source&&source.properties)||{};
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
        FIELDS.map(function(f){return '<label>'+escapeHtml(f[1])+
          '<textarea name="'+escapeHtml(f[0])+'" rows="2">'+escapeHtml(p[f[0]]||"")+'</textarea></label>';}).join("")+
        '<button type="submit">Save '+(mode==="fork"?"fork":mode==="edit"?"revision":"Test Case")+'</button>'+
        '<button type="button" id="case-cancel">Cancel</button></form>';
      if(mode==="create"&&taskId)container.querySelector('select[name="task_id"]').value=taskId;
      el("#case-cancel").addEventListener("click",function(){container.hidden=true;});
      var draft=window.AICompassDrafts && window.AICompassDraftAccount ?
        window.AICompassDrafts.attach(el("#case-form"),{
          mode:"server",account:window.AICompassDraftAccount,kind:"test-case-"+mode,
          id:source?source.id:"new",revision:source?source.revision:"new",schema:"test-case-v1"
        }):null;
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
          container.hidden=true;
          await refresh();
          status("Saved "+result.id+" · "+result.case_version+" · "+result.revision);
          var created=cases.find(function(x){return x.id===result.id;});
          if(created) details(created);
        }catch(error){if(draft&&/409|revision_conflict/.test(error.message))draft.conflict();status("Test Case save refused: "+error.message,true);}
        finally{button.disabled=false;}
      });
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
        target.innerHTML=
          '<h3>'+escapeHtml(row.name)+' · '+escapeHtml(row.case_version)+'</h3>'+
          '<p>Task '+escapeHtml(row.task_id)+' · created against task revision '+
          escapeHtml(row.task_revision_at_creation)+'</p>'+
          '<p>Fork parent: '+escapeHtml(row.fork_parent_id||"none (root)")+
          ' · immutable source revision: '+escapeHtml(row.fork_source_revision_id||"none")+'</p>'+
          '<h4>Immutable revision history</h4>'+
          revisions.map(function(x){return '<details><summary>'+escapeHtml(x.revision)+
            ' · '+escapeHtml(x.created_by)+' · '+escapeHtml(x.created_at)+'</summary><pre '+
            'style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';}).join("")+
          '<h4>Original evidence attachments</h4><p>'+escapeHtml(evidence.length)+
          ' attachment(s) linked through the shared evidence store.</p>'+
          '<p class="muted small">Uploads use the existing authorized evidence API; '+
          'each object and version retains its original blob hashes.</p>';
        var blocks=target.querySelectorAll("details pre");
        revisions.forEach(function(x,i){blocks[i].textContent=JSON.stringify(x.properties,null,2);});
      }catch(error){
        if(allowed&&generation===ticket&&el("#case-detail"))
          el("#case-detail").textContent="History unavailable: "+error.message;
      }
    }
    function setAccess(read,write){
      ++ticket;allowed=!!read;canWrite=!!write&&allowed;
      cases=[];tasks=[];editing=null;root.replaceChildren();root.hidden=!allowed;
      if(allowed){build();refresh();}
    }
    root.hidden=true;
    return {setAccess:setAccess,refresh:refresh};
  }
  window.AICompassServerTestCases={mount:mount};
})();
