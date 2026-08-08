
(function(){
  function cleanTicker(v){
    return String(v || "").trim().toUpperCase().replace(/[^A-Z0-9.\-]/g, "");
  }
  function goTicker(sym){
    const ticker = cleanTicker(sym);
    if(!ticker) return;
    window.location.href = `/stock/${encodeURIComponent(ticker)}`;
  }
  document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("global-ticker-search");
    const input = document.getElementById("global-ticker-input");
    if(!form || !input) return;

    // Pre-fill when already on a stock page.
    const m = window.location.pathname.match(/^\/stock\/([^\/]+)/);
    if(m) input.value = decodeURIComponent(m[1]).toUpperCase();

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      goTicker(input.value);
    });

    input.addEventListener("keydown", (e) => {
      if(e.key === "Escape"){
        input.value = "";
        input.blur();
      }
    });
  });
})();
