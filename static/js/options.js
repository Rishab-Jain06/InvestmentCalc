const payoffGuidePlugin = {
  id: "payoffGuide",
  afterDatasetsDraw(chart, args, opts){
    const {ctx, chartArea:{top,bottom}, scales:{x}} = chart;
    if(!x) return;
    ctx.save();
    function draw(price, label, color){
      if(price == null) return;
      const xPos = x.getPixelForValue(String(Number(price).toFixed(2)));
      if(!Number.isFinite(xPos) || xPos < chart.chartArea.left || xPos > chart.chartArea.right) return;
      ctx.beginPath();
      ctx.moveTo(xPos, top);
      ctx.lineTo(xPos, bottom);
      ctx.lineWidth = 1;
      ctx.setLineDash([5,5]);
      ctx.strokeStyle = color;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = color;
      ctx.font = "12px Inter, sans-serif";
      ctx.fillText(label, xPos + 6, top + 14);
    }
    draw(opts.spot, "Spot", opts.spotColor || "#8b5cf6");
    draw(opts.breakeven, "B/E", opts.beColor || "#10b981");
    ctx.restore();
  }
};
const payoffCrosshairPlugin = {
  id: "payoffCrosshair",
  afterDatasetsDraw(chart,args,opts){
    const active = chart.tooltip?.getActiveElements?.() || [];
    if(!active.length) return;
    const {ctx, chartArea:{top,bottom}} = chart;
    const x = active[0].element.x;
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x, top);
    ctx.lineTo(x, bottom);
    ctx.lineWidth = 1;
    ctx.setLineDash([4,4]);
    ctx.strokeStyle = opts.color || "rgba(148,163,184,.75)";
    ctx.stroke();
    ctx.restore();
  }
};
if(window.Chart){
  if(!Chart.registry.plugins.get("payoffGuide")) Chart.register(payoffGuidePlugin);
  if(!Chart.registry.plugins.get("payoffCrosshair")) Chart.register(payoffCrosshairPlugin);
}

let strategyType = "single";
let direction = "bullish";
let strategy = "buy_call";
let payoffChart = null;
let lastSpot = null;
let lastOptionRows = [];

const $ = id => document.getElementById(id);
const error = m => { const e = $("options-error"); e.textContent = m; e.classList.remove("hidden"); };
const clearError = () => $("options-error").classList.add("hidden");
function selectGroup(container, button){ container.querySelectorAll("button").forEach(b => b.classList.toggle("active", b === button)); }
function setVal(id, v){ const el = $(id); if(el) el.value = v; }
function fmt(v, d=2){ return v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d); }
function pct(v){ return v == null ? "—" : `${(Number(v)*100).toFixed(1)}%`; }
function labelStrategy(s){ return ({buy_call:"Buy Call", sell_put:"Sell Put", buy_put:"Buy Put", sell_call:"Sell Call", call_debit:"Call Debit", call_credit:"Call Credit", put_debit:"Put Debit", put_credit:"Put Credit"}[s] || s); }

