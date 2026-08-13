from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import requests

SUPABASE_TIMEOUT = 25
ACCESS_COOKIE = "investify_access_token"
REFRESH_COOKIE = "investify_refresh_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def _base_url() -> str:
    return (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")


def _anon_key() -> str:
    return (os.getenv("SUPABASE_ANON_KEY") or "").strip()


def _service_key() -> str:
    return (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()


def configured() -> bool:
    return bool(_base_url() and _anon_key())


def service_configured() -> bool:
    return bool(_base_url() and _service_key())


def public_config() -> Dict[str, Any]:
    return {
        "configured": configured(),
        "url": _base_url(),
        "anon_key": _anon_key(),
    }


def _auth_headers(access_token: Optional[str] = None) -> Dict[str, str]:
    headers = {"apikey": _anon_key(), "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _db_headers(prefer: Optional[str] = None) -> Dict[str, str]:
    key = _service_key()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _check_config(require_service: bool = False) -> None:
    if not _base_url() or not _anon_key():
        raise RuntimeError("Supabase is not configured. Add SUPABASE_URL and SUPABASE_ANON_KEY.")
    if require_service and not _service_key():
        raise RuntimeError("Supabase service key is missing. Add SUPABASE_SERVICE_ROLE_KEY on the server.")


def _raise_api_error(response: requests.Response, fallback: str) -> None:
    if response.ok:
        return
    try:
        data = response.json()
        msg = data.get("msg") or data.get("message") or data.get("error_description") or data.get("error")
    except Exception:
        msg = response.text[:250]
    raise RuntimeError(msg or f"{fallback} failed with HTTP {response.status_code}")


def auth_user(access_token: str) -> Dict[str, Any]:
    _check_config(False)
    if not access_token:
        raise RuntimeError("No access token")
    r = requests.get(f"{_base_url()}/auth/v1/user", headers=_auth_headers(access_token), timeout=SUPABASE_TIMEOUT)
    _raise_api_error(r, "Get user")
    data = r.json() or {}
    user = data.get("user") if isinstance(data.get("user"), dict) else data
    if not user or not user.get("id"):
        raise RuntimeError("User session is invalid")
    return user


def refresh_session(refresh_token: str) -> Dict[str, Any]:
    _check_config(False)
    if not refresh_token:
        raise RuntimeError("No refresh token")
    r = requests.post(
        f"{_base_url()}/auth/v1/token?grant_type=refresh_token",
        headers=_auth_headers(),
        json={"refresh_token": refresh_token},
        timeout=SUPABASE_TIMEOUT,
    )
    _raise_api_error(r, "Refresh session")
    return r.json() or {}


def sign_in(email: str, password: str) -> Dict[str, Any]:
    _check_config(False)
    r = requests.post(
        f"{_base_url()}/auth/v1/token?grant_type=password",
        headers=_auth_headers(),
        json={"email": email, "password": password},
        timeout=SUPABASE_TIMEOUT,
    )
    _raise_api_error(r, "Sign in")
    return r.json() or {}


def sign_up(email: str, password: str, display_name: str = "") -> Dict[str, Any]:
    _check_config(False)
    body: Dict[str, Any] = {"email": email, "password": password}
    if display_name:
        body["data"] = {"display_name": display_name}
    r = requests.post(f"{_base_url()}/auth/v1/signup", headers=_auth_headers(), json=body, timeout=SUPABASE_TIMEOUT)
    _raise_api_error(r, "Sign up")
    return r.json() or {}


def sign_out(access_token: str) -> None:
    if not access_token or not configured():
        return
    try:
        requests.post(f"{_base_url()}/auth/v1/logout", headers=_auth_headers(access_token), timeout=10)
    except Exception:
        pass


def google_authorize_url(redirect_to: str) -> str:
    _check_config(False)
    params = urlencode({"provider": "google", "redirect_to": redirect_to})
    return f"{_base_url()}/auth/v1/authorize?{params}"


def _rest_url(table: str, query: str = "") -> str:
    return f"{_base_url()}/rest/v1/{table}{query}"


def _select(table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
    _check_config(True)
    query = "?" + urlencode(params)
    r = requests.get(_rest_url(table, query), headers=_db_headers(), timeout=SUPABASE_TIMEOUT)
    _raise_api_error(r, f"Select {table}")
    data = r.json() or []
    return data if isinstance(data, list) else []


def _insert(table: str, rows: Any) -> List[Dict[str, Any]]:
    _check_config(True)
    r = requests.post(_rest_url(table), headers=_db_headers("return=representation"), json=rows, timeout=SUPABASE_TIMEOUT)
    _raise_api_error(r, f"Insert {table}")
    data = r.json() or []
    return data if isinstance(data, list) else [data]


def _upsert(table: str, row: Dict[str, Any], conflict: str) -> List[Dict[str, Any]]:
    _check_config(True)
    query = "?" + urlencode({"on_conflict": conflict})
    r = requests.post(
        _rest_url(table, query),
        headers=_db_headers("resolution=merge-duplicates,return=representation"),
        json=row,
        timeout=SUPABASE_TIMEOUT,
    )
    _raise_api_error(r, f"Upsert {table}")
    data = r.json() or []
    return data if isinstance(data, list) else [data]


def _delete(table: str, params: Dict[str, str]) -> None:
    _check_config(True)
    query = "?" + urlencode(params)
    r = requests.delete(_rest_url(table, query), headers=_db_headers(), timeout=SUPABASE_TIMEOUT)
    _raise_api_error(r, f"Delete {table}")


def _patch(table: str, params: Dict[str, str], body: Dict[str, Any]) -> List[Dict[str, Any]]:
    _check_config(True)
    query = "?" + urlencode(params)
    r = requests.patch(_rest_url(table, query), headers=_db_headers("return=representation"), json=body, timeout=SUPABASE_TIMEOUT)
    _raise_api_error(r, f"Patch {table}")
    data = r.json() or []
    return data if isinstance(data, list) else [data]


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clean_symbol(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9.\-]", "", str(value or "").upper())[:20]


def _clean_uuid(value: Any) -> Optional[str]:
    text = str(value or "")
    return text if _UUID_RE.match(text) else None


def _missing_optional_table(exc: Exception, table: str) -> bool:
    msg = str(exc).lower()
    return table.lower() in msg and ("does not exist" in msg or "relation" in msg or "schema cache" in msg or "pgrst" in msg or "not found" in msg)


def _optional_select(table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
    try:
        return _select(table, params)
    except Exception as exc:
        if _missing_optional_table(exc, table):
            return []
        raise


def _optional_delete(table: str, params: Dict[str, str]) -> None:
    try:
        _delete(table, params)
    except Exception as exc:
        if _missing_optional_table(exc, table):
            return
        raise


def _optional_insert(table: str, rows: Any) -> List[Dict[str, Any]]:
    try:
        return _insert(table, rows)
    except Exception as exc:
        if _missing_optional_table(exc, table):
            return []
        raise


def normalize_profile(user: Dict[str, Any]) -> Dict[str, Any]:
    meta = user.get("user_metadata") or {}
    app_meta = user.get("app_metadata") or {}
    provider = app_meta.get("provider") or (app_meta.get("providers") or [None])[0]
    return {
        "id": user.get("id"),
        "email": user.get("email"),
        "display_name": meta.get("display_name") or meta.get("full_name") or meta.get("name") or (user.get("email") or "").split("@")[0],
        "avatar_url": meta.get("avatar_url") or meta.get("picture"),
        "provider": provider,
    }


def ensure_profile(user: Dict[str, Any]) -> Dict[str, Any]:
    profile = normalize_profile(user)
    if not profile.get("id"):
        raise RuntimeError("Cannot create profile without user id")
    rows = _upsert("profiles", profile, "id")
    return rows[0] if rows else profile


def ensure_settings(user_id: str) -> Dict[str, Any]:
    rows = _select("user_settings", {"select": "*", "user_id": f"eq.{user_id}", "limit": "1"})
    if rows:
        return rows[0]
    rows = _upsert("user_settings", {"user_id": user_id}, "user_id")
    return rows[0] if rows else {"user_id": user_id}


def ensure_default_portfolio(user_id: str) -> Dict[str, Any]:
    rows = _select("portfolios", {"select": "*", "user_id": f"eq.{user_id}", "is_default": "eq.true", "limit": "1"})
    if rows:
        return rows[0]
    rows = _select("portfolios", {"select": "*", "user_id": f"eq.{user_id}", "order": "created_at.asc", "limit": "1"})
    if rows:
        row = rows[0]
        _patch("portfolios", {"id": f"eq.{row['id']}"}, {"is_default": True})
        row["is_default"] = True
        return row
    rows = _insert("portfolios", {"user_id": user_id, "name": "Main Portfolio", "is_default": True})
    return rows[0]


def normalize_option_position(row: Dict[str, Any]) -> Dict[str, Any]:
    strategy = str(row.get("strategy") or "single").lower()
    if strategy not in {"single", "vertical"}:
        strategy = "single"
    option_type = str(row.get("option_type") or "call").lower()
    if option_type not in {"call", "put"}:
        option_type = "call"
    side = str(row.get("position_side") or "long").lower()
    if side not in {"long", "short"}:
        side = "long"
    spread_type = str(row.get("spread_type") or "").lower().replace(" ", "_").replace("-", "_")
    if spread_type not in {"put_credit", "call_credit", "put_debit", "call_debit"}:
        spread_type = "put_credit" if option_type == "put" else "call_debit"
    return {
        "id": row.get("id"),
        "strategy": strategy,
        "spread_type": spread_type if strategy == "vertical" else None,
        "underlying": _clean_symbol(row.get("underlying") or row.get("symbol")),
        "option_type": option_type,
        "position_side": side,
        "expiration": str(row.get("expiration") or "")[:10],
        "strike": _num(row.get("strike")),
        "short_strike": _num(row.get("short_strike")),
        "long_strike": _num(row.get("long_strike")),
        "contracts": _num(row.get("contracts"), 1),
        "entry_price": _num(row.get("entry_price"), 0),
        "account": str(row.get("account") or "Brokerage")[:80],
        "notes": str(row.get("notes") or "")[:1000],
        "opened_at": str(row.get("opened_at") or "")[:10] or None,
    }


def option_position_db_row(user_id: str, portfolio_id: str, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    row = normalize_option_position(raw)
    if not row["underlying"] or not row["expiration"]:
        return None
    if row["strategy"] == "single" and row["strike"] is None:
        return None
    if row["strategy"] == "vertical" and (row["short_strike"] is None or row["long_strike"] is None):
        return None
    out = {
        "user_id": user_id,
        "portfolio_id": portfolio_id,
        "strategy": row["strategy"],
        "spread_type": row["spread_type"],
        "underlying": row["underlying"],
        "option_type": row["option_type"],
        "position_side": row["position_side"],
        "expiration": row["expiration"],
        "strike": row["strike"],
        "short_strike": row["short_strike"],
        "long_strike": row["long_strike"],
        "contracts": row["contracts"],
        "entry_price": row["entry_price"],
        "account": row["account"],
        "notes": row["notes"],
    }
    if row.get("opened_at"):
        out["opened_at"] = row["opened_at"]
    cleaned_id = _clean_uuid(row.get("id"))
    if cleaned_id:
        out["id"] = cleaned_id
    return out


def load_cloud_bundle(user: Dict[str, Any]) -> Dict[str, Any]:
    user_id = user["id"]
    profile = ensure_profile(user)
    portfolio = ensure_default_portfolio(user_id)
    settings = ensure_settings(user_id)
    portfolio_id = portfolio["id"]
    holdings = _select("holdings", {"select": "*", "user_id": f"eq.{user_id}", "portfolio_id": f"eq.{portfolio_id}", "order": "created_at.desc"})
    cash = _select("cash_entries", {"select": "*", "user_id": f"eq.{user_id}", "portfolio_id": f"eq.{portfolio_id}", "order": "created_at.desc"})
    watchlist = _select("watchlist", {"select": "*", "user_id": f"eq.{user_id}", "order": "created_at.asc"})
    option_positions = _optional_select("option_positions", {"select": "*", "user_id": f"eq.{user_id}", "portfolio_id": f"eq.{portfolio_id}", "order": "created_at.desc"})
    return {
        "profile": profile,
        "portfolio": portfolio,
        "holdings": holdings,
        "cash": cash,
        "watchlist": watchlist,
        "option_positions": option_positions,
        "settings": settings,
    }


def save_cloud_bundle(user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = user["id"]
    ensure_profile(user)
    portfolio = ensure_default_portfolio(user_id)
    portfolio_id = portfolio["id"]

    raw_holdings = payload.get("holdings") or []
    raw_cash = payload.get("cash") or []
    raw_watchlist = payload.get("watchlist") or []
    raw_settings = payload.get("settings") or {}
    raw_option_positions = payload.get("option_positions") or payload.get("options") or []

    # Replace the user portfolio rows. This keeps the browser state as source-of-truth for v50.
    _delete("holdings", {"user_id": f"eq.{user_id}", "portfolio_id": f"eq.{portfolio_id}"})
    _delete("cash_entries", {"user_id": f"eq.{user_id}", "portfolio_id": f"eq.{portfolio_id}"})
    _optional_delete("option_positions", {"user_id": f"eq.{user_id}", "portfolio_id": f"eq.{portfolio_id}"})
    _delete("watchlist", {"user_id": f"eq.{user_id}"})

    holdings_rows = []
    for h in raw_holdings if isinstance(raw_holdings, list) else []:
        symbol = _clean_symbol(h.get("symbol"))
        if not symbol:
            continue
        row = {
            "user_id": user_id,
            "portfolio_id": portfolio_id,
            "symbol": symbol,
            "shares": _num(h.get("shares")),
            "average_cost": _num(h.get("average_cost", h.get("avg_cost"))),
            "account": str(h.get("account") or "Brokerage")[:80],
            "notes": str(h.get("notes") or "")[:1000],
        }
        cleaned_id = _clean_uuid(h.get("id"))
        if cleaned_id:
            row["id"] = cleaned_id
        holdings_rows.append(row)
    if holdings_rows:
        _insert("holdings", holdings_rows)

    cash_rows = []
    for c in raw_cash if isinstance(raw_cash, list) else []:
        row = {
            "user_id": user_id,
            "portfolio_id": portfolio_id,
            "account": str(c.get("account") or "Cash")[:80],
            "amount": _num(c.get("amount")),
        }
        cleaned_id = _clean_uuid(c.get("id"))
        if cleaned_id:
            row["id"] = cleaned_id
        cash_rows.append(row)
    if cash_rows:
        _insert("cash_entries", cash_rows)

    option_rows = []
    for o in raw_option_positions if isinstance(raw_option_positions, list) else []:
        if not isinstance(o, dict):
            continue
        row = option_position_db_row(user_id, portfolio_id, o)
        if row:
            option_rows.append(row)
    if option_rows:
        # Do not silently drop user-entered option contracts if the v51 table has not been created.
        _insert("option_positions", option_rows)

    seen = set()
    watch_rows = []
    for w in raw_watchlist if isinstance(raw_watchlist, list) else []:
        symbol = _clean_symbol(w.get("symbol") if isinstance(w, dict) else w)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        watch_rows.append({"user_id": user_id, "symbol": symbol, "notes": str(w.get("notes") or "")[:500] if isinstance(w, dict) else ""})
    if watch_rows:
        _insert("watchlist", watch_rows)

    settings_update = {"user_id": user_id}
    if isinstance(raw_settings, dict):
        if raw_settings.get("theme") in {"light", "dark", "system"}:
            settings_update["theme"] = raw_settings.get("theme")
        if "hide_portfolio_value" in raw_settings:
            settings_update["hide_portfolio_value"] = bool(raw_settings.get("hide_portfolio_value"))
        if raw_settings.get("default_screener_universe"):
            settings_update["default_screener_universe"] = str(raw_settings.get("default_screener_universe"))[:80]
        if raw_settings.get("default_screener_scan_size"):
            settings_update["default_screener_scan_size"] = int(_num(raw_settings.get("default_screener_scan_size"), 100))
        app_preferences = raw_settings.get("app_preferences") if isinstance(raw_settings.get("app_preferences"), dict) else {}
        ai_preferences = raw_settings.get("ai_preferences") if isinstance(raw_settings.get("ai_preferences"), dict) else {}
        if app_preferences:
            settings_update["app_preferences"] = app_preferences
        if ai_preferences:
            settings_update["ai_preferences"] = ai_preferences
    _upsert("user_settings", settings_update, "user_id")

    return load_cloud_bundle(user)


def save_account_settings(user: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    user_id = user["id"]
    ensure_profile(user)
    existing = ensure_settings(user_id)
    app_prefs = existing.get("app_preferences") or {}
    ai_prefs = existing.get("ai_preferences") or {}
    if not isinstance(app_prefs, dict):
        app_prefs = {}
    if not isinstance(ai_prefs, dict):
        ai_prefs = {}

    update: Dict[str, Any] = {"user_id": user_id}
    theme = payload.get("theme")
    if theme in {"light", "dark", "system"}:
        update["theme"] = theme
    if "hide_portfolio_value" in payload:
        update["hide_portfolio_value"] = bool(payload.get("hide_portfolio_value"))
    if payload.get("default_ticker"):
        app_prefs["default_ticker"] = _clean_symbol(payload.get("default_ticker")) or "SPY"
    if payload.get("default_range"):
        app_prefs["default_range"] = str(payload.get("default_range"))[:20]
    if payload.get("answer_style"):
        ai_prefs["answer_style"] = str(payload.get("answer_style"))[:30]
    if payload.get("ai_mode"):
        ai_prefs["ai_mode"] = str(payload.get("ai_mode"))[:30]
    update["app_preferences"] = app_prefs
    update["ai_preferences"] = ai_prefs
    rows = _upsert("user_settings", update, "user_id")
    return rows[0] if rows else update
