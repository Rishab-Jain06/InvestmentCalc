from __future__ import annotations
import math
import os
import time
from threading import Lock
import pandas as pd
import numpy as np
import requests
import yfinance as yf

_CACHE = {}
_CACHE_LOCK = Lock()


def _cache_fetch(key, ttl_seconds, loader, stale_grace_seconds=None):
    now = time.time()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and entry["expires_at"] > now:
            return entry["value"]
    try:
        value = loader()
        with _CACHE_LOCK:
            _CACHE[key] = {
                "value": value,
                "cached_at": now,
                "expires_at": now + ttl_seconds,
            }
        return value
    except Exception:
        if entry and stale_grace_seconds is not None and (now - entry["cached_at"]) <= stale_grace_seconds:
            return entry["value"]
        raise


def _safe_float(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return float(v)
    except Exception:
        return None


def _safe_int(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return int(v)
    except Exception:
        return None




def _display_exchange(value):
    raw = (value or "").strip()
    code = raw.upper()
    mapping = {
        "NMS": "NASDAQ",
        "NGM": "NASDAQ",
        "NCM": "NASDAQ",
        "NASDAQGS": "NASDAQ",
        "NASDAQGM": "NASDAQ",
        "NASDAQCM": "NASDAQ",
        "NYQ": "NYSE",
        "NYSE": "NYSE",
        "ASE": "NYSE American",
        "AMEX": "NYSE American",
        "PCX": "NYSE Arca",
        "ARCA": "NYSE Arca",
        "BTS": "Cboe BZX",
        "BATS": "Cboe BZX",
        "PNK": "OTC",
        "OTC": "OTC",
    }
    return mapping.get(code, raw)



FINNHUB_BASE = "https://finnhub.io/api/v1"


def _finnhub_token():
    return (os.getenv("FINNHUB_API_KEY") or "").strip()


def _finnhub_get(path, params=None, timeout=12):
    token = _finnhub_token()
    if not token:
        raise RuntimeError("FINNHUB_API_KEY is not configured.")
    p = dict(params or {})
    p["token"] = token
    r = requests.get(f"{FINNHUB_BASE}{path}", params=p, timeout=timeout)
    if r.status_code == 429:
        raise RuntimeError("Finnhub rate limit reached.")
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data.get("error")))
    return data


def _first_not_none(*vals):
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return None


def _valid_price(v):
    x = _safe_float(v)
    if x is None or x <= 0:
        return None
    return x


def _finnhub_market_cap(profile, metric):
    raw = _safe_float((profile or {}).get("marketCapitalization"))
    if raw is not None:
        # Finnhub profile marketCapitalization is commonly returned in millions.
        return _safe_int(raw * 1_000_000)
    raw2 = _safe_float(((metric or {}).get("metric") or {}).get("marketCapitalization"))
    if raw2 is not None:
        return _safe_int(raw2 * 1_000_000)
    return None


def _metric_value(metric, *keys):
    m = (metric or {}).get("metric") or {}
    for key in keys:
        if key in m:
            v = _safe_float(m.get(key))
            if v is not None:
                return v
    return None


def _normalize_finnhub_exchange(raw):
    text = (raw or "").strip()
    up = text.upper()
    if "NASDAQ" in up:
        return "NASDAQ"
    if "NEW YORK STOCK EXCHANGE" in up or up.startswith("NYSE"):
        return "NYSE"
    if "AMEX" in up or "NYSE AMERICAN" in up:
        return "NYSE American"
    if "ARCA" in up:
        return "NYSE Arca"
    return _display_exchange(text)