function syncDeltaLabels(){
  const vertical = strategyType === "vertical";
  $("min-delta-label").textContent = vertical ? "Min short |Delta|" : "Min |Delta|";
  $("max-delta-label").textContent = vertical ? "Max short |Delta|" : "Max |Delta|";
}
function syncStrategies(){
  const container=strategyType==="single"?$("single-strategies"):$("vertical-strategies");

  if(strategyType==="single"){
    container.querySelectorAll("button").forEach(b=>b.classList.toggle("hidden",b.dataset.direction!==direction));
  } else {
    // Show all four vertical spreads at all times: Call Debit, Put Credit, Call Credit, Put Debit.
    container.querySelectorAll("button").forEach(b=>b.classList.remove("hidden"));
  }

  const candidates = strategyType==="single"
    ? [...container.querySelectorAll(`button[data-direction="${direction}"]`)]
    : [...container.querySelectorAll("button")];

  const current=candidates.find(b=>b.dataset.value===strategy);
  const preferred = strategyType==="vertical"
    ? candidates.find(b=>b.dataset.direction===direction) || candidates[0]
    : candidates[0];

  const chosen=current||preferred;
  if(chosen){selectGroup(container,chosen);strategy=chosen.dataset.value}
  syncDeltaLabels();
}
function setStrategyType(value){
  strategyType = value;
  const btn = [...$("strategy-type").querySelectorAll("button")].find(b => b.dataset.value === value);
  if(btn) selectGroup($("strategy-type"), btn);
  const vertical = strategyType === "vertical";
  $("single-strategies").classList.toggle("hidden", vertical);
  $("vertical-strategies").classList.toggle("hidden", !vertical);
  document.querySelectorAll(".vertical-only").forEach(x => x.classList.toggle("hidden", !vertical));
  syncStrategies();
}
function setDirection(value){
  direction = value;
  const btn = [...$("direction").querySelectorAll("button")].find(b => b.dataset.value === value);
  if(btn) selectGroup($("direction"), btn);
  syncStrategies();
}
function setStrategy(value){
  strategy = value;
  const container = strategyType === "single" ? $("single-strategies") : $("vertical-strategies");
  const btn = [...container.querySelectorAll("button")].find(b => b.dataset.value === value);
  if(btn) selectGroup(container, btn);
}

$("strategy-type").querySelectorAll("button").forEach(b => b.addEventListener("click", () => setStrategyType(b.dataset.value)));
$("direction").querySelectorAll("button").forEach(b => b.addEventListener("click", () => setDirection(b.dataset.value)));
[$("single-strategies"), $("vertical-strategies")].forEach(container => {
  container.querySelectorAll("button").forEach(b => b.addEventListener("click", () => setStrategy(b.dataset.value)));
});

async function loadExpirations(){
  clearError();
  const sym = $("opt-symbol").value.trim().toUpperCase();
  if(!sym) return;
  $("expiration").innerHTML = "<option>Loading…</option>";
  try{
    const d = await (await fetch(`/api/options/expirations/${sym}`)).json();
    if(d.error) throw Error(d.error);
    $("expiration").innerHTML = `<option value="AUTO">Any expiration matching DTE</option>` + d.expirations.map(x => `<option value="${x.date}">${x.date} · ${x.dte} DTE</option>`).join("");
    $("underlying").textContent = sym;
  }catch(e){
    error(e.message);
    $("expiration").innerHTML = "<option>Unavailable</option>";
  }
}
$("load-options").addEventListener("click", loadExpirations);

$("put-credit-preset").addEventListener("click", () => {
  setStrategyType("vertical");
  setDirection("bullish");
  setStrategy("put_credit");
  setVal("expiration", "AUTO");
  setVal("min-dte", "30"); setVal("max-dte", "45");
  setVal("min-delta", ".10"); setVal("max-delta", ".15");
  setVal("min-iv", "20"); setVal("min-oi", "100"); setVal("min-volume", "10");
  setVal("max-bid-ask", ".05"); setVal("min-credit", ".25"); setVal("max-debit", "");
  setVal("min-ror", "20"); setVal("spread-width", "1"); setVal("max-loss", "100"); setVal("max-width", "");
  setVal("trend-filter", "off");
});

