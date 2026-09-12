"""
FinGuru Net Worth Engine
========================
Pure, deterministic aggregation of a user's balance sheet:
      Net Worth = Total Assets − Total Liabilities

Data sources (all resolved by the service layer, never the engine):
  * Liquid assets   = Σ accounts.balance          (bank / cash — the app's existing
                                                    accounts already track balances)
  * Investment assets = Σ investments.current_value, grouped by asset class
                                                    (Stock / Mutual Fund / FD / Gold / Property / Other)
  * Liabilities     = rows from the `liabilities` table (outstanding_amount)

The function takes plain numbers/dicts so it is unit-testable without a DB,
and the returned breakdown dict is the single source of truth for both the
screen and the AI chatbot's grounding context.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional


def _f(value) -> float:
    """Coerce to float, safely defaulting to 0.0 for None/garbage."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def networth_snapshot(liquid_assets: float,
                      investments_by_type: Dict[str, float],
                      liabilities: List[Dict],
                      as_of: Optional[str] = None) -> Dict:
    """
    Build a full net-worth snapshot dict from parts.

    liquid_assets         : Σ bank/cash balances (a plain float).
    investments_by_type   : {asset_type: current_value} — exactly the allocation
                            from engines/portfolio_engine.portfolio_summary.
    liabilities           : [{"name", "liability_type", "outstanding_amount"}].

    Returns a breakdown dict that feeds BOTH the page and the AI context.
    """
    inv_total = sum(_f(v) for v in investments_by_type.values())

    assets_breakdown: List[Dict] = [{"name": "Bank & Cash",
                                     "category": "Liquid",
                                     "amount": _f(liquid_assets)}]
    for atype, amount in investments_by_type.items():
        if amount and _f(amount) > 0:
            assets_breakdown.append({"name": atype, "category": "Investment",
                                     "amount": _f(amount)})
    assets_breakdown.sort(key=lambda r: -r["amount"])

    total_assets = _f(liquid_assets) + inv_total

    values: List[Dict] = []
    total_liabilities = 0.0
    for row in liabilities:
        out = _f(row.get("outstanding_amount"))
        total_liabilities += out
        values.append({
            "name": str(row.get("name") or "Liability"),
            "type": str(row.get("liability_type") or "Other"),
            "outstanding_amount": out,
        })
    values.sort(key=lambda r: -r["outstanding_amount"])

    return {
        "as_of": as_of or date.today().isoformat(),
        "liquid_assets": _f(liquid_assets),
        "investments_total": inv_total,
        "investment_breakdown": [
            {"asset_type": k, "current_value": _f(v)}
            for k, v in investments_by_type.items()
            if _f(v) > 0
        ],
        "total_assets": total_assets,
        "assets_breakdown": assets_breakdown,
        "total_liabilities": total_liabilities,
        "liabilities_breakdown": values,
        "net_worth": total_assets - total_liabilities,
    }


def month_key(day: date | None = None) -> str:
    """First-of-month key used to dedupe snapshots (one per calendar month)."""
    d = day or date.today()
    return d.strftime("%Y-%m-01")