def _finnhub_quote_data(s):
    quote_payload = _finnhub_get("/quote", {"symbol": s})
    profile = {}
    metric = {}

    # Quote response may return zeros/empty for unsupported symbols. Treat as unusable unless current/prev exists.
    current = _valid_price(quote_payload.get("c"))
    previous = _valid_price(quote_payload.get("pc"))
    if current is None and previous is None:
        raise RuntimeError("Finnhub returned no quote values.")

    try:
        profile = _finnhub_get("/stock/profile2", {"symbol": s})
    except Exception:
        profile = {}
    try:
        metric = _finnhub_get("/stock/metric", {"symbol": s, "metric": "all"})
    except Exception:
        metric = {}

    change = _safe_float(quote_payload.get("d"))
    pct = _safe_float(quote_payload.get("dp"))
    if change is None and current is not None and previous is not None:
        change = current - previous
    if pct is None and change is not None and previous:
        pct = change / previous * 100

    # Finnhub does not provide bid/ask in the basic quote endpoint. Yahoo fallback may fill those.
    profile_name = profile.get("name") or profile.get("ticker") or s
    finnhub_industry = profile.get("finnhubIndustry")

    avg_vol = _metric_value(metric, "10DayAverageTradingVolume", "3MonthAverageTradingVolume")
    # Some Finnhub average volume metrics are in millions of shares; leave very large values unchanged.
    if avg_vol is not None and avg_vol < 100000:
        avg_vol = avg_vol * 1_000_000

    return {
        "symbol": s,
        "name": profile_name,
        "sector": finnhub_industry,
        "industry": finnhub_industry,
        "market_cap": _finnhub_market_cap(profile, metric),
        "quote_type": "EQUITY",
        "exchange": _normalize_finnhub_exchange(profile.get("exchange")),
        "exchange_raw": profile.get("exchange"),
        "currency": profile.get("currency") or "USD",
        "price": current,
        "previous_close": previous,
        "change": change,
        "percent_change": pct,
        "open": _valid_price(quote_payload.get("o")),
        "day_high": _valid_price(quote_payload.get("h")),
        "day_low": _valid_price(quote_payload.get("l")),
        "volume": None,
        "avg_volume": _safe_int(avg_vol),
        "bid": None,
        "ask": None,
        "bid_size": None,
        "ask_size": None,
        "market_state": None,
        "fifty_two_week_low": _metric_value(metric, "52WeekLow", "52WeekLowDate"),
        "fifty_two_week_high": _metric_value(metric, "52WeekHigh", "52WeekHighDate"),
        "source": "Finnhub primary",
        "provider": "finnhub",
    }


def _yahoo_quote_data(s):
    t = yf.Ticker(s)
    fi = {}
    info = {}
    try:
        fi = dict(t.fast_info)
    except Exception:
        pass
    try:
        info = t.info or {}
    except Exception:
        pass

    price = _safe_float(fi.get("last_price") or info.get("currentPrice") or info.get("regularMarketPrice"))
    prev = _safe_float(fi.get("previous_close") or info.get("previousClose") or info.get("regularMarketPreviousClose"))
    change = (price - prev) if price is not None and prev is not None else None
    pct = (change / prev * 100) if change is not None and prev else None

    raw_exchange = info.get("exchange") or info.get("fullExchangeName")
    return {
        "symbol": s,
        "name": info.get("shortName") or info.get("longName") or s,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": _safe_int(info.get("marketCap")),
        "quote_type": info.get("quoteType"),
        "exchange": _display_exchange(raw_exchange),
        "exchange_raw": raw_exchange,
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
        "source": "Yahoo Finance fallback",
        "provider": "yfinance",
    }