function query(){
  const p = new URLSearchParams({expiration: $("expiration").value, strategy_type: strategyType, strategy, trend_filter: $("trend-filter").value});
  [["min_dte","min-dte"],["max_dte","max-dte"],["min_delta","min-delta"],["max_delta","max-delta"],["min_iv","min-iv"],["min_oi","min-oi"],["min_volume","min-volume"],["max_bid_ask","max-bid-ask"],["min_credit","min-credit"],["max_debit","max-debit"],["min_ror","min-ror"],["spread_width","spread-width"],["max_loss","max-loss"],["max_width","max-width"]].forEach(([k,id]) => {
    const v = $(id)?.value;
    if(v !== "") p.set(k, v);
  });
  return p.toString();
}
async function findTrades(){
  clearError();
  const sym = $("opt-symbol").value.trim().toUpperCase();
  if(!sym || !$("expiration").value) return;
  $("results-body").innerHTML = `<tr><td class="empty-cell">Screening…</td></tr>`;
  try{
    const d = await (await fetch(`/api/options/screen/${sym}?${query()}`)).json();
    if(d.error) throw Error(d.error);
    lastSpot = d.spot;
    $("underlying").textContent = d.symbol;
    $("opt-spot").textContent = d.spot ? `$${Number(d.spot).toFixed(2)}` : "—";
    $("opt-dte").textContent = d.dte_min != null || d.dte_max != null ? `${d.dte_min ?? "—"}–${d.dte_max ?? "—"}` : (d.results?.[0]?.dte ?? "—");
    $("match-count").textContent = d.count;
    renderResults(d.results || []);
  }catch(e){
    error(e.message);
    $("results-body").innerHTML = `<tr><td class="empty-cell">No results.</td></tr>`;
  }
}
$("find-trades").addEventListener("click", findTrades);

