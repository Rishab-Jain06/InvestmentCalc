const HOLDINGS_KEY="investify_portfolio_holdings_v1";
const CASH_KEY="investify_portfolio_cash_v1";
const WATCH_KEY="investify_watchlist";
const OPTIONS_KEY="investify_portfolio_option_positions_v1";
const AI_KEY="investify_portfolio_ai_review_v3";
const AI_CACHE_MS=15*60*1000;
const AI_CONTEXT_KEY="investify_pending_ai_context";
const ALLOCATION_CASH_KEY="investify_include_cash_allocation_v1";
const QUOTE_CACHE_KEY="investify_portfolio_quote_cache_v51_1";
const QUOTE_CACHE_TTL_MS=5*60*1000;

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
let editingOptionId=null;
let holdings=load(HOLDINGS_KEY,[]);
let cash=load(CASH_KEY,[]);
let optionPositions=load(OPTIONS_KEY,[]);
let watchlistData=load(WATCH_KEY,["SPY","QQQ"]);
let quoteCache=load(QUOTE_CACHE_KEY,{});
let portfolioRows=[];
let optionQuoteRows=[];
let cloudMode=false;
let cloudUser=null;
let cloudSaveTimer=null;
let cloudSaving=false;
let cloudLoaded=false;

function load(key,fallback){try{return JSON.parse(localStorage.getItem(key)||JSON.stringify(fallback));}catch{return fallback;}}
function save(key,val){localStorage.setItem(key,JSON.stringify(val));}
function error(msg){const e=$("portfolio-error");if(!e)return;e.textContent=msg;e.classList.remove("hidden");setTimeout(()=>e.classList.add("hidden"),4200);}
function getWatch(){return cloudMode ? watchlistData : load(WATCH_KEY,["SPY","QQQ"]);}
function persistLocal(){save(HOLDINGS_KEY,holdings);save(CASH_KEY,cash);save(OPTIONS_KEY,optionPositions);save(WATCH_KEY,watchlistData);save(ALLOCATION_CASH_KEY,includeCashAllocation());}
function setWatch(x){watchlistData=[...new Set(x.map(s=>String(s).toUpperCase()).filter(Boolean))];persistData();}
function includeCashAllocation(){return $("include-cash-allocation")?.checked ?? true;}
function syncPill(text, live=false){const pill=$("portfolio-sync-pill");if(!pill)return;pill.textContent=text;pill.classList.toggle("sync-pill-live", !!live);}
function cloudBanner(html){const b=$("portfolio-cloud-banner");if(!b)return;b.innerHTML=html||"";b.classList.toggle("hidden", !html);}