def _merge_quote(primary, fallback):
    primary = dict(primary or {})
    fallback = dict(fallback or {})
    merged = dict(primary)

    filled = []
    for key, value in fallback.items():
        if key in {"source", "provider"}:
            continue
        current = merged.get(key)
        if current in (None, "", [], {}) and value not in (None, "", [], {}):
            merged[key] = value
            filled.append(key)

    # Recalculate change if fallback filled missing current/previous.
    price = _safe_float(merged.get("price"))
    prev = _safe_float(merged.get("previous_close"))
    if merged.get("change") is None and price is not None and prev is not None:
        merged["change"] = price - prev
    if merged.get("percent_change") is None and merged.get("change") is not None and prev:
        merged["percent_change"] = merged["change"] / prev * 100

    if filled:
        merged["source"] = f"{primary.get('source', 'Finnhub primary')} + Yahoo fallback"
        merged["fallback_filled_fields"] = filled
    else:
        merged["source"] = primary.get("source") or fallback.get("source")
        merged["fallback_filled_fields"] = []
    merged["provider"] = primary.get("provider") or fallback.get("provider")
    return merged

def quote(symbol):
    s = symbol.upper().strip()

    def _load():
        finnhub = None
        yahoo = None
        errors = []

        try:
            finnhub = _finnhub_quote_data(s)
        except Exception as e:
            errors.append(f"Finnhub: {e}")

        # Use Yahoo only as a fallback/fill source when Finnhub fails or has missing fields.
        needs_yahoo = (
            finnhub is None
            or finnhub.get("volume") is None
            or finnhub.get("bid") is None
            or finnhub.get("ask") is None
            or finnhub.get("sector") is None
            or finnhub.get("fifty_two_week_high") is None
            or finnhub.get("fifty_two_week_low") is None
        )
        if needs_yahoo:
            try:
                yahoo = _yahoo_quote_data(s)
            except Exception as e:
                errors.append(f"Yahoo fallback: {e}")

        if finnhub and yahoo:
            out = _merge_quote(finnhub, yahoo)
        elif finnhub:
            out = finnhub
        elif yahoo:
            out = yahoo
            out["source"] = "Yahoo Finance fallback only"
        else:
            # Preserve the old response shape instead of breaking the UI.
            out = {
                "symbol": s, "name": s, "sector": None, "industry": None, "market_cap": None,
                "quote_type": None, "exchange": "", "exchange_raw": None, "currency": "USD",
                "price": None, "previous_close": None, "change": None, "percent_change": None,
                "open": None, "day_high": None, "day_low": None, "volume": None, "avg_volume": None,
                "bid": None, "ask": None, "bid_size": None, "ask_size": None, "market_state": None,
                "fifty_two_week_low": None, "fifty_two_week_high": None, "source": "unavailable",
                "provider": None,
            }

        out["errors"] = errors
        return out

    return _cache_fetch(f"quote:v49:{s}", 30, _load, stale_grace_seconds=1800)


RANGES = {
    "1D": ("1d", "5m"),
    "5D": ("5d", "15m"),
    "1M": ("1mo", "60m"),
    "3M": ("3mo", "1d"),
    "6M": ("6mo", "1d"),
    "YTD": ("ytd", "1d"),
    "1Y": ("1y", "1d"),
    "5Y": ("5y", "1wk"),
    "MAX": ("max", "1mo"),
}

_HISTORY_TTLS = {
    "1D": 45,
    "5D": 90,
    "1M": 300,
    "3M": 600,
    "6M": 900,
    "YTD": 900,
    "1Y": 1800,
    "5Y": 3600,
    "MAX": 7200,
}


def history(symbol, range_name="1M"):
    s = symbol.upper()
    range_key = range_name.upper()
    period, interval = RANGES.get(range_key, RANGES["1M"])

    def _load():
        df = yf.Ticker(s).history(period=period, interval=interval, auto_adjust=False)
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
        return {"symbol": s, "range": range_key, "interval": interval, "values": rows}

    return _cache_fetch(f"history:{s}:{range_key}", _HISTORY_TTLS.get(range_key, 300), _load, stale_grace_seconds=7200)


def _pct(v):
    x = _safe_float(v)
    return x * 100 if x is not None else None


def stats(symbol):
    s = symbol.upper()

    def _load():
        t = yf.Ticker(s)
        try:
            info = t.info or {}
        except Exception:
            info = {}
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

    return _cache_fetch(f"stats:{s}", 1800, _load, stale_grace_seconds=86400)


