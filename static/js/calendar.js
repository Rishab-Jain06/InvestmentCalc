function dots(label="Loading"){return `<span class="loading-dots">${label}</span>`;}
const $=id=>document.getElementById(id);
const HOLDINGS_KEY="investify_portfolio_holdings_v1";
const WATCH_KEY="investify_watchlist";
const CAL_CACHE_PREFIX="investify_calendar_cache_v45:";
const CAL_CACHE_TTL_MS=24*60*60*1000;
const money=v=>Number.isFinite(Number(v))?Number(v).toLocaleString(undefined,{style:"currency",currency:"USD",maximumFractionDigits:0}):"—";
const fmtVal=v=>v===null||v===undefined||v===""?"—":String(v);
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:null};
const safe=s=>String(s??"").replace(/[<>&"\']/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;",'"':"&quot;","\'":"&#39;"}[c]));
let current=new Date(); current.setDate(1);
let events=[]; let selectedEvent=null; let lastPayload=null; let resolvedSymbols=[];

function load(key,fallback){try{return JSON.parse(localStorage.getItem(key)||JSON.stringify(fallback));}catch{return fallback;}}
function error(msg){const e=$("calendar-error");e.textContent=msg;e.classList.remove("hidden");setTimeout(()=>e.classList.add("hidden"),6000);}
function ymd(d){return d.toISOString().slice(0,10);}
function monthBounds(){const start=new Date(current.getFullYear(),current.getMonth(),1);const end=new Date(current.getFullYear(),current.getMonth()+1,0);return {start:ymd(start),end:ymd(end)};}
function holdingsSymbols(){return [...new Set(load(HOLDINGS_KEY,[]).map(x=>String(x.symbol||"").trim().toUpperCase()).filter(Boolean))];}
function watchSymbols(){return [...new Set(load(WATCH_KEY,["SPY","QQQ"]).map(x=>String(x||"").trim().toUpperCase()).filter(Boolean))];}
function cleanTicker(v){return String(v||"").trim().toUpperCase().replace(/[^A-Z0-9.\-]/g,"");}
async function resolveSymbolText(text){
  const raw=String(text||"").trim(); if(!raw)return "";
  if(/^[A-Z0-9.\-]{1,7}$/.test(raw) && raw===raw.toUpperCase())return cleanTicker(raw);
  try{const rows=await window.InvestifySymbols?.search?.(raw); if(rows?.[0]?.symbol)return cleanTicker(rows[0].symbol);}catch{}
  return cleanTicker(raw);
}
async function selectedSymbols(){
  const view=$("earnings-view")?.value||"portfolio_watchlist";
  if(view==="all")return {symbols:[],restrict:false,view};
  if(view==="portfolio")return {symbols:holdingsSymbols(),restrict:true,view};
  if(view==="watchlist")return {symbols:watchSymbols(),restrict:true,view};
  if(view==="portfolio_watchlist")return {symbols:[...new Set([...holdingsSymbols(),...watchSymbols()])],restrict:true,view};
  const parts=($("calendar-symbol-filter")?.value||"").split(/[,;]+/).map(x=>x.trim()).filter(Boolean).slice(0,25);
  const syms=[]; for(const p of parts){const s=await resolveSymbolText(p); if(s)syms.push(s);}
  return {symbols:[...new Set(syms)],restrict:true,view};
}
function toggleCustomFilter(){const custom=($("earnings-view")?.value||"")==="custom";$("custom-symbol-filter-wrap")?.classList.toggle("hidden",!custom);}
function cacheKey(sel){const {start,end}=monthBounds();return CAL_CACHE_PREFIX+[start,end,sel.view,sel.restrict,sel.symbols.join(",")].join(":");}
function setCacheMeta(text){const el=$("calendar-cache-meta"); if(el)el.textContent=text;}
function readCalendarCache(key){try{const raw=localStorage.getItem(key);if(!raw)return null;const payload=JSON.parse(raw);if(Date.now()-payload.saved_at>CAL_CACHE_TTL_MS)return null;return payload;}catch{return null;}}
function writeCalendarCache(key,data){try{localStorage.setItem(key,JSON.stringify({saved_at:Date.now(),data}));}catch{}}
async function loadCalendar(force=false){
  $("refresh-calendar").disabled=true; $("refresh-calendar").innerHTML=force?dots("Refreshing"):dots("Loading");
  const {start,end}=monthBounds(); const sel=await selectedSymbols(); resolvedSymbols=sel.symbols;
  const key=cacheKey(sel);
  if(!force){const cached=readCalendarCache(key); if(cached?.data){applyCalendarPayload(cached.data);setCacheMeta(`Loaded from browser cache · ${new Date(cached.saved_at).toLocaleString()}`);$("refresh-calendar").disabled=false;$("refresh-calendar").textContent="Refresh Calendar";return;}}
  const p=new URLSearchParams({start,end,restrict_to_symbols:sel.restrict?"1":"0"}); if(sel.symbols.length)p.set("symbols",sel.symbols.join(","));
  try{const r=await fetch(`/api/calendar/events?${p.toString()}`);const d=await r.json();if(d.error)throw Error(d.error);writeCalendarCache(key,d);applyCalendarPayload(d);const bits=[d.cache_layer?`server ${d.cache_layer}`:null,d.cached?"cached":"fresh"].filter(Boolean).join(" · ");setCacheMeta(`Updated ${new Date().toLocaleString()}${bits?` · ${bits}`:""} · browser cache 24h`);}catch(e){error(e.message);events=[];renderCalendar();}
  finally{$("refresh-calendar").disabled=false;$("refresh-calendar").textContent="Refresh Calendar";}
}
function applyCalendarPayload(d){lastPayload=d;events=d.events||[];$("earnings-count").textContent=d.counts?.earnings ?? events.filter(e=>e.type==="earnings").length;$("economic-count").textContent=d.counts?.economic ?? events.filter(e=>e.type==="economic").length;const errs=Object.entries(d.errors||{}).filter(([k,v])=>v).map(([k,v])=>`${k}: ${v}`);if(errs.length)error(errs.join(" · "));renderCalendar();}
function visibleEventsForDate(dateStr){const showE=$("show-earnings").checked, showM=$("show-economic").checked;return events.filter(e=>{if(e.date!==dateStr)return false;if(e.type==="earnings"&&!showE)return false;if(e.type==="economic"&&!showM)return false;return true;});}
function eventChip(e){const impact=String(e.impact||"").toLowerCase();const cls=[e.type, impact.includes("high")?"high-impact":""].join(" ");const title=e.type==="earnings" ? (e.symbol || e.title) : e.title;const sub=e.type==="earnings" ? (e.time_label || e.hour || "TBD") : `${e.time_label||""}${e.impact?` · ${e.impact}`:""}`;const desc=e.type==="economic"?(e.full_name||e.description||""):e.company||"";return `<button class="calendar-event ${cls}" data-id="${safe(e.id)}"><strong>${safe(title)}</strong><span>${safe(sub)}</span>${desc?`<em>${safe(desc)}</em>`:""}</button>`;}
function renderCalendar(){
  $("calendar-title").textContent=current.toLocaleString(undefined,{month:"long",year:"numeric"});
  const grid=$("calendar-grid"); const first=new Date(current.getFullYear(),current.getMonth(),1); const last=new Date(current.getFullYear(),current.getMonth()+1,0); const days=[]; for(let i=0;i<first.getDay();i++)days.push(null); for(let d=1;d<=last.getDate();d++)days.push(new Date(current.getFullYear(),current.getMonth(),d)); while(days.length%7!==0)days.push(null); const today=ymd(new Date());
  grid.innerHTML=days.map(day=>{if(!day)return `<div class="calendar-day empty"></div>`;const ds=ymd(day);const ev=visibleEventsForDate(ds);const earnings=ev.filter(e=>e.type==="earnings").length;const economic=ev.filter(e=>e.type==="economic").length;const counts=[earnings?`${earnings} ER`:null,economic?`${economic} macro`:null].filter(Boolean).join(" · ");return `<div class="calendar-day ${ds===today?"today":""}"><div class="calendar-date"><strong>${day.getDate()}</strong><span>${counts}</span></div><div class="calendar-events">${ev.slice(0,5).map(eventChip).join("")}${ev.length>5?`<button class="calendar-more" data-date="${ds}">+${ev.length-5} more</button>`:""}</div></div>`}).join("");
  grid.querySelectorAll(".calendar-event").forEach(b=>b.onclick=()=>selectEvent(events.find(e=>e.id===b.dataset.id)));
  grid.querySelectorAll(".calendar-more").forEach(b=>b.onclick=()=>showDayList(b.dataset.date));
}
function showDayList(dateStr){const ev=visibleEventsForDate(dateStr);const box=$("calendar-detail");box.innerHTML=`<p class="eyebrow">DAY EVENTS</p><h2>${new Date(dateStr+"T00:00:00").toLocaleDateString(undefined,{month:"long",day:"numeric",year:"numeric"})}</h2><p class="small-muted">${ev.length} visible event${ev.length===1?"":"s"}.</p><div class="event-list-detail">${ev.map(e=>`<button data-id="${safe(e.id)}">${eventChip(e)}</button>`).join("")}</div>`;box.querySelectorAll("[data-id]").forEach(b=>b.onclick=()=>selectEvent(events.find(e=>e.id===b.dataset.id)));}
function rev(v){const n=num(v);if(n==null)return "—";if(Math.abs(n)>=1e9)return `$${(n/1e9).toFixed(2)}B`;if(Math.abs(n)>=1e6)return `$${(n/1e6).toFixed(1)}M`;return money(n);}
function detailMetric(label,val,sub=""){return `<div><span>${safe(label)}</span><strong>${safe(val??"—")}</strong>${sub?`<small>${safe(sub)}</small>`:""}</div>`;}
function eventDetailsHtml(e,ai=""){if(!e)return "";if(e.type==="earnings"){return `<div class="detail-type-pill earnings">Earnings</div><h2>${safe(e.symbol)} earnings</h2><p class="small-muted">${safe(e.company||e.symbol)} · ${safe(e.date)} · ${safe(e.time_label||e.hour||"TBD")}</p><div class="detail-impact-strip"><span>Source: ${safe(e.earnings_source||e.source||"Alpha Vantage")}</span><span>${safe(e.fiscal_date_ending?`Fiscal period ${e.fiscal_date_ending}`:"Calendar estimate")}</span></div><div class="event-explain-block"><strong>What it is</strong><p>${safe(e.description||"Quarterly earnings report.")}</p></div><div class="event-explain-block"><strong>Why it matters</strong><p>${safe(e.why_it_matters||"Earnings can reset investor expectations.")}</p></div><div class="detail-metric-grid">${detailMetric("EPS Estimate",fmtVal(e.eps_estimate))}${detailMetric("EPS Actual",fmtVal(e.eps_actual))}${detailMetric("Revenue Est.",rev(e.revenue_estimate))}${detailMetric("Revenue Actual",rev(e.revenue_actual))}${detailMetric("Report Time",e.time_label||e.hour||"TBD")}${detailMetric("Currency",e.currency||"USD")}</div><div class="detail-actions"><a class="secondary-button" href="/stock/${safe(e.symbol)}">Open Research</a><button id="event-ai" class="secondary-button">AI Earnings Preview</button></div><div id="event-ai-box" class="event-ai-box">${ai||"Click AI Earnings Preview for what matters and what to watch."}</div>`;}
  const affected=(e.assets||[]).map(a=>`<span>${safe(a)}</span>`).join("");return `<div class="detail-type-pill economic">Macro</div><h2>${safe(e.title)}</h2><p class="small-muted">${safe(e.full_name||"")} · ${safe(e.date)} · ${safe(e.time_label||"")}</p><div class="detail-impact-strip"><span>${safe(e.impact||"Impact")} impact</span><span>${safe(e.value_source||e.source||"Investify + Alpha Vantage")}</span></div><div class="event-explain-block"><strong>What it is</strong><p>${safe(e.description||"Major macro event watched by markets.")}</p></div><div class="event-explain-block"><strong>Why it matters</strong><p>${safe(e.why_it_matters||"Investors watch this because it can affect growth expectations, rates and risk appetite.")}</p></div><div class="detail-metric-grid">${detailMetric("Latest / Actual",fmtVal(e.actual),e.actual_date?`as of ${e.actual_date}`:"when Alpha Vantage mapping exists")}${detailMetric("Previous",fmtVal(e.previous),e.previous_date?`as of ${e.previous_date}`:"")}${detailMetric("Forecast",fmtVal(e.estimate),"not provided by Alpha Vantage")}${detailMetric("Unit",e.unit||"—")}${detailMetric("Impact",e.impact||"—")}${detailMetric("Category",e.category||"—")}</div><div class="affected-assets"><strong>Usually affects</strong><div>${affected||"<span>SPY</span><span>QQQ</span><span>Treasuries</span><span>USD</span>"}</div></div><div class="economic-read-grid"><div><strong>Higher than expected</strong><p>${safe(e.higher_read||"May shift rate, growth and risk expectations.")}</p></div><div><strong>Lower than expected</strong><p>${safe(e.lower_read||"May shift rate, growth and risk expectations.")}</p></div></div>${e.value_note?`<p class="calendar-value-note">${safe(e.value_note)}</p>`:""}<p class="calendar-value-note">${safe(e.schedule_note||"Confirm official release date before trading.")}</p><div class="detail-actions"><button id="event-ai" class="secondary-button">AI Macro Explain</button></div><div id="event-ai-box" class="event-ai-box">${ai||"Click AI Macro Explain for a short beginner-friendly read."}</div>`;}
