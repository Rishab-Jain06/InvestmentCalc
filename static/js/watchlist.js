const KEY="investify_watchlist";
const get=()=>JSON.parse(localStorage.getItem(KEY)||'["SPY","QQQ"]');
const set=x=>localStorage.setItem(KEY,JSON.stringify(x));
const grid=document.getElementById("watch-grid"), empty=document.getElementById("watch-empty");
async function render(){
  const syms=[...new Set(get().map(x=>x.toUpperCase()))];
  grid.innerHTML=""; empty.classList.toggle("hidden",syms.length>0);
  for(const s of syms){
    const a=document.createElement("div");a.className="market-tile watch-tile";a.innerHTML=`<a href="/stock/${s}"><span class="symbol">${s}</span><strong class="m-price">—</strong><span class="m-change muted">Loading…</span></a><button class="remove-watch" data-s="${s}">×</button>`;grid.appendChild(a);
    try{const r=await fetch(`/api/quote/${s}`),q=await r.json();a.querySelector(".m-price").textContent=`$${Number(q.price).toFixed(2)}`;const c=Number(q.percent_change||0);const e=a.querySelector(".m-change");e.textContent=`${c>=0?"+":""}${c.toFixed(2)}%`;e.className=`m-change ${c>=0?"positive":"negative"}`;}catch(e){a.querySelector(".m-change").textContent="Unavailable";}
  }
  document.querySelectorAll(".remove-watch").forEach(b=>b.onclick=()=>{set(get().filter(x=>x.toUpperCase()!=b.dataset.s));render();});
}
document.getElementById("watch-add").onclick=()=>{const i=document.getElementById("watch-input");const s=i.value.trim().toUpperCase();if(s){set([...get(),s]);i.value="";render();}};
render();