function saveQuoteCache(){
  try{save(QUOTE_CACHE_KEY,quoteCache);}catch{}
}
function clearQuoteCache(){
  quoteCache={};
  try{localStorage.removeItem(QUOTE_CACHE_KEY);}catch{}
}
async function fetchQuote(symbol, force=false){
  const s=String(symbol||"").trim().toUpperCase(); if(!s)return null;
  const cached=quoteCache[s];
  if(!force && cached?.data && Date.now()-num(cached.ts)<QUOTE_CACHE_TTL_MS)return cached.data;
  const r=await fetch(`/api/quote/${encodeURIComponent(s)}`);
  const q=await r.json(); if(q.error)throw Error(q.error);
  quoteCache[s]={ts:Date.now(),data:q}; saveQuoteCache(); return q;
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
function signedOptionValue(o){
  const v=num(o.current_value);
  if(!v)return 0;
  if(o.strategy==="single") return o.position_side==="short" ? -v : v;
  return isCreditSpread(o) ? -v : v;
}
function optionBasis(o){
  const contracts=num(o.contracts)||1;
  const entry=num(o.entry_price);
  return Math.abs(entry*contracts*100);
}
function optionTotals(){
  const rows=optionQuoteRows||[];
  const optionsValue=rows.reduce((s,x)=>s+signedOptionValue(x),0);
  const optionsPnl=rows.reduce((s,x)=>s+num(x.pnl),0);
  const optionsBasis=rows.reduce((s,x)=>s+optionBasis(x),0);
  const pricedCount=rows.filter(x=>x.status==="priced").length;
  return {optionsValue,optionsPnl,optionsBasis,pricedCount,optionsCount:rows.length};
}
function totals(rows){
  const cashTotal=cash.reduce((s,x)=>s+num(x.amount),0);
  const holdingsValue=rows.reduce((s,x)=>s+num(x.value),0);
  const costBasis=rows.reduce((s,x)=>s+num(x.costBasis),0);
  const dayChange=rows.reduce((s,x)=>s+num(x.dayChange),0);
  const opt=optionTotals();
  const totalReturn=rows.reduce((s,x)=>s+num(x.totalReturn),0)+opt.optionsPnl;
  const totalValue=holdingsValue+cashTotal+opt.optionsValue;
  const totalBasis=costBasis+opt.optionsBasis;
  const dayBase=holdingsValue-dayChange;
  return {cashTotal,holdingsValue,costBasis,totalBasis,dayChange,totalReturn,totalValue,dayPct:dayBase?dayChange/dayBase*100:0,totalReturnPct:totalBasis?totalReturn/totalBasis*100:0,...opt};
}
function colorClass(v){return Number(v)>=0?"positive":"negative";}
function renderSummary(rows){
  const t=totals(rows);
  $("portfolio-total").textContent=money(t.totalValue);
  $("portfolio-total-sub").textContent=`${money(t.holdingsValue)} stocks · ${money(t.optionsValue)} options · ${money(t.cashTotal)} cash`;
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
  list.querySelectorAll("[data-cash-remove]").forEach(b=>b.onclick=()=>{cash=cash.filter(x=>x.id!==b.dataset.cashRemove);persistData();if(editingCashId===b.dataset.cashRemove)clearCashForm();renderAll(false);});
  list.querySelectorAll("[data-cash-edit]").forEach(b=>b.onclick=()=>editCash(b.dataset.cashEdit));
}
function clearHoldingForm(){editingHoldingId=null;["holding-symbol","holding-shares","holding-cost","holding-notes"].forEach(id=>$(id).value="");$("holding-account").value="Robinhood";$("save-holding").textContent="Add Position";}
function clearCashForm(){editingCashId=null;$("cash-amount").value="";$("cash-account").value="Robinhood";$("save-cash").textContent="Add Cash";}
function editHolding(id){const h=holdings.find(x=>x.id===id); if(!h)return; editingHoldingId=id;$("holding-symbol").value=h.symbol||"";$("holding-shares").value=h.shares||"";$("holding-cost").value=h.avg_cost||"";$("holding-account").value=h.account||"Robinhood";$("holding-notes").value=h.notes||"";$("save-holding").textContent="Save Changes";document.querySelector(".portfolio-side")?.scrollIntoView({behavior:"smooth",block:"start"});}
function editCash(id){const c=cash.find(x=>x.id===id); if(!c)return; editingCashId=id;$("cash-account").value=c.account||"Cash";$("cash-amount").value=c.amount||"";$("save-cash").textContent="Save Cash";document.querySelector(".portfolio-side")?.scrollIntoView({behavior:"smooth",block:"center"});}
function removeHolding(id){if(!confirm("Remove this holding?"))return;holdings=holdings.filter(x=>x.id!==id);persistData();renderAll(false);}
async function resolveSymbolInput(input){const raw=(input?.value||"").trim();if(!raw)return "";if(window.InvestifySymbols?.resolveInput){try{return await window.InvestifySymbols.resolveInput(input);}catch{return raw.toUpperCase().replace(/[^A-Z0-9.\-]/g,"");}}return raw.toUpperCase().replace(/[^A-Z0-9.\-]/g,"");}
async function saveHolding(){const symbol=await resolveSymbolInput($("holding-symbol"));const shares=num($("holding-shares").value);const avg=num($("holding-cost").value);if(!symbol || shares<=0 || avg<0){error("Enter ticker/company, shares and average cost.");return;}const data={id:editingHoldingId||uid(),symbol,shares,avg_cost:avg,account:$("holding-account").value.trim()||"Robinhood",notes:$("holding-notes").value.trim(),updated_at:new Date().toISOString()};if(editingHoldingId)holdings=holdings.map(x=>x.id===editingHoldingId?data:x);else holdings.unshift(data);persistData();clearHoldingForm();renderAll(false);}
function saveCash(){const amount=num($("cash-amount").value);const account=$("cash-account").value.trim()||"Cash";if(amount<0 || !Number.isFinite(amount)){error("Enter a valid cash amount.");return;}const data={id:editingCashId||uid(),account,amount,updated_at:new Date().toISOString()};if(editingCashId)cash=cash.map(x=>x.id===editingCashId?data:x);else cash.unshift(data);persistData();clearCashForm();renderAll(false);}

function normalizeOptionPosition(o){
  const strategy=String(o.strategy||"single").toLowerCase()==="vertical"?"vertical":"single";
  const spread=String(o.spread_type||"put_credit").toLowerCase();
  let type=String(o.option_type||"call").toLowerCase()==="put"?"put":"call";
  if(strategy==="vertical") type=spread.startsWith("call")?"call":"put";
  const side=String(o.position_side||"long").toLowerCase()==="short"?"short":"long";
  return {
    id:o.id||uid(),strategy,spread_type:spread,underlying:String(o.underlying||o.symbol||"").toUpperCase(),option_type:type,position_side:side,
    expiration:String(o.expiration||"").slice(0,10),strike:o.strike==null?null:num(o.strike),short_strike:o.short_strike==null?null:num(o.short_strike),long_strike:o.long_strike==null?null:num(o.long_strike),
    contracts:num(o.contracts)||1,entry_price:num(o.entry_price),account:o.account||"Brokerage",notes:o.notes||"",opened_at:o.opened_at||new Date().toISOString().slice(0,10),updated_at:o.updated_at||o.created_at||new Date().toISOString()
  };
}
function isCreditSpread(o){return String(o.spread_type||"").includes("credit");}
function optionStrategyLabel(o){
  if(o.strategy==="single") return `${o.position_side==="short"?"Short":"Long"} ${o.option_type==="put"?"Put":"Call"}`;
  const m={put_credit:"Put Credit",call_credit:"Call Credit",put_debit:"Put Debit",call_debit:"Call Debit"};
  return `${m[o.spread_type]||"Vertical"} Spread`;
}
function optionStrikeLabel(o){
  if(o.strategy==="single") return `${num(o.strike).toLocaleString(undefined,{maximumFractionDigits:2})}${o.option_type==="put"?"P":"C"}`;
  return `${num(o.short_strike).toLocaleString(undefined,{maximumFractionDigits:2})}/${num(o.long_strike).toLocaleString(undefined,{maximumFractionDigits:2})}`;
}
function optionQtyLabel(o){return `${num(o.contracts).toLocaleString(undefined,{maximumFractionDigits:0})}x`; }
function optionEntryLabel(o){
  if(o.strategy==="vertical") return `${isCreditSpread(o)?"Credit":"Debit"} ${money(o.entry_price)}`;
  return `${o.position_side==="short"?"Credit":"Debit"} ${money(o.entry_price)}`;
}
function setOptionFormMode(){
  const strategy=$("option-strategy")?.value||"single";
  const isVertical=strategy==="vertical";
  $("option-spread-type-wrap")?.classList.toggle("hidden", !isVertical);
  $("option-type-wrap")?.classList.toggle("hidden", isVertical);
  $("option-side-wrap")?.classList.toggle("hidden", isVertical);
  $("option-strike-wrap")?.classList.toggle("hidden", isVertical);
  $("option-short-strike-wrap")?.classList.toggle("hidden", !isVertical);
  $("option-long-strike-wrap")?.classList.toggle("hidden", !isVertical);
  const label=$("option-entry-label");
  if(label) label.textContent=isVertical ? "Net credit/debit" : "Entry premium";
  const btn=$("save-option-position");
  if(btn) btn.textContent=editingOptionId ? "Save Option" : (isVertical ? "Add Spread" : "Add Contract");
}
function clearOptionForm(){
  editingOptionId=null;
  ["option-underlying","option-expiration","option-strike","option-short-strike","option-long-strike","option-entry-price","option-notes"].forEach(id=>{const el=$(id); if(el)el.value="";});
  if($("option-strategy"))$("option-strategy").value="single";
  if($("option-spread-type"))$("option-spread-type").value="put_credit";
  if($("option-type"))$("option-type").value="call";
  if($("option-side"))$("option-side").value="long";
  if($("option-contracts"))$("option-contracts").value="1";
  if($("option-account"))$("option-account").value="Robinhood";
  setOptionFormMode();
}
async function saveOptionPosition(){
  const underlying=await resolveSymbolInput($("option-underlying"));
  const strategy=$("option-strategy")?.value||"single";
  const expiration=$("option-expiration")?.value||"";
  const contracts=num($("option-contracts")?.value)||1;
  const entry=num($("option-entry-price")?.value);
  if(!underlying || !expiration || contracts<=0 || entry<0){error("Enter underlying, expiration, contracts and entry price.");return;}
  let data={id:editingOptionId||uid(),strategy,underlying,expiration,contracts,entry_price:entry,account:$("option-account")?.value.trim()||"Robinhood",notes:$("option-notes")?.value.trim()||"",opened_at:new Date().toISOString().slice(0,10),updated_at:new Date().toISOString()};
  if(strategy==="vertical"){
    const spread=$("option-spread-type")?.value||"put_credit";
    const shortStrike=num($("option-short-strike")?.value), longStrike=num($("option-long-strike")?.value);
    if(shortStrike<=0 || longStrike<=0 || shortStrike===longStrike){error("Enter different long and short strikes for the spread.");return;}
    data={...data,spread_type:spread,option_type:spread.startsWith("call")?"call":"put",position_side:"spread",short_strike:shortStrike,long_strike:longStrike,strike:null};
  }else{
    const strike=num($("option-strike")?.value); if(strike<=0){error("Enter a valid strike.");return;}
    data={...data,option_type:$("option-type")?.value||"call",position_side:$("option-side")?.value||"long",strike,short_strike:null,long_strike:null,spread_type:null};
  }
  if(editingOptionId){
    const existing=optionPositions.find(x=>x.id===editingOptionId);
    if(existing?.opened_at)data.opened_at=existing.opened_at;
    optionPositions=optionPositions.map(x=>x.id===editingOptionId?data:x);
  }else optionPositions.unshift(data);
  persistData();clearOptionForm();await renderAll(false);
}
function editOptionPosition(id){
  const o=optionPositions.find(x=>x.id===id); if(!o)return; editingOptionId=id;
  $("option-strategy").value=o.strategy||"single"; setOptionFormMode();
  $("option-underlying").value=o.underlying||""; $("option-expiration").value=o.expiration||""; $("option-contracts").value=o.contracts||1; $("option-entry-price").value=o.entry_price||""; $("option-account").value=o.account||"Robinhood"; $("option-notes").value=o.notes||"";
  if(o.strategy==="vertical"){ $("option-spread-type").value=o.spread_type||"put_credit"; $("option-short-strike").value=o.short_strike||""; $("option-long-strike").value=o.long_strike||""; }
  else { $("option-type").value=o.option_type||"call"; $("option-side").value=o.position_side||"long"; $("option-strike").value=o.strike||""; }
  setOptionFormMode(); document.querySelector("#option-entry-card")?.scrollIntoView({behavior:"smooth",block:"start"});
}
function removeOptionPosition(id){if(!confirm("Remove this option position?"))return;optionPositions=optionPositions.filter(x=>x.id!==id);persistData();if(editingOptionId===id)clearOptionForm();renderAll(false);}
async function buildOptionRows(){
  const normalized=optionPositions.map(normalizeOptionPosition).filter(x=>x.underlying&&x.expiration);
  if(!normalized.length)return [];
  try{const d=await fetchJson("/api/options/portfolio-value",{method:"POST",body:JSON.stringify({positions:normalized})});return d.positions||normalized;}
  catch(e){error("Options quotes unavailable: "+e.message);return normalized.map(x=>({...x,status:"unpriced",message:e.message,current_price:null,current_value:null,pnl:null,pnl_pct:null}));}
}
function renderOptionPositions(rows){
  const body=$("options-positions-body"), count=$("options-count"); if(!body)return;
  const priced=rows.filter(r=>r.status==="priced"); const totalValue=rows.reduce((s,r)=>s+signedOptionValue(r),0); const totalPnl=rows.reduce((s,r)=>s+num(r.pnl),0);
  if(count)count.textContent=rows.length?`Showing ${rows.length} option ${rows.length===1?"position":"positions"}. ${priced.length} priced from live/delayed chains.`:"Showing 0 option positions.";
  if($("options-total-value"))$("options-total-value").textContent=`Value ${rows.length?money(totalValue):"—"}`;
  if($("options-total-pnl")){ $("options-total-pnl").textContent=`P/L ${rows.length?(totalPnl>=0?"+":"")+money(totalPnl):"—"}`; $("options-total-pnl").className=rows.length?colorClass(totalPnl):""; }
  if(!rows.length){body.innerHTML=`<tr><td colspan="9" class="empty-cell">No options yet. Add your first contract or vertical spread.</td></tr>`;return;}
  body.innerHTML=rows.map(r=>{
    const current=r.current_price==null?"—":money(r.current_price); const pnl=r.pnl==null?"—":`${r.pnl>=0?"+":""}${money(r.pnl)}`; const pnlPct=r.pnl_pct==null?"":"<small class='table-sub'>"+pct(r.pnl_pct)+"</small>";
    const msg=r.message?`<small class="table-sub muted">${safe(r.message)}</small>`:(r.delayed?`<small class="table-sub muted">delayed</small>`:"");
    return `<tr>
      <td><strong>${safe(optionStrategyLabel(r))}</strong><small class="table-sub">${safe(r.account||"")}</small></td>
      <td><a href="/stock/${safe(r.underlying)}"><strong>${safe(r.underlying)}</strong></a></td>
      <td>${safe(r.expiration||"—")}<small class="table-sub">${r.dte==null?"":r.dte+" DTE"}</small></td>
      <td>${safe(optionStrikeLabel(r))}</td>
      <td>${optionQtyLabel(r)}</td>
      <td>${optionEntryLabel(r)}</td>
      <td>${current}${msg}</td>
      <td><span class="${r.pnl==null?"":colorClass(r.pnl)}">${pnl}</span>${pnlPct}</td>
      <td class="row-actions row-actions-icon"><button class="icon-action analyze-icon" data-option-ai="${safe(r.id)}" title="Analyze option" aria-label="Analyze option">AI</button><button class="icon-action edit-icon" data-option-edit="${safe(r.id)}" title="Edit option" aria-label="Edit option">✎</button><button class="icon-action remove-icon" data-option-remove="${safe(r.id)}" title="Remove option" aria-label="Remove option">×</button></td>
    </tr>`;
  }).join("");
  body.querySelectorAll("[data-option-edit]").forEach(b=>b.onclick=()=>editOptionPosition(b.dataset.optionEdit));
  body.querySelectorAll("[data-option-remove]").forEach(b=>b.onclick=()=>removeOptionPosition(b.dataset.optionRemove));
  body.querySelectorAll("[data-option-ai]").forEach(b=>b.onclick=()=>askAIAboutOption(b.dataset.optionAi));
}
function askAIAboutOption(id){
  const row=optionQuoteRows.find(x=>x.id===id)||optionPositions.find(x=>x.id===id); if(!row)return;
  localStorage.setItem(AI_CONTEXT_KEY,JSON.stringify({mode:"options",option_position:row,portfolio:portfolioSummaryForAI(),created_at:new Date().toISOString(),portfolio_prompt:"Analyze this tracked option position. Explain current P/L, main risks, expiration risk, and what to watch next."}));
  window.location.href="/search";
}
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
  const payload={generated_at:new Date().toISOString(),totals:t,holdings:holdingsPayload,option_positions:optionQuoteRows.map(normalizeOptionPosition),sector_exposure:aggregateExposure(portfolioRows,"sector",t.totalValue),industry_exposure:aggregateExposure(portfolioRows,"industry",t.totalValue),largest_positions:[...holdingsPayload].sort((a,b)=>num(b.market_value)-num(a.market_value)).slice(0,5),cash:cash.map(c=>({account:c.account,amount:num(c.amount)})),watchlist:getWatch()};
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

function normalizeCloudHolding(h){return {id:h.id||uid(),symbol:String(h.symbol||"").toUpperCase(),shares:num(h.shares),avg_cost:num(h.average_cost??h.avg_cost),account:h.account||"Brokerage",notes:h.notes||"",updated_at:h.updated_at||h.created_at||new Date().toISOString()};}
function normalizeCloudCash(c){return {id:c.id||uid(),account:c.account||"Cash",amount:num(c.amount),updated_at:c.updated_at||c.created_at||new Date().toISOString()};}
function normalizeCloudOption(o){return normalizeOptionPosition(o);}
function cloudSettingsPayload(){return {theme:localStorage.getItem("investify_theme")||"system",hide_portfolio_value:localStorage.getItem("investify_home_portfolio_hidden_v1")==="1",app_preferences:{include_cash_allocation:includeCashAllocation(),default_ticker:localStorage.getItem("investify_default_ticker")||"SPY",default_range:localStorage.getItem("investify_default_range")||"1D"},ai_preferences:{ai_mode:localStorage.getItem("investify_ai_mode")||"general",answer_style:localStorage.getItem("investify_answer_style")||"short"}};}
function localHasPortfolio(){let w=0;try{const raw=localStorage.getItem(WATCH_KEY);w=raw?JSON.parse(raw).length:0;}catch{}return load(HOLDINGS_KEY,[]).length || load(CASH_KEY,[]).length || load(OPTIONS_KEY,[]).length || w;}
function cloudEmpty(){return !holdings.length && !cash.length && !optionPositions.length && (!watchlistData.length || watchlistData.join(",")==="SPY,QQQ");}
async function fetchJson(url, options={}){const r=await fetch(url,{cache:"no-store",...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});const d=await r.json().catch(()=>({}));if(!r.ok||d.error)throw Error(d.error||`Request failed: ${r.status}`);return d;}
function applyCloudBundle(d){holdings=(d.holdings||[]).map(normalizeCloudHolding);cash=(d.cash||[]).map(normalizeCloudCash);optionPositions=(d.option_positions||[]).map(normalizeCloudOption);watchlistData=(d.watchlist||[]).map(x=>String(x.symbol||x).toUpperCase()).filter(Boolean);if(!watchlistData.length)watchlistData=["SPY","QQQ"];const prefs=d.settings?.app_preferences||{};if(prefs.include_cash_allocation!==undefined && $("include-cash-allocation"))$("include-cash-allocation").checked=!!prefs.include_cash_allocation;if(d.settings?.theme){localStorage.setItem("investify_theme",d.settings.theme);if(window.applyTheme)window.applyTheme();}if(prefs.default_ticker)localStorage.setItem("investify_default_ticker",prefs.default_ticker);if(prefs.default_range)localStorage.setItem("investify_default_range",prefs.default_range);}
async function saveCloudNow(){if(!cloudMode||cloudSaving)return;cloudSaving=true;syncPill("Saving to account…",true);try{const d=await fetchJson("/api/cloud/portfolio",{method:"PUT",body:JSON.stringify({holdings,cash,option_positions:optionPositions,watchlist:getWatch(),settings:cloudSettingsPayload()})});applyCloudBundle(d);syncPill("Cloud portfolio · Live quote refresh",true);}catch(e){syncPill("Cloud save issue · Using current browser copy",false);error("Cloud save failed: "+e.message);}finally{cloudSaving=false;}}
function persistData(){if(cloudMode){clearTimeout(cloudSaveTimer);cloudSaveTimer=setTimeout(saveCloudNow,450);}else{persistLocal();syncPill("Local portfolio · Login to sync",false);}}
async function importLocalToCloud(){const localHoldings=load(HOLDINGS_KEY,[]), localCash=load(CASH_KEY,[]), localOptions=load(OPTIONS_KEY,[]), localWatch=load(WATCH_KEY,["SPY","QQQ"]);holdings=localHoldings;cash=localCash;optionPositions=localOptions;watchlistData=localWatch;cloudBanner("");await saveCloudNow();await renderAll(false);}
async function initCloud(){try{const me=await fetchJson("/api/auth/me");if(!me.authenticated){cloudMode=false;watchlistData=load(WATCH_KEY,["SPY","QQQ"]);syncPill("Local portfolio · Login to sync",false);cloudBanner(`<div><strong>Want cloud sync?</strong><p>Create a free account to save portfolio, watchlist and settings across devices.</p></div><div class="cloud-banner-actions"><a class="secondary-button" href="/login?next=/portfolio">Login</a><a class="secondary-button" href="/signup?next=/portfolio">Sign up</a></div>`);return;}cloudMode=true;cloudUser=me.user;syncPill("Loading cloud portfolio…",true);const d=await fetchJson("/api/cloud/portfolio");const localExists=localHasPortfolio();applyCloudBundle(d);cloudLoaded=true;syncPill("Cloud portfolio · Live quote refresh",true);if(localExists && cloudEmpty()){cloudBanner(`<div><strong>Import local portfolio?</strong><p>We found portfolio/watchlist data saved in this browser. Save it to your account.</p></div><div class="cloud-banner-actions"><button id="import-local-cloud" class="secondary-button" type="button">Import to account</button><button id="dismiss-cloud-import" class="secondary-button" type="button">Not now</button></div>`);setTimeout(()=>{$("import-local-cloud")?.addEventListener("click",importLocalToCloud);$("dismiss-cloud-import")?.addEventListener("click",()=>cloudBanner(""));},0);}else{cloudBanner("");}}catch(e){cloudMode=false;syncPill("Local portfolio · Cloud unavailable",false);error("Cloud sync unavailable: "+e.message);}}
async function renderAll(refreshQuotes=false){if(refreshQuotes)clearQuoteCache();portfolioRows=await buildPortfolioRows();optionQuoteRows=await buildOptionRows();renderSummary(portfolioRows);renderChart(portfolioRows);renderHoldings(portfolioRows);renderOptionPositions(optionQuoteRows);renderCash();renderWatchlist();}
async function initPortfolioApp(){await initCloud();try{renderAIReview(JSON.parse(localStorage.getItem(AI_KEY)||"null"));}catch{}await renderAll(false);}

$("save-holding").onclick=saveHolding;
$("clear-holding-form").onclick=clearHoldingForm;
$("save-cash").onclick=saveCash;
$("clear-cash-form").onclick=clearCashForm;
$("option-strategy")?.addEventListener("change",setOptionFormMode);
$("option-spread-type")?.addEventListener("change",setOptionFormMode);
$("save-option-position")?.addEventListener("click",saveOptionPosition);
$("clear-option-form")?.addEventListener("click",clearOptionForm);
setOptionFormMode();
const refreshTop=$("refresh-portfolio-top");
if(refreshTop) refreshTop.onclick=async()=>{refreshTop.disabled=true;refreshTop.innerHTML=dots("Refreshing");try{await renderAll(true);}finally{refreshTop.disabled=false;refreshTop.textContent="Refresh Portfolio";}};
$("portfolio-sort").onchange=()=>{renderHoldings(portfolioRows);renderChart(portfolioRows);renderDonutMetric(portfolioRows);};
$("include-cash-allocation").checked=load(ALLOCATION_CASH_KEY,true)!==false;
$("include-cash-allocation").onchange=()=>{persistData();renderChart(portfolioRows);};
$("watch-add").onclick=addWatch;
$("watch-input").addEventListener("keydown",e=>{if(e.key==="Enter")addWatch();});
$("ai-review").onclick=runAIReview;
$("ask-ai-portfolio").onclick=askAIAboutPortfolio;

initPortfolioApp();
