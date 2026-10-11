/* PLAT-18: Server-only Research Source library and Technology Watch hypothesis workspace.
   All data comes from authenticated PostgreSQL APIs. Never reads or writes Demo storage. */
(function(){
"use strict";
function mount(root,csrf,escapeHtml){
  var active=false,writer=false,reviewer=false,seq=0,sources=[],entries=[];
  function $(selector){return root.querySelector(selector);}
  function esc(value){return escapeHtml(value==null?"":String(value));}
  // One shared loading/read/error presentation in Demo and Server.
  function note(message,error){
    var node=$("#watch-status");
    if(node){
      node.className=error?"server-status server-error":"server-status";
      node.innerHTML=window.AICompassWorkgroup.renderDomainStatus({
        mode:"server",state:error?"error":"ok",message:message==null?"":String(message)});
    }
  }
  async function api(path,method,data){
    var options={method:method||"GET",credentials:"same-origin",cache:"no-store"};
    if(method&&method!=="GET"){
      options.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
      options.body=JSON.stringify(data||{});
    }
    var response=await fetch("/api/v1/"+path,options),body=await response.json().catch(function(){return {};});
    if(!response.ok)throw Error(body.detail||body.error||("HTTP "+response.status));
    return body;
  }
  function option(value,label,selected){
    return '<option value="'+esc(value)+'"'+(selected?' selected':'')+'>'+esc(label)+'</option>';
  }
  function frame(){
    root.hidden=false;
    root.innerHTML='<h2>Technology Watch · Research Sources</h2>'+
      '<p class="muted small">Shared PostgreSQL provenance and immutable revisioned hypotheses. Public readers see reviewed/published material only.</p>'+
      '<p id="watch-status" class="server-status" role="status"></p>'+
      '<div style="display:flex;gap:14px;flex-wrap:wrap"><button type="button" id="watch-refresh">Refresh</button>'+
      (writer?'<button type="button" id="watch-add-source">+ Research Source</button>'+
        '<button type="button" id="watch-add-entry">+ Watch Entry</button>':'')+'</div>'+
      '<label>Filter visible records<input type="search" id="watch-search" placeholder="Title or ID"></label>'+
      '<h3>Research Source library</h3><div id="watch-sources" class="server-card"></div>'+
      '<h3>Technology Watch entries</h3><div id="watch-entries" class="server-card"></div>'+
      '<section id="watch-editor" class="server-card" hidden></section>'+
      '<section id="watch-detail" class="server-card" hidden></section>';
    $("#watch-refresh").addEventListener("click",refresh);
    $("#watch-search").addEventListener("input",render);
    if(writer){
      $("#watch-add-source").addEventListener("click",function(){edit("sources",null);});
      $("#watch-add-entry").addEventListener("click",function(){edit("watch-entries",null);});
    }
    root.addEventListener("click",handle); // One delegated listener per mount.
  }
  async function refresh(){
    if(!active)return;
    var ticket=++seq;
    note("Loading the independent Server knowledge base…");
    try{
      var result=await Promise.all([api("sources"),api("watch-entries")]);
      if(!active||ticket!==seq)return;
      sources=result[0].results||[];entries=result[1].results||[];
      render();
      note(sources.length+" Research Source(s), "+entries.length+" Watch Entry(ies). No Demo data imported.");
    }catch(error){
      if(ticket!==seq||!active)return;
      sources=[];entries=[];render();
      note("Cannot load real Server Technology Watch: "+error.message,true);
    }
  }
  function render(){
    if(!active)return;
    var query=($("#watch-search")&&$("#watch-search").value||"").toLowerCase().trim();
    [["sources",sources],["entries",entries]].forEach(function(pair){
      var node=$("#watch-"+pair[0]);if(!node)return;
      var rows=pair[1].filter(function(r){
        return !query||r.name.toLowerCase().includes(query)||r.id.toLowerCase().includes(query);
      });
      node.innerHTML=window.AICompassWorkgroup.renderRecords(rows.map(function(r){
        var p=r.properties||{},kind=pair[0];
        var actions=[{label:"Details / history",
          attributes:{"data-kind":kind,"data-row":r.id,"data-action":"inspect"}}];
        if(writer)actions.push({label:"Revise",
          attributes:{"data-kind":kind,"data-row":r.id,"data-action":"edit"}});
        if(reviewer)actions.push({label:"Review / publish",
          attributes:{"data-kind":kind,"data-row":r.id,"data-action":"review"}});
        return {id:r.id,title:r.name,revision:r.revision,status:p.review_state||"",
          facts:[p.visibility||"internal"].concat(kind==="entries"?
            [(r.sources||[]).length+" exact source revisions"]:[]),actions:actions};
      }),{domain:pair[0]==="sources"?"research-sources":"watch",mode:"server",
        emptyText:"No matching real Server records."});
    });
  }
  async function handle(event){
    var btn=event.target.closest("button[data-row]");
    if(!btn||!active)return;
    var rows=btn.dataset.kind==="sources"?sources:entries,row=rows.find(function(x){
      return x.id===btn.dataset.row;
    });
    if(!row)return;
    if(btn.dataset.action==="inspect")return inspect(btn.dataset.kind,row);
    if(btn.dataset.action==="edit"&&writer)return edit(btn.dataset.kind,row);
    if(btn.dataset.action==="review"&&reviewer)return review(btn.dataset.kind,row);
  }
  function routeForKind(kind){
    if(kind==="sources")return "sources";
    if(kind==="entries"||kind==="watch-entries")return "watch-entries";
    throw Error("Unsupported Watch record kind");
  }
  function edit(kind,row){
    if(!active||!writer)return;
    var isSource=kind==="sources",p=row&&row.properties||{},area=$("#watch-editor");
    var known=isSource?["claim","citation","url","source_type","confidence","published_on",
      "retrieved_on","limitations","visibility"]:
      ["hypothesis","assumptions","notes","visibility","review_state"];
    var extensions=JSON.stringify(Object.fromEntries(Object.entries(p).filter(function(pair){
      return !known.includes(pair[0]);})),null,2);
    var values=isSource?{
      name:row?row.name:"",claim:p.claim||"",citation:p.citation||"",url:p.url||"",
      source_type:p.source_type||"research",confidence:p.confidence||"unknown",
      published_on:p.published_on||"",retrieved_on:p.retrieved_on||"",
      limitations:p.limitations||"",extensions:extensions
    }:{
      name:row?row.name:"",hypothesis:p.hypothesis||"",assumptions:p.assumptions||"",
      notes:p.notes||"",extensions:extensions,
      sources:(row&&row.sources||[]).map(function(link){return link.id;})
    };
    area.hidden=false;
    area.innerHTML='<h3>'+(row?"Revise ":"Create ")+(isSource?"Research Source":"Watch Entry")+'</h3>'+
      '<form id="watch-form">'+
      window.AICompassWorkgroup.renderDomainFields(
        isSource?window.AICompassWorkgroup.WATCH_SOURCE_FIELDS:
          window.AICompassWorkgroup.WATCH_ENTRY_FIELDS,
        values,"server",{idPrefix:"watch",choices:{sources:sources.map(function(source){
          return [source.id,source.name+" · "+source.revision];})}})+
      '<button type="submit">Save immutable revision</button> <button type="button" id="watch-cancel">Cancel</button></form>';
    $("#watch-cancel").addEventListener("click",function(){area.hidden=true;});
    var draft=window.AICompassDrafts && window.AICompassDraftAccount ?
      window.AICompassDrafts.attach($("#watch-form"),{
        mode:"server",account:window.AICompassDraftAccount,kind:kind,
        id:row?row.id:"new",revision:row?row.revision:"new",schema:"watch-v1"
      }):null;
    $("#watch-form").addEventListener("submit",async function(event){
      event.preventDefault();var form=event.target,button=form.querySelector('[type="submit"]');
      button.disabled=true;
      try{
        var extensions=JSON.parse(form.elements.extensions.value||"{}");
        if(!extensions||Array.isArray(extensions)||typeof extensions!=="object")throw Error("Extensions must be a JSON object");
        var props=isSource?{
          claim:form.elements.claim.value,citation:form.elements.citation.value,
          url:form.elements.url.value,source_type:form.elements.source_type.value,
          confidence:form.elements.confidence.value,
          published_on:form.elements.published_on.value||null,
          retrieved_on:form.elements.retrieved_on.value||null,
          limitations:form.elements.limitations.value
        }:{
          hypothesis:form.elements.hypothesis.value,
          assumptions:form.elements.assumptions.value,
          notes:form.elements.notes.value
        };
        Object.assign(props,extensions);
        var data={name:form.elements.name.value,properties:props};
        if(!isSource){
          var keep=new Map((row&&row.sources||[]).map(function(x){return [x.id,x.revision];}));
          data.sources=Array.from(form.elements.sources.selectedOptions).map(function(x){
            return {id:x.value,revision:keep.get(x.value)||sources.find(function(r){return r.id===x.value;}).revision};
          });
        }
        if(row)data.expected_revision=row.revision;
        await api(routeForKind(kind)+(row?"/"+encodeURIComponent(row.id):""),row?"PATCH":"POST",data);
        if(!active)return;
        if(draft)draft.clear();
        area.hidden=true;await refresh();
        note("Revision safely committed in Server; previous history and exact source pins retained.");
      }catch(error){if(draft&&/409|revision_conflict/.test(error.message))draft.conflict();note("NOT saved: "+error.message,true);}
      finally{button.disabled=false;}
    });
  }
  async function inspect(kind,row){
    var ticket=seq,area=$("#watch-detail");area.hidden=false;area.textContent="Loading history…";
    try{
      var histories=await Promise.all([
        api(routeForKind(kind)+"/"+encodeURIComponent(row.id)+"/revisions"),
        api("catalog/items/"+encodeURIComponent(row.id)+"/evidence")
      ]);
      if(!active||seq!==ticket)return;
      area.innerHTML=window.AICompassWorkgroup.renderKnowledgeDetail(row,{domain:kind==="sources"?"sources":"watch",mode:"server"})+
        '<h4>Immutable history</h4>'+
        (histories[0].revisions||[]).map(function(r){
          return '<details><summary>'+esc(r.revision)+' · '+esc(r.created_at)+
            ' · '+esc(r.created_by)+'</summary><pre style="white-space:pre-wrap;overflow-wrap:anywhere"></pre></details>';
        }).join("")+
        '<h4>Original document attachments</h4>'+
        (histories[1].results||[]).map(function(link){
          return '<p>'+esc(link.original_filename||link.filename)+' · '+esc(link.blob_sha256||link.sha256)+
             ' <a href="/api/v1/evidence/'+encodeURIComponent(link.id)+'/download">Download verified original</a></p>';
        }).join("")+
        (writer?'<label>Attach original PDF / reference file<input type="file" id="watch-upload"></label>'+
          '<button type="button" id="watch-upload-button">Attach original bytes to current revision</button>':'');
      area.querySelectorAll("details pre").forEach(function(pre,index){
        pre.textContent=JSON.stringify(histories[0].revisions[index],null,2);
      });
      if(writer)$("#watch-upload-button").addEventListener("click",async function(){
        var input=$("#watch-upload"),file=input.files&&input.files[0];if(!file)return note("Select a document.",true);
        var form=new FormData();
        form.append("file",file);form.append("revision",row.revision);
        form.append("source","technology-watch:original-document");
        form.append("provenance",JSON.stringify({usage:kind,source_revision:row.revision}));
        var response=await fetch("/api/v1/catalog/items/"+encodeURIComponent(row.id)+
          "/evidence/upload",{method:"POST",credentials:"same-origin",cache:"no-store",
            headers:{"X-CSRFToken":csrf()},body:form});
        var result=await response.json().catch(function(){return {};});
        if(!response.ok)return note("Evidence rejected: "+(result.detail||result.error),true);
        note("Original evidence SHA-256 "+result.sha256+" stored and attributed to "+row.revision+".");
        await inspect(kind,row);
      });
    }catch(error){if(active&&ticket===seq){area.textContent="Unable to read immutable history";note(error.message,true);}}
  }
  function review(kind,row){
    if(!reviewer)return;
    var node=$("#watch-editor"),p=row.properties||{};
    var actions=kind==="sources"?
      (p.visibility==="published"?["unpublish"]:["publish"]):
      p.review_state==="draft"?["submit"]:p.review_state==="under_review"?["approve"]:
      p.visibility==="published"?["unpublish"]:["publish"];
    node.hidden=false;
    node.innerHTML='<h3>Review '+esc(row.name)+' · '+esc(row.revision)+'</h3>'+
      '<p class="muted small">Every review transition creates a new, attributable revision. Linked unpublished sources prevent publication.</p>'+
      actions.map(function(action){
        return '<button type="button" data-review="'+esc(action)+'">'+esc(action)+'</button>';
      }).join("");
    node.querySelectorAll("[data-review]").forEach(function(button){
      button.addEventListener("click",async function(){
        button.disabled=true;
        try{
          await api(routeForKind(kind)+"/"+encodeURIComponent(row.id)+"/actions/"+button.dataset.review,
                    "POST",{expected_revision:row.revision});
          node.hidden=true;await refresh();
        }catch(error){note("Review blocked: "+error.message,true);}
        finally{button.disabled=false;}
      });
    });
  }
  function setAccess(read,write,review){
    active=!!read;writer=active&&!!write;reviewer=active&&!!review;
    ++seq;sources=[];entries=[];
    root.replaceChildren();root.hidden=!active;
    if(active){frame();refresh();}
  }
  root.hidden=true;
  return {setAccess:setAccess,refresh:refresh};
}
window.AICompassServerWatch={mount:mount};
})();
