
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
function renderChatList(){
  $("chat-list").innerHTML=chats.length?chats.map(c=>`
    <button class="chat-list-item ${c.id===activeId?"active":""}" data-id="${c.id}">
      <strong>${safe(c.title)}</strong>
      <span>${new Date(c.createdAt).toLocaleString([], {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"})}</span>
    </button>`).join(""):'<p class="small-muted">No saved chats yet.</p>';
  document.querySelectorAll(".chat-list-item").forEach(b=>b.addEventListener("click",()=>{
    activeId=b.dataset.id;context=active().context||{};renderAll();
  }));
}
function contextName(){
  if(context.trade)return `Attached trade: ${context.trade.symbol||context.ticker||""} ${context.trade.strategy_label||context.trade.strategy||""}`;
  if(context.ticker)return `Ticker: ${context.ticker}`;
  return "No context attached";
}
function renderContext(){
  const chips=[];
  if(context.ticker)chips.push(`<span>${safe(context.ticker)}</span>`);
  if(context.quote)chips.push(`<span>Quote</span>`);
  if(context.technicals)chips.push(`<span>Technicals</span>`);
  if(context.sentiment)chips.push(`<span>Sentiment</span>`);
  if(context.articles?.length)chips.push(`<span>News ${context.articles.length}</span>`);
  if(context.trade)chips.push(`<span>Options trade</span>`);
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
async function attachStock(){
  const symbol=$("chat-symbol").value.trim().toUpperCase();
  if(!symbol)return;
  context={...context,ticker:symbol};
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
      context,
      symbol:context.ticker||$("chat-symbol").value.trim().toUpperCase(),
      include_live_context: !!context.ticker && !context.trade
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
$("clear-context").addEventListener("click",()=>{context={};active().context={};save();renderContext()});
$("send-chat").addEventListener("click",()=>sendMessage());
$("chat-input").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendMessage()}});
document.querySelectorAll(".prompt-chips button").forEach(b=>b.addEventListener("click",()=>sendMessage(b.dataset.prompt)));

const pending=loadPendingContext();
if(pending){
  newChat(pending);
  if(pending.ticker)$("chat-symbol").value=pending.ticker;
  active().title=pending.trade?`Trade: ${pending.trade.symbol||pending.ticker} ${pending.trade.strategy_label||pending.trade.strategy||""}`:`${pending.ticker} research`;
  active().messages.push({role:"assistant",content:`${contextName()}\n\nAsk me about risks, breakeven, Greeks, liquidity, payoff, or scenarios.`});
  save();renderAll();
}else if(!chats.length){newChat()}else{activeId=chats[0].id;context=chats[0].context||{};renderAll()}


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
