"""
Tax Service — orchestrates Supabase persistence around the pure tax engine.
The engine (engines/tax_engine.py) does all the math; this layer only:
  * loads/saves a user's tax declaration (tax_profiles)
  * stores computed results for history + chatbot grounding (tax_calculations)
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from supabase import Client

from engines import tax_engine


class TaxService:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    # ----------------------------------------------------------- read

    def get_profile(self, user_id: str, financial_year: str) -> Optional[Dict]:
        """Return a saved tax declaration for a (user, FY)."""
        try:
            res = self.supabase.table("tax_profiles") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("financial_year", financial_year) \
                .maybe_single().execute()
            return res.data
        except Exception:
            return None

    def get_recent_calculations(self, user_id: str, financial_year: str,
                                limit: int = 3) -> List[Dict]:
        """Latest computed results for an assessment year (history)."""
        try:
            res = self.supabase.table("tax_calculations") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("financial_year", financial_year) \
                .order("created_at", desc=True) \
                .limit(limit).execute()
            return res.data or []
        except Exception:
            return []

    def get_latest_calculation(self, user_id: str,
                               financial_year: str) -> Optional[Dict]:
        calcs = self.get_recent_calculations(user_id, financial_year, limit=1)
        return calcs[0] if calcs else None

    # ----------------------------------------------------------- write

    def save_profile(self, user_id: str, financial_year: str,
                     inputs: Dict) -> bool:
        """Upsert the user's tax inputs (income + deductions) for an AY."""
        try:
            payload = {
                "user_id": user_id,
                "financial_year": financial_year,
                "age": int(inputs.get("age", 30)),
                "residential_status": inputs.get("residential_status", "Resident"),
                "income": json.dumps(inputs["income"]),
                "deductions": json.dumps(inputs["deductions"]),
                "updated_at": "now()",
            }
            self.supabase.table("tax_profiles") \
                .upsert(payload, on_conflict="user_id,financial_year") \
                .execute()
            return True
        except Exception as e:
            print(f"[tax_service] failed to save profile: {e}")
            return False

    def save_calculation(self, user_id: str, result: Dict) -> bool:
        """Persist a computed result so it can be re-shown later + feed the AI."""
        try:
            payload = {
                "user_id": user_id,
                "financial_year": result["financial_year"],
                "old_regime_tax": result["regimes"]["old"]["total_tax"],
                "new_regime_tax": result["regimes"]["new"]["total_tax"],
                "recommended_regime": result["recommended_regime"],
                "potential_saving": result["potential_saving"],
                "breakdown": json.dumps(result, default=float),
            }
            self.supabase.table("tax_calculations").insert(payload).execute()
            return True
        except Exception as e:
            print(f"[tax_service] failed to save calculation: {e}")
            return False

    # ----------------------------------------------------------- helpers

    @staticmethod
    def profile_to_inputs(profile: Dict, financial_year: str) -> Dict:
        """Rebuild a tax_engine inputs dict from a saved tax_profiles row."""
        base = tax_engine.default_inputs()
        base["financial_year"] = profile.get("financial_year", financial_year)
        base["age"] = int(profile.get("age", base["age"]))
        base["residential_status"] = profile.get("residential_status", "Resident")
        # income/deductions are stored as JSON strings
        for key in ("income", "deductions"):
            raw = profile.get(key)
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = None
            if isinstance(raw, dict):
                base[key].update({k: v for k, v in raw.items() if v is not None})
        return base


def get_tax_service(supabase: Client) -> TaxService:
    return TaxService(supabase)