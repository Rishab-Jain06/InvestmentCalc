const $ = id => document.getElementById(id);
let lastRows = [];

const money = v => v == null ? "—" : `$${Number(v).toFixed(2)}`;
const pct = v => v == null ? "—" : `${Number(v) >= 0 ? "+" : ""}${Number(v).toFixed(2)}%`;
const score = v => v == null ? "—" : `${Math.round(Number(v))}/100`;
const volume = v => v == null ? "—" : Number(v).toLocaleString();

function ratingClass(r){
  const x = String(r || "").toLowerCase();
  if(x.includes("strong buy") || x === "buy") return "positive";
  if(x.includes("sell")) return "negative";
  return "";
}
function scorePill(v, rating){
  if(v == null) return `<span class="quality-pill neutral">—</span>`;
  const n = Math.round(Number(v));
  const tone = n >= 81 ? "excellent" : n >= 61 ? "good" : n >= 41 ? "neutral" : n >= 21 ? "weak" : "poor";
  return `<span class="score-mini ${tone}">${n}</span><small class="${ratingClass(rating)}">${rating || "—"}</small>`;
}
function numOrNull(id){
  const v = $(id)?.value;
  return v === "" || v == null ? null : Number(v);
}
function values(){
  return {
    filters: {
      universe: $("screen-universe").value,
      symbols: $("screen-symbols").value,
      scan_size: Number($("screen-scan-size").value || 100),
      top_n: 10,
      min_price: numOrNull("screen-min-price"),
      max_price: numOrNull("screen-max-price"),
      overall_rating: $("screen-overall-rating").value,
      technical_rating: $("screen-technical-rating").value,
      fundamental_rating: $("screen-fundamental-rating").value,
      min_overall_score: numOrNull("screen-min-overall"),
      min_technical_score: numOrNull("screen-min-technical"),
      min_fundamental_score: numOrNull("screen-min-fundamental"),
      deep_fundamentals: $("screen-deep").checked
    }
  };
}
function toggleCustom(){
  $("custom-symbols-wrap")?.classList.toggle("hidden", $("screen-universe").value !== "custom");
}
$("screen-universe")?.addEventListener("change", toggleCustom);
toggleCustom();

function render(rows){
  const body = $("screen-body");
  if(!rows.length){
    body.innerHTML = `<tr><td colspan="8" class="empty-cell">No matches. Try lowering score filters or scanning a larger batch.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map(x => `
    <tr class="clickable-row" data-symbol="${x.symbol}">
      <td><a href="/stock/${x.symbol}"><strong>${x.symbol}</strong></a></td>
      <td>${x.company || "—"}</td>
      <td>${money(x.price)}</td>
      <td class="${(x.percent_change || 0) >= 0 ? "positive" : "negative"}">${pct(x.percent_change)}</td>
      <td>${scorePill(x.overall_score, x.overall_rating)}</td>
      <td>${scorePill(x.technical_score, x.technical_rating)}</td>
      <td>${scorePill(x.fundamental_score, x.fundamental_rating)}</td>
      <td>${volume(x.volume)}</td>
    </tr>
  `).join("");
  body.querySelectorAll("tr[data-symbol]").forEach(tr => {
    tr.addEventListener("dblclick", () => location.href = `/stock/${tr.dataset.symbol}`);
  });
}
$("run-screen").onclick = async () => {
  const v = values();
  $("screen-body").innerHTML = `<tr><td colspan="8" class="empty-cell">${dots(`Scanning ${v.filters.scan_size} stocks`)}</td></tr>`;
  $("screen-status").textContent = v.filters.deep_fundamentals
    ? "Deep mode may take longer because it can refresh fundamentals."
    : "Fast mode uses cached fundamentals when available and avoids heavy SEC refreshes.";
  try{
    const res = await fetch("/api/screener", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(v)});
    const d = await res.json();
    if(d.error) throw Error(d.error);
    lastRows = d.results || [];
    $("screen-status").textContent = `Scanned ${d.scanned || 0} of ${d.universe_count || 0} stocks · ${d.matched_count || 0} matched · showing top ${d.top_n || 10} · ${d.mode || "fast"} mode.`;
    render(lastRows);
  }catch(e){
    $("screen-body").innerHTML = `<tr><td colspan="8" class="empty-cell">Screener error: ${e.message}</td></tr>`;
    $("screen-status").textContent = "Unable to complete screener run.";
  }
};

const filterToggle=$("toggle-screener-filters");
const filterBody=$("screener-filter-body");
function setFilterCollapsed(collapsed){
  if(!filterToggle||!filterBody)return;
  filterBody.classList.toggle("collapsed", collapsed);
  filterToggle.textContent = collapsed ? "Show filters ▾" : "Hide filters ▴";
}
if(filterToggle){
  const small=window.matchMedia("(max-width: 900px)").matches;
  setFilterCollapsed(small);
  filterToggle.addEventListener("click",()=>setFilterCollapsed(!filterBody.classList.contains("collapsed")));
}

document.querySelectorAll(".filter-collapse-trigger").forEach(btn=>{
  const target=document.getElementById(`filter-section-${btn.dataset.filterTarget}`);
  if(!target)return;
  function label(){
    const base=btn.dataset.filterTarget==="score"?"Score filters":btn.dataset.filterTarget.charAt(0).toUpperCase()+btn.dataset.filterTarget.slice(1);
    btn.textContent=base + (target.classList.contains("collapsed") ? " ▾" : " ▴");
  }
  label();
  btn.addEventListener("click",()=>{target.classList.toggle("collapsed");label();});
});
