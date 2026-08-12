
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

let newsMode="market";
let currentArticles=[];
const $=id=>document.getElementById(id);
const err=m=>{const e=$("news-error");e.textContent=m;e.classList.remove("hidden")};
const clearErr=()=>$("news-error").classList.add("hidden");
function safe(s){return String(s??"").replace(/[<>&]/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]))}
async function resolveNewsSymbol(){
  const input=$("news-symbol");
  if(window.InvestifySymbols?.resolveInput){try{return await window.InvestifySymbols.resolveInput(input);}catch{}}
  return input.value.trim().toUpperCase()||"SPY";
}
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
function newsSentimentLabel(score, fallback){
  if(score==null)return fallback||"Unavailable";
  const n=Number(score);
  if(n>=75)return "Bullish";
  if(n>=60)return "Moderately Bullish";
  if(n<=25)return "Bearish";
  if(n<=40)return "Moderately Bearish";
  return "Neutral";
}
function toneClass(label){
  const l=String(label||"").toLowerCase();
  return l.includes("bullish")?"positive":l.includes("bearish")?"negative":"";
}

function renderBrief(d){
  const box=$("news-brief");box.classList.remove("hidden");
  const list=(title,items)=>items?.length?`<div class="ai-list"><h4>${title}</h4>${items.map(x=>`<span>${safe(x)}</span>`).join("")}</div>`:"";
  box.innerHTML=`<p class="eyebrow">AI BRIEF</p><h2 class="${toneClass(d.sentiment)}">${safe(d.sentiment||"Summary")}</h2>
    <p class="ai-summary-body">${safe(d.summary)}</p>
    <div class="ai-brief-grid">${list("Themes",d.themes)}${list("Catalysts",d.catalysts)}${list("Risks",d.risks)}</div>
    ${d.question_answer?`<div class="ai-answer"><span>Answer</span><strong>${safe(d.question_answer)}</strong></div>`:""}
    <p class="small-muted">Model: ${safe(d.model||"Unavailable")} · News sentiment is an AI classification of the loaded articles, not a price forecast.</p>`;
}
async function loadNews(){
  clearErr();
  $("news-ai-state").textContent="Ready";
  $("news-brief").classList.add("hidden");
  $("news-sentiment").classList.add("hidden");
  try{
    let url="/api/news/market?limit=24";
    $("news-current-mode").textContent=newsMode[0].toUpperCase()+newsMode.slice(1);
    if(newsMode==="ticker"){
      const s=await resolveNewsSymbol();
      $("news-current-symbol").textContent=s;
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
  $("news-ai-state").innerHTML='<span class="typing inline"><span></span><span></span><span></span></span>';
  try{
    let d;
    if(newsMode==="ticker"){
      const sym=await resolveNewsSymbol();
      d=await (await fetch(`/api/news/sentiment/${encodeURIComponent(sym)}?days=10&limit=6`)).json();
      if(d.error)throw Error(d.error);
      d=d.analysis||{};
    }else{
      d=await (await fetch("/api/ai/summarize-news",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
        articles:currentArticles.slice(0,6),
        symbol:null,
        question:$("news-question").value
      })})).json();
    }
    if(d.error)throw Error(d.error);
    renderSentiment(d);renderBrief(d);
    $("news-ai-state").textContent=d.mode==="gemini"?"Gemini":"Fallback";
  }catch(e){err(e.message);$("news-ai-state").textContent="Error"}
});
loadNews();


// v13 simple sentiment rendering
function simpleLabel(score,fallback){
  if(score==null)return fallback||"Unavailable";
  const n=Number(score);
  if(n>=75)return "Bullish";
  if(n>=60)return "Moderately Bullish";
  if(n<=25)return "Bearish";
  if(n<=40)return "Moderately Bearish";
  return "Neutral";
}
function simpleTone(label){
  const l=String(label||"").toLowerCase();
  if(l.includes("bullish"))return "positive";
  if(l.includes("bearish"))return "negative";
  return "";
}


// v14 shared sentiment rendering
function renderSentiment(d){
  const box = $("news-sentiment");
  if(box) box.classList.remove("hidden");
  if(window.InvestifySentiment){
    window.InvestifySentiment.render("news", d || {}, {symbol: $("news-symbol")?.value?.trim()?.toUpperCase()});
  }
}
