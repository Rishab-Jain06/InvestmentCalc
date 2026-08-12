from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

import requests

import alpha_vantage_data

FINNHUB_BASE = "https://finnhub.io/api/v1"
_CACHE: dict[str, dict[str, Any]] = {}
_LOCK = Lock()
CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "calendar"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _token():
    return (os.getenv("FINNHUB_API_KEY") or "").strip()


def _cache_file(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return CACHE_DIR / f"{digest}.json"


def _cache(key: str, ttl: int, loader):
    now = time.time()
    with _LOCK:
        entry = _CACHE.get(key)
        if entry and entry["expires_at"] > now:
            value = dict(entry["value"])
            value["cached"] = True
            value["cache_layer"] = "memory"
            return value

    path = _cache_file(key)
    if path.exists():
        try:
            payload = json.loads(path.read_text())
            if payload.get("expires_at", 0) > now:
                value = dict(payload["value"])
                with _LOCK:
                    _CACHE[key] = {"value": payload["value"], "expires_at": payload["expires_at"]}
                value["cached"] = True
                value["cache_layer"] = "disk"
                return value
        except Exception:
            pass

    value = loader()
    expires_at = now + ttl
    with _LOCK:
        _CACHE[key] = {"value": value, "expires_at": expires_at}
    try:
        path.write_text(json.dumps({"value": value, "expires_at": expires_at}, default=str))
    except Exception:
        pass
    value = dict(value)
    value["cached"] = False
    value["cache_layer"] = "live"
    return value


def _finnhub_get(path, params=None, timeout=20):
    key = _token()
    if not key:
        raise RuntimeError("FINNHUB_API_KEY is not configured.")
    p = dict(params or {})
    p["token"] = key
    r = requests.get(f"{FINNHUB_BASE}{path}", params=p, timeout=timeout)
    if r.status_code == 429:
        raise RuntimeError("Finnhub rate limit reached.")
    r.raise_for_status()
    return r.json()


def _safe_date(s):
    if not s:
        return None
    text = str(s)[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except Exception:
        return None


def _num(v):
    try:
        if v in (None, "", "null"):
            return None
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def _date_range_default():
    today = date.today()
    first = today.replace(day=1)
    last = (first + timedelta(days=40)).replace(day=1) - timedelta(days=1)
    return first.isoformat(), last.isoformat()


def _in_range(d: str | None, start: str, end: str) -> bool:
    return bool(d and start <= d <= end)


MACRO_EVENT_DEFS: dict[str, dict[str, Any]] = {
    "CPI": {
        "full_name": "Consumer Price Index",
        "category": "Inflation",
        "impact": "High",
        "unit": "index",
        "av_function": "CPI",
        "av_params": {"interval": "monthly"},
        "description": "Measures the price change of a basket of goods and services paid by consumers.",
        "why_it_matters": "It is one of the biggest inflation inputs for interest-rate expectations and equity valuation.",
        "higher_read": "Usually pressures bonds and growth stocks because markets may price higher-for-longer rates.",
        "lower_read": "Often supports growth stocks and rate-sensitive sectors if it eases inflation concerns.",
        "assets": ["SPY", "QQQ", "Treasuries", "USD", "Gold"],
    },
    "Core CPI": {
        "full_name": "Core Consumer Price Index",
        "category": "Inflation",
        "impact": "High",
        "unit": "index",
        "av_function": "CPI",
        "av_params": {"interval": "monthly"},
        "description": "Measures consumer inflation excluding food and energy. Alpha Vantage uses headline CPI as the available value proxy.",
        "why_it_matters": "Core inflation is watched closely because it can show persistent price pressure.",
        "higher_read": "Can pressure high-valuation stocks if investors expect tighter Fed policy.",
        "lower_read": "Can support risk appetite if it signals inflation is cooling.",
        "assets": ["SPY", "QQQ", "Treasuries", "USD"],
    },
    "PPI": {
        "full_name": "Producer Price Index",
        "category": "Inflation",
        "impact": "High",
        "unit": "%",
        "av_function": None,
        "description": "Measures inflation at the producer/business level before it reaches consumers.",
        "why_it_matters": "It can foreshadow margin pressure and future consumer inflation.",
        "higher_read": "Can pressure equities if input costs look sticky.",
        "lower_read": "Can support margins and reduce inflation fears.",
        "assets": ["SPY", "Industrials", "Treasuries", "USD"],
    },
    "Core PPI": {
        "full_name": "Core Producer Price Index",
        "category": "Inflation",
        "impact": "High",
        "unit": "%",
        "av_function": None,
        "description": "Producer inflation excluding food and energy.",
        "why_it_matters": "Markets use it to judge whether producer cost pressure is broad-based.",
        "higher_read": "Can hurt rate-sensitive stocks if inflation appears sticky.",
        "lower_read": "Can support equities if cost pressure is easing.",
        "assets": ["SPY", "QQQ", "Treasuries", "USD"],
    },
    "Nonfarm Payrolls": {
        "full_name": "Monthly U.S. Payroll Employment",
        "category": "Labor",
        "impact": "High",
        "unit": "jobs",
        "av_function": "NONFARM_PAYROLL",
        "description": "Tracks monthly change in U.S. nonfarm jobs.",
        "why_it_matters": "Payrolls influence growth expectations, wage pressure and Fed policy expectations.",
        "higher_read": "Can support cyclicals and the dollar, but may pressure bonds if growth looks too hot.",
        "lower_read": "Can hurt risk appetite if it signals slowdown, but may support rate-cut expectations.",
        "assets": ["SPY", "DIA", "QQQ", "Treasuries", "USD"],
    },
    "Unemployment Rate": {
        "full_name": "U.S. Unemployment Rate",
        "category": "Labor",
        "impact": "High",
        "unit": "%",
        "av_function": "UNEMPLOYMENT",
        "description": "Shows the share of the labor force that is unemployed and actively looking for work.",
        "why_it_matters": "The labor market affects consumer spending, recession risk and Fed policy expectations.",
        "higher_read": "Can be bearish if it signals slowing growth, but can also reduce rate-hike pressure.",
        "lower_read": "Can support growth expectations, but too-hot labor data may revive inflation concerns.",
        "assets": ["SPY", "QQQ", "Treasuries", "USD"],
    },
    "Retail Sales": {
        "full_name": "U.S. Retail Sales",
        "category": "Consumer",
        "impact": "High",
        "unit": "value",
        "av_function": "RETAIL_SALES",
        "description": "Measures spending at retail businesses and gives a read on consumer demand.",
        "why_it_matters": "Consumer spending is a major driver of U.S. economic activity and revenue expectations.",
        "higher_read": "Can support consumer discretionary and cyclicals, but may also add inflation concerns.",
        "lower_read": "Can signal slowing demand and pressure consumer-exposed sectors.",
        "assets": ["SPY", "XLY", "Retail", "USD"],
    },
    "Initial Jobless Claims": {
        "full_name": "Initial Jobless Claims",
        "category": "Labor",
        "impact": "Medium",
        "unit": "claims",
        "av_function": None,
        "description": "Weekly count of people filing for unemployment insurance for the first time.",
        "why_it_matters": "It is a high-frequency read on labor-market stress.",
        "higher_read": "Can pressure stocks if it suggests layoffs are rising.",
        "lower_read": "Can support confidence if the labor market remains resilient.",
        "assets": ["SPY", "QQQ", "Treasuries", "USD"],
    },
    "Real GDP": {
        "full_name": "Real Gross Domestic Product",
        "category": "Growth",
        "impact": "High",
        "unit": "billions",
        "av_function": "REAL_GDP",
        "av_params": {"interval": "quarterly"},
        "description": "Measures inflation-adjusted economic output.",
        "why_it_matters": "GDP helps investors judge expansion, slowdown or recession risk.",
        "higher_read": "Can support equities if growth is healthy, but may pressure rates if too hot.",
        "lower_read": "Can pressure cyclicals and small caps if slowdown risk rises.",
        "assets": ["SPY", "IWM", "Treasuries", "USD"],
    },
    "PCE Inflation": {
        "full_name": "Personal Consumption Expenditures Inflation",
        "category": "Inflation",
        "impact": "High",
        "unit": "%",
        "av_function": "INFLATION",
        "description": "Inflation gauge watched closely by the Federal Reserve. Alpha Vantage fallback uses its available inflation series.",
        "why_it_matters": "Fed officials often emphasize PCE when discussing inflation trends.",
        "higher_read": "Can pressure equities and bonds if it implies sticky inflation.",
        "lower_read": "Can support rate-cut expectations and growth stocks.",
        "assets": ["SPY", "QQQ", "Treasuries", "USD"],
    },
    "Core PCE": {
        "full_name": "Core PCE Inflation",
        "category": "Inflation",
        "impact": "High",
        "unit": "%",
        "av_function": "INFLATION",
        "description": "Fed-preferred inflation concept excluding food and energy. Alpha Vantage fallback uses its available inflation series.",
        "why_it_matters": "Core PCE helps markets judge underlying inflation momentum.",
        "higher_read": "Can hurt high-multiple stocks if rate-cut odds fall.",
        "lower_read": "Can support risk assets if disinflation looks durable.",
        "assets": ["SPY", "QQQ", "Treasuries", "USD"],
    },
    "ISM Manufacturing PMI": {
        "full_name": "ISM Manufacturing PMI",
        "category": "Business Activity",
        "impact": "Medium",
        "unit": "index",
        "av_function": None,
        "description": "Survey-based gauge of U.S. manufacturing activity.",
        "why_it_matters": "It can reveal whether industrial demand is expanding or contracting.",
        "higher_read": "Can support industrials and cyclicals.",
        "lower_read": "Can signal weakening demand or recession risk.",
        "assets": ["SPY", "DIA", "Industrials", "USD"],
    },
    "ISM Services PMI": {
        "full_name": "ISM Services PMI",
        "category": "Business Activity",
        "impact": "Medium",
        "unit": "index",
        "av_function": None,
        "description": "Survey-based gauge of U.S. services-sector activity.",
        "why_it_matters": "Services are a large part of the U.S. economy, so this can affect growth and inflation views.",
        "higher_read": "Can support growth expectations but may keep inflation concerns alive.",
        "lower_read": "Can pressure markets if it signals weaker demand.",
        "assets": ["SPY", "QQQ", "USD"],
    },
    "Consumer Sentiment": {
        "full_name": "Consumer Sentiment",
        "category": "Consumer",
        "impact": "Medium",
        "unit": "index",
        "av_function": "CONSUMER_SENTIMENT",
        "description": "Measures how consumers feel about the economy and their finances.",
        "why_it_matters": "Consumer confidence can affect spending behavior and market expectations.",
        "higher_read": "Can support consumer stocks and broad risk appetite.",
        "lower_read": "Can raise concerns about future spending.",
        "assets": ["SPY", "XLY", "USD"],
    },
    "FOMC Rate Decision": {
        "full_name": "Federal Reserve Rate Decision",
        "category": "Federal Reserve",
        "impact": "High",
        "unit": "%",
        "av_function": "FEDERAL_FUNDS_RATE",
        "av_params": {"interval": "monthly"},
        "description": "Federal Reserve policy-rate decision and statement.",
        "why_it_matters": "Fed policy drives rates, liquidity, valuations and sector leadership.",
        "higher_read": "A more hawkish outcome can pressure equities and bonds.",
        "lower_read": "A more dovish outcome can support risk assets and rate-sensitive sectors.",
        "assets": ["SPY", "QQQ", "Treasuries", "USD", "Gold"],
    },
    "FOMC Minutes": {
        "full_name": "FOMC Meeting Minutes",
        "category": "Federal Reserve",
        "impact": "High",
        "unit": "%",
        "av_function": "FEDERAL_FUNDS_RATE",
        "av_params": {"interval": "monthly"},
        "description": "Detailed record of the Federal Reserve's prior policy meeting.",
        "why_it_matters": "Minutes show how policymakers view inflation, jobs, growth and future rate decisions.",
        "higher_read": "Hawkish minutes can pressure growth stocks and bonds.",
        "lower_read": "Dovish minutes can support rate-cut expectations.",
        "assets": ["SPY", "QQQ", "Treasuries", "USD"],
    },
}

FOMC_DECISION_DATES = {
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-16", "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
}


def earnings_calendar(start: str, end: str, restrict_to_symbols: bool = False, symbols: list[str] | None = None, limit: int = 1000):
    syms = [s.upper().strip() for s in (symbols or []) if s and str(s).strip()]
    key = f"calendar:earnings:v45:{start}:{end}:{restrict_to_symbols}:{','.join(syms[:100])}:{limit}"

    def _load():
        events = []
        errors = []
        source = None

        if restrict_to_symbols and not syms:
            return {"events": [], "source": "No selected symbols", "errors": []}

        if alpha_vantage_data.configured():
            try:
                av = alpha_vantage_data.earnings_calendar("3month")
                source = av.get("source")
                for row in av.get("events") or []:
                    d = _safe_date(row.get("report_date"))
                    sym = (row.get("symbol") or "").upper()
                    if not _in_range(d, start, end):
                        continue
                    if restrict_to_symbols and sym not in syms:
                        continue
                    events.append({
                        "id": f"earnings:{d}:{sym}:alpha",
                        "type": "earnings",
                        "date": d,
                        "symbol": sym,
                        "title": f"{sym} earnings",
                        "company": row.get("company") or sym,
                        "full_name": f"{row.get('company') or sym} Earnings Report",
                        "hour": "TBD",
                        "time_label": "TBD",
                        "fiscal_quarter": None,
                        "fiscal_year": None,
                        "fiscal_date_ending": row.get("fiscal_date_ending"),
                        "eps_estimate": row.get("eps_estimate"),
                        "eps_actual": None,
                        "revenue_estimate": None,
                        "revenue_actual": None,
                        "currency": row.get("currency") or "USD",
                        "impact": "Company-specific",
                        "description": "Quarterly earnings report. Investors compare actual results and guidance against expectations.",
                        "why_it_matters": "Earnings can reset expectations for revenue growth, margins, cash flow and valuation.",
                        "source": source,
                    })
            except Exception as e:
                errors.append(f"Alpha Vantage earnings: {e}")
        else:
            errors.append("ALPHA_VANTAGE_API_KEY is not configured.")

        if not events:
            try:
                rows = _finnhub_get("/calendar/earnings", {"from": start, "to": end, "symbol": "", "international": "false"}).get("earningsCalendar") or []
                source = "Finnhub earnings calendar fallback"
                for row in rows:
                    d = _safe_date(row.get("date") or row.get("period"))
                    sym = (row.get("symbol") or "").upper()
                    if not _in_range(d, start, end):
                        continue
                    if restrict_to_symbols and sym not in syms:
                        continue
                    events.append(_normalize_finnhub_earning(row, source))
            except Exception as e:
                errors.append(f"Finnhub earnings fallback: {e}")

        dedup = {}
        for e in events:
            if e.get("date") and e.get("symbol"):
                dedup[(e["date"], e["symbol"])] = e
        clean = sorted(dedup.values(), key=lambda x: (x.get("date") or "", x.get("symbol") or ""))[:limit]
        return {"events": clean, "source": source or "Unavailable", "errors": errors}

    # AV raw earnings is cached for 24h inside alpha_vantage_data; month result also cached 24h.
    return _cache(key, 60 * 60 * 24, _load)


def _normalize_finnhub_earning(row: dict[str, Any], source: str):
    d = _safe_date(row.get("date") or row.get("period"))
    sym = (row.get("symbol") or "").upper()
    hour = row.get("hour") or row.get("time") or "TBD"
    return {
        "id": f"earnings:{d}:{sym}:finnhub",
        "type": "earnings",
        "date": d,
        "symbol": sym,
        "title": f"{sym} earnings",
        "company": row.get("company") or row.get("name") or sym,
        "full_name": f"{row.get('company') or row.get('name') or sym} Earnings Report",
        "hour": hour,
        "time_label": hour,
        "fiscal_quarter": row.get("quarter"),
        "fiscal_year": row.get("year"),
        "fiscal_date_ending": row.get("period"),
        "eps_estimate": _num(row.get("epsEstimate")),
        "eps_actual": _num(row.get("epsActual")),
        "revenue_estimate": _num(row.get("revenueEstimate")),
        "revenue_actual": _num(row.get("revenueActual")),
        "surprise": _num(row.get("surprise")),
        "surprise_percent": _num(row.get("surprisePercent")),
        "currency": "USD",
        "impact": "Company-specific",
        "description": "Quarterly earnings report. Investors compare actual results and guidance against expectations.",
        "why_it_matters": "Earnings can reset expectations for revenue growth, margins, cash flow and valuation.",
        "source": source,
    }


def nth_weekday(year: int, month: int, weekday: int, n: int):
    d = date(year, month, 1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d + timedelta(days=7 * (n - 1))


def first_weekday_on_or_after(year: int, month: int, day: int):
    d = date(year, month, day)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def last_weekday(year: int, month: int, weekday: int):
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while d.weekday() != weekday:
        d -= timedelta(days=1)
    return d


def _macro_event(day: date, title: str, *, time_label="08:30 AM ET"):
    meta = MACRO_EVENT_DEFS[title]
    return {
        "id": f"economic:{day.isoformat()}:{title.lower().replace(' ', '-')}",
        "type": "economic",
        "date": day.isoformat(),
        "title": title,
        "full_name": meta.get("full_name") or title,
        "country": "US",
        "category": meta.get("category"),
        "impact": meta.get("impact"),
        "time_label": time_label,
        "actual": None,
        "estimate": None,
        "previous": None,
        "unit": meta.get("unit"),
        "av_function": meta.get("av_function"),
        "av_params": meta.get("av_params") or {},
        "assets": meta.get("assets") or [],
        "description": meta.get("description"),
        "why_it_matters": meta.get("why_it_matters"),
        "higher_read": meta.get("higher_read"),
        "lower_read": meta.get("lower_read"),
        "source": "Investify macro calendar + Alpha Vantage values",
        "schedule_note": "Macro event dates are Investify's curated major-market schedule. Confirm official release dates before trading.",
    }


def curated_economic_calendar(start: str, end: str):
    key = f"calendar:economic_curated:v45:{start}:{end}"

    def _load():
        start_d = datetime.strptime(start, "%Y-%m-%d").date()
        end_d = datetime.strptime(end, "%Y-%m-%d").date()
        events = []
        cur = date(start_d.year, start_d.month, 1)
        while cur <= end_d:
            y, m = cur.year, cur.month
            cpi_day = first_weekday_on_or_after(y, m, 10)
            events.append(_macro_event(cpi_day, "CPI"))
            events.append(_macro_event(cpi_day, "Core CPI"))

            ppi_day = first_weekday_on_or_after(y, m, min(cpi_day.day + 1, 24))
            events.append(_macro_event(ppi_day, "PPI"))
            events.append(_macro_event(ppi_day, "Core PPI"))

            nfp = nth_weekday(y, m, 4, 1)
            events.append(_macro_event(nfp, "Nonfarm Payrolls"))
            events.append(_macro_event(nfp, "Unemployment Rate"))

            retail = first_weekday_on_or_after(y, m, 15)
            events.append(_macro_event(retail, "Retail Sales"))

            pce = last_weekday(y, m, 4)
            events.append(_macro_event(pce, "PCE Inflation"))
            events.append(_macro_event(pce, "Core PCE"))

            events.append(_macro_event(first_weekday_on_or_after(y, m, 1), "ISM Manufacturing PMI", time_label="10:00 AM ET"))
            events.append(_macro_event(first_weekday_on_or_after(y, m, 3), "ISM Services PMI", time_label="10:00 AM ET"))
            events.append(_macro_event(nth_weekday(y, m, 4, 2), "Consumer Sentiment", time_label="10:00 AM ET"))

            d = date(y, m, 1)
            while d.month == m:
                if d.weekday() == 3:
                    events.append(_macro_event(d, "Initial Jobless Claims"))
                d += timedelta(days=1)

            if m in {1, 4, 7, 10}:
                events.append(_macro_event(first_weekday_on_or_after(y, m, 25), "Real GDP"))

            for ds in sorted(FOMC_DECISION_DATES):
                if ds.startswith(f"{y:04d}-{m:02d}"):
                    dd = datetime.strptime(ds, "%Y-%m-%d").date()
                    events.append(_macro_event(dd, "FOMC Rate Decision", time_label="2:00 PM ET"))
                    minutes = dd + timedelta(days=21)
                    if minutes.month == m:
                        events.append(_macro_event(minutes, "FOMC Minutes", time_label="2:00 PM ET"))

            cur = date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)

        filtered = [e for e in events if start <= e["date"] <= end]
        filtered.sort(key=lambda x: (x["date"], 0 if x.get("impact") == "High" else 1, x["title"]))
        return {"events": filtered, "source": "Investify macro calendar + Alpha Vantage values"}

    return _cache(key, 60 * 60 * 24, _load)


def market_calendar(start=None, end=None, symbols=None, restrict_to_symbols=False):
    if not start or not end:
        start, end = _date_range_default()
    symbols = symbols or []
    restrict_to_symbols = bool(restrict_to_symbols)

    key = f"calendar:combined:v45:{start}:{end}:{restrict_to_symbols}:{','.join(symbols[:100])}"

    def _load():
        earnings = earnings_calendar(start, end, restrict_to_symbols=restrict_to_symbols, symbols=symbols)
        economic = curated_economic_calendar(start, end)
        events = (earnings.get("events") or []) + (economic.get("events") or [])
        events = [e for e in events if e.get("date")]
        events.sort(key=lambda x: (x.get("date") or "", 0 if x.get("type") == "economic" else 1, x.get("symbol") or x.get("title") or ""))
        return {
            "start": start,
            "end": end,
            "events": events,
            "counts": {
                "earnings": len([e for e in events if e.get("type") == "earnings"]),
                "economic": len([e for e in events if e.get("type") == "economic"]),
            },
            "sources": {"earnings": earnings.get("source"), "economic": economic.get("source")},
            "errors": {"earnings": "; ".join(earnings.get("errors") or []) or None, "economic": None},
            "notes": [
                "Economic event dates come from Investify's major U.S. macro schedule.",
                "Alpha Vantage values are loaded only when an event has a matching indicator mapping and are cached heavily.",
            ],
        }

    return _cache(key, 60 * 60 * 24, _load)


def event_details(event: dict[str, Any]):
    event = dict(event or {})
    if event.get("type") == "economic" and event.get("av_function"):
        try:
            av = alpha_vantage_data.latest_macro_for_event(event)
            if av.get("available"):
                event["actual"] = av.get("actual")
                event["actual_date"] = av.get("actual_date")
                event["previous"] = av.get("previous")
                event["previous_date"] = av.get("previous_date")
                event["unit"] = event.get("unit") or av.get("unit")
                event["value_source"] = av.get("source")
                event["value_cached"] = av.get("cached")
                event["cache_layer"] = av.get("cache_layer")
            else:
                event["value_note"] = av.get("reason")
        except Exception as e:
            event["value_note"] = str(e)
    elif event.get("type") == "economic" and not event.get("av_function"):
        event["value_note"] = "No matching Alpha Vantage indicator endpoint is available for this event, so Investify shows the event description and market interpretation only."
    return {"event": event, "source": event.get("value_source") or event.get("source"), "cached": bool(event.get("value_cached"))}


def event_ai_brief(event):
    import news_ai

    enriched = event_details(event).get("event", event)
    prompt = f"""
You are Investify AI explaining a market calendar event.
Use only the supplied event details and general market reasoning. Do not invent actual numbers.
Do not tell the user to buy or sell.
Keep it brief and beginner-friendly.

If this is an earnings event, cover: what the event is, what matters, bullish surprise, bearish surprise, and what to watch.
If this is an economic event, cover: what it is, why it matters, higher-than-expected reaction, lower-than-expected reaction, and assets affected.

Event:
{json.dumps(enriched, indent=2, default=str)}
"""
    try:
        text, model = news_ai._gemini_rest(prompt, json_mode=False)
        return {"mode": "gemini", "model": model, "brief": text.strip(), "event": enriched}
    except Exception as e:
        return {"mode": "fallback", "model": None, "brief": f"AI event explanation unavailable. {e}", "event": enriched}