function renderResults(rows){
  lastOptionRows = rows || [];
  const h = $("results-head");
  const b = $("results-body");
  if(strategyType === "single"){
    h.innerHTML = "<th>Trade</th><th>Exp</th><th>DTE</th><th>Strike</th><th>Bid</th><th>Ask</th><th>Delta</th><th>IV</th><th>Vol</th><th>OI</th>";
    b.innerHTML = lastOptionRows.length ? lastOptionRows.map((x,i) => `<tr data-i="${i}"><td>${labelStrategy(x.strategy)}</td><td>${x.expiration}</td><td>${x.dte}</td><td>${x.strike}</td><td>$${fmt(x.bid)}</td><td>$${fmt(x.ask)}</td><td>${fmt(x.delta,3)}</td><td>${pct(x.iv)}</td><td>${x.volume}</td><td>${x.open_interest}</td></tr>`).join("") : `<tr><td colspan="10" class="empty-cell">No contracts match these filters.</td></tr>`;
  }else{
    h.innerHTML = "<th>Strategy</th><th>Exp</th><th>DTE</th><th>Legs</th><th>Credit/Debit</th><th>Max Loss</th><th>ROR</th><th>Short Δ</th><th>IV</th><th>OI</th>";
    b.innerHTML = lastOptionRows.length ? lastOptionRows.map((x,i) => `<tr data-i="${i}"><td>${labelStrategy(x.strategy)}</td><td>${x.expiration}</td><td>${x.dte}</td><td>${x.legs.map(l => `${l.action === "buy" ? "B" : "S"} ${l.strike}${l.type === "call" ? "C" : "P"}`).join(" / ")}</td><td>${x.net_premium >= 0 ? "Credit " : "Debit "}$${fmt(Math.abs(x.net_premium))}</td><td>$${fmt(x.max_loss)}</td><td>${fmt(x.ror)}%</td><td>${fmt(x.short_delta,3)}</td><td>${pct(x.iv)}</td><td>${x.open_interest}</td></tr>`).join("") : `<tr><td colspan="10" class="empty-cell">No spreads match these filters.</td></tr>`;
  }
  b.querySelectorAll("tr[data-i]").forEach(tr => tr.addEventListener("click", () => analyze(lastOptionRows[Number(tr.dataset.i)])));
}
function metric(label,val){ return `<div><span>${label}</span><strong>${val}</strong></div>`; }
function greekBox(name,val,help){ return `<div class="greek-box"><span>${name}</span><strong>${fmt(val,4)}</strong><small>${help}</small></div>`; }
function legCard(l){
  const label = `$${fmt(l.strike,0)} ${l.type === "call" ? "Call" : "Put"}`;
  return `<article class="leg-card"><div class="leg-head"><div><span class="leg-action ${l.action}">${l.action.toUpperCase()}</span><h4>${label}</h4><small>${l.contract || ""}</small></div><strong>$${fmt(l.price)}</strong></div><div class="leg-quote-grid">${metric("Bid",`$${fmt(l.bid)}`)}${metric("Ask",`$${fmt(l.ask)}`)}${metric("Mark",`$${fmt(l.mid)}`)}${metric("Last",`$${fmt(l.last)}`)}${metric("IV",pct(l.iv))}${metric("Volume",l.volume ?? "—")}${metric("Open interest",l.open_interest ?? "—")}</div><div class="leg-greeks"><div><span>Delta</span><strong>${fmt(l.delta,4)}</strong></div><div><span>Gamma</span><strong>${fmt(l.gamma,4)}</strong></div><div><span>Theta</span><strong>${fmt(l.theta,4)}</strong></div><div><span>Vega</span><strong>${fmt(l.vega,4)}</strong></div><div><span>Rho</span><strong>${fmt(l.rho,4)}</strong></div></div></article>`;
}
async function analyze(x, isBest=false){
  $("trade-analysis").classList.remove("hidden");
  $("analysis-title").textContent = `${isBest ? "★ Best Match · " : ""}${labelStrategy(x.strategy)}`;
  $("analysis-subtitle").textContent = `${$("underlying").textContent} · ${x.expiration || $("expiration").value} · ${x.dte ?? "—"} DTE`;
  const bb = $("analysis-bias");
  bb.textContent = (x.bias || direction).toUpperCase();
  bb.className = `bias-badge ${x.bias || direction}`;
  $("analysis-metrics").innerHTML = [
    metric("Net premium", `${x.net_premium >= 0 ? "Credit" : "Debit"} $${fmt(Math.abs(x.net_premium))}`),
    metric("Max profit", x.max_profit == null ? "Strategy dependent" : `$${fmt(x.max_profit)}`),
    metric("Max loss", x.max_loss == null ? "Strategy dependent" : `$${fmt(x.max_loss)}`),
    metric("Breakeven", `$${fmt(x.breakeven)}`),
    metric("Return on risk", x.ror == null ? "—" : `${fmt(x.ror)}%`)
  ].join("");
  const g = x.position_greeks || {};
  $("position-greeks").innerHTML = [
    greekBox("Delta", g.delta, "≈ $ P/L per $1 move"),
    greekBox("Gamma", g.gamma, "Delta change per $1"),
    greekBox("Theta", g.theta, "≈ daily time decay $"),
    greekBox("Vega", g.vega, "≈ $ per 1 IV point"),
    greekBox("Rho", g.rho, "≈ $ per 1% rate move")
  ].join("");
  $("leg-cards").innerHTML = (x.legs || []).map(legCard).join("");

  const low = Math.max(0, lastSpot * .8);
  const high = lastSpot * 1.2;
  const d = await (await fetch("/api/options/payoff", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({legs:x.legs, spot:lastSpot, low, high})})).json();
  if(payoffChart) payoffChart.destroy();
  const dark = document.documentElement.dataset.theme === "dark";
  payoffChart = new Chart($("payoff-chart"), {
    type: "line",
    data: { labels: d.points.map(p => Number(p.price).toFixed(2)), datasets: [{
      data: d.points.map(p => p.pnl), borderWidth: 2.5, pointRadius: 0, pointHoverRadius: 5, pointHitRadius: 12, tension: 0,
      fill: { target:{value:0}, above:"rgba(16,185,129,.10)", below:"rgba(239,68,68,.10)" }
    }]},
    options: {
      responsive:true, maintainAspectRatio:false, interaction:{mode:"index", intersect:false},
      plugins:{ legend:{display:false}, tooltip:{enabled:true, displayColors:false, callbacks:{ title:items => `Underlying: $${Number(items[0].label).toFixed(2)}`, label:item => `P/L: ${item.parsed.y>=0?"+":""}$${Number(item.parsed.y).toFixed(2)}` }}, payoffGuide:{spot:lastSpot, breakeven:x.breakeven, spotColor:dark?"#a78bfa":"#7c3aed", beColor:"#10b981"}, payoffCrosshair:{color:dark?"rgba(156,163,175,.75)":"rgba(107,114,128,.55)"} },
      scales:{ x:{grid:{color:dark?"rgba(255,255,255,.06)":"rgba(17,24,39,.06)"}, ticks:{color:dark?"#9ca3af":"#6b7280"}, title:{display:true,text:"Underlying price at expiration",color:dark?"#9ca3af":"#6b7280"}}, y:{grid:{color:dark?"rgba(255,255,255,.06)":"rgba(17,24,39,.06)"}, ticks:{color:dark?"#9ca3af":"#6b7280", callback:v=>"$"+v}, title:{display:true,text:"Profit / Loss ($)",color:dark?"#9ca3af":"#6b7280"}} }
    }
  });
  $("trade-analysis").scrollIntoView({behavior:"smooth", block:"start"});
}

