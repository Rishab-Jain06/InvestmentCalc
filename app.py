from flask import Flask, render_template, jsonify, request, send_from_directory
from dotenv import load_dotenv
import os
import time
import json

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

import yahoo_data
import options_data
import news_ai
import sec_data
import screener_data
import tradier_data
import calendar_data
import alpha_vantage_data

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "local-personal-tool")

_COMPANY_AI_CACHE = {}


@app.get("/favicon.ico")
def favicon():
    return send_from_directory(os.path.join(app.root_path, "static", "img"), "favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.get("/")
def home(): return render_template("index.html")
@app.get("/markets")
def markets(): return render_template("markets.html")
@app.get("/research")
def research(): return render_template("research.html")
@app.get("/stock/<symbol>")
def stock(symbol): return render_template("stock.html", symbol=symbol.upper())
@app.get("/portfolio")
def portfolio(): return render_template("portfolio.html")
@app.get("/watchlist")
def watchlist(): return render_template("portfolio.html")
@app.get("/screener")
def screener(): return render_template("screener.html")
@app.get("/options")
def options(): return render_template("options.html")
@app.get("/settings")
def settings(): return render_template("settings.html")

@app.get("/news")
def news_page(): return render_template("news.html")

@app.get("/search")
def search_page(): return render_template("search.html")

@app.get("/api/quote/<symbol>")
def api_quote(symbol):
    try: return jsonify(yahoo_data.quote(symbol))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.get("/api/history/<symbol>")
def api_history(symbol):
    try: return jsonify(yahoo_data.history(symbol, request.args.get("range","1M")))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.get("/api/stats/<symbol>")
def api_stats(symbol):
    try: return jsonify(yahoo_data.stats(symbol))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.get("/api/technicals/<symbol>")
def api_technicals(symbol):
    try: return jsonify(yahoo_data.technicals(symbol))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.get("/api/analyze/<symbol>")
def api_analyze(symbol):
    try: return jsonify(yahoo_data.analyze_stock(symbol))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.get("/api/fundamentals/<symbol>")
def api_fundamentals(symbol):
    try: return jsonify(sec_data.fundamental_signal(symbol))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.get("/api/stock-signal/<symbol>")
def api_stock_signal(symbol):
    try: return jsonify(sec_data.overall_signal(symbol))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.get("/api/sec-filings/<symbol>")
def api_sec_filings(symbol):
    try: return jsonify(sec_data.recent_filings(symbol, limit=int(request.args.get("limit",8))))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.route("/api/company-summary/<symbol>", methods=["GET","POST"])
def api_company_summary(symbol):
    s = symbol.upper()
    refresh = request.args.get("refresh") == "1"
    now = time.time()
    cached = _COMPANY_AI_CACHE.get(s)
    if cached and not refresh and cached.get("expires_at", 0) > now:
        return jsonify(cached["value"])
    try:
        ctx = sec_data.company_context(s)
        identity = ctx.get("identity") or {}
        filings = ctx.get("recent_filings") or []
        prompt = f"""
You are writing a concise company overview for a personal stock research app.
Use only the provided context. Do not invent revenue segments if they are not provided.
Write 4-5 short sentences covering:
1. main business,
2. sector/industry,
3. important products/services or segments if known,
4. useful investor context or key business quality,
5. mention if important details are unavailable.

Context:
Ticker: {s}
Company name: {identity.get('name')}
Sector: {identity.get('sector')}
Industry: {identity.get('industry')}
Country: {identity.get('country')}
Employees: {identity.get('employees')}
Website: {identity.get('website')}
Business description: {identity.get('description')}
Fundamental snapshot: {ctx.get('fundamental')}
Recent SEC filings: {filings[:3]}
"""
        try:
            text, model = news_ai._gemini_rest(prompt)
            value = {"symbol": s, "summary": text.strip(), "mode": "gemini", "model": model, "cached": False}
        except Exception as ai_error:
            desc = (identity.get("description") or "").strip()
            fallback = "Company overview unavailable because Gemini is not configured and no business description was available."
            if desc:
                sentences = [x.strip() for x in desc.replace("\\n"," ").split(".") if x.strip()]
                fallback = ". ".join(sentences[:4]) + ("." if sentences else "")
            value = {"symbol": s, "summary": fallback, "mode": "fallback", "model": None, "error": str(ai_error), "cached": False}
        _COMPANY_AI_CACHE[s] = {"value": {**value, "cached": True}, "expires_at": now + 60*60*24*7}
        return jsonify(value)
    except Exception as e:
        return jsonify({"error":str(e)}),400

@app.get("/api/search")
def api_search():
    try: return jsonify(yahoo_data.search_symbols(request.args.get("q","")))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.post("/api/screener")
def api_screener():
    try:
        body = request.get_json(force=True) or {}
        filters = body.get("filters") or {}
        if body.get("symbols") and not filters.get("symbols"):
            filters["symbols"] = ",".join(body.get("symbols"))
            filters["universe"] = "custom"
        return jsonify(screener_data.run_screener(filters))
    except Exception as e:
        return jsonify({"error":str(e)}),400

@app.get("/api/options/expirations/<symbol>")
def api_options_expirations(symbol):
    try:
        exps=options_data.expirations(symbol)
        status=tradier_data.provider_status()
        return jsonify({
            "symbol":symbol.upper(),
            "expirations":[{"date":x,"dte":options_data.dte_for(x)} for x in exps],
            "provider":"tradier" if status.get("configured") else "yfinance",
            "source":status.get("label") if status.get("configured") else "Yahoo Finance fallback",
            "delayed": status.get("env") == "sandbox" if status.get("configured") else False
        })
    except Exception as e: return jsonify({"error":str(e)}),400


@app.get("/api/options/chain/<symbol>")
def api_options_chain(symbol):
    try:
        requested = request.args.get("expiration") or "AUTO"
        exps = options_data.expirations(symbol)
        if not exps:
            raise RuntimeError("No option expirations found")
        expiration = exps[0] if requested == "AUTO" else requested
        if expiration not in exps and requested != "AUTO":
            # Keep the requested date in case provider accepts it; otherwise this raises inside option_chain.
            expiration = requested
        chain = options_data.option_chain(symbol, expiration)
        rows = options_data.chain_rows(chain, limit_each_side=int(request.args.get("strikes", 14)))
        quote = chain.get("quote") or {}
        return jsonify({
            "symbol": symbol.upper(),
            "expiration": chain.get("expiration") or expiration,
            "dte": chain.get("dte"),
            "spot": chain.get("spot"),
            "quote": quote,
            "rows": rows,
            "calls_count": len(chain.get("calls") or []),
            "puts_count": len(chain.get("puts") or []),
            "provider": chain.get("provider") or "yfinance",
            "source": chain.get("source") or "Yahoo Finance fallback",
            "delayed": bool(chain.get("delayed")),
            "cached": bool(chain.get("cached")),
            "stale": bool(chain.get("stale")),
            "math_note": chain.get("math_note"),
            "fallback_error": chain.get("fallback_error"),
        })
    except Exception as e: return jsonify({"error":str(e)}),400

def _f(name, default=None):
    v=request.args.get(name)
    if v in (None,""): return default
    try:return float(v)
    except:return default

def _i(name, default=None):
    v=_f(name,default)
    return int(v) if v is not None else None

@app.get("/api/options/screen/<symbol>")
def api_options_screen(symbol):
    expiration=request.args.get("expiration","AUTO")
    strategy_type=request.args.get("strategy_type","single")
    strategy=request.args.get("strategy","buy_call")
    risk_profile=request.args.get("risk_profile","balanced")
    min_dte,max_dte=_i("min_dte"),_i("max_dte")
    if expiration == "AUTO" and min_dte is None and max_dte is None:
        if risk_profile == "conservative":
            min_dte, max_dte = 30, 60
        elif risk_profile == "aggressive":
            min_dte, max_dte = 7, 30
        else:
            min_dte, max_dte = 21, 45
    filters={
      "min_delta":_f("min_delta"),"max_delta":_f("max_delta"),"min_iv":_f("min_iv"),
      "min_oi":int(_f("min_oi",0) or 0),"min_volume":int(_f("min_volume",0) or 0),
      "max_bid_ask":_f("max_bid_ask"),"min_credit":_f("min_credit"),"max_debit":_f("max_debit"),
      "min_ror":_f("min_ror"),"spread_width":_f("spread_width"),"max_loss":_f("max_loss"),"max_width":_f("max_width"),
      "risk_profile": risk_profile, "strategy": strategy
    }
    try:
        scan=options_data.expirations_in_dte(symbol,min_dte,max_dte,limit=8) if expiration=="AUTO" else [expiration]
        try:
            technical=options_data.technical_snapshot(symbol)
        except Exception:
            technical={"status":"unknown","score":0,"signals":[],"reason":"Trend snapshot unavailable"}
        all_results=[]; spot=None
        for exp in scan:
            chain=options_data.option_chain(symbol,exp);spot=chain["spot"]
            if strategy_type=="single":
                display_strategy = strategy
                if strategy == "cash_secured_put":
                    action, kind = "sell", "put"
                    filters["display_strategy"] = display_strategy
                elif strategy == "covered_call":
                    action, kind = "sell", "call"
                    filters["display_strategy"] = display_strategy
                else:
                    action,kind=strategy.split("_",1)
                    filters.pop("display_strategy", None)
                rows=options_data.build_single_candidates(chain,action,kind,filters)
            else:
                rows=options_data.build_vertical_candidates(chain,strategy,filters)
            all_results.extend(rows)
        all_results=[options_data.score_trade_quality(x, technical) for x in all_results]
        # Sort in relevant natural order: closest useful strike first, then numerically outward.
        try:
            all_results.sort(key=lambda x: options_data._natural_sort_key(x, spot))
        except Exception:
            all_results.sort(key=lambda x:(x.get("expiration") or "", float(x.get("strike") or 0)))
        source = None
        provider = None
        delayed = False
        fallback_error = None
        math_note = None
        stale = False
        cached = False
        try:
            if scan:
                sample_chain = options_data.option_chain(symbol, scan[0])
                source = sample_chain.get("source")
                provider = sample_chain.get("provider")
                delayed = bool(sample_chain.get("delayed"))
                fallback_error = sample_chain.get("fallback_error")
                math_note = sample_chain.get("math_note")
                stale = bool(sample_chain.get("stale"))
                cached = bool(sample_chain.get("cached"))
        except Exception:
            pass
        return jsonify({"symbol":symbol.upper(),"spot":spot,"results":all_results[:400],"count":min(len(all_results),400),"expirations_scanned":scan,"dte_min":min_dte,"dte_max":max_dte,"trend":technical,"source":source,"provider":provider,"delayed":delayed,"fallback_error":fallback_error,"math_note":math_note,"stale":stale,"cached":cached})
    except Exception as e: return jsonify({"error":str(e)}),400

@app.post("/api/options/payoff")
def api_options_payoff():
    try:
        b=request.get_json(force=True);spot=float(b.get("spot") or 100)
        return jsonify({"points":options_data.payoff(b["legs"],float(b.get("low") or spot*.8),float(b.get("high") or spot*1.2))})
    except Exception as e:return jsonify({"error":str(e)}),400


@app.get("/api/news/market")
def api_news_market():
    try:
        limit = int(request.args.get("limit", 20))
        category = request.args.get("category", "general")
        return jsonify({"articles": news_ai.market_news(limit=limit, category=category)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.get("/api/news/company/<symbol>")
def api_news_company(symbol):
    try:
        limit = int(request.args.get("limit", 20))
        days = int(request.args.get("days", 14))
        return jsonify({"symbol": symbol.upper(), "articles": news_ai.company_news(symbol, days_back=days, limit=limit)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/news/sentiment/<symbol>")
def api_news_sentiment(symbol):
    try:
        days = int(request.args.get("days", 14))
        limit = int(request.args.get("limit", 6))
        return jsonify(news_ai.sentiment_for_symbol(symbol, days_back=days, limit=min(limit, 7)))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.post("/api/ai/summarize-news")
def api_ai_summarize_news():
    try:
        body = request.get_json(force=True)
        articles = body.get("articles") or []
        symbol = body.get("symbol")
        question = body.get("question")
        return jsonify(news_ai.summarize_with_gemini(articles, symbol=symbol, question=question))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.post("/api/ai/search")
def api_ai_search():
    try:
        body = request.get_json(force=True)
        query = body.get("query") or "Summarize the latest news."
        symbol = (body.get("symbol") or "").strip().upper() or None
        return jsonify(news_ai.ai_search(query, symbol=symbol))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.post("/api/ai/chat")
def api_ai_chat():
    try:
        body = request.get_json(force=True)
        messages = body.get("messages") or []
        context = body.get("context") or {}
        mode = (body.get("mode") or context.get("mode") or "general").strip().lower()
        symbol = (body.get("symbol") or context.get("ticker") or "").strip().upper()

        # Build live context only when requested. This avoids slow calls for every chat.
        if body.get("include_live_context"):
            live = {}
            if mode == "market" and not symbol:
                live = news_ai.build_market_chat_context(limit=10)
            elif symbol:
                live = news_ai.build_stock_chat_context(symbol)
            live.update(context or {})
            context = live
            if symbol:
                context["ticker"] = symbol
        context["mode"] = mode

        return jsonify(news_ai.chat_with_gemini(messages, context=context, mode=mode))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/news/digest")
def api_news_digest():
    try:
        limit = int(request.args.get("limit", 10))
        return jsonify(news_ai.market_context_digest(limit=limit))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.get("/api/markets/digest")
def api_markets_digest():
    try:
        limit = int(request.args.get("limit", 12))
        return jsonify(news_ai.market_strategy_digest(limit=limit))
    except Exception as e:
        return jsonify({"error": str(e)}), 400



@app.post("/api/portfolio/review")
def api_portfolio_review():
    try:
        body = request.get_json(force=True) or {}
        holdings = body.get("holdings") or []
        cash = body.get("cash") or []
        totals = body.get("totals") or {}
        watchlist = body.get("watchlist") or []
        sector_exposure = body.get("sector_exposure") or []
        industry_exposure = body.get("industry_exposure") or []
        largest_positions = body.get("largest_positions") or []
        prompt = f"""
You are Investify AI reviewing a manually entered portfolio.
Use only the supplied portfolio data. Do not invent holdings, prices, sectors, or real-time market facts.
Do not tell the user to buy or sell.
Return an extremely short, high-level dashboard view only. No markdown. No long paragraphs.
Do NOT restate each holding, all allocations, or position-by-position performance.
Focus on diversification, gaps, and suggestions. Keep it useful but very brief.

Return valid JSON only using this exact shape:
{{
  "health_score": 0-100,
  "health_label": "Strong" | "Balanced" | "Needs attention" | "High risk",
  "headline": "one short sentence, under 100 characters",
  "bullets": ["exactly 3 bullets: diversification, gaps, suggestions; each under 120 characters"]
}}

Portfolio totals:
{totals}

Sector exposure:
{sector_exposure}

Industry exposure:
{industry_exposure}

Largest positions:
{largest_positions}

Holdings with quote context:
{holdings}

Cash:
{cash}

Watchlist:
{watchlist}
"""
        try:
            text, model = news_ai._gemini_rest(prompt, json_mode=True)
            parsed = news_ai._parse_json_safely(text) or {}
            if not isinstance(parsed, dict) or not parsed.get("headline"):
                raise RuntimeError("Gemini returned an unstructured review.")
            bullets = parsed.get("bullets") or []
            if not isinstance(bullets, list):
                bullets = [str(bullets)]
            parsed["bullets"] = [str(x).replace("\n", " ").strip()[:120] for x in bullets[:3]]
            parsed["headline"] = str(parsed.get("headline") or "").replace("\n", " ").strip()[:110]
            return jsonify({"mode": "gemini", "model": model, "review_card": parsed})
        except Exception as e:
            total_value = float(totals.get("totalValue") or 0)
            cash_total = sum(float(x.get("amount") or 0) for x in cash)
            biggest = sorted(holdings, key=lambda x: float(x.get("market_value") or 0), reverse=True)[:1]
            top_weight = float(biggest[0].get("weight") or 0) if biggest else 0
            cash_weight = (cash_total / total_value * 100) if total_value else 0
            sector_names = [x.get("name") for x in sector_exposure[:3] if x.get("name")]
            industry_names = [x.get("name") for x in industry_exposure[:3] if x.get("name")]
            sector_count = len([x for x in sector_exposure if x.get("name")])
            score = 78
            if top_weight > 20:
                score -= min(18, int(top_weight - 20))
            if cash_weight > 35:
                score -= min(12, int((cash_weight - 35) / 2))
            if sector_count >= 4:
                score += 4
            elif sector_count <= 2:
                score -= 8
            score = max(35, min(90, score))
            label = "Strong" if score >= 82 else "Balanced" if score >= 68 else "Needs attention" if score >= 50 else "High risk"
            card = {
                "health_score": score,
                "health_label": label,
                "headline": "Balanced mix; watch concentration, cash level and sector gaps.",
                "bullets": [
                    f"Diversification spans {', '.join(sector_names[:2]) if sector_names else 'available sectors'} with some concentration risk.",
                    f"Gaps may remain in defensive sectors and non-tech industry coverage.",
                    f"Consider whether {cash_weight:.1f}% cash and a {top_weight:.1f}% top position match your risk target."
                ],
            }
            return jsonify({"mode": "fallback", "model": None, "review_card": card, "error": str(e)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get("/calendar")
def calendar_page():
    return render_template("calendar.html")


@app.get("/api/calendar/events")
def api_calendar_events():
    try:
        start = request.args.get("start")
        end = request.args.get("end")
        raw_symbols = request.args.get("symbols", "")
        symbols = [x.strip().upper() for x in raw_symbols.replace(";", ",").split(",") if x.strip()]
        restrict_to_symbols = request.args.get("restrict_to_symbols") in ("1", "true", "yes")
        return jsonify(calendar_data.market_calendar(start=start, end=end, symbols=symbols, restrict_to_symbols=restrict_to_symbols))
    except Exception as e:
        return jsonify({"error": str(e)}), 400



@app.post("/api/calendar/event-details")
def api_calendar_event_details():
    try:
        body = request.get_json(force=True) or {}
        event = body.get("event") or body
        return jsonify(calendar_data.event_details(event))
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.post("/api/calendar/event-brief")
def api_calendar_event_brief():
    try:
        body = request.get_json(force=True) or {}
        event = body.get("event") or body
        return jsonify(calendar_data.event_ai_brief(event))
    except Exception as e:
        return jsonify({"error": str(e)}), 400



if __name__=="__main__":
    app.run(debug=True)
