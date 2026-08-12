function newsSentimentLabel(score, fallback){
  if(score==null)return fallback||"Unavailable";
  const n=Number(score);
  if(n>=75)return "Bullish";
  if(n>=60)return "Moderately Bullish";
  if(n<=25)return "Bearish";
  if(n<=40)return "Moderately Bearish";
  return "Neutral";
}
function sentimentTone(label){
  const l=String(label||"").toLowerCase();
  if(l.includes("bullish"))return "positive";
  if(l.includes("bearish"))return "negative";
  return "";
}

let chart = null;
let statsCache = null;
const s = window.INVESTIFY_SYMBOL;
const $ = id => document.getElementById(id);
const money = v => v == null ? "—" : `$${Number(v).toLocaleString(undefined,{maximumFractionDigits:2})}`;
const num = v => v == null ? "—" : Number(v).toLocaleString();
const pct = v => v == null ? "—" : `${Number(v).toFixed(2)}%`;
const compact = v => v == null ? "—" : Intl.NumberFormat("en",{notation:"compact",maximumFractionDigits:2}).format(v);
const historyCache = {};
let latestQuote = null;

function dots(label="Loading"){return `<span class="loading-dots">${label}</span>`;}
function showErr(m){ $("error").textContent = m; $("error").classList.remove("hidden"); }

function setupStockCollapsibles(){
  const cards=[
    ["stock-signal-card","Stock signal"],
    [null,"Price chart",".chart-card"],
    [null,"Business summary",".company-overview-card"],
    [null,"Technicals",".indicator-card"],
    [null,"Key statistics",".key-stats-card"],
    [null,"SEC filings",".sec-filings-card"]
  ];
  cards.forEach(([id,title,selector])=>{
    const card=id?document.getElementById(id):document.querySelector(selector);
    if(!card || card.dataset.collapsibleReady)return;
    card.dataset.collapsibleReady="1";
    const content=document.createElement("div");
    content.className="stock-collapse-content";
    while(card.firstChild)content.appendChild(card.firstChild);
    const btn=document.createElement("button");
    btn.className="stock-collapse-toggle";
    btn.type="button";
    btn.innerHTML=`<span>${title}</span><b>Show ▾</b>`;
    card.appendChild(btn);
    card.appendChild(content);
    card.classList.add("stock-collapsible","collapsed");
    btn.addEventListener("click",()=>{
      const collapsed=card.classList.toggle("collapsed");
      btn.querySelector("b").textContent=collapsed?"Show ▾":"Hide ▴";
      if(!collapsed && chart) setTimeout(()=>chart.resize(),80);
    });
  });
}

function rememberTicker(){
  const key = "investify_recent_tickers";
  const list = JSON.parse(localStorage.getItem(key) || "[]");
  localStorage.setItem(key, JSON.stringify([s, ...list.filter(x => x !== s)].slice(0,6)));
}
function setChartPrice(v, change=null, pctChange=null, label="End price"){
  const priceEl = $("chart-price");
  const changeEl = $("chart-price-change");
  const labelEl = $("chart-price-label");
  if(priceEl) priceEl.textContent = money(v);
  if(labelEl) labelEl.textContent = label || "End price";
  if(changeEl){
    if(change == null || pctChange == null){
      changeEl.textContent = "—";
      changeEl.className = "";
    }else{
      const sign = change >= 0 ? "+" : "";
      changeEl.textContent = `${sign}$${Math.abs(change).toFixed(2)} · ${sign}${pctChange.toFixed(2)}%`;
      changeEl.className = pctChange > 0 ? "positive" : pctChange < 0 ? "negative" : "";
    }
  }
}

function setChartToQuote(){
  if(!latestQuote) return;
  setChartPrice(latestQuote.price, latestQuote.change, latestQuote.percent_change, "Current price");
}

