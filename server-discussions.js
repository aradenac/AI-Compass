/* PLAT-23: chronological authenticated Discussion UI, independent of seeded Demo. */
(function(){
"use strict";
function mount(root,csrf,escapeHtml){
  var enabled=false,privileged=false,ticket=0,threads=[],selected=null,username="";
  function $(selector){return root.querySelector(selector);}
  function esc(v){return escapeHtml(v==null?"":String(v));}
  function status(message,bad){
    var node=$("#discussion-status");
    if(node){
      node.className=bad?"server-status server-error":"server-status";
      node.innerHTML=window.AICompassWorkgroup.renderDomainStatus({
        mode:"server",state:bad?"error":"ok",message:message==null?"":String(message)});
    }
  }
  async function api(path,method,data){
    var options={method:method||"GET",credentials:"same-origin",cache:"no-store"};
    if(method&&method!=="GET"){
      options.headers={"Content-Type":"application/json","X-CSRFToken":csrf()};
      options.body=JSON.stringify(data||{});
    }
    var response=await fetch("/api/v1/"+path,options);
    var body=await response.json().catch(function(){return {};});
    if(!response.ok)throw Error(body.detail||body.error||"HTTP "+response.status);
    return body;
  }
  function choice(value,label,chosen){
    return '<option value="'+esc(value)+'"'+(chosen?" selected":"")+'>'+esc(label)+'</option>';
  }
  function scopeChoice(current){
    return choice("public","Public to logged-in engineers",current!=="internal")+
           (privileged?choice("internal","Internal workgroup only",current==="internal"):"");
  }
  // Permission-aware choices: "internal" is only offered to privileged roles,
  // in Demo and Server alike. The shared field component renders them.
  function scopeChoices(){
    return [["public","Public to logged-in engineers"]].concat(privileged?
      [["internal","Internal workgroup only"]]:[]);
  }
  function shell(){
    root.innerHTML='<div class="server-model-toolbar"><div>'+
      '<h2>Knowledge & Collaboration · Feedback & Discussions</h2>'+
      '<p class="muted small">Shared chronological conversations; every message has a permanent identity and immutable correction history. Public means visible to signed-in platform readers, not the Internet.</p></div>'+
      '<button type="button" id="discussion-refresh">Refresh</button></div>'+
      '<p class="server-status" role="status" id="discussion-status"></p>'+
      '<button type="button" id="discussion-new">+ New feedback / discussion</button>'+
      '<div id="discussion-compose" class="server-card" hidden></div>'+
      '<h3>Persisted feedback threads</h3><div id="discussion-threads" class="server-card"></div>'+
      '<section id="discussion-conversation" class="server-card" hidden></section>'+
      '<section id="discussion-editor" class="server-card" hidden></section>'+
      '<section id="discussion-history" class="server-card" hidden></section>';
    $("#discussion-refresh").addEventListener("click",refresh);
    $("#discussion-new").addEventListener("click",newThread);
    $("#discussion-threads").addEventListener("click",function(event){
      var button=event.target.closest("button[data-thread]");
      if(button)openThread(button.dataset.thread);
    });
    $("#discussion-conversation").addEventListener("click",function(event){
      var button=event.target.closest("button[data-message]");
      if(!button)return;
      if(button.dataset.action==="reply")composeReply(button.dataset.message);
      if(button.dataset.action==="correct")editMessage(button.dataset.message);
      if(button.dataset.action==="history")history(button.dataset.message);
    });
  }
  function newThread(){
    var panel=$("#discussion-compose");panel.hidden=false;
    panel.innerHTML='<h3>Submit new feedback</h3>'+
      '<form id="discussion-new-form">'+
      window.AICompassWorkgroup.renderDomainFields(
        window.AICompassWorkgroup.FEEDBACK_THREAD_FIELDS,
        {title:"",kind:"feedback",scope:"public",context_id:"",body:""},"server",
        {idPrefix:"discussion-new",choices:{
          kind:[["feedback","feedback"],["question","question"],["idea","idea"],
            ["request","request"],["discussion","discussion"]],
          scope:scopeChoices()}})+
      '<p class="muted small">Only public task, solution and technology catalog references can be attached to discussion threads. The exact catalog revision is pinned at creation.</p>'+
      '<button type="submit">Publish feedback</button><button type="button" id="discussion-new-cancel">Cancel</button>'+
      '</form>';
    $("#discussion-new-cancel").addEventListener("click",function(){panel.hidden=true;});
    $("#discussion-new-form").addEventListener("submit",async function(event){
      event.preventDefault();
      var f=event.target,b=f.querySelector('[type="submit"]');b.disabled=true;
      try{
        var result=await api("discussions","POST",{
          title:f.elements.title.value,body:f.elements.body.value,
          context_id:f.elements.context_id.value.trim()||null,
          properties:{kind:f.elements.kind.value,scope:f.elements.scope.value}
        });
        panel.hidden=true;await refresh();await openThread(result.thread.id);
        status("Persisted "+result.thread.id+"; visible to authorized browsers.");
      }catch(err){status("Feedback not saved: "+err.message,true);}
      finally{b.disabled=false;}
    });
  }
  function renderThreads(){
    var list=$("#discussion-threads");
    list.innerHTML=window.AICompassWorkgroup.renderRecords(threads.map(function(t){
      var p=t.properties||{};
      return {id:t.id,title:t.title,status:p.scope==="internal"?"INTERNAL workgroup":"Public",
        facts:[p.kind,t.created_by,t.message_count+" visible messages"].concat(
          t.context_id?["Linked "+t.context_id]:[]),
        actions:[{label:"Read / reply",attributes:{"data-thread":t.id}}]};
    }),{domain:"feedback",mode:"server",
      emptyText:"No real Server feedback yet; the Demo fixtures are not imported."});
  }
  async function refresh(){
    if(!enabled)return;
    var current=++ticket;
    status("Loading shared Server discussion history…");
    try{
      var results=await Promise.all([api("discussions"),api("auth/account")]);
      if(!enabled||current!==ticket)return;
      threads=results[0].results||[];
      username=results[1].username||"";
      renderThreads();
      if(selected&&threads.some(function(t){return t.id===selected;})){
        await openThread(selected);
      }else{
        selected=null;$("#discussion-conversation").hidden=true;
      }
      status(threads.length+" persisted conversation(s).");
    }catch(err){
      if(!enabled||current!==ticket)return;
      threads=[];renderThreads();$("#discussion-conversation").hidden=true;
      status("Server discussions unavailable; no Demo fallback: "+err.message,true);
    }
  }
  async function openThread(identifier){
    if(!enabled)return;
    var current=++ticket;
    var panel=$("#discussion-conversation");panel.hidden=false;
    panel.textContent="Loading exact chronological messages…";
    try{
      var data=await api("discussions/"+encodeURIComponent(identifier));
      if(!enabled||current!==ticket)return;
      selected=identifier;
      var t=data.thread;
      panel.innerHTML='<h3>'+esc(t.title)+' · '+esc(t.id)+'</h3>'+
        '<p class="muted small">'+(t.properties.scope==="internal"?"INTERNAL":"Public")+
        ' · '+esc(t.created_by)+' · context: '+esc(t.context_id||"none")+'</p>'+
        '<div id="discussion-messages">'+window.AICompassWorkgroup.renderThread(
          (data.messages||[]).map(function(m){
            return {id:m.id,author:m.created_by,at:m.created_at,revision:m.revision,
              parentId:m.parent_id,visibility:m.visibility==="internal"?"internal":"public",
              body:m.body,
              attachments:(m.attachments||[]).map(function(a){
                return {href:a.download,filename:a.filename,sha256:a.sha256};})};}),
          {mode:"server",emptyText:"No message in this Server conversation yet.",
           actions:function(m){
             var isAuthor=m.author===username;
             return [{label:"Reply",attributes:{"data-message":m.id,"data-action":"reply"}}].concat(
               (isAuthor||privileged)?[{label:"Correct / change visibility",
                 attributes:{"data-message":m.id,"data-action":"correct"}}]:[]).concat(
               [{label:"Correction history",
                 attributes:{"data-message":m.id,"data-action":"history"}}]);}})+'</div>'+
        '<div id="discussion-attachments">'+(data.messages||[]).map(function(m){
          var isAuthor=m.created_by===username;
          return (isAuthor||privileged)?'<form data-attachment="'+esc(m.id)+
            '" style="display:inline-block;margin:4px 8px 4px 0">'+
            '<input name="file" type="file" accept=".pdf,.txt,.md,.csv,.json,.png,.jpg,.jpeg,.webp,.zip" required>'+
            '<button type="submit">Attach original to '+esc(m.id)+'</button></form>':"";
        }).join("")+'</div>'+
        '<div id="discussion-reply-editor"></div>';
      panel.querySelectorAll("form[data-attachment]").forEach(function(form){
        form.addEventListener("submit",function(event){event.preventDefault();upload(form);});
      });
      status("Loaded "+data.messages.length+" permitted messages in chronological order.");
    }catch(err){
      if(!enabled||current!==ticket)return;
      panel.hidden=true;status("Cannot open discussion: "+err.message,true);
    }
  }
  function composeReply(parent){
    if(!selected)return;
    var t=threads.find(function(x){return x.id===selected;});
    var area=$("#discussion-reply-editor");
    area.innerHTML='<h4>Reply '+(parent?"to "+esc(parent):"to conversation")+'</h4>'+
      '<form id="discussion-reply-form">'+
      window.AICompassWorkgroup.renderDomainFields(
        window.AICompassWorkgroup.FEEDBACK_REPLY_FIELDS,
        {visibility:(t&&t.properties.scope==="internal"?"internal":"public"),body:""},"server",
        {idPrefix:"discussion-reply",choices:{visibility:scopeChoices()}})+
      '<button type="submit">Persist reply</button></form>';
    $("#discussion-reply-form").addEventListener("submit",async function(event){
      event.preventDefault();var f=event.target,button=f.querySelector('[type="submit"]');button.disabled=true;
      try{
        await api("discussions/"+encodeURIComponent(selected)+"/messages","POST",{
          body:f.elements.body.value,visibility:f.elements.visibility.value,
          parent_id:parent||null,
        });
        await openThread(selected);
      }catch(err){status("Reply rejected: "+err.message,true);button.disabled=false;}
    });
  }
  async function editMessage(identifier){
    var area=$("#discussion-editor");area.hidden=false;
    area.textContent="Loading latest message revision…";
    try{
      var message=await api("discussions/messages/"+encodeURIComponent(identifier));
      var visibility=message.visibility;
      area.innerHTML='<h3>Correct original message '+esc(message.id)+'</h3>'+
        '<form id="discussion-correction-form">'+
        '<label>Message<textarea name="body" required maxlength="16000" rows="5">'+esc(message.body)+'</textarea></label>'+
        (privileged?'<label>Visibility<select name="visibility">'+
          scopeChoice(visibility)+'</select></label>':'')+
        '<label>Reason for correction / moderation<textarea name="edit_reason" required maxlength="4000"></textarea></label>'+
        '<p class="muted small">Original wording, visibility, editor and timestamps remain in immutable history. Internal text is never returned by the public history API.</p>'+
        '<button type="submit">Append correction revision</button>'+
        '<button type="button" id="discussion-correction-cancel">Cancel</button></form>';
      $("#discussion-correction-cancel").addEventListener("click",function(){area.hidden=true;});
      $("#discussion-correction-form").addEventListener("submit",async function(event){
        event.preventDefault();var f=event.target,button=f.querySelector('[type="submit"]');button.disabled=true;
        try{
          await api("discussions/messages/"+encodeURIComponent(identifier),"PATCH",{
            expected_revision:message.revision,
            properties:{body:f.elements.body.value,edit_reason:f.elements.edit_reason.value,
              visibility:privileged?f.elements.visibility.value:visibility},
          });
          area.hidden=true;await openThread(selected);
        }catch(err){status("Correction rejected: "+err.message,true);button.disabled=false;}
      });
    }catch(err){area.hidden=true;status("Cannot edit message: "+err.message,true);}
  }
  async function history(identifier){
    var area=$("#discussion-history");area.hidden=false;
    area.textContent="Loading retained revision history…";
    try{
      var data=await api("discussions/messages/"+encodeURIComponent(identifier)+"/revisions");
      area.innerHTML='<h3>Immutable message history · '+esc(identifier)+'</h3>'+
        (data.revisions||[]).map(function(r){
          return '<details><summary>'+esc(r.revision)+' · '+esc(r.revision_by)+
            ' · '+esc(r.revision_at)+' · '+esc(r.visibility)+'</summary>'+
            '<p style="white-space:pre-wrap;overflow-wrap:anywhere">'+esc(r.body)+'</p>'+
            '<p>Reason: '+esc(r.edit_reason||"Original message")+'</p></details>';
        }).join("");
    }catch(err){area.hidden=true;status("History unavailable: "+err.message,true);}
  }
  async function upload(form){
    var id=form.dataset.attachment,button=form.querySelector("button");
    button.disabled=true;
    try{
      var latest=await api("discussions/messages/"+encodeURIComponent(id));
      var file=form.elements.file.files[0];
      if(!file)throw Error("Choose a file");
      var body=new FormData();body.append("file",file);
      body.append("expected_revision",latest.revision);
      body.append("source","feedback-original");
      var response=await fetch("/api/v1/discussions/messages/"+encodeURIComponent(id)+
        "/attachments",{method:"POST",body:body,credentials:"same-origin",cache:"no-store",
                        headers:{"X-CSRFToken":csrf()}});
      var detail=await response.json().catch(function(){return {};});
      if(!response.ok)throw Error(detail.detail||detail.error||"Upload error");
      await openThread(selected);
      status("Stored original attachment with SHA-256 "+detail.sha256);
    }catch(err){status("Attachment refused: "+err.message,true);}
    finally{button.disabled=false;}
  }
  function setAccess(read,write,review){
    ++ticket;enabled=!!read;privileged=enabled&&(!!write||!!review);
    selected=null;threads=[];username="";
    root.replaceChildren();root.hidden=!enabled;
    if(enabled){shell();refresh();}
  }
  root.hidden=true;
  return {setAccess:setAccess,refresh:refresh};
}
window.AICompassServerDiscussions={mount:mount};
})();
