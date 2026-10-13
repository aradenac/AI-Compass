#!/usr/bin/env node
"use strict";
/* UX-R05: scoped ephemeral drafts — isolation, privacy, step identity, bounded
 * retention, stale-base refusal and first-class 409 conflict retention. */
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");

const memory=new Map();
let denyWrites=false;
const store={get length(){return memory.size;},key(i){return [...memory.keys()][i]||null;},
getItem(k){return memory.get(k)||null;},
setItem(k,v){if(denyWrites)throw new Error("QuotaExceededError");memory.set(k,v);},
removeItem(k){memory.delete(k);}};

function element(tag){
  return {tag,type:"",name:"",value:"",className:"",textContent:"",attributes:{},children:[],events:{},
    hidden:false,removed:false,
    setAttribute(k,v){this.attributes[k]=String(v);},
    getAttribute(k){return Object.prototype.hasOwnProperty.call(this.attributes,k)?this.attributes[k]:null;},
    addEventListener(k,cb){(this.events[k]=this.events[k]||[]).push(cb);},
    removeEventListener(k,cb){this.events[k]=(this.events[k]||[]).filter(x=>x!==cb);},
    appendChild(child){this.children.push(child);return child;},
    insertAdjacentElement(where,el){this.adjacent=el;return el;},
    select(){},remove(){this.removed=true;},
    fire(kind){ (this.events[kind]||[]).slice().forEach(cb=>cb({target:this})); },
    buttons(){return this.children.flatMap(x=>x.tag==="button"?[x]:x.buttons?x.buttons():[]);},
    text(){return this.children.map(x=>x.textContent).join(" ");}};
}
const doc={createElement:element,body:element("body"),
  execCommand(){return false;}};
const unloaded=[];
const win={localStorage:store,location:{origin:"http://localhost:8080"},document:doc,
  addEventListener(kind,cb){if(kind==="beforeunload")unloaded.push(cb);}};
vm.runInNewContext(fs.readFileSync("shared-drafts.js","utf8"),
  {window:win,Date,Array,Object,JSON,String,Number,Error});
const d=win.AICompassDrafts;

const alice={mode:"server",account:"alice",kind:"guide",id:"g1",revision:"r001"};
const bob={...alice,account:"bob"},demo={...alice,mode:"demo"};
assert.notEqual(d.key(alice),d.key(bob),"accounts must not share a draft key");
assert.notEqual(d.key(alice),d.key(demo),"Demo and Server drafts must not mix");
assert.notEqual(d.key(alice),d.key({...alice,id:"g2"}),"objects must not share a draft key");
assert.throws(()=>d.scope({mode:"server",kind:"guide"}),/mode\/account/);
assert.equal(d.forMode("server","guide",{}),null,"no account identity means no draft scope");

function input(name,value,type="text",extra){
  return Object.assign(element("input"),{name,value,type,disabled:false},extra||{});
}
function makeForm(){
  const form=element("form");
  form.elements=[input("name","draft"),input("password","secret","password"),
    input("api_key","secret"),input("notes","x".repeat(3000),"textarea"),
    input("body","ordinary"),input("file","secret","file"),
    input("hidden_internal","secret","hidden"),
    Object.assign(input("staff_note","private"),{dataset:{draftSkip:"1"}}),
    input("internal_rating","7")];
  return form;
}
const options={exclude:["internal_rating"]};
const form=makeForm(),fields=d.fields(form,options);
assert.equal(fields.name,"draft");
assert.equal(fields.body,"ordinary");
for(const gone of ["password","api_key","notes","file","hidden_internal","staff_note",
    "internal_rating"])
  assert(!Object.prototype.hasOwnProperty.call(fields,gone),
    "sensitive or explicitly excluded field must never be cached: "+gone);
assert.equal(d.fields(form).internal_rating,"7","exclusion is configurable per caller");

/* Resume restores fields *and* the remembered step, without any Server write. */
let resumedStep=null;
const handle=d.attach(form,{...alice,...options,step:"planning",steps:["setup","planning"],
  guardUnload:true,onStep(step){resumedStep=step;}});
assert.equal(d.read(alice),null,"attaching alone must not create a draft");
form.listeners=form.events;
assert.equal(unloaded.length,1,"an unsaved-draft unload guard is registered exactly once");
assert.equal(unloaded[0]({preventDefault(){}}),undefined,
  "guard stays silent while the form is untouched");
form.fire("input");
const stored=d.read(alice);
assert.equal(stored.data.name,"draft");
assert.equal(stored.schema,"v1");
assert.equal(stored.step,"planning","active step is part of the draft envelope");
assert.equal(stored.stepLabel,null);
handle.setStep("setup");
assert.equal(d.read(alice).step,"setup","step transitions autosave locally");
handle.setStep("planning");
assert.equal(d.read(bob),null,"another account sees no draft");
assert.equal(d.read(demo),null,"Demo sees no Server draft");
assert.equal(unloaded.length,1,"an unsaved-draft unload guard is registered exactly once");
assert.equal(d.hasUnsaved(),true);
assert.equal(unloaded[0]({preventDefault(){}}),
  "Unsaved local draft on this device is not committed to Server.",
  "the guard warns before leaving with an unsaved local draft");

const resumed=makeForm();
resumed.elements[0].value="authoritative server value";
const resumedHandle=d.attach(resumed,{...alice,...options,step:"planning"});
const resumedBanner=resumedHandle.dom.banner;
assert(resumedBanner.textContent.includes("Unsaved draft on this device"));
assert(resumedBanner.textContent.includes("not saved in Server"));
assert.equal(resumed.elements[0].value,"authoritative server value",
  "a draft is never applied before Resume");
