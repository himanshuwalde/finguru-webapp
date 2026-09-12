"""
FinGuru Portfolio Engine
========================
Pure, deterministic analytics for a manually-tracked investment portfolio:
stocks / mutual funds / FDs / gold / property / other.

Inputs are plain dicts (one per holding) so the engine is unit-testable and
DB-free. All return/ROI/XIRR/allocation/health math lives here — the LLM only
explains these figures (via ai/context_builder.py).

Assumptions (documented for viva):
  * "Equity" = Stock + Mutual Fund; "Stable" = FD/Gold/Property/Other.
  * FD current value uses principal × (1 + annual_rate)^elapsed_years (approx).
  * XIRR uses a bisection solver over the IRR equation; guaranteed convergence
    for the usual one-sign-change cashflow (buys → one terminal sale).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

EQUITY_TYPES = {"Stock", "Mutual Fund"}
STABLE_TYPES = {"FD", "Gold", "Property", "Other"}

# Target equity weight by declared risk tolerance (used by the health score).
RISK_TARGET: Dict[str, float] = {
    "Very Conservative": 20.0,
    "Moderate": 50.0,
    "Aggressive": 70.0,
    "Wall Street Bets": 90.0,
}

DAYS_PER_YEAR = 365.25


# ------------------------------------------------------------ date helpers


def _to_date(value) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.date() if isinstance(value, datetime) else value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            pass
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _years_between(start: date, end: date) -> float:
    return max(0.0, (end - start).days / DAYS_PER_YEAR)


# ------------------------------------------------------------ FD valuation


def fd_current_value(principal: float, annual_rate: float,
                     start_date: date, as_of: date,
                     maturity_date: Optional[date] = None) -> float:
    """
    Approximate current value of an FD: principal grows at the annual rate,
    compounded over the elapsed or full maturity term.
    """
    if start_date >= as_of:
        return float(principal)
    term_years = _years_between(start_date, as_of)
    if maturity_date and as_of >= maturity_date:
        term_years = max(term_years, _years_between(start_date, maturity_date))
    return principal * (1.0 + annual_rate / 100.0) ** term_years


# ------------------------------------------------------------ normalisation


def _f(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def resolve_holdings(investments: List[Dict],
                     as_of: date | None = None) -> List[Dict]:
    """
    Normalise raw DB rows into engine-grade holdings with resolved
    invested_amount / current_value / valuation date.
    """
    as_of = as_of or date.today()
    out = []
    for row in investments:
        asset_type = str(row.get("asset_type") or "Other")
        qty, buy = _f(row.get("quantity")), _f(row.get("buy_price"))
        units, pnav = _f(row.get("units")), _f(row.get("purchase_nav"))
        cprice, cnav = _f(row.get("current_price")), _f(row.get("current_nav"))
        principal, rate = _f(row.get("principal")), _f(row.get("interest_rate") or 0)
        start = _to_date(row.get("start_date")) or _to_date(row.get("purchased_on"))
        maturity = _to_date(row.get("maturity_date"))

        # --- invested amount ----------------------------------------------
        invested = None
        if qty is not None and buy is not None:
            invested = qty * buy
        elif units is not None and pnav is not None:
            invested = units * pnav
        elif principal is not None:
            invested = principal
        else:
            invested = _f(row.get("invested_amount")) or 0.0

        # --- current value ------------------------------------------------
        current = None
        if qty is not None and cprice is not None:
            current = qty * cprice
        elif units is not None and cnav is not None:
            current = units * cnav
        elif asset_type == "FD" and principal is not None and start is not None:
            current = fd_current_value(principal, rate or 0.0, start, as_of, maturity)
        else:
            stored = _f(row.get("current_value"))
            current = stored if stored is not None else invested

        out.append({
            "name": str(row.get("name") or "Unnamed"),
            "asset_type": asset_type,
            "invested_amount": invested,
            "current_value": current,
            "date": start,
        })
    return out


# ------------------------------------------------------------------ metrics


def xirr(cashflows: List[float], dates: List[date],
         guess: float = 0.1) -> Optional[float]:
    """
    Return the internal rate of return for irregular cashflows (XIRR) as a
    fraction (0.10 == 10%), or None if no root is found.
    """
    if not cashflows or len(cashflows) != len(dates) or len(cashflows) < 2:
        return None
    d0 = min(dates)
    years = [((d - d0).days / DAYS_PER_YEAR) for d in dates]

    def npv(rate: float) -> float:
        total = 0.0
        for cf, y in zip(cashflows, years):
            total += cf / (1.0 + rate) ** y
        return total

    # Bisection on rate: NPV falls monotonically with r for a single IRR.
    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None  # no sign change — no usable root
    for _ in range(250):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < 1e-7:
            return mid
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def portfolio_summary(investments: List[Dict],
                      as_of: date | None = None) -> Dict:
    """Aggregate invested/current/return/allocation/XIRR for the portfolio."""
    holdings = resolve_holdings(investments, as_of)
    if not holdings:
        return {
            "as_of": (as_of or date.today()).isoformat(),
            "total_invested": 0.0, "total_current": 0.0,
            "absolute_return": 0.0, "return_pct": 0.0, "xirr_pct": 0.0,
            "allocation": [], "holdings": [],
        }

    total_invested = sum(h["invested_amount"] for h in holdings)
    total_current = sum(h["current_value"] for h in holdings)
    absolute_return = total_current - total_invested
    return_pct = (absolute_return / total_invested * 100) if total_invested else 0.0

    # --- allocation by asset class ----------------------------------------
    by_class: Dict[str, dict] = {}
    for h in holdings:
        b = by_class.setdefault(h["asset_type"], {"invested": 0.0, "current": 0.0})
        b["invested"] += h["invested_amount"]
        b["current"] += h["current_value"]
    allocation = [
        {
            "asset_type": k,
            "invested": v["invested"],
            "current": v["current"],
            "pct": (v["current"] / total_current * 100) if total_current else 0.0,
        }
        for k, v in sorted(by_class.items(), key=lambda kv: -kv[1]["current"])
    ]

    # --- per-holding + portfolio XIRR -------------------------------------
    holding_out = []
    for h in holdings:
        held_pct = ((h["current_value"] - h["invested_amount"])
                    / h["invested_amount"] * 100) if h["invested_amount"] else 0.0
        hb_xirr = None
        if h["date"]:
            hb_xirr = xirr([-h["invested_amount"], h["current_value"]],
                           [h["date"], as_of or date.today()])
        holding_out.append({
            **h,
            "date": h["date"].isoformat() if h["date"] else None,
            "return_pct": held_pct,
            "xirr_pct": (hb_xirr * 100) if hb_xirr is not None else 0.0,
        })

    # portfolio-level XIRR: all buys + current value as terminal liquidation
    port_xirr = 0.0
    flow_dates = [h["date"] for h in holdings if h["date"]]
    if len(flow_dates) == len(holdings):
        cf = [-h["invested_amount"] for h in holdings] + [total_current]
        ds = flow_dates + [as_of or date.today()]
        irr = xirr(cf, ds)
        port_xirr = (irr * 100) if irr is not None else 0.0

    return {
        "as_of": (as_of or date.today()).isoformat(),
        "total_invested": total_invested,
        "total_current": total_current,
        "absolute_return": absolute_return,
        "return_pct": return_pct,
        "xirr_pct": port_xirr,
        "allocation": allocation,
        "holdings": holding_out,
    }


# ------------------------------------------------------------ health score


def portfolio_health(investments: List[Dict],
                     risk_tolerance: str = "Moderate",
                     as_of: date | None = None) -> Tuple[int, List[str]]:
    """
    Portfolio Health Score (0–100) from real data:
      40% allocation-vs-risk-tolerance   (how close equity% is to the target)
      30% concentration (Herfindahl-Hirschman index over holdings)
      30% diversification (spread across asset classes and count)
    Returns (score, [insight strings]).
    """
    holdings = resolve_holdings(investments, as_of)
    summary = portfolio_summary(investments, as_of)
    insights: List[str] = []
    if not holdings:
        return 0, ["No holdings yet — start by adding an investment."]

    total_current = summary["total_current"]
    if total_current <= 0:
        return 0, ["Portfolio has no current value to assess."]

    equity_current = sum(h["current_value"] for h in holdings
                         if h["asset_type"] in EQUITY_TYPES)
    equity_pct = equity_current / total_current * 100
    target = RISK_TARGET.get(risk_tolerance, 50.0)

    alloc_score = max(0.0, 100.0 - abs(equity_pct - target) * 1.5)

    # Herfindahl-Hirschman over holding weights (1 = one single holding).
    weights = [h["current_value"] / total_current for h in holdings]
    hhi = sum(w * w for w in weights)
    conc_score = max(0.0, (1.0 - min(hhi, 1.0)) * 100.0)

    num_classes = len(set(h["asset_type"] for h in holdings))
    divers_score = min(100.0, 20.0 + 15.0 * num_classes + 8.0 * min(len(holdings), 6))

    score = round(0.40 * alloc_score + 0.30 * conc_score + 0.30 * divers_score)

    if equity_pct > target + 25:
        insights.append(
            f"Equity exposure is ~{equity_pct:.0f}% vs your {risk_tolerance} "
            f"target of {target:.0f}% — consider rebalancing toward stable assets.")
    elif equity_pct < target - 25:
        insights.append(
            f"Your portfolio is ~{equity_pct:.0f}% equity — well below your "
            f"{risk_tolerance} target; growth assets may be under-represented.")
    if hhi > 0.5:
        insights.append(f"Concentration is high (largest position is "
                        f"{max(weights) * 100:.0f}% of the portfolio).")
    num_types = len([a for a in summary["allocation"]])
    if num_types < 3:
        insights.append("Consider diversifying across at least 3 asset classes.")

    if not insights:
        insights.append("Portfolio looks well balanced for your risk profile.")
    return score, insights