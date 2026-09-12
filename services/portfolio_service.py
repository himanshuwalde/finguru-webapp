"""
Portfolio Service — Supabase persistence + engine orchestration for investments.
CRUD maps directly onto the `investments` table from migrations/001.
Amounts are resolved AT WRITE TIME (via the engine) so that Net Worth / FIRE /
the AI context can rely on a clean current_value column without re-deriving.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from supabase import Client

from engines import portfolio_engine


class PortfolioService:
    def __init__(self, supabase: Client):
        self.supabase = supabase

    # ------------------------------------------------------------- read

    def get_investments(self, user_id: str) -> List[Dict]:
        try:
            res = self.supabase.table("investments") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("created_at").execute()
            return res.data or []
        except Exception:
            return []

    def get_summary(self, user_id: str) -> Dict:
        return portfolio_engine.portfolio_summary(self.get_investments(user_id))

    def get_health(self, user_id: str, risk_tolerance: str = "Moderate"):
        rows = self.get_investments(user_id)
        return portfolio_engine.portfolio_health(rows, risk_tolerance)

    # ------------------------------------------------------------ write

    def add_investment(self, user_id: str, data: Dict) -> bool:
        """Insert a holding; invested/current resolved by the engine first."""
        try:
            resolved = portfolio_engine.resolve_holdings(
                [_infer_row(data)])[0]
            payload = {
                "user_id": user_id,
                "asset_type": data["asset_type"],
                "name": data["name"],
                "invested_amount": resolved["invested_amount"],
                "current_value": resolved["current_value"],
                "notes": data.get("notes") or None,
            }
            # store only the fields relevant to the asset type + typed values
            for key in ("quantity", "buy_price", "current_price", "units",
                        "purchase_nav", "current_nav", "principal",
                        "interest_rate", "start_date", "maturity_date",
                        "purchased_on"):
                val = data.get(key)
                if val is not None:
                    payload[key] = val.isoformat() if hasattr(val, "isoformat") else val
            self.supabase.table("investments").insert(payload).execute()
            return True
        except Exception as e:
            print(f"[portfolio_service] add failed: {e}")
            return False

    def update_investment(self, inv_id: str, data: Dict) -> bool:
        try:
            resolved = portfolio_engine.resolve_holdings([_infer_row(data)])[0]
            updates = {
                "invested_amount": resolved["invested_amount"],
                "current_value": resolved["current_value"],
                "updated_at": "now()",
            }
            for key in ("asset_type", "name", "quantity", "buy_price",
                        "current_price", "units", "purchase_nav", "current_nav",
                        "principal", "interest_rate", "start_date",
                        "maturity_date", "purchased_on", "notes"):
                val = data.get(key)
                if val is not None:
                    updates[key] = val.isoformat() if hasattr(val, "isoformat") else val
            self.supabase.table("investments").update(updates) \
                .eq("id", inv_id).execute()
            return True
        except Exception as e:
            print(f"[portfolio_service] update failed: {e}")
            return False

    def delete_investment(self, inv_id: str) -> bool:
        try:
            self.supabase.table("investments").delete().eq("id", inv_id).execute()
            return True
        except Exception as e:
            print(f"[portfolio_service] delete failed: {e}")
            return False


def _infer_row(data: Dict) -> Dict:
    """Build the flat row shape resolve_holdings expects from a form payload."""
    return {
        "asset_type": data["asset_type"],
        "name": data["name"],
        "invested_amount": data.get("invested_amount") or 0,
        "current_value": data.get("current_value") or 0,
        "quantity": data.get("quantity"), "buy_price": data.get("buy_price"),
        "current_price": data.get("current_price"), "units": data.get("units"),
        "purchase_nav": data.get("purchase_nav"), "current_nav": data.get("current_nav"),
        "principal": data.get("principal"), "interest_rate": data.get("interest_rate"),
        "start_date": data.get("start_date"), "maturity_date": data.get("maturity_date"),
        "purchased_on": data.get("purchased_on"),
    }


def get_portfolio_service(supabase: Client) -> PortfolioService:
    return PortfolioService(supabase)