resumedBanner.buttons()[0].fire("click");
assert.equal(resumed.elements[0].value,"draft");
assert(resumedBanner.textContent.includes("restored locally"));

/* Incompatible schema or moved base revision: never silently reapplied. */
const invalid=makeForm();
const invalidHandle=d.attach(invalid,{...alice,schema:"guide-v2"});
const invalidBanner=invalidHandle.dom.banner;
assert(invalidBanner.textContent.includes("NOT applied"));
assert(invalidBanner.textContent.includes("this form changed"));
assert.equal(invalid.elements[0].value,"draft","stale draft must not overwrite the live form");
assert.equal(d.read(alice).revision,"r001","stale draft stays for manual recovery");
assert(invalidBanner.buttons().map(b=>b.textContent).join("/").includes("Copy my unsaved text"));
invalidBanner.buttons()[0].fire("click");
assert(invalidBanner.children.some(x=>x.className==="shared-draft-recovery"),
  "manual recovery text is offered when the clipboard is unavailable");
invalidBanner.buttons()[2].fire("click");
assert.equal(d.read(alice),null,"explicit discard removes the incompatible draft");

/* HTTP 409: unsaved input is preserved, both revisions are named and no merge happens. */
form.fire("input");
const kept=d.read(alice);
assert.equal(kept.data.name,"draft");
handle.conflict({label:"Guide g1",latestRevision:"r004",baseRevision:"r001",
  message:"Revision conflict (revision_conflict)."});
const conflictText=handle.element.textContent;
assert(conflictText.includes("changed since you opened it"),conflictText);
assert(conflictText.includes("r004")&&conflictText.includes("r001"),
  "both the newer Server revision and the local base must be visible");
assert(conflictText.includes("preserved"));
assert(d.read(alice),"the 409 path keeps the local draft");
assert.deepEqual(d.read(alice).data.name,"draft");
assert.equal(d.read(alice).revision,"r001","a conflict never repins the local base");
const labels=handle.element.buttons().map(b=>b.textContent);
for(const expected of ["Reload latest","Review my draft","Copy draft","Discard draft"])
  assert(labels.includes(expected),"missing conflict action: "+expected);
handle.element.buttons()[1].fire("click");
assert(handle.element.children.some(x=>x.className==="shared-draft-recovery"),
  "review shows the unsaved values");
handle.element.buttons()[3].fire("click");
assert.equal(d.read(alice),null,"discarding after a conflict clears only the local draft");
handle.dispose();

/* Bounded retention: expired entries and the oldest overflow are pruned. */
const old={format:d.FORMAT,scope:d.scope({...alice,kind:"old"}),schema:"v1",revision:"r001",
  savedAt:Date.now()-9*86400000,data:{name:"expired"}};
store.setItem(d.key({...alice,kind:"old"}),JSON.stringify(old));
for(let i=0;i<3;i++)store.setItem(d.key({...alice,kind:"k"+i}),JSON.stringify({
  format:d.FORMAT,scope:d.scope({...alice,kind:"k"+i}),schema:"v1",revision:"r001",
  savedAt:Date.now()-(i+1)*1000,data:{name:"k"+i}}));
assert.equal(d.read({...alice,kind:"old"}),null,"expired drafts are dropped");
d.prune(2);
assert.equal(d.read({...alice,kind:"k2"}),null,"oldest drafts are pruned beyond the cap");
assert(d.read({...alice,kind:"k0"}),"the newest drafts are retained");

/* Storage denial is reported instead of silently losing unsaved input. */
denyWrites=true;
const denied=makeForm();
const deniedHandle=d.attach(denied,{...alice,kind:"denied"});
denied.fire("input");
assert(deniedHandle.element.textContent.includes("cannot store drafts"),
  "a browser that refuses storage must say so explicitly");
denyWrites=false;

/* Shared first-class notice for conflicts raised outside a form handle. */
const host=element("section");
let reloaded=false;
d.notice(host,{kind:"matrix-conflict",tone:"error",title:"Conflict: Campaign cmp-one changed",
  message:"Nothing was overwritten or merged.",
  actions:[{label:"Reload latest plan",primary:true,onClick(){reloaded=true;}}]});
const notice_=host.children[0];
assert.equal(notice_.getAttribute("role"),"alert","a conflict notice must be announced");
assert.equal(notice_.getAttribute("data-draft-notice"),"matrix-conflict");
assert(notice_.text().includes("Nothing was overwritten"));
notice_.buttons()[0].fire("click");
assert(reloaded,"the notice exposes an explicit reload action");
assert.equal(d.available(),true);

/* A draft identical to what Server already shows is redundant and not offered. */
const identicalForm=makeForm();
store.setItem(d.key(alice),JSON.stringify({format:d.FORMAT,scope:d.scope(alice),
  schema:"v1",revision:"r001",savedAt:Date.now(),step:"planning",
  data:d.fields(identicalForm,options)}));
const redundantHandle=d.attach(identicalForm,{...alice,...options,step:"planning"});
assert.equal(redundantHandle.hasDraft(),false,
  "a draft identical to the live form is not proposed again");
assert.equal(redundantHandle.dom.banner.textContent,"");

console.log("UX-R05 draft isolation, privacy, step identity, bounded retention, "+
  "stale-base refusal and 409 conflict retention: PASS");
