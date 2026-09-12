"""
Net Worth Service — Supabase persistence + engine orchestration.
Assets come from the existing `accounts` table (balances) and the `investments`
table (current values, via the portfolio service). Liabilities live in the new
`liabilities` table. One `net_worth_snapshots` row is kept per calendar month
for the growth chart.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, List

from supabase import Client

from engines import networth_engine
from services.database import get_db_service
from services.portfolio_service import get_portfolio_service


class NetWorthService:
    def __init__(self, supabase: Client):
        self.supabase = supabase
        self.db = get_db_service(supabase)
        self.portfolio = get_portfolio_service(supabase)

    # ------------------------------------------------------------ read

    def get_liquid_assets(self, user_id: str) -> float:
        accounts = self.db.get_user_accounts(user_id)
        return sum(float(a.get("balance") or 0) for a in accounts)

    def get_investments_by_type(self, user_id: str) -> Dict[str, float]:
        summary = self.portfolio.get_summary(user_id)
        return {a["asset_type"]: a["current"] for a in summary["allocation"]}

    def get_liabilities(self, user_id: str) -> List[Dict]:
        try:
            res = self.supabase.table("liabilities") \
                .select("*") \
                .eq("user_id", user_id) \
                .order("created_at").execute()
            return res.data or []
        except Exception:
            return []

    def compute_networth(self, user_id: str) -> Dict:
        liquid = self.get_liquid_assets(user_id)
        inv_by_type = self.get_investments_by_type(user_id)
        liabilities = self.get_liabilities(user_id)
        return networth_engine.networth_snapshot(liquid, inv_by_type, liabilities)

    def get_snapshot_history(self, user_id: str) -> List[Dict]:
        """Monthly snapshots oldest→newest (for the growth line chart)."""
        try:
            res = self.supabase.table("net_worth_snapshots") \
                .select("snapshot_date, net_worth, total_assets, total_liabilities") \
                .eq("user_id", user_id) \
                .order("snapshot_date").execute()
            return res.data or []
        except Exception:
            return []

    # ------------------------------------------------------------ write

    def add_liability(self, user_id: str, data: Dict) -> bool:
        try:
            self.supabase.table("liabilities").insert({
                "user_id": user_id,
                "liability_type": data["liability_type"],
                "name": data["name"],
                "outstanding_amount": float(data.get("outstanding_amount") or 0),
                "interest_rate": float(data.get("interest_rate") or 0),
            }).execute()
            return True
        except Exception as e:
            print(f"[networth_service] add_liability failed: {e}")
            return False

    def delete_liability(self, liability_id: str) -> bool:
        try:
            self.supabase.table("liabilities").delete() \
                .eq("id", liability_id).execute()
            return True
        except Exception as e:
            print(f"[networth_service] delete_liability failed: {e}")
            return False

    def record_snapshot(self, user_id: str) -> bool:
        """Write (or update) this month's snapshot — deduped on the month key."""
        net = self.compute_networth(user_id)
        key = networth_engine.month_key(date.today())
        try:
            existing = self.supabase.table("net_worth_snapshots") \
                .select("id") \
                .eq("user_id", user_id) \
                .eq("snapshot_date", key).execute()
            payload = {
                "user_id": user_id,
                "snapshot_date": key,
                "total_assets": round(net["total_assets"], 2),
                "total_liabilities": round(net["total_liabilities"], 2),
                "net_worth": round(net["net_worth"], 2),
                "breakdown": net,
            }
            if existing.data:
                self.supabase.table("net_worth_snapshots") \
                    .update(payload).eq("id", existing.data[0]["id"]).execute()
            else:
                self.supabase.table("net_worth_snapshots").insert(payload).execute()
            return True
        except Exception as e:
            print(f"[networth_service] record_snapshot failed: {e}")
            return False


def get_networth_service(supabase: Client) -> NetWorthService:
    return NetWorthService(supabase)