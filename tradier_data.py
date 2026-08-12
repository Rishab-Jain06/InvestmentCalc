from __future__ import annotations

import math
import os
import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any

import requests

SQRT_2 = math.sqrt(2.0)
_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_LOCK = Lock()


def _cache_fetch(key, ttl_seconds, loader, stale_grace_seconds=None):
    now = time.time()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and entry["expires_at"] > now:
            value = dict(entry["value"]) if isinstance(entry["value"], dict) else entry["value"]
            if isinstance(value, dict):
                value.setdefault("cached", True)
                value.setdefault("cached_at", entry["cached_at"])
            return value
    try:
        value = loader()
        with _CACHE_LOCK:
            _CACHE[key] = {"value": value, "cached_at": now, "expires_at": now + ttl_seconds}
        if isinstance(value, dict):
            value.setdefault("cached", False)
            value.setdefault("cached_at", now)
        return value
    except Exception:
        if entry and stale_grace_seconds is not None and (now - entry["cached_at"]) <= stale_grace_seconds:
            value = dict(entry["value"]) if isinstance(entry["value"], dict) else entry["value"]
            if isinstance(value, dict):
                value["cached"] = True
                value["stale"] = True
                value["cached_at"] = entry["cached_at"]
            return value
        raise


def configured_env():
    env = (os.getenv("TRADIER_ENV") or "sandbox").strip().lower()
    if env in ("prod", "production", "live"):
        env = "production"
        token = os.getenv("TRADIER_PRODUCTION_TOKEN") or os.getenv("TRADIER_TOKEN")
        base_url = "https://api.tradier.com/v1"
        label = "Tradier Production"
    else:
        env = "sandbox"
        token = os.getenv("TRADIER_SANDBOX_TOKEN") or os.getenv("TRADIER_TOKEN")
        base_url = "https://sandbox.tradier.com/v1"
        label = "Tradier Sandbox"
    return {
        "env": env,
        "token": (token or "").strip(),
        "base_url": base_url,
        "label": label,
        "configured": bool((token or "").strip()),
    }


def is_configured():
    return configured_env()["configured"]


def provider_status():
    c = configured_env()
    return {"configured": c["configured"], "env": c["env"], "label": c["label"], "base_url": c["base_url"]}


def _headers():
    token = configured_env()["token"]
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "InvestifyAnalytics/1.0",
    }


def _get(path, params=None, timeout=20):
    c = configured_env()
    if not c["configured"]:
        raise RuntimeError("Tradier token is not configured")
    url = f"{c['base_url']}{path}"
    r = requests.get(url, headers=_headers(), params=params or {}, timeout=timeout)
    if r.status_code == 401:
        raise RuntimeError("Tradier authentication failed. Check token and TRADIER_ENV.")
    if r.status_code == 429:
        raise RuntimeError("Tradier rate limit reached. Cached data will be used if available.")
    r.raise_for_status()
    return r.json()


def _num(v):
    try:
        if v in (None, "", "null"):
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None


def _int(v):
    try:
        if v in (None, "", "null"):
            return 0
        return int(float(str(v).replace(",", "")))
    except Exception:
        return 0


def _int_or_none(v):
    try:
        if v in (None, "", "null"):
            return None
        return int(float(str(v).replace(",", "")))
    except Exception:
        return None


def _cdf(x):
    return 0.5 * (1.0 + math.erf(x / SQRT_2))


def _pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs_price(spot, strike, years, rate, iv, kind):
    try:
        spot, strike, years, rate, iv = map(float, (spot, strike, years, rate, iv))
    except Exception:
        return None
    if spot <= 0 or strike <= 0 or years <= 0 or iv <= 0:
        return None
    rt = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * years) / (iv * rt)
    d2 = d1 - iv * rt
    disc = math.exp(-rate * years)
    if kind == "call":
        return spot * _cdf(d1) - strike * disc * _cdf(d2)
    return strike * disc * _cdf(-d2) - spot * _cdf(-d1)