function selectEvent(e){selectedEvent=e;const box=$("calendar-detail");box.innerHTML=`<p class="eyebrow">DETAILS</p><h2>Loading event details…</h2><p class="small-muted">Using cached provider data when available.</p>`;fetch("/api/calendar/event-details",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({event:e})}).then(r=>r.json()).then(d=>{if(d.error)throw Error(d.error);selectedEvent=d.event||e;box.innerHTML=eventDetailsHtml(selectedEvent);box.querySelector("#event-ai")?.addEventListener("click",()=>runEventAI(selectedEvent));}).catch(err=>{box.innerHTML=eventDetailsHtml(e);box.querySelector("#event-ai")?.addEventListener("click",()=>runEventAI(e));error("Event details fallback: "+err.message);});}
function renderMarkdown(text){return String(text||"").split(/\n+/).filter(Boolean).map(line=>{const t=line.trim().replace(/^#+\s*/,"");if(/^[-•]\s+/.test(t))return `<li>${safe(t.replace(/^[-•]\s+/,""))}</li>`;if(t.length<65&&!/[.!?]$/.test(t))return `<h4>${safe(t)}</h4>`;return `<p>${safe(t).replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>")}</p>`;}).join("").replace(/(<li>.*<\/li>)/gs,"<ul>$1</ul>");}
async function runEventAI(e){const box=$("event-ai-box");box.innerHTML=dots("Generating explanation");try{const r=await fetch("/api/calendar/event-brief",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({event:e})});const d=await r.json();if(d.error)throw Error(d.error);if(d.event)selectedEvent=d.event;box.innerHTML=renderMarkdown(d.brief||"No explanation returned.");}catch(err){box.textContent="AI explanation unavailable. "+err.message;}}
$("prev-month").onclick=()=>{current=new Date(current.getFullYear(),current.getMonth()-1,1);loadCalendar(false);};
$("next-month").onclick=()=>{current=new Date(current.getFullYear(),current.getMonth()+1,1);loadCalendar(false);};
$("refresh-calendar").onclick=()=>loadCalendar(true);
["show-earnings","show-economic"].forEach(id=>$(id).addEventListener("change",renderCalendar));
$("earnings-view").addEventListener("change",()=>{toggleCustomFilter();loadCalendar(false);});
$("calendar-symbol-filter").addEventListener("keydown",e=>{if(e.key==="Enter")loadCalendar(true);});
toggleCustomFilter(); loadCalendar(false);
