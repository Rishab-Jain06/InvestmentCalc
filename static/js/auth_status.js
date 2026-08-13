(function(){
  async function checkAuth(){
    try{
      const r = await fetch("/api/auth/me", {cache:"no-store"});
      const d = await r.json();
      const authed = !!d.authenticated;
      const user = d.user || {};
      document.querySelectorAll("[data-auth='account']").forEach(el=>{
        el.classList.toggle("hidden", !authed);
        if(authed && el.dataset.short !== "1") el.textContent = user.display_name ? `Account` : "Account";
      });
      document.querySelectorAll("[data-auth='login'], [data-auth='signup']").forEach(el=>el.classList.toggle("hidden", authed));
      window.InvestifyAuth = {authenticated: authed, user};
      window.dispatchEvent(new CustomEvent("investify:auth", {detail: window.InvestifyAuth}));
    }catch(e){
      document.querySelectorAll("[data-auth='account']").forEach(el=>el.classList.add("hidden"));
      document.querySelectorAll("[data-auth='login'], [data-auth='signup']").forEach(el=>el.classList.remove("hidden"));
      window.InvestifyAuth = {authenticated:false, user:null};
    }
  }
  checkAuth();
})();