def technicals(symbol, period="1y"):
    s = symbol.upper()
    cache_key = f"technicals:{s}:{period}"

    def _load():
        df = yf.Ticker(s).history(period=period, interval="1d", auto_adjust=False)
        if df is None or df.empty or len(df) < 30:
            return {"error": "Insufficient history"}
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
        gain = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
        loss = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs)

        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_signal

        tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()

        std20 = c.rolling(20).std()
        bb_mid = sma20
        bb_upper = bb_mid + 2 * std20
        bb_lower = bb_mid - 2 * std20

        obv = (np.sign(c.diff()).fillna(0) * v).cumsum()

        def last(series):
            try:
                x = float(series.dropna().iloc[-1])
                return x if not math.isnan(x) else None
            except Exception:
                return None

        def prev(series, n=5):
            try:
                clean = series.dropna()
                if len(clean) <= n:
                    return None
                x = float(clean.iloc[-1-n])
                return x if not math.isnan(x) else None
            except Exception:
                return None

        price = last(c)
        atr_now = last(atr)
        ema20_now = last(ema20)
        ema50_now = last(ema50)
        ema50_prev = prev(ema50, 5)
        macd_hist_now = last(macd_hist)
        macd_hist_prev = prev(macd_hist, 3)
        try:
            recent_return_5d = (float(c.iloc[-1]) / float(c.iloc[-6]) - 1) * 100 if len(c) >= 6 and float(c.iloc[-6]) else None
        except Exception:
            recent_return_5d = None

        return {
            "price": price, "sma20": last(sma20), "sma50": last(sma50), "sma200": last(sma200),
            "ema20": ema20_now, "ema50": ema50_now, "ema200": last(ema200),
            "ema50_prev_5d": ema50_prev, "ema50_slope_pct_5d": ((ema50_now - ema50_prev) / ema50_prev * 100) if ema50_now and ema50_prev else None,
            "rsi14": last(rsi), "macd": last(macd), "macd_signal": last(macd_signal),
            "macd_histogram": macd_hist_now, "macd_histogram_prev_3d": macd_hist_prev,
            "macd_histogram_change_3d": (macd_hist_now - macd_hist_prev) if macd_hist_now is not None and macd_hist_prev is not None else None,
            "atr14": atr_now, "atr_pct": (atr_now / price * 100) if atr_now and price else None,
            "recent_return_5d": recent_return_5d,
            "distance_ema20_pct": ((price - ema20_now) / ema20_now * 100) if price and ema20_now else None,
            "distance_ema50_pct": ((price - ema50_now) / ema50_now * 100) if price and ema50_now else None,
            "bb_upper": last(bb_upper), "bb_mid": last(bb_mid), "bb_lower": last(bb_lower),
            "obv": last(obv)
        }

    return _cache_fetch(cache_key, 600, _load, stale_grace_seconds=86400)



def _component(label, score, weight, details):
    score = max(0, min(100, round(score)))
    points = round(score * weight / 100)
    return {"label": label, "score": score, "weight": weight, "points": points, "details": details}


