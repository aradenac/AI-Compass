#!/usr/bin/env node
"use strict";
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict");
const memory=new Map();
const store={get length(){return memory.size;},key(i){return [...memory.keys()][i]||null;},
getItem(k){return memory.get(k)||null;},setItem(k,v){memory.set(k,v);},removeItem(k){memory.delete(k);}};
const doc={createElement(tag){return {tag,type:"",textContent:"",attributes:{},
setAttribute(k,v){this.attributes[k]=v;},addEventListener(k,cb){this["on"+k]=cb;},
appendChild(b){this.button=b;},remove(){this.removed=true;}};}};
const win={localStorage:store,location:{origin:"http://localhost:8080"},document:doc};
vm.runInNewContext(fs.readFileSync("shared-drafts.js","utf8"),{window:win,Date,Array,Object});
const d=win.AICompassDrafts;
const alice={mode:"server",account:"alice",kind:"guide",id:"g1",revision:"r001"};
const bob={...alice,account:"bob"},demo={...alice,mode:"demo"};
assert.notEqual(d.key(alice),d.key(bob));assert.notEqual(d.key(alice),d.key(demo));
assert.throws(()=>d.scope({mode:"server",kind:"guide"}),/mode\/account/);
function input(name,value,type="text"){return {name,value,type,disabled:false};}
function makeForm(){return {elements:[input("name","draft"),input("password","secret","password"),
  input("api_key","secret"),input("notes","x".repeat(3000),"textarea"),
  input("body","ordinary"),input("file","secret","file")],
  listeners:{},insertAdjacentElement(where,el){this.banner=el;},
  addEventListener(k,cb){this.listeners[k]=cb;},
  removeEventListener(k){delete this.listeners[k];}};}
const form=makeForm(),fields=d.fields(form);
assert.equal(fields.name,"draft");assert.equal(fields.body,"ordinary");
assert(!Object.keys(fields).some(k=>["password","api_key","notes","file"].includes(k)));
const handle=d.attach(form,alice);
assert.equal(d.read(alice),null);
form.listeners.input();
assert.equal(d.read(alice).data.name,"draft");
assert.equal(d.read(bob),null);assert.equal(d.read(demo),null);
handle.conflict();assert(d.read(alice),"Conflict retains unsaved changes");
const resumed=makeForm();
d.attach(resumed,alice);
assert(resumed.banner.textContent.includes("Unsaved draft exists"));
const invalid=makeForm();
d.attach(invalid,{...alice,revision:"r002"});
assert(invalid.banner.textContent.includes("different revision"));
assert.equal(d.read(alice).revision,"r001");
handle.clear();assert.equal(d.read(alice),null);
console.log("FUT-04 draft privacy, explicit resume, stale-base refusal and 409 retention: PASS");
