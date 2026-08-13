const ticker=document.getElementById("default-ticker"), range=document.getElementById("default-range");
const appearanceSelect=document.getElementById("appearance-select");
const statusEl=document.getElementById("settings-status");
function localLoad(){
  ticker.value=localStorage.getItem("investify_default_ticker")||"SPY";
  range.value=localStorage.getItem("investify_default_range")||"1D";
  if(appearanceSelect) appearanceSelect.value=localStorage.getItem("investify_theme")||"system";
}
function setStatus(msg){if(statusEl)statusEl.textContent=msg;}
async function cloudSettings(){
  try{
    const me=await (await fetch("/api/auth/me",{cache:"no-store"})).json();
    if(!me.authenticated)return false;
    const d=await (await fetch("/api/cloud/settings",{cache:"no-store"})).json();
    if(d.error)throw Error(d.error);
    const s=d.settings||{}, prefs=s.app_preferences||{};
    ticker.value=prefs.default_ticker||localStorage.getItem("investify_default_ticker")||"SPY";
    range.value=prefs.default_range||localStorage.getItem("investify_default_range")||"1D";
    if(appearanceSelect) appearanceSelect.value=s.theme||localStorage.getItem("investify_theme")||"system";
    setStatus("Signed in · settings save to your account.");
    return true;
  }catch(e){setStatus("Cloud settings unavailable. Local settings still work.");return false;}
}
let cloudMode=false;
localLoad();
cloudSettings().then(v=>cloudMode=v);

document.getElementById("save-settings").onclick=async()=>{
  let s=ticker.value.trim().toUpperCase()||"SPY";
  if(window.InvestifySymbols?.resolveInput){try{s=await window.InvestifySymbols.resolveInput(ticker)||s;}catch{}}
  localStorage.setItem("investify_default_ticker",s);
  localStorage.setItem("investify_default_range",range.value);
  if(appearanceSelect)localStorage.setItem("investify_theme",appearanceSelect.value);
  if(window.applyTheme) window.applyTheme();
  if(cloudMode){
    try{
      const r=await fetch("/api/cloud/settings",{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({default_ticker:s,default_range:range.value,theme:appearanceSelect?.value||"system"})});
      const d=await r.json();
      if(!r.ok||d.error)throw Error(d.error||"Save failed");
      setStatus("Saved to account.");
    }catch(e){setStatus("Saved locally, but cloud save failed: "+e.message);}
  }else setStatus("Saved locally. Login to sync settings across devices.");
};
if(appearanceSelect){
  appearanceSelect.addEventListener("change",()=>{
    localStorage.setItem("investify_theme",appearanceSelect.value);
    if(window.applyTheme) window.applyTheme();
  });
}
