from __future__ import annotations
import math
from datetime import datetime, timezone
import yfinance as yf

SQRT_2 = math.sqrt(2.0)

def _cdf(x): return 0.5 * (1.0 + math.erf(x / SQRT_2))
def _pdf(x): return math.exp(-0.5*x*x) / math.sqrt(2*math.pi)

def bs_greeks(spot, strike, years, rate, iv, kind):
    """Black-Scholes estimates. Theta is per calendar day; vega/rho are per 1 percentage point."""
    try:
        spot, strike, years, rate, iv = map(float, (spot, strike, years, rate, iv))
    except (TypeError, ValueError):
        return {}
    if spot <= 0 or strike <= 0 or years <= 0 or iv <= 0:
        return {}
    rt = math.sqrt(years)
    disc = math.exp(-rate * years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * years) / (iv * rt)
    d2 = d1 - iv * rt
    gamma = _pdf(d1) / (spot * iv * rt)
    vega = spot * _pdf(d1) * rt / 100.0
    if kind == "call":
        delta = _cdf(d1)
        theta = (-(spot * _pdf(d1) * iv) / (2 * rt) - rate * strike * disc * _cdf(d2)) / 365.0
        rho = strike * years * disc * _cdf(d2) / 100.0
    else:
        delta = _cdf(d1) - 1
        theta = (-(spot * _pdf(d1) * iv) / (2 * rt) + rate * strike * disc * _cdf(-d2)) / 365.0
        rho = -strike * years * disc * _cdf(-d2) / 100.0
    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}

def expirations(symbol):
    return list(yf.Ticker(symbol.upper()).options)