def analyze_stock(symbol):
    t = technicals(symbol)
    if t.get("error"):
        return {"signal": "unknown", "score": 0, "reasons": [t["error"]], "components": [], "technicals": t}

    p = t.get("price")
    ema20 = t.get("ema20")
    ema50 = t.get("ema50")
    ema50_slope = t.get("ema50_slope_pct_5d")
    rsi = t.get("rsi14")
    mh = t.get("macd_histogram")
    mh_change = t.get("macd_histogram_change_3d")
    ret5 = t.get("recent_return_5d")
    dist20 = t.get("distance_ema20_pct")
    dist50 = t.get("distance_ema50_pct")
    atr_pct = t.get("atr_pct")

    reasons = []
    chips = []

    # 1) Trend Structure: 40%
    trend_checks = []
    if p is not None and ema20 is not None:
        trend_checks.append(100 if p >= ema20 else 0)
        chips.append("Price above EMA20" if p >= ema20 else "Price below EMA20")
        reasons.append("Price is above EMA20, supporting short-term trend." if p >= ema20 else "Price is below EMA20, showing short-term weakness.")
    if p is not None and ema50 is not None:
        trend_checks.append(100 if p >= ema50 else 0)
        chips.append("Price above EMA50" if p >= ema50 else "Price below EMA50")
        reasons.append("Price is above EMA50, supporting medium-term trend." if p >= ema50 else "Price is below EMA50, showing medium-term weakness.")
    if ema20 is not None and ema50 is not None:
        trend_checks.append(100 if ema20 >= ema50 else 0)
        chips.append("EMA20 above EMA50" if ema20 >= ema50 else "EMA20 below EMA50")
    if ema50_slope is not None:
        if ema50_slope > 0.20:
            trend_checks.append(100)
            chips.append("EMA50 rising")
        elif ema50_slope < -0.20:
            trend_checks.append(0)
            chips.append("EMA50 falling")
        else:
            trend_checks.append(50)
            chips.append("EMA50 flat")
    trend_score = sum(trend_checks) / len(trend_checks) if trend_checks else 50

    # 2) Momentum: 25%
    momentum_parts = []
    if rsi is not None:
        if 55 <= rsi <= 70:
            momentum_parts.append(90)
            chips.append(f"RSI {rsi:.1f}: bullish")
        elif 50 <= rsi < 55:
            momentum_parts.append(65)
            chips.append(f"RSI {rsi:.1f}: slightly bullish")
        elif 45 <= rsi < 50:
            momentum_parts.append(45)
            chips.append(f"RSI {rsi:.1f}: slightly weak")
        elif 30 <= rsi < 45:
            momentum_parts.append(25)
            chips.append(f"RSI {rsi:.1f}: weak")
        elif rsi > 75:
            momentum_parts.append(55)
            chips.append(f"RSI {rsi:.1f}: overextended")
        elif rsi < 30:
            momentum_parts.append(20)
            chips.append(f"RSI {rsi:.1f}: oversold")
        else:
            momentum_parts.append(50)
            chips.append(f"RSI {rsi:.1f}: neutral")
    if mh is not None:
        if mh > 0 and (mh_change is None or mh_change >= 0):
            momentum_parts.append(90)
            chips.append("MACD positive/rising")
        elif mh > 0:
            momentum_parts.append(70)
            chips.append("MACD positive but weakening")
        elif mh <= 0 and mh_change is not None and mh_change > 0:
            momentum_parts.append(45)
            chips.append("MACD negative but improving")
        else:
            momentum_parts.append(20)
            chips.append("MACD negative")
    momentum_score = sum(momentum_parts) / len(momentum_parts) if momentum_parts else 50

    # 3) Price Strength: 20%
    strength_parts = []
    if ret5 is not None:
        if ret5 >= 3:
            strength_parts.append(85)
            chips.append(f"5D return +{ret5:.1f}%")
        elif ret5 >= 0.5:
            strength_parts.append(70)
            chips.append(f"5D return +{ret5:.1f}%")
        elif ret5 <= -3:
            strength_parts.append(15)
            chips.append(f"5D return {ret5:.1f}%")
        elif ret5 <= -0.5:
            strength_parts.append(35)
            chips.append(f"5D return {ret5:.1f}%")
        else:
            strength_parts.append(50)
            chips.append(f"5D return {ret5:.1f}%")
    if dist20 is not None:
        ad = abs(dist20)
        if 0 <= dist20 <= 4:
            strength_parts.append(80)
        elif dist20 > 8:
            strength_parts.append(55)  # strong but extended
            chips.append("Extended above EMA20")
        elif dist20 < -4:
            strength_parts.append(25)
        else:
            strength_parts.append(50)
    if dist50 is not None:
        if 0 <= dist50 <= 8:
            strength_parts.append(75)
        elif dist50 > 15:
            strength_parts.append(55)
            chips.append("Extended above EMA50")
        elif dist50 < -6:
            strength_parts.append(20)
        else:
            strength_parts.append(45)
    strength_score = sum(strength_parts) / len(strength_parts) if strength_parts else 50

    # 4) Volatility / Risk Context: 15%
    vol_parts = []
    if atr_pct is not None:
        if atr_pct <= 1.5:
            vol_parts.append(80)
            chips.append(f"ATR {atr_pct:.1f}%: calm")
        elif atr_pct <= 3.5:
            vol_parts.append(60)
            chips.append(f"ATR {atr_pct:.1f}%: normal")
        elif atr_pct <= 6:
            vol_parts.append(40)
            chips.append(f"ATR {atr_pct:.1f}%: elevated")
        else:
            vol_parts.append(20)
            chips.append(f"ATR {atr_pct:.1f}%: high risk")
    else:
        vol_parts.append(50)
    volatility_score = sum(vol_parts) / len(vol_parts)

    components = [
        _component("Trend Structure", trend_score, 40, "Price vs EMA20/EMA50, EMA20 vs EMA50, and EMA50 slope."),
        _component("Momentum", momentum_score, 25, "RSI range plus MACD histogram level and direction."),
        _component("Price Strength", strength_score, 20, "Recent return and distance from EMA20/EMA50."),
        _component("Volatility Context", volatility_score, 15, "ATR percentage and whether recent movement is calm, normal, or elevated."),
    ]
    score = max(0, min(100, round(sum(c["points"] for c in components))))

    if score >= 70:
        signal = "bullish"
    elif score <= 40:
        signal = "bearish"
    else:
        signal = "neutral"

    if not reasons:
        reasons = ["Technical data is mixed or incomplete."]
    return {
        "signal": signal,
        "score": score,
        "components": components,
        "reasons": reasons[:6],
        "chips": chips[:10],
        "summary": "Technical Signal uses trend structure, momentum, price strength, and volatility context. It is rule-based and not investment advice.",
        "technicals": t
    }


