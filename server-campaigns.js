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
    var catalog={model:[],provider:[],harness:[]};
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
        '<section id="campaign-detail" class="server-card" hidden></section>';
      el("#campaign-refresh").addEventListener("click",refresh);
      if(canWrite)el("#campaign-add").addEventListener("click",function(){editor(null);});
      el("#campaign-list").addEventListener("click",function(e){
        var btn=e.target.closest("button[data-id]");
        if(!btn)return;
        var row=campaigns.find(function(c){return c.id===btn.dataset.id;});
        if(!row)return;
        if(btn.dataset.action==="history")history(row);
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
          ' · '+x.test_case_ids.length+' Test Case(s)</p>'+
          '<p>'+esc(x.properties.objective)+'</p>'+
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
          api("guides"),api("catalog/model"),api("catalog/provider"),api("catalog/harness")
        ]);
        if(!allowed||run!==ticket)return;
        campaigns=responses[0].results; methods=responses[1].results;
        tasks=responses[2].results; cases=responses[3].results; guides=responses[4].results;
        ["model","provider","harness"].forEach(function(k,i){catalog[k]=responses[i+5].results;});
        render();status(campaigns.length+" campaign(s) persisted in Server. Pipeline shows plans, not measured results.");
      }catch(error){
        if(!allowed||run!==ticket)return;
        campaigns=[];el("#campaign-list").textContent="Campaigns unavailable; no Demo fallback.";
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
        '<div id="campaign-solution-row">'+["model","provider","harness"].map(function(k){
          return '<label>Fixed '+esc(k)+'<select name="'+k+'">'+options(catalog[k],
            source?(source.component_ids||{})[k]:null,true)+'</select></label>';
        }).join("")+'</div>'+
        '<label>Reusable Setup Guide<select name="guide_id">'+options(guides,source?source.guide_id:null,true)+'</select></label>'+
        '<div><button type="button" id="campaign-inline-guide">+ Create reusable Setup Guide</button></div>'+
        '<div id="campaign-guide-form" hidden><label>Guide title<input name="guide_name" maxlength="160"></label>'+
        '<label>Setup procedure text<textarea name="guide_text"></textarea></label>'+
        '<label>HTTP(S) guide URL<input name="guide_url" maxlength="2048"></label>'+
        '<button type="button" id="campaign-save-guide">Save Guide to knowledge base</button></div>'+
        '<label>Linked Test Cases (Ctrl/Command to select multiple)'+
        '<select name="test_case_ids" multiple size="6">'+cases.map(function(c){
          return '<option value="'+esc(c.id)+'"'+(source&&source.test_case_ids.includes(c.id)?" selected":"")+
            '>'+esc(c.name)+' ('+esc(c.task_id)+')</option>';
        }).join("")+'</select></label>'+
        '<label>Fixed configuration and parameters (JSON object)<textarea name="configuration">'+
          esc(JSON.stringify(source?source.configuration:{},null,2))+'</textarea></label>'+
        '<button type="submit">Save '+(source?"new revision":"campaign")+'</button>'+
        '<button type="button" id="campaign-cancel">Cancel</button></form>';
      var form=el("#campaign-form");
      function syncMode(){
        var chosen=form.elements.mode.value;
        el("#campaign-task-row").hidden=chosen!=="task_centred";
        el("#campaign-solution-row").hidden=chosen!=="solution_centred";
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
      el("#campaign-inline-guide").addEventListener("click",function(){
        el("#campaign-guide-form").hidden=false;
      });
      el("#campaign-save-guide").addEventListener("click",async function(){
        var button=this;button.disabled=true;
        try{
          var props={},txt=form.elements.guide_text.value.trim(),url=form.elements.guide_url.value.trim();
          if(txt)props.text=txt;if(url)props.url=url;
          var saved=await api("guides","POST",{name:form.elements.guide_name.value,properties:props});
          guides.push(saved);
          form.elements.guide_id.innerHTML=options(guides,saved.id,true);
          el("#campaign-guide-form").hidden=true;
          status("Guide "+saved.id+" saved; campaign will pin its current revision when saved.");
        }catch(error){status("Guide creation refused: "+error.message,true);}
        finally{button.disabled=false;}
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
            configuration:config
          };
          if(form.elements.owner.value.trim())payload.owner=form.elements.owner.value.trim();
          if(selectedMode==="task_centred")payload.task_id=form.elements.task_id.value;
          else payload.component_ids=Object.fromEntries(["model","provider","harness"].map(function(k){
            return [k,form.elements[k].value];}));
          if(source)payload.expected_revision=source.revision;
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