def implied_volatility(price, spot, strike, years, rate, kind):
    price = _num(price)
    spot = _num(spot)
    strike = _num(strike)
    years = _num(years)
    if price is None or spot is None or strike is None or years is None or price <= 0 or spot <= 0 or strike <= 0 or years <= 0:
        return None
    # Basic no-arbitrage intrinsic floor. If price is too close to intrinsic, IV can be unstable.
    intrinsic = max(0.0, spot - strike) if kind == "call" else max(0.0, strike - spot)
    if price < intrinsic * 0.98:
        return None
    lo, hi = 0.01, 5.0
    for _ in range(70):
        mid = (lo + hi) / 2
        val = bs_price(spot, strike, years, rate, mid, kind)
        if val is None:
            return None
        if val > price:
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2, 6)


def bs_greeks(spot, strike, years, rate, iv, kind):
    try:
        spot, strike, years, rate, iv = map(float, (spot, strike, years, rate, iv))
    except Exception:
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


def dte_for(expiration):
    exp_dt = datetime.strptime(expiration, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return max((exp_dt.date() - datetime.now(timezone.utc).date()).days, 0)


def quote(symbol):
    s = symbol.upper()

    def _load():
        raw = _get("/markets/quotes", {"symbols": s})
        q = ((raw or {}).get("quotes") or {}).get("quote") or {}
        if isinstance(q, list):
            q = q[0] if q else {}
        price = _num(q.get("last")) or _num(q.get("bid")) or _num(q.get("ask"))
        if price is None and _num(q.get("bid")) and _num(q.get("ask")):
            price = (_num(q.get("bid")) + _num(q.get("ask"))) / 2
        return {
            "symbol": s,
            "name": q.get("description") or q.get("symbol") or s,
            "price": price,
            "bid": _num(q.get("bid")),
            "ask": _num(q.get("ask")),
            "change": _num(q.get("change")),
            "percent_change": _num(q.get("change_percentage")),
            "volume": _int_or_none(q.get("volume")),
            "avg_volume": _int_or_none(q.get("average_volume")),
            "previous_close": _num(q.get("prevclose")),
            "open": _num(q.get("open")),
            "day_low": _num(q.get("low")),
            "day_high": _num(q.get("high")),
            "fifty_two_week_low": _num(q.get("week_52_low")),
            "fifty_two_week_high": _num(q.get("week_52_high")),
            "source": configured_env()["label"],
            "provider": "tradier",
            "delayed": configured_env()["env"] == "sandbox",
        }

    return _cache_fetch(f"tradier:quote:{configured_env()['env']}:{s}", 30, _load, stale_grace_seconds=3600)


def expirations(symbol):
    s = symbol.upper()

    def _load():
        raw = _get("/markets/options/expirations", {"symbol": s, "includeAllRoots": "true"})
        dates = ((raw or {}).get("expirations") or {}).get("date") or []
        if isinstance(dates, str):
            dates = [dates]
        dates = sorted([x for x in dates if x])
        return {
            "symbol": s,
            "expirations": dates,
            "source": configured_env()["label"],
            "provider": "tradier",
            "delayed": configured_env()["env"] == "sandbox",
        }

    return _cache_fetch(f"tradier:expirations:{configured_env()['env']}:{s}", 1800, _load, stale_grace_seconds=86400)


def _extract_iv(row, greeks):
    candidates = [
        row.get("iv"), row.get("implied_volatility"), row.get("impliedVolatility"),
        greeks.get("mid_iv"), greeks.get("smv_vol"), greeks.get("volatility"),
    ]
    for v in candidates:
        x = _num(v)
        if x is None or x <= 0:
            continue
        # ORATS/Tradier can return percent-like vol on some fields; normalize to decimal.
        if x > 3:
            x = x / 100.0
        return x
    return None


def _extract_greek(greeks, name):
    x = _num(greeks.get(name))
    if x is None:
        return None
    return x


def _row_to_contract(row, kind, spot, expiration, rate):
    strike = _num(row.get("strike"))
    bid = _num(row.get("bid"))
    ask = _num(row.get("ask"))
    last = _num(row.get("last"))
    mid = (bid + ask) / 2 if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid else last
    width = (ask - bid) if bid is not None and ask is not None and bid > 0 and ask > 0 and ask >= bid else None
    greeks_raw = row.get("greeks") or {}
    dte = dte_for(expiration)
    years = max(dte / 365.0, 1 / 365.0)

    iv = _extract_iv(row, greeks_raw)
    iv_estimated = False
    if not iv and mid and spot and strike:
        iv = implied_volatility(mid, spot, strike, years, rate, kind)
        iv_estimated = iv is not None

    calc_greeks = bs_greeks(spot, strike, years, rate, iv, kind) if iv else {}
    out_greeks = {}
    greek_estimated = False
    for g in ("delta", "gamma", "theta", "vega", "rho"):
        provided = _extract_greek(greeks_raw, g)
        # In sandbox many Greeks are 0/blank. Replace zeros with calculated values when calculation is possible,
        # except keep true zero when calculation is also essentially zero.
        calc = calc_greeks.get(g)
        if provided is None or (provided == 0 and calc not in (None, 0)):
            out_greeks[g] = calc
            if calc is not None:
                greek_estimated = True
        else:
            out_greeks[g] = provided

    return {
        "contract": row.get("symbol") or row.get("option_symbol") or "",
        "root_symbol": row.get("root_symbol") or row.get("underlying") or "",
        "type": kind,
        "strike": strike,
        "expiration": expiration,
        "bid": bid,
        "ask": ask,
        "last": last,
        "mid": mid,
        "spread_width": width,
        "volume": _int(row.get("volume")),
        "open_interest": _int_or_none(row.get("open_interest")),
        "open_interest_available": _int_or_none(row.get("open_interest")) is not None,
        "iv": iv,
        "iv_estimated": iv_estimated,
        "greeks_estimated": greek_estimated,
        "greeks_source": "calculated" if greek_estimated else ("tradier" if greeks_raw else "unavailable"),
        "in_the_money": bool(row.get("in_the_money")) if row.get("in_the_money") is not None else (
            strike is not None and spot is not None and ((kind == "call" and spot > strike) or (kind == "put" and spot < strike))
        ),
        "source": configured_env()["label"],
        **out_greeks,
    }


def option_chain(symbol, expiration, risk_free_rate=0.043):
    s = symbol.upper()
    exp = expiration

    def _load():
        q = quote(s)
        spot = q.get("price")
        raw = _get("/markets/options/chains", {"symbol": s, "expiration": exp, "greeks": "true"})
        rows = ((raw or {}).get("options") or {}).get("option") or []
        if isinstance(rows, dict):
            rows = [rows]

        calls = []
        puts = []
        for row in rows:
            kind = (row.get("option_type") or row.get("type") or "").lower()
            if kind not in ("call", "put"):
                continue
            c = _row_to_contract(row, kind, spot, exp, risk_free_rate)
            if kind == "call":
                calls.append(c)
            else:
                puts.append(c)

        calls.sort(key=lambda x: float(x.get("strike") or 0))
        puts.sort(key=lambda x: float(x.get("strike") or 0))
        return {
            "symbol": s,
            "spot": spot,
            "quote": q,
            "expiration": exp,
            "dte": dte_for(exp),
            "risk_free_rate": risk_free_rate,
            "calls": calls,
            "puts": puts,
            "source": configured_env()["label"],
            "provider": "tradier",
            "delayed": configured_env()["env"] == "sandbox",
            "math_note": "Missing/zero sandbox IV and Greeks are estimated with Black-Scholes when enough price data is available.",
        }

    return _cache_fetch(f"tradier:chain:{configured_env()['env']}:{s}:{exp}", 60, _load, stale_grace_seconds=3600)


def chain_rows(chain, limit_each_side=14):
    spot = chain.get("spot")
    by_strike = {}
    for c in chain.get("calls") or []:
        by_strike.setdefault(c.get("strike"), {})["call"] = c
    for p in chain.get("puts") or []:
        by_strike.setdefault(p.get("strike"), {})["put"] = p

    rows = []
    for strike in sorted([x for x in by_strike.keys() if x is not None]):
        rows.append({"strike": strike, **by_strike.get(strike, {})})

    if spot:
        below = [r for r in rows if float(r["strike"]) <= float(spot)]
        above = [r for r in rows if float(r["strike"]) > float(spot)]
        rows = below[-limit_each_side:] + above[:limit_each_side]

    return rows
