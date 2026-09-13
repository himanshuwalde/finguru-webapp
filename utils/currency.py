"""
Preferred-currency display module — single source of truth for how money is
written on screen and inside LLM prompts.

Contract:
- All amounts are stored in INR (rupees) in the database. Engines and rules
  keep working in INR.
- When the user's preferred currency is INR: we relabel only (symbol ₹).
- When viewing in another currency: we apply the live INR → target rate.
- The FX API (open.er-api.com) returns INR→X rates; since all stored amounts
  are INR, this is sufficient for INR→X conversion.
- If the FX API is unreachable, `to_display` degrades to a 1.0 rate (symbol
  still swaps, values unchanged) so the app never breaks.
- `default_code()` returns "INR" outside a Streamlit session, keeping the
  offline tests byte-for-byte identical to before.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Dict

# Curated set offered in Profile & Settings (order = dropdown order).
CURRENCIES: Dict[str, Dict[str, str]] = {
    "INR": {"symbol": "₹", "name": "Indian Rupee"},
    "USD": {"symbol": "$", "name": "US Dollar"},
    "EUR": {"symbol": "€", "name": "Euro"},
    "GBP": {"symbol": "£", "name": "British Pound"},
    "JPY": {"symbol": "¥", "name": "Japanese Yen"},
    "AUD": {"symbol": "A$", "name": "Australian Dollar"},
    "CAD": {"symbol": "C$", "name": "Canadian Dollar"},
    "SGD": {"symbol": "S$", "name": "Singapore Dollar"},
    "AED": {"symbol": "AED ", "name": "UAE Dirham"},
    "CHF": {"symbol": "CHF ", "name": "Swiss Franc"},
}

DEFAULT_CODE = "INR"

# Base is fixed to INR because every stored amount is in rupees.
_DEFAULT_FX_URL = "https://open.er-api.com/v6/latest/INR"
_RATE_TTL_SECONDS = 12 * 3600  # 12h cache


def _code() -> str:
    """The user's preferred currency code, safe to call outside Streamlit."""
    try:
        import streamlit as st
        return st.session_state.get("preferred_currency", DEFAULT_CODE) or DEFAULT_CODE
    except Exception:
        return DEFAULT_CODE


def default_code() -> str:
    return _code()


def symbol(code: str | None = None) -> str:
    """Display symbol for a currency (defaults to the preferred one)."""
    code = code or _code()
    return CURRENCIES.get(code, CURRENCIES[DEFAULT_CODE])["symbol"]


def currency_name(code: str | None = None) -> str:
    code = code or _code()
    return CURRENCIES.get(code, CURRENCIES[DEFAULT_CODE])["name"]


_rates_cache: Dict[str, object] = {}
_rates_lock = threading.Lock()


def get_rates() -> Dict[str, float]:
    """INR→currency rates. Cached ~12h per endpoint (module-level TTL cache,
    so pages with dozens of money values never hammer the API). Returns {} on
    any failure (callers fall back to a 1.0 rate). `FX_API_URL` can override
    the endpoint for tests."""
    import json
    import urllib.request

    url = os.environ.get("FX_API_URL") or _DEFAULT_FX_URL
    now = time.time()
    cached = _rates_cache.get(url)
    if cached and (now - cached["ts"]) < _RATE_TTL_SECONDS:
        return cached["data"]

    payload: Dict[str, float] = {}
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
        rates = data.get("rates") or {}
        payload = {"INR": 1.0}
        for code in CURRENCIES:
            val = rates.get(code)
            if isinstance(val, (int, float)) and val and code != "INR":
                payload[code] = float(val)
    except Exception:
        payload = {}
    with _rates_lock:
        _rates_cache[url] = {"ts": now, "data": payload}
    return payload


def _rate(rate_map: Dict[str, float], code: str) -> float:
    """Get the INR→currency rate for a given code."""
    return rate_map.get(code, 1.0)


def to_display(value: float, code: str | None = None) -> float:
    """Convert a stored INR value into the user's display currency.

    Since all stored amounts are in INR, we only need INR→target rates.
    This is a 1-step conversion: INR amount × INR→target rate = target amount.
    """
    code = code or _code()
    if code == DEFAULT_CODE:
        return float(value)
    return float(value) * _rate(get_rates(), code)


def to_inr(value: float, from_code: str | None = None) -> float:
    """Convert an amount from any currency to INR for storage.

    User enters in their preferred currency (e.g., $100), we convert to INR
    (e.g., ₹8,333) before storing in the database.

    Example: to_inr(100, "USD") with rate 0.012 → 100 / 0.012 = 8333.33 INR
    """
    from_code = from_code or _code()
    if from_code == DEFAULT_CODE:
        return float(value)

    # Get the INR→from_code rate, then invert to get from_code→INR
    # e.g., INR→USD = 0.012, so USD→INR = 1/0.012 = 83.33
    rate = _rate(get_rates(), from_code)
    if rate == 0 or rate == 1.0:
        return float(value)  # Fallback: assume already INR or no rate
    return float(value) / rate


def fmt_input_label(text: str, code: str | None = None) -> str:
    """Format input label with currency symbol - e.g., 'Amount' -> 'Amount ($)'
    for non-INR currencies, 'Amount' -> 'Amount (₹)' for INR."""
    code = code or _code()
    sym = symbol(code)
    # Replace (₹) or ($) etc with (symbol)
    import re
    # Match any currency in parentheses at end of string
    pattern = r'\s*\([^)]+\)\s*$'
    if re.search(pattern, text):
        return re.sub(pattern, f" ({sym})", text)
    return f"{text} ({sym})"


def fmt_money(value: float, dp: int = 0, code: str | None = None) -> str:
    """Format a stored INR amount as the user's preferred currency."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    return f"{symbol(code)}{to_display(v, code):,.{dp}f}"


def fmt_label(text: str, code: str | None = None) -> str:
    """Rewrite a '... (₹)' input/axis label to the display currency symbol,
    e.g. 'Amount (₹)' -> 'Amount ($)'. Leaves non-rupee labels untouched."""
    code = code or _code()
    sym = symbol(code)
    if "₹" in text:
        if code == DEFAULT_CODE:
            return text
        return text.replace("(₹)", f"({sym})")
    return text


def ai_currency_note(code: str | None = None) -> str:
    """Prompt line that tells the model exactly how to write money amounts."""
    code = code or _code()
    sym = symbol(code)
    if code == DEFAULT_CODE:
        return (f"All money amounts you mention must be written with the Indian "
                f"rupee symbol (₹) and INR figures — do not invent an exchange "
                f"rate or change the numbers you are given.")
    return (f"All money amounts you mention must be written in {currency_name(code)} "
            f"using the symbol '{sym}'. The figures in the data are already converted "
            f"to {code} — quote them exactly as given, never apply your own rate or "
            f"convert them yourself.")