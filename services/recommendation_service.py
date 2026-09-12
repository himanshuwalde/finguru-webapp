"""
Recommendation Service — the single financial-context factory.

`build_financial_context(user_id)` gathers the user's real numbers from the
same services the screens use, runs the Health Score engine, and returns ONE
dict. Dashboard, Health Score and the AI chatbot all consume this same
context — so the whole product always agrees on the numbers (unified source
of truth; screens and bot can never disagree).
"""
from __future__ import annotations

from typing import Dict

from supabase import Client

from engines import fire_engine, health_score
from services.database import get_db_service
from services.fire_service import get_fire_service
from services.networth_service import get_networth_service
from services.portfolio_service import get_portfolio_service
from services.tax_service import get_tax_service


def build_financial_context(supabase: Client, user_id: str) -> Dict:
    """Assemble all real-data figures → health score + flags + headline KPIs."""
    db = get_db_service(supabase)
    nw = get_networth_service(supabase)
    pf = get_portfolio_service(supabase)
    tx = get_tax_service(supabase)
    fire = get_fire_service(supabase)

    # ---------------- spending / income (last 3 months) ------------------
    # monthly totals, averaged across months → "typical" monthly income/expense
    monthly_income = 0.0
    monthly_expense = 0.0
    try:
        df = db.get_transactions_dataframe(user_id)
        if not df.empty:
            inc = df[df["type"] == "Income"]
            if len(inc):
                grp = inc.assign(_m=inc["transaction_time"].dt.to_period("M")) \
                    .groupby("_m")["amount"].sum()
                if len(grp):
                    monthly_income = max(0.0, float(grp.mean()))
        exp = db.get_historical_expenses(user_id, months_back=3)
        if not exp.empty:
            grp = exp.assign(_m=exp["transaction_time"].dt.to_period("M")) \
                .groupby("_m")["amount"].sum()
            if len(grp):
                monthly_expense = float(grp.mean())
    except Exception as e:
        print(f"[recommendation] spending read failed: {e}")

    # ------------------------- net worth / assets -------------------------
    try:
        n = nw.compute_networth(user_id)
        total_assets = n["total_assets"]
        total_liabilities = n["total_liabilities"]
        net_worth = n["net_worth"]
        liquid_assets = n["liquid_assets"]
        invested_current = n["investments_total"]
    except Exception as e:
        print(f"[recommendation] networth read failed: {e}")
        total_assets = total_liabilities = net_worth = liquid_assets = 0.0
        invested_current = 0.0

    # ------------------------- portfolio health ---------------------------
    portfolio_health_score = 0.0
    try:
        portfolio_health_score, _ = pf.get_health(user_id, "Moderate")
    except Exception as e:
        print(f"[recommendation] portfolio health failed: {e}")

    # ------------------------------ tax -----------------------------------
    effective_tax_rate, has_tax_data = 0.0, False
    potential_tax_saving, recommended_regime = 0.0, "new"
    try:
        from engines import tax_engine
        profile = tx.get_profile(user_id, "2026-27")
        if profile:
            inputs = tx.profile_to_inputs(profile, "2026-27")
            res = tax_engine.compute_tax(inputs)
            effective_tax_rate = res["effective_tax_rate"]
            potential_tax_saving = res["potential_saving"]
            recommended_regime = res["recommended_regime"]
            has_tax_data = True
    except Exception as e:
        print(f"[recommendation] tax read failed: {e}")

    # ------------------------------ FIRE -----------------------------------
    fire_probability_pct, has_fire_data = 0.0, False
    try:
        profile = fire.get_profile(user_id)
        if profile:
            r = fire_engine.fire_simulation(
                current_age=profile.get("current_age", 22),
                target_retirement_age=profile.get("target_retirement_age", 45),
                monthly_expense=profile.get("monthly_expense", 0),
                monthly_investment=profile.get("monthly_investment", 0),
                current_corpus=profile.get("current_corpus", 0),
                expected_return_pct=profile.get("expected_return_pct", 10),
                inflation_pct=profile.get("inflation_pct", 6),
                safe_withdrawal_rate_pct=profile.get("safe_withdrawal_rate_pct", 4),
                n_simulations=1500, seed=42)
            fire_probability_pct = r["probability_pct"]
            has_fire_data = True
    except Exception as e:
        print(f"[recommendation] fire read failed: {e}")

    financial = {
        "monthly_income": monthly_income,
        "monthly_expense": monthly_expense,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "net_worth": net_worth,
        "liquid_assets": liquid_assets,
        "invested_current": invested_current,
        "portfolio_health_score": portfolio_health_score,
        "effective_tax_rate": effective_tax_rate,
        "has_tax_data": has_tax_data,
        "potential_tax_saving": potential_tax_saving,
        "recommended_regime": recommended_regime,
        "fire_probability_pct": fire_probability_pct,
        "has_fire_data": has_fire_data,
    }
    hs = health_score.compute_health_score(financial)

    return {
        "as_of": None,  # filled by caller if needed (avoid clock in pure path)
        "health_score": hs,
        "financial": financial,
        "kpis": {
            "net_worth": financial["net_worth"],
            "monthly_expense": financial["monthly_expense"],
            "monthly_income": financial["monthly_income"],
            "invested_current": financial["invested_current"],
            "effective_tax_rate": financial["effective_tax_rate"],
            "has_tax_data": financial["has_tax_data"],
            "fire_probability_pct": financial["fire_probability_pct"],
            "has_fire_data": financial["has_fire_data"],
        },
    }


def get_recommendation_service(supabase: Client):
    return {"build_financial_context": lambda uid: build_financial_context(supabase, uid)}


def explain_health(context: Dict) -> str:
    """Deterministic narrative summary of the health score + flags (no AI)."""
    hs = context["health_score"]
    lines = [
        f"Your Financial Health Score is {hs['overall']}/100 ({hs['verb']}).",
    ]
    best = max(hs["components"], key=lambda c: c["contribution"])
    worst = min(hs["components"], key=lambda c: c["contribution"])
    lines.append(f"Strongest pillar: {best['label']} ({best['score']}).")
    lines.append(f"Biggest lever: {worst['label']} ({worst['score']}).")
    if hs["missing_data"]:
        lines.append("Tip: record tax/FIRE/investment data to unlock pillars "
                     "currently scored at 0.")
    for flag in hs["flags"]:
        emoji = {"positive": "✅", "warning": "⚠️", "danger": "🛑"}.get(flag["severity"], "•")
        lines.append(f"{emoji} {flag['message']}")
    return "\n".join(lines)