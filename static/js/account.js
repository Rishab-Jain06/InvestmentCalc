(async function(){
  const $=id=>document.getElementById(id);
  function err(m){const e=$("account-error"); if(e){e.textContent=m;e.classList.remove("hidden");}}
  try{
    const me = await (await fetch("/api/auth/me", {cache:"no-store"})).json();
    if(!me.authenticated){ window.location.href="/login?next=/account"; return; }
    const u = me.user || {};
    $("account-name").textContent = u.display_name || "Investify user";
    $("account-email").textContent = u.email || "No email on file";
    $("account-provider").textContent = u.provider ? `Signed in with ${u.provider}` : "Signed in";
    const data = await (await fetch("/api/cloud/portfolio", {cache:"no-store"})).json();
    if(data.error) throw Error(data.error);
    $("account-sync-stats").innerHTML = `
      <span>${(data.holdings||[]).length} holdings</span>
      <span>${(data.cash||[]).length} cash entries</span>
      <span>${(data.watchlist||[]).length} watchlist symbols</span>
      <span>${(data.option_positions||[]).length} option positions</span>`;
  }catch(e){err(e.message);}
  const logout=$("account-logout");
  if(logout) logout.onclick=async()=>{await fetch("/api/auth/logout", {method:"POST"}); window.location.href="/";};
})();
