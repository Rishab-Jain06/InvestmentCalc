const RECENT_KEY = "investify_recent_tickers";
function recentTickers(){ return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]"); }
function saveRecentTicker(symbol){
  const s = symbol.trim().toUpperCase();
  if(!s) return;
  const next = [s, ...recentTickers().filter(x => x !== s)].slice(0, 6);
  localStorage.setItem(RECENT_KEY, JSON.stringify(next));
}
function renderRecentTickers(){
  const box = document.getElementById("recent-tickers");
  if(!box) return;
  const list = recentTickers();
  if(!list.length){ box.classList.add("hidden"); return; }
  box.classList.remove("hidden");
  box.innerHTML = "<span>Recent</span>" + list.map(s => `<a href="/stock/${encodeURIComponent(s)}">${s}</a>`).join("");
}
const form = document.getElementById("ticker-form");
if(form){
  form.addEventListener("submit", e => {
    e.preventDefault();
    const s = document.getElementById("ticker").value.trim().toUpperCase();
    if(s){ saveRecentTicker(s); location.href = `/stock/${encodeURIComponent(s)}`; }
  });
}
renderRecentTickers();
