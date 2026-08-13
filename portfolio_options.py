from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

import options_data

_SYMBOL_RE = re.compile(r"[^A-Za-z0-9.\-]")


def _num(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value in (None, "", "null"):
            return default
        x = float(value)
        if math.isnan(x) or math.isinf(x):
            return default
        return x
    except Exception:
        return default


def _clean_symbol(value: Any) -> str:
    return _SYMBOL_RE.sub("", str(value or "").upper())[:20]


def _clean_strategy(value: Any) -> str:
    s = str(value or "single").lower().strip().replace(" ", "_").replace("-", "_")
    return s if s in {"single", "vertical"} else "single"


def _clean_type(value: Any) -> str:
    s = str(value or "call").lower().strip()
    return "put" if s == "put" else "call"


def _clean_side(value: Any) -> str:
    s = str(value or "long").lower().strip()
    return "short" if s == "short" else "long"


def _clean_spread_type(value: Any, option_type: str = "put") -> str:
    s = str(value or "").lower().strip().replace(" ", "_").replace("-", "_")
    allowed = {"put_credit", "call_credit", "put_debit", "call_debit"}
    if s in allowed:
        return s
    return f"{option_type if option_type in {'call','put'} else 'put'}_credit"


def _dte(expiration: str) -> Optional[int]:
    try:
        return (datetime.strptime(str(expiration), "%Y-%m-%d").date() - date.today()).days
    except Exception:
        return None


def _is_credit(spread_type: str) -> bool:
    return "credit" in str(spread_type or "")


def _is_debit(spread_type: str) -> bool:
    return "debit" in str(spread_type or "")


def _spread_option_type(spread_type: str, fallback: str = "put") -> str:
    return "call" if str(spread_type or "").startswith("call") else "put" if str(spread_type or "").startswith("put") else fallback


def _mark(contract: Optional[Dict[str, Any]]) -> Optional[float]:
    if not contract:
        return None
    bid = _num(contract.get("bid"))
    ask = _num(contract.get("ask"))
    mid = _num(contract.get("mid"))
    last = _num(contract.get("last"))
    if bid is not None and ask is not None and bid >= 0 and ask > 0 and ask >= bid:
        return round((bid + ask) / 2, 4)
    for x in (mid, last, bid, ask):
        if x is not None and x >= 0:
            return round(x, 4)
    return None


def _contract_quote(contract: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not contract:
        return {"found": False, "mark": None}
    return {
        "found": True,
        "contract": contract.get("contract"),
        "type": contract.get("type"),
        "strike": contract.get("strike"),
        "expiration": contract.get("expiration"),
        "bid": _num(contract.get("bid")),
        "ask": _num(contract.get("ask")),
        "last": _num(contract.get("last")),
        "mid": _num(contract.get("mid")),
        "mark": _mark(contract),
        "iv": _num(contract.get("iv")),
        "delta": _num(contract.get("delta")),
        "theta": _num(contract.get("theta")),
        "volume": contract.get("volume"),
        "open_interest": contract.get("open_interest"),
    }


def _find_contract(chain: Dict[str, Any], kind: str, strike: Any) -> Optional[Dict[str, Any]]:
    target = _num(strike)
    if target is None:
        return None
    rows = chain.get("calls") if kind == "call" else chain.get("puts")
    best = None
    best_dist = 1e9
    for c in rows or []:
        s = _num(c.get("strike"))
        if s is None:
            continue
        dist = abs(s - target)
        if dist < best_dist:
            best, best_dist = c, dist
        if dist < 0.0001:
            return c
    # Only accept a near match, not an obviously different strike.
    return best if best_dist <= 0.01 else None


def normalize_position(raw: Dict[str, Any]) -> Dict[str, Any]:
    strategy = _clean_strategy(raw.get("strategy"))
    underlying = _clean_symbol(raw.get("underlying") or raw.get("symbol"))
    option_type = _clean_type(raw.get("option_type") or raw.get("type"))
    spread_type = _clean_spread_type(raw.get("spread_type"), option_type)
    if strategy == "vertical":
        option_type = _spread_option_type(spread_type, option_type)
    return {
        "id": str(raw.get("id") or ""),
        "strategy": strategy,
        "spread_type": spread_type if strategy == "vertical" else None,
        "underlying": underlying,
        "option_type": option_type,
        "position_side": _clean_side(raw.get("position_side") or raw.get("side")),
        "expiration": str(raw.get("expiration") or "")[:10],
        "strike": _num(raw.get("strike")),
        "short_strike": _num(raw.get("short_strike")),
        "long_strike": _num(raw.get("long_strike")),
        "contracts": max(_num(raw.get("contracts"), 1) or 1, 0),
        "entry_price": max(_num(raw.get("entry_price") or raw.get("entry"), 0) or 0, 0),
        "account": str(raw.get("account") or "Brokerage")[:80],
        "notes": str(raw.get("notes") or "")[:1000],
        "opened_at": str(raw.get("opened_at") or "")[:10] or None,
    }


def value_positions(raw_positions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    positions = [normalize_position(p) for p in (raw_positions or []) if isinstance(p, dict)]
    chains: Dict[Tuple[str, str], Dict[str, Any]] = {}
    errors: Dict[str, str] = {}
    rows: List[Dict[str, Any]] = []

    for p in positions:
        row = dict(p)
        row.update({
            "current_price": None,
            "current_value": None,
            "pnl": None,
            "pnl_pct": None,
            "max_profit": None,
            "max_loss": None,
            "dte": _dte(p.get("expiration")),
            "status": "unpriced",
            "message": "",
            "source": None,
            "delayed": False,
            "legs": [],
        })
        if not p["underlying"] or not p["expiration"]:
            row["message"] = "Missing underlying or expiration"
            rows.append(row)
            continue

        key = (p["underlying"], p["expiration"])
        try:
            if key not in chains:
                chains[key] = options_data.option_chain(p["underlying"], p["expiration"])
            chain = chains[key]
            row["underlying_price"] = chain.get("spot")
            row["source"] = chain.get("source") or chain.get("provider") or "options chain"
            row["provider"] = chain.get("provider")
            row["delayed"] = bool(chain.get("delayed"))
        except Exception as e:
            errors[f"{key[0]} {key[1]}"] = str(e)
            row["message"] = str(e)
            rows.append(row)
            continue

        contracts = p["contracts"]
        entry = p["entry_price"]
        multiplier = 100 * contracts

        if p["strategy"] == "single":
            c = _find_contract(chain, p["option_type"], p["strike"])
            q = _contract_quote(c)
            mark = q.get("mark")
            row["legs"] = [{"role": p["position_side"], **q}]
            row["current_price"] = mark
            if mark is not None:
                row["current_value"] = round(mark * multiplier, 2)
                if p["position_side"] == "short":
                    pnl = (entry - mark) * multiplier
                    basis = entry * multiplier
                else:
                    pnl = (mark - entry) * multiplier
                    basis = entry * multiplier
                row["pnl"] = round(pnl, 2)
                row["pnl_pct"] = round((pnl / basis * 100), 2) if basis else None
                row["status"] = "priced"
            else:
                row["message"] = "Contract quote unavailable"
            rows.append(row)
            continue

        kind = p["option_type"]
        short_c = _find_contract(chain, kind, p["short_strike"])
        long_c = _find_contract(chain, kind, p["long_strike"])
        short_q = _contract_quote(short_c)
        long_q = _contract_quote(long_c)
        short_mark = short_q.get("mark")
        long_mark = long_q.get("mark")
        row["legs"] = [{"role": "short", **short_q}, {"role": "long", **long_q}]
        width = abs((p["short_strike"] or 0) - (p["long_strike"] or 0))
        row["width"] = width
        credit = _is_credit(p.get("spread_type"))
        if width and entry is not None:
            if credit:
                row["max_profit"] = round(entry * multiplier, 2)
                row["max_loss"] = round(max(width - entry, 0) * multiplier, 2)
            else:
                row["max_profit"] = round(max(width - entry, 0) * multiplier, 2)
                row["max_loss"] = round(entry * multiplier, 2)
        if short_mark is not None and long_mark is not None:
            current = short_mark - long_mark if credit else long_mark - short_mark
            row["current_price"] = round(current, 4)
            row["current_value"] = round(current * multiplier, 2)
            pnl = (entry - current) * multiplier if credit else (current - entry) * multiplier
            basis = row["max_loss"] if credit else entry * multiplier
            row["pnl"] = round(pnl, 2)
            row["pnl_pct"] = round((pnl / basis * 100), 2) if basis else None
            row["status"] = "priced"
        else:
            row["message"] = "One or both spread legs are unavailable"
        rows.append(row)

    total_value = sum((_num(r.get("current_value"), 0) or 0) for r in rows)
    total_pnl = sum((_num(r.get("pnl"), 0) or 0) for r in rows)
    return {
        "positions": rows,
        "count": len(rows),
        "priced_count": sum(1 for r in rows if r.get("status") == "priced"),
        "total_value": round(total_value, 2),
        "total_pnl": round(total_pnl, 2),
        "errors": errors,
    }
