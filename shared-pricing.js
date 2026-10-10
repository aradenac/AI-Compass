/* FUT-05: one pricing and enterprise-access editor for fictional Demo and real Server.
 * Adapter is explicitly chosen by bootstrap; never import/cross-fallback.
 */
(function(root){
"use strict";
var KINDS=["model","provider","harness","framework"];
var STATUSES=["unknown","accessible","restricted","not_accessible"];
function esc(value){return String(value==null?"":value).replace(/[&<>"']/g,
  c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function sample(component){
 return {component_id:component||"",billing_owner:"",currency:"EUR",
   source:"",checked_on:new Date().toISOString().slice(0,10),status:"unknown",
   effective_from:null,effective_to:null,lines:[{
     charge_id:"vendor:charge-identity",family:"token",charge_type:"variable",
     meter:"input_tokens",unit_size:1000000,rate:"0"
   }]};
}
function mount(host,adapter,options){
 if(!host||!adapter)throw Error("Pricing domain provider required");
 var readable=false,writable=false,components=[],offers=[],selected=null,epoch=0;
 host.innerHTML='<div class="server-card"><h2>Enterprise Accessibility & Commercial Pricing</h2>'+
   '<p class="muted">Enterprise access is not individual entitlement. Alternative offers are selected manually in each campaign. Recurring fees are not per-Run usage.</p>'+
   '<button type="button" data-price-action="refresh">Refresh</button> '+
   '<button type="button" data-price-action="new">+ Register commercial offer</button>'+
   '<p data-price-status role="status"></p><div data-price-access></div>'+
   '<div data-price-list></div><section data-price-editor hidden></section>'+
   '<section data-price-history hidden></section></div>';
 var status=host.querySelector("[data-price-status]"),
   access=host.querySelector("[data-price-access]"),
   list=host.querySelector("[data-price-list]"),
   editor=host.querySelector("[data-price-editor]"),
   history=host.querySelector("[data-price-history]");
 function info(s){status.textContent=s;}
 async function refresh(){
   if(!readable)return;
   var ticket=++epoch;info("Loading "+options.mode+" offers and accessibility…");
   try{
     var r=await Promise.all([adapter.components(),adapter.offers()]);
     if(ticket!==epoch||!readable)return;
     components=r[0];offers=r[1];
     if(!Array.isArray(components)||!Array.isArray(offers))throw Error("Invalid catalog/pricing representation");
     draw();info(offers.length+" registered offers. Unknown prices never imply zero cost.");
   }catch(e){
     if(ticket!==epoch)return;
     components=[];offers=[];access.replaceChildren();list.replaceChildren();
     info("Pricing unavailable: "+e.message+". No Demo fallback.");
   }
 }
 function draw(){
   access.innerHTML='<h3>Enterprise availability</h3>'+
      (components.length?components.map(function(c){
        var v=(c.properties||{}).enterprise_accessibility||"unknown";
        if(!STATUSES.includes(v))v="unknown";
        return '<div class="list-row"><strong>'+esc(c.name)+'</strong> · '+esc(c.id)+
         ' · '+esc(c.revision||"")+
         ' <label>Enterprise <select data-access-id="'+esc(c.id)+'"'+(!writable?" disabled":"")+'>'+
         STATUSES.map(s=>'<option value="'+s+'"'+(s===v?" selected":"")+'>'+s+'</option>').join("")+
         '</select></label> · personal entitlement: not determined here</div>';
      }).join(""):"No catalog components.")+
      '<h3>Commercial offers</h3>';
   list.innerHTML=offers.length?offers.map(function(o){
     var p=o.properties||{},r=o.readiness||{};
     return '<div class="list-row"><strong>'+esc(o.name)+'</strong> · '+esc(o.id)+
       ' · '+esc(o.revision)+'<p>Component '+esc(p.component_id)+' · '+esc(p.currency)+
       ' · '+esc(p.status)+' · '+esc((p.lines||[]).length)+' cumulative charge line(s)</p>'+
       '<p>'+esc(p.source)+' · verified '+esc(p.checked_on)+'</p>'+
       '<p>'+esc(r.complete===true?"Meter schema complete":
              "Pricing incomplete: "+(r.reasons||[]).join("; "))+'</p>'+
       '<button data-price-action="history" data-id="'+esc(o.id)+'">History</button>'+
       (writable?'<button data-price-action="revise" data-id="'+esc(o.id)+'">Revise</button>':"")+
       '</div>';
   }).join(""):"No commercial offers recorded; commercial terms unknown.";
   var plus=host.querySelector('[data-price-action="new"]');
   plus.hidden=!writable;
 }
 function openEdit(row){
   if(!writable)return;
   selected=row||null;
   var p=row?row.properties:sample(components[0]&&components[0].id);
   editor.hidden=false;
   editor.innerHTML='<h3>'+(row?"Revise pinned tariff":"Register new offer")+'</h3>'+
     '<form data-price-form><label>Offer name<input name="name" required maxlength="160" value="'+
         esc(row?row.name:"")+'"></label>'+
     '<label>Billable component<select name="component_id"'+(row?" disabled":"")+'>'+
     components.map(c=>'<option value="'+esc(c.id)+'"'+(c.id===p.component_id?" selected":"")+
       '>'+esc(c.name)+' ('+esc(c.id)+')</option>').join("")+'</select></label>'+
     '<label>Currency<input name="currency" required maxlength="3" value="'+esc(p.currency||"EUR")+'"></label>'+
     '<label>Billing owner<input name="billing_owner" required value="'+esc(p.billing_owner||"")+'"></label>'+
     '<label>Tariff source URL / reference<input name="source" required value="'+esc(p.source||"")+'"></label>'+
     '<label>Checked YYYY-MM-DD<input name="checked_on" type="date" required value="'+esc(p.checked_on||"")+'"></label>'+
     '<label>State<select name="status">'+["active","retired","unknown"].map(s=>
       '<option value="'+s+'"'+(p.status===s?" selected":"")+'>'+s+'</option>').join("")+'</select></label>'+
     '<label>Validity start (optional)<input type="date" name="effective_from" value="'+esc(p.effective_from||"")+'"></label>'+
     '<label>Validity end (optional)<input type="date" name="effective_to" value="'+esc(p.effective_to||"")+'"></label>'+
     '<label>Charge lines (JSON array · cumulative within this offer)<textarea name="lines" rows="11" required>'+
       esc(JSON.stringify(p.lines||[],null,2))+'</textarea></label>'+
     '<p class="muted">Free, token/input/output/cache/reasoning, provider credits, requests/time, tiered/overage, subscriptions/per-seat, hybrid and unknown lines are supported. Alternative offers must not be summed.</p>'+
     '<button type="submit">Save immutable '+(row?"revision":"offer")+'</button>'+
     '<button type="button" data-price-action="cancel">Cancel</button></form>';
 }
 host.addEventListener("change",async function(e){
   var el=e.target;
   if(!el.matches("[data-access-id]")||!writable)return;
   var c=components.find(x=>x.id===el.dataset.accessId);
   if(!c)return;
   el.disabled=true;
   try{await adapter.access(c,el.value);await refresh();}
   catch(err){info("Enterprise access revision rejected: "+err.message);el.value=(c.properties||{}).enterprise_accessibility||"unknown";}
   finally{el.disabled=false;}
 });
 host.addEventListener("click",async function(e){
   var btn=e.target.closest("[data-price-action]");if(!btn)return;
   var action=btn.dataset.priceAction;
   if(action==="refresh")return refresh();
   if(action==="cancel"){editor.hidden=true;return;}
   if(action==="new")return openEdit(null);
   var obj=offers.find(x=>x.id===btn.dataset.id);if(!obj)return;
   if(action==="revise")return openEdit(obj);
   if(action==="history"){
     history.hidden=false;history.textContent="Loading immutable price revisions…";
     try{var rows=await adapter.revisions(obj.id);
       history.innerHTML='<h3>Original offer revisions</h3>'+
       rows.map(x=>'<details><summary>'+esc(x.revision)+' · '+esc(x.created_at)+
         '</summary><pre></pre></details>').join("");
       history.querySelectorAll("pre").forEach((pre,i)=>pre.textContent=JSON.stringify(rows[i],null,2));
     }catch(err){history.textContent="History unavailable: "+err.message;}
   }
 });
 host.addEventListener("submit",async function(e){
   if(!e.target.matches("[data-price-form]"))return;
   e.preventDefault();if(!writable)return;
   var form=e.target,button=form.querySelector('[type="submit"]');button.disabled=true;
   try{
     var original=selected&&selected.properties||{};
     var data=Object.assign({},original,{
       component_id:selected?original.component_id:form.elements.component_id.value,
       currency:form.elements.currency.value.toUpperCase(),billing_owner:form.elements.billing_owner.value,
       source:form.elements.source.value,checked_on:form.elements.checked_on.value,
       status:form.elements.status.value,effective_from:form.elements.effective_from.value||null,
       effective_to:form.elements.effective_to.value||null,
       lines:JSON.parse(form.elements.lines.value)
     });
     if(!Array.isArray(data.lines))throw Error("Charge lines must be a JSON array");
     if(selected)await adapter.revise(selected.id,{expected_revision:selected.revision,
       name:form.elements.name.value,properties:data});
     else await adapter.create({name:form.elements.name.value,properties:data});
     editor.hidden=true;await refresh();
   }catch(err){info("Pricing change rejected: "+err.message+"; original draft retained.");}
   finally{button.disabled=false;}
 });
 function setAccess(read,write){
   readable=!!read;writable=readable&&!!write;++epoch;
   editor.hidden=true;history.hidden=true;host.hidden=!readable;
   access.replaceChildren();list.replaceChildren();
   if(readable)refresh();
 }
 host.hidden=true;
 return {setAccess,refresh};
}
function serverAdapter(fetcher,csrf){
 const transport=root.AICompassRuntime.ServerTransport(fetcher,csrf);
 const request=transport.request;
 return {
   components:async()=>{var results=await Promise.all(KINDS.map(k=>request("/api/v1/catalog/"+k)));
     return results.flatMap(r=>r.results);},
   offers:async()=> (await request("/api/v1/pricing/offers")).results,
   create:data=>request("/api/v1/pricing/offers","POST",data),
   revise:(id,data)=>request("/api/v1/pricing/offers/"+encodeURIComponent(id),"PATCH",data),
   revisions:async id=>(await request("/api/v1/pricing/offers/"+encodeURIComponent(id)+"/revisions")).revisions,
   access:(row,status)=>{
     var parts={model:"model",provider:"provider",harness:"harness",framework:"framework"};
     var type=row.type||(row.id.startsWith("mdl-")?"model":row.id.startsWith("prv-")?"provider":
       row.id.startsWith("hrn-")?"harness":"framework");
     if(!parts[type])throw Error("Unrecognized type");
     return request("/api/v1/pricing/access/"+type+"/"+encodeURIComponent(row.id),"PATCH",
        {enterprise_accessibility:status,expected_revision:row.revision});
   }
 };
}
root.AICompassPricing={mount,serverAdapter,sample};
})(window);
