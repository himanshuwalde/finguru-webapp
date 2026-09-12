"""
FinGuru Financial Health Score Engine
=====================================
Deterministic, weighted composite built from REAL user data:

  Savings rate      25%   (income minus spend, relative to income)
  Spending discipline 20%  (expense-to-income ratio)
  Debt load         15%   (liabilities relative to assets)
  Investment allocation 15% (portfolio health score: allocation vs risk,
                             concentration, diversification)
  Tax efficiency    10%   (effective tax rate on gross income)
  FIRE readiness    15%   (Monte-Carlo probability of FIRE)

Every input is a plain float/dict — pure function, unit-testable, DB-free.
Missing data contributes 0 to its pillar and raises a `missing_data` flag
(the honest score: "record this to find out"). The same Overview dict feeds
the unified Dashboard AND the AI chatbot's grounding.
"""
from __future__ import annotations

from typing import Dict, List

# Weight → score key. Kept as data so the formula is transparent for the viva.
WEIGHTS = [
    ("savings", "Savings Rate", 0.25),
    ("spending", "Spending Discipline", 0.20),
    ("debt", "Debt Load", 0.15),
    ("investment", "Investment Allocation", 0.15),
    ("tax", "Tax Efficiency", 0.10),
    ("fire", "FIRE Readiness", 0.15),
]


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _sub_scores(f: Dict) -> Dict[str, float]:
    """Compute each pillar's 0–100 score from the financial inputs."""

    # --- savings rate ----------------------------------------------------
    income = f.get("monthly_income", 0.0)
    expense = f.get("monthly_expense", 0.0)
    if income > 0:
        rate = (income - expense) / income
        savings = _clamp(rate / 0.30 * 100.0)  # 30%+ savings = perfect score
    else:
        rate, savings = 0.0, 0.0

    # --- spending discipline -------------------------------------------
    if income > 0:
        # 50% of income spent on living = perfect; spending everything = 0.
        spending = _clamp(100.0 - max(0.0, (expense / income - 0.5) * 200.0))
    else:
        spending = 0.0

    # --- debt load --------------------------------------------------------
    liabilities = f.get("total_liabilities", 0.0)
    assets = f.get("total_assets", 0.0)
    if liabilities <= 0:
        debt = 100.0
    elif assets > 0:
        debt = _clamp(100.0 * (1.0 - liabilities / assets))
    else:
        debt = 0.0

    # --- investment allocation (portfolio health) -----------------------
    investment = _clamp(f.get("portfolio_health_score", 0.0))

    # --- tax efficiency ----------------------------------------------------
    effective_rate = f.get("effective_tax_rate", 0.0)  # % of gross income paid
    if f.get("has_tax_data"):
        tax = _clamp(100.0 * max(0.0, 1.0 - effective_rate / 30.0))
    else:
        tax = 0.0

    # --- FIRE readiness ---------------------------------------------------
    prob = f.get("fire_probability_pct", 0.0)
    fire = _clamp(prob) if f.get("has_fire_data") else 0.0

    return {
        "savings": savings, "spending": spending, "debt": debt,
        "investment": investment, "tax": tax, "fire": fire,
        "_savings_rate": rate,
    }


def _flags(scores: Dict[str, float], f: Dict) -> List[Dict]:
    """Deterministic rule-based flags ('what the numbers say'), no AI."""
    flags: List[Dict] = []

    rate = scores.get("_savings_rate", 0.0)
    income = f.get("monthly_income", 0.0)
    expense = f.get("monthly_expense", 0.0)
    if income > 0 and rate < 0.10:
        flags.append({"severity": "danger",
                      "message": f"Savings rate is only {rate*100:.0f}% — target "
                                 "20–30% to build wealth steadily."})
    if income > 0 and expense >= income:
        flags.append({"severity": "danger",
                      "message": "Spending matches or exceeds income — run the "
                                 "Ghost Spend Auditor to find leaky categories."})
    assets = f.get("total_assets", 0.0)
    liabilities = f.get("total_liabilities", 0.0)
    if assets > 0 and liabilities / max(assets, 1.0) > 0.40:
        flags.append({"severity": "warning",
                      "message": f"Liabilities are {liabilities/assets*100:.0f}% "
                                 "of assets — high debt drags your net worth."})
    if f.get("invested_current", 0.0) <= 0:
        flags.append({"severity": "warning",
                      "message": "No investments yet — add one in the Portfolio "
                                 "page to power the Investment pillar."})
    if f.get("has_tax_data") and (f.get("potential_tax_saving", 0.0) or 0.0) > 0:
        flags.append({"severity": "warning",
                      "message": f"The {f.get('recommended_regime','new').upper()} "
                                 f"regime could save ₹{f['potential_tax_saving']:,.0f}."})
    if f.get("has_fire_data") and f.get("fire_probability_pct", 0.0) < 40:
        flags.append({"severity": "warning",
                      "message": f"Only {f['fire_probability_pct']:.0f}% Monte-Carlo "
                                 "chance of retiring on time — raise monthly "
                                 "investment in FIRE Planner."})
    if not flags:
        flags.append({"severity": "positive",
                      "message": "Your finances look well balanced. Keep the "
                                 "savings rate and contributions up!"})
    return flags


def compute_health_score(financial: Dict) -> Dict:
    """
    financial = the real-data context dict built by recommendation_service
                (keys: monthly_income, monthly_expense, total_assets,
                 total_liabilities, portfolio_health_score, effective_tax_rate,
                 has_tax_data, potential_tax_saving, recommended_regime,
                 fire_probability_pct, has_fire_data, invested_current, …)
    """
    scores = _sub_scores(financial)

    components: List[Dict] = []
    overall = 0.0
    for key, label, weight in WEIGHTS:
        val = scores[key]
        overall += val * weight
        components.append({
            "key": key, "label": label, "score": round(val),
            "weight": weight, "contribution": round(val * weight, 1),
        })

    overall = round(overall)
    missing = not (financial.get("has_tax_data")
                   and financial.get("has_fire_data")
                   and financial.get("monthly_income", 0.0) > 0
                   and financial.get("invested_current", 0.0) > 0)

    return {
        "overall": overall,
        "components": components,
        "flags": _flags(scores, financial),
        "missing_data": missing,
        "verb": ("Excellent" if overall >= 85 else "Good" if overall >= 70
                 else "Fair" if overall >= 50 else "Needs work"),
    }