/* FUT-17: separate /maintenance Audit & Changes; read-only, no Demo storage. */
(function () {
  "use strict";
  function mount(root, escapeHtml) {
    var allowed = false, generation = 0, filters = {source:"all",object_type:"",
      object_id:"",actor:"",action:"",field:"",from:"",to:""}, page = 1;
    root.hidden = true;
    function el(s) {return root.querySelector(s);}
    function status(msg,bad) {var n=el("#audit-status");if(n){
      n.textContent=msg;n.className=bad?"server-status server-error":"server-status";}}
    function query(withPage) {
      var params = new URLSearchParams();
      Object.keys(filters).forEach(function(k) {
        if(filters[k] && filters[k]!=="all")params.set(k,filters[k]);
      });
      if(withPage)params.set("page",String(page));
      return params;
    }
    async function get(path){
      var response=await fetch("/api/v1/maintenance/audit"+path,{
        credentials:"same-origin",cache:"no-store"});
      var data=await response.json().catch(function(){return {};});
      if(!response.ok)throw Error(data.detail||data.error||"HTTP "+response.status);
      return data;
    }
    function render(){
      root.innerHTML='<section class="server-card" aria-label="Governance Audit & Changes">'+
        '<div class="server-model-toolbar"><h2>Audit & Changes</h2>'+
        '<button id="audit-refresh" type="button">Refresh</button></div>'+
        '<p>Read-only committed-change inspector. Historic values and source links '+
        'appear only when authorized and available; no activity surveillance.</p>'+
        '<form id="audit-filters">'+
        '<label>Source<select name="source"><option value="all">All permitted sources</option>'+
        '<option value="catalog">Catalog, Campaigns and corrections</option>'+
        '<option value="run">Measured Runs</option><option value="composite_run">Framework Runs</option>'+
        '<option value="session">Session checkpoints</option>'+
        '<option value="workload">Planning workloads</option>'+
        '<option value="opportunity">Opportunity decisions</option>'+
        '<option value="budget">Resource budgets</option>'+
        '<option value="deployment_revision">Deployment targets</option>'+
        '<option value="deployment_event">Deployment access actions</option>'+
        '<option value="health">Data Health changes</option>'+
        '</select></label>'+
        '<label>Object type <input name="object_type" placeholder="model / campaign / run"></label>'+
        '<label>Permanent object ID <input name="object_id" maxlength="120" placeholder="mdl-..."></label>'+
        '<label>Actor (current username) <input name="actor" maxlength="150"></label>'+
        '<label>Operation <input name="action" maxlength="32"></label>'+
        '<label>Changed field (exact path) <input name="field" maxlength="120"></label>'+
        '<label>From UTC <input name="from" type="datetime-local"></label>'+
        '<label>To UTC <input name="to" type="datetime-local"></label>'+
        '<button type="submit">Apply filters</button></form>'+
        '<p id="audit-status" class="server-status" role="status"></p>'+
        '<div id="audit-list"></div>'+
        '<div class="server-actions"><button id="audit-prev" type="button">Previous</button> '+
        '<span id="audit-page">Page 1</span> '+
        '<button id="audit-next" type="button">Next</button></div>'+
        '<p><a id="audit-export-json" href="#">Export filtered metadata JSON</a> · '+
        '<a id="audit-export-csv" href="#">CSV</a></p>'+
        '<section id="audit-details" class="server-card" hidden>'+
        '<h3>Immutable revision and field differences</h3>'+
        '<div id="audit-details-body"></div></section></section>';
      el('#audit-refresh').addEventListener('click',refresh);
      el('#audit-filters').addEventListener('submit',function(e){
        e.preventDefault();
        var f=e.target;Object.keys(filters).forEach(function(k){
          filters[k]=f.elements[k].value.trim();
          if(["from","to"].includes(k) && filters[k])filters[k]+=":00Z";
        });page=1;refresh();
      });
      el('#audit-prev').addEventListener('click',function(){if(page>1){page--;refresh();}});
      el('#audit-next').addEventListener('click',function(){page++;refresh();});
      el('#audit-list').addEventListener('click',async function(e){
        var button=e.target.closest('button[data-id]');if(!button)return;
        var key=button.getAttribute('data-id'),ticket=generation;
        el('#audit-details').hidden=false;
        el('#audit-details-body').textContent="Loading immutable source…";
        try{
          var r=await get('/'+encodeURIComponent(key));
          if(!allowed||ticket!==generation)return;
          var event=r.event||{},changes=r.changes||[];
          el('#audit-details-body').innerHTML='<p><strong>'+escapeHtml(event.object_type)+
            ' / '+escapeHtml(event.object_id)+'</strong> · '+escapeHtml(event.operation)+
            ' · '+escapeHtml(event.occurred_at)+'</p>'+
            '<p>Revision '+escapeHtml(event.revision||'unavailable')+
            ' · origin '+escapeHtml(event.origin||'unknown')+
            ' · source '+escapeHtml(event.source)+'</p>'+
            '<p>'+escapeHtml(changes.length)+' visible field/relationship changes; '+
            'private fields excluded, missing historic values never reconstructed.</p>'+
            (changes.length?'<table><thead><tr><th>Field</th><th>Before</th>'+
            '<th>After</th></tr></thead><tbody>'+changes.map(function(c){
              return '<tr><td>'+escapeHtml(c.field)+'</td><td><code>'+
                escapeHtml(JSON.stringify(c.before))+'</code></td><td><code>'+
                escapeHtml(JSON.stringify(c.after))+'</code></td></tr>';
            }).join('')+'</tbody></table>':'<p>Visible details unavailable or unchanged.</p>');
        }catch(error){if(ticket===generation)el('#audit-details-body').textContent=error.message;}
      });
      ['json','csv'].forEach(function(type){
        var a=el('#audit-export-'+type);
        a.addEventListener('click',function(ev){if(!allowed){ev.preventDefault();}});
      });
    }
    async function refresh(){
      if(!allowed)return;
      var ticket=++generation;
      status('Loading committed source history…');
      el('#audit-details').hidden=true;
      var params=query(true);
      ['json','csv'].forEach(function(type){
        var q=query(false);q.set('format',type);
        el('#audit-export-'+type).href='/api/v1/maintenance/audit/export?'+q.toString();
      });
      try {
        var result=await get('?'+params.toString());
        if(!allowed||generation!==ticket)return;
        var sourceSelect=el('#audit-filters').elements.source;
        (result.sources||[]).filter(function(s){
          return ['access','environment'].includes(s) &&
            !sourceSelect.querySelector('option[value="'+s+'"]');
        }).forEach(function(s){
          var option=document.createElement('option');
          option.value=s;option.textContent=s==='access'?
            'Accounts (restricted)': 'User OS declarations (restricted)';
          sourceSelect.appendChild(option);
        });
        el('#audit-list').innerHTML=(result.results||[]).map(function(r){
          return '<div class="list-row"><strong>'+escapeHtml(r.operation)+
            '</strong> · '+escapeHtml(r.object_type)+' / '+escapeHtml(r.object_id)+
            '<div class="muted small">'+escapeHtml(r.actor||'actor unknown')+
            ' · '+escapeHtml(r.occurred_at)+' · '+escapeHtml(r.revision||'no revision')+
            '</div><button type="button" data-id="'+escapeHtml(r.id)+'">Inspect</button></div>';
        }).join('')||'<p>No matching, authorized change records.</p>';
        el('#audit-prev').disabled=page===1;
        el('#audit-next').disabled=!result.has_more;
        el('#audit-page').textContent='Page '+page;
        status((result.results||[]).length+' event(s); '+(result.limited?
          'bounded latest 500, narrow filters for older history.':
          'only persisted committed source records.')); 
      }catch(err){if(generation!==ticket||!allowed)return;
        status('Audit unavailable: '+err.message,true);
        el('#audit-list').textContent='No authorized source details available.';}
    }
    return {setAccess:function(read){
      allowed=!!read;generation++;root.hidden=!allowed;
      root.replaceChildren();page=1;
      filters={source:"all",object_type:"",object_id:"",actor:"",
        action:"",field:"",from:"",to:""};
      if(allowed){render();refresh();}
    }};
  }
  window.AICompassServerAudit={mount:mount};
})();
