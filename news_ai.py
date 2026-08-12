from __future__ import annotations
import json
import os
import re
import time
import requests
from datetime import date, timedelta, datetime

FINNHUB_BASE = "https://finnhub.io/api/v1"
GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

_CACHE = {}
CACHE_SECONDS = 15 * 60

def _finnhub_key():
    return os.getenv("FINNHUB_API_KEY", "").strip()

def _gemini_key():
    return os.getenv("GEMINI_API_KEY", "").strip()


def _friendly_gemini_error(status_code, body_text=""):
    text = str(body_text or "")
    if status_code == 429:
        return "Gemini daily/rate quota reached. Try again after the quota reset or enable billing. The app did not make a bad request."
    if status_code == 503:
        return "Gemini is temporarily unavailable or overloaded. Try again in a few minutes."
    if status_code == 401 or status_code == 403:
        return "Gemini API key/model access issue. Check GEMINI_API_KEY and GEMINI_MODEL in .env."
    return f"Gemini request failed with HTTP {status_code}."

def _gemini_models():
    # v16: use one configured model only to avoid burning quota across fallback models.
    configured = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
    return [configured]

def _normalize_article(a):
    dt = a.get("datetime") or a.get("time_published") or a.get("publishedAt")
    readable = None
    try:
        if isinstance(dt, (int, float)):
            readable = datetime.fromtimestamp(dt).strftime("%b %d, %Y %I:%M %p")
        elif isinstance(dt, str):
            readable = dt
    except Exception:
        readable = None
    return {
        "headline": a.get("headline") or a.get("title") or "Untitled",
        "summary": a.get("summary") or a.get("description") or "",
        "source": a.get("source") or a.get("source_name") or "Unknown",
        "url": a.get("url") or "",
        "datetime": dt,
        "date_label": readable or "—",
        "image": a.get("image") or "",
        "category": a.get("category") or "",
        "related": a.get("related") or "",
    }

def market_news(limit=20, category="general"):
    key = _finnhub_key()
    if not key:
        raise RuntimeError("FINNHUB_API_KEY is missing from .env")
    r = requests.get(f"{FINNHUB_BASE}/news", params={"category": category, "token": key}, timeout=20)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(data["error"])
    return [_normalize_article(a) for a in data[:limit]]

