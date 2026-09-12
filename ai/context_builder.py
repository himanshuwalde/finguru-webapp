"""
Context Builder — deterministic financial "tools" for the CA chatbot.
Every tool reads real user data from Supabase and runs the SAME pure engines
that power the screens. The outputs are serialized into the chatbot prompt,
so the bot can never disagree with the numbers on screen.

Latency / token discipline: the chatbot loads only the tools its intent needs
(see ai/intent_router.py), not the entire financial picture.
"""
from __future__ import annotations

import json
from typing import Callable, Dict, List, Tuple

from supabase import Client

from engines import tax_engine
from services.database import get_db_service
from services.fire_service import get_fire_service
from services.networth_service import get_networth_service
from services.portfolio_service import get_portfolio_service
from services.tax_service import get_tax_service

DEFAULT_AY = "2026-27"


def _fmt_money(v: float) -> str:
    return f"₹{v:,.0f}"


def _pprune(d: Dict, max_chars: int = 1_200_000) -> str:
    """Serialize dict → JSON, trimmed for the prompt (safety cap)."""
    s = json.dumps(d, default=float, indent=1)
    return s[:max_chars]


# ------------------------------------------------------------------- tools


def tool_tax_calculator(supabase: Client, user_id: str) -> Dict:
    """Compute fresh tax (both regimes) from the user's saved declaration."""
    svc = get_tax_service(supabase)
    profile = svc.get_profile(user_id, DEFAULT_AY)
    if not profile:
        return {"status": "no_data",
                "note": "No saved tax declaration — run Tax Planner first."}
    inputs = svc.profile_to_inputs(profile, DEFAULT_AY)
    result = tax_engine.compute_tax(inputs)
    return {
        "status": "ok",
        "assessment_year": DEFAULT_AY,
        "recommended_regime": result["recommended_regime"],
        "potential_saving": result["potential_saving"],
        "regimes": {
            "old": {k: v for k, v in result["regimes"]["old"].items()
                    if k not in ("breakdown",)},
            "new": {k: v for k, v in result["regimes"]["new"].items()
                    if k not in ("breakdown",)},
        },
        "top_deductions": {
            k: v for k, v in result["regimes"]["old"].get("deductions", {}).items()
        },
    }


def tool_tax_saving_opportunities(supabase: Client, user_id: str) -> Dict:
    svc = get_tax_service(supabase)
    profile = svc.get_profile(user_id, DEFAULT_AY)
    if not profile:
        return {"status": "no_data", "opportunities": [],
                "note": "No saved tax declaration — run Tax Planner first."}
    inputs = svc.profile_to_inputs(profile, DEFAULT_AY)
    result = tax_engine.compute_tax(inputs)
    return {
        "status": "ok",
        "assessment_year": DEFAULT_AY,
        "opportunities": result["tax_saving_opportunities"],
    }


def tool_portfolio_summary(supabase: Client, user_id: str) -> Dict:
    svc = get_portfolio_service(supabase)
    s = svc.get_summary(user_id)
    if not s["holdings"]:
        return {"status": "no_data", "note": "No investments added yet.",
                "as_of": s["as_of"]}
    health, insights = svc.get_health(user_id, "Moderate")
    return {
        "status": "ok",
        "as_of": s["as_of"],
        "total_invested": s["total_invested"],
        "total_current": s["total_current"],
        "absolute_return": s["absolute_return"],
        "return_pct": s["return_pct"],
        "xirr_pct": s["xirr_pct"],
        "allocation": s["allocation"],
        "health_score": health,
        "health_insights": insights,
    }


def tool_net_worth(supabase: Client, user_id: str) -> Dict:
    svc = get_networth_service(supabase)
    n = svc.compute_networth(user_id)
    return {
        "status": "ok",
        "as_of": n["as_of"],
        "liquid_assets": n["liquid_assets"],
        "investments_total": n["investments_total"],
        "total_assets": n["total_assets"],
        "total_liabilities": n["total_liabilities"],
        "net_worth": n["net_worth"],
        "liabilities": n["liabilities_breakdown"],
    }


def tool_fire_status(supabase: Client, user_id: str) -> Dict:
    svc = get_fire_service(supabase)
    profile = svc.get_profile(user_id)
    if not profile:
        return {"status": "no_data", "note": "No FIRE profile — run FIRE Planner."}
    # Read-only recompute with a fixed seed so chat never writes to the DB.
    from engines import fire_engine
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
    return {"status": "ok", **r}


def tool_spending_summary(supabase: Client, user_id: str) -> Dict:
    db = get_db_service(supabase)
    exp = db.get_historical_expenses(user_id, months_back=3)
    if exp.empty:
        return {"status": "no_data", "note": "No expense transactions in the "
                                             "last 3 months."}
    exp = exp.assign(_m=exp["transaction_time"].dt.to_period("M"))
    monthly = exp.groupby("_m")["amount"].agg(["sum", "mean"]).reset_index()
    months = [str(r["_m"]) for r in monthly.to_dict("records")]
    return {
        "status": "ok",
        "months_covered": months,
        "avg_monthly_expense": float(monthly["sum"].mean()),
        "last_month_expense": float(monthly.iloc[-1]["sum"]),
        "avg_monthly_income": 0,  # incomes are set by the service below when present
        "note": "Expense figures only; income is captured via Net Worth / FIRE.",
    }


TOOL_REGISTRY: Dict[str, Tuple[str, Callable]] = {
    "tax_calculator": ("Income-tax comparison (old vs new regime)",
                       tool_tax_calculator),
    "tax_saving_opportunities": ("Deterministic tax-saving gaps",
                                 tool_tax_saving_opportunities),
    "portfolio_summary": ("Investment portfolio summary", tool_portfolio_summary),
    "net_worth": ("Net worth / balance sheet", tool_net_worth),
    "fire_status": ("FIRE (retirement) readiness", tool_fire_status),
    "spending_summary": ("Recent monthly spending", tool_spending_summary),
}


def run_tools(supabase: Client, user_id: str,
              tool_names: List[str]) -> Dict[str, Dict]:
    """Execute the requested tools and return {name: result}."""
    out: Dict[str, Dict] = {}
    for name in tool_names:
        fn = TOOL_REGISTRY.get(name)
        if fn:
            try:
                out[name] = fn[1](supabase, user_id)
            except Exception as e:
                out[name] = {"status": "error", "error": str(e)}
    return out


def build_grounding(supabase: Client, user_id: str,
                    tool_names: List[str]) -> str:
    """Serialized grounding JSON for the chatbot prompt (the AI's only data)."""
    results = run_tools(supabase, user_id, tool_names)
    return serialize_results(results)


def serialize_results(results: Dict[str, Dict]) -> str:
    """JSON-serialize an already-built tool-results dict for the prompt."""
    return _pprune(results)