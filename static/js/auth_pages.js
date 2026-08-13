(function(){
  const cfg = window.INVESTIFY_SUPABASE || {};
  const page = window.INVESTIFY_AUTH_PAGE || "login";
  const $ = id => document.getElementById(id);
  const nextParam = new URLSearchParams(window.location.search).get("next") || "/portfolio";

  function showError(msg){
    const el = $("auth-error");
    if(!el)return;
    el.textContent = msg || "Authentication failed.";
    el.classList.remove("hidden");
  }
  function status(msg){
    const el = $("auth-status");
    if(el) el.textContent = msg || "";
  }
  function client(){
    if(!cfg.configured || !cfg.url || !cfg.anon_key){
      throw new Error("Supabase is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY.");
    }
    if(!window.supabase) throw new Error("Supabase JS failed to load.");
    return window.supabase.createClient(cfg.url, cfg.anon_key, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
    });
  }
  async function saveServerSession(session){
    if(!session?.access_token) throw new Error("No Supabase session returned.");
    const r = await fetch("/api/auth/session", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({access_token: session.access_token, refresh_token: session.refresh_token})
    });
    const d = await r.json().catch(()=>({}));
    if(!r.ok || d.error) throw new Error(d.error || "Server session could not be saved.");
    return d;
  }
  function redirectAfterLogin(){
    window.location.href = nextParam && nextParam.startsWith("/") ? nextParam : "/portfolio";
  }
  async function googleLogin(){
    try{
      status("Opening Google sign in…");
      const c = client();
      const redirectTo = `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextParam || "/portfolio")}`;
      const { error } = await c.auth.signInWithOAuth({provider:"google", options:{redirectTo}});
      if(error) throw error;
    }catch(e){showError(e.message);status("");}
  }

  const googleBtn = $("google-login");
  if(googleBtn) googleBtn.addEventListener("click", googleLogin);

  const loginForm = $("login-form");
  if(loginForm){
    loginForm.addEventListener("submit", async e=>{
      e.preventDefault();
      const btn = $("login-submit");
      try{
        btn.disabled = true; btn.textContent = "Logging in…"; status("Checking credentials…");
        const c = client();
        const { data, error } = await c.auth.signInWithPassword({
          email: $("login-email").value.trim(),
          password: $("login-password").value
        });
        if(error) throw error;
        await saveServerSession(data.session);
        status("Logged in. Redirecting…");
        redirectAfterLogin();
      }catch(err){showError(err.message);status("");}
      finally{btn.disabled = false; btn.textContent = "Login";}
    });
  }

  const signupForm = $("signup-form");
  if(signupForm){
    signupForm.addEventListener("submit", async e=>{
      e.preventDefault();
      const btn = $("signup-submit");
      try{
        btn.disabled = true; btn.textContent = "Creating account…"; status("Creating your account…");
        const c = client();
        const { data, error } = await c.auth.signUp({
          email: $("signup-email").value.trim(),
          password: $("signup-password").value,
          options: {
            data: { display_name: $("signup-name").value.trim() },
            emailRedirectTo: `${window.location.origin}/auth/callback?next=${encodeURIComponent(nextParam || "/portfolio")}`
          }
        });
        if(error) throw error;
        if(data.session){
          await saveServerSession(data.session);
          status("Account created. Redirecting…");
          redirectAfterLogin();
        }else{
          status("Account created. Check your email to confirm your login, then return to Investify.");
        }
      }catch(err){showError(err.message);status("");}
      finally{btn.disabled = false; btn.textContent = "Create account";}
    });
  }

  if(page === "callback"){
    (async()=>{
      try{
        const c = client();
        let session = null;
        const url = new URL(window.location.href);
        if(url.searchParams.get("code") && c.auth.exchangeCodeForSession){
          const { data, error } = await c.auth.exchangeCodeForSession(url.searchParams.get("code"));
          if(error) throw error;
          session = data.session;
        }
        if(!session){
          const { data, error } = await c.auth.getSession();
          if(error) throw error;
          session = data.session;
        }
        await saveServerSession(session);
        status("Signed in. Redirecting…");
        redirectAfterLogin();
      }catch(e){
        showError(e.message || "Google login callback failed.");
        status("Sign in was not completed.");
      }
    })();
  }
})();
