
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

const $=id=>document.getElementById(id);
const CHAT_KEY="investify_ai_chats_v1";
const CONTEXT_KEY="investify_pending_ai_context";
let chats=JSON.parse(localStorage.getItem(CHAT_KEY)||"[]");
let activeId=null;
let context={};
let aiMode=localStorage.getItem("investify_ai_mode")||"general";
const MODE_PROMPTS={
  general:[
    ["Explain simply","Explain this clearly and simply."],
    ["Pros and cons","Give me the pros and cons."],
    ["Step-by-step","Walk me through this step by step."],
    ["Compare choices","Compare the main options and recommend a practical next step."],
    ["Improve answer","Make this more useful and specific."]
  ],
  market:[
    ["Why is the market moving today?","Why is market moving today?"],
    ["Upcoming catalysts","What are the biggest upcoming catalysts to watch this week?"],
    ["Fed / inflation","How are inflation, yields and Fed expectations affecting the market?"],
    ["Sector rotation","What sectors look strong or weak today?"],
    ["Biggest risks","What are the biggest market risks right now?"]
  ],
  ticker:[
    ["Company story","Explain the business, current stock story, and what matters now."],
    ["Tailwinds","What are the biggest tailwinds for this company?"],
    ["Risks","What are the biggest company-specific risks?"],
    ["Valuation","How does valuation look based on available context?"],
    ["News drivers","What recent news is driving the stock?"]
  ],
  options:[
    ["Explain trade","Explain this attached options trade simply."],
    ["Main risks","What are the main risks of this setup?"],
    ["If flat","What happens if the stock is flat?"],
    ["Scenarios","What happens if the stock moves up or down 3%?"],
    ["Greeks","Explain the Greeks and liquidity risk for this trade."]
  ]
};

function uid(){return "chat_"+Date.now()+"_"+Math.random().toString(16).slice(2)}
function save(){localStorage.setItem(CHAT_KEY,JSON.stringify(chats.slice(0,30)))}
function safe(s){return String(s??"").replace(/[<>&]/g,c=>({"<":"&lt;",">":"&gt;","&":"&amp;"}[c]))}
function active(){return chats.find(c=>c.id===activeId)}
function titleFrom(text){return (text||"New chat").replace(/\s+/g," ").trim().slice(0,42)||"New chat"}

