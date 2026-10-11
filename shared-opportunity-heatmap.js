/* FUT-14: one visual opportunity experience for Planner and Management.
   Server is protected; Demo is fictional. No financial recomputation here. */
(function(root){
"use strict";
function escape(v){return String(v==null?"":v).replace(/[&<>"']/g,function(c){
return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}
function qs(data){return Object.keys(data).filter(k=>data[k]!==""&&data[k]!=null).map(
  k=>encodeURIComponent(k)+"="+encodeURIComponent(data[k])).join("&");}
function serverProvider(fetcher,csrf){
 const request=root.AICompassRuntime.ServerTransport(fetcher,csrf).request;
 return {
   bootstrap:async()=>{let r=await Promise.all([
     request("/api/v1/planning/profiles"),
     request("/api/v1/planning/opportunities")]);
     return {profiles:r[0].results,scenarios:r[1].results};},
   heatmap:p=>request("/api/v1/planning/heatmap?"+qs(p)),
   insights:p=>request("/api/v1/planning/insights?"+qs(p)),
   explain:p=>request("/api/v1/planning/insights/explain?"+qs(p)),
   suggestions:p=>request("/api/v1/planning/insights/suggestions?"+qs(p))
 };
}
function demoProvider(db){
 // Reuse the original fictional FUT-13 cost model; no second real engine.
 const economy=root.AICompassOpportunities.demoProvider(db);
 const population={id:"wlp-demo",name:"Fictional Demo cohort (2 people)",kind:"cohort"};
 const historical={name:"Demo illustrative candidate portfolio",
   benchmark_weight:"0.8",choices:[]};
 const tasks=db.tasks||[],cases=db.cases||[],runs=db.runs||[],sols=db.solutions||[];
 const valid=[];
 cases.forEach(c=>runs.filter(r=>r.case===c.id&&r.status==="published"&&!r.withdrawn)
   .forEach(r=>{const s=sols.find(x=>x.id===r.solution);
     if(s&&!valid.some(x=>x.task_id===c.task&&x.candidate_id===s.id))
       valid.push({task_id:c.task,kind:"benchmark",candidate_id:s.id,
                   name:s.name,label:"Fictional measured Demo"});}));
 const selectedTasks=new Set();
 valid.forEach(x=>{if(!selectedTasks.has(x.task_id)&&historical.choices.length<4){
   selectedTasks.add(x.task_id);historical.choices.push({
     task_id:x.task_id,kind:x.kind,candidate_id:x.candidate_id});}});
 const scenarios=[{id:"opp-demo-insights",profile_id:"wlp-demo",
                   latest_revision:"r002",name:historical.name}];
 async function current(){return economy.preview("wlp-demo",historical);}
 async function frozen(number){
   const d=await current();
   if(number===1){
     // Historical fixture is explicitly simulated from fictional economics,
     // not a claim about a historic real source or verified prior revision.
     return {...d,algorithm:"fictional-demo-as-of-2026-09-20",
       totals:{...d.totals,
         benchmarked_opportunity_eur:(Number(d.totals.benchmarked_opportunity_eur)*0.65).toFixed(2),
         forecast_opportunity_eur:"0.00",
         positive_modeled_total_eur:(Number(d.totals.positive_modeled_total_eur)*0.65).toFixed(2)}};
   }
   return d;
 }
 function history(one,two){
   return [one,two].map((projection,i)=>({
     revision:"r00"+(i+1),revision_number:i+1,
     date:i===0?"2026-09-20T12:00:00Z":"2026-10-08T12:00:00Z",
     annual_slices:{
       activated_potential_eur:projection.totals.activated_potential_eur,
       benchmarked_opportunity_eur:projection.totals.benchmarked_opportunity_eur,
       forecast_opportunity_eur:projection.totals.forecast_opportunity_eur},
     total_eur:projection.totals.positive_modeled_total_eur,
     possible_change_factors:i?["fictional_demo_simulated_change"]:["initial_snapshot"],
     source_frozen:true}));
 }
 const projectionCells=async(revision)=>{
   const data=await frozen(revision||2);const chosen=historical.choices;
   return chosen.map(c=>{
     const v=data.cells.find(x=>x.task_id===c.task_id&&x.candidate_id===c.candidate_id);
     return {...c,computed:v};});
 };
 function candidates(){return valid.concat((db.proposals||[]).filter(p=>p.status==="published")
   .map(p=>({task_id:p.task,kind:"forecast",candidate_id:p.id,
     name:p.name,label:"Fictional theoretical hypothesis"})));}
 return {
   bootstrap:async()=>({profiles:[population],scenarios}),
   heatmap:async p=>{
     const rev=p.revision?Number(String(p.revision).slice(1)):null;
     const all=candidates(),cols=Array.from(new Map(all.map(c=>[
       c.kind+"|"+c.candidate_id,{kind:c.kind,id:c.candidate_id,name:c.name,label:c.label}])).values());
     const rr=Number(p.row_page||0),cc=Number(p.column_page||0),
       rowSize=Number(p.row_size||8),colSize=Number(p.column_size||8),
       rows=tasks.slice(rr*rowSize,rr*rowSize+rowSize).map((t,i)=>({id:t.id,name:t.name,
         parent_id:t.parent,depth:0})),
       columns=cols.slice(cc*colSize,cc*colSize+colSize);
     const calculated=await projectionCells(rev);
     let cells=[];
     for(const t of rows){for(const c of columns){
       const same=all.find(x=>x.task_id===t.id&&x.kind===c.kind&&x.candidate_id===c.id);
       if(!same)continue;
       const chosen=calculated.find(x=>x.task_id===t.id&&x.kind===c.kind&&x.candidate_id===c.id);
       if(rev&&!chosen)continue;
       const v=chosen?chosen.computed:(await economy.preview("wlp-demo",{name:"Fictional alternative",
         benchmark_weight:"0.8",choices:[same]})).cells[0];
       const amount=v.economic&&v.economic.annual_eur;
       cells.push({task_id:t.id,candidate_id:c.id,kind:c.kind,selected:!!chosen,
         status:v.status,annual_eur:amount,
         intensity_eur:amount!=null&&Number(amount)>0?amount:null,
         maturity:v.status==="unquantifiable"?"?":c.kind==="benchmark"?"B":"F",
         reason_codes:v.reasons||[],coverage:1});
     }}
     return {scope:"fictional_demo_only",profile_id:p.profile_id,
       scenario_id:p.scenario_id||null,revision:p.revision||"r002",
       historical:!!p.revision,period:"annual",currency:"EUR",
       row_page:rr,column_page:cc,row_size:rowSize,column_size:colSize,
       total_rows:tasks.length,total_columns:cols.length,rows,columns,cells,
       note:"All data and original dates in this demo are fictional.",
       legend:{intensity_breakpoints_eur:["0","1000","10000","100000"]}};
   },
   insights:async p=>{
     if(!p.scenario_id)return {profile_id:p.profile_id,scenario_id:null,portfolio:null,
       snapshots:[],empty:"Select fictional Demo scenario to see the portfolio"};
     const older=await frozen(1),newer=await frozen(2);
     return {profile_id:"wlp-demo",scenario_id:p.scenario_id,
       revision:p.revision||"r002",portfolio:p.revision?older:newer,
       snapshots:history(older,newer),historical:!!p.revision,
       source_changed_since_snapshot:false,period:"annual",
       interpretation:"fictional_fixture_no_real_financial_evidence"};
   },
   explain:async p=>{
     const data=await (p.revision?frozen(Number(p.revision.slice(1))):current());
     const cell=data.cells.find(c=>c.task_id===p.task_id&&
       c.candidate_id===p.candidate_id&&c.kind===p.kind);
     if(!cell)throw Error("This candidate is not selected in the fictional scenario.");
     return {scenario_id:p.scenario_id,revision:p.revision||"r002",
       historical:!!p.revision,summary:{status:cell.status,
         annual_eur:cell.economic&&cell.economic.annual_eur,
         reasons:cell.reasons||[],slices:cell.slices},
       breadcrumbs:[{type:"scenario",id:p.scenario_id},
         {type:"task",id:p.task_id},{type:p.kind,id:p.candidate_id}],
       branches:[{type:"formula",label:"Fictional illustrative assumptions",
         factors:cell.source_workload||{}},
         {type:"deployment",label:"Unverified",
         factors:{entitlement:"not verified",first_use:"not verified"}}],
       source_warning:"Synthetic Demo provenance; no real historical Run"};
   },
   suggestions:async p=>({profile_id:p.profile_id,
     sort_policy:"fictional_descriptive_only",total_candidates:valid.length,
     suggestions:valid.slice(0,40).map(x=>({...x,not_selected:true,
        deployment_started:false,reason:"Fictional published Demo Run"}))})
 };
}
const STYLE='<style>'+
'.management-heatmap{max-width:none!important;min-width:0}.heat-controls{display:grid;grid-template-columns:repeat(auto-fit,minmax(165px,1fr));gap:12px}'+
'.management-heatmap h3{margin-top:18px}.heat-scroll{max-width:100%;max-height:575px;overflow:auto;border:1px solid #dce4ee;border-radius:10px}'+
'.heat-grid{border-collapse:separate;border-spacing:0;table-layout:fixed;font-size:12px;width:max-content;min-width:100%}'+
'.heat-grid th,.heat-grid td{padding:0;border-right:1px solid #e3e9f2;border-bottom:1px solid #e3e9f2;text-align:left}'+
'.heat-grid thead th{background:#eef3fa;position:sticky;top:0;z-index:3;padding:11px;min-width:125px;max-width:155px}'+
'.heat-grid thead th small{display:block;font-size:10px;color:#52627a}'+
'.heat-grid .heat-task-col{position:sticky;left:0;z-index:2;background:#fff;min-width:215px;max-width:260px;padding:8px;box-shadow:2px 0 3px #182b4310}'+
'.heat-grid thead .heat-task-col{z-index:4;background:#e9f0fa}'+
'.heat-grid .heat-task-col div{display:flex;align-items:center;gap:5px;white-space:normal}'+
'.heat-grid .heat-task-col button{margin:0;padding:3px 6px;font-size:11px}'+
'.heat-cell button{display:flex;align-items:center;justify-content:space-between;gap:7px;background:transparent!important;color:inherit!important;border:0;width:100%;min-height:47px;margin:0!important;padding:8px!important;font:inherit;cursor:pointer}'+
'.heat-cell button:focus-visible{outline:3px solid #295edb;outline-offset:-3px}'+
'.heat-cell.heat-1{background:#edf6fd}.heat-cell.heat-2{background:#d3e8f9}.heat-cell.heat-3{background:#9ac8ed}.heat-cell.heat-4{background:#5196cb;color:#092b48}'+
'.heat-maturity{background:#fff9;border:1px solid #8198b8;border-radius:50%;font-size:10px;min-width:20px;height:20px;display:inline-grid;place-items:center}'+
'.heat-selected{font-size:9px;color:#2650a4}.heat-blank{color:#8896ad;text-align:center!important}'+
'.heat-pagination,.heat-slice-legend{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:10px 0}'+
'.heat-pagination button{font-size:11px;padding:6px 9px}.heat-slices{height:23px;display:flex;border:1px solid #bdcadd;border-radius:6px;overflow:hidden;background:#f2f5fb}'+
'.heat-slice{min-width:0}.heat-slice-0{background:#4b7597}.heat-slice-1{background:#2f9a92}.heat-slice-2{background:#c1a05b}'+
'.heat-slice-legend button{font-size:12px;padding:7px}.heat-history-bars{display:flex;align-items:flex-end;overflow-x:auto;min-height:185px;gap:16px;padding:12px 5px}'+
'.heat-history-point{display:flex;flex-direction:column;align-items:center;gap:6px;min-width:104px}'+
'.heat-history-column{height:140px;width:48px;display:flex;flex-direction:column-reverse;background:#edf1f6;border:1px solid #d6deea}'+
'.heat-history-point button{font-size:11px;padding:5px}.heat-lines{display:block;width:100%;height:170px;border:1px solid #dce3eb}'+
'.heat-history-point-buttons{display:flex;gap:10px;overflow-x:auto}.heat-trend-line{stroke:#1b547f}.heat-trend-line.trend-1{stroke:#269f87}.heat-trend-line.trend-2{stroke:#b78a3b}.heat-trend-line.trend-3{stroke:#3c4a68}'+
'.heat-inspector{border:1px solid #b5c7df;border-radius:12px;padding:18px;margin-top:20px;background:#f7faff}'+
'.heat-inspector pre{font-size:11px;max-height:310px;white-space:pre-wrap;overflow:auto;overflow-wrap:anywhere;background:#fff;padding:9px}'+
'@media(max-width:700px){.heat-grid .heat-task-col{min-width:160px;max-width:190px}.heat-controls{grid-template-columns:1fr 1fr}}'+
'</style>';
function mount(element,provider,mode){
 let available=false,scenarios=[],profiles=[],profile="",scenario="",revision="",
     rowPage=0,columnPage=0,historyMode="stacked",activeSlice="",collapsed=new Set(),matrix=null,
     insights=null,detail=null,branch=-1,suggestions=null,seq=0,status="";
 const id=n=>element.querySelector(n);
 function info(s){status=s;const out=id("[data-heat-status]");if(out)out.textContent=s;}
 function template(){
   element.innerHTML=STYLE+'<section class="server-card management-heatmap">'+
     '<div class="server-model-toolbar"><div><h2>Profitability & Opportunity Heatmap</h2>'+
     '<p>Task hierarchy × AI configurations • annual EUR prospective capacity, not recognized profit'+
     (mode==="demo"?" • fictional offline Demo":" • authorized Server")+'</p></div>'+
     '<button type="button" data-heat-refresh>Refresh current evidence</button></div>'+
     '<p data-heat-status role="status"></p><div data-heat-content></div></section>';
   id("[data-heat-refresh]").onclick=refresh;
 }
 function select(rows,value,placeholder){
   return '<option value="">'+escape(placeholder)+'</option>'+
     rows.map(r=>'<option value="'+escape(r.id)+'"'+(r.id===value?' selected':'')+'>'+
       escape(r.name||r.id)+'</option>').join("");
 }
 function controls(){
   return '<div class="heat-controls">'+
     '<label>Population<select data-heat-profile>'+
       select(profiles,profile,"Select authorized population")+'</select></label>'+
     '<label>Scenario<select data-heat-scenario>'+
       select(scenarios.filter(x=>x.profile_id===profile),scenario,
              "No selected scenario / comparisons only")+'</select></label>'+
     '<label>As-of<select data-heat-asof>'+
       '<option value="">Current effective published sources</option>'+
       (insights&&insights.snapshots||[]).map(x=>
         '<option value="'+escape(x.revision)+'"'+(revision===x.revision?' selected':'')+'>'+
          escape(x.date.slice(0,10))+' • '+escape(x.revision)+'</option>').join("")+
       '</select></label>'+
     '<label>Period<select data-heat-period><option value="annual">Annual EUR</option></select></label>'+
     '</div><p class="muted small">Every alternative column is a comparison only; only the explicitly saved portfolio contributes to the total. '+
     'No automatic deployment, entitlement or invented scoring.</p>';
 }
 function band(value){
   if(value==null||Number(value)<=0)return "";
   const n=Number(value);
   return n<1000?"heat-1":n<10000?"heat-2":n<100000?"heat-3":"heat-4";
 }
 function amount(value){return value==null?"Unknown":Number(value).toLocaleString("en-GB",{
   style:"currency",currency:"EUR",maximumFractionDigits:0})+"/yr";}
 function matrixView(){
   if(!matrix)return '<p>Choose a population for the source-backed matrix.</p>';
   let index=new Map((matrix.cells||[]).map(c=>[
     c.task_id+"|"+c.kind+"|"+c.candidate_id,c]));
   let expanded=matrix.rows||[],visible=[];
   const hidden=new Set();
   expanded.forEach(r=>{
     if(hidden.has(r.parent_id))hidden.add(r.id);
     if(!hidden.has(r.id))visible.push(r);
     if(collapsed.has(r.id))hidden.add(r.id);
   });
   const headers=matrix.columns.map(x=>'<th title="'+escape(x.label)+'">'+
     escape(x.name)+'<small> · '+escape(x.kind==="benchmark"?"Measured":"Theoretical")+
     '</small></th>').join("");
   const body=visible.map(row=>'<tr><th class="heat-task-col">'+
     '<div style="padding-left:'+Math.min(row.depth*16,200)+'px">'+
     '<button type="button" data-heat-collapse="'+escape(row.id)+'" aria-label="Toggle Task descendants">'+
       (collapsed.has(row.id)?"+":"−")+'</button> '+escape(row.name)+
     '</div></th>'+
     matrix.columns.map(col=>{
       const c=index.get(row.id+"|"+col.kind+"|"+col.id);
       if(!c)return '<td class="heat-blank" title="Uncovered Task/configuration">—</td>';
       const belonging=c.evidence_class==="measured"?"benchmarked_opportunity_eur":
         "forecast_opportunity_eur";
       if(activeSlice && (activeSlice==="activated_potential_eur"||!c.selected||
          belonging!==activeSlice||c.intensity_eur==null))
         return '<td class="heat-blank" title="Not part of the chosen annual slice">—</td>';
       const noShade=band(c.intensity_eur);
       const value=c.annual_eur==null?"unknown":amount(c.annual_eur);
       const mature=c.maturity==="B"?"Measured":c.maturity==="F"?"Forecast":"Incomplete";
       return '<td class="heat-cell '+noShade+'"><button type="button"'+
         ' data-heat-cell="'+escape(row.id)+'|'+escape(col.kind)+'|'+escape(col.id)+'"'+
         ' aria-label="'+escape(row.name+" / "+col.name+": "+value+", "+mature)+'"'+
         ' title="'+escape(value+" · "+mature+" · "+c.status)+'">'+
         '<span class="heat-maturity" aria-hidden="true">'+escape(c.maturity)+'</span>'+
         '<span class="heat-amount">'+escape(c.annual_eur==null?"?":Number(c.annual_eur).toLocaleString("en-GB",{
           maximumFractionDigits:0}))+'</span>'+
         (c.selected?'<span class="heat-selected" aria-label="Chosen portfolio">●</span>':'')+
         '</button></td>';
     }).join("")+'</tr>').join("");
   const nextR=(matrix.row_page+1)*matrix.row_size<matrix.total_rows;
   const nextC=(matrix.column_page+1)*matrix.column_size<matrix.total_columns;
   return '<div class="heat-pagination">'+
     '<button data-heat-rprev'+(rowPage===0?' disabled':'')+'>Previous Tasks</button>'+
     '<span>Tasks '+(matrix.total_rows?rowPage*matrix.row_size+1:0)+'–'+
       Math.min((rowPage+1)*matrix.row_size,matrix.total_rows)+' of '+matrix.total_rows+'</span>'+
     '<button data-heat-rnext'+(!nextR?' disabled':'')+'>Next Tasks</button>'+
     '<button data-heat-cprev'+(columnPage===0?' disabled':'')+'>Previous configurations</button>'+
     '<span>Configs '+(matrix.total_columns?columnPage*matrix.column_size+1:0)+'–'+
       Math.min((columnPage+1)*matrix.column_size,matrix.total_columns)+' of '+matrix.total_columns+'</span>'+
     '<button data-heat-cnext'+(!nextC?' disabled':'')+'>Next configurations</button></div>'+
     '<div class="heat-scroll" role="region" aria-label="Task × configuration heatmap" tabindex="0">'+
     '<table class="heat-grid"><thead><tr><th class="heat-task-col">Expandable Task hierarchy</th>'+
     headers+'</tr></thead><tbody>'+body+'</tbody></table></div>'+
     '<p class="muted small">Intensity bands (EUR/year): 0–999, 1k–9,999, 10k–99,999, 100k+. '+
     'Only strictly positive quantified economic amounts receive shading. Negative / zero remain plain; '+
     'unknown/unsupported show ?. Icons: B measured, F Forecast, ? insufficient evidence; '+
     '● is the chosen scenario alternative. Uncovered cells remain blank.</p>'+
     (revision?'<p>Frozen historical comparison: only original saved scenario candidates appear; no retroactive backfill.</p>':'');
 }
 function slices(){
   if(!insights||!insights.portfolio)return '<p>No explicit saved scenario selected; comparison cells never contribute to a portfolio total.</p>';
   const t=insights.portfolio.totals||{},sum=Math.max(0,Number(t.positive_modeled_total_eur)||0);
   const ks=[["activated_potential_eur","Activated Potential"],
     ["benchmarked_opportunity_eur","Benchmarked Opportunity"],
     ["forecast_opportunity_eur","Forecast Opportunity"]];
   return '<h3>Annual potential distribution</h3>'+
     '<p><strong>'+amount(t.positive_modeled_total_eur)+'</strong> · prospective valuation, not realized cash savings'+
     (insights.source_changed_since_snapshot?" · CURRENT SOURCES CHANGED SINCE SAVED REVISION":"")+'</p>'+
     '<div class="heat-slices" role="img" aria-label="'+
       escape(ks.map(k=>k[1]+" "+amount(t[k[0]])).join(", "))+'">'+
       ks.map((k,i)=>'<div class="heat-slice heat-slice-'+i+'" style="width:'+
         (sum?Math.max(0,Number(t[k[0]])/sum*100):0)+'%"></div>').join("")+'</div>'+
     '<div class="heat-slice-legend">'+ks.map((k,i)=>
       '<button type="button" aria-pressed="'+(activeSlice===k[0])+'" data-heat-slice="'+escape(k[0])+'">'+escape(k[1])+': '+
       amount(t[k[0]])+' ('+(sum?(Number(t[k[0]])/sum*100).toFixed(1):"0")+'%)</button>').join("")+'</div>'+
     '<button type="button" data-heat-clear-slice'+(activeSlice?'':' disabled')+
       '>Show all comparison cells</button>'+
     '<p class="muted small">Three mutually exclusive slices: activated requires verified first use. '+
       'No such source is connected in FUT-14. Missing / negative values do not become positive totals.'+
       (activeSlice?' Matrix filtered to the selected saved-portfolio slice; totals remain unchanged.':'')+'</p>';
 }
 function timeline(){
   if(!insights||!insights.snapshots.length)return '<p>No historical saved revisions.</p>';
   const points=insights.snapshots;
   const max=Math.max(1,...points.map(p=>Number(p.total_eur)||0));
   const keys=["activated_potential_eur","benchmarked_opportunity_eur","forecast_opportunity_eur"];
   let chart="";
   if(historyMode==="stacked"){
     chart='<div class="heat-history-bars">'+points.map(p=>{
       const t=p.annual_slices;
       return '<div class="heat-history-point"><div class="heat-history-column" role="img" aria-label="'+
         escape(p.revision+" "+amount(p.total_eur))+'">'+
         keys.map((k,i)=>'<div class="heat-slice heat-slice-'+i+'" style="height:'+
           Math.min(100,Math.max(0,Number(t[k])/max*100))+'%"></div>').join("")+'</div>'+
         '<button type="button" data-heat-point="'+p.revision+'">'+escape(p.date.slice(0,10))+
         ' · '+escape(p.revision)+'</button></div>';}).join("")+'</div>';
   }else{
     const pts=points.length;
     const series=[...keys,"total"];
     const poly=series.map((key,i)=>'<polyline class="heat-trend-line trend-'+i+
       '" fill="none" stroke-width="2.5" points="'+points.map((p,index)=>{
         let v=Number(key==="total"?p.total_eur:p.annual_slices[key])||0;
         let x=pts===1?50:index/(pts-1)*98+1;
         return x.toFixed(2)+","+(100-95*v/max).toFixed(2);
       }).join(" ")+'"></polyline>').join("");
     chart='<svg viewBox="0 0 100 105" preserveAspectRatio="none" role="img" '+
       'aria-label="Historical frozen annual potential trend per slice and total"'+
       ' class="heat-lines">'+poly+'</svg><div class="heat-history-point-buttons">'+
       points.map(p=>'<button data-heat-point="'+p.revision+'">'+escape(p.date.slice(0,10))+
         ' · '+escape(p.revision)+'</button>').join("")+'</div>';
   }
   return '<h3>Immutable as-of snapshots</h3>'+
     '<button type="button" data-heat-stack'+(historyMode==="stacked"?' disabled':'')+
     '>Stacked bars</button><button type="button" data-heat-lines'+
       (historyMode==="lines"?' disabled':'')+'>Individual curves</button>'+
     chart+'<table><thead><tr><th>As of</th><th>Total EUR/year</th>'+
       '<th>Delta EUR/year</th><th>Possible factors</th></tr></thead><tbody>'+
       points.map(p=>'<tr><td><button data-heat-point="'+p.revision+'">'+
         escape(p.date.slice(0,10))+' '+escape(p.revision)+'</button></td>'+
         '<td>'+amount(p.total_eur)+'</td><td>'+escape(p.delta_eur||"—")+'</td><td>'+
         escape((p.possible_change_factors||[]).join(" · "))+'</td></tr>').join("")+
       '</tbody></table>'+
     '<p class="muted small">Frozen source revisions are never rewritten. Selecting a point opens its exact as-of calculations; '+
     'the current scenario can differ. Change factors are observed differences, not proof of a single cause.</p>';
 }
 function inspector(){
   if(!detail)return "";
   if(detail.error)return '<aside class="heat-inspector"><button data-heat-back>Back</button><p>'+
      escape(detail.error)+'</p></aside>';
   const p=detail.summary||{};
   return '<aside class="heat-inspector" aria-label="Evidence and calculation inspector">'+
     '<button type="button" data-heat-back>Back to matrix</button>'+
     '<h3>Evidence & Calculation Explorer</h3>'+
     '<p>'+escape((detail.breadcrumbs||[]).map(x=>x.type+": "+x.id).join(" › "))+'</p>'+
     '<p><strong>'+amount(p.annual_eur)+'</strong> · '+escape(p.status)+
       ' · '+escape((p.reasons||[]).join("; "))+'</p>'+
     '<p class="muted small">'+escape(detail.source_warning||"")+'</p>'+
     (detail.branches||[]).map((b,i)=>'<section><button type="button" data-heat-branch="'+i+
       '" aria-expanded="'+(branch===i)+'">'+escape(b.label)+' '+(branch===i?"−":"+")+'</button>'+
       (branch===i?'<pre>'+escape(JSON.stringify(b.factors||{},null,2))+'</pre>'+
         (b.refs||[]).map(r=>'<p>Original source '+escape(r.id||"")+
           ' · '+escape(r.revision||"")+' (pinned, not updated)</p>').join(""):'')+
       '</section>').join("")+'</aside>';
 }
 function suggestionsView(){
   if(!suggestions)return "";
   return '<section><h3>Candidate suggestions (descriptive only)</h3>'+
     '<p class="muted small">Sorted by evidence maturity, then economic amount if known. '+
     'No unvalidated quality ranking and no automatic assignment.</p>'+
     (suggestions.suggestions||[]).map(x=>'<div class="list-row"><strong>'+
       escape(x.name||x.candidate_id)+'</strong> · '+escape(x.task_id)+
       ' · '+escape(x.kind)+' · '+amount(x.annual_eur)+
       '<p>'+escape(x.reason||"")+'</p></div>').join("")+'</section>';
 }
 function render(){
   const target=id("[data-heat-content]");if(!target)return;
   target.innerHTML=controls()+slices()+matrixView()+timeline()+
     '<button data-heat-suggestions type="button">Explain possible Task candidates</button>'+
     suggestionsView()+inspector();
   const change=(attr,fn)=>{let item=id(attr);if(item)item.onchange=fn;};
   change("[data-heat-profile]",function(){profile=this.value;scenario="";revision="";rowPage=0;columnPage=0;load();});
   change("[data-heat-scenario]",function(){scenario=this.value;revision="";load();});
   change("[data-heat-asof]",function(){revision=this.value;load();});
   const buttons=[["[data-heat-rprev]",()=>{rowPage--;load();}],
     ["[data-heat-rnext]",()=>{rowPage++;load();}],
     ["[data-heat-cprev]",()=>{columnPage--;load();}],
     ["[data-heat-cnext]",()=>{columnPage++;load();}],
     ["[data-heat-stack]",()=>{historyMode="stacked";render();}],
     ["[data-heat-lines]",()=>{historyMode="lines";render();}],
     ["[data-heat-back]",()=>{detail=null;branch=-1;render();}],
     ["[data-heat-suggestions]",getSuggestions],
     ["[data-heat-clear-slice]",()=>{activeSlice="";render();}]];
   buttons.forEach(([selector,fn])=>{const node=id(selector);if(node)node.onclick=fn;});
   element.querySelectorAll("[data-heat-collapse]").forEach(el=>el.onclick=()=>{
     const key=el.dataset.heatCollapse;
     if(collapsed.has(key))collapsed.delete(key);else collapsed.add(key);render();});
   element.querySelectorAll("[data-heat-cell]").forEach(el=>el.onclick=()=>{
     const [task,kind,candidate]=el.dataset.heatCell.split("|");
     inspect(task,kind,candidate);});
   element.querySelectorAll("[data-heat-point]").forEach(el=>el.onclick=()=>{
     revision=el.dataset.heatPoint;load();});
   element.querySelectorAll("[data-heat-branch]").forEach(el=>el.onclick=()=>{
     const n=Number(el.dataset.heatBranch);branch=branch===n?-1:n;render();});
   element.querySelectorAll("[data-heat-slice]").forEach(el=>el.onclick=()=>{
     activeSlice=activeSlice===el.dataset.heatSlice?"":el.dataset.heatSlice;
     render();
     info(activeSlice?"Matrix filtered to "+activeSlice+
       " among the saved portfolio; no unselected alternative contributes.":"All alternative comparisons shown.");
   });
 }
 async function inspect(task_id,kind,candidate_id){
   const chosen=matrix&&matrix.cells.find(c=>c.task_id===task_id&&
     c.kind===kind&&c.candidate_id===candidate_id);
   if(!chosen||!chosen.selected||!scenario){
     detail={error:"This alternative is not selected in the saved portfolio. " +
       "Edit a scenario in Annual Opportunity Scenarios to inspect exact original sources. " +
       "Exploration does not trigger deployment."};
     branch=-1;render();return;
   }
   const n=++seq;
   info("Loading exact authorized source lineage…");
   try{const result=await provider.explain({
     profile_id:profile,scenario_id:scenario,revision,task_id,kind,candidate_id});
     if(n!==seq||!available)return;
     detail=result;branch=-1;info("");render();
   }catch(e){if(n!==seq)return;detail={error:e.message};info(e.message);render();}
 }
 async function getSuggestions(){
   const n=++seq;info("Comparing current published alternatives without ranking quality…");
   try{const result=await provider.suggestions({profile_id:profile,limit:40});
     if(!available||n!==seq)return;suggestions=result;info("");render();
   }catch(e){if(n!==seq)return;info(e.message);}
 }
 async function load(){
   if(!available)return;
   const n=++seq;detail=null;suggestions=null;matrix=null;insights=null;
   if(!profile){render();info("Choose a population to view authorized annual economics.");return;}
   info("Loading paginated Task × configuration economic projections…");
   try{
     const args={profile_id:profile,scenario_id:scenario,revision};
     // As-of history and the same current portfolio are authoritative Server responses.
     const r=await Promise.all([
       provider.insights(args),
       provider.heatmap({...args,row_page:rowPage,column_page:columnPage,
         row_size:8,column_size:8,period:"annual"})]);
     if(!available||n!==seq)return;
     insights=r[0];matrix=r[1];render();info("");
   }catch(e){if(n!==seq)return;info("No fallback or unqualified amount: "+e.message);}
 }
 async function refresh(){
   if(!available)return;
   const n=++seq;info("Loading protected population and saved scenarios…");
   try{const data=await provider.bootstrap();
     if(n!==seq||!available)return;profiles=data.profiles||[];scenarios=data.scenarios||[];
     if(!profiles.some(p=>p.id===profile))profile=profiles.length===1?profiles[0].id:"";
     if(!scenarios.some(s=>s.id===scenario&&s.profile_id===profile)){scenario="";revision="";}
     await load();
   }catch(e){if(n!==seq||!available)return;info("Protected data unavailable: "+e.message);}
 }
 function setAccess(canRead){
   available=!!canRead;++seq;matrix=null;insights=null;detail=null;branch=-1;
   element.hidden=!available;
   if(available){template();refresh();}else element.replaceChildren();
 }
 element.hidden=true;return {setAccess,refresh};
}
root.AICompassHeatmap={mount,serverProvider,demoProvider};
})(window);
