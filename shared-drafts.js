/* FUT-04: scoped, uncommitted, optional browser drafts; never a Server write. */
(function(root){
"use strict";
var PREFIX="ai-compass-working-draft:v1:",FORMAT=1,MAX_AGE=7*86400000,MAX_FIELDS=40,MAX_LENGTH=2000;
var OMIT=/password|token|secret|authorization|api[_-]?key|file|attachment|credential|private[_-]?key|bearer/i;
function scope(x){
  if(!x||!["server","demo"].includes(x.mode)||!x.account||!x.kind)
    throw Error("Explicit mode/account/form required to isolate drafts");
  return [x.mode,String(x.origin||root.location.origin),x.account,x.kind,x.id||"new"]
    .map(function(v){return encodeURIComponent(String(v));}).join(":");
}
function key(x){return PREFIX+scope(x);}
function safely(action){try{return action();}catch(_){return null;}}
function store(){return root.localStorage;}
function read(x){
  return safely(function(){
    var v=JSON.parse(store().getItem(key(x))||"null");
    if(!v||v.format!==FORMAT||v.scope!==scope(x)||Date.now()-v.savedAt>MAX_AGE){
      store().removeItem(key(x));return null;
    }
    return v;
  });
}
function clear(x){return safely(function(){store().removeItem(key(x));return true;});}
function prune(){
  safely(function(){
    for(var i=store().length-1;i>=0;i--){
      var k=store().key(i);
      if(!k||!k.startsWith(PREFIX))continue;
      var v;
      try{v=JSON.parse(store().getItem(k));}catch(_){}
      if(!v||v.format!==FORMAT||Date.now()-v.savedAt>MAX_AGE)store().removeItem(k);
    }
  });
}
function allowed(el){
  return !!(el.name&&!OMIT.test(el.name)&&
    el.type!=="password"&&el.type!=="file"&&el.type!=="hidden"&&
    !el.disabled&&["text","number","search","url","date","textarea","select-one","select-multiple","checkbox","radio"].includes(el.type||el.tagName.toLowerCase()));
}
function fields(form){
  var result={},n=0;
  Array.from(form.elements||[]).forEach(function(el){
    if(!allowed(el)||n>=MAX_FIELDS)return;
    var value=el.type==="checkbox"||el.type==="radio"?!!el.checked:
      el.type==="select-multiple"?Array.from(el.selectedOptions).map(function(o){return o.value;}):el.value;
    if(typeof value==="string"&&value.length>MAX_LENGTH)return; // avoid sensitive long R&D text
    if(Array.isArray(value)&&value.some(function(v){return v.length>MAX_LENGTH}))return;
    result[el.name]=value;n++;
  });
  return result;
}
function apply(form,data){
  Array.from(form.elements||[]).forEach(function(el){
    if(!allowed(el)||!Object.prototype.hasOwnProperty.call(data,el.name))return;
    var v=data[el.name];
    if(el.type==="checkbox"||el.type==="radio")el.checked=!!v;
    else if(el.type==="select-multiple")Array.from(el.options).forEach(function(o){o.selected=Array.isArray(v)&&v.includes(o.value);});
    else if(typeof v==="string"||typeof v==="number")el.value=v;
  });
}
function attach(form,x){
  if(!form||!x)throw Error("Draft form and scope required");
  prune();
  var base=String(x.revision||""),schema=String(x.schema||"v1"),dead=false;
  var banner=root.document.createElement("p");banner.className="shared-draft-status";
  banner.setAttribute("role","status");form.insertAdjacentElement("beforebegin",banner);
  var existing=read(x);
  if(existing){
    if(existing.revision!==base||existing.schema!==schema){
      banner.textContent="Unsaved draft from a different revision/schema. NOT applied. Review latest, copy manually or discard.";
      var discard=root.document.createElement("button");discard.type="button";discard.textContent="Discard incompatible draft";
      discard.addEventListener("click",function(){clear(x);banner.textContent="Old draft discarded.";discard.remove();});
      banner.appendChild(discard);
    }else{
      banner.textContent="Unsaved draft exists on this device. It is not saved in Server.";
      var resume=root.document.createElement("button");resume.type="button";resume.textContent="Resume draft";
      var drop=root.document.createElement("button");drop.type="button";drop.textContent="Discard";
      resume.addEventListener("click",function(){apply(form,existing.data);banner.textContent="Unsaved draft restored locally.";});
      drop.addEventListener("click",function(){clear(x);banner.textContent="Draft discarded.";});
      banner.appendChild(resume);banner.appendChild(drop);
    }
  }
  function save(){
    if(dead)return;
    var data=fields(form);
    var entry={format:FORMAT,scope:scope(x),schema:schema,revision:base,
      savedAt:Date.now(),step:x.step||null,data:data};
    var worked=safely(function(){store().setItem(key(x),JSON.stringify(entry));return true;});
    banner.textContent=worked?"Unsaved draft on this device (not committed).":
      "Draft could not be saved on this device; do not navigate away.";
  }
  form.addEventListener("input",save);form.addEventListener("change",save);
  return {clear:function(){dead=true;clear(x);banner.textContent="Saved business revision; local draft cleared.";},
    conflict:function(){banner.textContent="409: authoritative revision changed. Unsaved local draft preserved; reload and reapply manually.";},
    dispose:function(){dead=true;form.removeEventListener("input",save);form.removeEventListener("change",save);},
    snapshot:save};
}
root.AICompassDrafts={scope:scope,key:key,read:read,clear:clear,prune:prune,
  fields:fields,attach:attach};
})(window);
