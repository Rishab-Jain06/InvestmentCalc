from __future__ import annotations
import math
import os
import time
from threading import Lock
from datetime import datetime
import requests

import yahoo_data

_SEC_CACHE = {}
_SEC_LOCK = Lock()

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_DATA_BASE = "https://data.sec.gov"
SEC_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"


def _cache_fetch(key, ttl_seconds, loader, stale_grace_seconds=None):
    now = time.time()
    with _SEC_LOCK:
        entry = _SEC_CACHE.get(key)
        if entry and entry["expires_at"] > now:
            return entry["value"]
    try:
        value = loader()
        with _SEC_LOCK:
            _SEC_CACHE[key] = {"value": value, "cached_at": now, "expires_at": now + ttl_seconds}
        return value
    except Exception:
        if entry and stale_grace_seconds is not None and (now - entry["cached_at"]) <= stale_grace_seconds:
            return entry["value"]
        raise


def _user_agent():
    return os.getenv("SEC_USER_AGENT") or "InvestifyAnalytics/1.0 research@example.com"


def _get_json(url, timeout=25):
    r = requests.get(url, headers={"User-Agent": _user_agent(), "Accept-Encoding": "gzip, deflate", "Host": url.split('/')[2]}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _num(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return float(v)
    except Exception:
        return None


def _safe_div(a, b):
    a = _num(a); b = _num(b)
    if a is None or b in (None, 0):
        return None
    return a / b


def _score_lower_better(v, bands):
    v = _num(v)
    if v is None or v <= 0:
        return None
    for cutoff, score in bands:
        if v <= cutoff:
            return score
    return bands[-1][1]


def _score_higher_better(v, bands):
    v = _num(v)
    if v is None:
        return None
    for cutoff, score in bands:
        if v >= cutoff:
            return score
    return bands[-1][1]


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


def _component(label, weight, metric_scores, details, missing=None):
    available = [x for x in metric_scores if x is not None]
    if available:
        score = round(sum(available) / len(available))
        points = round(score * weight / 100)
    else:
        score = None
        points = 0
    return {
        "label": label,
        "weight": weight,
        "score": score,
        "points": points,
        "details": details,
        "missing": missing or [],
        "available_metrics": len(available),
        "total_metrics": len(metric_scores),
    }


def ticker_cik_map():
    def _load():
        data = _get_json(SEC_TICKERS_URL)
        out = {}
        for _, row in (data or {}).items():
            ticker = (row.get("ticker") or "").upper()
            cik = int(row.get("cik_str"))
            if ticker:
                out[ticker] = {"cik": cik, "cik_padded": str(cik).zfill(10), "title": row.get("title")}
        return out
    return _cache_fetch("sec:ticker_map", 60 * 60 * 24 * 30, _load, stale_grace_seconds=60 * 60 * 24 * 365)


def cik_for_ticker(symbol):
    return ticker_cik_map().get(symbol.upper())


def company_submissions(symbol):
    s = symbol.upper()
    def _load():
        row = cik_for_ticker(s)
        if not row:
            return {"error": "CIK not found for ticker", "symbol": s}
        return _get_json(f"{SEC_DATA_BASE}/submissions/CIK{row['cik_padded']}.json")
    return _cache_fetch(f"sec:submissions:{s}", 60 * 60 * 6, _load, stale_grace_seconds=60 * 60 * 24 * 30)


def company_facts(symbol):
    s = symbol.upper()
    def _load():
        row = cik_for_ticker(s)
        if not row:
            return {"error": "CIK not found for ticker", "symbol": s}
        return _get_json(f"{SEC_DATA_BASE}/api/xbrl/companyfacts/CIK{row['cik_padded']}.json")
    return _cache_fetch(f"sec:facts:{s}", 60 * 60 * 24, _load, stale_grace_seconds=60 * 60 * 24 * 90)


def _fact_items(facts, concept, unit="USD"):
    try:
        items = (((facts.get("facts") or {}).get("us-gaap") or {}).get(concept) or {}).get("units") or {}
        vals = items.get(unit) or []
        return vals if isinstance(vals, list) else []
    except Exception:
        return []


def _latest_fact(facts, concepts, unit="USD", annual_only=False):
    best = None
    for concept in concepts:
        for item in _fact_items(facts, concept, unit):
            if annual_only and item.get("fp") != "FY":
                continue
            if item.get("val") is None:
                continue
            form = item.get("form") or ""
            if form and form not in ("10-K", "10-Q", "20-F", "40-F"):
                continue
            end = item.get("end") or item.get("filed") or ""
            key = (end, item.get("filed") or "")
            if best is None or key > best[0]:
                best = (key, float(item["val"]), concept, item)
    return None if best is None else {"value": best[1], "concept": best[2], "item": best[3]}


def _annual_series(facts, concepts, unit="USD", years=6):
    rows = []
    for concept in concepts:
        for item in _fact_items(facts, concept, unit):
            if item.get("fp") != "FY" or item.get("val") is None:
                continue
            form = item.get("form") or ""
            if form not in ("10-K", "20-F", "40-F"):
                continue
            fy = item.get("fy")
            end = item.get("end")
            try:
                val = float(item["val"])
            except Exception:
                continue
            rows.append({"fy": fy, "end": end, "filed": item.get("filed"), "value": val, "concept": concept})
    # Deduplicate by fiscal year, keeping latest filing/end.
    by_year = {}
    for row in rows:
        key = row.get("fy") or row.get("end")
        if not key:
            continue
        old = by_year.get(key)
        if old is None or (row.get("filed") or "") > (old.get("filed") or ""):
            by_year[key] = row
    series = sorted(by_year.values(), key=lambda x: str(x.get("end") or x.get("fy") or ""))[-years:]
    return series


def _cagr(series, years_back=3):
    if not series or len(series) < 2:
        return None
    latest = series[-1]["value"]
    # Prefer exact years_back if available.
    base_index = max(0, len(series) - 1 - years_back)
    base = series[base_index]["value"]
    n = len(series) - 1 - base_index
    if base <= 0 or latest <= 0 or n <= 0:
        return None
    return ((latest / base) ** (1 / n) - 1) * 100


REVENUE_CONCEPTS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]
NET_INCOME_CONCEPTS = ["NetIncomeLoss", "ProfitLoss"]
OPERATING_INCOME_CONCEPTS = ["OperatingIncomeLoss", "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"]
CFO_CONCEPTS = ["NetCashProvidedByUsedInOperatingActivities", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"]
CAPEX_CONCEPTS = ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets", "CapitalExpenditures"]
CASH_CONCEPTS = ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"]
DEBT_CONCEPTS = ["LongTermDebtAndFinanceLeaseObligations", "LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtAndFinanceLeaseObligationsNoncurrent", "LongTermDebtCurrent", "LongTermDebtNoncurrent", "ShortTermBorrowings"]
ASSETS_CONCEPTS = ["Assets"]
LIABILITIES_CONCEPTS = ["Liabilities"]
EQUITY_CONCEPTS = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
INTEREST_CONCEPTS = ["InterestExpenseNonOperating", "InterestExpense"]
CURRENT_ASSETS_CONCEPTS = ["AssetsCurrent"]
CURRENT_LIABILITIES_CONCEPTS = ["LiabilitiesCurrent"]
RETAINED_EARNINGS_CONCEPTS = ["RetainedEarningsAccumulatedDeficit"]


def _sum_latest_debt(facts):
    values = []
    for concept in DEBT_CONCEPTS:
        x = _latest_fact(facts, [concept])
        if x and x["value"] is not None:
            values.append((concept, x["value"]))
    # If comprehensive debt concept exists, use it. Otherwise add current/non-current pieces where available.
    for concept, val in values:
        if concept == "LongTermDebtAndFinanceLeaseObligations":
            return val
    total = 0
    found = False
    for concept, val in values:
        if concept in ("LongTermDebtAndFinanceLeaseObligationsCurrent", "LongTermDebtAndFinanceLeaseObligationsNoncurrent", "LongTermDebtCurrent", "LongTermDebtNoncurrent", "ShortTermBorrowings"):
            total += val
            found = True
    return total if found else None


def _metric(label, value, score, display=None):
    return {"label": label, "value": value, "display": display if display is not None else _display(value), "score": score}


def _display(v, suffix=""):
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        if abs(v) >= 1_000_000_000:
            return f"{v/1_000_000_000:.2f}B{suffix}"
        if abs(v) >= 1_000_000:
            return f"{v/1_000_000:.2f}M{suffix}"
        return f"{v:.2f}{suffix}"
    return str(v)


def _fmt_pct(v):
    return "—" if v is None else f"{v:.1f}%"


def fundamental_signal(symbol):
    s = symbol.upper()
    def _load():
        stats = yahoo_data.stats(s)
        valuation = stats.get("valuation") or {}
        profitability = stats.get("profitability") or {}
        financial = stats.get("financial") or {}
        market = stats.get("market") or {}
        facts = {}
        sec_error = None
        try:
            facts = company_facts(s)
            if facts.get("error"):
                sec_error = facts.get("error")
                facts = {}
        except Exception as e:
            sec_error = str(e)

        market_cap = _num(market.get("market_cap"))
        pe = _num(valuation.get("trailing_pe"))
        fpe = _num(valuation.get("forward_pe"))
        peg = _num(valuation.get("peg_ratio"))
        yahoo_fcf = _num(financial.get("free_cash_flow"))
        p_fcf = _safe_div(market_cap, yahoo_fcf) if yahoo_fcf and yahoo_fcf > 0 else None

        revenue_latest = _latest_fact(facts, REVENUE_CONCEPTS)
        revenue_series = _annual_series(facts, REVENUE_CONCEPTS)
        revenue_cagr = _cagr(revenue_series, 3)
        net_income_latest = _latest_fact(facts, NET_INCOME_CONCEPTS)
        ni_series = _annual_series(facts, NET_INCOME_CONCEPTS)
        ni_cagr = _cagr(ni_series, 3)
        op_income_latest = _latest_fact(facts, OPERATING_INCOME_CONCEPTS)
        cfo_latest = _latest_fact(facts, CFO_CONCEPTS)
        capex_latest = _latest_fact(facts, CAPEX_CONCEPTS)
        cash_latest = _latest_fact(facts, CASH_CONCEPTS)
        assets_latest = _latest_fact(facts, ASSETS_CONCEPTS)
        liabilities_latest = _latest_fact(facts, LIABILITIES_CONCEPTS)
        equity_latest = _latest_fact(facts, EQUITY_CONCEPTS)
        interest_latest = _latest_fact(facts, INTEREST_CONCEPTS)
        current_assets = _latest_fact(facts, CURRENT_ASSETS_CONCEPTS)
        current_liabilities = _latest_fact(facts, CURRENT_LIABILITIES_CONCEPTS)
        retained_earnings = _latest_fact(facts, RETAINED_EARNINGS_CONCEPTS)

        cfo = cfo_latest["value"] if cfo_latest else _num(financial.get("operating_cash_flow"))
        capex = capex_latest["value"] if capex_latest else None
        fcf = None
        if cfo is not None and capex is not None:
            fcf = cfo - abs(capex)
        elif yahoo_fcf is not None:
            fcf = yahoo_fcf

        p_fcf = _safe_div(market_cap, fcf) if fcf and fcf > 0 and market_cap else p_fcf
        net_income = net_income_latest["value"] if net_income_latest else None
        fcf_conversion = _safe_div(fcf, net_income) if fcf is not None and net_income and net_income > 0 else None

        debt = _sum_latest_debt(facts)
        if debt is None:
            debt = _num(financial.get("debt"))
        cash = cash_latest["value"] if cash_latest else _num(financial.get("cash"))
        ebitda = _num(financial.get("ebitda"))
        net_debt_ebitda = None
        if ebitda and ebitda > 0 and debt is not None:
            net_debt_ebitda = (debt - (cash or 0)) / ebitda
        interest = interest_latest["value"] if interest_latest else None
        ebit = op_income_latest["value"] if op_income_latest else None
        interest_coverage = _safe_div(ebit, abs(interest)) if interest and ebit is not None else None

        assets = assets_latest["value"] if assets_latest else None
        liabilities = liabilities_latest["value"] if liabilities_latest else None
        equity = equity_latest["value"] if equity_latest else None
        working_capital = None
        if current_assets and current_liabilities:
            working_capital = current_assets["value"] - current_liabilities["value"]
        altman_z = None
        if assets and assets > 0 and liabilities and market_cap and revenue_latest and retained_earnings and ebit is not None:
            altman_z = (
                1.2 * ((working_capital or 0) / assets)
                + 1.4 * (retained_earnings["value"] / assets)
                + 3.3 * (ebit / assets)
                + 0.6 * (market_cap / liabilities)
                + 1.0 * (revenue_latest["value"] / assets)
            )

        invested_capital = None
        if debt is not None and equity is not None:
            invested_capital = debt + equity - (cash or 0)
        roic = None
        if invested_capital and invested_capital > 0 and ebit is not None:
            roic = (ebit * 0.79) / invested_capital * 100

        current_ratio = _num(financial.get("current_ratio"))
        gross_margin = _num(profitability.get("gross_margin"))
        operating_margin = _num(profitability.get("operating_margin"))
        profit_margin = _num(profitability.get("profit_margin"))
        roe = _num(profitability.get("roe"))
        roa = _num(profitability.get("roa"))
        revenue_growth = revenue_cagr if revenue_cagr is not None else _num(financial.get("revenue_growth"))

        # Metric scores
        pe_score = _score_lower_better(pe, [(15, 90), (25, 75), (40, 50), (60, 30), (10**9, 15)])
        fpe_score = _score_lower_better(fpe, [(15, 90), (25, 75), (40, 50), (60, 30), (10**9, 15)])
        peg_score = _score_lower_better(peg, [(1.0, 90), (2.0, 70), (3.0, 45), (10**9, 20)])
        pfcf_score = _score_lower_better(p_fcf, [(15, 90), (25, 75), (40, 50), (60, 30), (10**9, 15)])

        nde_score = None
        if net_debt_ebitda is not None:
            if net_debt_ebitda < 0:
                nde_score = 95
            else:
                nde_score = _score_lower_better(net_debt_ebitda, [(1, 90), (2, 75), (3.5, 55), (4.0, 35), (10**9, 15)])
        ic_score = _score_higher_better(interest_coverage, [(10, 90), (5, 75), (3, 55), (1.5, 30), (-10**9, 10)])
        z_score = _score_higher_better(altman_z, [(3, 90), (1.8, 55), (-10**9, 20)])
        cr_score = _score_higher_better(current_ratio, [(2, 85), (1.2, 65), (1, 45), (-10**9, 20)])

        roic_score = _score_higher_better(roic, [(20, 95), (15, 85), (10, 65), (5, 45), (-10**9, 20)])
        gm_score = _score_higher_better(gross_margin, [(60, 90), (40, 75), (25, 55), (10, 35), (-10**9, 15)])
        om_score = _score_higher_better(operating_margin, [(30, 90), (20, 75), (10, 55), (3, 35), (-10**9, 15)])
        pm_score = _score_higher_better(profit_margin, [(20, 90), (12, 75), (6, 55), (1, 35), (-10**9, 15)])
        roe_score = _score_higher_better(roe, [(25, 90), (15, 75), (8, 55), (0, 30), (-10**9, 10)])

        rev_growth_score = _score_higher_better(revenue_growth, [(15, 90), (8, 75), (3, 55), (0, 35), (-10**9, 15)])
        ni_growth_score = _score_higher_better(ni_cagr, [(15, 90), (8, 75), (3, 55), (0, 35), (-10**9, 15)])
        fcf_conv_score = None
        if fcf_conversion is not None:
            if fcf_conversion >= 1.0:
                fcf_conv_score = 90
            elif fcf_conversion >= 0.75:
                fcf_conv_score = 70
            elif fcf_conversion >= 0.5:
                fcf_conv_score = 45
            else:
                fcf_conv_score = 20

        def missing(names_scores):
            return [name for name, score in names_scores if score is None]

        valuation_component = _component(
            "Valuation", 30,
            [pe_score, fpe_score, pfcf_score, peg_score],
            "P/E, Forward P/E, Price/FCF and PEG Ratio.",
            missing([("P/E", pe_score), ("Forward P/E", fpe_score), ("P/FCF", pfcf_score), ("PEG", peg_score)])
        )
        health_component = _component(
            "Financial Health", 25,
            [nde_score, ic_score, z_score, cr_score],
            "Net Debt/EBITDA, Interest Coverage, Altman Z-Score and liquidity fallback.",
            missing([("Net Debt/EBITDA", nde_score), ("Interest Coverage", ic_score), ("Altman Z-Score", z_score), ("Current Ratio", cr_score)])
        )
        profitability_component = _component(
            "Profitability & Efficiency", 25,
            [roic_score, gm_score, om_score, pm_score, roe_score],
            "ROIC, margins and return metrics.",
            missing([("ROIC", roic_score), ("Gross Margin", gm_score), ("Operating Margin", om_score), ("Profit Margin", pm_score), ("ROE", roe_score)])
        )
        growth_component = _component(
            "Growth & Earnings Quality", 20,
            [rev_growth_score, ni_growth_score, fcf_conv_score],
            "Revenue growth, net income growth and free cash flow conversion.",
            missing([("Revenue CAGR/Growth", rev_growth_score), ("Net Income CAGR", ni_growth_score), ("FCF Conversion", fcf_conv_score)])
        )

        components = [valuation_component, health_component, profitability_component, growth_component]
        available_weight = sum(c["weight"] for c in components if c["score"] is not None)
        if available_weight:
            score = round(sum(c["points"] for c in components) * 100 / available_weight)
        else:
            score = None

        total_metric_count = sum(c["total_metrics"] for c in components)
        available_metric_count = sum(c["available_metrics"] for c in components)
        confidence = "High" if available_metric_count >= 12 else "Medium" if available_metric_count >= 7 else "Low"

        metrics = {
            "P/E": _metric("P/E", pe, pe_score),
            "Forward P/E": _metric("Forward P/E", fpe, fpe_score),
            "P/FCF": _metric("P/FCF", p_fcf, pfcf_score),
            "PEG": _metric("PEG", peg, peg_score),
            "Net Debt / EBITDA": _metric("Net Debt / EBITDA", net_debt_ebitda, nde_score, _display(net_debt_ebitda, "x")),
            "Interest Coverage": _metric("Interest Coverage", interest_coverage, ic_score, _display(interest_coverage, "x")),
            "Altman Z-Score": _metric("Altman Z-Score", altman_z, z_score),
            "ROIC": _metric("ROIC", roic, roic_score, _fmt_pct(roic)),
            "Gross Margin": _metric("Gross Margin", gross_margin, gm_score, _fmt_pct(gross_margin)),
            "Operating Margin": _metric("Operating Margin", operating_margin, om_score, _fmt_pct(operating_margin)),
            "Profit Margin": _metric("Profit Margin", profit_margin, pm_score, _fmt_pct(profit_margin)),
            "Revenue CAGR/Growth": _metric("Revenue CAGR/Growth", revenue_growth, rev_growth_score, _fmt_pct(revenue_growth)),
            "Net Income CAGR": _metric("Net Income CAGR", ni_cagr, ni_growth_score, _fmt_pct(ni_cagr)),
            "FCF Conversion": _metric("FCF Conversion", fcf_conversion, fcf_conv_score, _display(fcf_conversion, "x")),
        }

        score_for_rating = score if score is not None else 0
        rating = _rating(score) if score is not None else "Unavailable"
        missing_all = []
        for c in components:
            missing_all.extend(c.get("missing") or [])

        return {
            "symbol": s,
            "score": score,
            "rating": rating,
            "components": components,
            "metrics": metrics,
            "confidence": confidence,
            "available_metrics": available_metric_count,
            "total_metrics": total_metric_count,
            "missing": missing_all[:12],
            "summary": f"Fundamental score uses valuation, financial health, profitability/efficiency, and growth/earnings quality. Confidence is {confidence.lower()} based on available Yahoo and SEC metrics.",
            "sec_error": sec_error,
            "source": "Yahoo stats + SEC EDGAR where available",
        }

    return _cache_fetch(f"fundamental_signal:{s}", 60 * 60 * 24, _load, stale_grace_seconds=60 * 60 * 24 * 14)


def recent_filings(symbol, limit=8):
    s = symbol.upper()
    def _load():
        row = cik_for_ticker(s)
        if not row:
            return {"symbol": s, "filings": [], "error": "CIK not found for ticker"}
        sub = company_submissions(s)
        recent = (sub.get("filings") or {}).get("recent") or {}
        forms = recent.get("form") or []
        accessions = recent.get("accessionNumber") or []
        filing_dates = recent.get("filingDate") or []
        report_dates = recent.get("reportDate") or []
        docs = recent.get("primaryDocument") or []
        accepted = {"10-K", "10-Q", "8-K", "DEF 14A", "20-F", "40-F"}
        filings = []
        cik_plain = str(row["cik"])
        for i, form in enumerate(forms):
            if form not in accepted:
                continue
            accession = accessions[i] if i < len(accessions) else ""
            doc = docs[i] if i < len(docs) else ""
            accession_clean = accession.replace("-", "")
            url = f"{SEC_ARCHIVES_BASE}/{cik_plain}/{accession_clean}/{doc}" if accession and doc else None
            filings.append({
                "form": form,
                "filing_date": filing_dates[i] if i < len(filing_dates) else None,
                "report_date": report_dates[i] if i < len(report_dates) else None,
                "accession": accession,
                "document": doc,
                "url": url,
            })
            if len(filings) >= limit:
                break
        return {"symbol": s, "cik": row["cik_padded"], "company": row.get("title"), "filings": filings}
    return _cache_fetch(f"sec:recent_filings:{s}:{limit}", 60 * 60 * 6, _load, stale_grace_seconds=60 * 60 * 24 * 30)


def company_context(symbol):
    stats = yahoo_data.stats(symbol)
    identity = stats.get("identity") or {}
    fundamentals = {}
    try:
        fundamentals = fundamental_signal(symbol)
    except Exception:
        fundamentals = {}
    filings = {}
    try:
        filings = recent_filings(symbol, limit=4)
    except Exception:
        filings = {}
    return {
        "symbol": symbol.upper(),
        "identity": identity,
        "fundamental": {
            "score": fundamentals.get("score"),
            "rating": fundamentals.get("rating"),
            "confidence": fundamentals.get("confidence"),
            "summary": fundamentals.get("summary"),
        },
        "recent_filings": filings.get("filings") or [],
    }


def overall_signal(symbol):
    technical = yahoo_data.analyze_stock(symbol)
    fundamental = fundamental_signal(symbol)
    t_score = technical.get("score")
    f_score = fundamental.get("score")
    if t_score is not None and f_score is not None:
        score = round((float(t_score) * 0.5) + (float(f_score) * 0.5))
    elif t_score is not None:
        score = round(float(t_score))
    elif f_score is not None:
        score = round(float(f_score))
    else:
        score = None
    rating = _rating(score) if score is not None else "Unavailable"
    if t_score is not None and f_score is not None:
        if f_score >= 65 and t_score <= 40:
            summary = "Fundamentals are stronger than the current technical setup. This may indicate a quality stock with weak near-term price action."
        elif f_score <= 40 and t_score >= 65:
            summary = "Technicals are stronger than fundamentals. This may be a short-term momentum setup with weaker long-term fundamentals."
        else:
            summary = "Overall signal blends technical trend context and fundamental quality equally."
    else:
        summary = "Overall signal uses the available technical or fundamental score."
    return {"symbol": symbol.upper(), "score": score, "rating": rating, "technical": technical, "fundamental": fundamental, "summary": summary}
