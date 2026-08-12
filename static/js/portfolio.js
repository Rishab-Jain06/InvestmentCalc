const HOLDINGS_KEY="investify_portfolio_holdings_v1";
const CASH_KEY="investify_portfolio_cash_v1";
const WATCH_KEY="investify_watchlist";
const AI_KEY="investify_portfolio_ai_review_v3";
const AI_CACHE_MS=15*60*1000;
const AI_CONTEXT_KEY="investify_pending_ai_context";
const ALLOCATION_CASH_KEY="investify_include_cash_allocation_v1";

const $=id=>document.getElementById(id);
const money=(v,d=2)=>Number.isFinite(Number(v)) ? Number(v).toLocaleString(undefined,{style:"currency",currency:"USD",minimumFractionDigits:d,maximumFractionDigits:d}) : "—";
const pct=v=>Number.isFinite(Number(v)) ? `${Number(v)>=0?"+":""}${Number(v).toFixed(2)}%` : "—";
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:0};
const uid=()=>`p_${Date.now()}_${Math.random().toString(16).slice(2)}`;
const safe=s=>String(s??"").replace(/[<>&"']/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;",'"':"&quot;","'":"&#39;"}[c]));
const dots=(label="Loading")=>`<span class="loading-dots">${label}</span>`;
let chart=null;
let editingHoldingId=null;
let editingCashId=null;
let holdings=load(HOLDINGS_KEY,[]);
let cash=load(CASH_KEY,[]);
let quoteCache={};
let portfolioRows=[];

function load(key,fallback){try{return JSON.parse(localStorage.getItem(key)||JSON.stringify(fallback));}catch{return fallback;}}
function save(key,val){localStorage.setItem(key,JSON.stringify(val));}
function error(msg){const e=$("portfolio-error");if(!e)return;e.textContent=msg;e.classList.remove("hidden");setTimeout(()=>e.classList.add("hidden"),4200);}
function getWatch(){return load(WATCH_KEY,["SPY","QQQ"]);}
function setWatch(x){save(WATCH_KEY,[...new Set(x.map(s=>String(s).toUpperCase()).filter(Boolean))]);}
function includeCashAllocation(){return $("include-cash-allocation")?.checked ?? true;}

