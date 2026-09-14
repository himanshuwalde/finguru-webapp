"""
FinGuru Market Data Service
===========================
Live market prices via yfinance (Yahoo Finance). Used by the Portfolio page to
make the CURRENT PRICE of stocks / mutual funds dynamic instead of the static
value typed at add-time.

Design rules (documented for viva):
  * A fetch NEVER throws back to the caller. Any failure (offline, bad ticker,
    unknown scheme) returns None and the caller silently uses the stored manual
    price — the "manual tracking always works" invariant.
  * Live prices are OVERLAID at read time, never written to Supabase
    (`overlay_live_prices`). `services/portfolio_service.py` still stores the
    user-entered current_price/current_nav as the fallback.
  * Prices are cached per ticker per day for the app process, so repeated page
    reruns within a market day reuse one HTTP call instead of hammering Yahoo.
  * Tooling stays pure/deterministic: if yfinance is not installed, the module
    degrades to the manual fallback instead of crashing the app.
"""
from __future__ import annotations

from datetime import date

try:  # optional third-party — degrade to manual fallback if unavailable
    import yfinance as yf
except Exception:  # pragma: no cover - exercised only when lib missing
    yf = None

# ticker.upper() -> {"price": float, "as_of": "YYYY-MM-DD"}
_cache: dict[str, dict] = {}


def clear_cache() -> None:
    """Drop cached prices (used by the Portfolio "Refresh prices" button)."""
    _cache.clear()


def live_price(ticker: str) -> dict | None:
    """
    Return {"price": float, "as_of": "YYYY-MM-DD"} for a Yahoo ticker, or None
    if the ticker is blank, unresolved, or the network/lib is unavailable.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker or yf is None:
        return None
    today = date.today().isoformat()
    cached = _cache.get(ticker)
    if cached and cached["as_of"] == today:
        return cached
    try:
        hist = yf.Ticker(ticker).history(period="1d")
        if hist is None or hist.empty:
            return None
        price = float(hist["Close"].iloc[-1])
        if price <= 0:
            return None
        out = {"price": price, "as_of": today}
        _cache[ticker] = out
        return out
    except Exception:
        return None


def overlay_live_prices(rows: list[dict]) -> list[dict]:
    """
    Given raw `investments` rows, return NEW rows with current_price /
    current_nav overridden by the live price for any row that (a) has a ticker
    and (b) resolves today. Rows without a resolving ticker pass through
    untouched, keeping their stored manual price. Row order and ids are
    preserved so callers can zip back to the raw rows.
    """
    out = []
    for row in rows:
        ticker = (row.get("ticker") or "").strip().upper()
        if ticker:
            live = live_price(ticker)
            if live:
                if row.get("asset_type") == "Stock":
                    row = {**row, "current_price": live["price"]}
                elif row.get("asset_type") == "Mutual Fund":
                    row = {**row, "current_nav": live["price"]}
        out.append(row)
    return out