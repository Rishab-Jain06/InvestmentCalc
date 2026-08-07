let chart = null;
let statsCache = null;
const s = window.INVESTIFY_SYMBOL;
const $ = id => document.getElementById(id);
const money = v => v == null ? "—" : `$${Number(v).toLocaleString(undefined,{maximumFractionDigits:2})}`;
const num = v => v == null ? "—" : Number(v).toLocaleString();
const pct = v => v == null ? "—" : `${Number(v).toFixed(2)}%`;
const compact = v => v == null ? "—" : Intl.NumberFormat("en",{notation:"compact",maximumFractionDigits:2}).format(v);

function showErr(m){ $("error").textContent = m; $("error").classList.remove("hidden"); }
function rememberTicker(){
  const key = "investify_recent_tickers";
  const list = JSON.parse(localStorage.getItem(key) || "[]");
  localStorage.setItem(key, JSON.stringify([s, ...list.filter(x => x !== s)].slice(0,6)));
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

async function loadQuote(){
  try{
    const q = await (await fetch(`/api/quote/${s}`)).json();
    if(q.error) throw Error(q.error);
    $("company").textContent = [q.name, q.exchange].filter(Boolean).join(" · ");
    $("price").textContent = money(q.price);
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
  const d = await (await fetch(`/api/history/${s}?range=${range}`)).json();
  if(d.error){ showErr(d.error); return; }
  const vals = d.values || [];
  const closes = vals.map(x => Number(x.close)).filter(x => !Number.isNaN(x));
  if(closes.length > 1){
    const ch = closes.at(-1) - closes[0];
    const pc = closes[0] ? ch / closes[0] * 100 : 0;
    $("range-change").textContent = `${ch>=0?"+":""}$${ch.toFixed(2)} · ${pc>=0?"+":""}${pc.toFixed(2)}%`;
    $("range-change").className = pc >= 0 ? "positive" : "negative";
  }
  if(chart) chart.destroy();
  const dark = document.documentElement.dataset.theme === "dark";
  chart = new Chart($("price-chart"), {
    type: "line",
    data: { labels: vals.map(x => x.datetime), datasets: [{
      data: vals.map(x => x.close), borderWidth: 2.3, pointRadius: 0, pointHoverRadius: 5, pointHitRadius: 12, tension: .12,
      fill: { target: "origin", above: dark ? "rgba(59,130,246,.07)" : "rgba(91,78,229,.06)" }
    }]},
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display:false },
        tooltip: { enabled:true, displayColors:false, callbacks: {
          title: items => formatDateLabel(items[0].label, range),
          label: item => `Price: $${Number(item.parsed.y).toFixed(2)}`,
          afterLabel: item => {
            const row = vals[item.dataIndex];
            return row?.volume != null ? `Volume: ${Number(row.volume).toLocaleString()}` : "";
          }
        }},
        stockCrosshair: { color: dark ? "rgba(156,163,175,.75)" : "rgba(107,114,128,.55)" }
      },
      scales: { x: { display:false }, y: { ticks:{ color:dark?"#9ca3af":"#6b7280", callback:v=>"$"+v }, grid:{ color:dark?"rgba(255,255,255,.05)":"rgba(17,24,39,.05)" } } }
    }
  });
  $("range-label").textContent = range;
}
document.querySelectorAll(".range-tab").forEach(b => b.addEventListener("click", () => loadHistory(b.dataset.range)));

function statBox(label,val){ return `<div><span>${label}</span><strong>${val}</strong></div>`; }
async function loadTechnicals(){
  const t = await (await fetch(`/api/technicals/${s}`)).json();
  const vals = [["RSI 14",t.rsi14?.toFixed(1)],["MACD",t.macd?.toFixed(3)],["MACD Hist.",t.macd_histogram?.toFixed(3)],["ATR 14",t.atr14?.toFixed(2)],["EMA 20",money(t.ema20)],["EMA 50",money(t.ema50)],["EMA 200",money(t.ema200)],["SMA 20",money(t.sma20)],["SMA 50",money(t.sma50)],["SMA 200",money(t.sma200)],["BB Upper",money(t.bb_upper)],["BB Lower",money(t.bb_lower)],["OBV",compact(t.obv)]];
  $("technical-grid").innerHTML = vals.map(([a,b]) => statBox(a,b ?? "—")).join("");
}
async function loadStats(){ statsCache = await (await fetch(`/api/stats/${s}`)).json(); renderStats("market"); }
const labels = {market_cap:"Market Cap",enterprise_value:"Enterprise Value",shares_outstanding:"Shares Outstanding",float_shares:"Float",beta:"Beta",avg_volume:"Avg Volume",fifty_day_average:"50D Avg",two_hundred_day_average:"200D Avg",fifty_two_week_low:"52W Low",fifty_two_week_high:"52W High",trailing_pe:"P/E (TTM)",forward_pe:"Forward P/E",peg_ratio:"PEG",price_to_sales:"Price / Sales",price_to_book:"Price / Book",ev_to_revenue:"EV / Revenue",ev_to_ebitda:"EV / EBITDA",profit_margin:"Profit Margin",gross_margin:"Gross Margin",operating_margin:"Operating Margin",roe:"ROE",roa:"ROA",revenue:"Revenue",revenue_growth:"Revenue Growth",ebitda:"EBITDA",free_cash_flow:"Free Cash Flow",operating_cash_flow:"Operating Cash Flow",cash:"Cash",debt:"Debt",current_ratio:"Current Ratio",quick_ratio:"Quick Ratio",trailing_eps:"EPS (TTM)",forward_eps:"Forward EPS",yield:"Dividend Yield",rate:"Dividend Rate",payout_ratio:"Payout Ratio",ex_dividend_date:"Ex-Dividend"};
function renderStats(tab){
  document.querySelectorAll("#stats-tabs button").forEach(b => b.classList.toggle("active", b.dataset.tab === tab));
  const o = statsCache?.[tab] || {};
  $("stats-content").innerHTML = Object.entries(o).map(([k,v]) => {
    let d = v;
    if(["market_cap","enterprise_value","shares_outstanding","float_shares","avg_volume","revenue","ebitda","free_cash_flow","operating_cash_flow","cash","debt"].includes(k)) d = compact(v);
    else if(["profit_margin","gross_margin","operating_margin","roe","roa","revenue_growth","yield","payout_ratio"].includes(k)) d = v == null ? "—" : pct(v);
    else if(["fifty_day_average","two_hundred_day_average","fifty_two_week_low","fifty_two_week_high","rate"].includes(k)) d = money(v);
    else if(v == null) d = "—"; else if(typeof v === "number") d = Number(v).toFixed(2);
    return statBox(labels[k] || k, d);
  }).join("");
}
document.querySelectorAll("#stats-tabs button").forEach(b => b.addEventListener("click", () => renderStats(b.dataset.tab)));
$("analyze-btn").addEventListener("click", async () => {
  const a = await (await fetch(`/api/analyze/${s}`)).json();
  $("signal-card").classList.remove("hidden");
  $("signal-label").textContent = (a.signal || "unknown").toUpperCase();
  $("signal-label").className = a.signal === "bullish" ? "positive" : a.signal === "bearish" ? "negative" : "";
  $("signal-score").textContent = `${a.score}/100`;
  $("signal-reasons").innerHTML = (a.reasons || []).map(x => `<span>${x}</span>`).join("");
});
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
rememberTicker();
loadQuote();
loadHistory(localStorage.getItem("investify_default_range") || "1D");
loadTechnicals();
loadStats();
