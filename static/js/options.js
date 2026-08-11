
function summarizeTradeText(x){
  const symbol=document.getElementById("opt-symbol")?.value?.trim()?.toUpperCase()||x.symbol||"";
  const fmtLocal=(v,d=2)=>v==null||Number.isNaN(Number(v))?"—":Number(v).toFixed(d);
  const strategyLabel=typeof labelStrategy==="function"?labelStrategy(x.strategy):(x.strategy||"Trade");
  const lines=[];
  lines.push(`${symbol} ${strategyLabel} ${x.expiration||""} ${x.dte??"—"} DTE`);
  if(x.net_premium!=null)lines.push(`Net premium: ${x.net_premium>=0?"Credit":"Debit"} $${fmtLocal(Math.abs(x.net_premium))}`);
  if(x.max_profit!=null)lines.push(`Max profit: ${typeof x.max_profit==="number"?"$"+fmtLocal(x.max_profit):x.max_profit}`);
  if(x.max_loss!=null)lines.push(`Max loss: ${typeof x.max_loss==="number"?"$"+fmtLocal(x.max_loss):x.max_loss}`);
  if(x.breakeven!=null)lines.push(`Breakeven: $${fmtLocal(x.breakeven)}`);
  if(x.ror!=null)lines.push(`Return on risk: ${fmtLocal(x.ror)}%`);
  if(x.quality){
    lines.push(`Trade quality score: ${x.quality.score}/100`);
    lines.push(`Risk level: ${x.quality.risk_level || x.quality.riskiness?.grade || "—"}`);
    lines.push(`${x.quality.probability?.label || "Probability"}: ${x.quality.probability?.value == null ? "—" : "~" + Math.round(x.quality.probability.value) + "%"}`);
    lines.push(`Delta/Probability: ${x.quality.delta_probability?.grade || "—"}; Risk/Reward: ${x.quality.risk_reward?.grade || "—"}; IV: ${x.quality.iv_suitability?.grade || "—"}; Trend: ${x.quality.trend_match?.grade || "—"}; Liquidity: ${x.quality.liquidity?.grade || "—"}; Bid/Ask: ${x.quality.bid_ask?.grade || "—"}`);
  }
  if(x.position_greeks){
    const g=x.position_greeks;
    lines.push(`Position Greeks: Delta ${fmtLocal(g.delta,4)}, Gamma ${fmtLocal(g.gamma,4)}, Theta ${fmtLocal(g.theta,4)}, Vega ${fmtLocal(g.vega,4)}, Rho ${fmtLocal(g.rho,4)}`);
  }
  if(x.legs?.length){
    lines.push("Legs:");
    x.legs.forEach(l=>{
      lines.push(`- ${String(l.action||"").toUpperCase()} ${l.strike} ${String(l.type||"").toUpperCase()} @ ${l.expiration||x.expiration||""}; bid ${l.bid??"—"}, ask ${l.ask??"—"}, mark ${l.mark??"—"}, last ${l.last??"—"}, IV ${l.iv??"—"}, volume ${l.volume??"—"}, OI ${l.open_interest??"—"}, delta ${l.delta??"—"}, theta ${l.theta??"—"}`);
    });
  }
  return lines.join("\\n");
}
function buildTradeAIContext(x){
  const symbol=document.getElementById("opt-symbol")?.value?.trim()?.toUpperCase()||x.symbol||"";
  return {
    ticker:symbol,
    trade:{
      ...x,
      symbol,
      strategy_label:typeof labelStrategy==="function"?labelStrategy(x.strategy):(x.strategy||"Trade"),
      summary_text:summarizeTradeText(x)
    },
    source:"Options Lab",
    createdAt:new Date().toISOString()
  };
}
function sendTradeToAI(x){
  localStorage.setItem("investify_pending_ai_context",JSON.stringify(buildTradeAIContext(x)));
  window.location.href="/search";
}
async function copyTradeToClipboard(x){
  const text=summarizeTradeText(x);
  try{
    await navigator.clipboard.writeText(text);
    const b=document.getElementById("copy-trade");
    if(b){const old=b.textContent;b.textContent="Copied";setTimeout(()=>b.textContent=old,1200);}
  }catch(e){
    window.prompt("Copy trade details:", text);
  }
}
function bindTradeActionButtons(x){
  const ask=document.getElementById("ask-ai-trade");
  const copy=document.getElementById("copy-trade");
  if(ask){ask.onclick=()=>sendTradeToAI(x); ask.disabled=false;}
  if(copy){copy.onclick=()=>copyTradeToClipboard(x); copy.disabled=false;}
}







