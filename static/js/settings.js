const ticker=document.getElementById("default-ticker"),range=document.getElementById("default-range");
ticker.value=localStorage.getItem("investify_default_ticker")||"SPY";range.value=localStorage.getItem("investify_default_range")||"1D";
document.getElementById("save-settings").onclick=async()=>{let s=ticker.value.trim().toUpperCase()||"SPY";if(window.InvestifySymbols?.resolveInput){try{s=await window.InvestifySymbols.resolveInput(ticker)||s;}catch{}}localStorage.setItem("investify_default_ticker",s);localStorage.setItem("investify_default_range",range.value);document.getElementById("settings-status").textContent="Saved.";};
const appearanceSelect=document.getElementById("appearance-select");
if(appearanceSelect){
  appearanceSelect.value=localStorage.getItem("investify_theme")||"system";
  appearanceSelect.addEventListener("change",()=>{
    localStorage.setItem("investify_theme",appearanceSelect.value);
    if(window.applyTheme) window.applyTheme();
    else location.reload();
  });
}