def search_symbols(query):
    q = (query or "").strip()
    if not q:
        return []

    def _load():
        results = []
        try:
            data = _finnhub_get("/search", {"q": q})
            rows = data.get("result") or []
            for x in rows[:12]:
                sym = x.get("symbol") or x.get("displaySymbol")
                if not sym:
                    continue
                results.append({
                    "symbol": str(sym).upper(),
                    "name": x.get("description") or str(sym).upper(),
                    "exchange": None,
                    "type": x.get("type"),
                    "source": "Finnhub",
                })
        except Exception:
            results = []

        if results:
            return results[:10]

        try:
            s = yf.Search(q, max_results=10, news_count=0)
            quotes = getattr(s, "quotes", None) or []
            return [
                {"symbol": x.get("symbol"), "name": x.get("shortname") or x.get("longname"), "exchange": x.get("exchange"), "source": "Yahoo fallback"}
                for x in quotes if x.get("symbol")
            ]
        except Exception:
            return [{"symbol": q.upper(), "name": q.upper(), "exchange": None, "source": "typed"}]

    return _cache_fetch(f"search:v49:{q.lower()}", 60*60*24*7, _load, stale_grace_seconds=60*60*24*30)


def bulk_snapshot(symbols):
    out = []
    for s in symbols[:25]:
        try:
            q = quote(s)
            a = analyze_stock(s)
            out.append({
                **q,
                "signal": a["signal"],
                "score": a["score"],
                "rsi": a["technicals"].get("rsi14"),
                "ema20": a["technicals"].get("ema20"),
                "ema50": a["technicals"].get("ema50")
            })
        except Exception as e:
            out.append({"symbol": s.upper(), "error": str(e)})
    return out