const OPT_PRESET_KEY = "investify_option_presets";
const optPresets = () => JSON.parse(localStorage.getItem(OPT_PRESET_KEY) || "{}");
function saveOptPresets(x){ localStorage.setItem(OPT_PRESET_KEY, JSON.stringify(x)); }
function optionState(){
  const ids = ["opt-symbol","expiration","min-dte","max-dte","min-delta","max-delta","min-iv","min-oi","min-volume","max-bid-ask","min-credit","max-debit","min-ror","spread-width","max-loss","max-width","trend-filter"];
  const fields = {};
  ids.forEach(id => { if($(id)) fields[id] = $(id).value; });
  return {strategyType, direction, strategy, fields};
}
function applyOptionState(p){
  if(!p) return;
  Object.entries(p.fields || {}).forEach(([id,v]) => setVal(id,v));
  setStrategyType(p.strategyType || "single");
  setDirection(p.direction || "bullish");
  setStrategy(p.strategy || strategy);
}
function refreshOptionPresets(){
  const p = optPresets();
  $("option-preset-select").innerHTML = '<option value="">Saved preset…</option>' + Object.keys(p).map(k => `<option value="${k}">${k}</option>`).join("");
}
$("option-save-preset").addEventListener("click", () => {
  const name = prompt("Preset name");
  if(!name) return;
  const p = optPresets();
  p[name] = optionState();
  saveOptPresets(p);
  refreshOptionPresets();
  $("option-preset-select").value = name;
});
$("option-delete-preset").addEventListener("click", () => {
  const name = $("option-preset-select").value;
  if(!name) return;
  const p = optPresets();
  delete p[name];
  saveOptPresets(p);
  refreshOptionPresets();
});
$("option-preset-select").addEventListener("change", () => applyOptionState(optPresets()[$("option-preset-select").value]));
function whyMatched(x){
  const bits = [];
  if(x.short_delta != null || x.delta != null) bits.push(`Delta ${fmt(x.short_delta ?? x.delta,3)}`);
  if(x.net_premium != null) bits.push(`${x.net_premium >= 0 ? "Credit" : "Debit"} $${fmt(Math.abs(x.net_premium))}`);
  if(x.ror != null) bits.push(`${fmt(x.ror)}% ROR`);
  if(x.open_interest != null) bits.push(`${x.open_interest} OI`);
  if(x.iv != null) bits.push(`${pct(x.iv)} IV`);
  return bits.join(" · ");
}
$("best-option").addEventListener("click", () => {
  const x = lastOptionRows[0];
  const c = $("best-option-card");
  if(!x){
    c.classList.remove("hidden");
    c.innerHTML = '<p class="small-muted">No Best Match yet. Click Find Trades first.</p>';
    return;
  }
  c.classList.remove("hidden");
  c.innerHTML = `<div class="best-match-strip"><div><p class="eyebrow">BEST MATCH SELECTED</p><h3>${labelStrategy(x.strategy)}</h3><p class="small-muted">${whyMatched(x)}</p></div><button id="jump-analysis" class="secondary-button">View full analysis</button></div>`;
  analyze(x, true);
  setTimeout(() => $("jump-analysis")?.addEventListener("click", () => $("trade-analysis")?.scrollIntoView({behavior:"smooth", block:"start"})), 100);
});

refreshOptionPresets();
syncStrategies();
loadExpirations();
