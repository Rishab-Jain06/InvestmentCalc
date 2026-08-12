(function(){
  const CACHE_KEY="investify_symbol_lookup_cache_v1";
  const CACHE_TTL=7*24*60*60*1000;
  const INPUT_IDS=[
    "global-ticker-input","mobile-ticker-input","ticker","opt-symbol","news-symbol","chat-symbol",
    "holding-symbol","watch-input","default-ticker","calendar-symbol-filter","screen-symbols"
  ];
  function safe(s){return String(s??"").replace(/[<>&"']/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;",'"':"&quot;","'":"&#39;"}[c]));}
  function cleanTicker(v){return String(v||"").trim().toUpperCase().replace(/[^A-Z0-9.\-]/g,"");}
  function saveRecent(sym){try{const k="investify_recent_tickers";const s=cleanTicker(sym);if(!s)return;const arr=JSON.parse(localStorage.getItem(k)||"[]");localStorage.setItem(k,JSON.stringify([s,...arr.filter(x=>x!==s)].slice(0,6)));}catch{}}
  function readCache(){try{return JSON.parse(localStorage.getItem(CACHE_KEY)||"{}");}catch{return {};}}
  function writeCache(c){try{localStorage.setItem(CACHE_KEY,JSON.stringify(c));}catch{}}
  function isLikelyTypedTicker(raw){
    const t=String(raw||"").trim();
    return /^[A-Z0-9.\-]{1,6}$/.test(t) && t===t.toUpperCase();
  }
  async function search(q){
    q=String(q||"").trim();
    if(!q)return [];
    const key=q.toLowerCase();
    const cache=readCache();
    if(cache[key] && Date.now()-cache[key].ts<CACHE_TTL)return cache[key].data||[];
    const r=await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const d=await r.json();
    if(d.error)throw Error(d.error);
    const arr=Array.isArray(d)?d.slice(0,8):[];
    cache[key]={ts:Date.now(),data:arr};
    writeCache(cache);
    return arr;
  }
  async function resolveInput(input){
    const raw=(input?.value||"").trim();
    if(!raw)return "";
    const selected=input?.dataset?.selectedSymbol;
    if(selected && (raw===selected || raw.includes(selected)))return cleanTicker(selected);
    if(isLikelyTypedTicker(raw))return cleanTicker(raw);
    const first=(await search(raw))[0];
    if(first?.symbol){
      input.value=first.symbol.toUpperCase();
      input.dataset.selectedSymbol=first.symbol.toUpperCase();
      input.dataset.companyName=first.name||"";
      return first.symbol.toUpperCase();
    }
    return cleanTicker(raw);
  }
  function dropdownFor(input){
    let box=input.parentElement?.querySelector?.(".symbol-suggest-box");
    if(!box){
      box=document.createElement("div");
      box.className="symbol-suggest-box hidden";
      input.insertAdjacentElement("afterend",box);
      const parent=input.parentElement;
      if(parent && getComputedStyle(parent).position==="static")parent.style.position="relative";
    }
    return box;
  }
  function render(input,rows){
    const box=dropdownFor(input);
    if(!rows.length){box.classList.add("hidden");box.innerHTML="";return;}
    box.innerHTML=rows.slice(0,6).map(r=>`<button type="button" data-symbol="${safe(r.symbol)}" data-name="${safe(r.name||"")}"><strong>${safe(r.symbol)}</strong><span>${safe(r.name||"")}</span><small>${safe(r.exchange||"")}</small></button>`).join("");
    box.classList.remove("hidden");
    box.querySelectorAll("button").forEach(b=>b.onclick=()=>{
      input.value=b.dataset.symbol||"";
      input.dataset.selectedSymbol=b.dataset.symbol||"";
      input.dataset.companyName=b.dataset.name||"";
      box.classList.add("hidden");
      input.dispatchEvent(new CustomEvent("symbol:selected",{bubbles:true,detail:{symbol:input.value,name:input.dataset.companyName}}));
    });
  }
  function attach(input){
    if(!input || input.dataset.symbolLookupAttached)return;
    input.dataset.symbolLookupAttached="1";
    input.setAttribute("autocomplete","off");
    let timer=null;
    input.addEventListener("input",()=>{
      input.dataset.selectedSymbol="";
      clearTimeout(timer);
      const q=input.value.trim();
      if(q.length<2){render(input,[]);return;}
      timer=setTimeout(async()=>{
        try{render(input,await search(q));}catch{render(input,[]);}
      },260);
    });
    input.addEventListener("blur",()=>setTimeout(()=>dropdownFor(input).classList.add("hidden"),160));
    input.addEventListener("keydown",async e=>{
      if(e.key==="Escape")dropdownFor(input).classList.add("hidden");
      if(e.key==="Tab" && !isLikelyTypedTicker(input.value)){
        try{await resolveInput(input);}catch{}
      }
    });
  }
  document.addEventListener("submit",async e=>{
    const form=e.target;
    if(!form || !["global-ticker-search","mobile-ticker-search","ticker-form"].includes(form.id))return;
    e.preventDefault();
    e.stopImmediatePropagation();
    const input=form.querySelector("input");
    const sym=await resolveInput(input);
    if(sym){saveRecent(sym);window.location.href=`/stock/${encodeURIComponent(sym)}`;}
  },true);
  document.addEventListener("DOMContentLoaded",()=>{
    INPUT_IDS.forEach(id=>document.querySelectorAll(`#${id}`).forEach(attach));
    document.querySelectorAll("input[data-symbol-lookup]").forEach(attach);
  });
  window.InvestifySymbols={search,resolveInput,cleanTicker,attach};
})();
