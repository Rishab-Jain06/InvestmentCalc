from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
import yahoo_data
import options_data
import news_ai
import os

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "local-personal-tool")

@app.get("/")
def home(): return render_template("index.html")
@app.get("/markets")
def markets(): return render_template("markets.html")
@app.get("/research")
def research(): return render_template("research.html")
@app.get("/stock/<symbol>")
def stock(symbol): return render_template("stock.html", symbol=symbol.upper())
@app.get("/watchlist")
def watchlist(): return render_template("watchlist.html")
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

@app.get("/api/search")
def api_search():
    try: return jsonify(yahoo_data.search_symbols(request.args.get("q","")))
    except Exception as e: return jsonify({"error":str(e)}),400

@app.post("/api/screener")
def api_screener():
    try:
        body=request.get_json(force=True)
        symbols=body.get("symbols") or []
        rows=yahoo_data.bulk_snapshot(symbols)
        f=body.get("filters") or {}
        def passed(x):
            if x.get("error"): return False
            if f.get("min_price") is not None and (x.get("price") or 0)<f["min_price"]: return False
            if f.get("max_price") is not None and (x.get("price") or 0)>f["max_price"]: return False
            if f.get("min_volume") is not None and (x.get("volume") or 0)<f["min_volume"]: return False
            if f.get("min_score") is not None and (x.get("score") or 0)<f["min_score"]: return False
            if f.get("signal") and f["signal"]!="any" and x.get("signal")!=f["signal"]: return False
            if f.get("min_rsi") is not None and (x.get("rsi") is None or x["rsi"]<f["min_rsi"]): return False
            if f.get("max_rsi") is not None and (x.get("rsi") is None or x["rsi"]>f["max_rsi"]): return False
            return True
        rows=[x for x in rows if passed(x)]
        rows.sort(key=lambda x:(x.get("score") or 0,x.get("volume") or 0), reverse=True)
        return jsonify({"results":rows,"count":len(rows)})
    except Exception as e:
        return jsonify({"error":str(e)}),400

@app.get("/api/options/expirations/<symbol>")
def api_options_expirations(symbol):
    try:
        exps=options_data.expirations(symbol)
        return jsonify({"symbol":symbol.upper(),"expirations":[{"date":x,"dte":options_data.dte_for(x)} for x in exps]})
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
    min_dte,max_dte=_i("min_dte"),_i("max_dte")
    filters={
      "min_delta":_f("min_delta"),"max_delta":_f("max_delta"),"min_iv":_f("min_iv"),
      "min_oi":int(_f("min_oi",0) or 0),"min_volume":int(_f("min_volume",0) or 0),
      "max_bid_ask":_f("max_bid_ask"),"min_credit":_f("min_credit"),"max_debit":_f("max_debit"),
      "min_ror":_f("min_ror"),"spread_width":_f("spread_width"),"max_loss":_f("max_loss"),"max_width":_f("max_width")
    }
    try:
        scan=options_data.expirations_in_dte(symbol,min_dte,max_dte,limit=8) if expiration=="AUTO" else [expiration]
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
        if strategy_type=="vertical":
            all_results.sort(key=lambda x:(x.get("ror") or -999,x.get("open_interest") or 0),reverse=True)
        else:
            all_results.sort(key=lambda x:(x.get("open_interest") or 0,x.get("volume") or 0),reverse=True)
        return jsonify({"symbol":symbol.upper(),"spot":spot,"results":all_results[:400],"count":min(len(all_results),400),"expirations_scanned":scan,"dte_min":min_dte,"dte_max":max_dte})
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
        symbol = (body.get("symbol") or context.get("ticker") or "").strip().upper()

        # Build live context only when requested. This avoids slow calls for every chat.
        if body.get("include_live_context") and symbol:
            live = news_ai.build_stock_chat_context(symbol)
            live.update(context or {})
            context = live

        return jsonify(news_ai.chat_with_gemini(messages, context=context))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.get("/api/news/digest")
def api_news_digest():
    try:
        limit = int(request.args.get("limit", 8))
        return jsonify(news_ai.market_context_digest(limit=limit))
    except Exception as e:
        return jsonify({"error": str(e)}), 400





if __name__=="__main__":
    app.run(debug=True)
