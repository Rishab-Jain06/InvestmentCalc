const input=document.getElementById("beta-search-input");
const btn=document.getElementById("beta-search-btn");
const out=document.getElementById("beta-search-output");
function runSearch(){
  const q=input.value.trim();
  if(!q)return;
  const maybeTicker=/^[A-Za-z.\-]{1,8}$/.test(q);
  if(maybeTicker){
    const s=q.toUpperCase();
    out.innerHTML=`<div class="beta-result"><p class="eyebrow">TICKER RESULT</p><h2>${s}</h2><p class="small-muted">This looks like a ticker. Open it in Stock Research or Options Lab.</p><div class="beta-actions"><a class="secondary-button" href="/stock/${encodeURIComponent(s)}">Open Stock Research</a><a class="secondary-button" href="/options">Open Options Lab</a></div></div>`;
  }else{
    out.innerHTML=`<div class="beta-result"><p class="eyebrow">BETA PLACEHOLDER</p><h2>Search coming later</h2><p class="small-muted">You searched: <strong>${q.replace(/[<>&]/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]))}</strong></p><p class="small-muted">Future versions can use this page for market/news search, research notes, saved ideas, or AI-assisted explanations.</p></div>`;
  }
}
btn.addEventListener("click",runSearch);
input.addEventListener("keydown",e=>{if(e.key==="Enter")runSearch()});
