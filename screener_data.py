from __future__ import annotations
import csv
import os
import time
from pathlib import Path
from threading import Lock
import requests

import yahoo_data
import sec_data

_CACHE = {}
_LOCK = Lock()

# Source used when internet is available. Local fallback exists so app still works offline.
SP500_CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/refs/heads/main/data/constituents.csv"

FALLBACK_SP500 = [
"AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","BRK-B","AVGO","LLY","JPM","TSLA","V","UNH","XOM","MA","COST","WMT","HD","PG",
"JNJ","NFLX","BAC","ABBV","KO","CRM","ORCL","AMD","CVX","PEP","MRK","TMO","ADBE","CSCO","WFC","MCD","ABT","QCOM","GE","INTU",
"IBM","DIS","NOW","TXN","AMGN","PM","CAT","VZ","ISRG","PFE","NEE","UBER","GS","RTX","SPGI","CMCSA","T","LOW","AXP","UNP",
"BKNG","PGR","HON","BLK","ETN","TJX","COP","SCHW","SYK","BSX","C","LMT","ANET","VRTX","MDT","PANW","ADP","CB","UPS","DE",
"MMC","ADI","PLD","AMAT","GILD","MU","NKE","LRCX","KLAC","SO","INTC","MO","APH","ICE","DUK","WM","EQIX","SHW","CDNS","SNPS",
"PH","MCO","TT","CMG","CME","ORLY","TDG","MSI","AON","MMM","CI","USB","PNC","HCA","EOG","MAR","AJG","REGN","ELV","APO",
"GD","WELL","CL","EMR","ITW","NOC","FDX","ECL","TFC","CSX","BDX","APD","SLB","ROP","HLT","AZO","FCX","NSC","COF","NXPI",
"MNST","AFL","PSA","TRV","PCAR","OKE","ALL","MCK","GM","MET","JCI","O","ROST","DLR","SRE","AEP","KMI","SPG","DHI","BK",
"PAYX","AMP","AIG","F","GWW","URI","MSCI","VLO","COR","CPRT","KMB","CMI","FIS","LHX","PSX","KR","FAST","A","OXY","EW",
"PRU","PEG","CTAS","KDP","KVUE","RSG","CTVA","EXC","AME","YUM","CCI","HWM","OTIS","IR","VRSK","FANG","ACGL","GEV","IDXX",
"CTSH","CBRE","GIS","ODFL","D","EA","XEL","BKR","SYY","IT","HES","TRGP","VMC","NUE","ED","DD","LEN","MLM","MPWR","HPQ",
"ROK","EFX","VICI","WAB","WTW","ETR","HIG","XYL","AVB","WEC","TSCO","EIX","MTD","RCL","NDAQ","HUM","KEYS","CSGP","MTB","FITB",
"ANSS","STZ","BRO","STT","EXR","IQV","IRM","DXCM","DOW","EBAY","AWK","VTR","CHTR","LYV","CAH","CCL","PPG","UAL","KHC","TTWO",
"BR","EQR","DOV","FTV","VLTO","ADM","DTE","HPE","TYL","PPL","PHM","CDW","HSY","NTAP","STE","CINF","GPN","WRB","ON","WAT",
"DVN","WST","IFF","TROW","NVR","DECK","FE","AEE","LDOS","ATO","HAL","SYF","PTC","HBAN","ES","SBAC","WY","BIIB","STX","ZBH",
"TDY","CBOE","STLD","MKC","EQT","TSN","RF","EXPE","PKG","CPAY","CMS","DRI","CLX","LH","DG","LULU","ULTA","CFG","LVS","JBL",
"MOH","NRG","TRMB","DGX","TER","INVH","MAA","PODD","LUV","ESS","NI","WDC","FFIV","FDS","COO","SNA","CTRA","KEY","BBY","TPR",
"OMC","MAS","J","IEX","BALL","GDDY","EXPD","LNT","AVY","ZBRA","HOLX","BAX","GEN","K","ARE","SWKS","ALGN","TXT","AKAM","CF",
"VRSN","PNR","DOC","UDR","CAG","POOL","NDSN","RL","JBHT","SWK","MRNA","JKHY","REG","UHS","NTRS","CPT","RVTY","CHD","HST","EPAM",
"GL","BXP","ALLE","JNPR","AIZ","BG","TAP","IP","DAY","TECH","EMN","LKQ","INCY","QRVO","LW","MKTX","MGM","CRL","TFX","HAS",
"ERIE","WYNN","PNW","HSIC","AES","CPB","AOS","MTCH","MOS","APA","FOXA","FOX","CZR","MHK","NWSA","NWS","FRT","HII","PAYC","BEN"
]


def _cache_fetch(key, ttl, loader, stale_grace=None):
    now = time.time()
    with _LOCK:
        entry = _CACHE.get(key)
        if entry and entry["expires_at"] > now:
            return entry["value"]
    try:
        value = loader()
        with _LOCK:
            _CACHE[key] = {"value": value, "cached_at": now, "expires_at": now + ttl}
        return value
    except Exception:
        if entry and stale_grace is not None and now - entry["cached_at"] <= stale_grace:
            return entry["value"]
        raise


def _rating(score):
    if score is None:
        return "Unavailable"
    if score >= 81:
        return "Strong Buy"
    if score >= 61:
        return "Buy"
    if score >= 41:
        return "Hold"
    if score >= 21:
        return "Sell"
    return "Strong Sell"


def _rating_pass(value, wanted):
    if not wanted or wanted == "any":
        return True
    return (value or "").lower() == wanted.lower()


