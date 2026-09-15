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


# ------------------------------------------------------------ rebalancing


def rebalancing_plan(investments: List[Dict],
                     risk_tolerance: str = "Moderate",
                     as_of: date | None = None) -> Dict:
    """
    Deterministic rebalancing suggestions: close the gap between the current
    allocation and the risk-tolerance target, tilted toward better performers.

    The equity/stable split is anchored on RISK_TARGET (same as the health
    score, so the two features never contradict each other); within a bucket,
    each holding's ideal share is proportional to (1 + return_pct/100), so
    winners absorb the additions and laggards take the reductions.

    Returns a plan dict:
      plan_status       : "rebalance" | "balanced" | "diversify" | "skip"
      headline          : one-line status for the UI
      current_equity_pct / target_equity_pct : floats
      equity_delta      : ₹ to move INTO equity (negative = reduce equity)
      trades            : [{"from": {name, asset_type}, "to": {name, asset_type},
                            "amount": float, "reason": str}] — funded moves
      adds              : [{"name", "asset_type", "amount", "reason"}] — new money
      warnings          : [str]
      as_of             : ISO date
    """
    holdings = resolve_holdings(investments, as_of)
    total = sum(h["current_value"] for h in holdings)
    as_of_str = (as_of or date.today()).isoformat()

    if len(holdings) < 2 or total <= 0:
        return {
            "plan_status": "skip",
            "headline": "Add at least two holdings to see rebalancing suggestions.",
            "current_equity_pct": 0.0,
            "target_equity_pct": RISK_TARGET.get(risk_tolerance, 50.0),
            "equity_delta": 0.0,
            "trades": [], "adds": [], "warnings": [],
            "as_of": as_of_str,
        }

    # Per-holding return (same formula portfolio_summary uses per holding).
    for h in holdings:
        invested = h["invested_amount"]
        h["return_pct"] = (((h["current_value"] - invested) / invested) * 100
                           if invested else 0.0)

    equity = [h for h in holdings if h["asset_type"] in EQUITY_TYPES]
    stable = [h for h in holdings if h["asset_type"] not in EQUITY_TYPES]
    equity_current = sum(h["current_value"] for h in equity)

    target_equity_pct = RISK_TARGET.get(risk_tolerance, 50.0)
    current_equity_pct = equity_current / total * 100.0
    target_equity_value = target_equity_pct / 100.0 * total
    target_stable_value = total - target_equity_value
    equity_delta = target_equity_value - equity_current

    warnings: List[str] = []

    # The bucket the target calls for isn't held at all → diversification ask.
    def _diversify_plan(headline: str) -> Dict:
        return {
            "plan_status": "diversify",
            "headline": headline,
            "current_equity_pct": current_equity_pct,
            "target_equity_pct": target_equity_pct,
            "equity_delta": equity_delta,
            "trades": [], "adds": [], "warnings": [headline],
            "as_of": as_of_str,
        }

    if equity_delta > 0 and not equity:
        return _diversify_plan(
            f"Everything you hold is a stable asset, but your {risk_tolerance} "
            f"target wants ~{target_equity_pct:.0f}% in growth. Add a stock or "
            f"mutual-fund position to move toward it.")
    if equity_delta < 0 and not stable:
        return _diversify_plan(
            f"Everything you hold is equity, but your {risk_tolerance} target "
            f"wants {target_equity_pct:.0f}% in growth. Add an FD, Gold or "
            f"Property position to lower risk.")

    # Winner-tilted ideal value for each holding within its own bucket.
    def _apply_ideal(bucket: List[Dict], size: float) -> None:
        weights = [max(0.05, 1.0 + h["return_pct"] / 100.0) for h in bucket]
        total_w = sum(weights)
        for h, w in zip(bucket, weights):
            h["_ideal"] = w / total_w * size

    _apply_ideal(equity, target_equity_value)
    _apply_ideal(stable, target_stable_value)

    thr = max(1000.0, 0.01 * total)           # ignore sub-₹1k / <1% moves
    trims: List[Tuple[Dict, float]] = []      # (holding, ₹ to free)
    adds: List[Tuple[Dict, float]] = []       # (holding, ₹ to invest)
    for h in holdings:
        gap = h["_ideal"] - h["current_value"]
        if gap >= thr:
            adds.append((h, gap))
        elif gap <= -thr:
            trims.append((h, -gap))

    trims.sort(key=lambda t: (t[0]["return_pct"], t[0]["name"]))     # weak first
    adds.sort(key=lambda t: (-t[0]["return_pct"], t[0]["name"]))     # strong first

    # Pair reductions with additions into funded trades.
    trades: List[Dict] = []
    ti = ai = 0
    while ti < len(trims) and ai < len(adds):
        t_h, t_amt = trims[ti]
        a_h, a_amt = adds[ai]
        move = int(round(min(t_amt, a_amt)))
        if move >= 1000:
            trades.append({
                "from": {"name": t_h["name"], "asset_type": t_h["asset_type"]},
                "to": {"name": a_h["name"], "asset_type": a_h["asset_type"]},
                "amount": move,
                "reason": (f"Trim {t_h['name']} ({t_h['return_pct']:+.1f}%) — "
                           f"the weaker performer — to fund {a_h['name']} "
                           f"({a_h['return_pct']:+.1f}%), the stronger one."),
            })
        trims[ti] = (t_h, t_amt - move)
        adds[ai] = (a_h, a_amt - move)
        if t_amt - move < 1000:
            ti += 1
        if a_amt - move < 1000:
            ai += 1

    # Additions left unpaired need new money.
    adds_out: List[Dict] = []
    for h, amt in adds[ai:]:
        if amt >= 1000:
            adds_out.append({
                "name": h["name"],
                "asset_type": h["asset_type"],
                "amount": int(round(amt)),
                "reason": (f"{h['name']} sits below its target weight — top it "
                           f"up with fresh capital."),
            })

    # Reductions left unpaired → freed cash with no obvious home.
    leftover_freed = int(round(sum(amt for _, amt in trims[ti:])))
    if leftover_freed >= 1000:
        warnings.append(
            f"Trimming the weaker holdings frees about ₹{leftover_freed:,} with "
            f"no under-allocated holding to absorb it — reinvest it into a new "
            f"position or hold it for a market dip.")

    if trades or adds_out or warnings:
        n_moves = len(trades) + len(adds_out)
        headline = (
            f"{n_moves} rebalancing move{'s' if n_moves != 1 else ''} suggested: "
            f"{target_equity_pct:.0f}% growth is your {risk_tolerance} target — "
            f"redeploying toward stronger performers.")
        plan_status = "rebalance"
    else:
        plan_status = "balanced"
        headline = (f"Your portfolio already matches your {risk_tolerance} "
                    f"allocation — no rebalancing needed.")

    return {
        "plan_status": plan_status,
        "headline": headline,
        "current_equity_pct": current_equity_pct,
        "target_equity_pct": target_equity_pct,
        "equity_delta": equity_delta,
        "trades": trades,
        "adds": adds_out,
        "warnings": warnings,
        "as_of": as_of_str,
    }