window.InvestifySentiment = (function(){
  function $(id){return document.getElementById(id)}
  function label(score, fallback){
    if(score===null || score===undefined || Number.isNaN(Number(score))) return fallback || "Unavailable";
    const n = Number(score);
    if(n >= 75) return "Bullish";
    if(n >= 60) return "Moderately Bullish";
    if(n <= 25) return "Bearish";
    if(n <= 40) return "Moderately Bearish";
    return "Neutral";
  }
  function tone(lbl){
    const l = String(lbl || "").toLowerCase();
    if(l.includes("bullish")) return "positive";
    if(l.includes("bearish")) return "negative";
    return "";
  }
  function dots(){
    return '<span class="typing inline"><span></span><span></span><span></span></span>';
  }
  function setLoading(prefix, text){
    const labelEl = $(prefix + "-sentiment-label");
    const scoreEl = $(prefix + "-sentiment-score");
    const marker = $(prefix + "-sentiment-marker");
    const summary = $(prefix + "-sentiment-summary") || $(prefix + "-sentiment-trend");
    if(labelEl) labelEl.innerHTML = dots();
    if(scoreEl) scoreEl.textContent = "—";
    if(marker){ marker.style.left = "50%"; marker.className = "score-line-marker"; }
    if(summary) summary.textContent = text || "Checking recent headlines with Gemini.";
  }
  function render(prefix, analysis, opts){
    analysis = analysis || {};
    opts = opts || {};
    const score = analysis.sentiment_score === null || analysis.sentiment_score === undefined
      ? null
      : Math.max(0, Math.min(100, Number(analysis.sentiment_score)));
    const lbl = label(score, analysis.sentiment);
    const cls = tone(lbl);

    const labelEl = $(prefix + "-sentiment-label");
    const scoreEl = $(prefix + "-sentiment-score");
    const marker = $(prefix + "-sentiment-marker");
    const summary = $(prefix + "-sentiment-summary") || $(prefix + "-sentiment-trend");
    const updated = $(prefix + "-sentiment-updated");

    if(labelEl){ labelEl.textContent = lbl.toUpperCase(); labelEl.className = cls; }
    if(scoreEl){ scoreEl.textContent = score === null ? "—" : `${Math.round(score)}/100`; scoreEl.className = `sentiment-score ${cls}`; }
    if(marker){ marker.style.left = (score === null ? 50 : score) + "%"; marker.className = `score-line-marker ${cls}`; }
    if(summary){
      const symbol = opts.symbol ? `${opts.symbol} ` : "";
      summary.textContent = analysis.summary || `${symbol}news sentiment based on recent headlines.`;
    }
    if(updated){
      updated.textContent = `Updated ${new Date().toLocaleTimeString([], {hour:"numeric", minute:"2-digit"})}`;
    }
  }
  async function loadTicker(prefix, symbol, opts){
    opts = opts || {};
    if(!symbol){ render(prefix, {sentiment:"Unavailable", sentiment_score:null, summary:"No ticker selected."}); return null; }
    setLoading(prefix, "Checking recent headlines with Gemini.");
    const days = opts.days || 10;
    const limit = opts.limit || 6;
    try{
      const d = await (await fetch(`/api/news/sentiment/${encodeURIComponent(symbol)}?days=${days}&limit=${limit}`)).json();
      if(d.error) throw Error(d.error);
      render(prefix, d.analysis || {}, {symbol});
      return d;
    }catch(e){
      render(prefix, {sentiment:"Unavailable", sentiment_score:null, summary:"Sentiment unavailable. News and stock data are still available."}, {symbol});
      return null;
    }
  }
  return {label, tone, dots, setLoading, render, loadTicker};
})();
