
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
(async function loadHomeNews(){
  const box=document.getElementById("home-news-list");
  if(!box)return;
  try{
    const d=await (await fetch("/api/news/market?limit=5")).json();
    if(d.error)throw Error(d.error);
    const articles=d.articles||[];
    box.innerHTML=articles.length?articles.slice(0,5).map(a=>`
      <a class="home-news-item" href="${safeHomeNews(a.url)}" target="_blank" rel="noopener noreferrer">
        <span>${safeHomeNews(a.source)} · ${safeHomeNews(a.date_label)}</span>
        <strong>${safeHomeNews(a.headline)}</strong>
      </a>`).join(""):'<div class="empty-cell">No headlines found.</div>';
  }catch(e){
    box.innerHTML='<div class="empty-cell">Headlines unavailable. Check Finnhub key.</div>';
  }
})();




async function refreshHomeDigest(){
  const box=document.getElementById("home-digest");
  const updated=document.getElementById("home-digest-updated");
  if(!box)return;
  box.innerHTML='<div class="typing inline"><span></span><span></span><span></span></div><small id="home-digest-updated" class="small-muted">Generating with Gemini…</small>';
  try{
    const d=await (await fetch("/api/news/digest?limit=8")).json();
    if(d.error)throw Error(d.error);
    const lines=String(d.digest||"").split("\n").filter(Boolean).slice(0,2);
    box.innerHTML=`<p>${safeHomeNews(lines[0]||"Market digest unavailable.")}</p><p>${safeHomeNews(lines[1]||"Open News for more context.")}</p><small id="home-digest-updated" class="small-muted">Updated ${new Date().toLocaleTimeString([], {hour:"numeric", minute:"2-digit"})}</small>`;
  }catch(e){
    box.innerHTML=`<p>AI digest unavailable.</p><p>${safeHomeNews(friendlyAIError(e.message||"Gemini quota may be temporarily unavailable."))}</p><small id="home-digest-updated" class="small-muted">Last attempt ${new Date().toLocaleTimeString([], {hour:"numeric", minute:"2-digit"})}</small>`;
  }
}
const refreshDigestBtn=document.getElementById("refresh-market-digest");
if(refreshDigestBtn)refreshDigestBtn.addEventListener("click",refreshHomeDigest);
