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
  form.addEventListener("submit", async e => {
    e.preventDefault();
    const input = document.getElementById("ticker");
    let s = input.value.trim().toUpperCase();
    if(window.InvestifySymbols?.resolveInput){
      try{s = await window.InvestifySymbols.resolveInput(input);}catch{}
    }
    s = String(s||"").trim().toUpperCase();
    if(s){ saveRecentTicker(s); location.href = `/stock/${encodeURIComponent(s)}`; }
  });
}
renderRecentTickers();

// v46 home portfolio snapshot
(async function renderHomePortfolioSnapshot(){
  const totalEl=document.getElementById("home-portfolio-total");
  const changeEl=document.getElementById("home-portfolio-change");
  const subEl=document.getElementById("home-portfolio-sub");
  const eye=document.getElementById("home-hide-value");
  if(!totalEl||!changeEl||!subEl)return;
  const H="investify_portfolio_holdings_v1", C="investify_portfolio_cash_v1", V="investify_home_portfolio_hidden_v1", Q="investify_home_portfolio_quote_cache_v2";
  const money=v=>Number.isFinite(Number(v))?Number(v).toLocaleString(undefined,{style:"currency",currency:"USD",maximumFractionDigits:0}):"—";
  const pct=v=>Number.isFinite(Number(v))?`${Number(v)>=0?"+":""}${Number(v).toFixed(2)}%`:"—";
  const load=(k,f)=>{try{return JSON.parse(localStorage.getItem(k)||JSON.stringify(f));}catch{return f;}};
  const save=(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v));}catch{}};
  let holdings=load(H,[]), cash=load(C,[]);
  try{
    const me=await (await fetch("/api/auth/me",{cache:"no-store"})).json();
    if(me.authenticated){
      const cloud=await (await fetch("/api/cloud/portfolio",{cache:"no-store"})).json();
      if(!cloud.error){
        holdings=(cloud.holdings||[]).map(h=>({symbol:h.symbol,shares:Number(h.shares||0),avg_cost:Number(h.average_cost||0)}));
        cash=(cloud.cash||[]).map(c=>({amount:Number(c.amount||0)}));
      }
    }
  }catch{}
  const cashTotal=cash.reduce((s,x)=>s+Number(x.amount||0),0);
  async function quote(sym){
    const s=String(sym||"").toUpperCase();
    const cache=load(Q,{});
    if(cache[s] && Date.now()-cache[s].ts<60000)return cache[s].data;
    const d=await (await fetch(`/api/quote/${encodeURIComponent(s)}`)).json();
    if(!d.error){cache[s]={ts:Date.now(),data:d};save(Q,cache);}
    return d;
  }
  let holdingsValue=0, totalReturn=0, dayChange=0, quoteCount=0;
  if(holdings.length){
    totalEl.innerHTML='<span class="loading-dots">Loading</span>';
    for(const h of holdings){
      const shares=Number(h.shares||0), avg=Number(h.avg_cost||0);
      let price=0, prev=0;
      try{const q=await quote(h.symbol); price=Number(q.price||0); prev=Number(q.previous_close||0); quoteCount++;}catch{}
      if(!price)price=avg;
      const value=shares*price;
      holdingsValue+=value;
      totalReturn+=value-(shares*avg);
      if(prev)dayChange+=(price-prev)*shares;
    }
  }
  const total=holdingsValue+cashTotal;
  function draw(){
    const h=localStorage.getItem(V)==="1";
    totalEl.textContent=h?"••••••":money(total);
    changeEl.textContent=h?"Hidden":`${dayChange>=0?"+":""}${money(dayChange)} today · ${totalReturn>=0?"+":""}${money(totalReturn)} all-time`;
    changeEl.className=`${dayChange>=0?"positive":"negative"}`;
    subEl.textContent=`${holdings.length} holdings · ${cash.length} cash ${cash.length===1?"entry":"entries"}${quoteCount?` · live quotes`:""}`;
    if(eye){eye.textContent=h?"Show":"Hide";eye.setAttribute("aria-pressed", h?"true":"false");}
  }
  if(eye)eye.addEventListener("click",()=>{localStorage.setItem(V,localStorage.getItem(V)==="1"?"0":"1");draw();});
  draw();
})();
