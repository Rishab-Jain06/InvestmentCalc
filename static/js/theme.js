(()=>{
  const root=document.documentElement;
  const btn=document.getElementById('theme-toggle');
  const saved=localStorage.getItem('investify_theme');
  const prefersDark=window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  const setTheme=(t)=>{root.dataset.theme=t;localStorage.setItem('investify_theme',t);if(btn)btn.textContent=t==='dark'?'☀':'☾';};
  setTheme(saved || (prefersDark?'dark':'light'));
  if(btn)btn.addEventListener('click',()=>setTheme(root.dataset.theme==='dark'?'light':'dark'));
})();
