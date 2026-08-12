
function friendlyAIError(msg){
  const text=String(msg||"");
  if(text.includes("429")||text.toLowerCase().includes("quota")||text.includes("TooManyRequests")){
    return "Gemini quota reached. Try again after reset or enable billing. No issue with your app code.";
  }
  if(text.includes("503")||text.toLowerCase().includes("unavailable")){
    return "Gemini is temporarily unavailable. Try again in a few minutes.";
  }
  return text || "AI is temporarily unavailable.";
}

function safeHomeNews(s){return String(s??"").replace(/[<>&]/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]))}

const HOME_DIGEST_KEY = "investify_home_ai_digest_v2";

function renderSavedHomeDigest(){
  const box=document.getElementById("home-digest");
  if(!box)return;
  try{
    const saved=JSON.parse(localStorage.getItem(HOME_DIGEST_KEY)||"null");
    if(!saved || !saved.lines?.length)return;
    const updated=saved.updatedAt ? new Date(saved.updatedAt) : null;
    const label=updated ? updated.toLocaleString([], {month:"short", day:"numeric", hour:"numeric", minute:"2-digit"}) : "previously";
    const lines=(saved.lines||[]).slice(0,3);
    box.innerHTML=`${lines.map(x=>`<p>${safeHomeNews(x)}</p>`).join("")}<small id="home-digest-updated" class="small-muted">Last updated ${label}</small>`;
  }catch(e){}
}

function normalizeArticle(a){
  return {
    headline:a.headline||a.title||"Untitled",
    source:a.source||"News",
    date_label:a.date_label||a.datetime||"",
    url:a.url||"#"
  };
}

async function fetchHomeArticles(){
  const urls=[
    "/api/news/market?limit=8",
    "/api/news/company/SPY?limit=4",
    "/api/news/company/QQQ?limit=4",
    "/api/news/company/AAPL?limit=4"
  ];
  const seen=new Set();
  const out=[];
  for(const url of urls){
    try{
      const d=await (await fetch(url)).json();
      if(d.error)continue;
      const rows=(d.articles||[]).map(normalizeArticle);
      rows.forEach(a=>{
        const key=String(a.headline||"").toLowerCase().trim();
        if(key && !seen.has(key)){
          seen.add(key);
          out.push(a);
        }
      });
      if(out.length>=4)break;
    }catch(e){}
  }
  return out.slice(0,4);
}

(async function loadHomeNews(){
  const box=document.getElementById("home-news-list");
  if(!box)return;
  try{
    const articles=await fetchHomeArticles();
    box.innerHTML=articles.length?articles.map(a=>`
      <a class="home-news-item" href="${safeHomeNews(a.url)}" target="_blank" rel="noopener noreferrer">
        <span>${safeHomeNews(a.source)}${a.date_label ? " · "+safeHomeNews(a.date_label) : ""}</span>
        <strong>${safeHomeNews(a.headline)}</strong>
      </a>`).join(""):'<div class="empty-cell">No headlines found. Check Finnhub API key or market-news availability.</div>';
  }catch(e){
    box.innerHTML='<div class="empty-cell">Headlines unavailable. Check Finnhub key.</div>';
  }
})();

async function refreshHomeDigest(){
  const box=document.getElementById("home-digest");
  if(!box)return;
  box.innerHTML='<div class="typing inline"><span></span><span></span><span></span></div><small id="home-digest-updated" class="small-muted">Generating</small>';
  try{
    const d=await (await fetch("/api/news/digest?limit=10")).json();
    if(d.error)throw Error(d.error);
    const lines=String(d.digest||"").split("\n").filter(Boolean).slice(0,2);
    const saved={lines, updatedAt:new Date().toISOString()};
    localStorage.setItem(HOME_DIGEST_KEY, JSON.stringify(saved));
    renderSavedHomeDigest();
  }catch(e){
    box.innerHTML=`<p>AI digest unavailable.</p><p>${safeHomeNews(friendlyAIError(e.message||"Gemini quota may be temporarily unavailable."))}</p><small id="home-digest-updated" class="small-muted">Last attempt ${new Date().toLocaleTimeString([], {hour:"numeric", minute:"2-digit"})}</small>`;
  }
}
renderSavedHomeDigest();
const refreshDigestBtn=document.getElementById("refresh-market-digest");
if(refreshDigestBtn)refreshDigestBtn.addEventListener("click",refreshHomeDigest);
