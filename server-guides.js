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
  function formMarkup(escape,guide,heading) {
    var properties=guide&&guide.properties||{};
    return '<h3>'+escape(heading)+'</h3>'+
      '<form class="guide-form">'+
      '<label>Guide title <input name="name" maxlength="160" required value="'+
      escape(guide&&guide.name||"")+'"></label>'+
      '<label>Procedure text (optional if URL present) <textarea name="text" rows="6" maxlength="32768">'+
      escape(properties.text||"")+'</textarea></label>'+
      '<label>Setup URL (optional if text present) <input name="url" type="url" maxlength="2048" value="'+
      escape(properties.url||"")+'" placeholder="https://example.com/setup"></label>'+
      '<label>Notes / description <textarea name="description" rows="2" maxlength="4000">'+
      escape(properties.description||"")+'</textarea></label>'+
      '<button type="submit">Save guide</button> <button type="button" class="guide-cancel">Cancel</button>'+
      '</form>';
  }
  function collect(form) {
    return {name:form.elements.name.value,
      properties:{text:form.elements.text.value,url:form.elements.url.value,
        description:form.elements.description.value}};
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
      var node=find("#guide-list");
      if(!node)return;
      var q=(find("#guide-filter").value||"").toLowerCase().trim();
      var visible=records.filter(function(g){return !q||g.name.toLowerCase().includes(q)||g.id.toLowerCase().includes(q);});
      if(!visible.length){node.textContent="No matching Server Setup Guides. No Demo data is imported.";return;}
      node.innerHTML=visible.map(function(g){
        var p=g.properties||{};
        return '<div class="list-row" style="padding:12px 0;border-bottom:1px solid #edf1f6">'+
          '<strong>'+escapeHtml(g.name)+'</strong>'+
          '<div class="muted small">'+escapeHtml(g.id)+' · '+escapeHtml(g.revision)+
          ' · '+escapeHtml(p.url?"URL"+(p.text?" + text":""):"text procedure")+'</div>'+
          '<button type="button" data-guide="'+escapeHtml(g.id)+'" data-action="inspect">Details / history</button> '+
          (write?'<button type="button" data-guide="'+escapeHtml(g.id)+'" data-action="edit">Revise</button>':"")+
          '</div>';
      }).join("");
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
      node.innerHTML=formMarkup(escapeHtml,item,item?"Revise existing Setup Guide":"New reusable Setup Guide");
      node.querySelector(".guide-cancel").addEventListener("click",function(){node.hidden=true;});
      node.querySelector("form").addEventListener("submit",async function(event){
        event.preventDefault();
        if(!active||!write)return;
        var button=event.target.querySelector('button[type="submit"]'),payload=collect(event.target);
        button.disabled=true;
        try {
          if(item) {
            payload.expected_revision=item.revision;
            await request(csrf,"/"+encodeURIComponent(item.id),"PATCH",payload);
          } else await request(csrf,"","POST",payload);
          if(!active)return;
          node.hidden=true;
          await refresh();
        } catch(error){status("Guide not saved: "+error.message,true);}
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
        node.innerHTML='<h3>'+escapeHtml(item.name)+' · '+escapeHtml(item.id)+'</h3>'+
          (response.revisions||[]).map(function(r){
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
        node.innerHTML=formMarkup(escapeHtml,null,"Create a reusable Setup Guide");
        node.querySelector(".guide-cancel").addEventListener("click",function(){node.hidden=true;});
        node.querySelector("form").addEventListener("submit",async function(event){
          event.preventDefault();
          var payload=collect(event.target),button=event.target.querySelector('button[type="submit"]');
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