function renderMarkdown(text){
  const raw=String(text||"");
  const lines=raw.replace(/\r/g,"").split("\n");
  let html="", inList=false;
  function closeList(){if(inList){html+="</ul>";inList=false;}}
  for(let line of lines){
    let t=line.trim();
    if(!t){closeList();html+='<div class="msg-gap"></div>';continue;}
    t=t.replace(/^#{1,6}\s*/,"");
    t=t.replace(/\*\*(.*?)\*\*/g,"<strong>$1</strong>");
    t=t.replace(/\*(.*?)\*/g,"<em>$1</em>");
    t=t.replace(/`([^`]+)`/g,"<code>$1</code>");
    if(/^[-*]\s+/.test(t)){
      if(!inList){html+="<ul>";inList=true;}
      html+=`<li>${safe(t.replace(/^[-*]\s+/,"")).replace(/&lt;strong&gt;/g,"<strong>").replace(/&lt;\/strong&gt;/g,"</strong>").replace(/&lt;em&gt;/g,"<em>").replace(/&lt;\/em&gt;/g,"</em>").replace(/&lt;code&gt;/g,"<code>").replace(/&lt;\/code&gt;/g,"</code>")}</li>`;
    }else{
      closeList();
      const isHeading = raw.includes(t+"\n") && t.length<50 && !/[.!?]$/.test(t);
      html += isHeading ? `<h4>${safe(t)}</h4>` : `<p>${safe(t).replace(/&lt;strong&gt;/g,"<strong>").replace(/&lt;\/strong&gt;/g,"</strong>").replace(/&lt;em&gt;/g,"<em>").replace(/&lt;\/em&gt;/g,"</em>").replace(/&lt;code&gt;/g,"<code>").replace(/&lt;\/code&gt;/g,"</code>")}</p>`;
    }
  }
  closeList();
  return html;
}
function typingBubble(){
  return `<div class="typing"><span></span><span></span><span></span></div>`;
}
function newChat(seedContext=null){
  const c={id:uid(),title:"New research chat",createdAt:new Date().toISOString(),messages:[],context:seedContext||{}};
  chats.unshift(c);activeId=c.id;context=c.context;save();renderAll();
}
function loadPendingContext(){
  const raw=localStorage.getItem(CONTEXT_KEY);
  if(!raw)return null;
  localStorage.removeItem(CONTEXT_KEY);
  try{return JSON.parse(raw)}catch{return null}
}
function setMode(mode){
  aiMode=mode||"market";
  localStorage.setItem("investify_ai_mode", aiMode);
  if(context){context.mode=aiMode; const c=active(); if(c){c.context=context; save();}}
  document.querySelectorAll("#ai-mode-tabs button").forEach(b=>b.classList.toggle("active", b.dataset.mode===aiMode));
  const input=$("chat-input");
  if(input){
    input.placeholder = aiMode==="general"
      ? "Ask anything, or attach ticker/trade context for a more specific answer…"
      : aiMode==="market"
        ? "Ask about market direction, macro catalysts, sectors, rates, or risk…"
        : aiMode==="ticker"
          ? "Ask about the attached ticker, business, valuation, drivers, tailwinds, or risks…"
          : "Ask about an attached options trade, payoff, Greeks, liquidity, or scenarios…";
  }
  renderPromptChips();
  renderContext();
}
function renderPromptChips(){
  const row=document.querySelector(".prompt-chips");
  if(!row)return;
  const prompts=MODE_PROMPTS[aiMode]||MODE_PROMPTS.general;
  row.innerHTML=prompts.map(([label,prompt])=>`<button type="button" data-prompt="${safe(prompt)}">${safe(label)}</button>`).join("");
  row.querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>sendMessage(b.dataset.prompt)));
}
function renderChatList(){
  $("chat-list").innerHTML=chats.length?chats.map(c=>`
    <button class="chat-list-item ${c.id===activeId?"active":""}" data-id="${c.id}">
      <strong>${safe(c.title)}</strong>
      <span>${new Date(c.createdAt).toLocaleString([], {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})}</span>
    </button>`).join(""):'<p class="small-muted">No saved chats yet.</p>';
  document.querySelectorAll(".chat-list-item").forEach(b=>b.addEventListener("click",()=>{
    activeId=b.dataset.id;context=active().context||{};aiMode=context.mode||aiMode;renderAll();setMode(aiMode);
  }));
}
function contextName(){
  if(context.portfolio)return "Attached portfolio context";
  if(context.trade)return `Attached trade: ${context.trade.symbol||context.ticker||""} ${context.trade.strategy_label||context.trade.strategy||""}`;
  if(context.ticker)return `Ticker: ${context.ticker}`;
  return "No context attached";
}
function renderContext(){
  const chips=[];
  chips.push(`<span>${safe((aiMode||"market").toUpperCase())} mode</span>`);
  if(context.ticker)chips.push(`<span>${safe(context.ticker)}</span>`);
  if(context.quote)chips.push(`<span>Quote</span>`);
  if(context.technicals)chips.push(`<span>Technicals</span>`);
  if(context.sentiment)chips.push(`<span>Sentiment</span>`);
  if(context.articles?.length)chips.push(`<span>News ${context.articles.length}</span>`);
  if(context.trade)chips.push(`<span>Options trade</span>`);
  if(context.portfolio)chips.push(`<span>Portfolio</span>`);
  $("context-chips").innerHTML=chips.length?chips.join(""):'<span class="muted-chip">No context attached</span>';
  $("chat-title").textContent=active()?.title||"New research chat";
}
function renderMessages(){
  const c=active();
  if(!c){$("chat-messages").innerHTML="";return}
  if(!c.messages.length){
    $("chat-messages").innerHTML=`<div class="chat-empty"><h3>Start a research chat.</h3><p>Ask about a ticker, market news, technicals, or an attached options trade. Follow-up questions keep the conversation context.</p></div>`;
    return;
  }
  $("chat-messages").innerHTML=c.messages.map(m=>`
    <div class="message ${m.role}">
      <div class="message-label">${m.role==="user"?"You":"Investify AI"}</div>
      <div class="message-body">${m.loading?typingBubble():renderMarkdown(m.content)}</div>
    </div>`).join("");
  $("chat-messages").scrollTop=$("chat-messages").scrollHeight;
}
function renderAll(){renderChatList();renderContext();renderMessages()}
async function resolveChatSymbol(){
  const input=$("chat-symbol");
  if(window.InvestifySymbols?.resolveInput){try{return await window.InvestifySymbols.resolveInput(input);}catch{}}
  return input.value.trim().toUpperCase();
}
async function attachStock(){
  const symbol=await resolveChatSymbol();
  if(!symbol)return;
  context={...context,ticker:symbol,mode:aiMode};
  active().context=context;save();renderContext();
}
async function sendMessage(text=null){
  const c=active(); if(!c)return;
  const content=(text??$("chat-input").value).trim();
  if(!content)return;
  $("chat-input").value="";
  c.messages.push({role:"user",content});
  if(c.title==="New research chat")c.title=titleFrom(content);
  c.context=context;
  save();renderAll();

  c.messages.push({role:"assistant",content:"",loading:true});
  renderMessages();

  try{
    const res=await fetch("/api/ai/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({
      messages:c.messages.filter(m=>!m.loading).map((m,i,arr)=> i===arr.length-1 && m.role==="user" ? {...m, content:enhancePromptWithStyle(m.content)} : m),
      context:{...context, mode:aiMode},
      mode:aiMode,
      symbol:context.ticker||await resolveChatSymbol(),
      include_live_context: aiMode==="market" || !!context.ticker || !!context.trade
    })});
    const d=await res.json();
    if(d.error)throw Error(d.error);
    c.messages[c.messages.length-1]={role:"assistant",content:d.answer||"No answer returned."};
  }catch(e){
    c.messages[c.messages.length-1]={role:"assistant",content:"AI chat is temporarily unavailable. Source pages and tools still work.\n\n"+e.message};
  }
  save();renderAll();
}
$("new-chat").addEventListener("click",()=>newChat());
$("attach-stock").addEventListener("click",attachStock);
$("clear-context").addEventListener("click",()=>{context={mode:aiMode};active().context=context;save();renderContext()});
$("send-chat").addEventListener("click",()=>sendMessage());
$("chat-input").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage()}});
document.querySelectorAll("#ai-mode-tabs button").forEach(b=>b.addEventListener("click",()=>setMode(b.dataset.mode)));

const pending=loadPendingContext();
if(pending){
  if(pending.trade) aiMode="options";
  else if(pending.ticker) aiMode="ticker";
  else aiMode="general";
  localStorage.setItem("investify_ai_mode", aiMode);
  pending.mode=aiMode;
  newChat(pending);
  if(pending.ticker)$("chat-symbol").value=pending.ticker;
  if(pending.portfolio){
    active().title="Portfolio review";
    active().messages.push({role:"assistant",content:"Portfolio context attached. Ask about diversification, concentration, sector exposure, cash positioning, or risks."});
    if(pending.portfolio_prompt)$("chat-input").value=pending.portfolio_prompt;
  }else{
    active().title=pending.trade?`Trade: ${pending.trade.symbol||pending.ticker} ${pending.trade.strategy_label||pending.trade.strategy||""}`:`${pending.ticker} research`;
    active().messages.push({role:"assistant",content:`${contextName()}\n\nAsk me about risks, breakeven, Greeks, liquidity, payoff, or scenarios.`});
  }
  save();renderAll();
}else if(!chats.length){newChat({mode:aiMode})}else{activeId=chats[0].id;context=active().context||{};aiMode=context.mode||aiMode;renderAll()}
setMode(aiMode);


// v14 chat management: rename, delete, edit last, regenerate, answer style
function currentAnswerStyle(){
  return document.getElementById("answer-style")?.value || localStorage.getItem("investify_answer_style") || "short";
}
function enhancePromptWithStyle(content){
  const style=currentAnswerStyle();
  if(style==="detailed") return content + "\n\nAnswer style: detailed but organized.";
  return content + "\n\nAnswer style: short and concise. Use clean bullets and no long essay.";
}
function renameActiveChat(){
  const c=active(); if(!c)return;
  const name=prompt("Rename chat:", c.title || "New research chat");
  if(!name)return;
  c.title=name.trim().slice(0,60)||c.title;
  save();renderAll();
}
function deleteActiveChat(){
  const c=active(); if(!c)return;
  if(!confirm(`Delete "${c.title}"?`))return;
  chats=chats.filter(x=>x.id!==c.id);
  if(!chats.length){newChat();return;}
  activeId=chats[0].id;context=active().context||{};save();renderAll();
}

document.addEventListener("DOMContentLoaded",()=>{
  const rename=document.getElementById("rename-chat");
  const del=document.getElementById("delete-chat");
  const style=document.getElementById("answer-style");
  if(rename)rename.onclick=renameActiveChat;
  if(del)del.onclick=deleteActiveChat;
  if(style){
    style.value=localStorage.getItem("investify_answer_style")||"short";
    style.onchange=()=>localStorage.setItem("investify_answer_style",style.value);
  }
});
