/* FUT-05: explicit, non-automatic tariff choice for pinned Campaign sources. */
(function(root){
"use strict";
function escape(s){return String(s==null?"":s).replace(/[&<>"']/g,
  c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function mount(host,form,offers,previous,getParticipants){
 if(!host||!form||!Array.isArray(offers))throw Error("Campaign tariff picker needs form and real offers");
 previous=previous||[];
 var pending={};
 function rows(){
   var out=[],framework=form.elements.framework_id.value;
   if(framework)out.push(["root:framework",framework]);
   if(framework){
     getParticipants().forEach(function(p){
       if(!p.id)return;
       ["model","provider","harness"].forEach(function(k){
         if(p.component_ids&&p.component_ids[k])out.push([p.id+":"+k,p.component_ids[k]]);
       });
     });
   }else if(form.elements.mode.value==="solution_centred"){
     ["model","provider","harness"].forEach(function(k){
       if(form.elements[k].value)out.push(["root:"+k,form.elements[k].value]);
     });
   }
   return out;
 }
 function render(){
   var next=rows();
   host.innerHTML='<h4>Commercial offers · manual selection per billable source</h4>'+
     '<p class="muted">No plan is selected automatically. Multiple price lines within one offer are cumulative; alternatives are exclusive. Fixed commitments are not marginal Run charges.</p>'+
     next.map(function(p){
       var key=p[0],component=p[1];
       var selected=pending[key]||previous.find(function(x){
         return x.source_key===key&&x.component_id===component;
       });
       var options=offers.filter(function(x){return x.properties.component_id===component;})
         .map(function(x){return {
           value:x.id+"|"+x.revision_id,
           label:x.name+" · "+x.revision+" · "+x.properties.currency+
             (x.readiness.complete?"":" · MISSING RATE / INACTIVE")
         };});
       if(selected && !options.some(function(x){
          return x.value===selected.offer_id+"|"+selected.offer_revision_id;
        }))options.push({value:selected.offer_id+"|"+selected.offer_revision_id,
           label:"Previous frozen revision · "+selected.offer_id+" · "+selected.offer_revision_id});
       return '<label>'+escape(key)+' · '+escape(component)+
         '<select data-pricing-source="'+escape(key)+'" data-pricing-component="'+escape(component)+'">'+
         '<option value="">— Select offer revision —</option>'+
         options.map(function(o){return '<option value="'+escape(o.value)+'"'+
           (selected&&o.value===selected.offer_id+"|"+selected.offer_revision_id?" selected":"")+
           '>'+escape(o.label)+'</option>';}).join("")+'</select></label>';
     }).join("")+(next.length?"":'<p class="server-error">No explicit technical setup to price: complete the campaign first.</p>')+
     (getParticipants().some(function(x){return !x.id;})?
       '<p class="server-error">Save new participants first, then pin their permanent IDs and tariffs.</p>':"");
 }
 host.addEventListener("change",function(e){
   if(!e.target.matches("[data-pricing-source]"))return;
   var x=e.target,sep=x.value.indexOf("|");
   pending[x.dataset.pricingSource]=x.value?{
     source_key:x.dataset.pricingSource,component_id:x.dataset.pricingComponent,
     offer_id:x.value.slice(0,sep),offer_revision_id:x.value.slice(sep+1)}:null;
 });
 function selections(){
   return Array.from(host.querySelectorAll("[data-pricing-source]"))
     .filter(function(node){return node.value;})
     .map(function(node){
       var split=node.value.indexOf("|");
       return {source_key:node.dataset.pricingSource,
         component_id:node.dataset.pricingComponent,
         offer_id:node.value.slice(0,split),offer_revision_id:node.value.slice(split+1)};
     });
 }
 render();
 return {render,selections,rows};
}
root.AICompassPricingSelection={mount};
})(window);
