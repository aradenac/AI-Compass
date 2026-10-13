/* FUT-04 / UX-R05: scoped, uncommitted, optional browser drafts; never a Server write.
 *
 * A draft is an ephemeral per-account working copy of *unsaved* form input plus the
 * active step of that form. It is never a business record, never shared between
 * accounts or Demo/Server modes, never promoted to evidence, and never applied
 * automatically: the user must explicitly Resume, copy or Discard it. A draft whose
 * base revision/schema no longer matches, or whose save received HTTP 409, is kept
 * for manual recovery only while the authoritative Server state stays untouched.
 */
(function(root){
"use strict";
/* Key prefix kept stable so pruning can still find entries written by format 1. */
var PREFIX="ai-compass-working-draft:v1:",FORMAT=2,MAX_AGE=7*86400000,MAX_FIELDS=40,MAX_LENGTH=2000,MAX_ENTRIES=24;
var SENSITIVE=/password|token|secret|authorization|api[_-]?key|file|attachment|credential|private[_-]?key|bearer|iban|card[_-]?number/i;
var TYPES=["text","number","search","url","email","tel","date","datetime-local","time","month",
  "textarea","select-one","select-multiple","checkbox","radio"];
function scope(x){
  if(!x||!["server","demo"].includes(x.mode)||!x.account||!x.kind)
    throw Error("Explicit mode/account/form required to isolate drafts");
  return [x.mode,String(x.origin||root.location.origin),x.account,x.kind,x.id||"new"]
    .map(function(v){return encodeURIComponent(String(v));}).join(":");
}
function key(x){return PREFIX+scope(x);}
function safely(action){try{return action();}catch(_){return null;}}
function store(){return root.localStorage;}
function document_(){return root.document;}
/* Storage may be disabled (private mode) or full; never hide the consequence. */
function available(){
  return !!safely(function(){
    var k=PREFIX+"probe";
    store().setItem(k,"1");store().removeItem(k);return true;
  });
}
function expired(entry,x){
  var limit=Number(x&&x.retentionMs)>0?Number(x.retentionMs):MAX_AGE;
  return Date.now()-Number(entry.savedAt||0)>limit;
}
function read(x){
  return safely(function(){
    var v=JSON.parse(store().getItem(key(x))||"null");
    if(!v||v.format!==FORMAT||v.scope!==scope(x)||expired(v,x)){
      store().removeItem(key(x));return null;
    }
    return v;
  });
}
function clear(x){return safely(function(){store().removeItem(key(x));return true;});}
/* Bounded retention: drop expired entries and the oldest drafts beyond the cap. */
function prune(maxEntries){
  return safely(function(){
    var kept=[],cap=Number(maxEntries)>0?Number(maxEntries):MAX_ENTRIES;
    for(var i=store().length-1;i>=0;i--){
      var k=store().key(i);
      if(!k||k.indexOf(PREFIX)!==0)continue;
      if(k===PREFIX+"probe"){store().removeItem(k);continue;}
      var v;
      try{v=JSON.parse(store().getItem(k));}catch(_){}
      if(!v||v.format!==FORMAT||expired(v)){store().removeItem(k);continue;}
      kept.push({key:k,savedAt:Number(v.savedAt||0)});
    }
    kept.sort(function(a,b){return b.savedAt-a.savedAt;});
    kept.slice(cap).forEach(function(item){store().removeItem(item.key);});
    return kept.length;
  });
}
function excluded(el,options){
  if(!el.name||el.disabled)return true;
  if(el.dataset&&el.dataset.draftSkip!==undefined)return true;
  if(el.getAttribute&&el.getAttribute("data-draft-skip")!==null)return true;
  if(el.type==="password"||el.type==="file"||el.type==="hidden")return true;
  if(el.tagName&&String(el.tagName).toLowerCase()==="input"&&el.type==="hidden")return true;
  var name=String(el.name);
  if(SENSITIVE.test(name))return true;
  var extra=options&&options.exclude;
  if(Array.isArray(extra)&&extra.some(function(x){
      return typeof x==="string"?x===name:(x&&x.test?x.test(name):false);
    }))return true;
  if(typeof extra==="function"&&extra(name,el))return true;
  return false;
}
function allowed(el,options){
  if(excluded(el,options))return false;
  return TYPES.includes(el.type||String(el.tagName||"").toLowerCase());
}
function blankEntry(x){
  return {format:FORMAT,scope:scope(x),kind:x.kind,schema:String(x.schema||"v1"),
    revision:String(x.revision||""),label:x.label||null,step:null,
    stepLabel:null,savedAt:Date.now(),data:{}};
}
function fields(form,options){
  var result={},n=0,
    limit=Number(options&&options.maxFields)>0?Number(options.maxFields):MAX_FIELDS,
    maxLength=Number(options&&options.maxLength)>0?Number(options.maxLength):MAX_LENGTH;
  Array.from(form.elements||[]).forEach(function(el){
    if(!allowed(el,options)||n>=limit)return;
    var value=el.type==="checkbox"||el.type==="radio"?!!el.checked:
      el.type==="select-multiple"?Array.from(el.selectedOptions||[]).map(function(o){return o.value;}):el.value;
    if(typeof value==="string"&&value.length>maxLength)return; // avoid sensitive long R&D text
    if(Array.isArray(value)&&value.some(function(v){return v.length>maxLength;}))return;
    result[el.name]=value;n++;
  });
  return result;
}
function apply(form,data,options){
  Array.from(form.elements||[]).forEach(function(el){
    if(!allowed(el,options)||!Object.prototype.hasOwnProperty.call(data||{},el.name))return;
    var v=data[el.name];
    if(el.type==="checkbox"||el.type==="radio")el.checked=!!v;
    else if(el.type==="select-multiple")Array.from(el.options||[]).forEach(function(o){
      o.selected=Array.isArray(v)&&v.includes(o.value);});
    else if(typeof v==="string"||typeof v==="number")el.value=v;
  });
}
function node(tag,text,className){
  var el=document_().createElement(tag);
  el.className=className||"";
  if(text!==undefined&&text!==null)el.textContent=String(text);
  return el;
}
function action(label,onClick,primary){
  var button=node("button",label,"shared-draft-action"+(primary?" primary":""));
  button.type="button";
  button.addEventListener("click",onClick);
  return button;
}
/* Copy unsaved input without any network call; falls back to a selectable block. */
function copyText(text){
  var ok=safely(function(){
    var nav=root.navigator;
    if(nav&&nav.clipboard&&nav.clipboard.writeText){nav.clipboard.writeText(text);return true;}
    var area=document_().createElement("textarea");
    area.value=text;area.setAttribute("aria-hidden","true");
    document_().body.appendChild(area);area.select();
    var legacy=document_().execCommand&&document_().execCommand("copy");
    document_().body.removeChild(area);
    if(!legacy)throw Error("clipboard unavailable");
    return true;
  });
  return !!ok;
}
function flatten(entry){
  var lines=[],data=entry&&entry.data||{};
  Object.keys(data).forEach(function(name){
    var value=data[name];
    lines.push(name+": "+(Array.isArray(value)?value.join(", "):String(value)));
  });
  return lines.join("\n");
}
/* Shared first-class notice: never dismisses, never writes, lists explicit actions. */
function notice(host,options){
  if(!host)return null;
  var opts=options||{};
  var box=node("div","","shared-conflict-notice");
  box.setAttribute("role",opts.tone==="error"?"alert":"status");
  box.setAttribute("data-draft-notice",opts.kind||"conflict");
  if(opts.title)box.appendChild(node("strong",opts.title));
  if(opts.message)box.appendChild(node("p",opts.message));
  var actions=opts.actions||[];
  if(actions.length){
    var row=node("div","","shared-conflict-actions");
    actions.forEach(function(item){row.appendChild(action(item.label,item.onClick,item.primary));});
    box.appendChild(row);
  }
  host.appendChild(box);
  return box;
}
var dirtyCount=0,unloadBound=false;
function guardUnload(){
  if(unloadBound||!root.addEventListener)return;
  unloadBound=true;
  root.addEventListener("beforeunload",function(event){
    if(!dirtyCount)return undefined;
    var message="Unsaved local draft on this device is not committed to Server.";
    if(event&&event.preventDefault)event.preventDefault();
    if(event)event.returnValue=message;
    return message;
  });
}
function attach(form,x){
  if(!form||!x)throw Error("Draft form and scope required");
  prune(x.maxEntries);
  var base=String(x.revision||""),schema=String(x.schema||"v1"),dead=false,dirty=false,
    banner=node("p","","shared-draft-status"),handle=null;
  banner.setAttribute("role","status");
  banner.setAttribute("data-draft-banner",x.kind||"form");
  banner.hidden=true; // an empty status container must not paint a stray box
  form.insertAdjacentElement("beforebegin",banner);
  function render(text,actions){
    banner.textContent=text;
    banner.hidden=!text;
    if(banner.classList&&banner.classList.remove)banner.classList.remove("shared-conflict-notice");
    (actions||[]).forEach(function(item){banner.appendChild(action(item.label,item.onClick,item.primary));});
  }
  function markDirty(value){
    if(dirty===value)return;
    dirty=value;dirtyCount+=value?1:-1;
    if(dirtyCount<0)dirtyCount=0;
    banner.setAttribute("data-draft-dirty",dirty?"true":"false");
  }
  function discard(message){
    markDirty(false);
    clear(x);
    render(message||"Draft discarded. Nothing was sent to Server.");
    if(typeof x.onDiscard==="function")x.onDiscard();
  }
  function save(){
    if(dead)return false;
    var entry=read(x)||blankEntry(x);
    entry.format=FORMAT;entry.kind=x.kind;entry.schema=schema;entry.revision=base;
    entry.label=x.label||entry.label||null;
    entry.step=handle?handle.stepValue||null:null;
    entry.stepLabel=(entry.step&&typeof x.stepLabel==="function")?x.stepLabel(entry.step):entry.stepLabel;
    entry.savedAt=Date.now();
    entry.data=fields(form,x);
    var worked=safely(function(){store().setItem(key(x),JSON.stringify(entry));return true;});
    markDirty(true);
    render(worked?"Unsaved draft on this device (not committed to Server).":
      "This device cannot store drafts (storage unavailable or full). Do not navigate away from unsaved input.");
    return !!worked;
  }
  function offerResume(entry){
    render("Unsaved draft on this device. It is not saved in Server.",[
      {label:"Resume draft",primary:true,onClick:function(){
        apply(form,entry.data,x);
        if(entry.step){handle.setStep(entry.step);if(typeof x.onStep==="function")x.onStep(entry.step);}
        markDirty(true);
        render("Unsaved draft restored locally; nothing was written to Server.");
        if(typeof x.onResume==="function")x.onResume(entry);
      }},
      {label:"Discard",onClick:function(){discard("Draft discarded. Server state was never touched.");}}
    ]);
  }
  function offerStale(entry){
    var reason=entry.schema!==schema?
      "this form changed (draft "+entry.schema+" → "+schema+")":
      "the shared object moved (base "+entry.revision+" → "+base+")";
    render("A local draft exists but was NOT applied because "+reason+
      ". Latest Server data stays as shown. Review, copy or discard the old draft.",[
      {label:"Copy my unsaved text",onClick:function(){
        var text=flatten(entry);
        render(copyText(text)?"Old draft copied to the clipboard. Nothing was applied or sent.":
          "Clipboard unavailable; the old draft text is shown below for manual copying.",[]);
        var block=node("pre","","shared-draft-recovery");
        block.textContent=text;
        banner.appendChild(block);
      }},
      {label:"Review latest form",onClick:function(){
        if(typeof x.onStale==="function")x.onStale(entry,false);
        render("Showing the latest authoritative form. Old draft kept for manual recovery.");
      }},
      {label:"Discard stale draft",onClick:function(){
        discard("Old incompatible draft discarded. Nothing was sent to Server.");
      }}
    ]);
    if(typeof x.onStale==="function")x.onStale(entry,true);
  }
  form.addEventListener("input",save);
  form.addEventListener("change",save);
  handle={
    element:banner,key:key(x),scope:scope(x),stepValue:x.step||null,
    dirty:function(){return dirty;},
    step:function(){return handle.stepValue;},
    setStep:function(step){
      handle.stepValue=step||null;
      if(dirty)save();
      return handle.stepValue;
    },
    /* A successful Server save moves the authoritative revision. The local draft
     * follows it so genuinely unsaved input elsewhere in the same form stays
     * resumable instead of being reported as a stale base. */
    rebase:function(revision){
      if(revision)base=String(revision);
      if(read(x))save();
      return base;
    },
    hasDraft:function(){return !!read(x);},
    snapshot:function(){return save();},
    resume:function(){var entry=read(x);if(entry)offerResume(entry);return entry;},
    /* Re-display the offer after a caller re-rendered the form DOM around it
     * (the draft itself is never applied without an explicit user action). */
    reoffer:function(){
      var entry=read(x);
      if(!entry)return null;
      if(entry.revision!==base||entry.schema!==schema)offerStale(entry);else offerResume(entry);
      return entry;
    },
    discard:discard,
    /* HTTP 409: the shared object changed. Nothing is overwritten or merged. */
    conflict:function(details){
      var info=details||{},entry=read(x)||blankEntry(x);
      markDirty(true);
      var title="Conflict: "+(info.label||x.label||x.kind)+" changed since you opened it";
      var message=(info.message||"")+" Server revision "+(info.latestRevision||"unknown")+
        (info.baseRevision||base?" · your base "+(info.baseRevision||base):"")+
        ". Your unsaved draft is preserved; nothing was overwritten or merged.";
      banner.textContent=title+". "+message;
      banner.hidden=false;
      if(banner.classList&&banner.classList.add)banner.classList.add("shared-conflict-notice");
      var row=node("div","","shared-conflict-actions");
      row.appendChild(action("Reload latest",function(){
        if(typeof x.onConflictReload==="function")x.onConflictReload(info);
        else if(typeof x.onStale==="function")x.onStale(entry,false);
        render(title+". Reloaded Server revision "+(info.latestRevision||"latest")+
          " · your unsaved draft is still here for manual reapplication.",[
          {label:"Copy my unsaved text",onClick:function(){
            render(copyText(flatten(entry))?"Unsaved draft copied to the clipboard.":
              "Clipboard unavailable; unsaved text shown below for manual copying.",[]);
            var block=node("pre","","shared-draft-recovery");
            block.textContent=flatten(entry);banner.appendChild(block);
          }},
          {label:"Discard my draft",onClick:function(){
            discard("Unsaved draft discarded after reviewing latest Server data.");}}
        ]);
      },true));
      row.appendChild(action("Review my draft",function(){
        var block=node("pre","","shared-draft-recovery");
        block.textContent=Object.keys(entry.data||{}).length?flatten(entry):
          "No field values were captured for this draft.";
        banner.appendChild(block);
      }));
      row.appendChild(action("Copy draft",function(){
        render(copyText(flatten(entry))?"Unsaved draft copied to the clipboard. Server state is unchanged.":
          "Clipboard unavailable; unsaved text shown below for manual copying.",[]);
        var block=node("pre","","shared-draft-recovery");
        block.textContent=flatten(entry);banner.appendChild(block);
      }));
      row.appendChild(action("Discard draft",function(){
        discard("Unsaved draft discarded. Server state was never overwritten.");}));
      banner.appendChild(row);
      if(typeof x.onConflict==="function")x.onConflict(info,entry);
    },
    /* Incompatible schema/revision discovered later; never applied automatically. */
    stale:function(){var entry=read(x);if(entry)offerStale(entry);return entry;},
    dispose:function(){
      dead=true;markDirty(false);
      form.removeEventListener("input",save);
      form.removeEventListener("change",save);
      if(banner.remove)banner.remove();
    },
    clear:function(){
      dead=true;markDirty(false);clear(x);
      render("Saved business revision; local draft cleared.");
    },
    synchronize:function(){if(dirty)save();return true;},
    dom:{banner:banner}
  };
  var existing=read(x);
  if(existing&&x.quiet){
    /* Re-attached after a re-render of the same live form: the user's own
     * unsaved values are already on screen, so no Resume prompt is repeated. */
    markDirty(true);
  }else if(existing){
    var currentValues=fields(form,x);
    var identical=Object.keys(currentValues).length>0&&
      JSON.stringify(currentValues)===JSON.stringify(existing.data||{});
    if(existing.revision!==base||existing.schema!==schema)offerStale(existing);
    else if(identical)clear(x); // nothing unsaved relative to what Server already shows
    else offerResume(existing);
  }
  if(x.guardUnload)guardUnload();
  return handle;
}
/* Build a scoped draft descriptor for a runtime. Returns null when no account
 * identity is known yet, so a form never silently inherits another account's keys. */
function forMode(mode,kind,options){
  var o=options||{};
  var account=o.account||root.AICompassDraftAccount;
  if(!account)return null;
  var x={mode:mode,account:account,kind:kind};
  Object.keys(o).forEach(function(k){x[k]=o[k];});
  return x;
}
root.AICompassDrafts={FORMAT:FORMAT,PREFIX:PREFIX,
  scope:scope,key:key,read:read,clear:clear,prune:prune,available:available,
  fields:fields,apply:apply,attach:attach,notice:notice,copyText:copyText,flatten:flatten,
  forMode:forMode,
  hasUnsaved:function(){return dirtyCount>0;}};
})(window);