def company_news(symbol, days_back=14, limit=20):
    key = _finnhub_key()
    if not key:
        raise RuntimeError("FINNHUB_API_KEY is missing from .env")
    end = date.today()
    start = end - timedelta(days=int(days_back or 14))
    r = requests.get(
        f"{FINNHUB_BASE}/company-news",
        params={"symbol": symbol.upper(), "from": start.isoformat(), "to": end.isoformat(), "token": key},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(data["error"])
    return [_normalize_article(a) for a in data[:limit]]

def _article_prompt(articles):
    lines = []
    for i, a in enumerate(articles[:12], start=1):
        lines.append(
            f"{i}. Headline: {a.get('headline','')}\n"
            f"Source: {a.get('source','')}\n"
            f"Date: {a.get('date_label','')}\n"
            f"Summary: {a.get('summary','')[:300]}"
        )
    return "\n\n".join(lines)

def _gemini_rest(prompt, json_mode=False):
    key = _gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is missing from .env")

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    if json_mode:
        payload["generationConfig"] = {"responseMimeType": "application/json"}

    errors = []
    for model in _gemini_models():
        try:
            url = f"{GEMINI_BASE}/{model}:generateContent"
            r = requests.post(
                url,
                headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                json=payload,
                timeout=45,
            )
            if not r.ok:
                errors.append(f"{model}: HTTP {r.status_code} {r.text[:220]}")
                continue
            data = r.json()
            candidates = data.get("candidates") or []
            if not candidates:
                errors.append(f"{model}: no candidates returned")
                continue
            parts = (((candidates[0].get("content") or {}).get("parts")) or [])
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if text:
                return text, model
            errors.append(f"{model}: empty response")
        except Exception as e:
            errors.append(f"{model}: {e}")
    raise RuntimeError(errors[-1] if errors else "Gemini request failed.")

def _fallback_summary(articles, question=None, error=None):
    return {
        "mode": "fallback",
        "model": None,
        "sentiment": "Unavailable",
        "sentiment_score": None,
        "confidence": None,
        "positive_count": None,
        "neutral_count": None,
        "negative_count": None,
        "summary": "AI summary unavailable." + (f" {error}" if error else ""),
        "themes": [],
        "risks": [],
        "catalysts": [],
        "question_answer": None if not question else "Gemini is unavailable, so the question could not be answered.",
    }


def _clean_json_text(raw):
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()

def _parse_json_safely(raw):
    text = _clean_json_text(raw)
    candidates = [text]
    if "{" in text and "}" in text:
        candidates.append(text[text.find("{"):text.rfind("}")+1])
    candidates.append(re.sub(r",\s*([}\]])", r"\1", text))
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except Exception:
            pass
    return None

def _normalize_analysis(data, model):
    try:
        score = max(0, min(100, int(round(float(data.get("sentiment_score"))))))
    except Exception:
        score = None

    if score is None:
        label = str(data.get("sentiment") or "Mixed").title()
        if label not in {"Bullish", "Bearish", "Neutral", "Mixed", "Moderately Bullish", "Moderately Bearish"}:
            label = "Mixed"
    elif score >= 75:
        label = "Bullish"
    elif score >= 60:
        label = "Moderately Bullish"
    elif score <= 25:
        label = "Bearish"
    elif score <= 40:
        label = "Moderately Bearish"
    else:
        label = "Neutral"

    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence"))))
    except Exception:
        confidence = None

    def _ilist(v):
        return [str(x).strip() for x in v[:5] if str(x).strip()] if isinstance(v, list) else []

    def _i(v):
        try:
            return int(v)
        except Exception:
            return None

    return {
        "mode": "gemini",
        "model": model,
        "sentiment": label,
        "sentiment_score": score,
        "confidence": confidence,
        "positive_count": _i(data.get("positive_count")),
        "neutral_count": _i(data.get("neutral_count")),
        "negative_count": _i(data.get("negative_count")),
        "summary": str(data.get("summary") or "").strip(),
        "themes": _ilist(data.get("themes")),
        "risks": _ilist(data.get("risks")),
        "catalysts": _ilist(data.get("catalysts")),
        "question_answer": str(data.get("question_answer") or "").strip(),
    }

def analyze_news_with_gemini(articles, symbol=None, question=None):
    if not articles:
        return _fallback_summary([], question, "No articles were supplied.")

    context_label = symbol or "broad market"
    analyst_mode = "company news analyst" if symbol else "market strategist"
    focus_rules = """
For market mode:
- Explain what is moving the broad market today: rates, yields, inflation, Fed expectations, earnings, geopolitics, oil, sectors, or megacap tech when visible in the loaded headlines.
- Include upcoming catalysts only when supported by the headlines or when they are broad recurring macro items to monitor, such as CPI, PPI, jobs data, Fed speakers/meetings, Treasury yields, major earnings, or geopolitical developments.
- Make the answer useful for deciding what to watch next, not a generic news recap.
""" if not symbol else """
For ticker mode:
- Explain the company-specific story: business driver, stock catalyst, tailwinds, headwinds, risks, and what upcoming events to watch.
- Tie the headlines back to the company whenever possible.
- If the loaded headlines are thin, clearly say the current article set is limited.
"""

    base_prompt = f"""
You are Investify AI, acting as a senior {analyst_mode} inside a financial research app.
Use ONLY the supplied article headlines/descriptions plus the broad watchlist guidance below. Do not invent article facts.
Do not give personalized financial advice or tell the user to buy or sell.

Context: {context_label}
User question: {question or "Summarize the important news and what to watch next."}

{focus_rules}

Return ONLY compact valid JSON, with no markdown and no commentary, using exactly these fields:
{{
  "sentiment_score": integer from 0 to 100 where 50 is neutral,
  "sentiment": "Bullish" or "Bearish" or "Neutral" or "Mixed" or "Moderately Bullish" or "Moderately Bearish",
  "confidence": number from 0 to 1,
  "positive_count": integer,
  "neutral_count": integer,
  "negative_count": integer,
  "summary": "2-3 sentence analyst-style summary that explains the current state, main driver, and what to watch next",
  "themes": ["up to 3 short market/company themes"],
  "catalysts": ["up to 3 specific catalysts or upcoming watch items"],
  "risks": ["up to 3 risks"],
  "question_answer": "direct answer to the user question in 1-2 strong sentences"
}}

Articles:
{_article_prompt(articles)}
""".strip()

    last_error = None

    for attempt in range(2):
        try:
            prompt = base_prompt
            if attempt == 1:
                prompt += "\n\nIMPORTANT: Return compact, strictly valid JSON only. Escape all quotation marks inside string values."
            raw, model = _gemini_rest(prompt, json_mode=True)
            data = _parse_json_safely(raw)
            if data is not None:
                return _normalize_analysis(data, model)
            last_error = "Gemini returned malformed JSON."
        except Exception as e:
            last_error = str(e)

    try:
        raw, model = _gemini_rest(
            base_prompt + "\n\nReturn a single compact JSON object on one line.",
            json_mode=False
        )
        data = _parse_json_safely(raw)
        if data is not None:
            return _normalize_analysis(data, model)
        last_error = "Gemini returned an unreadable response after retries."
    except Exception as e:
        last_error = str(e)

    return _fallback_summary(articles, question, last_error)

def summarize_with_gemini(articles, symbol=None, question=None):
    return analyze_news_with_gemini(articles, symbol=symbol, question=question)

def sentiment_for_symbol(symbol, days_back=14, limit=6):
    key = f"sentiment:{symbol.upper()}:{days_back}:{limit}"
    now = time.time()
    cached = _CACHE.get(key)
    if cached and now - cached["time"] < CACHE_SECONDS:
        return cached["value"]

    articles = company_news(symbol, days_back=days_back, limit=min(int(limit or 6), 7))
    analysis = analyze_news_with_gemini(
        articles,
        symbol=symbol.upper(),
        question="What is the current news sentiment and what are the main drivers?"
    )
    value = {"symbol": symbol.upper(), "analysis": analysis, "articles": articles[:6]}
    _CACHE[key] = {"time": now, "value": value}
    return value

def ai_search(query, symbol=None):
    articles = company_news(symbol, days_back=21, limit=20) if symbol else market_news(limit=20)
    brief = analyze_news_with_gemini(articles, symbol=symbol, question=query)
    return {"query": query, "symbol": symbol, "brief": brief, "articles": articles}


def _compact_article_lines(articles, limit=8):
    lines = []
    for i, a in enumerate((articles or [])[:limit], start=1):
        lines.append(
            f"{i}. {a.get('headline','Untitled')} | {a.get('source','Unknown')} | {a.get('date_label','')}\n"
            f"   {a.get('summary','')[:450]}"
        )
    return "\n".join(lines)

def _format_context_for_chat(context):
    context = context or {}
    parts = []

    ticker = (context.get("ticker") or "").strip().upper()
    if ticker:
        parts.append(f"Ticker context: {ticker}")

    market_quotes = context.get("market_quotes") or {}
    if market_quotes:
        parts.append("Market quotes: " + json.dumps(market_quotes, default=str)[:1500])

    quote = context.get("quote") or {}
    if quote:
        parts.append(
            "Quote: "
            + ", ".join(
                f"{k}={v}" for k, v in quote.items()
                if v is not None and k in {"price", "previous_close", "percent_change", "volume", "day_high", "day_low", "market_cap", "name"}
            )
        )

    technicals = context.get("technicals") or {}
    if technicals:
        parts.append(
            "Technicals: "
            + ", ".join(
                f"{k}={v}" for k, v in technicals.items()
                if v is not None and k in {"rsi14", "macd", "macd_histogram", "ema20", "ema50", "ema200", "sma50", "sma200"}
            )
        )

    stats = context.get("stats") or {}
    if stats:
        slim = {k: stats.get(k) for k in ("identity", "valuation", "profitability", "financial") if stats.get(k)}
        parts.append("Company/fundamental stats: " + json.dumps(slim, default=str)[:2500])

    stock_signal = context.get("stock_signal") or {}
    if stock_signal:
        slim = {k: stock_signal.get(k) for k in ("score", "rating", "summary")}
        slim["technical_score"] = (stock_signal.get("technical") or {}).get("score")
        slim["technical_signal"] = (stock_signal.get("technical") or {}).get("signal")
        slim["fundamental_score"] = (stock_signal.get("fundamental") or {}).get("score")
        slim["fundamental_rating"] = (stock_signal.get("fundamental") or {}).get("rating")
        parts.append("Investify stock signal: " + json.dumps(slim, default=str)[:1500])

    sentiment = context.get("sentiment") or {}
    if sentiment:
        parts.append(
            "News sentiment: "
            + ", ".join(
                f"{k}={v}" for k, v in sentiment.items()
                if v is not None and k in {"sentiment", "sentiment_score", "confidence", "summary"}
            )
        )

    trade = context.get("trade") or {}
    if trade:
        parts.append("Attached options trade:\n" + json.dumps(trade, indent=2, default=str)[:3500])

    portfolio = context.get("portfolio") or {}
    if portfolio:
        slim = {
            "totals": portfolio.get("totals"),
            "sector_exposure": portfolio.get("sector_exposure"),
            "industry_exposure": portfolio.get("industry_exposure"),
            "largest_positions": portfolio.get("largest_positions"),
            "cash": portfolio.get("cash"),
            "watchlist": portfolio.get("watchlist"),
            "holdings": (portfolio.get("holdings") or [])[:30],
        }
        parts.append("Attached portfolio context:\n" + json.dumps(slim, indent=2, default=str)[:6500])

    articles = context.get("articles") or []
    if articles:
        parts.append("Recent news articles:\n" + _compact_article_lines(articles, limit=8))

    return "\n\n".join([p for p in parts if p.strip()])

def _mode_prompt(mode):
    mode = (mode or "general").lower()
    if mode == "general":
        return """
Mode: General assistant.
Answer the user's question directly and practically. You may use attached ticker, market, news, or options context if it is present, but do not force the response into a market/ticker/options format when the user is asking a general question.
Preferred response structure:
- Direct answer first.
- Then short bullets or steps when useful.
- If financial context is attached, clearly distinguish context-based observations from general explanation.
- If the user asks a non-financial question, answer normally and do not invent market data.
"""
    if mode == "ticker":
        return """
Mode: Company/Ticker analyst.
Act like a CFA-style equity analyst. Use ticker context, company stats, stock signal, recent headlines, and SEC/Yahoo-derived metrics when provided.
Preferred response structure:
- Current read: 1 direct sentence.
- Business / stock story: explain what the company does and what is driving the stock now.
- Tailwinds: 2-4 bullets.
- Headwinds / risks: 2-4 bullets.
- Valuation + fundamentals: mention P/E, growth, margins, balance sheet, or missing data when relevant.
- What to watch next: earnings, guidance, macro, product cycle, filings, or news catalysts.
Do not invent facts. If data is missing, say what is missing.
"""
    if mode == "options":
        return """
Mode: Options strategist.
If an attached options trade exists, analyze that exact trade and do not replace it with a generic strategy.
Preferred response structure:
- Trade read: what the setup is and whether it is conservative/balanced/aggressive.
- Payoff: max profit, max loss, breakeven, and best/worst case when available.
- Probability + trend: connect delta/probability to technical trend and underlying movement.
- Greeks: explain delta/theta/vega/gamma only as they matter to this trade.
- Liquidity / execution: bid-ask, volume, OI, stale data risk, and fill considerations.
- Scenarios: what happens if underlying is flat, up, or down.
- Bottom line: Good / OK / Avoid with the main reason.
Never say you can place trades. Do not give personalized financial advice.
"""
    return """
Mode: Market strategist.
Act like a senior macro/market strategist. Use market quotes, recent headlines, sector/index context, and the user's question.
Preferred response structure:
- Market read: bullish/bearish/neutral with one direct reason.
- Today's drivers: rates/yields, inflation/Fed, earnings, sectors, geopolitics, oil, megacap tech, or risk appetite when supported.
- Upcoming catalysts: CPI, PPI, jobs data, Fed speakers/meetings, Treasury yields/auctions, major earnings, or geopolitical headlines when relevant.
- Risks: 2-4 concrete risks.
- What to watch next: 3 bullets.
Avoid generic filler. If the supplied headlines do not support a claim, say the loaded context is limited.
"""


def chat_with_gemini(messages, context=None, mode="general"):
    """
    Multi-turn research chat. Messages should be a list of {role: "user"/"assistant", content: "..."}.
    Uses Gemini directly through REST with mode-specific analyst behavior.
    """
    messages = messages or []
    mode = (mode or "market").lower()
    context_text = _format_context_for_chat(context or {})

    history_lines = []
    for m in messages[-12:]:
        role = "User" if m.get("role") == "user" else "Assistant"
        history_lines.append(f"{role}: {str(m.get('content','')).strip()}")

    prompt = f"""
You are Investify AI Analyst inside a personal market analytics app.

Core rules:
- Use the supplied context first. Do not invent live facts that are not in context.
- Be direct, specific, and practical; avoid generic textbook answers.
- Do not say you can place trades.
- Do not give personalized financial advice or tell the user they should buy or sell.
- Use clean markdown with short headings and tight bullets.
- Keep answers concise unless the user requests detail.
- End with a concrete "What to watch" section when the question involves markets, stocks, or options.

{_mode_prompt(mode)}

Attached/context data:
{context_text or "No live context attached."}

Conversation:
{chr(10).join(history_lines)}

Answer the latest user message in {mode} mode.
""".strip()

    try:
        text, model = _gemini_rest(prompt, json_mode=False)
        return {"mode": "gemini", "model": model, "answer": text.strip()}
    except Exception as e:
        return {
            "mode": "fallback",
            "model": None,
            "answer": f"AI chat is temporarily unavailable. {e}"
        }

def build_market_chat_context(limit=10):
    """Lightweight market context for AI chat/digests."""
    context = {"mode": "market"}
    try:
        import yahoo_data
        quotes = {}
        for sym, name in [("^GSPC", "S&P 500"), ("^IXIC", "Nasdaq"), ("^DJI", "Dow"), ("^VIX", "VIX"), ("SPY", "SPY"), ("QQQ", "QQQ")]:
            try:
                q = yahoo_data.quote(sym)
                quotes[name] = {"symbol": sym, "price": q.get("price"), "percent_change": q.get("percent_change"), "change": q.get("change")}
            except Exception:
                pass
        context["market_quotes"] = quotes
    except Exception:
        pass
    try:
        context["articles"] = market_news(limit=limit)
    except Exception:
        pass
    return context

def build_stock_chat_context(symbol):
    """
    Lightweight context bundle for chatbot. Imports are inside function to avoid circular startup problems.
    """
    symbol = symbol.upper().strip()
    context = {"ticker": symbol}
    try:
        import yahoo_data
        context["quote"] = yahoo_data.quote(symbol)
    except Exception:
        pass
    try:
        import yahoo_data
        context["technicals"] = yahoo_data.technicals(symbol)
    except Exception:
        pass
    try:
        import yahoo_data
        context["stats"] = yahoo_data.stats(symbol)
    except Exception:
        pass
    try:
        import sec_data
        context["stock_signal"] = sec_data.overall_signal(symbol)
    except Exception:
        pass
    try:
        articles = company_news(symbol, days_back=14, limit=8)
        context["articles"] = articles
        # use cache-aware sentiment endpoint but do not fail context if Gemini is slow/unavailable
        s = sentiment_for_symbol(symbol, days_back=14, limit=8).get("analysis")
        context["sentiment"] = s
    except Exception:
        pass
    return context


def market_context_digest(limit=10):
    """Return a compact 3-sentence AI market context digest from current market headlines."""
    try:
        articles = market_news(limit=limit)
    except Exception as e:
        return {"mode": "fallback", "digest": f"Market headlines unavailable: {e}", "articles": []}

    prompt = f"""
You are writing a concise market context digest for the Investify home dashboard.
Use only the headlines below and broad market reasoning.
Return exactly 3 short sentences, no markdown and no bullets:
Sentence 1: current market tone and main driver.
Sentence 2: key themes behind the move.
Sentence 3: what investors should watch next, including likely macro/earnings catalysts if relevant.
Do not give buy/sell advice.

Headlines:
{_compact_article_lines(articles, limit=limit)}
""".strip()
    try:
        text, model = _gemini_rest(prompt, json_mode=False)
        sentences = [x.strip(" -•\t") for x in re.split(r"(?<=[.!?])\s+|\n+", text.strip()) if x.strip()]
        digest = "\n".join(sentences[:3]) if sentences else text.strip()
        return {"mode": "gemini", "model": model, "digest": digest, "articles": articles[:6], "generated_at": datetime.now().isoformat()}
    except Exception:
        h = [a.get("headline", "") for a in articles[:3]]
        digest = "\n".join([
            "Market tone is being driven by the latest broad headlines and index moves.",
            h[0] if h else "Recent headlines are loaded, but Gemini is unavailable.",
            "Watch upcoming inflation data, Fed commentary, Treasury yields, earnings and geopolitical headlines."
        ])
        return {"mode": "fallback", "digest": digest, "articles": articles[:6], "generated_at": datetime.now().isoformat()}


def market_strategy_digest(limit=12):
    """Structured AI market brief for Markets page. Called only when user clicks Refresh AI."""
    try:
        articles = market_news(limit=limit)
    except Exception as e:
        return {"mode": "fallback", "error": str(e), "articles": [], "brief": _fallback_summary([], None, str(e))}

    brief = analyze_news_with_gemini(
        articles,
        symbol=None,
        question="Give a market strategist brief: current state of the market, main drivers, upcoming catalysts, biggest risks, and bottom line."
    )
    return {"mode": brief.get("mode"), "model": brief.get("model"), "brief": brief, "articles": articles[:8], "generated_at": datetime.now().isoformat()}