const stockCrosshairPlugin = {
  id: "stockCrosshair",
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
if(window.Chart && !Chart.registry.plugins.get("stockCrosshair")){ Chart.register(stockCrosshairPlugin); }

function formatDateLabel(raw, range){
  const d = new Date(raw);
  if(Number.isNaN(d.getTime())) return raw;
  if(range === "1D" || range === "5D") return d.toLocaleString([], {month:"short", day:"numeric", hour:"numeric", minute:"2-digit"});
  return d.toLocaleDateString([], {month:"short", day:"numeric", year:"numeric"});
}

function formatAxisTick(raw, range){
  const d = new Date(raw);
  if(Number.isNaN(d.getTime())) return "";
  if(range === "1D") return d.toLocaleTimeString([], {hour:"numeric", minute:"2-digit"});
  if(range === "5D") return d.toLocaleDateString([], {weekday:"short", month:"numeric", day:"numeric"});
  if(["1M","3M"].includes(range)) return d.toLocaleDateString([], {month:"short", day:"numeric"});
  if(["6M","YTD","1Y"].includes(range)) return d.toLocaleDateString([], {month:"short"});
  return d.toLocaleDateString([], {month:"short", year:"2-digit"});
}

async function getHistory(range){
  if(historyCache[range]) return historyCache[range];
  const response = await fetch(`/api/history/${s}?range=${range}`);
  const data = await response.json();
  if(!data.error) historyCache[range] = data;
  return data;
}

function rangeStartClose(vals){
  for(const row of vals || []){
    const c = Number(row.close);
    if(Number.isFinite(c)) return c;
  }
  return null;
}
function setChartSnapshot(vals, range, index=null){
  if(!vals || !vals.length) return;
  const i = index == null ? vals.length - 1 : Math.max(0, Math.min(vals.length - 1, index));
  const row = vals[i];
  const close = Number(row?.close);
  const first = rangeStartClose(vals);
  if(!Number.isFinite(close) || !Number.isFinite(first) || !first) return;
  const ch = close - first;
  const pc = ch / first * 100;
  const label = index == null ? `${range} end price` : formatDateLabel(row.datetime, range);
  setChartPrice(close, ch, pc, label);
  $("range-change").textContent = `${ch>=0?"+":""}$${ch.toFixed(2)} · ${pc>=0?"+":""}${pc.toFixed(2)}%`;
  $("range-change").className = pc >= 0 ? "positive hidden" : "negative hidden";
}

async function loadQuote(){
  try{
    const q = await (await fetch(`/api/quote/${s}`)).json();
    if(q.error) throw Error(q.error);
    latestQuote = q;
    const exchange = q.exchange || q.exchange_raw || "";
    $("company").textContent = [q.name, exchange].filter(Boolean).join(" · ");
    const badge = $("market-badge");
    if(badge) badge.textContent = exchange || "Market";
    $("price").textContent = money(q.price);
    setChartToQuote();
    $("change").textContent = `${q.change>=0?"+":""}${money(q.change)} (${q.percent_change>=0?"+":""}${pct(q.percent_change)})`;
    $("change").className = `change ${q.percent_change>=0?"positive":"negative"}`;
    $("prev").textContent = money(q.previous_close);
    $("open").textContent = money(q.open);
    $("day-range").textContent = `${money(q.day_low)} – ${money(q.day_high)}`;
    $("52-range").textContent = `${money(q.fifty_two_week_low)} – ${money(q.fifty_two_week_high)}`;
    $("volume").textContent = num(q.volume);
    $("avg-volume").textContent = num(q.avg_volume);
  }catch(e){ showErr(e.message); }
}
async function loadHistory(range){
  document.querySelectorAll(".range-tab").forEach(b => b.classList.toggle("active", b.dataset.range === range));
  const d = await getHistory(range);
  if(d.error){ showErr(d.error); return; }
  const vals = d.values || [];
  setChartToQuote();

  if(chart) chart.destroy();
  const dark = document.documentElement.dataset.theme === "dark";
  const labels = vals.map(x => x.datetime);
  const canvas = $("price-chart");
  chart = new Chart(canvas, {
    type: "line",
    data: { labels, datasets: [{
      data: vals.map(x => x.close),
      borderWidth: 2.3,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHitRadius: 12,
      tension: .12,
      fill: { target: "origin", above: dark ? "rgba(59,130,246,.07)" : "rgba(91,78,229,.06)" }
    }]},
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      onHover: (event, active) => {
        if(active && active.length){
          setChartSnapshot(vals, range, active[0].index);
        }
      },
      plugins: {
        legend: { display:false },
        tooltip: {
          enabled:true,
          displayColors:false,
          callbacks: {
            title: items => formatDateLabel(items[0].label, range),
            label: item => `Price: $${Number(item.parsed.y).toFixed(2)}`,
            afterLabel: item => {
              const row = vals[item.dataIndex];
              return row?.volume != null ? `Volume: ${Number(row.volume).toLocaleString()}` : "";
            }
          }
        },
        stockCrosshair: { color: dark ? "rgba(156,163,175,.75)" : "rgba(107,114,128,.55)" }
      },
      scales: {
        x: {
          display:true,
          ticks:{
            color:dark?"#9ca3af":"#6b7280",
            maxRotation:0,
            autoSkip:true,
            maxTicksLimit: range === "1D" ? 6 : 7,
            callback:function(value, index){
              return formatAxisTick(labels[index], range);
            }
          },
          grid:{ color:dark?"rgba(255,255,255,.03)":"rgba(17,24,39,.035)" }
        },
        y: {
          ticks:{ color:dark?"#9ca3af":"#6b7280", callback:v=>"$"+v },
          grid:{ color:dark?"rgba(255,255,255,.05)":"rgba(17,24,39,.05)" }
        }
      }
    }
  });
  canvas.onmouseleave = () => setChartToQuote();
  $("range-label").textContent = range;
}
document.querySelectorAll(".range-tab").forEach(b => b.addEventListener("click", () => loadHistory(b.dataset.range)));

