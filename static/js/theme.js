
function getPreferredTheme(){
  const saved=localStorage.getItem("investify_theme")||"system";
  if(saved==="light"||saved==="dark")return saved;
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark":"light";
}
function applyTheme(){
  document.documentElement.dataset.theme=getPreferredTheme();
}
applyTheme();
window.applyTheme=applyTheme;
document.addEventListener("DOMContentLoaded",()=>{
  const btn=document.getElementById("theme-toggle");
  if(btn){
    btn.addEventListener("click",()=>{
      const current=localStorage.getItem("investify_theme")||"system";
      const actual=getPreferredTheme();
      localStorage.setItem("investify_theme", actual==="dark"?"light":"dark");
      applyTheme();
    });
  }
});
