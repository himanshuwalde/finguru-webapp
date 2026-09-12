"""
FIRE Service — Supabase persistence + engine orchestration for the
retirement planner. One `fire_profiles` row per user (upserted), a history of
`fire_simulations` runs, and a sensible default monthly expense derived from
the user's real transactions (average spend of recent months).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from supabase import Client

from engines import fire_engine
from services.database import get_db_service


class FireService:
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.db = get_db_service(supabase)

    # ------------------------------------------------------------ read

    def get_profile(self, user_id: str) -> Optional[Dict]:
        try:
            res = self.supabase.table("fire_profiles") \
                .select("*") \
                .eq("user_id", user_id) \
                .maybe_single().execute()
            return res.data
        except Exception:
            return None

    def estimate_monthly_expense(self, user_id: str) -> float:
        """Average monthly spend over the last 3 months of real transactions."""
        try:
            df = self.db.get_historical_expenses(user_id, months_back=3)
            if df.empty:
                return 30000.0
            # %Y-%m group → mean of monthly totals
            monthly = df.assign(_m=df["transaction_time"].dt.to_period("M")) \
                .groupby("_m")["amount"].sum()
            return round(float(monthly.mean()), 0)
        except Exception:
            return 30000.0

    def get_recent_simulations(self, user_id: str, limit: int = 5) -> List[Dict]:
        try:
            res = self.supabase.table("fire_simulations") \
                .select("target_age, required_corpus, projected_corpus, "
                        "probability_pct, p5, p95, created_at") \
                .eq("user_id", user_id) \
                .order("created_at", desc=True) \
                .limit(limit).execute()
            return res.data or []
        except Exception:
            return []

    # ------------------------------------------------------------ write

    def save_profile(self, user_id: str, data: Dict) -> bool:
        try:
            payload = {
                "user_id": user_id,
                "current_age": int(data.get("current_age") or 22),
                "target_retirement_age": int(data.get("target_retirement_age") or 45),
                "monthly_expense": float(data.get("monthly_expense") or 0),
                "monthly_investment": float(data.get("monthly_investment") or 0),
                "current_corpus": float(data.get("current_corpus") or 0),
                "expected_return_pct": float(data.get("expected_return_pct") or 10),
                "inflation_pct": float(data.get("inflation_pct") or 6),
                "safe_withdrawal_rate_pct": float(data.get("safe_withdrawal_rate_pct") or 4),
            }
            self.supabase.table("fire_profiles") \
                .upsert(payload, on_conflict="user_id").execute()
            return True
        except Exception as e:
            print(f"[fire_service] save_profile failed: {e}")
            return False

    def run_and_save(self, user_id: str, data: Dict, seed: Optional[int] = None) -> Optional[Dict]:
        """Run the Monte Carlo and store the result in fire_simulations."""
        try:
            result = fire_engine.fire_simulation(
                current_age=data.get("current_age", 22),
                target_retirement_age=data.get("target_retirement_age", 45),
                monthly_expense=data.get("monthly_expense", 0),
                monthly_investment=data.get("monthly_investment", 0),
                current_corpus=data.get("current_corpus", 0),
                expected_return_pct=data.get("expected_return_pct", 10),
                inflation_pct=data.get("inflation_pct", 6),
                safe_withdrawal_rate_pct=data.get("safe_withdrawal_rate_pct", 4),
                volatility_pct=float(data.get("volatility_pct") or
                                     fire_engine.DEFAULT_VOLATILITY_PCT),
                n_simulations=int(data.get("n_simulations", 3000)),
                seed=seed,
            )
            profile = self.get_profile(user_id) or {}
            payload = {
                "user_id": user_id,
                "fire_profile_id": profile.get("id"),
                "target_age": int(result["target_retirement_age"]),
                "required_corpus": result["required_corpus"],
                "projected_corpus": result["median_corpus"],
                "probability_pct": result["probability_pct"],
                "p5": result["p5_corpus"],
                "p95": result["p95_corpus"],
                "simulations_count": result["n_simulations"],
            }
            self.supabase.table("fire_simulations").insert(payload).execute()
            return result
        except Exception as e:
            print(f"[fire_service] run_and_save failed: {e}")
            return None


def get_fire_service(supabase: Client) -> FireService:
    return FireService(supabase)