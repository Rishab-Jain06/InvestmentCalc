from __future__ import annotations
import os
import requests
from datetime import date, timedelta, datetime

FINNHUB_BASE = "https://finnhub.io/api/v1"

def _finnhub_key():
    return os.getenv("FINNHUB_API_KEY", "").strip()

def _gemini_key():
    return os.getenv("GEMINI_API_KEY", "").strip()

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

def _fallback_summary(articles, question=None):
    bullets = []
    for a in articles[:5]:
        bits = [a.get("headline", "Untitled")]
        if a.get("source"):
            bits.append(f"Source: {a['source']}")
        bullets.append(" - " + " · ".join(bits))
    return {
        "mode": "fallback",
        "sentiment": "Unavailable",
        "summary": "AI summary unavailable because GEMINI_API_KEY is missing or the Gemini request failed.",
        "themes": bullets,
        "risks": [],
        "catalysts": [],
        "question_answer": None if not question else "Add a Gemini API key to enable AI answers based on the fetched headlines.",
    }

def summarize_with_gemini(articles, symbol=None, question=None):
    key = _gemini_key()
    if not key:
        return _fallback_summary(articles, question)

    # Keep prompt compact to stay friendly to free tiers.
    lines = []
    for i, a in enumerate(articles[:12], start=1):
        lines.append(f"{i}. Headline: {a.get('headline','')}\nSource: {a.get('source','')}\nDate: {a.get('date_label','')}\nSummary: {a.get('summary','')[:600]}")

    prompt = f"""
You are helping with a personal investing research dashboard.
Do not give personalized financial advice or instructions to buy/sell.
Use only the article information below. If evidence is weak, say so.

Ticker/context: {symbol or "market"}
Question: {question or "Summarize the major news themes and risks."}

Return a concise structured brief with:
- Overall read: Bullish, Bearish, Neutral, or Mixed
- 3 to 5 key themes
- catalysts to watch
- risks to watch
- short answer to the user's question if one was asked

Articles:
{chr(10).join(lines)}
""".strip()

    try:
        from google import genai
        client = genai.Client(api_key=key)
        model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        resp = client.models.generate_content(model=model, contents=prompt)
        text = getattr(resp, "text", None) or ""
        return {
            "mode": "gemini",
            "sentiment": _extract_sentiment(text),
            "summary": text.strip(),
            "themes": [],
            "risks": [],
            "catalysts": [],
            "question_answer": None,
        }
    except Exception as e:
        fb = _fallback_summary(articles, question)
        fb["summary"] = f"AI summary unavailable: {e}"
        return fb

def _extract_sentiment(text):
    t = (text or "").lower()
    for word in ["bullish", "bearish", "neutral", "mixed"]:
        if word in t:
            return word.title()
    return "Mixed"

def ai_search(query, symbol=None):
    # Backend backbone for the AI Search tab: fetch relevant news, then summarize.
    if symbol:
        articles = company_news(symbol, days_back=21, limit=20)
    else:
        articles = market_news(limit=20)
    brief = summarize_with_gemini(articles, symbol=symbol, question=query)
    return {"query": query, "symbol": symbol, "brief": brief, "articles": articles}
