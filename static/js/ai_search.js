const $=id=>document.getElementById(id);
const KEY="investify_ai_saved_searches";
const err=m=>{const e=$("ai-error");e.textContent=m;e.classList.remove("hidden")};
const clearErr=()=>$("ai-error").classList.add("hidden");
function safe(s){return String(s||"").replace(/[<>&]/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]))}
function saved(){return JSON.parse(localStorage.getItem(KEY)||"[]")}
function setSaved(v){localStorage.setItem(KEY,JSON.stringify(v.slice(0,20)))}
function renderSaved(){
  const list=saved();
  $("saved-ai-searches").innerHTML=list.length?list.map((x,i)=>`
    <button class="saved-search-item" data-i="${i}">
      <strong>${safe(x.symbol||"Market")}</strong>
      <span>${safe(x.query)}</span>
    </button>`).join(""):'<p class="small-muted">No saved searches yet.</p>';
  document.querySelectorAll(".saved-search-item").forEach(b=>b.addEventListener("click",()=>{
    const x=saved()[Number(b.dataset.i)];
    $("ai-symbol").value=x.symbol||"";
    $("ai-query").value=x.query||"";
  }));
}
function renderArticles(articles){
  $("ai-articles").innerHTML=(articles||[]).length?(articles||[]).map(a=>`
    <article class="news-item">
      <div class="news-meta"><span>${safe(a.source)}</span><span>${safe(a.date_label)}</span></div>
      <h3><a href="${safe(a.url)}" target="_blank" rel="noopener noreferrer">${safe(a.headline)}</a></h3>
      <p>${safe(a.summary)}</p>
    </article>`).join(""):'<div class="empty-cell">No source articles returned.</div>';
}
$("ai-run").addEventListener("click",async()=>{
  clearErr();
  const symbol=$("ai-symbol").value.trim().toUpperCase();
  const query=$("ai-query").value.trim()||"Summarize the latest news.";
  $("ai-brief").classList.remove("hidden");
  $("ai-brief").innerHTML='<p class="eyebrow">AI SEARCH</p><h2>Thinking…</h2><p class="small-muted">Fetching news and building the brief.</p>';
  try{
    const d=await (await fetch("/api/ai/search",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({symbol,query})})).json();
    if(d.error)throw Error(d.error);
    const brief=d.brief||{};
    $("ai-brief").innerHTML=`<p class="eyebrow">AI BRIEF</p><h2>${safe(brief.sentiment||"Summary")}</h2><pre class="ai-summary-text">${safe(brief.summary)}</pre>`;
    renderArticles(d.articles||[]);
  }catch(e){
    err(e.message);
    $("ai-brief").innerHTML='<p class="small-muted">AI Search failed. Check your API keys in .env.</p>';
  }
});
$("ai-save").addEventListener("click",()=>{
  const item={symbol:$("ai-symbol").value.trim().toUpperCase(),query:$("ai-query").value.trim()};
  if(!item.query)return;
  setSaved([item,...saved().filter(x=>x.query!==item.query || x.symbol!==item.symbol)]);
  renderSaved();
});
renderSaved();
