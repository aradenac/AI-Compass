/* FUT-06: the same real/fictional OS self-profile and discovery presenter.
 * No browser OS sniffing, no Demo -> Server fallback, no inferred entitlement.
 */
(function (root) {
  "use strict";
  var OS = ["windows", "linux"];
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g,function(c){
      return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
    });
  }
  function valid(list) {
    return Array.isArray(list) && list.length>0 && list.length<=2 &&
      list.every(x=>OS.includes(x)) && new Set(list).size===list.length;
  }
  function normalize(list) {return valid(list)?OS.filter(x=>list.includes(x)):null;}
  function record(row) {
    var declared=normalize((row.properties||{}).supported_os);
    return {id:row.id,type:row.type,revision:row.revision,revision_id:row.revision_id,
      name:row.name, supported_os:declared,status:declared?"classified":"unknown"};
  }
  function compose(rows, available, topology) {
    if(topology && topology!=="shared_os")return {
      status:"unknown_topology",supported_os:null,
      reason:"Distributed/multi-machine topology is unverified; OS compatibility unknown"};
    if(!Array.isArray(rows)||!rows.length)return {
      status:"unknown",supported_os:null,reason:"No Harness or Framework selected"};
    var intersection=new Set(OS),unknown=[];
    var sources=rows.filter(r=>["harness","framework"].includes(r.type)).map(record);
    if(!sources.length)return {status:"unknown",supported_os:null,
      reason:"No OS-dependent component in this configuration"};
    sources.forEach(r=>{
      if(r.supported_os===null)unknown.push(r.id);
      else r.supported_os.forEach(x=>{}),OS.filter(x=>!r.supported_os.includes(x)).forEach(x=>intersection.delete(x));
    });
    var shared=OS.filter(x=>intersection.has(x));
    if(!shared.length)return {status:"unsupported_combination",supported_os:[],
      reason:"No common OS across this Harness/Framework configuration",sources:sources};
    if(unknown.length)return {status:"unknown",supported_os:null,
      reason:"OS not classified for "+unknown.join(", "),sources:sources};
    if(!normalize(available))return {status:"unconfigured_user",supported_os:shared,
      reason:"Set your Windows/Linux availability in your profile",sources:sources};
    var matching=shared.filter(x=>available.includes(x));
    if(matching.length)return {status:"compatible",supported_os:shared,matching_os:matching,
      reason:"OS compatible; actual entitlement, access and guide not verified",sources:sources};
    return {status:"other_os",supported_os:shared,requires_os:shared,
      reason:"Requires "+shared.map(x=>x[0].toUpperCase()+x.slice(1)).join(" or ")+
             ". Still discoverable as an alternative.",sources:sources};
  }
  function demoProvider(db,identity,persist) {
    // Local in-browser fixtures are not physical Server user accounts.
    function revisions(){return (db.environmentHistory||[]).filter(x=>x.user===identity());}
    return {
      profile:async function() {
        var rows=revisions(),last=rows[rows.length-1];
        return {configured:!!last, available_os:last?last.available_os.slice():null,
          revision:last?"r"+String(last.number).padStart(3,"0"):null,
          source:last?"self_declared_fictional":"unconfigured",entitlement_status:"not_verified_by_os"};
      },
      save:async function(expected,available){
        if(!valid(available))throw Error("Select at least one of Windows or Linux");
        var old=await this.profile();
        if(old.revision!==expected){var e=Error("revision_conflict");e.status=409;throw e;}
        var next=OS.filter(x=>available.includes(x));
        if(old.configured && JSON.stringify(old.available_os)===JSON.stringify(next))return old;
        db.environmentHistory=db.environmentHistory||[];
        db.environmentHistory.push({user:identity(),number:revisions().length+1,
          available_os:next,at:new Date().toISOString()});persist();
        return this.profile();
      },
      sources:async function(){
        var list=(db.components||[]).filter(c=>["harness","framework"].includes(c.type));
        return list.map(c=>Object.assign({revision:"r001",revision_id:null},c,
          {properties:c.properties||{},type:c.type}));
      },
      evaluate:async function(selected,available){return compose(selected,available,"shared_os");}
    };
  }
  function serverProvider(fetcher,csrf) {
    var api=root.AICompassRuntime.ServerTransport(fetcher,csrf);
    return {
      profile:()=>api.request("/api/v1/profile/environment"),
      save:(revision,available_os)=>api.request("/api/v1/profile/environment","PATCH",
        {expected_revision:revision,available_os:available_os}),
      sources:async()=>{
        var results=await Promise.all(["harness","framework"].map(k=>
          api.request("/api/v1/catalog/"+k)));
        return results.flatMap(r=>r.results);
      },
      evaluate:(selected)=>api.request("/api/v1/environment/compatibility","POST",{
        components:selected.map(r=>({type:r.type,id:r.id,revision_id:r.revision_id})),
        topology:"shared_os"
      })
    };
  }
  function mount(element,provider,mode) {
    if(!element||!provider)throw Error("Environment presenter requires selected provider");
    var enabled=false,generation=0,profile=null,sources=[];
    element.innerHTML='<div class="server-card"><h2>My available operating systems</h2>'+
      '<p class="muted">Self-declared Windows/Linux only. Not a license, verified deployment, or host-server OS.</p>'+
      '<p data-os-message role="status"></p>'+
      '<form data-os-profile><label><input type="checkbox" name="windows"> Windows available</label> '+
      '<label><input type="checkbox" name="linux"> Linux available</label> '+
      '<button type="submit">Save my environment</button></form>'+
      '<section data-os-discovery><h3>Discover compatible and alternative tools</h3>'+
      '<p class="muted">OS compatibility is only one facet. No ranking by benchmark quality is implied.</p>'+
      '<div data-os-collection></div>'+
      '<h4>Assembled Harness + Framework / participant Harnesses</h4>'+
      '<label>Components in one shared OS environment<select multiple size="7" data-os-parts></select></label>'+
      '<button type="button" data-os-evaluate>Evaluate selected components</button>'+
      '<p data-os-evaluation role="status"></p></section></div>';
    element.hidden=true;
    var msg=element.querySelector("[data-os-message]");
    var collection=element.querySelector("[data-os-collection]");
    var parts=element.querySelector("[data-os-parts]");
    var result=element.querySelector("[data-os-evaluation]");
    var form=element.querySelector("[data-os-profile]");
    function status(s){msg.textContent=s;}
    function label(r) {
      if(!r.supported_os)return "OS support unknown — not verified";
      return r.supported_os.map(x=>x[0].toUpperCase()+x.slice(1)).join(" + ");
    }
    async function refresh(){
      if(!enabled)return;
      var ticket=++generation;
      status("Loading "+(mode==="demo"?"fictional":"authenticated")+" user OS profile and catalog…");
      try{
        var data=await Promise.all([provider.profile(),provider.sources()]);
        if(ticket!==generation||!enabled)return;
        profile=data[0];sources=data[1].filter(r=>["harness","framework"].includes(r.type));
        var chosen=profile.available_os||[];
        OS.forEach(x=>{form.querySelector('[name="'+x+'"]').checked=chosen.includes(x);});
        status(profile.configured?"Saved profile "+profile.revision:"No OS profile configured: Set your OS.");
        var compatible=[],alternative=[],unknown=[],disjoint=[];
        sources.forEach(row=>{
          var computed=compose([row],chosen.length?chosen:null);
          var tag=esc(row.name)+" ("+esc(row.id)+" · "+esc(row.revision)+") — "+
            esc(label(record(row)))+" · "+esc(computed.reason);
          var markup='<li>'+tag+'</li>';
          if(computed.status==="compatible")compatible.push(markup);
          else if(computed.status==="other_os")alternative.push(markup);
          else if(computed.status==="unsupported_combination")disjoint.push(markup);
          else unknown.push(markup);
        });
        collection.innerHTML='<h4>Compatible with my available OS ('+compatible.length+')</h4><ul>'+
          compatible.join("")+'</ul><h4>Interesting other-OS alternatives ('+alternative.length+
          ')</h4><ul>'+alternative.join("")+'</ul><h4>Unclassified / set your OS ('+
          unknown.length+')</h4><ul>'+unknown.join("")+'</ul>';
        parts.innerHTML=sources.map(r=>'<option value="'+esc(r.id)+'">'+
          esc(r.type)+" · "+esc(r.name)+" · "+esc(label(record(r)))+'</option>').join("");
        result.textContent="";
      }catch(e){
        if(ticket!==generation)return;
        profile=null;sources=[];collection.replaceChildren();parts.replaceChildren();
        result.textContent="";
        status("OS data unavailable: "+e.message+". No cross-mode fallback.");
      }
    }
    form.addEventListener("submit",async function(event){
      event.preventDefault();if(!enabled||!profile)return;
      var selected=OS.filter(x=>form.querySelector('[name="'+x+'"]').checked);
      if(!selected.length){status("Choose at least Windows or Linux before saving.");return;}
      var button=form.querySelector('[type="submit"]');button.disabled=true;
      try{
        profile=await provider.save(profile.revision,selected);
        await refresh();
      }catch(e){status("Profile not saved: "+e.message+
        (e.status===409?". Reload and retry; never overwrite another version.":""));}
      finally{button.disabled=false;}
    });
    element.querySelector("[data-os-evaluate]").addEventListener("click",async function(){
      if(!enabled||!profile)return;
      var chosen=Array.from(parts.selectedOptions||[]).map(opt=>
        sources.find(r=>r.id===opt.value)).filter(Boolean);
      if(!chosen.length){result.textContent="Select at least a Harness or Framework.";return;}
      try{
        var projection=await provider.evaluate(chosen,profile.available_os);
        result.textContent="Result: "+projection.status+" · "+projection.reason+
          (projection.supported_os?" · Supported OS: "+projection.supported_os.join(", "):"")+
          " · Enterprise access, personal entitlement, Setup Guide and measured quality remain separate.";
      }catch(e){result.textContent="Cannot evaluate: "+e.message+
        ". No fabricated compatibility result.";}
    });
    return {setAccess:function(on){enabled=!!on;++generation;element.hidden=!enabled;
      if(enabled)refresh();else{profile=null;sources=[];collection.replaceChildren();parts.replaceChildren();
        result.textContent="";status("");}},refresh:refresh};
  }
  root.AICompassEnvironment={OS,normalize,record,compose,demoProvider,serverProvider,mount};
})(window);
