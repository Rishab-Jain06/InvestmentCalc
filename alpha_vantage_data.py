from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from threading import Lock
from typing import Any

import requests

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

BASE = "https://www.alphavantage.co/query"
_CACHE: dict[str, dict[str, Any]] = {}
_LOCK = Lock()
CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "alpha_vantage"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def configured():
    return bool((os.getenv("ALPHA_VANTAGE_API_KEY") or "").strip())


def _key():
    return (os.getenv("ALPHA_VANTAGE_API_KEY") or "").strip()


def _cache_file(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return CACHE_DIR / f"{digest}.json"


def _get_cached(key: str, ttl_seconds: int):
    now = time.time()
    with _LOCK:
        entry = _CACHE.get(key)
        if entry and entry.get("expires_at", 0) > now:
            value = entry["value"]
            if isinstance(value, dict):
                value = dict(value)
                value["cached"] = True
                value["cache_layer"] = "memory"
            return value

    path = _cache_file(key)
    if path.exists():
        try:
            payload = json.loads(path.read_text())
            if payload.get("expires_at", 0) > now:
                value = payload["value"]
                with _LOCK:
                    _CACHE[key] = {"value": value, "expires_at": payload["expires_at"]}
                if isinstance(value, dict):
                    value = dict(value)
                    value["cached"] = True
                    value["cache_layer"] = "disk"
                return value
        except Exception:
            pass
    return None


def _save_cache(key: str, ttl_seconds: int, value):
    expires_at = time.time() + ttl_seconds
    with _LOCK:
        _CACHE[key] = {"value": value, "expires_at": expires_at}
    try:
        _cache_file(key).write_text(json.dumps({"expires_at": expires_at, "value": value}, default=str))
    except Exception:
        pass


def _cached(key: str, ttl_seconds: int, loader):
    cached = _get_cached(key, ttl_seconds)
    if cached is not None:
        return cached
    value = loader()
    _save_cache(key, ttl_seconds, value)
    if isinstance(value, dict):
        value = dict(value)
        value["cached"] = False
        value["cache_layer"] = "live"
    return value


def _request(params: dict[str, Any], timeout=25):
    if not configured():
        raise RuntimeError("ALPHA_VANTAGE_API_KEY is not configured.")
    p = dict(params or {})
    p["apikey"] = _key()
    r = requests.get(BASE, params=p, timeout=timeout)
    r.raise_for_status()
    text = r.text.strip()
    if "Thank you for using Alpha Vantage" in text and "standard API rate limit" in text:
        raise RuntimeError("Alpha Vantage free API rate limit reached. Cached data will be used when available.")
    if text.lower().startswith("{"):
        data = r.json()
        if isinstance(data, dict):
            if data.get("Note"):
                raise RuntimeError(str(data.get("Note"))[:240])
            if data.get("Information"):
                raise RuntimeError(str(data.get("Information"))[:240])
            if data.get("Error Message"):
                raise RuntimeError(str(data.get("Error Message"))[:240])
        return data
    return text


def earnings_calendar(horizon="3month"):
    """Alpha Vantage returns CSV for EARNINGS_CALENDAR."""
    horizon = horizon if horizon in {"3month", "6month", "12month"} else "3month"
    key = f"av:earnings_calendar:{horizon}"

    def _load():
        raw = _request({"function": "EARNINGS_CALENDAR", "horizon": horizon})
        if not isinstance(raw, str):
            raise RuntimeError("Unexpected Alpha Vantage earnings calendar response.")
        reader = csv.DictReader(io.StringIO(raw))
        rows = []
        for r in reader:
            sym = (r.get("symbol") or "").strip().upper()
            report_date = (r.get("reportDate") or r.get("report_date") or "").strip()
            if not sym or not report_date:
                continue
            rows.append({
                "symbol": sym,
                "company": (r.get("name") or sym).strip(),
                "report_date": report_date[:10],
                "fiscal_date_ending": (r.get("fiscalDateEnding") or "").strip(),
                "eps_estimate": _num(r.get("estimate")),
                "currency": (r.get("currency") or "USD").strip(),
                "raw": r,
            })
        return {"events": rows, "source": "Alpha Vantage EARNINGS_CALENDAR", "horizon": horizon}

    # Heavy cache: one broad earnings pull per day.
    return _cached(key, 60 * 60 * 24, _load)


def company_earnings(symbol: str):
    s = symbol.upper().strip()
    key = f"av:company_earnings:{s}"

    def _load():
        data = _request({"function": "EARNINGS", "symbol": s})
        quarterly = data.get("quarterlyEarnings") or []
        annual = data.get("annualEarnings") or []
        return {
            "symbol": s,
            "quarterly": quarterly[:12],
            "annual": annual[:5],
            "source": "Alpha Vantage EARNINGS",
        }

    # Per-symbol details are cached for 7 days to protect free API limits.
    return _cached(key, 60 * 60 * 24 * 7, _load)


def indicator(function_name: str, **params):
    fn = function_name.upper().strip()
    clean_params = {k: v for k, v in params.items() if v not in (None, "")}
    key = "av:indicator:" + fn + ":" + json.dumps(clean_params, sort_keys=True)

    def _load():
        data = _request({"function": fn, **clean_params})
        series = data.get("data") or []
        clean = []
        for row in series:
            val = _num(row.get("value"))
            date = row.get("date")
            if date and val is not None:
                clean.append({"date": date[:10], "value": val})
        return {
            "function": fn,
            "name": data.get("name") or fn,
            "interval": data.get("interval") or clean_params.get("interval"),
            "unit": data.get("unit"),
            "data": clean[:240],
            "latest": clean[0] if clean else None,
            "previous": clean[1] if len(clean) > 1 else None,
            "source": "Alpha Vantage Economic Indicators",
        }

    # Macro indicators update slowly; 7-day cache protects the free Alpha Vantage quota.
    return _cached(key, 60 * 60 * 24 * 7, _load)


def latest_macro_for_event(event: dict[str, Any]):
    code = (event.get("av_function") or "").strip().upper()
    if not code:
        return {"available": False, "reason": "No Alpha Vantage indicator mapping for this event."}

    params = event.get("av_params") or {}
    try:
        data = indicator(code, **params)
        latest = data.get("latest") or {}
        previous = data.get("previous") or {}
        return {
            "available": True,
            "function": code,
            "name": data.get("name"),
            "unit": data.get("unit") or event.get("unit"),
            "actual": latest.get("value"),
            "actual_date": latest.get("date"),
            "previous": previous.get("value"),
            "previous_date": previous.get("date"),
            "source": data.get("source"),
            "cached": bool(data.get("cached")),
            "cache_layer": data.get("cache_layer"),
        }
    except Exception as e:
        return {"available": False, "reason": str(e)}


def _num(v):
    try:
        if v in (None, "", "None", "null"):
            return None
        return float(str(v).replace(",", ""))
    except Exception:
        return None
