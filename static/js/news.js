let newsMode="market";
let currentArticles=[];
const $=id=>document.getElementById(id);
const err=m=>{const e=$("news-error");e.textContent=m;e.classList.remove("hidden")};
const clearErr=()=>$("news-error").classList.add("hidden");
function safe(s){return String(s||"").replace(/[<>&]/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]))}
function renderArticles(articles){
  currentArticles=articles||[];
  $("news-count").textContent=currentArticles.length;
  if(!currentArticles.length){$("news-list").innerHTML='<div class="empty-cell">No headlines found.</div>';return}
  $("news-list").innerHTML=currentArticles.map(a=>`
    <article class="news-item">
      <div>
        <div class="news-meta"><span>${safe(a.source)}</span><span>${safe(a.date_label)}</span></div>
        <h3><a href="${safe(a.url)}" target="_blank" rel="noopener noreferrer">${safe(a.headline)}</a></h3>
        <p>${safe(a.summary)}</p>
      </div>
    </article>`).join("");
}
async function loadNews(){
  clearErr();
  $("news-ai-state").textContent="Ready";
  $("news-brief").classList.add("hidden");
  try{
    let url="/api/news/market?limit=24";
    $("news-current-mode").textContent=newsMode[0].toUpperCase()+newsMode.slice(1);
    if(newsMode==="ticker"){
      const s=$("news-symbol").value.trim().toUpperCase()||"SPY";
      $("news-current-symbol").textContent=s;
      url=`/api/news/company/${encodeURIComponent(s)}?limit=24&days=21`;
    }else if(newsMode==="watchlist"){
      const list=JSON.parse(localStorage.getItem("investify_watchlist")||'["SPY","QQQ"]');
      const s=(list[0]||"SPY").toUpperCase();
      $("news-current-symbol").textContent=list.slice(0,5).join(", ");
      url=`/api/news/company/${encodeURIComponent(s)}?limit=24&days=21`;
    }else{
      $("news-current-symbol").textContent="—";
    }
    const d=await (await fetch(url)).json();
    if(d.error)throw Error(d.error);
    renderArticles(d.articles||[]);
  }catch(e){err(e.message);renderArticles([])}
}
$("news-mode").querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{
  newsMode=b.dataset.mode;
  $("news-mode").querySelectorAll("button").forEach(x=>x.classList.toggle("active",x===b));
  $("news-ticker-field").classList.toggle("hidden",newsMode!=="ticker");
  loadNews();
}));
$("load-news").addEventListener("click",loadNews);
$("summarize-news").addEventListener("click",async()=>{
  clearErr();
  if(!currentArticles.length){err("Load news first.");return}
  $("news-ai-state").textContent="Thinking…";
  try{
    const d=await (await fetch("/api/ai/summarize-news",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({articles:currentArticles,symbol:$("news-symbol").value.trim().toUpperCase(),question:$("news-question").value})})).json();
    if(d.error)throw Error(d.error);
    const box=$("news-brief");
    box.classList.remove("hidden");
    box.innerHTML=`<p class="eyebrow">AI BRIEF</p><h2>${safe(d.sentiment||"Summary")}</h2><pre class="ai-summary-text">${safe(d.summary)}</pre>`;
    $("news-ai-state").textContent=d.mode==="gemini"?"Gemini":"Fallback";
  }catch(e){err(e.message);$("news-ai-state").textContent="Error"}
});
loadNews();