def sp500_universe():
    def _load():
        try:
            r = requests.get(SP500_CSV_URL, timeout=15)
            r.raise_for_status()
            rows = list(csv.DictReader(r.text.splitlines()))
            out = []
            for row in rows:
                sym = (row.get("Symbol") or row.get("symbol") or "").strip().replace(".", "-").upper()
                if not sym:
                    continue
                out.append({
                    "symbol": sym,
                    "company": row.get("Security") or row.get("Name") or row.get("company") or "",
                    "sector": row.get("GICS Sector") or row.get("sector") or "",
                })
            if out:
                return out
        except Exception:
            pass
        return [{"symbol": s, "company": "", "sector": ""} for s in FALLBACK_SP500]

    return _cache_fetch("sp500_universe", 60 * 60 * 24, _load, stale_grace=60 * 60 * 24 * 30)


def _safe_num(v):
    try:
        if v is None:
            return None
        return float(v)
    except Exception:
        return None


def score_symbol(symbol, deep_fundamentals=False):
    s = symbol.upper().replace(".", "-")
    ttl = 60 * 30
    def _load():
        q = yahoo_data.quote(s)
        t = yahoo_data.analyze_stock(s)

        fundamental = None
        if deep_fundamentals:
            try:
                fundamental = sec_data.fundamental_signal(s)
            except Exception:
                fundamental = None
        else:
            # Use already-cached fundamentals if present. Avoid SEC calls during fast screener scans.
            try:
                cached = sec_data._SEC_CACHE.get(f"fundamental_signal:{s}") if hasattr(sec_data, "_SEC_CACHE") else None
                if cached and cached.get("expires_at", 0) > time.time():
                    fundamental = cached.get("value")
            except Exception:
                fundamental = None

        f_score = fundamental.get("score") if fundamental else None
        t_score = t.get("score")
        overall, raw_overall, blend_weights, cap_reason = sec_data._overall_blend(
            t_score, f_score, fundamental.get("confidence") if fundamental else None
        )

        return {
            "symbol": s,
            "company": q.get("name") or s,
            "price": q.get("price"),
            "percent_change": q.get("percent_change"),
            "change": q.get("change"),
            "volume": q.get("volume"),
            "overall_score": overall,
            "overall_rating": _rating(overall),
            "overall_raw_score": raw_overall,
            "blend_weights": blend_weights,
            "cap_reason": cap_reason,
            "technical_score": t_score,
            "technical_rating": _rating(t_score),
            "technical_signal": t.get("signal"),
            "fundamental_score": f_score,
            "fundamental_rating": fundamental.get("rating") if fundamental else "Cached only",
            "fundamental_confidence": fundamental.get("confidence") if fundamental else "Not loaded",
            "source": "fast scan" if not deep_fundamentals else "deep scan",
        }
    return _cache_fetch(f"screener_score:{s}:{int(bool(deep_fundamentals))}", ttl, _load, stale_grace=60 * 60 * 6)


def run_screener(filters):
    universe_name = (filters.get("universe") or "sp500").lower()
    if universe_name == "custom":
        symbols = [x.strip().upper().replace(".", "-") for x in (filters.get("symbols") or "").split(",") if x.strip()]
        universe = [{"symbol": s, "company": "", "sector": ""} for s in symbols]
    else:
        universe = sp500_universe()

    scan_size = int(filters.get("scan_size") or 100)
    scan_size = max(10, min(scan_size, 500))
    top_n = int(filters.get("top_n") or 10)
    top_n = max(1, min(top_n, 25))
    deep = bool(filters.get("deep_fundamentals"))

    rows = []
    errors = []
    for row in universe[:scan_size]:
        sym = row["symbol"]
        try:
            item = score_symbol(sym, deep_fundamentals=deep)
            item["sector"] = row.get("sector") or ""
            if _passes(item, filters):
                rows.append(item)
        except Exception as e:
            errors.append({"symbol": sym, "error": str(e)})

    rows.sort(key=lambda x: (
        x.get("overall_score") if x.get("overall_score") is not None else -999,
        x.get("fundamental_score") if x.get("fundamental_score") is not None else -999,
        x.get("technical_score") if x.get("technical_score") is not None else -999,
        x.get("volume") or 0
    ), reverse=True)

    return {
        "results": rows[:top_n],
        "matched_count": len(rows),
        "scanned": min(scan_size, len(universe)),
        "universe_count": len(universe),
        "top_n": top_n,
        "errors": errors[:10],
        "mode": "deep" if deep else "fast",
    }


def _passes(x, f):
    min_price = _safe_num(f.get("min_price"))
    max_price = _safe_num(f.get("max_price"))
    min_overall = _safe_num(f.get("min_overall_score"))
    min_technical = _safe_num(f.get("min_technical_score"))
    min_fundamental = _safe_num(f.get("min_fundamental_score"))

    price = _safe_num(x.get("price"))
    if min_price is not None and (price is None or price < min_price):
        return False
    if max_price is not None and (price is None or price > max_price):
        return False
    if min_overall is not None and ((x.get("overall_score") or 0) < min_overall):
        return False
    if min_technical is not None and ((x.get("technical_score") or 0) < min_technical):
        return False
    if min_fundamental is not None and x.get("fundamental_score") is not None and x.get("fundamental_score") < min_fundamental:
        return False
    if not _rating_pass(x.get("overall_rating"), f.get("overall_rating")):
        return False
    if not _rating_pass(x.get("technical_rating"), f.get("technical_rating")):
        return False
    if f.get("fundamental_rating") not in (None, "", "any") and x.get("fundamental_score") is None:
        return False
    if not _rating_pass(x.get("fundamental_rating"), f.get("fundamental_rating")):
        return False
    return True
