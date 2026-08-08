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
    const tone=String(brief.sentiment||"").toLowerCase();
    const cls=tone==="bullish"?"positive":tone==="bearish"?"negative":"";
    $("ai-brief").innerHTML=`<div class="sentiment-head"><div><p class="eyebrow">AI BRIEF</p><h2 class="${cls}">${safe(brief.sentiment||"Summary")}</h2></div><div class="sentiment-score ${cls}">${brief.sentiment_score==null?"—":brief.sentiment_score+"/100"}</div></div><p class="ai-summary-body">${safe(brief.summary)}</p>${brief.question_answer?`<div class="ai-answer"><span>Answer</span><strong>${safe(brief.question_answer)}</strong></div>`:""}<p class="small-muted">Gemini model: ${safe(brief.model||"Unavailable")}</p>`;
    renderArticles(d.articles||[]);
  }catch(e){
    err(e.message);
    $("ai-brief").innerHTML='<p class="small-muted">AI analysis is temporarily unavailable. Source articles are still available.</p>';
  }
});
$("ai-save").addEventListener("click",()=>{
  const item={symbol:$("ai-symbol").value.trim().toUpperCase(),query:$("ai-query").value.trim()};
  if(!item.query)return;
  setSaved([item,...saved().filter(x=>x.query!==item.query || x.symbol!==item.symbol)]);
  renderSaved();
});
renderSaved();