async function fetchQuote(symbol){
  const s=String(symbol||"").trim().toUpperCase(); if(!s)return null;
  if(quoteCache[s] && Date.now()-quoteCache[s].ts<60000)return quoteCache[s].data;
  const r=await fetch(`/api/quote/${encodeURIComponent(s)}`);
  const q=await r.json(); if(q.error)throw Error(q.error);
  quoteCache[s]={ts:Date.now(),data:q}; return q;
}
async function buildPortfolioRows(){
  const out=[];
  for(const h of holdings){
    const symbol=String(h.symbol||"").toUpperCase();
    let q=null, quoteError=null;
    try{q=await fetchQuote(symbol);}catch(e){quoteError=e.message;}
    const price=num(q?.price), prev=num(q?.previous_close), shares=num(h.shares), avgCost=num(h.avg_cost);
    const value=shares*price, costBasis=shares*avgCost;
    const dayChange=(price && prev) ? (price-prev)*shares : 0;
    const dayPct=(prev && price) ? ((price-prev)/prev*100) : null;
    const totalReturn=value-costBasis, totalReturnPct=costBasis ? (totalReturn/costBasis*100) : null;
    out.push({...h,symbol,quote:q,quoteError,name:q?.name||symbol,sector:q?.sector||"Unknown",industry:q?.industry||"Unknown",price,previous_close:prev,value,costBasis,dayChange,dayPct,totalReturn,totalReturnPct});
  }
  return out;
}
function sortRows(rows){
  const key=$("portfolio-sort")?.value||"value";
  return [...rows].sort((a,b)=>{
    if(key==="symbol")return a.symbol.localeCompare(b.symbol);
    if(key==="day_pct")return num(b.dayChange)-num(a.dayChange);
    if(key==="day_dollar")return num(b.dayChange)-num(a.dayChange);
    if(key==="return_pct")return num(b.totalReturnPct)-num(a.totalReturnPct);
    if(key==="return_dollar")return num(b.totalReturn)-num(a.totalReturn);
    if(key==="cost_basis")return num(b.costBasis)-num(a.costBasis);
    return num(b.value)-num(a.value);
  });
}
function totals(rows){
  const cashTotal=cash.reduce((s,x)=>s+num(x.amount),0);
  const holdingsValue=rows.reduce((s,x)=>s+num(x.value),0);
  const costBasis=rows.reduce((s,x)=>s+num(x.costBasis),0);
  const dayChange=rows.reduce((s,x)=>s+num(x.dayChange),0);
  const totalReturn=rows.reduce((s,x)=>s+num(x.totalReturn),0);
  const totalValue=holdingsValue+cashTotal;
  const dayBase=holdingsValue-dayChange;
  return {cashTotal,holdingsValue,costBasis,dayChange,totalReturn,totalValue,dayPct:dayBase?dayChange/dayBase*100:0,totalReturnPct:costBasis?totalReturn/costBasis*100:0};
}
function colorClass(v){return Number(v)>=0?"positive":"negative";}
function renderSummary(rows){
  const t=totals(rows);
  $("portfolio-total").textContent=money(t.totalValue);
  $("portfolio-total-sub").textContent=`${money(t.holdingsValue)} invested · ${money(t.cashTotal)} cash`;
  $("portfolio-day").textContent=`${t.dayChange>=0?"+":""}${money(t.dayChange)}`;$("portfolio-day").className=colorClass(t.dayChange);
  $("portfolio-day-pct").textContent=pct(t.dayPct);$("portfolio-day-pct").className=colorClass(t.dayPct);
  $("portfolio-return").textContent=`${t.totalReturn>=0?"+":""}${money(t.totalReturn)}`;$("portfolio-return").className=colorClass(t.totalReturn);
  $("portfolio-return-pct").textContent=pct(t.totalReturnPct);$("portfolio-return-pct").className=colorClass(t.totalReturnPct);
  $("portfolio-cash").textContent=money(t.cashTotal);
  $("cash-count").textContent=`${cash.length} cash ${cash.length===1?"entry":"entries"}`;
  renderDonutMetric(rows);
}
function renderDonutMetric(rows){
  const t=totals(rows); const metric=$("portfolio-sort")?.value||"value";
  let main=money(t.totalValue,0), sub=`${t.totalReturn>=0?"+":""}${money(t.totalReturn,0)} (${pct(t.totalReturnPct)})`, cls=colorClass(t.totalReturn);
  if(metric==="invested_value"){main=money(t.holdingsValue,0);sub=`${t.totalValue?((t.holdingsValue/t.totalValue)*100).toFixed(1):"0.0"}% invested`;cls="";}
  else if(metric==="cash"){main=money(t.cashTotal,0);sub=`${t.totalValue?((t.cashTotal/t.totalValue)*100).toFixed(1):"0.0"}% cash`;cls="";}
  else if(metric==="cost_basis"){main=money(t.costBasis,0);sub="Total cost basis";cls="";}
  else if(metric==="day_dollar"){main=`${t.dayChange>=0?"+":""}${money(t.dayChange,0)}`;sub=`Today ${pct(t.dayPct)}`;cls=colorClass(t.dayChange);}
  else if(metric==="day_pct"){main=pct(t.dayPct);sub=`Today ${t.dayChange>=0?"+":""}${money(t.dayChange,0)}`;cls=colorClass(t.dayPct);}
  else if(metric==="return_dollar"){main=`${t.totalReturn>=0?"+":""}${money(t.totalReturn,0)}`;sub=`All-time ${pct(t.totalReturnPct)}`;cls=colorClass(t.totalReturn);}
  else if(metric==="return_pct"){main=pct(t.totalReturnPct);sub=`All-time ${t.totalReturn>=0?"+":""}${money(t.totalReturn,0)}`;cls=colorClass(t.totalReturnPct);}
  else if(metric==="symbol"){main=money(t.totalValue,0);sub=`${rows.length} holding${rows.length===1?"":"s"}`;cls="";}
  $("donut-total").textContent=main;$("donut-total").className=cls;$("donut-return").textContent=sub;$("donut-return").className=cls;
}

function allocationMetricValue(row, base){
  const key=$("portfolio-sort")?.value||"value";
  if(key==="day_dollar"||key==="day_pct")return {label:`${row.dayChange>=0?"+":""}${money(row.dayChange,2)}`, value:num(row.dayChange)};
  if(key==="return_dollar"||key==="return_pct")return {label:`${row.totalReturn>=0?"+":""}${money(row.totalReturn,2)}`, value:num(row.totalReturn)};
  if(key==="cost_basis")return {label:money(row.costBasis,2), value:num(row.costBasis)};
  return {label:`${base?((row.value/base)*100).toFixed(1):"0.0"}%`, value:num(row.value)};
}

