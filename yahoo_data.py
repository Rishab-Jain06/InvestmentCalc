from __future__ import annotations
import math
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import yfinance as yf

def _safe_float(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)): return None
        return float(v)
    except Exception:
        return None

def _safe_int(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)): return None
        return int(v)
    except Exception:
        return None

def quote(symbol):
    s = symbol.upper()
    t = yf.Ticker(s)
    fi = {}
    info = {}
    try: fi = dict(t.fast_info)
    except Exception: pass
    try: info = t.info or {}
    except Exception: pass

    price = _safe_float(fi.get("last_price") or info.get("currentPrice") or info.get("regularMarketPrice"))
    prev = _safe_float(fi.get("previous_close") or info.get("previousClose") or info.get("regularMarketPreviousClose"))
    change = (price-prev) if price is not None and prev is not None else None
    pct = (change/prev*100) if change is not None and prev else None

    return {
        "symbol": s,
        "name": info.get("shortName") or info.get("longName") or s,
        "exchange": info.get("exchange") or info.get("fullExchangeName"),
        "currency": info.get("currency") or fi.get("currency"),
        "price": price,
        "previous_close": prev,
        "change": change,
        "percent_change": pct,
        "open": _safe_float(info.get("open") or info.get("regularMarketOpen")),
        "day_high": _safe_float(info.get("dayHigh") or info.get("regularMarketDayHigh")),
        "day_low": _safe_float(info.get("dayLow") or info.get("regularMarketDayLow")),
        "volume": _safe_int(info.get("volume") or info.get("regularMarketVolume")),
        "avg_volume": _safe_int(info.get("averageVolume") or info.get("averageDailyVolume10Day")),
        "bid": _safe_float(info.get("bid")),
        "ask": _safe_float(info.get("ask")),
        "bid_size": _safe_int(info.get("bidSize")),
        "ask_size": _safe_int(info.get("askSize")),
        "market_state": info.get("marketState"),
        "fifty_two_week_low": _safe_float(info.get("fiftyTwoWeekLow")),
        "fifty_two_week_high": _safe_float(info.get("fiftyTwoWeekHigh")),
    }

RANGES = {
    "1D": ("1d","5m"),
    "5D": ("5d","15m"),
    "1M": ("1mo","60m"),
    "3M": ("3mo","1d"),
    "6M": ("6mo","1d"),
    "YTD": ("ytd","1d"),
    "1Y": ("1y","1d"),
    "5Y": ("5y","1wk"),
    "MAX": ("max","1mo"),
}

def history(symbol, range_name="1M"):
    period, interval = RANGES.get(range_name.upper(), RANGES["1M"])
    df = yf.Ticker(symbol.upper()).history(period=period, interval=interval, auto_adjust=False)
    rows = []
    if df is not None and not df.empty:
        for idx, r in df.iterrows():
            rows.append({
                "datetime": idx.isoformat(),
                "open": _safe_float(r.get("Open")),
                "high": _safe_float(r.get("High")),
                "low": _safe_float(r.get("Low")),
                "close": _safe_float(r.get("Close")),
                "volume": _safe_int(r.get("Volume")),
            })
    return {"symbol": symbol.upper(), "range": range_name.upper(), "interval": interval, "values": rows}

def _pct(v):
    x = _safe_float(v)
    return x*100 if x is not None else None

def stats(symbol):
    t = yf.Ticker(symbol.upper())
    try: info = t.info or {}
    except Exception: info = {}
    return {
        "identity": {
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "website": info.get("website"),
            "country": info.get("country"),
            "employees": _safe_int(info.get("fullTimeEmployees")),
            "description": info.get("longBusinessSummary"),
        },
        "market": {
            "market_cap": _safe_int(info.get("marketCap")),
            "enterprise_value": _safe_int(info.get("enterpriseValue")),
            "shares_outstanding": _safe_int(info.get("sharesOutstanding")),
            "float_shares": _safe_int(info.get("floatShares")),
            "beta": _safe_float(info.get("beta")),
            "avg_volume": _safe_int(info.get("averageVolume")),
            "fifty_day_average": _safe_float(info.get("fiftyDayAverage")),
            "two_hundred_day_average": _safe_float(info.get("twoHundredDayAverage")),
            "fifty_two_week_low": _safe_float(info.get("fiftyTwoWeekLow")),
            "fifty_two_week_high": _safe_float(info.get("fiftyTwoWeekHigh")),
        },
        "valuation": {
            "trailing_pe": _safe_float(info.get("trailingPE")),
            "forward_pe": _safe_float(info.get("forwardPE")),
            "peg_ratio": _safe_float(info.get("pegRatio") or info.get("trailingPegRatio")),
            "price_to_sales": _safe_float(info.get("priceToSalesTrailing12Months")),
            "price_to_book": _safe_float(info.get("priceToBook")),
            "ev_to_revenue": _safe_float(info.get("enterpriseToRevenue")),
            "ev_to_ebitda": _safe_float(info.get("enterpriseToEbitda")),
        },
        "profitability": {
            "profit_margin": _pct(info.get("profitMargins")),
            "gross_margin": _pct(info.get("grossMargins")),
            "operating_margin": _pct(info.get("operatingMargins")),
            "roe": _pct(info.get("returnOnEquity")),
            "roa": _pct(info.get("returnOnAssets")),
        },
        "financial": {
            "revenue": _safe_int(info.get("totalRevenue")),
            "revenue_growth": _pct(info.get("revenueGrowth")),
            "ebitda": _safe_int(info.get("ebitda")),
            "free_cash_flow": _safe_int(info.get("freeCashflow")),
            "operating_cash_flow": _safe_int(info.get("operatingCashflow")),
            "cash": _safe_int(info.get("totalCash")),
            "debt": _safe_int(info.get("totalDebt")),
            "current_ratio": _safe_float(info.get("currentRatio")),
            "quick_ratio": _safe_float(info.get("quickRatio")),
            "trailing_eps": _safe_float(info.get("trailingEps")),
            "forward_eps": _safe_float(info.get("forwardEps")),
        },
        "dividend": {
            "yield": _pct(info.get("dividendYield")),
            "rate": _safe_float(info.get("dividendRate")),
            "payout_ratio": _pct(info.get("payoutRatio")),
            "ex_dividend_date": info.get("exDividendDate"),
        }
    }

