
document.querySelectorAll(".market-tile").forEach(async tile=>{
  const s=tile.dataset.symbol;
  try{
    const q=await (await fetch(`/api/quote/${encodeURIComponent(s)}`)).json();
    if(q.error)throw Error(q.error);
    tile.querySelector(".m-price").textContent=q.price==null?"—":`$${Number(q.price).toFixed(2)}`;
    const c=Number(q.percent_change||0), e=tile.querySelector(".m-change");
    e.textContent=`${c>=0?"+":""}${c.toFixed(2)}%`;
    e.className=`m-change ${c>=0?"positive":"negative"}`;
  }catch(e){
    tile.querySelector(".m-change").textContent="Unavailable";
  }
});


function safeMarketAI(s){return String(s??"").replace(/[<>&]/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]))}
const MARKETS_DIGEST_KEY="investify_markets_ai_digest_v1";
function marketTone(label){
  const l=String(label||"").toLowerCase();
  if(l.includes("bullish"))return "positive";
  if(l.includes("bearish"))return "negative";
  return "";
}
function renderMarketsDigest(saved){
  const box=document.getElementById("markets-ai-brief");
  if(!box || !saved)return;
  const b=saved.brief||{};
  const updated=saved.updatedAt?new Date(saved.updatedAt):null;
  const label=updated?updated.toLocaleString([], {month:"short", day:"numeric", hour:"numeric", minute:"2-digit"}):"previously";
  const list=(title,items)=>items?.length?`<div class="ai-list"><h4>${title}</h4>${items.slice(0,3).map(x=>`<span>${safeMarketAI(x)}</span>`).join("")}</div>`:"";
  box.innerHTML=`<div class="sentiment-head"><div><p class="eyebrow">AI MARKET BRIEF</p><h2 class="${marketTone(b.sentiment)}">${safeMarketAI(b.sentiment||"Market Brief")}</h2></div><div class="sentiment-score ${marketTone(b.sentiment)}">${b.sentiment_score==null?"—":b.sentiment_score+"/100"}</div></div>
    <p class="ai-summary-body">${safeMarketAI(b.summary||"AI market brief unavailable.")}</p>
    <div class="ai-brief-grid">${list("Themes",b.themes)}${list("Catalysts",b.catalysts)}${list("Risks",b.risks)}</div>
    ${b.question_answer?`<div class="ai-answer"><span>Bottom line</span><strong>${safeMarketAI(b.question_answer)}</strong></div>`:""}
    <p class="small-muted">Last updated ${label}${saved.model?" · "+safeMarketAI(saved.model):""}</p>`;
}
function loadSavedMarketsDigest(){
  try{renderMarketsDigest(JSON.parse(localStorage.getItem(MARKETS_DIGEST_KEY)||"null"));}catch(e){}
}
async function refreshMarketsDigest(){
  const box=document.getElementById("markets-ai-brief");
  if(!box)return;
  box.innerHTML='<div class="typing inline"><span></span><span></span><span></span></div><small class="small-muted">Generating</small>';
  try{
    const d=await (await fetch("/api/markets/digest?limit=12")).json();
    if(d.error)throw Error(d.error);
    const saved={brief:d.brief||{}, model:d.model||d.brief?.model, updatedAt:new Date().toISOString()};
    localStorage.setItem(MARKETS_DIGEST_KEY, JSON.stringify(saved));
    renderMarketsDigest(saved);
  }catch(e){
    box.innerHTML=`<p>AI market brief unavailable.</p><p>${safeMarketAI(e.message||"Gemini or Finnhub may be temporarily unavailable.")}</p><small class="small-muted">Last attempt ${new Date().toLocaleTimeString([], {hour:"numeric", minute:"2-digit"})}</small>`;
  }
}
loadSavedMarketsDigest();
document.getElementById("refresh-markets-digest")?.addEventListener("click", refreshMarketsDigest);
