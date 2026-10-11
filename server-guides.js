/* PLAT-11: Server-only Guides & Charter and reusable inline Setup Guide selector. */
(function () {
  "use strict";
  function request(csrf,path,method,payload) {
    var options={method:method||"GET",credentials:"same-origin",cache:"no-store"};
    if(method&&method!=="GET") {
      options.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
      options.body=JSON.stringify(payload);
    }
    return fetch("/api/v1/guides"+(path||""),options).then(async function(response){
      var body=await response.json().catch(function(){return {};});
      if(!response.ok)throw Error(body.detail||body.error||("HTTP "+response.status));
      return body;
    });
  }
  function formMarkup(escape,guide,heading,known) {
    var properties=guide&&guide.properties||{};
    known=known||[];
    return '<h3>'+escape(heading)+'</h3>'+
      '<form class="guide-form">'+
      window.AICompassWorkgroup.renderGuideFields(guide||{},"server")+
      '<fieldset><legend>Composable recipe (optional)</legend>'+
      '<p class="muted small">Reuse exact guide revisions. For OS/versions and variants, edit the JSON recipe.</p>'+
      '<label>Reusable modules<select name="recipe_modules" multiple size="5">'+
      known.filter(function(g){return !guide||g.id!==guide.id;}).map(function(g){
        return '<option value="'+escape(g.id)+'">'+escape(g.name)+' · '+escape(g.revision)+'</option>';
      }).join("")+'</select></label>'+
      '<button type="button" class="guide-add-modules">Add selected pinned modules</button>'+
      '<label>Recipe (JSON; optional)<textarea name="recipe_spec" rows="8">'+
      escape(properties.recipe?JSON.stringify(properties.recipe,null,2):"")+'</textarea></label></fieldset>'+
      '<button type="submit">Save guide</button> <button type="button" class="guide-cancel">Cancel</button>'+
      '</form>';
  }
  function collect(form) {
    var properties={text:form.elements.text.value,url:form.elements.url.value,
      description:form.elements.description.value};
    if(form.elements.recipe_spec){
      // Explicit null retires a recipe in a new immutable revision; it does
      // not alter any historical guide or already pinned experiment.
      properties.recipe=form.elements.recipe_spec.value.trim()?
        JSON.parse(form.elements.recipe_spec.value):null;
      if(properties.recipe!==null&&(Array.isArray(properties.recipe)||
         typeof properties.recipe!=="object"))
        throw Error("Recipe must be a JSON object");
    }
    return {name:form.elements.name.value,properties:properties};
  }
  function wireRecipeBuilder(node,known) {
    var form=node.querySelector("form"),add=node.querySelector(".guide-add-modules");
    if(!add)return;
    add.addEventListener("click",function(){
      try{
        var spec=form.elements.recipe_spec.value.trim()?
          JSON.parse(form.elements.recipe_spec.value):{modules:[],required:[]};
        if(!spec||!Array.isArray(spec.modules))throw Error("Recipe needs a modules array");
        Array.from(form.elements.recipe_modules.selectedOptions).forEach(function(option){
          var chosen=known.find(function(g){return g.id===option.value;});
          if(chosen&&!spec.modules.some(function(m){return m.id===chosen.id&&m.revision===chosen.revision;}))
            spec.modules.push({id:chosen.id,revision:chosen.revision});
        });
        form.elements.recipe_spec.value=JSON.stringify(spec,null,2);
      }catch(error){add.textContent="Invalid recipe: "+error.message;}
    });
  }
  function mount(root,csrf,escapeHtml) {
    var active=false,write=false,ticket=0,records=[],selected=null;
    function find(s){return root.querySelector(s);}
    function status(message,error) {
      var node=find("#guide-status");
      if(node){node.textContent=message;node.className=error?"server-status server-error":"server-status";}
    }
    function shell() {
      root.innerHTML=
        '<div class="server-model-toolbar"><div><h2>Knowledge & Collaboration · Guides & Charter</h2>'+
        '<p class="muted small">Reusable, revisioned Setup Guides stored in the shared Server database</p></div>'+
        '<button type="button" id="guide-refresh">Refresh</button></div>'+
        '<p id="guide-status" role="status" class="server-status"></p>'+
        '<div style="margin:14px 0"><label>Find existing guide '+
        '<input id="guide-filter" maxlength="160" placeholder="Search by title or ID"></label> '+
        (write?'<button type="button" id="guide-add">+ Create reusable guide</button>':"")+
        '</div><section id="guide-editor" class="server-card" hidden></section>'+
        '<div id="guide-list" class="server-card" style="margin:14px 0"></div>'+
        '<section id="guide-history" class="server-card" hidden></section>'+
        '<section id="guide-inline" class="server-card" style="margin-top:14px"></section>';
      find("#guide-refresh").addEventListener("click",refresh);
      find("#guide-filter").addEventListener("input",render);
      if(write)find("#guide-add").addEventListener("click",function(){edit(null);});
      find("#guide-list").addEventListener("click",function(event){
        var btn=event.target.closest("button[data-guide]");
        if(!btn)return;
        var item=records.find(function(g){return g.id===btn.dataset.guide;});
        if(!item)return;
        if(btn.dataset.action==="inspect")inspect(item);
        else if(btn.dataset.action==="preview")preview(item);
        else if(btn.dataset.action==="edit"&&write)edit(item);
      });
      var panel=find("#guide-inline");
      inline=mountInline(panel,csrf,escapeHtml,function(chosen){
        selected=chosen;
        status("Selected reusable guide "+chosen.id+" · "+chosen.revision+
          " (ready for attachment in a benchmark campaign).");
      },{canWrite:write,heading:"Setup Guide selector · reusable for campaigns"});
    }
    function render() {
      var node=find("#guide-list");if(!node)return;
      var q=(find("#guide-filter").value||"").toLowerCase().trim();
      var visible=records.filter(function(g){
        return !q||g.name.toLowerCase().includes(q)||g.id.toLowerCase().includes(q);
      });
      node.innerHTML=window.AICompassWorkgroup.renderRecords(visible.map(function(g){
        var p=g.properties||{}, actions=[
          {label:"Details / history",attributes:{"data-guide":g.id,"data-action":"inspect"}}
        ];
        if(p.recipe)actions.push({label:"Render recipe",attributes:{"data-guide":g.id,"data-action":"preview"}});
        if(write)actions.push({label:"Revise",attributes:{"data-guide":g.id,"data-action":"edit"}});
        return {id:g.id,title:g.name,revision:g.revision,
          facts:[p.url?(p.text?"URL + text":"URL"):"text procedure"],
          actions:actions};
      }),{domain:"guides",mode:"server",
        emptyText:"No matching Server Setup Guides. No Demo data is imported."});
    }

    async function refresh() {
      if(!active)return;
      var run=++ticket;
      status("Loading Setup Guides from Server…");
      try {
        var data=await request(csrf,"");
        if(!active||run!==ticket)return;
        records=data.results||[];
        render();
        status(records.length+" persistent Setup Guide(s).");
        // The inline selector is independent and refreshes from the same backend.
        if(inline&&inline.refresh)inline.refresh();
      } catch(error) {
        if(!active||run!==ticket)return;
        records=[];
        var list=find("#guide-list");
        if(list)list.textContent="Server Setup Guides unavailable.";
        status(error.message,true);
      }
    }
    var inline=null;
    function edit(item) {
      var node=find("#guide-editor");
      node.hidden=false;
      node.innerHTML=formMarkup(escapeHtml,item,item?"Revise existing Setup Guide":"New reusable Setup Guide",records);
      wireRecipeBuilder(node,records);
      node.querySelector(".guide-cancel").addEventListener("click",function(){node.hidden=true;});
      var draft = window.AICompassDrafts && window.AICompassDraftAccount ?
        window.AICompassDrafts.attach(node.querySelector("form"),{
          mode:"server",account:window.AICompassDraftAccount,kind:"guide",
          id:item?item.id:"new",revision:item?item.revision:"new",schema:"guide-v1"
        }):null;
      node.querySelector("form").addEventListener("submit",async function(event){
        event.preventDefault();
        if(!active||!write)return;
        var button=event.target.querySelector('button[type="submit"]'),payload;
        try{payload=collect(event.target);}
        catch(error){status("Invalid recipe: "+error.message,true);return;}
        button.disabled=true;
        try {
          if(item) {
            payload.expected_revision=item.revision;
            await request(csrf,"/"+encodeURIComponent(item.id),"PATCH",payload);
          } else await request(csrf,"","POST",payload);
          if(!active)return;
          if(draft)draft.clear();
          node.hidden=true;
          await refresh();
        } catch(error){if(draft&&/409|revision_conflict/.test(error.message))draft.conflict();status("Guide not saved: "+error.message,true);}
        finally{button.disabled=false;}
      });
    }
    async function inspect(item) {
      var current=ticket,node=find("#guide-history");
      node.hidden=false;node.textContent="Loading immutable history…";
      try {
        var response=await request(csrf,"/"+encodeURIComponent(item.id)+"/revisions");
        if(!active||current!==ticket)return;
        node=find("#guide-history");
        node.innerHTML=window.AICompassWorkgroup.renderGuideDetail(item,"server")+
          '<h4>Immutable revision history</h4>'+(response.revisions||[]).map(function(r){
            return '<details><summary>'+escapeHtml(r.revision)+' · '+
              escapeHtml(r.created_at)+' · '+escapeHtml(r.created_by)+'</summary>'+
              '<pre style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';
          }).join("");
        var pre=node.querySelectorAll("details pre");
        response.revisions.forEach(function(r,i){pre[i].textContent=JSON.stringify({
          name:r.name,properties:r.properties,schema_version:r.schema_version},null,2);});
      } catch(error) {
        if(active&&current===ticket)find("#guide-history").textContent="History unavailable: "+error.message;
      }
    }
    function preview(item) {
      var node=find("#guide-history");node.hidden=false;
      node.innerHTML='<h3>Composed setup · '+escapeHtml(item.name)+'</h3>'+
        '<p>Supply exact OS, runtime, Model/Provider/Harness versions and settings. Unknown coverage is never assumed.</p>'+
        '<textarea id="guide-render-configuration" rows="6">{}</textarea>'+
        '<button type="button" id="guide-render-now">Render pinned recipe</button>'+
        '<div id="guide-render-result" role="status"></div>';
      find("#guide-render-now").addEventListener("click",async function(){
        var output=find("#guide-render-result"),button=this;button.disabled=true;
        try{
          var configuration=JSON.parse(find("#guide-render-configuration").value);
          if(!configuration||Array.isArray(configuration)||typeof configuration!=="object")
            throw Error("Configuration must be a JSON object");
          var result=await request(csrf,"/render","POST",{
            guide_id:item.id,revision:item.revision,configuration:configuration});
          var markup='<p>'+(result.ready?"All declared modules applicable":"Incomplete or ambiguous recipe")+'</p>'+
            '<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+
            escapeHtml(JSON.stringify(result.missing,null,2))+'</pre>';
          result.sections.forEach(function(section){
            markup+='<details open><summary>'+escapeHtml(section.name)+' · '+escapeHtml(section.revision)+'</summary>'+
              '<pre style="white-space:pre-wrap;overflow-wrap:anywhere">'+escapeHtml(section.text||"")+'</pre>'+
              '<p>'+escapeHtml(section.url||"")+'</p></details>';
          });
          output.innerHTML=markup;
        }catch(error){output.textContent="Unable to render: "+error.message;}
        finally{button.disabled=false;}
      });
    }
    function setAccess(canRead,canWrite) {
      ++ticket;active=!!canRead;write=active&&!!canWrite;records=[];
      if(inline)inline.setAccess(false,false);
      inline=null;
      root.replaceChildren();root.hidden=!active;
      if(active){shell();refresh();}
    }
    root.hidden=true;
    return {setAccess:setAccess,refresh:refresh};
  }
  /* Future campaign workspace calls mountInline with an onSelected callback;
     selection is pure reference metadata until #12 commits campaign links. */
  function mountInline(root,csrf,escapeHtml,onSelected,options) {
    options=options||{};
    var active=true,write=!!options.canWrite,known=[],generation=0;
    function el(s){return root.querySelector(s);}
    function render(){
      root.innerHTML='<h3>'+escapeHtml(options.heading||"Select or create Setup Guide")+'</h3>'+
        '<label>Registered guide <select class="guide-inline-select">'+
        '<option value="">No setup guide selected</option>'+
        known.map(function(g){return '<option value="'+escapeHtml(g.id)+'">'+
          escapeHtml(g.name)+' · '+escapeHtml(g.revision)+'</option>';}).join("")+
        '</select></label> '+
        (write?'<button type="button" class="guide-inline-create">+ Create here</button>':"")+
        '<p class="guide-inline-status muted small"></p>'+
        '<div class="guide-inline-editor" hidden></div>';
      el(".guide-inline-select").addEventListener("change",function(){
        var item=known.find(function(x){return x.id===this.value;},this);
        if(item)onSelected({id:item.id,revision:item.revision,revision_id:item.revision_id,name:item.name});
      });
      if(write)el(".guide-inline-create").addEventListener("click",function(){
        var node=el(".guide-inline-editor");
        node.hidden=false;
        node.innerHTML=formMarkup(escapeHtml,null,"Create a reusable Setup Guide",known);
        wireRecipeBuilder(node,known);
        node.querySelector(".guide-cancel").addEventListener("click",function(){node.hidden=true;});
        node.querySelector("form").addEventListener("submit",async function(event){
          event.preventDefault();
          var button=event.target.querySelector('button[type="submit"]'),payload;
          try{payload=collect(event.target);}
          catch(error){el(".guide-inline-status").textContent="Invalid recipe: "+error.message;return;}
          button.disabled=true;
          try {
            var created=await request(csrf,"","POST",payload);
            if(!active)return;
            await refresh();
            if(!active)return;
            el(".guide-inline-select").value=created.id;
            onSelected({id:created.id,revision:created.revision,revision_id:created.revision_id,name:created.name});
            el(".guide-inline-status").textContent="Created and selected "+created.id;
          } catch(error) {
            if(active)el(".guide-inline-status").textContent="Create refused: "+error.message;
          } finally {button.disabled=false;}
        });
      });
    }
    async function refresh(){
      if(!active)return;
      var current=++generation;
      try{
        var response=await request(csrf,"");
        if(!active||current!==generation)return;
        var previously=el(".guide-inline-select")&&el(".guide-inline-select").value;
        known=response.results||[];render();
        if(previously&&known.some(function(x){return x.id===previously;}))
          el(".guide-inline-select").value=previously;
      }catch(error){if(active&&current===generation&&el(".guide-inline-status"))
        el(".guide-inline-status").textContent="Guide lookup unavailable: "+error.message;}
    }
    function setAccess(read,edit){++generation;active=!!read;write=active&&!!edit;
      root.replaceChildren();root.hidden=!active;if(active){render();refresh();}}
    render();refresh();
    return {refresh:refresh,setAccess:setAccess};
  }
  window.AICompassServerGuides={mount:mount,mountInline:mountInline};
})();