def technicals(symbol, period="1y"):
    df = yf.Ticker(symbol.upper()).history(period=period, interval="1d", auto_adjust=False)
    if df is None or df.empty or len(df) < 30:
        return {"error":"Insufficient history"}
    c = df["Close"].astype(float)
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    v = df["Volume"].astype(float)

    sma20 = c.rolling(20).mean()
    sma50 = c.rolling(50).mean()
    sma200 = c.rolling(200).mean()
    ema20 = c.ewm(span=20, adjust=False).mean()
    ema50 = c.ewm(span=50, adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()

    d = c.diff()
    gain = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100/(1+rs)

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd = ema12-ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd-macd_signal

    tr = pd.concat([(h-l),(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    std20 = c.rolling(20).std()
    bb_mid = sma20
    bb_upper = bb_mid + 2*std20
    bb_lower = bb_mid - 2*std20

    obv = (np.sign(c.diff()).fillna(0)*v).cumsum()

    def last(s):
        try:
            x = float(s.dropna().iloc[-1])
            return x if not math.isnan(x) else None
        except Exception: return None

    return {
        "price": last(c), "sma20":last(sma20),"sma50":last(sma50),"sma200":last(sma200),
        "ema20":last(ema20),"ema50":last(ema50),"ema200":last(ema200),
        "rsi14":last(rsi),"macd":last(macd),"macd_signal":last(macd_signal),
        "macd_histogram":last(macd_hist),"atr14":last(atr),
        "bb_upper":last(bb_upper),"bb_mid":last(bb_mid),"bb_lower":last(bb_lower),
        "obv":last(obv)
    }

def analyze_stock(symbol):
    t = technicals(symbol)
    if t.get("error"): return {"signal":"unknown","score":0,"reasons":[t["error"]],"technicals":t}
    p = t.get("price")
    score = 50
    reasons = []
    if p and t.get("ema20"):
        if p > t["ema20"]: score += 10; reasons.append("Price above EMA20")
        else: score -= 10; reasons.append("Price below EMA20")
    if p and t.get("ema50"):
        if p > t["ema50"]: score += 10; reasons.append("Price above EMA50")
        else: score -= 10; reasons.append("Price below EMA50")
    if t.get("ema20") and t.get("ema50"):
        if t["ema20"] > t["ema50"]: score += 8; reasons.append("EMA20 above EMA50")
        else: score -= 8; reasons.append("EMA20 below EMA50")
    rsi = t.get("rsi14")
    if rsi is not None:
        if 50 <= rsi <= 70: score += 8; reasons.append(f"RSI {rsi:.1f}: positive momentum")
        elif rsi > 75: score -= 4; reasons.append(f"RSI {rsi:.1f}: overbought")
        elif rsi < 35: score -= 6; reasons.append(f"RSI {rsi:.1f}: weak momentum")
        else: reasons.append(f"RSI {rsi:.1f}: neutral")
    mh = t.get("macd_histogram")
    if mh is not None:
        if mh > 0: score += 9; reasons.append("MACD histogram positive")
        else: score -= 9; reasons.append("MACD histogram negative")
    score = max(0,min(100,round(score)))
    signal = "bullish" if score >= 65 else "bearish" if score <= 35 else "neutral"
    return {"signal":signal,"score":score,"reasons":reasons,"technicals":t}

def search_symbols(query):
    # yfinance Search is not stable across versions; use its Search object when available.
    try:
        s = yf.Search(query, max_results=10, news_count=0)
        q = getattr(s, "quotes", None) or []
        return [{"symbol":x.get("symbol"),"name":x.get("shortname") or x.get("longname"),"exchange":x.get("exchange")} for x in q if x.get("symbol")]
    except Exception:
        return [{"symbol":query.upper(),"name":query.upper(),"exchange":None}]

def bulk_snapshot(symbols):
    out = []
    for s in symbols[:25]:
        try:
            q = quote(s)
            a = analyze_stock(s)
            out.append({**q, "signal":a["signal"],"score":a["score"],"rsi":a["technicals"].get("rsi14"),"ema20":a["technicals"].get("ema20"),"ema50":a["technicals"].get("ema50")})
        except Exception as e:
            out.append({"symbol":s.upper(),"error":str(e)})
    return out