const payoffGuidePlugin = {
  id: "payoffGuide",
  afterDatasetsDraw(chart, args, opts){
    const {ctx, chartArea:{top,bottom,left,right}, scales:{x}} = chart;
    if(!x) return;
    ctx.save();

    function draw(price, label, color, offset=14){
      const n = Number(price);
      if(!Number.isFinite(n)) return;
      const xPos = x.getPixelForValue(n);
      if(!Number.isFinite(xPos) || xPos < left || xPos > right) return;
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
      ctx.fillText(label, Math.min(xPos + 6, right - 95), top + offset);
    }

    draw(opts.spot, "Current Price", opts.spotColor || "#8b5cf6", 14);
    draw(opts.breakeven, "Breakeven", opts.beColor || "#10b981", 32);
    (opts.strikes || []).forEach((m, i) => {
      draw(m.price, m.label, m.color || opts.strikeColor || "#94a3b8", 50 + (i % 2) * 18);
    });
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
let riskProfile = "balanced";

const $ = id => document.getElementById(id);
const error = m => { const e = $("options-error"); e.textContent = m; e.classList.remove("hidden"); };
const clearError = () => $("options-error").classList.add("hidden");
function selectGroup(container, button){ container.querySelectorAll("button").forEach(b => b.classList.toggle("active", b === button)); }
function setVal(id, v){ const el = $(id); if(el) el.value = v; }
function fmt(v, d=2){ return v == null || Number.isNaN(Number(v)) ? "—" : Number(v).toFixed(d); }
function pct(v){ return v == null ? "—" : `${(Number(v)*100).toFixed(1)}%`; }
function labelStrategy(s){ return ({buy_call:"Buy Call", sell_put:"Sell Put", cash_secured_put:"Cash Secured Put", buy_put:"Buy Put", sell_call:"Sell Call", covered_call:"Covered Call", call_debit:"Call Debit", call_credit:"Call Credit", put_debit:"Put Debit", put_credit:"Put Credit"}[s] || s); }

function esc(v){
  return String(v ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}
function esc(v){
  return String(v ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
}
function gradeClass(v){
  return String(v || "").toLowerCase().replace(/\s+/g,"-").replace(/\//g,"-").replace(/[^a-z0-9-]/g,"");
}
function qPart(x, key){ return x?.quality?.[key] || null; }
function qualityPill(label){
  const text = label || "—";
  return `<span class="quality-pill ${gradeClass(text)}">${esc(text)}</span>`;
}
function subScore(part){
  if(!part || part.points == null) return "";
  return `<span class="quality-subscore">${Math.round(part.points)}/10</span>`;
}
function scoreBadge(x){
  const score = x?.quality_score ?? x?.quality?.score;
  if(score == null) return `<span class="score-badge neutral-score">—</span>`;
  const tone = score >= 85 ? "good-score" : score >= 70 ? "ok-score" : score >= 55 ? "weak-score" : "poor-score";
  return `<span class="score-badge ${tone}">${Math.round(score)}</span>`;
}
function probabilityText(x){
  const v = x?.quality?.delta_probability?.value ?? x?.quality?.probability?.value ?? x?.probability_estimate;
  return v == null ? "—" : `~${Math.round(v)}%`;
}
const oiText = v => v == null || Number(v) === 0 ? "—" : v;
function riskText(x){ return x?.quality?.risk_level || x?.quality?.delta_probability?.risk_level || x?.riskiness || "—"; }
function criticalIssueText(x){
  const issue = x?.quality?.critical_issue || x?.critical_issue;
  return !issue || issue === "None" ? "None" : issue;
}
function issuePill(x){
  const issue = criticalIssueText(x);
  return issue === "None" ? `<span class="issue-pill none">None</span>` : `<span class="issue-pill">${esc(issue)}</span>`;
}
function familyLabel(f){
  return ({
    credit_spread:"Credit spread quality score",
    debit_spread:"Debit spread quality score",
    long_option:"Long option quality score",
    short_put:"Short premium quality score",
    short_call:"Short call quality score",
    covered_call:"Covered call quality score"
  }[f] || "Strategy-specific quality score");
}
function compactQuality(x){
  const q = x?.quality;
  if(!q) return "";
  return [
    `Score ${q.score}/100`,
    `${riskText(x)} risk level`,
    `${probabilityText(x)} ${q.delta_probability?.label || q.probability?.label || "probability"}`,
    `${q.risk_reward?.grade || "—"} risk/reward`,
    `${q.iv_suitability?.grade || "—"} IV`,
    `${q.liquidity?.grade || "—"} liquidity`
  ].join(" · ");
}
function qualityTile(label, part){
  const grade = part?.grade ?? "—";
  const reason = part?.reason ? `<small>${esc(part.reason)}</small>` : "";
  const weight = part?.weight != null ? `<em>${part.weight}% weight</em>` : "";
  return `<div class="quality-tile">
    <div class="quality-tile-head"><span>${esc(label)}</span>${subScore(part)}</div>
    <strong>${qualityPill(grade)}</strong>
    ${weight}
    ${reason}
  </div>`;
}
function tradeLegLabel(l){
  const action = String(l.action || "").toUpperCase();
  const type = l.type === "call" ? "Call" : "Put";
  return `${action} $${fmt(l.strike,0)} ${type}`;
}
function orderedLegs(x){
  const legs = [...(x.legs || [])];
  if(["put_credit","call_credit","sell_put","sell_call","covered_call","cash_secured_put"].includes(x.strategy)){
    legs.sort((a,b) => (a.action === "sell" ? -1 : 1));
  }else{
    legs.sort((a,b) => (a.action === "buy" ? -1 : 1));
  }
  return legs;
}
function selectedTradeName(x){
  const symbol = $("underlying")?.textContent || $("opt-symbol")?.value?.trim()?.toUpperCase() || x.symbol || "";
  if(x.legs?.length === 2){
    const puts = x.legs.every(l => l.type === "put");
    const calls = x.legs.every(l => l.type === "call");
    const strikes = x.legs.map(l => Number(l.strike)).sort((a,b)=>b-a).map(v => fmt(v,0)).join("/");
    return `${symbol} ${strikes} ${puts ? "Put" : calls ? "Call" : ""} ${labelStrategy(x.strategy)}`;
  }
  const l = x.legs?.[0] || x;
  return `${symbol} $${fmt(l.strike ?? x.strike,0)} ${l.type === "call" ? "Call" : "Put"} · ${labelStrategy(x.strategy)}`;
}
function renderSelectedTradeSummary(x){
  const box = $("selected-trade-summary");
  if(!box) return;
  box.classList.remove("hidden");
  const legs = orderedLegs(x).map(l => `<span>${esc(tradeLegLabel(l))} @ $${fmt(l.price)}</span>`).join("");
  const delta = x.quality?.delta_probability?.delta ?? x.short_delta ?? x.delta;
  const critical = (x.quality?.critical_issues || []).slice(0,4).map(w => `<span class="warning-pill">${esc(w)}</span>`).join("");
  box.innerHTML = `
    <div class="selected-trade-head">
      <div>
        <p class="eyebrow">SELECTED TRADE</p>
        <h3>${esc(selectedTradeName(x))}</h3>
        <p class="small-muted">${esc($("underlying")?.textContent || "")} · ${esc(x.expiration || "")} · ${x.dte ?? "—"} DTE</p>
      </div>
      ${scoreBadge(x)}
    </div>
    <div class="selected-trade-grid">
      ${metric("Net premium", `${x.net_premium >= 0 ? "Credit" : "Debit"} $${fmt(Math.abs(x.net_premium))}`)}
      ${metric("Risk level", qualityPill(riskText(x)))}
      ${metric("Probability", probabilityText(x))}
      ${metric("Key delta", fmt(delta,3))}
      ${metric("IV", pct(x.quality?.iv_suitability?.iv))}
      ${metric("Critical issue", issuePill(x))}
    </div>
    <div class="selected-leg-row">${legs}</div>
    ${critical ? `<div class="warning-row">${critical}</div>` : ""}`;
}
function renderTradeQuality(x){
  const card = $("trade-quality-card");
  if(!card) return;
  const q = x?.quality;
  if(!q){ card.classList.add("hidden"); card.innerHTML = ""; return; }
  card.classList.remove("hidden");
  const pLabel = q.delta_probability?.label || q.probability?.label || "Probability";
  const pValue = probabilityText(x);
  const reasons = (q.reasons || []).filter(Boolean).slice(0,7).map(r => `<li>${esc(r)}</li>`).join("");
  const critical = (q.critical_issues || []).map(w => `<span class="warning-pill">${esc(w)}</span>`).join("");
  const warnings = (q.warnings || []).filter(w => !(q.critical_issues || []).includes(w)).map(w => `<span class="warning-pill secondary-warning">${esc(w)}</span>`).join("");
  const capNote = q.score_cap != null && q.raw_score != null && q.score < Math.round(q.raw_score)
    ? `<p class="quality-cap-note">Score was capped from ${Math.round(q.raw_score)} to ${q.score} because of critical issue rules.</p>` : "";
  const weightLines = q.weights ? Object.entries(q.weights).map(([k,v]) => `<span>${esc(k.replaceAll("_"," "))}: ${v}%</span>`).join("") : "";
  card.innerHTML = `
    <div class="quality-header">
      <div>
        <p class="eyebrow">TRADE QUALITY</p>
        <h3>${esc(familyLabel(q.strategy_family))}</h3>
        <p class="small-muted">Six-factor strategy-specific score. DTE and Greeks are warnings/caps only, not weighted categories.</p>
      </div>
      <div class="quality-score-large ${q.score >= 85 ? "good-score" : q.score >= 70 ? "ok-score" : q.score >= 55 ? "weak-score" : "poor-score"}">${Math.round(q.score)}<span>/100</span></div>
    </div>
    <div class="quality-highlight-row">
      <div><span>Risk Level</span><strong>${qualityPill(q.risk_level || "—")}</strong></div>
      <div><span>${esc(pLabel)}</span><strong>${pValue}</strong>${subScore(q.delta_probability || q.probability)}</div>
      <div><span>Key delta</span><strong>${fmt(q.delta_probability?.delta ?? q.probability?.delta,3)}</strong></div>
    </div>
    ${critical ? `<div class="quality-warnings critical"><strong>Critical Issues</strong><div>${critical}</div></div>` : ""}
    ${warnings ? `<div class="quality-warnings"><strong>Warnings</strong><div>${warnings}</div></div>` : ""}
    <div class="quality-grid six-grid">
      ${qualityTile("Delta / Probability", q.delta_probability || q.probability)}
      ${qualityTile("Risk / Reward", q.risk_reward)}
      ${qualityTile("IV Suitability", q.iv_suitability)}
      ${qualityTile("Trend Match", q.trend_match)}
      ${qualityTile("Liquidity", q.liquidity)}
      ${qualityTile("Bid/Ask Quality", q.bid_ask)}
    </div>
    ${capNote}
    <details class="quality-details" open>
      <summary>Why this score?</summary>
      <ul>${reasons}</ul>
    </details>
    <details class="quality-details">
      <summary>How is this calculated?</summary>
      <p>The score uses six 0–10 category scores and applies the strategy-specific weights below. DTE, theta, gamma and vega remain visible in analysis, but only create warnings or score caps when extreme.</p>
      <div class="weight-chip-row">${weightLines}</div>
      <p>${esc(q.disclaimer || "Rule-based estimate only. Confirm live quotes with your broker.")}</p>
    </details>`;
}

function syncDeltaLabels(){
  const vertical = strategyType === "vertical";
  $("min-delta-label").textContent = vertical ? "Min short |Delta|" : "Min |Delta|";
  $("max-delta-label").textContent = vertical ? "Max short |Delta|" : "Max |Delta|";
}

function syncStrategies(){
  const container = strategyType === "single" ? $("single-strategies") : $("vertical-strategies");

  container.querySelectorAll("button").forEach(b => {
    b.classList.toggle("hidden", b.dataset.direction !== direction);
  });

  const candidates = [...container.querySelectorAll(`button[data-direction="${direction}"]`)];
  const current = candidates.find(b => b.dataset.value === strategy);
  const preferred = strategyType === "vertical"
    ? candidates.find(b => direction === "bullish" ? b.dataset.value === "put_credit" : b.dataset.value === "call_credit") || candidates[0]
    : candidates[0];

  const chosen = current || preferred;
  if(chosen){
    selectGroup(container, chosen);
    strategy = chosen.dataset.value;
  }
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
$("risk-profile")?.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
  riskProfile = b.dataset.value || "balanced";
  selectGroup($("risk-profile"), b);
}));

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


const FILTER_IDS = ["min-dte","max-dte","min-delta","max-delta","min-iv","min-oi","min-volume","max-bid-ask","min-credit","max-debit","min-ror","spread-width","max-loss","max-width"];

function clearFilterValues(){
  FILTER_IDS.forEach(id => setVal(id, ""));
  setVal("trend-filter", "off");
}

function toggleFilters(forceOpen=null){
  const panel = $("filters-panel");
  const btn = $("filters-toggle");
  if(!panel || !btn) return;
  const open = forceOpen === null ? panel.classList.contains("hidden") : forceOpen;
  panel.classList.toggle("hidden", !open);
  btn.textContent = open ? "Hide filters" : "Show filters";
}


function query(){
  const p = new URLSearchParams({expiration: $("expiration").value, strategy_type: strategyType, strategy, risk_profile: riskProfile});
  const trend = $("trend-filter")?.value;
  if(trend && trend !== "off") p.set("trend_filter", trend);
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
    h.innerHTML = "<th>Score</th><th>Risk Level</th><th>Trade</th><th>Exp</th><th>DTE</th><th>Strike</th><th>Bid</th><th>Ask</th><th>Delta</th><th>IV</th><th>OI</th>";
    b.innerHTML = lastOptionRows.length ? lastOptionRows.map((x,i) => `<tr data-i="${i}"><td>${scoreBadge(x)}</td><td>${qualityPill(riskText(x))}</td><td>${labelStrategy(x.strategy)}</td><td>${x.expiration}</td><td>${x.dte}</td><td>${x.strike}</td><td>$${fmt(x.bid)}</td><td>$${fmt(x.ask)}</td><td>${fmt(x.delta,3)}</td><td>${pct(x.iv)}</td><td>${oiText(x.open_interest)}</td></tr>`).join("") : `<tr><td colspan="11" class="empty-cell">No contracts match. If this happens with no filters, Yahoo may have returned zero/missing option quotes; try Clear filters, a specific expiration, or wait and reload.</td></tr>`;
  }else{
    h.innerHTML = "<th>Score</th><th>Risk Level</th><th>Strategy</th><th>Exp</th><th>DTE</th><th>Legs</th><th>Credit/Debit</th><th>Max Loss</th><th>ROR</th><th>Short Δ</th><th>OI</th>";
    b.innerHTML = lastOptionRows.length ? lastOptionRows.map((x,i) => `<tr data-i="${i}"><td>${scoreBadge(x)}</td><td>${qualityPill(riskText(x))}</td><td>${labelStrategy(x.strategy)}</td><td>${x.expiration}</td><td>${x.dte}</td><td>${orderedLegs(x).map(l => `${l.action === "buy" ? "B" : "S"} ${l.strike}${l.type === "call" ? "C" : "P"}`).join(" / ")}</td><td>${x.net_premium >= 0 ? "Credit " : "Debit "}$${fmt(Math.abs(x.net_premium))}</td><td>$${fmt(x.max_loss)}</td><td>${fmt(x.ror)}%</td><td>${fmt(x.short_delta,3)}</td><td>${oiText(x.open_interest)}</td></tr>`).join("") : `<tr><td colspan="11" class="empty-cell">No spreads match. Try Clear filters, a wider expiration/strike range, or wait if Yahoo returned zero/missing quotes.</td></tr>`;
  }
  b.querySelectorAll("tr[data-i]").forEach(tr => tr.addEventListener("click", () => analyze(lastOptionRows[Number(tr.dataset.i)])));
}
function metric(label,val){ return `<div><span>${label}</span><strong>${val}</strong></div>`; }
function greekBox(name,val,help){ return `<div class="greek-box"><span>${name}</span><strong>${fmt(val,4)}</strong><small>${help}</small></div>`; }
function legCard(l){
  const label = `$${fmt(l.strike,0)} ${l.type === "call" ? "Call" : "Put"}`;
  return `<article class="leg-card"><div class="leg-head"><div><span class="leg-action ${l.action}">${l.action.toUpperCase()}</span><h4>${label}</h4><small>${l.contract || ""}</small></div><strong>$${fmt(l.price)}</strong></div><div class="leg-quote-grid">${metric("Bid",`$${fmt(l.bid)}`)}${metric("Ask",`$${fmt(l.ask)}`)}${metric("Mark",`$${fmt(l.mid)}`)}${metric("Last",`$${fmt(l.last)}`)}${metric("IV",pct(l.iv))}${metric("Volume",l.volume ?? "—")}${metric("Open interest",oiText(l.open_interest))}</div><div class="leg-greeks"><div><span>Delta</span><strong>${fmt(l.delta,4)}</strong></div><div><span>Gamma</span><strong>${fmt(l.gamma,4)}</strong></div><div><span>Theta</span><strong>${fmt(l.theta,4)}</strong></div><div><span>Vega</span><strong>${fmt(l.vega,4)}</strong></div><div><span>Rho</span><strong>${fmt(l.rho,4)}</strong></div></div></article>`;
}
function payoffRange(x){
  const nums = [lastSpot, x.breakeven, ...(x.legs || []).map(l => Number(l.strike))]
    .map(Number).filter(Number.isFinite);
  if(!nums.length) return {low:0, high:100};
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = Math.max(max - min, Math.abs(lastSpot || max) * 0.08, 5);
  const pad = Math.max(span * 0.22, Math.abs(lastSpot || max) * 0.035, 2);
  return {low: Math.max(0, min - pad), high: max + pad};
}
function payoffMarkers(x){
  return (x.legs || []).map(l => ({
    price:Number(l.strike),
    label:`${l.action === "sell" ? "Short" : "Long"} $${fmt(l.strike,0)}`,
    color:l.action === "sell" ? "#f87171" : "#60a5fa"
  }));
}
function profitZoneText(x){
  const s = x.strategy || "";
  if(x.breakeven == null) return "Strategy dependent";
  if(["put_credit","sell_put","cash_secured_put","call_debit","buy_call"].includes(s)) return `Above $${fmt(x.breakeven)}`;
  if(["call_credit","sell_call","covered_call","put_debit","buy_put"].includes(s)) return `Below $${fmt(x.breakeven)}`;
  return "Around breakeven";
}
function renderPayoffSummary(x){
  const el = $("payoff-summary");
  if(!el) return;
  el.innerHTML = `
    ${metric("Current price", `$${fmt(lastSpot)}`)}
    ${metric("Breakeven", x.breakeven == null ? "—" : `$${fmt(x.breakeven)}`)}
    ${metric("Max profit", x.max_profit == null ? "Strategy dependent" : `$${fmt(x.max_profit)}`)}
    ${metric("Max loss", x.max_loss == null ? "Strategy dependent" : `$${fmt(x.max_loss)}`)}
    ${metric("Profit zone", profitZoneText(x))}
  `;
}
async function analyze(x, isBest=false){
  const analysisPanel = $("trade-analysis");
  if(analysisPanel){
    analysisPanel.classList.remove("hidden");
    analysisPanel.scrollIntoView({behavior:"smooth", block:"start"});
  }
  bindTradeActionButtons(x);
  renderSelectedTradeSummary(x);
  $("analysis-title").textContent = `${isBest ? "★ Best Match · " : ""}${labelStrategy(x.strategy)}`;
  $("analysis-subtitle").textContent = `${$("underlying").textContent} · ${x.expiration || $("expiration").value} · ${x.dte ?? "—"} DTE`;
  const bb = $("analysis-bias");
  bb.textContent = (x.bias || direction).toUpperCase();
  bb.className = `bias-badge ${x.bias || direction}`;
  renderTradeQuality(x);
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
  $("leg-cards").innerHTML = orderedLegs(x).map(legCard).join("");
  renderPayoffSummary(x);

  const range = payoffRange(x);
  const d = await (await fetch("/api/options/payoff", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({legs:x.legs, spot:lastSpot, low:range.low, high:range.high})
  })).json();

  if(payoffChart) payoffChart.destroy();
  const dark = document.documentElement.dataset.theme === "dark";
  payoffChart = new Chart($("payoff-chart"), {
    type: "line",
    data: { datasets: [{
      data: (d.points || []).map(p => ({x:Number(p.price), y:Number(p.pnl)})),
      borderWidth: 2.5,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHitRadius: 12,
      tension: 0,
      fill: { target:{value:0}, above:"rgba(16,185,129,.10)", below:"rgba(239,68,68,.10)" }
    }]},
    options: {
      responsive:true,
      maintainAspectRatio:false,
      parsing:false,
      interaction:{mode:"nearest", intersect:false},
      plugins:{
        legend:{display:false},
        tooltip:{enabled:true, displayColors:false, callbacks:{
          title:items => `Underlying: $${Number(items[0].parsed.x).toFixed(2)}`,
          label:item => `P/L: ${item.parsed.y>=0?"+":""}$${Number(item.parsed.y).toFixed(2)}`
        }},
        payoffGuide:{
          spot:lastSpot,
          breakeven:x.breakeven,
          strikes:payoffMarkers(x),
          spotColor:dark?"#a78bfa":"#7c3aed",
          beColor:"#10b981",
          strikeColor:dark?"#93c5fd":"#2563eb"
        },
        payoffCrosshair:{color:dark?"rgba(156,163,175,.75)":"rgba(107,114,128,.55)"}
      },
      scales:{
        x:{
          type:"linear",
          min:range.low,
          max:range.high,
          grid:{color:dark?"rgba(255,255,255,.06)":"rgba(17,24,39,.06)"},
          ticks:{
            color:dark?"#9ca3af":"#6b7280",
            maxTicksLimit:8,
            callback:v=>"$"+Number(v).toFixed(0)
          },
          title:{display:true,text:"Underlying price at expiration",color:dark?"#9ca3af":"#6b7280"}
        },
        y:{
          grid:{color:dark?"rgba(255,255,255,.06)":"rgba(17,24,39,.06)"},
          ticks:{color:dark?"#9ca3af":"#6b7280", callback:v=>"$"+Number(v).toLocaleString()},
          title:{display:true,text:"Profit / Loss ($)",color:dark?"#9ca3af":"#6b7280"}
        }
      }
    }
  });
}


function whyMatched(x){
  const bits = [];
  if(x.quality_score != null) bits.push(`Score ${Math.round(x.quality_score)}/100`);
  if(riskText(x) !== "—") bits.push(`${riskText(x)} risk level`);
  if(criticalIssueText(x) !== "None") bits.push(`Issue: ${criticalIssueText(x)}`);
  if(x.probability_estimate != null) bits.push(`${probabilityText(x)} ${x.probability_label || "probability"}`);
  if(x.short_delta != null || x.delta != null) bits.push(`Delta ${fmt(x.short_delta ?? x.delta,3)}`);
  if(x.net_premium != null) bits.push(`${x.net_premium >= 0 ? "Credit" : "Debit"} $${fmt(Math.abs(x.net_premium))}`);
  if(x.ror != null) bits.push(`${fmt(x.ror)}% ROR`);
  if(x.open_interest != null && Number(x.open_interest) > 0) bits.push(`${x.open_interest} OI`);
  return bits.join(" · ");
}
$("best-option").addEventListener("click", () => {
  const x = [...lastOptionRows].sort((a,b) => (b.quality_score || 0) - (a.quality_score || 0))[0];
  const c = $("best-option-card");
  if(!x){
    c.classList.remove("hidden");
    c.innerHTML = '<p class="small-muted">No Best Match yet. Click Find Trades first.</p>';
    return;
  }
  c.classList.remove("hidden");
  c.innerHTML = `<div class="best-match-strip"><div><p class="eyebrow">BEST MATCH SELECTED</p><h3>${labelStrategy(x.strategy)} ${scoreBadge(x)}</h3><p class="small-muted">${whyMatched(x)}</p><div class="best-quality-row">${qualityPill(riskText(x))}${qualityPill(x.quality?.liquidity?.grade || "—")}${qualityPill(x.quality?.risk_reward?.grade || "—")}${issuePill(x)}</div></div><button id="jump-analysis" class="secondary-button">View full analysis</button></div>`;
  analyze(x, true);
  setTimeout(() => $("jump-analysis")?.addEventListener("click", () => $("trade-analysis")?.scrollIntoView({behavior:"smooth", block:"start"})), 100);
});


syncStrategies();


$("filters-toggle")?.addEventListener("click", () => toggleFilters());
$("clear-filters")?.addEventListener("click", () => { clearFilterValues(); toggleFilters(false); });

$("close-trade-analysis")?.addEventListener("click", () => {
  $("trade-analysis")?.classList.add("hidden");
});

loadExpirations();