def dte_for(expiration):
    exp_dt = datetime.strptime(expiration, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return max((exp_dt.date() - datetime.now(timezone.utc).date()).days, 0)

def expirations_in_dte(symbol, min_dte=None, max_dte=None, limit=8):
    exps = expirations(symbol)
    selected = []
    for exp in exps:
        dte = dte_for(exp)
        if min_dte is not None and dte < min_dte:
            continue
        if max_dte is not None and dte > max_dte:
            continue
        selected.append(exp)
        if len(selected) >= limit:
            break
    return selected

def _spot(ticker):
    try:
        p = ticker.fast_info.get("last_price")
        if p:
            return float(p)
    except Exception:
        pass
    hist = ticker.history(period="1d", interval="1m")
    if not hist.empty:
        return float(hist["Close"].dropna().iloc[-1])
    raise RuntimeError("Unable to load underlying price")

def option_chain(symbol, expiration, risk_free_rate=0.043):
    symbol = symbol.upper()
    ticker = yf.Ticker(symbol)
    spot = _spot(ticker)
    chain = ticker.option_chain(expiration)
    dte = dte_for(expiration)
    years = max(dte / 365.0, 1 / 365.0)

    def convert(df, kind):
        rows = []
        for _, r in df.iterrows():
            bid = _num(r.get("bid"))
            ask = _num(r.get("ask"))
            last = _num(r.get("lastPrice"))
            strike = _num(r.get("strike"))
            iv = _num(r.get("impliedVolatility"))
            mid = (bid + ask) / 2 if bid is not None and ask is not None else last
            width = (ask - bid) if bid is not None and ask is not None else None
            greeks = bs_greeks(spot, strike, years, risk_free_rate, iv, kind) if iv else {}
            rows.append({
                "contract": str(r.get("contractSymbol", "")),
                "type": kind,
                "strike": strike,
                "bid": bid,
                "ask": ask,
                "last": last,
                "mid": mid,
                "spread_width": width,
                "volume": _int(r.get("volume")),
                "open_interest": _int(r.get("openInterest")),
                "iv": iv,
                "in_the_money": bool(r.get("inTheMoney", False)),
                **greeks,
            })
        return rows

    return {
        "symbol": symbol,
        "spot": spot,
        "expiration": expiration,
        "dte": dte,
        "risk_free_rate": risk_free_rate,
        "calls": convert(chain.calls, "call"),
        "puts": convert(chain.puts, "put"),
    }

def technical_snapshot(symbol):
    """Simple daily trend snapshot from Yahoo history. Not a prediction."""
    ticker = yf.Ticker(symbol.upper())
    h = ticker.history(period="6mo", interval="1d", auto_adjust=False)
    if h is None or h.empty or len(h) < 55:
        return {"status": "unknown", "score": 0, "signals": [], "reason": "Insufficient price history"}

    close = h["Close"].dropna()
    if len(close) < 55:
        return {"status": "unknown", "score": 0, "signals": [], "reason": "Insufficient price history"}

    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal

    price = float(close.iloc[-1])
    e20 = float(ema20.iloc[-1])
    e50 = float(ema50.iloc[-1])
    rsi_v = float(rsi.iloc[-1]) if not math.isnan(float(rsi.iloc[-1])) else None
    macd_hist = float(hist.iloc[-1])

    bullish = 0
    bearish = 0
    signals = []

    if price > e20:
        bullish += 1; signals.append("Price above EMA20")
    else:
        bearish += 1; signals.append("Price below EMA20")

    if price > e50:
        bullish += 1; signals.append("Price above EMA50")
    else:
        bearish += 1; signals.append("Price below EMA50")

    if e20 > e50:
        bullish += 1; signals.append("EMA20 above EMA50")
    else:
        bearish += 1; signals.append("EMA20 below EMA50")

    if rsi_v is not None:
        if rsi_v >= 50:
            bullish += 1; signals.append(f"RSI {rsi_v:.1f} ≥ 50")
        else:
            bearish += 1; signals.append(f"RSI {rsi_v:.1f} < 50")

    if macd_hist >= 0:
        bullish += 1; signals.append("MACD histogram positive")
    else:
        bearish += 1; signals.append("MACD histogram negative")

    score = bullish - bearish
    status = "bullish" if score >= 3 else "bearish" if score <= -3 else "neutral"
    return {
        "status": status,
        "score": score,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "signals": signals,
        "price": price,
        "ema20": e20,
        "ema50": e50,
        "rsi14": rsi_v,
        "macd_histogram": macd_hist,
    }

def trend_filter_passes(technical, trend_filter):
    if not trend_filter or trend_filter == "off":
        return True
    status = technical.get("status", "unknown")
    if status == "unknown":
        return True
    if trend_filter == "avoid_bearish":
        return status != "bearish"
    if trend_filter == "avoid_bullish":
        return status != "bullish"
    if trend_filter == "bullish_only":
        return status == "bullish"
    if trend_filter == "bearish_only":
        return status == "bearish"
    return True

def _num(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return float(v)
    except Exception:
        return None

def _int(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return 0
        return int(v)
    except Exception:
        return 0

def _leg(c, action, price):
    return {
        "action": action,
        "type": c["type"],
        "contract": c.get("contract"),
        "strike": c["strike"],
        "price": price,
        "bid": c.get("bid"),
        "ask": c.get("ask"),
        "mid": c.get("mid"),
        "last": c.get("last"),
        "volume": c.get("volume", 0),
        "open_interest": c.get("open_interest", 0),
        "iv": c.get("iv"),
        "delta": c.get("delta"),
        "gamma": c.get("gamma"),
        "theta": c.get("theta"),
        "vega": c.get("vega"),
        "rho": c.get("rho"),
    }

def _position_greeks(legs):
    out = {k: 0.0 for k in ("delta", "gamma", "theta", "vega", "rho")}
    available = False
    for l in legs:
        sign = 1 if l["action"] == "buy" else -1
        for k in out:
            v = l.get(k)
            if v is not None:
                out[k] += sign * float(v) * 100
                available = True
    return out if available else {}

def build_single_candidates(chain, action, kind, filters):
    contracts = chain["calls"] if kind == "call" else chain["puts"]
    out = []
    for c in contracts:
        if not _contract_passes(c, filters):
            continue
        price = c.get("ask") if action == "buy" else c.get("bid")
        if price is None or price <= 0:
            continue
        if action == "buy" and filters.get("max_debit") is not None and price > filters["max_debit"]:
            continue
        if action == "sell" and filters.get("min_credit") is not None and price < filters["min_credit"]:
            continue

        legs = [_leg(c, action, price)]
        item = dict(c)
        item.update({
            "strategy": filters.get("display_strategy") or f"{action}_{kind}",
            "bias": "bullish" if (action, kind) in [("buy", "call"), ("sell", "put")] else "bearish",
            "legs": legs,
            "position_greeks": _position_greeks(legs),
            "net_premium": -price if action == "buy" else price,
            "max_profit": None,
            "max_loss": price * 100 if action == "buy" else None,
            "breakeven": c["strike"] + price if kind == "call" else c["strike"] - price,
            "ror": None,
            "expiration": chain["expiration"],
            "dte": chain["dte"],
        })
        if filters.get("max_loss") is not None and item.get("max_loss") is not None and item["max_loss"] > filters["max_loss"]:
            continue
        out.append(item)
    return out[:200]

def build_vertical_candidates(chain, strategy, filters):
    aliases = {"bull_call": "call_debit", "bear_call": "call_credit", "bull_put": "put_credit", "bear_put": "put_debit"}
    strategy = aliases.get(strategy, strategy)
    contracts = chain["calls"] if strategy.startswith("call_") else chain["puts"]
    valid = [c for c in contracts if _contract_passes(c, filters)]
    out = []

    max_width = filters.get("max_width")
    target_width = filters.get("spread_width")

    for i, a in enumerate(valid):
        for b in valid[i+1:]:
            low, high = (a, b) if a["strike"] < b["strike"] else (b, a)
            width = high["strike"] - low["strike"]
            if width <= 0:
                continue
            if target_width is not None and abs(width - target_width) > 0.001:
                continue
            if target_width is None and max_width is not None and width > max_width:
                continue

            if strategy == "call_debit":
                buy, sell = low, high
                debit = _ask(buy) - _bid(sell)
                if debit <= 0: continue
                net = -debit
                max_profit = (width - debit) * 100
                max_loss = debit * 100
                breakeven = buy["strike"] + debit
                bias = "bullish"
            elif strategy == "put_debit":
                buy, sell = high, low
                debit = _ask(buy) - _bid(sell)
                if debit <= 0: continue
                net = -debit
                max_profit = (width - debit) * 100
                max_loss = debit * 100
                breakeven = buy["strike"] - debit
                bias = "bearish"
            elif strategy == "call_credit":
                sell, buy = low, high
                credit = _bid(sell) - _ask(buy)
                if credit <= 0: continue
                net = credit
                max_profit = credit * 100
                max_loss = (width - credit) * 100
                breakeven = sell["strike"] + credit
                bias = "bearish"
            else:  # put credit
                buy, sell = low, high
                credit = _bid(sell) - _ask(buy)
                if credit <= 0: continue
                net = credit
                max_profit = credit * 100
                max_loss = (width - credit) * 100
                breakeven = sell["strike"] - credit
                bias = "bullish"

            ror = max_profit / max_loss * 100 if max_loss > 0 else None
            if filters.get("min_ror") is not None and (ror is None or ror < filters["min_ror"]):
                continue
            if net >= 0 and filters.get("min_credit") is not None and net < filters["min_credit"]:
                continue
            if net < 0 and filters.get("max_debit") is not None and abs(net) > filters["max_debit"]:
                continue
            if filters.get("max_loss") is not None and max_loss > filters["max_loss"]:
                continue

            legs = [_leg(buy, "buy", _ask(buy)), _leg(sell, "sell", _bid(sell))]
            out.append({
                "strategy": strategy,
                "bias": bias,
                "short_delta": sell.get("delta"),
                "iv": sell.get("iv"),
                "volume": min(buy.get("volume", 0), sell.get("volume", 0)),
                "open_interest": min(buy.get("open_interest", 0), sell.get("open_interest", 0)),
                "spread_width": width,
                "net_premium": net,
                "max_profit": max_profit,
                "max_loss": max_loss,
                "breakeven": breakeven,
                "ror": ror,
                "legs": legs,
                "position_greeks": _position_greeks(legs),
                "expiration": chain["expiration"],
                "dte": chain["dte"],
            })

    out.sort(key=lambda x: (x.get("ror") or -999), reverse=True)
    return out[:250]

def _ask(c):
    return float(c.get("ask") or c.get("mid") or c.get("last") or 0)

def _bid(c):
    return float(c.get("bid") or c.get("mid") or c.get("last") or 0)

def _contract_passes(c, f):
    delta = c.get("delta")
    iv = c.get("iv")
    if f.get("min_delta") is not None and (delta is None or abs(delta) < f["min_delta"]):
        return False
    if f.get("max_delta") is not None and (delta is None or abs(delta) > f["max_delta"]):
        return False
    if f.get("min_iv") is not None and (iv is None or iv * 100 < f["min_iv"]):
        return False
    if c.get("open_interest", 0) < f.get("min_oi", 0):
        return False
    if c.get("volume", 0) < f.get("min_volume", 0):
        return False
    if f.get("max_bid_ask") is not None:
        w = c.get("spread_width")
        if w is None or w > f["max_bid_ask"]:
            return False
    return True

def payoff(legs, low_price, high_price, points=121):
    if high_price <= low_price:
        high_price = low_price + 1
    step = (high_price - low_price) / (points - 1)
    data = []
    for i in range(points):
        s = low_price + i * step
        pnl = 0.0
        for leg in legs:
            mult = 1 if leg["action"] == "buy" else -1
            strike = float(leg["strike"])
            premium = float(leg["price"])
            intrinsic = max(s - strike, 0) if leg["type"] == "call" else max(strike - s, 0)
            pnl += mult * (intrinsic - premium) * 100
        data.append({"price": round(s, 2), "pnl": round(pnl, 2)})
    return data