function statBox(label,val,extra=""){ return `<div class="overall-mini-tile"><span>${label}</span><strong>${val}</strong>${extra?`<small>${extra}</small>`:""}</div>`; }
function ratingPill(score, label){
  const tone = signalTone(score);
  return `<span class="rating-pill ${tone}">${label || signalRating(score)}</span>`;
}
function helpTip(text){ return `<b class="metric-help" tabindex="0">?<i>${text}</i></b>`; }
const metricHelp = {
  "RSI 14":"Momentum oscillator from 0–100. Above 50 leans bullish; below 50 leans weak. Very high/low can mean extended/oversold.",
  "MACD":"Trend momentum indicator comparing short and long EMAs. Positive usually supports bullish momentum.",
  "MACD Hist.":"MACD minus its signal line. Rising or positive histogram shows improving momentum; negative shows weakness.",
  "ATR 14":"Average True Range over 14 periods. Higher ATR means larger daily moves and more volatility risk.",
  "EMA 20":"Short-term exponential moving average. Price above it usually supports near-term trend.",
  "EMA 50":"Medium-term exponential moving average. Used as a key trend filter.",
  "EMA 200":"Long-term exponential moving average. Helps identify larger trend direction.",
  "SMA 20":"Simple 20-period average. A short-term trend reference.",
  "SMA 50":"Simple 50-period average. A medium-term trend reference.",
  "SMA 200":"Simple 200-period average. A long-term trend reference.",
  "BB Upper":"Upper Bollinger Band. Price near this area can be strong but extended.",
  "BB Lower":"Lower Bollinger Band. Price near this area can be weak or oversold.",
  "OBV":"On-Balance Volume. Attempts to show whether volume is accumulating or distributing.",
  market_cap:"Company equity value in the market. Larger companies can be more stable but may grow slower.",
  enterprise_value:"Market cap plus debt minus cash. Useful for comparing acquisition-style company value.",
  shares_outstanding:"Total shares currently outstanding. Used for market cap and per-share metrics.",
  float_shares:"Shares generally available for public trading. Lower float can mean larger price swings.",
  beta:"Sensitivity to market movement. Above 1 is more volatile than the market; below 1 is less volatile.",
  avg_volume:"Average trading volume. Higher volume usually means better liquidity.",
  trailing_pe:"Price divided by trailing earnings per share. Lower can mean cheaper, but growth and quality matter.",
  forward_pe:"Price divided by expected future EPS. Useful when earnings are expected to change.",
  peg_ratio:"P/E adjusted for growth. Around 1–2 is often more reasonable than high PEG.",
  price_to_sales:"Price relative to revenue. Useful when earnings are low or volatile.",
  price_to_book:"Price relative to book value. More useful for banks/financials than software firms.",
  ev_to_revenue:"Enterprise value relative to revenue. Helpful for comparing companies with different debt levels.",
  ev_to_ebitda:"Enterprise value relative to EBITDA. Lower can be cheaper, but industry matters.",
  profit_margin:"Net income as a percent of revenue. Higher margin means more revenue turns into profit.",
  gross_margin:"Gross profit as a percent of revenue. Shows pricing power and direct cost efficiency.",
  operating_margin:"Operating income as a percent of revenue. Shows core business profitability.",
  roe:"Return on equity. Measures profit generated from shareholder equity.",
  roa:"Return on assets. Measures profit generated from the asset base.",
  revenue:"Total sales generated by the company.",
  revenue_growth:"Revenue growth rate. Shows whether sales are expanding or contracting.",
  ebitda:"Earnings before interest, taxes, depreciation and amortization. A cash-flow style profitability proxy.",
  free_cash_flow:"Cash left after operating cash flow and capital expenditures. Important for buybacks, dividends and debt paydown.",
  operating_cash_flow:"Cash generated from operations before capital expenditures.",
  cash:"Cash and equivalents available on the balance sheet.",
  debt:"Debt obligations. Should be compared with cash and earnings power.",
  current_ratio:"Current assets divided by current liabilities. Above 1 usually means near-term liquidity is healthier.",
  quick_ratio:"Liquid assets divided by current liabilities. Stricter liquidity test than current ratio.",
  trailing_eps:"Earnings per share over the trailing period.",
  forward_eps:"Expected future earnings per share.",
  yield:"Annual dividend yield as a percent of stock price.",
  rate:"Annual dividend amount per share.",
  payout_ratio:"Percent of earnings paid as dividends. Very high payout can be risky.",
  ex_dividend_date:"Date after which buyers no longer receive the next dividend."
};
function metricCard(label, val, desc="", score=null){
  return `<div class="metric-card"><span>${label}${desc ? helpTip(desc) : ""}</span><strong>${val}</strong>${score==null?"":`<small>${score}</small>`}</div>`;
}
function detailsGroup(title, subtitle, cards, open=false){
  return `<details class="metric-group" ${open?"open":""}><summary><div><strong>${title}</strong><small>${subtitle||""}</small></div><span>${cards.length} metrics</span></summary><div class="metric-card-grid">${cards.join("")}</div></details>`;
}
async function loadTechnicals(){
  const t = await (await fetch(`/api/technicals/${s}`)).json();
  const groups = [
    ["Trend", "Moving averages and price trend references", [["EMA 20",money(t.ema20)],["EMA 50",money(t.ema50)],["EMA 200",money(t.ema200)],["SMA 20",money(t.sma20)],["SMA 50",money(t.sma50)],["SMA 200",money(t.sma200)]]],
    ["Momentum", "RSI and MACD momentum indicators", [["RSI 14",t.rsi14?.toFixed(1)],["MACD",t.macd?.toFixed(3)],["MACD Hist.",t.macd_histogram?.toFixed(3)]]],
    ["Volatility", "ATR and Bollinger Band context", [["ATR 14",t.atr14?.toFixed(2)],["BB Upper",money(t.bb_upper)],["BB Lower",money(t.bb_lower)]]],
    ["Volume", "Volume-based confirmation", [["OBV",compact(t.obv)]]]
  ];
  $("technical-grid").innerHTML = groups.map((g,i) => detailsGroup(g[0], g[1], g[2].map(([a,b]) => metricCard(a, b ?? "—", metricHelp[a] || "")), i<2)).join("");
}
async function loadStats(){ statsCache = await (await fetch(`/api/stats/${s}`)).json(); renderStats("market"); }
const labels = {market_cap:"Market Cap",enterprise_value:"Enterprise Value",shares_outstanding:"Shares Outstanding",float_shares:"Float",beta:"Beta",avg_volume:"Avg Volume",fifty_day_average:"50D Avg",two_hundred_day_average:"200D Avg",fifty_two_week_low:"52W Low",fifty_two_week_high:"52W High",trailing_pe:"P/E (TTM)",forward_pe:"Forward P/E",peg_ratio:"PEG",price_to_sales:"Price / Sales",price_to_book:"Price / Book",ev_to_revenue:"EV / Revenue",ev_to_ebitda:"EV / EBITDA",profit_margin:"Profit Margin",gross_margin:"Gross Margin",operating_margin:"Operating Margin",roe:"ROE",roa:"ROA",revenue:"Revenue",revenue_growth:"Revenue Growth",ebitda:"EBITDA",free_cash_flow:"Free Cash Flow",operating_cash_flow:"Operating Cash Flow",cash:"Cash",debt:"Debt",current_ratio:"Current Ratio",quick_ratio:"Quick Ratio",trailing_eps:"EPS (TTM)",forward_eps:"Forward EPS",yield:"Dividend Yield",rate:"Dividend Rate",payout_ratio:"Payout Ratio",ex_dividend_date:"Ex-Dividend"};
function formatStat(k,v){
  let d = v;
  if(["market_cap","enterprise_value","shares_outstanding","float_shares","avg_volume","revenue","ebitda","free_cash_flow","operating_cash_flow","cash","debt"].includes(k)) d = compact(v);
  else if(["profit_margin","gross_margin","operating_margin","roe","roa","revenue_growth","yield","payout_ratio"].includes(k)) d = v == null ? "—" : pct(v);
  else if(["fifty_day_average","two_hundred_day_average","fifty_two_week_low","fifty_two_week_high","rate"].includes(k)) d = money(v);
  else if(v == null) d = "—"; else if(typeof v === "number") d = Number(v).toFixed(2);
  return d;
}
function renderStats(tab){
  document.querySelectorAll("#stats-tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  const o = statsCache?.[tab] || {};
  const entries = Object.entries(o).map(([k,v]) => metricCard(labels[k] || k, formatStat(k,v), metricHelp[k] || ""));
  $("stats-content").innerHTML = `<div class="metric-card-grid stats-card-grid">${entries.join("") || '<p class="small-muted">No company metrics available.</p>'}</div>`;
}
document.querySelectorAll("#stats-tabs button").forEach(b => b.addEventListener("click", () => renderStats(b.dataset.tab)));

let signalData = null;
let activeSignalTab = "overall";

function signalTone(score){
  if(score == null) return "";
  if(score >= 61) return "positive";
  if(score <= 40) return "negative";
  return "";
}
function signalRating(score){
  if(score == null) return "Unavailable";
  if(score >= 81) return "Strong Buy";
  if(score >= 61) return "Buy";
  if(score >= 41) return "Hold";
  if(score >= 21) return "Sell";
  return "Strong Sell";
}
function scoreText(score){
  return score == null ? "—" : `${Math.round(score)}/100`;
}
function signalComponentCard(c){
  const score = c.score == null ? 0 : Number(c.score);
  const points = c.points == null ? "—" : Math.round(c.points);
  const missing = c.missing?.length ? `<small>Missing: ${c.missing.slice(0,3).join(", ")}${c.missing.length>3 ? "…" : ""}</small>` : "";
  return `<div class="signal-component">
    <div><span>${c.label}</span><strong>${points}/${c.weight}</strong></div>
    <div class="signal-bar"><i style="width:${Math.max(0,Math.min(100,score))}%"></i></div>
    <small>${c.details || ""}</small>
    ${missing}
  </div>`;
}
const fundamentalGroups = [
  ["Valuation", "Is the stock price fair?", ["P/E", "Forward P/E", "P/FCF", "PEG"]],
  ["Financial Health", "Is the balance sheet safe?", ["Net Debt / EBITDA", "Interest Coverage", "Altman Z-Score"]],
  ["Profitability & Efficiency", "How well is management operating?", ["ROIC", "Gross Margin", "Operating Margin", "Profit Margin"]],
  ["Growth & Earnings Quality", "Is the cash real?", ["Revenue CAGR/Growth", "Net Income CAGR", "FCF Conversion"]]
];
const fundamentalHelp = {
  "P/E":"Price divided by earnings. Lower can be cheaper, but growth and quality matter.",
  "Forward P/E":"Price divided by expected future earnings. Helps compare current valuation to expected profit.",
  "P/FCF":"Market value divided by free cash flow. Shows price relative to actual cash generation.",
  "PEG":"P/E adjusted for growth. A high P/E is more acceptable when growth is also high.",
  "Net Debt / EBITDA":"Net debt divided by EBITDA. Above 3.5x–4.0x can signal elevated balance-sheet risk.",
  "Interest Coverage":"EBIT divided by interest expense. Higher means the company can cover debt costs more comfortably.",
  "Altman Z-Score":"Composite solvency score. Higher generally suggests lower financial distress risk.",
  "ROIC":"Return on invested capital. High sustained ROIC can indicate strong capital efficiency and a moat.",
  "Gross Margin":"Gross profit divided by revenue. Higher can signal pricing power or lower direct costs.",
  "Operating Margin":"Operating income divided by revenue. Shows core business profitability.",
  "Profit Margin":"Net income divided by revenue. Shows how much revenue becomes profit after all costs.",
  "Revenue CAGR/Growth":"Compound or recent revenue growth. Shows whether sales are expanding.",
  "Net Income CAGR":"Compound net income growth over recent annual periods where SEC data is available.",
  "FCF Conversion":"Free cash flow divided by net income. Above 1.0 means reported earnings convert well to cash."
};
function renderFundamentalGroups(metrics){
  return fundamentalGroups.map((g,i) => {
    const cards = g[2].map(name => {
      const m = metrics?.[name] || {label:name, display:"—", score:null};
      const score = m.score == null ? "No score" : `${Math.round(m.score)}/100`;
      return metricCard(m.label || name, m.display ?? "—", fundamentalHelp[name] || "", score);
    });
    return detailsGroup(g[0], g[1], cards, i===0);
  }).join("");
}
function renderOverallSignal(d){
  const t = d.technical || {};
  const f = d.fundamental || {};
  const score = d.score == null ? 0 : Math.max(0, Math.min(100, Number(d.score)));
  const weights = d.weights || {technical:50, fundamental:50};
  const cap = d.cap_reason ? `<div class="overall-cap-note">${d.cap_reason}</div>` : "";
  const raw = d.raw_score != null && Math.round(d.raw_score) !== Math.round(d.score ?? d.raw_score)
    ? `<small>Raw blend ${Math.round(d.raw_score)}/100 before risk cap</small>` : "";
  return `
    <div class="overall-hero-card compact-overall-hero">
      <div>
        <span>Overall stock score</span>
        <strong class="${signalTone(d.score)}">${d.rating || signalRating(d.score)}</strong>
        <p>${d.summary || "Overall dynamically blends technical and fundamental scores."}</p>
        ${raw}
      </div>
      <div class="overall-score-ring"><b>${scoreText(d.score)}</b><i style="width:${score}%"></i></div>
    </div>
    ${cap}
    <div class="overall-signal-grid refined-overall-grid compact-overall-grid">
      ${statBox("Technical", scoreText(t.score), `${ratingPill(t.score, (t.signal || "—").toUpperCase())} · ${weights.technical ?? 0}% weight`)}
      ${statBox("Fundamental", scoreText(f.score), `${ratingPill(f.score, f.rating || "—")} · ${weights.fundamental ?? 0}% weight`)}
      ${statBox("Blend rule", `${weights.technical ?? 0}/${weights.fundamental ?? 0}`, "Tech/Fund · adjusts by data confidence")}
    </div>
    <details class="signal-details" open>
      <summary>How is overall calculated?</summary>
      <p class="small-muted">Overall uses a dynamic blend. High-confidence fundamentals weight fundamental quality more heavily; low-confidence fundamentals weight technicals more heavily. Severe weakness in either technicals or fundamentals can cap the final rating.</p>
    </details>`;
}
function renderTechnicalIndicatorGroups(t){
  const raw = t.technicals || {};
  const groups = [
    ["Trend", "EMA/SMA structure", [["EMA 20",money(raw.ema20)],["EMA 50",money(raw.ema50)],["EMA 200",money(raw.ema200)],["SMA 50",money(raw.sma50)],["SMA 200",money(raw.sma200)]]],
    ["Momentum", "RSI and MACD", [["RSI 14",raw.rsi14?.toFixed?.(1)],["MACD",raw.macd?.toFixed?.(3)],["MACD Hist.",raw.macd_histogram?.toFixed?.(3)]]],
    ["Volatility", "Risk context", [["ATR 14",raw.atr14?.toFixed?.(2)],["ATR %",raw.atr_pct == null ? "—" : raw.atr_pct.toFixed(2)+"%"],["Distance EMA20",raw.distance_ema20_pct == null ? "—" : raw.distance_ema20_pct.toFixed(2)+"%"]]]
  ];
  return `<div class="technical-groups">${groups.map((g,i)=>detailsGroup(g[0], g[1], g[2].map(([a,b])=>metricCard(a,b??"—",metricHelp[a]||"")), i===0)).join("")}</div>`;
}
function renderTechnicalSignal(t){
  return `
    <div class="signal-tab-head">
      <div><h3>${(t.signal || "—").toUpperCase()} technical setup</h3><p class="small-muted">${t.summary || "Weighted technical model."}</p></div>
      <strong class="mini-score ${signalTone(t.score)}">${scoreText(t.score)}</strong>
    </div>
    <div class="signal-components">${(t.components || []).map(signalComponentCard).join("")}</div>
    <div class="signal-reasons">${(t.chips || t.reasons || []).map(x => `<span>${x}</span>`).join("")}</div>
    ${renderTechnicalIndicatorGroups(t)}
    <details class="signal-details">
      <summary>How is this calculated?</summary>
      <p class="small-muted">Technical Score = Trend Structure 40% + Momentum 25% + Price Strength 20% + Volatility Context 15%. It uses EMA20/EMA50, EMA50 slope, RSI range, MACD histogram direction, recent return, distance from EMAs and ATR%.</p>
    </details>`;
}
function renderFundamentalSignal(f){
  return `
    <div class="signal-tab-head">
      <div><h3>${f.rating || "Unavailable"} fundamental setup</h3><p class="small-muted">${f.summary || "Fundamental score unavailable."}</p></div>
      <strong class="mini-score ${signalTone(f.score)}">${scoreText(f.score)}</strong>
    </div>
    <div class="fundamental-confidence">
      <span>Confidence: ${f.confidence || "—"}</span>
      <span>Available metrics: ${f.available_metrics ?? "—"}/${f.total_metrics ?? "—"}</span>
      <span>Source: ${f.source || "Yahoo + SEC"}</span>
    </div>
    <div class="signal-components">${(f.components || []).map(signalComponentCard).join("")}</div>
    ${renderFundamentalGroups(f.metrics || {})}
    <details class="signal-details">
      <summary>How is this calculated?</summary>
      <p class="small-muted">Fundamental Score = Valuation 30% + Financial Health 25% + Profitability & Efficiency 25% + Growth & Earnings Quality 20%. Missing metrics are shown and reduce confidence rather than being silently treated as zero.</p>
    </details>`;
}
function renderSignal(){
  if(!signalData) return;
  const body = $("signal-body");
  if(!body) return;
  document.querySelectorAll("#signal-tabs button").forEach(b => b.classList.toggle("active", b.dataset.signalTab === activeSignalTab));
  const headerScore = signalData.score;
  $("signal-label").textContent = activeSignalTab === "technical"
    ? (signalData.technical?.signal || "unknown").toUpperCase()
    : activeSignalTab === "fundamental"
      ? (signalData.fundamental?.rating || "Unavailable")
      : (signalData.rating || signalRating(headerScore));
  $("signal-label").className = signalTone(activeSignalTab === "technical" ? signalData.technical?.score : activeSignalTab === "fundamental" ? signalData.fundamental?.score : headerScore);
  $("signal-score").textContent = activeSignalTab === "technical"
    ? scoreText(signalData.technical?.score)
    : activeSignalTab === "fundamental"
      ? scoreText(signalData.fundamental?.score)
      : scoreText(headerScore);
  $("signal-summary").textContent = activeSignalTab === "technical"
    ? "Technical analysis uses trend, momentum, price strength and volatility."
    : activeSignalTab === "fundamental"
      ? "Fundamental analysis uses valuation, balance sheet safety, profitability and earnings quality."
      : "Overall blends technical and fundamental scores equally.";
  if(activeSignalTab === "technical") body.innerHTML = renderTechnicalSignal(signalData.technical || {});
  else if(activeSignalTab === "fundamental") body.innerHTML = renderFundamentalSignal(signalData.fundamental || {});
  else body.innerHTML = renderOverallSignal(signalData);
}
async function loadSignal(){
  try{
    const a = await (await fetch(`/api/stock-signal/${s}`)).json();
    if(a.error) throw Error(a.error);
    signalData = a;
    renderSignal();
  }catch(e){
    $("signal-label").textContent = "UNAVAILABLE";
    $("signal-score").textContent = "—";
    $("signal-body").innerHTML = '<p class="small-muted">Stock signal unavailable.</p>';
  }
}
document.querySelectorAll("#signal-tabs button").forEach(b => b.addEventListener("click", () => {
  activeSignalTab = b.dataset.signalTab;
  renderSignal();
}));

async function loadSecFilings(){
  const el = $("sec-filings");
  if(!el) return;
  try{
    const d = await (await fetch(`/api/sec-filings/${s}`)).json();
    if(d.error) throw Error(d.error);
    const rows = d.filings || [];
    if(!rows.length){ el.textContent = "No recent SEC filings found."; return; }
    el.innerHTML = rows.map(f => `<a class="filing-row" href="${f.url || "#"}" target="_blank" rel="noopener">
      <strong>${f.form}</strong><span>Filed ${f.filing_date || "—"}</span><span>Report ${f.report_date || "—"}</span>
    </a>`).join("");
  }catch(e){
    el.textContent = `SEC filings unavailable: ${e.message}`;
  }
}

async function loadCompanySummary(refresh=false){
  const box = $("company-summary");
  const btn = $("generate-company-summary");
  if(!box || !btn) return;
  btn.disabled = true;
  btn.innerHTML = refresh ? dots("Refreshing") : dots("Generating");
  box.innerHTML = dots("Generating company overview");
  try{
    const d = await (await fetch(`/api/company-summary/${s}${refresh ? "?refresh=1" : ""}`, {method:"POST"})).json();
    if(d.error) throw Error(d.error);
    box.innerHTML = `<p>${d.summary || "Summary unavailable."}</p><small>Mode: ${d.mode || "—"}${d.model ? " · " + d.model : ""}${d.cached ? " · cached" : ""}</small>`;
  }catch(e){
    box.textContent = `Company summary unavailable: ${e.message}`;
  }finally{
    btn.disabled = false;
    btn.textContent = "Generate AI summary";
  }
}
document.getElementById("generate-company-summary")?.addEventListener("click", () => loadCompanySummary(false));

const K = "investify_watchlist";
const watchButton = $("watch-btn");
function getWatch(){ return JSON.parse(localStorage.getItem(K) || "[]"); }
function syncWatch(){ watchButton.textContent = getWatch().includes(s) ? "★ Watching" : "☆ Watch"; }
watchButton.addEventListener("click", () => {
  let a = getWatch();
  a = a.includes(s) ? a.filter(x => x !== s) : [...a, s];
  localStorage.setItem(K, JSON.stringify(a));
  syncWatch();
});
syncWatch();
setupStockCollapsibles();
rememberTicker();
loadQuote();
loadHistory(localStorage.getItem("investify_default_range") || "1D");
loadTechnicals();
loadStats();
loadSignal();
loadSecFilings();

// v16 Ask AI about this stock: no Gemini call here; it only passes context to AI Search.
function sendStockToAI(){
  const payload = {
    ticker: s,
    source: "Stock Research",
    createdAt: new Date().toISOString(),
    stock_context: {
      symbol: s,
      company: document.getElementById("company")?.textContent || "",
      price: document.getElementById("price")?.textContent || "",
      change: document.getElementById("change")?.textContent || "",
      range: document.getElementById("range-label")?.textContent || "",
      note: "This context was sent from Stock Research. Gemini is only called after the user sends a message in AI Search."
    }
  };
  localStorage.setItem("investify_pending_ai_context", JSON.stringify(payload));
  window.location.href = "/search";
}
document.addEventListener("DOMContentLoaded", () => {
  const ask = document.getElementById("ask-ai-stock");
  if(ask) ask.onclick = sendStockToAI;
});