function renderChart(rows){
  const t=totals(rows); const includeCash=includeCashAllocation();
  const sortedRows=sortRows(rows).filter(x=>x.value>0);
  const entries=sortedRows.map(x=>({label:x.symbol,value:x.value,row:x}));
  if(includeCash && t.cashTotal>0)entries.unshift({label:"Cash",value:t.cashTotal,row:null});
  const base=entries.reduce((s,e)=>s+e.value,0);
  const list=$("allocation-list");
  const metric=$("portfolio-sort")?.value||"value";
  const metricMode=["day_dollar","return_dollar","cost_basis","day_pct","return_pct"].includes(metric);
  const pctOnly=["day_pct","return_pct"].includes(metric);
  const dollarOnly=["day_dollar","return_dollar","cost_basis"].includes(metric);
  $("allocation-count").textContent=entries.length?`Top ${Math.min(5,entries.length)} of ${entries.length}`:"No allocation";
  list.classList.toggle("allocation-metric-list", metricMode);
  list.innerHTML=entries.length?entries.map(e=>{
    const w=base?e.value/base*100:0;
    let right=`${w.toFixed(1)}%`;
    let bar=`<i style="width:${Math.max(2,Math.min(100,w))}%"></i>`;
    if(e.row && metricMode){
      if(metric==="day_pct")right=pct(e.row.dayPct);
      else if(metric==="return_pct")right=pct(e.row.totalReturnPct);
      else if(metric==="day_dollar")right=`${e.row.dayChange>=0?"+":""}${money(e.row.dayChange,2)}`;
      else if(metric==="return_dollar")right=`${e.row.totalReturn>=0?"+":""}${money(e.row.totalReturn,2)}`;
      else if(metric==="cost_basis")right=money(e.row.costBasis,2);
      bar="";
    }else if(!e.row && metricMode){
      right=metric==="cost_basis"?money(t.cashTotal,2):"—";
      bar="";
    }
    const tone=e.row && metricMode ? colorClass(metric.includes("return") ? (metric==="return_pct"?e.row.totalReturnPct:e.row.totalReturn) : (metric==="day_pct"?e.row.dayPct:e.row.dayChange)) : "";
    return `<div class="${metricMode?'metric-row':''}"><span>${safe(e.label)}</span><strong class="${tone}">${right}</strong>${bar}</div>`;
  }).join(""):`<p class="small-muted">Add holdings or cash to see allocation.</p>`;
  const ctx=$("portfolio-chart"); if(!ctx || !window.Chart)return; if(chart)chart.destroy();
  chart=new Chart(ctx,{type:"doughnut",data:{labels:entries.map(e=>e.label),datasets:[{data:entries.map(e=>e.value),borderWidth:4}]},options:{responsive:true,maintainAspectRatio:false,cutout:"68%",plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>`${c.label}: ${money(c.raw)}`}}}}});
}
function renderHoldings(rows){
  const body=$("holdings-body"); const t=totals(rows); const sorted=sortRows(rows);
  const countEl=$("holdings-count"); if(countEl)countEl.textContent=sorted.length?`Showing 10 of ${sorted.length} holdings. Scroll to view the rest.`:"Showing 0 holdings.";
  if(!sorted.length){body.innerHTML=`<tr><td colspan="9" class="empty-cell">No holdings yet. Add your first position.</td></tr>`;return;}
  body.innerHTML=sorted.map(r=>{const weight=t.totalValue?r.value/t.totalValue*100:0;return `<tr>
      <td><a href="/stock/${safe(r.symbol)}" class="holding-symbol"><strong>${safe(r.symbol)}</strong><span>${safe(r.account||"")}</span></a></td>
      <td>${num(r.shares).toLocaleString(undefined,{maximumFractionDigits:4})}</td><td>${money(r.avg_cost)}</td><td>${r.price?money(r.price):"<span class='muted'>Unavailable</span>"}</td>
      <td><strong>${money(r.value)}</strong></td><td><span class="${colorClass(r.dayChange)}">${r.dayChange>=0?"+":""}${money(r.dayChange)}</span><small class="table-sub">${pct(r.dayPct)}</small></td>
      <td><span class="${colorClass(r.totalReturn)}">${r.totalReturn>=0?"+":""}${money(r.totalReturn)}</span><small class="table-sub">${pct(r.totalReturnPct)}</small></td><td>${weight.toFixed(1)}%</td>
      <td class="row-actions row-actions-icon"><button class="icon-action edit-icon" data-edit="${r.id}" title="Edit ${safe(r.symbol)}" aria-label="Edit ${safe(r.symbol)}">✎</button><button class="icon-action remove-icon" data-remove="${r.id}" title="Remove ${safe(r.symbol)}" aria-label="Remove ${safe(r.symbol)}">×</button></td></tr>`;}).join("");
  body.querySelectorAll("[data-edit]").forEach(b=>b.onclick=()=>editHolding(b.dataset.edit));
  body.querySelectorAll("[data-remove]").forEach(b=>b.onclick=()=>removeHolding(b.dataset.remove));
}
function renderCash(){
  const list=$("cash-list"); 
  if(!cash.length){list.innerHTML=`<p class="small-muted">No cash entered.</p>`;return;}
  list.innerHTML=cash.map(c=>`<div class="cash-row cash-row-editable">
    <div><strong>${safe(c.account||"Cash")}</strong><span>${money(c.amount)}</span></div>
    <div class="cash-actions">
      <button class="icon-action edit-icon" data-cash-edit="${c.id}" title="Edit cash" aria-label="Edit cash">✎</button>
      <button class="icon-action remove-icon" data-cash-remove="${c.id}" title="Remove cash" aria-label="Remove cash">×</button>
    </div>
  </div>`).join("");
  list.querySelectorAll("[data-cash-remove]").forEach(b=>b.onclick=()=>{cash=cash.filter(x=>x.id!==b.dataset.cashRemove);save(CASH_KEY,cash);if(editingCashId===b.dataset.cashRemove)clearCashForm();renderAll(false);});
  list.querySelectorAll("[data-cash-edit]").forEach(b=>b.onclick=()=>editCash(b.dataset.cashEdit));
}
function clearHoldingForm(){editingHoldingId=null;["holding-symbol","holding-shares","holding-cost","holding-notes"].forEach(id=>$(id).value="");$("holding-account").value="Robinhood";$("save-holding").textContent="Add Position";}
function clearCashForm(){editingCashId=null;$("cash-amount").value="";$("cash-account").value="Robinhood";$("save-cash").textContent="Add Cash";}
function editHolding(id){const h=holdings.find(x=>x.id===id); if(!h)return; editingHoldingId=id;$("holding-symbol").value=h.symbol||"";$("holding-shares").value=h.shares||"";$("holding-cost").value=h.avg_cost||"";$("holding-account").value=h.account||"Robinhood";$("holding-notes").value=h.notes||"";$("save-holding").textContent="Save Changes";document.querySelector(".portfolio-side")?.scrollIntoView({behavior:"smooth",block:"start"});}
function editCash(id){const c=cash.find(x=>x.id===id); if(!c)return; editingCashId=id;$("cash-account").value=c.account||"Cash";$("cash-amount").value=c.amount||"";$("save-cash").textContent="Save Cash";document.querySelector(".portfolio-side")?.scrollIntoView({behavior:"smooth",block:"center"});}
function removeHolding(id){if(!confirm("Remove this holding?"))return;holdings=holdings.filter(x=>x.id!==id);save(HOLDINGS_KEY,holdings);renderAll();}
async function resolveSymbolInput(input){const raw=(input?.value||"").trim();if(!raw)return "";if(window.InvestifySymbols?.resolveInput){try{return await window.InvestifySymbols.resolveInput(input);}catch{return raw.toUpperCase().replace(/[^A-Z0-9.\-]/g,"");}}return raw.toUpperCase().replace(/[^A-Z0-9.\-]/g,"");}
async function saveHolding(){const symbol=await resolveSymbolInput($("holding-symbol"));const shares=num($("holding-shares").value);const avg=num($("holding-cost").value);if(!symbol || shares<=0 || avg<0){error("Enter ticker/company, shares and average cost.");return;}const data={id:editingHoldingId||uid(),symbol,shares,avg_cost:avg,account:$("holding-account").value.trim()||"Robinhood",notes:$("holding-notes").value.trim(),updated_at:new Date().toISOString()};if(editingHoldingId)holdings=holdings.map(x=>x.id===editingHoldingId?data:x);else holdings.unshift(data);save(HOLDINGS_KEY,holdings);clearHoldingForm();renderAll();}
function saveCash(){const amount=num($("cash-amount").value);const account=$("cash-account").value.trim()||"Cash";if(amount<0 || !Number.isFinite(amount)){error("Enter a valid cash amount.");return;}const data={id:editingCashId||uid(),account,amount,updated_at:new Date().toISOString()};if(editingCashId)cash=cash.map(x=>x.id===editingCashId?data:x);else cash.unshift(data);save(CASH_KEY,cash);clearCashForm();renderAll(false);}
async function renderWatchlist(){
  const grid=$("watch-grid"), empty=$("watch-empty"); const syms=[...new Set(getWatch().map(x=>String(x).toUpperCase()).filter(Boolean))]; grid.innerHTML=""; empty.classList.toggle("hidden",syms.length>0);
  for(const s of syms){const row=document.createElement("div");row.className="watch-row-card";row.innerHTML=`<a href="/stock/${safe(s)}"><strong>${safe(s)}</strong><span class="watch-name">${dots("Loading")}</span></a><span class="watch-price">—</span><span class="watch-change muted">—</span><button class="remove-watch" data-s="${safe(s)}">×</button>`;grid.appendChild(row);try{const q=await fetchQuote(s);row.querySelector(".watch-name").textContent=q.name||s;row.querySelector(".watch-price").textContent=money(q.price);const c=num(q.percent_change);const ce=row.querySelector(".watch-change");ce.textContent=pct(c);ce.className=`watch-change ${colorClass(c)}`;}catch(e){row.querySelector(".watch-name").textContent="Unavailable";}}
  grid.querySelectorAll(".remove-watch").forEach(b=>b.onclick=()=>{setWatch(getWatch().filter(x=>String(x).toUpperCase()!==b.dataset.s));renderWatchlist();});
}
async function addWatch(){const i=$("watch-input");const s=await resolveSymbolInput(i);if(!s)return;setWatch([...getWatch(),s]);i.value="";renderWatchlist();}
function aggregateExposure(rows, field, totalValue){const m={};rows.forEach(r=>{const key=(r[field]||"Unknown").trim()||"Unknown";m[key]=(m[key]||0)+num(r.value);});return Object.entries(m).map(([name,value])=>({name,value,weight:totalValue?value/totalValue*100:0})).sort((a,b)=>b.value-a.value).slice(0,8);}
function portfolioFingerprint(payload){try{return btoa(unescape(encodeURIComponent(JSON.stringify({h:payload.holdings,c:payload.cash,t:payload.totals.totalValue})))).slice(0,180);}catch{return String(Date.now());}}
function portfolioSummaryForAI(){
  const t=totals(portfolioRows); const holdingsPayload=portfolioRows.map(r=>({symbol:r.symbol,name:r.name,sector:r.sector,industry:r.industry,shares:r.shares,avg_cost:r.avg_cost,current_price:r.price,market_value:r.value,today_change:r.dayChange,total_return:r.totalReturn,total_return_pct:r.totalReturnPct,account:r.account,weight:t.totalValue?r.value/t.totalValue*100:0}));
  const payload={generated_at:new Date().toISOString(),totals:t,holdings:holdingsPayload,sector_exposure:aggregateExposure(portfolioRows,"sector",t.totalValue),industry_exposure:aggregateExposure(portfolioRows,"industry",t.totalValue),largest_positions:[...holdingsPayload].sort((a,b)=>num(b.market_value)-num(a.market_value)).slice(0,5),cash:cash.map(c=>({account:c.account,amount:num(c.amount)})),watchlist:getWatch()};
  payload.fingerprint=portfolioFingerprint(payload); return payload;
}
function conciseBullets(card){
  if(card?.bullets?.length)return card.bullets.slice(0,3);
  const arr=[]; if(card?.diversification?.note)arr.push(card.diversification.note); if(card?.concentration?.note)arr.push(card.concentration.note); if(card?.market_positioning?.note)arr.push(card.market_positioning.note); if(card?.risks?.[0])arr.push(card.risks[0]); return arr.slice(0,3);
}
function renderAIReview(obj){
  const body=$("ai-review-body");
  if(!obj){body.innerHTML=`<p class="small-muted">Add holdings, refresh prices, then generate a quick portfolio health score.</p>`;return;}
  const when=obj.generated_at?new Date(obj.generated_at).toLocaleString():"Cached";
  $("ai-review-meta").textContent=`Last updated ${when} · ${obj.mode||"AI"}${obj.cached_local?" · local cache":""}`;
  const card=obj.review_card||obj.card;
  if(card){
    const bullets=conciseBullets(card);
    const labels=["Diversification","Gaps","Suggestions"];
    const score=card.health_score??"—";
    body.innerHTML=`
      <div class="portfolio-ai-skinny-v47">
        <div class="portfolio-ai-score-mini">
          <span>Portfolio health</span>
          <strong>${safe(card.health_label||"Balanced")}</strong>
        </div>
        <b>${safe(score)}${score!=="—"?"/100":""}</b>
      </div>
      <div class="portfolio-ai-three-points">
        ${labels.map((label,i)=>`<div><span>${label}</span><p>${safe(bullets[i]||"No major issue identified from available portfolio context.")}</p></div>`).join("")}
      </div>`;
    return;
  }
  body.innerHTML=`<p>${safe(obj.review||obj.answer||"No review returned.")}</p>`;
}
async function runAIReview(){
  if(!portfolioRows.length && !cash.length){error("Add at least one holding or cash entry first.");return;} const payload=portfolioSummaryForAI();
  try{const cached=JSON.parse(localStorage.getItem(AI_KEY)||"null"); if(cached?.fingerprint===payload.fingerprint && Date.now()-new Date(cached.generated_at||0).getTime()<AI_CACHE_MS){renderAIReview({...cached,cached_local:true});return;}}catch{}
  $("ai-review").disabled=true;$("ai-review").innerHTML=dots("Analyzing");$("ai-review-body").innerHTML=`<div class="portfolio-ai-loading">${dots("Building portfolio read")}</div>`;
  try{const r=await fetch("/api/portfolio/review",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const d=await r.json();if(d.error)throw Error(d.error);const value={...d,generated_at:new Date().toISOString(),fingerprint:payload.fingerprint};localStorage.setItem(AI_KEY,JSON.stringify(value));renderAIReview(value);}catch(e){$("ai-review-body").textContent="AI review unavailable. "+e.message;}
  finally{$("ai-review").disabled=false;$("ai-review").textContent="Analyze Portfolio";}
}
function askAIAboutPortfolio(){
  if(!portfolioRows.length && !cash.length){error("Add holdings or cash first.");return;}
  const payload=portfolioSummaryForAI();
  const prompt="Analyze my portfolio at a high level. Focus on diversification, concentration, sector/industry coverage, cash vs equity positioning, market outlook, and key risks. Keep it concise and do not repeat every holding.";
  localStorage.setItem(AI_CONTEXT_KEY,JSON.stringify({mode:"general",portfolio:payload,portfolio_prompt:prompt,created_at:new Date().toISOString()}));
  window.location.href="/search";
}
async function renderAll(refreshQuotes=true){if(refreshQuotes)quoteCache={};portfolioRows=await buildPortfolioRows();renderSummary(portfolioRows);renderChart(portfolioRows);renderHoldings(portfolioRows);renderCash();renderWatchlist();}

$("save-holding").onclick=saveHolding;
$("clear-holding-form").onclick=clearHoldingForm;
$("save-cash").onclick=saveCash;
$("clear-cash-form").onclick=clearCashForm;
const refreshTop=$("refresh-portfolio-top");
if(refreshTop) refreshTop.onclick=async()=>{refreshTop.disabled=true;refreshTop.innerHTML=dots("Refreshing");try{await renderAll(true);}finally{refreshTop.disabled=false;refreshTop.textContent="Refresh Portfolio";}};
$("portfolio-sort").onchange=()=>{renderHoldings(portfolioRows);renderChart(portfolioRows);renderDonutMetric(portfolioRows);};
$("include-cash-allocation").checked=load(ALLOCATION_CASH_KEY,true)!==false;
$("include-cash-allocation").onchange=()=>{save(ALLOCATION_CASH_KEY,$("include-cash-allocation").checked);renderChart(portfolioRows);};
$("watch-add").onclick=addWatch;
$("watch-input").addEventListener("keydown",e=>{if(e.key==="Enter")addWatch();});
$("ai-review").onclick=runAIReview;
$("ask-ai-portfolio").onclick=askAIAboutPortfolio;

try{renderAIReview(JSON.parse(localStorage.getItem(AI_KEY)||"null"));}catch{}
renderAll(true);
