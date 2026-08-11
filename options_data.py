from __future__ import annotations
import math
import time
from datetime import datetime, timezone
from threading import Lock
import yfinance as yf

SQRT_2 = math.sqrt(2.0)
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
    s = symbol.upper()
    return _cache_fetch(
        f"options:expirations:{s}",
        900,
        lambda: list(yf.Ticker(s).options),
        stale_grace_seconds=86400,
    )


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

    def _load():
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
                mid = (bid + ask) / 2 if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid else last
                width = (ask - bid) if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid else None
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
                    "open_interest": _int_or_none(r.get("openInterest")),
                    "open_interest_available": _int_or_none(r.get("openInterest")) is not None,
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

    return _cache_fetch(
        f"options:chain:{symbol}:{expiration}",
        120,
        _load,
        stale_grace_seconds=1800,
    )


def technical_snapshot(symbol):
    """Simple daily trend snapshot from Yahoo history. Not a prediction."""
    s = symbol.upper()

    def _load():
        ticker = yf.Ticker(s)
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

    return _cache_fetch(f"options:technical_snapshot:{s}", 600, _load, stale_grace_seconds=86400)
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


def _int_or_none(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return int(v)
    except Exception:
        return None


def _trade_price(c, action):
    """Prefer live bid/ask, but fall back to mid/last when Yahoo returns zero quotes."""
    bid = _num(c.get("bid"))
    ask = _num(c.get("ask"))
    mid = _num(c.get("mid"))
    last = _num(c.get("last"))
    if action == "buy":
        for x in (ask, mid, last):
            if x is not None and x > 0:
                return x
    else:
        for x in (bid, mid, last):
            if x is not None and x > 0:
                return x
    return None


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

def _risk_profile(f):
    return (f.get("risk_profile") or "balanced").lower()


def _profile_delta_bounds(strategy, profile):
    """Default key-leg delta bands for showing relevant contracts near the stock price."""
    p = (profile or "balanced").lower()
    long_like = strategy in ("buy_call", "buy_put", "call_debit", "put_debit")
    short_like = strategy in ("sell_put", "cash_secured_put", "sell_call", "covered_call", "put_credit", "call_credit")
    if long_like:
        return {
            "conservative": (0.55, 0.85),
            "balanced": (0.30, 0.60),
            "aggressive": (0.12, 0.35),
        }.get(p, (0.30, 0.60))
    if short_like:
        return {
            "conservative": (0.05, 0.18),
            "balanced": (0.12, 0.30),
            "aggressive": (0.25, 0.45),
        }.get(p, (0.12, 0.30))
    return (0.10, 0.60)


def _profile_strike_bounds(strategy, profile, spot):
    """Loose hard strike relevance bounds. Keeps results near spot without deleting valid Yahoo chains."""
    if not spot:
        return None, None
    p = (profile or "balanced").lower()
    s = float(spot)

    # These are intentionally loose; profile preference happens in ranking/scoring.
    if strategy in ("buy_call", "call_debit"):
        bands = {
            "conservative": (0.90, 1.10),
            "balanced": (0.90, 1.18),
            "aggressive": (0.92, 1.28),
        }.get(p, (0.90, 1.18))
    elif strategy in ("sell_put", "cash_secured_put", "put_credit"):
        bands = {
            "conservative": (0.78, 1.00),
            "balanced": (0.82, 1.02),
            "aggressive": (0.88, 1.05),
        }.get(p, (0.82, 1.02))
    elif strategy in ("buy_put", "put_debit"):
        bands = {
            "conservative": (0.90, 1.12),
            "balanced": (0.82, 1.08),
            "aggressive": (0.72, 1.04),
        }.get(p, (0.82, 1.08))
    elif strategy in ("sell_call", "covered_call", "call_credit"):
        bands = {
            "conservative": (1.00, 1.22),
            "balanced": (0.98, 1.18),
            "aggressive": (0.95, 1.12),
        }.get(p, (0.98, 1.18))
    else:
        bands = (0.75, 1.25)
    return s * bands[0], s * bands[1]


def _default_max_width(spot, profile):
    if not spot:
        return 5.0
    s = float(spot)
    p = (profile or "balanced").lower()
    if s < 50:
        base = 2.5
    elif s < 150:
        base = 5.0
    elif s < 500:
        base = 10.0
    else:
        base = 25.0
    if p == "conservative":
        return base * 0.5
    if p == "aggressive":
        return base * 1.5
    return base


def _has_quote(c):
    bid = _num(c.get("bid")); ask = _num(c.get("ask"))
    return bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid


def _has_any_activity(c):
    oi = _num(c.get("open_interest"))
    vol = _num(c.get("volume")) or 0
    # If Yahoo returns missing/zero OI, volume or a usable quote is enough to keep it from being hidden.
    return (oi is not None and oi > 0) or vol > 0 or _has_quote(c)


def _profile_delta_passes(c, strategy, f):
    # Only user-entered delta filters are hard filters. Risk profile should rank/prefer, not wipe out Yahoo chains.
    delta = c.get("delta")
    lo = f.get("min_delta")
    hi = f.get("max_delta")
    if lo is None and hi is None:
        return True
    if delta is None:
        return True
    abs_delta = abs(delta)
    if lo is not None and abs_delta < lo:
        return False
    if hi is not None and abs_delta > hi:
        return False
    return True


def _profile_strike_passes(c, strategy, f, spot):
    lo, hi = _profile_strike_bounds(strategy, _risk_profile(f), spot)
    strike = c.get("strike")
    if strike is None or lo is None or hi is None:
        return True
    return lo <= strike <= hi


def _row_short_strike(row):
    for leg in row.get("legs") or []:
        if leg.get("action") == "sell":
            return float(leg.get("strike") or 0)
    return float(row.get("strike") or 0)


def _row_long_strike(row):
    for leg in row.get("legs") or []:
        if leg.get("action") == "buy":
            return float(leg.get("strike") or 0)
    return float(row.get("strike") or 0)


def _target_delta_for_sort(strategy, profile):
    lo, hi = _profile_delta_bounds(strategy, profile)
    return (lo + hi) / 2.0

def _distance_pct(strike, spot):
    try:
        if not spot:
            return 0.0
        return abs(float(strike) - float(spot)) / float(spot)
    except Exception:
        return 0.0

def _natural_sort_key(row, spot):
    strategy = row.get("strategy") or ""
    profile = row.get("risk_profile") or "balanced"
    short = _row_short_strike(row)
    long = _row_long_strike(row)
    strike = float(row.get("strike") or short or long or 0)
    key_strike = short or strike
    delta = row.get("short_delta")
    if delta is None:
        delta = row.get("delta")
    target_delta = _target_delta_for_sort(strategy, profile)
    delta_penalty = abs(abs(delta) - target_delta) if delta is not None else 0.15
    spot_penalty = _distance_pct(key_strike, spot)
    # For puts, show strikes nearest to spot first, then march down. For calls, march up.
    put_side = strategy in ("sell_put", "cash_secured_put", "put_credit", "buy_put", "put_debit")
    return (
        row.get("expiration") or "",
        round(delta_penalty, 4),
        round(spot_penalty, 4),
        -(key_strike) if put_side else key_strike,
        -long if put_side else long
    )


def build_single_candidates(chain, action, kind, filters):
    contracts = sorted(chain["calls"] if kind == "call" else chain["puts"], key=lambda x: float(x.get("strike") or 0))
    spot = chain.get("spot")
    strategy_name = filters.get("display_strategy") or f"{action}_{kind}"
    out = []
    for c in contracts:
        if not _profile_strike_passes(c, strategy_name, filters, spot):
            continue
        if not _profile_delta_passes(c, strategy_name, filters):
            continue
        if not _contract_passes(c, filters, check_delta=False):
            continue
        if not _has_any_activity(c):
            continue
        price = _trade_price(c, action)
        if price is None or price <= 0:
            continue
        if action == "buy" and filters.get("max_debit") is not None and price > filters["max_debit"]:
            continue
        if action == "sell" and filters.get("min_credit") is not None and price < filters["min_credit"]:
            continue

        legs = [_leg(c, action, price)]
        item = dict(c)
        item.update({
            "strategy": strategy_name,
            "bias": "bullish" if (action, kind) in [("buy", "call"), ("sell", "put")] else "bearish",
            "risk_profile": _risk_profile(filters),
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
    out.sort(key=lambda x: _natural_sort_key(x, spot))
    return out[:200]

def build_vertical_candidates(chain, strategy, filters):
    aliases = {"bull_call": "call_debit", "bear_call": "call_credit", "bull_put": "put_credit", "bear_put": "put_debit"}
    strategy = aliases.get(strategy, strategy)
    spot = chain.get("spot")
    contracts = sorted(chain["calls"] if strategy.startswith("call_") else chain["puts"], key=lambda x: float(x.get("strike") or 0))

    # Keep contracts with any usable activity/price. Yahoo often returns partial bid/ask; scoring will flag weak data.
    valid = [c for c in contracts if _contract_passes(c, filters, check_delta=False, check_iv=False) and _has_any_activity(c) and (_trade_price(c, "buy") is not None or _trade_price(c, "sell") is not None)]
    out = []

    max_width = filters.get("max_width")
    target_width = filters.get("spread_width")
    if target_width is None and max_width is None:
        max_width = _default_max_width(spot, _risk_profile(filters))

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
                key_leg = buy
                debit = _ask(buy) - _bid(sell)
                if debit <= 0: continue
                net = -debit
                max_profit = (width - debit) * 100
                max_loss = debit * 100
                breakeven = buy["strike"] + debit
                bias = "bullish"
            elif strategy == "put_debit":
                buy, sell = high, low
                key_leg = buy
                debit = _ask(buy) - _bid(sell)
                if debit <= 0: continue
                net = -debit
                max_profit = (width - debit) * 100
                max_loss = debit * 100
                breakeven = buy["strike"] - debit
                bias = "bearish"
            elif strategy == "call_credit":
                sell, buy = low, high
                key_leg = sell
                credit = _bid(sell) - _ask(buy)
                if credit <= 0: continue
                if credit >= width * 0.85: continue
                net = credit
                max_profit = credit * 100
                max_loss = (width - credit) * 100
                breakeven = sell["strike"] + credit
                bias = "bearish"
            else:  # put_credit
                buy, sell = low, high
                key_leg = sell
                credit = _bid(sell) - _ask(buy)
                if credit <= 0: continue
                if credit >= width * 0.85: continue
                net = credit
                max_profit = credit * 100
                max_loss = (width - credit) * 100
                breakeven = sell["strike"] - credit
                bias = "bullish"

            if not _profile_strike_passes(key_leg, strategy, filters, spot):
                continue
            if not _profile_delta_passes(key_leg, strategy, filters):
                continue
            if not _short_leg_passes(sell, filters, check_delta=False):
                continue

            ror = max_profit / max_loss * 100 if max_loss > 0 else None
            if strategy in ("put_credit", "call_credit"):
                # Default should not wipe out Yahoo chains. Exclude only clearly unusable/fake credits.
                if net <= 0:
                    continue
                if net >= width * 0.85:
                    continue

            if filters.get("min_ror") is not None and (ror is None or ror < filters["min_ror"]):
                continue
            if net >= 0 and filters.get("min_credit") is not None and net < filters["min_credit"]:
                continue
            if net < 0 and filters.get("max_debit") is not None and abs(net) > filters["max_debit"]:
                continue
            if filters.get("max_loss") is not None and max_loss > filters["max_loss"]:
                continue
            if max_profit is not None and max_profit <= 0:
                continue
            if max_loss is not None and max_loss <= 0:
                continue

            legs = [_leg(buy, "buy", _ask(buy)), _leg(sell, "sell", _bid(sell))]
            oi_vals = [x.get("open_interest") for x in (buy, sell) if x.get("open_interest") is not None and x.get("open_interest") > 0]
            out.append({
                "strategy": strategy,
                "bias": bias,
                "short_delta": sell.get("delta"),
                "iv": sell.get("iv"),
                "volume": min(buy.get("volume", 0), sell.get("volume", 0)),
                "open_interest": min(oi_vals) if oi_vals else None,
                "spread_width": width,
                "risk_profile": _risk_profile(filters),
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

    out.sort(key=lambda x: _natural_sort_key(x, spot))
    return out[:250]

def _ask(c):
    for x in (_num(c.get("ask")), _num(c.get("mid")), _num(c.get("last"))):
        if x is not None and x > 0:
            return float(x)
    return 0.0

def _bid(c):
    for x in (_num(c.get("bid")), _num(c.get("mid")), _num(c.get("last"))):
        if x is not None and x > 0:
            return float(x)
    return 0.0

def _contract_passes(c, f, check_delta=True, check_iv=True):
    delta = c.get("delta")
    iv = c.get("iv")
    if check_delta:
        if f.get("min_delta") is not None and (delta is None or abs(delta) < f["min_delta"]):
            return False
        if f.get("max_delta") is not None and (delta is None or abs(delta) > f["max_delta"]):
            return False
    if check_iv:
        if f.get("min_iv") is not None and (iv is None or iv * 100 < f["min_iv"]):
            return False
    min_oi = f.get("min_oi", 0) or 0
    oi = c.get("open_interest")
    if min_oi > 0 and (oi is None or oi < min_oi):
        return False
    if c.get("volume", 0) < f.get("min_volume", 0):
        return False
    if f.get("max_bid_ask") is not None:
        w = c.get("spread_width")
        if w is None or w > f["max_bid_ask"]:
            return False
    return True

def _short_leg_passes(c, f, check_delta=True):
    """For vertical spreads, manual delta/IV filters describe the short leg."""
    delta = c.get("delta")
    iv = c.get("iv")
    if check_delta:
        if f.get("min_delta") is not None and (delta is None or abs(delta) < f["min_delta"]):
            return False
        if f.get("max_delta") is not None and (delta is None or abs(delta) > f["max_delta"]):
            return False
    if f.get("min_iv") is not None and (iv is None or iv * 100 < f["min_iv"]):
        return False
    return True





def _quality_leg(candidate, prefer_short=True):
    legs = candidate.get("legs") or []
    if prefer_short:
        for leg in legs:
            if leg.get("action") == "sell":
                return leg
    return legs[0] if legs else candidate


def _quality_short_leg(candidate):
    for leg in candidate.get("legs") or []:
        if leg.get("action") == "sell":
            return leg
    return candidate


def _quality_long_leg(candidate):
    for leg in candidate.get("legs") or []:
        if leg.get("action") == "buy":
            return leg
    return _quality_leg(candidate, prefer_short=False)


def _quality_grade_payload(grade, points, reason, weight=0, **extra):
    points = max(0, min(10, float(points)))
    out = {
        "grade": grade,
        "points": int(round(points)),
        "max_points": 10,
        "weight": int(weight or 0),
        "weighted_points": round((points / 10.0) * float(weight or 0), 2),
        "reason": reason,
    }
    out.update(extra)
    return out


def _strategy_direction(strategy):
    strategy = strategy or ""
    if strategy in ("buy_call", "sell_put", "cash_secured_put", "call_debit", "put_credit"):
        return "bullish"
    if strategy in ("buy_put", "sell_call", "call_credit", "put_debit"):
        return "bearish"
    if strategy == "covered_call":
        return "neutral_bullish"
    return "neutral"


def _strategy_family(candidate):
    s = candidate.get("strategy") or ""
    if s in ("put_credit", "call_credit"):
        return "credit_spread"
    if s in ("call_debit", "put_debit"):
        return "debit_spread"
    if s in ("buy_call", "buy_put"):
        return "long_option"
    if s in ("sell_put", "cash_secured_put"):
        return "short_put"
    if s == "covered_call":
        return "covered_call"
    if s == "sell_call":
        return "short_call"
    return "other"


def _strategy_profile(strategy):
    profiles = {
        "buy_call": {"trend_match":25, "delta_probability":25, "risk_reward":20, "iv_suitability":15, "bid_ask":10, "liquidity":5},
        "buy_put": {"trend_match":25, "delta_probability":25, "risk_reward":20, "iv_suitability":15, "bid_ask":10, "liquidity":5},
        "sell_put": {"risk_reward":30, "delta_probability":25, "iv_suitability":15, "liquidity":15, "bid_ask":10, "trend_match":5},
        "cash_secured_put": {"risk_reward":30, "delta_probability":25, "iv_suitability":15, "liquidity":10, "bid_ask":10, "trend_match":10},
        "sell_call": {"risk_reward":30, "delta_probability":25, "iv_suitability":15, "liquidity":10, "bid_ask":10, "trend_match":10},
        "covered_call": {"risk_reward":30, "delta_probability":25, "iv_suitability":15, "trend_match":15, "bid_ask":10, "liquidity":5},
        "call_debit": {"trend_match":25, "risk_reward":25, "delta_probability":20, "iv_suitability":15, "bid_ask":10, "liquidity":5},
        "put_debit": {"trend_match":25, "risk_reward":25, "delta_probability":20, "iv_suitability":15, "bid_ask":10, "liquidity":5},
        "put_credit": {"risk_reward":30, "delta_probability":25, "iv_suitability":15, "liquidity":12, "bid_ask":10, "trend_match":8},
        "call_credit": {"risk_reward":30, "delta_probability":25, "iv_suitability":15, "liquidity":12, "bid_ask":10, "trend_match":8},
    }
    return profiles.get(strategy or "", {"risk_reward":25, "delta_probability":25, "iv_suitability":15, "trend_match":15, "liquidity":10, "bid_ask":10})


def _is_credit_strategy(candidate):
    return _strategy_family(candidate) in ("credit_spread", "short_put", "short_call", "covered_call")


def _is_long_or_debit_strategy(candidate):
    return _strategy_family(candidate) in ("long_option", "debit_spread")


def _key_leg(candidate):
    family = _strategy_family(candidate)
    if family in ("credit_spread", "short_put", "short_call", "covered_call"):
        return _quality_short_leg(candidate)
    return _quality_long_leg(candidate)


def _key_delta(candidate):
    leg = _key_leg(candidate)
    if candidate.get("short_delta") is not None and _strategy_family(candidate) in ("credit_spread", "short_put", "short_call", "covered_call"):
        return _num(candidate.get("short_delta"))
    return _num(leg.get("delta", candidate.get("delta")))


def _key_iv(candidate):
    leg = _key_leg(candidate)
    iv = _num(candidate.get("iv"))
    if iv is None:
        iv = _num(leg.get("iv"))
    return iv


def _premium(candidate):
    net = _num(candidate.get("net_premium"))
    return abs(net) if net is not None else None


def _strike_for_yield(candidate):
    leg = _key_leg(candidate)
    return _num(leg.get("strike") or candidate.get("strike"))


def _first_issue(warnings):
    if not warnings:
        return "None"
    return warnings[0]


def _risk_level_from_family_delta(candidate, abs_delta):
    family = _strategy_family(candidate)
    if abs_delta is None:
        return "Balanced"
    if family in ("long_option", "debit_spread"):
        if abs_delta < 0.10:
            return "Speculative"
        if abs_delta < 0.25:
            return "Aggressive"
        if abs_delta < 0.45:
            return "Directional"
        if abs_delta <= 0.70:
            return "Balanced"
        return "Expensive"
    if family in ("credit_spread", "short_put", "short_call", "covered_call"):
        if abs_delta < 0.05:
            return "Low Reward"
        if abs_delta <= 0.15:
            return "Conservative"
        if abs_delta <= 0.30:
            return "Balanced"
        if abs_delta <= 0.45:
            return "Aggressive"
        return "High Risk"
    return "Balanced"


def _liquidity_quality(candidate, weight=0):
    def leg_liq(leg):
        oi_raw = leg.get("open_interest", candidate.get("open_interest"))
        oi = _num(oi_raw)
        vol = _int(leg.get("volume", candidate.get("volume")))
        bid = _num(leg.get("bid", candidate.get("bid")))
        ask = _num(leg.get("ask", candidate.get("ask")))
        has_quote = bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid
        if oi is None or oi <= 0:
            if vol >= 100 and has_quote:
                return 6, "Unknown", None, vol, "Open interest is unavailable from Yahoo, but volume and quotes are active."
            if vol > 0 and has_quote:
                return 5, "Unknown", None, vol, "Open interest is unavailable from Yahoo; volume exists, so confirm liquidity with broker."
            if has_quote:
                return 4, "Unknown", None, vol, "Open interest is unavailable from Yahoo; confirm liquidity with broker."
            return 2, "Poor", None, vol, "Liquidity is weak or unavailable: no OI, volume, or usable quote."
        oi = int(oi)
        if has_quote and oi >= 1000 and vol >= 100:
            return 10, "Excellent", oi, vol, f"Strong liquidity: {oi:,} open interest and {vol:,} volume on the key leg."
        if has_quote and oi >= 500 and vol >= 50:
            return 8, "Good", oi, vol, f"Good liquidity: {oi:,} open interest and {vol:,} volume on the key leg."
        if has_quote and oi >= 150 and vol >= 10:
            return 6, "OK", oi, vol, f"Usable liquidity: {oi:,} open interest and {vol:,} volume on the key leg."
        if has_quote and oi >= 50:
            return 4, "Weak", oi, vol, f"Thin liquidity: {oi:,} open interest and {vol:,} volume on the key leg."
        return 2, "Poor", oi, vol, f"Poor liquidity: {oi:,} open interest and {vol:,} volume on the key leg."

    legs = candidate.get("legs") or []
    checks = [leg_liq(leg) for leg in legs] if legs else [leg_liq(_key_leg(candidate))]
    points, grade, oi, vol, reason = min(checks, key=lambda x: x[0])
    return _quality_grade_payload(grade, points, reason, weight=weight, open_interest=oi, volume=vol)


def _bid_ask_quality_for_leg(leg):
    bid = _num(leg.get("bid"))
    ask = _num(leg.get("ask"))
    mid = _num(leg.get("mid"))
    if mid is None and bid is not None and ask is not None:
        mid = (bid + ask) / 2
    if bid is None or ask is None or bid <= 0 or ask <= 0 or ask < bid or not mid:
        return {"grade": "Poor", "points": 1, "width": None, "pct": None, "reason": "Missing or unusable bid/ask spread."}
    width = ask - bid
    pct = width / mid if mid else None
    if width <= 0.03 or (pct is not None and pct <= 0.05):
        return {"grade": "Excellent", "points": 10, "width": width, "pct": pct, "reason": f"Very tight bid/ask spread of ${width:.2f}."}
    if width <= 0.07 or (pct is not None and pct <= 0.12):
        return {"grade": "Good", "points": 8, "width": width, "pct": pct, "reason": f"Tight bid/ask spread of ${width:.2f}."}
    if width <= 0.15 or (pct is not None and pct <= 0.25):
        return {"grade": "OK", "points": 6, "width": width, "pct": pct, "reason": f"Acceptable bid/ask spread of ${width:.2f}, but not very tight."}
    if width <= 0.30 or (pct is not None and pct <= 0.45):
        return {"grade": "Weak", "points": 3, "width": width, "pct": pct, "reason": f"Wide bid/ask spread of ${width:.2f}."}
    return {"grade": "Poor", "points": 1, "width": width, "pct": pct, "reason": f"Very wide bid/ask spread of ${width:.2f}."}


def _bid_ask_quality(candidate, weight=0):
    legs = candidate.get("legs") or []
    if not legs:
        result = _bid_ask_quality_for_leg(candidate)
    else:
        checks = [_bid_ask_quality_for_leg(leg) for leg in legs]
        result = min(checks, key=lambda x: x.get("points", 0))
    return _quality_grade_payload(
        result["grade"], result["points"], result["reason"],
        weight=weight, width=result.get("width"), pct=result.get("pct")
    )


def _delta_probability_quality(candidate, weight=0):
    family = _strategy_family(candidate)
    delta = _key_delta(candidate)
    if delta is None:
        return _quality_grade_payload("Unavailable", 3, "Delta unavailable, so probability/edge cannot be estimated.", weight=weight, delta=None, abs_delta=None, value=None, label="Probability estimate", risk_level="Balanced")
    abs_delta = abs(delta)
    risk_level = _risk_level_from_family_delta(candidate, abs_delta)

    if family in ("long_option", "debit_spread"):
        prob = max(0.0, min(1.0, abs_delta))
        label = "Approx. probability ITM"
        if 0.35 <= abs_delta <= 0.60:
            points, grade = 10, "Excellent"
        elif 0.25 <= abs_delta < 0.35 or 0.60 < abs_delta <= 0.70:
            points, grade = 7, "Good"
        elif 0.10 <= abs_delta < 0.25:
            points, grade = 3, "Weak"
        elif abs_delta < 0.10:
            points, grade = 1, "Lottery"
        else:
            points, grade = 4, "Expensive"
        reason = f"Long-leg delta is {delta:.3f}; estimated probability ITM is about {prob*100:.0f}%."
    else:
        prob = max(0.0, min(1.0, 1.0 - abs_delta))
        label = "Estimated probability of success"
        if 0.15 <= abs_delta <= 0.30:
            points, grade = 10, "Excellent"
        elif 0.05 <= abs_delta < 0.15:
            points, grade = 8, "Good"
        elif 0.30 < abs_delta <= 0.45:
            points, grade = 4, "Aggressive"
        elif abs_delta < 0.05:
            points, grade = 3, "Low Reward"
        else:
            points, grade = 1, "High Risk"
        reason = f"Short-leg delta is {delta:.3f}; estimated probability of success is about {prob*100:.0f}%."

    return _quality_grade_payload(grade, points, reason, weight=weight, delta=delta, abs_delta=abs_delta, value=round(prob*100), label=label, risk_level=risk_level)


def _iv_suitability_quality(candidate, weight=0):
    family = _strategy_family(candidate)
    iv = _key_iv(candidate)
    if iv is None:
        return _quality_grade_payload("Unavailable", 4, "IV unavailable, so volatility suitability cannot be estimated.", weight=weight, iv=None)

    iv_pct = iv * 100 if iv <= 5 else iv
    short_premium = family in ("credit_spread", "short_put", "short_call", "covered_call")

    if short_premium:
        if 35 <= iv_pct <= 70:
            points, grade = 9, "Good"
            reason = f"IV is {iv_pct:.1f}%, supportive for premium-selling strategies."
        elif 20 <= iv_pct < 35:
            points, grade = 6, "OK"
            reason = f"IV is {iv_pct:.1f}%, usable but not especially rich for selling premium."
        elif iv_pct < 20:
            points, grade = 3, "Weak"
            reason = f"IV is {iv_pct:.1f}%, so premium may be thin."
        else:
            points, grade = 6, "Elevated"
            reason = f"IV is {iv_pct:.1f}%, rich premium but higher event/move risk."
    else:
        if iv_pct < 25:
            points, grade = 9, "Good"
            reason = f"IV is {iv_pct:.1f}%, relatively favorable for buying premium."
        elif iv_pct < 40:
            points, grade = 7, "OK"
            reason = f"IV is {iv_pct:.1f}%, acceptable for long/debit strategies."
        elif iv_pct < 70:
            points, grade = 4, "Expensive"
            reason = f"IV is {iv_pct:.1f}%, making long premium more expensive."
        else:
            points, grade = 2, "Very Expensive"
            reason = f"IV is {iv_pct:.1f}%, which is very expensive for buying premium."
    return _quality_grade_payload(grade, points, reason, weight=weight, iv=iv, iv_pct=iv_pct)


def _risk_reward_quality(candidate, delta_part=None, weight=0):
    family = _strategy_family(candidate)
    ror = _num(candidate.get("ror"))
    max_loss = _num(candidate.get("max_loss"))
    max_profit = _num(candidate.get("max_profit"))
    premium = _premium(candidate)
    strike = _strike_for_yield(candidate)
    dte = max(_int(candidate.get("dte")) or 1, 1)
    abs_delta = (delta_part or {}).get("abs_delta")

    if family == "credit_spread":
        if ror is None:
            return _quality_grade_payload("Unavailable", 2, "Return on risk unavailable for this spread.", weight=weight)
        credit = _num(candidate.get("net_premium")) or 0
        width = _num(candidate.get("spread_width")) or 0
        credit_ratio = credit / width if width else None
        if ror >= 25 and (credit_ratio is None or credit_ratio >= 0.12):
            return _quality_grade_payload("Excellent", 10, f"Return on risk is {ror:.1f}% with strong credit for the spread width.", weight=weight, ror=ror, credit_ratio=credit_ratio)
        if ror >= 18 and (credit_ratio is None or credit_ratio >= 0.08):
            return _quality_grade_payload("Good", 8, f"Return on risk is {ror:.1f}%, with meaningful credit for the spread width.", weight=weight, ror=ror, credit_ratio=credit_ratio)
        if ror >= 10:
            return _quality_grade_payload("OK", 5, f"Return on risk is {ror:.1f}%, acceptable but not strong.", weight=weight, ror=ror, credit_ratio=credit_ratio)
        if ror >= 5:
            return _quality_grade_payload("Weak", 2, f"Return on risk is only {ror:.1f}%, which is low for the risk taken.", weight=weight, ror=ror, credit_ratio=credit_ratio)
        return _quality_grade_payload("Poor", 1, f"Return on risk is only {ror:.1f}%, so reward is very thin.", weight=weight, ror=ror, credit_ratio=credit_ratio)

    if family == "debit_spread":
        width = _num(candidate.get("spread_width"))
        debit = premium
        debit_ratio = debit / width if width and debit is not None else None
        reward_to_risk = max_profit / max_loss if max_profit is not None and max_loss and max_loss > 0 else None
        if abs_delta is not None and abs_delta < 0.10:
            return _quality_grade_payload("Lottery", 1, "Very low delta makes this lottery-like even if theoretical payoff is high.", weight=weight, reward_to_risk=reward_to_risk, debit_ratio=debit_ratio)
        if debit_ratio is not None and debit_ratio > 0.70:
            return _quality_grade_payload("Poor", 2, "Debit is high relative to spread width, limiting reward/risk.", weight=weight, reward_to_risk=reward_to_risk, debit_ratio=debit_ratio)
        if reward_to_risk is not None and reward_to_risk >= 1.0 and (abs_delta is None or abs_delta >= 0.30):
            return _quality_grade_payload("Good", 8, f"Reward/risk is {reward_to_risk:.1f}x with reasonable delta exposure.", weight=weight, reward_to_risk=reward_to_risk, debit_ratio=debit_ratio)
        if reward_to_risk is not None and reward_to_risk >= 0.5:
            return _quality_grade_payload("OK", 5, f"Reward/risk is {reward_to_risk:.1f}x.", weight=weight, reward_to_risk=reward_to_risk, debit_ratio=debit_ratio)
        return _quality_grade_payload("Weak", 3, "Debit spread reward/risk is weak or unavailable.", weight=weight, reward_to_risk=reward_to_risk, debit_ratio=debit_ratio)

    if family == "long_option":
        if abs_delta is None:
            return _quality_grade_payload("Speculative", 3, "Long-option risk/reward is hard to judge without delta.", weight=weight)
        if abs_delta < 0.10:
            return _quality_grade_payload("Lottery", 1, "Very low delta means tiny probability despite high theoretical upside.", weight=weight)
        if abs_delta < 0.25:
            return _quality_grade_payload("High Risk", 3, "Low delta means a higher-risk directional bet.", weight=weight)
        if abs_delta <= 0.45:
            return _quality_grade_payload("OK", 6, "Delta is usable, but still needs a strong directional move.", weight=weight)
        if abs_delta <= 0.70:
            return _quality_grade_payload("Good", 7, "Delta is in a reasonable range for a long option.", weight=weight)
        return _quality_grade_payload("Expensive", 4, "High delta behaves more stock-like and usually costs more premium.", weight=weight)

    if family in ("short_put", "covered_call", "short_call"):
        if premium is None or strike is None:
            return _quality_grade_payload("Strategy dependent", 2, "Premium yield unavailable.", weight=weight)
        premium_yield = premium / strike if strike else 0
        annualized_yield = premium_yield * (365 / dte)
        if premium < 0.10:
            return _quality_grade_payload("Poor", 1, f"Premium is only ${premium:.2f}, likely too small for the capital or assignment risk.", weight=weight, premium_yield=premium_yield, annualized_yield=annualized_yield)
        if annualized_yield >= 0.12:
            return _quality_grade_payload("Excellent", 10, f"Premium yield annualizes to about {annualized_yield*100:.1f}%.", weight=weight, premium_yield=premium_yield, annualized_yield=annualized_yield)
        if annualized_yield >= 0.08:
            return _quality_grade_payload("Good", 8, f"Premium yield annualizes to about {annualized_yield*100:.1f}%.", weight=weight, premium_yield=premium_yield, annualized_yield=annualized_yield)
        if annualized_yield >= 0.04:
            return _quality_grade_payload("OK", 5, f"Premium yield annualizes to about {annualized_yield*100:.1f}%.", weight=weight, premium_yield=premium_yield, annualized_yield=annualized_yield)
        return _quality_grade_payload("Poor", 2, f"Premium yield annualizes to only about {annualized_yield*100:.1f}%.", weight=weight, premium_yield=premium_yield, annualized_yield=annualized_yield)

    return _quality_grade_payload("Strategy dependent", 3, "Risk/reward is strategy dependent for this trade type.", weight=weight)


def _trend_match_quality(candidate, technical, weight=0):
    status = (technical or {}).get("status") or (technical or {}).get("signal") or "unknown"
    if status not in ("bullish", "bearish", "neutral"):
        status = "unknown"
    desired = _strategy_direction(candidate.get("strategy"))
    family = _strategy_family(candidate)

    if status == "unknown":
        return _quality_grade_payload("Neutral", 5, "Trend signal is unavailable, so this is not scored as aligned or misaligned.", weight=weight, trend=status, direction=desired)
    if status == "neutral":
        return _quality_grade_payload("Neutral", 6, "Stock trend is neutral, so the setup is not strongly aligned or rejected.", weight=weight, trend=status, direction=desired)

    if desired == status or (desired == "neutral_bullish" and status == "bullish") or (desired == "neutral_bearish" and status == "bearish"):
        return _quality_grade_payload("Good", 9, f"Trade direction is {desired.replace('_', '/')} and the stock trend is {status}.", weight=weight, trend=status, direction=desired)
    if family in ("short_put", "covered_call", "credit_spread") and desired.startswith("neutral"):
        return _quality_grade_payload("OK", 6, f"Trade is more neutral, while the stock trend is {status}.", weight=weight, trend=status, direction=desired)
    if desired.startswith("neutral"):
        return _quality_grade_payload("OK", 6, f"Trade is more neutral, while the stock trend is {status}.", weight=weight, trend=status, direction=desired)
    return _quality_grade_payload("Poor", 2, f"Trade direction is {desired}, but the stock trend is {status}.", weight=weight, trend=status, direction=desired)


def _dte_warning(candidate):
    dte = _int(candidate.get("dte"))
    family = _strategy_family(candidate)
    if dte is None:
        return None, None
    if dte < 4:
        return "Very short DTE", 50
    if dte < 7:
        return "Short DTE", 58
    if family in ("long_option", "debit_spread") and dte < 14:
        return "Short DTE for long/debit strategy", 65
    if dte > 180:
        return "Very far-dated expiration", 80
    return None, None


def _score_caps_and_warnings(candidate, parts):
    warnings = []
    critical = []
    cap = 100
    family = _strategy_family(candidate)
    premium = _premium(candidate)
    strike = _strike_for_yield(candidate)
    dte = max(_int(candidate.get("dte")) or 1, 1)
    abs_delta = parts["delta_probability"].get("abs_delta")
    ror = _num(candidate.get("ror"))

    def issue(text, score_cap=None):
        nonlocal cap
        warnings.append(text)
        critical.append(text)
        if score_cap is not None:
            cap = min(cap, score_cap)

    if parts["liquidity"].get("grade") in ("Weak", "Poor"):
        issue("Poor liquidity", 62 if parts["liquidity"].get("grade") == "Poor" else 72)
    if parts["bid_ask"].get("grade") in ("Weak", "Poor"):
        issue("Wide bid/ask", 62 if parts["bid_ask"].get("grade") == "Poor" else 70)
    if parts["iv_suitability"].get("grade") in ("Very Expensive",):
        issue("Very expensive IV", 62)

    if family in ("long_option", "debit_spread") and abs_delta is not None:
        if abs_delta < 0.05:
            issue("Lottery delta / very low probability", 42)
        elif abs_delta < 0.10:
            issue("Low probability", 52)
        elif abs_delta < 0.25:
            issue("High-risk delta", 68)

    if family == "debit_spread" and parts["risk_reward"].get("grade") in ("Lottery", "Poor", "Weak"):
        issue("Weak debit spread reward/risk", 60)

    if family == "credit_spread":
        if ror is not None and ror < 5:
            issue("Poor return on risk", 55)
        elif ror is not None and ror < 10:
            issue("Weak return on risk", 65)
        if abs_delta is not None and abs_delta > 0.45:
            issue("High short-leg delta", 58)
        if abs_delta is not None and abs_delta < 0.05:
            issue("Very low reward", 65)
        if premium is not None and premium < 0.05:
            issue("Tiny credit", 55)

    if family in ("short_put", "covered_call", "short_call"):
        if premium is not None and premium < 0.10:
            issue("Tiny premium", 55)
        if premium is not None and strike:
            annualized_yield = (premium / strike) * (365 / dte)
            if annualized_yield < 0.04:
                issue("Low premium yield", 62)
        if abs_delta is not None and abs_delta > 0.45:
            issue("High assignment risk", 58)
        if abs_delta is not None and abs_delta < 0.05:
            issue("Low reward short premium", 68)

    if family == "short_call":
        issue("Naked short call risk unless covered", 62)

    if parts["trend_match"].get("grade") == "Poor":
        issue("Trend mismatch", 70)

    dte_text, dte_cap = _dte_warning(candidate)
    if dte_text:
        issue(dte_text, dte_cap)

    # Do not let a trade look "good" if any core factor is terrible.
    weak_parts = [name for name, part in parts.items() if (part.get("points") or 0) <= 2]
    if weak_parts:
        cap = min(cap, 60)

    return cap, warnings, critical


def score_trade_quality(candidate, technical=None):
    """Strategy-aware six-factor trade-quality score. DTE/Greeks are warnings/caps, not weighted categories."""
    item = dict(candidate)
    weights = _strategy_profile(item.get("strategy"))

    liquidity = _liquidity_quality(item, weights.get("liquidity", 0))
    bid_ask = _bid_ask_quality(item, weights.get("bid_ask", 0))
    delta_probability = _delta_probability_quality(item, weights.get("delta_probability", 0))
    risk_reward = _risk_reward_quality(item, delta_probability, weights.get("risk_reward", 0))
    iv_suitability = _iv_suitability_quality(item, weights.get("iv_suitability", 0))
    trend_match = _trend_match_quality(item, technical or {}, weights.get("trend_match", 0))

    parts = {
        "delta_probability": delta_probability,
        "risk_reward": risk_reward,
        "iv_suitability": iv_suitability,
        "trend_match": trend_match,
        "liquidity": liquidity,
        "bid_ask": bid_ask,
    }
    raw_score = sum(p.get("weighted_points", 0) for p in parts.values())
    cap, warnings, critical_issues = _score_caps_and_warnings(item, parts)
    score = max(0, min(100, int(round(min(raw_score, cap)))))

    reasons = [
        delta_probability["reason"],
        risk_reward["reason"],
        iv_suitability["reason"],
        trend_match["reason"],
        liquidity["reason"],
        bid_ask["reason"],
    ]

    risk_level = delta_probability.get("risk_level") or _risk_level_from_family_delta(item, delta_probability.get("abs_delta"))

    item["quality_score"] = score
    item["quality"] = {
        "score": score,
        "raw_score": round(raw_score, 1),
        "score_cap": cap,
        "weights": weights,
        "strategy_family": _strategy_family(item),
        "risk_level": risk_level,
        "delta_probability": delta_probability,
        "probability": delta_probability,
        "risk_reward": risk_reward,
        "iv_suitability": iv_suitability,
        "trend_match": trend_match,
        "liquidity": liquidity,
        "bid_ask": bid_ask,
        "riskiness": delta_probability,
        "reasons": reasons,
        "warnings": warnings,
        "critical_issues": critical_issues,
        "critical_issue": _first_issue(critical_issues),
        "disclaimer": "Rule-based estimate from delayed market data and model-derived Greeks. DTE and Greeks are used only as warnings/caps. Confirm live bid/ask, liquidity, IV, Greeks and order price with your broker."
    }
    item["riskiness"] = risk_level
    item["probability_estimate"] = delta_probability.get("value")
    item["probability_label"] = delta_probability.get("label")
    item["critical_issue"] = _first_issue(critical_issues)
    return item


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
