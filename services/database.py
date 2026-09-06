"""
Database Service Layer
Centralizes all Supabase queries for better testability and separation of concerns.
"""
from typing import Optional, List, Dict, Any
import pandas as pd
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from supabase import Client


class DatabaseService:
    """Centralized database operations for FinGuru."""

    def __init__(self, supabase: Client):
        self.supabase = supabase

    # ============ USER / PROFILE OPERATIONS ============

    def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """Get user profile by ID."""
        try:
            res = self.supabase.table("profiles").select("*").eq("id", user_id).single().execute()
            return res.data
        except Exception:
            return None

    def get_user_email(self, user_id: str) -> Optional[str]:
        """Get user email from profiles table."""
        profile = self.get_user_profile(user_id)
        return profile.get('email') if profile else None

    def get_user_name(self, user_id: str) -> str:
        """Get user's first name from profile."""
        profile = self.get_user_profile(user_id)
        if profile and profile.get('full_name'):
            return profile['full_name'].split(' ')[0]
        return "User"

    # ============ ACCOUNT OPERATIONS ============

    def get_user_accounts(self, user_id: str) -> List[Dict]:
        """Get all accounts for a user, ordered by creation date."""
        try:
            res = self.supabase.table("accounts").select("*").eq("user_id", user_id).order("created_at").execute()
            return res.data or []
        except Exception:
            return []

    def get_account_by_id(self, account_id: str) -> Optional[Dict]:
        """Get single account by ID."""
        try:
            res = self.supabase.table("accounts").select("*").eq("id", account_id).single().execute()
            return res.data
        except Exception:
            return None

    def get_primary_account(self, user_id: str) -> Optional[Dict]:
        """Get user's primary account."""
        accounts = self.get_user_accounts(user_id)
        return next((acc for acc in accounts if acc.get('is_primary')), accounts[0] if accounts else None)

    def get_account_name_map(self, user_id: str) -> Dict[str, str]:
        """Get mapping of account_id -> account_name for a user."""
        accounts = self.get_user_accounts(user_id)
        return {acc['id']: acc['account_name'] for acc in accounts}

    def create_account(self, user_id: str, name: str, acc_type: str, balance: float,
                       budget: float = 0, is_primary: bool = False) -> Optional[Dict]:
        """Create a new account."""
        try:
            res = self.supabase.table("accounts").insert({
                "user_id": user_id,
                "account_name": name,
                "account_type": acc_type,
                "balance": balance,
                "monthly_budget": budget,
                "is_primary": is_primary
            }).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            raise Exception(f"Failed to create account: {e}")

    def update_account(self, account_id: str, updates: Dict) -> bool:
        """Update account fields."""
        try:
            self.supabase.table("accounts").update(updates).eq("id", account_id).execute()
            return True
        except Exception as e:
            raise Exception(f"Failed to update account: {e}")

    def set_primary_account(self, user_id: str, account_id: str) -> bool:
        """Set an account as primary (unsets others)."""
        try:
            # Unset all first
            self.supabase.table("accounts").update({"is_primary": False}).eq("user_id", user_id).execute()
            # Set new primary
            self.supabase.table("accounts").update({"is_primary": True}).eq("id", account_id).execute()
            return True
        except Exception as e:
            raise Exception(f"Failed to set primary account: {e}")

    def delete_account(self, account_id: str) -> bool:
        """Delete an account."""
        try:
            self.supabase.table("accounts").delete().eq("id", account_id).execute()
            return True
        except Exception as e:
            raise Exception(f"Failed to delete account: {e}")

    # ============ TRANSACTION OPERATIONS ============

    def get_user_transactions(self, user_id: str) -> List[Dict]:
        """Get all transactions for a user."""
        try:
            res = self.supabase.table("transactions").select("*").eq("user_id", user_id).execute()
            return res.data or []
        except Exception:
            return []

    def get_transactions_by_account(self, user_id: str, account_id: str) -> List[Dict]:
        """Get transactions for a specific account."""
        try:
            res = self.supabase.table("transactions").select("*").eq("user_id", user_id).eq("account_id", account_id).execute()
            return res.data or []
        except Exception:
            return []

    def get_transactions_dataframe(self, user_id: str, account_id: Optional[str] = None) -> pd.DataFrame:
        """Get transactions as a processed DataFrame."""
        if account_id:
            transactions = self.get_transactions_by_account(user_id, account_id)
        else:
            transactions = self.get_user_transactions(user_id)

        if not transactions:
            return pd.DataFrame()

        df = pd.DataFrame(transactions)
        df['amount'] = pd.to_numeric(df['amount'])
        df['transaction_time'] = pd.to_datetime(df['transaction_time'], format='mixed', utc=True).dt.tz_localize(None)
        if 'created_at' in df.columns:
            df['created_at'] = pd.to_datetime(df['created_at'])
        return df

    def get_monthly_transactions(self, user_id: str, account_id: Optional[str] = None,
                                 year: int = None, month: int = None) -> pd.DataFrame:
        """Get transactions for a specific month."""
        df = self.get_transactions_dataframe(user_id, account_id)
        if df.empty:
            return df

        today = datetime.now()
        year = year or today.year
        month = month or today.month

        return df[
            (df['transaction_time'].dt.month == month) &
            (df['transaction_time'].dt.year == year)
        ]

    def get_historical_expenses(self, user_id: str, account_id: Optional[str] = None,
                                months_back: int = 6) -> pd.DataFrame:
        """Get expense transactions for the last N months."""
        df = self.get_transactions_dataframe(user_id, account_id)
        if df.empty:
            return df

        cutoff = datetime.now() - relativedelta(months=months_back)
        return df[(df['type'] == 'Expense') & (df['transaction_time'] >= cutoff)]

    def create_transaction(self, user_id: str, account_id: str, amount: float,
                          type_: str, category: str, description: str,
                          transaction_time: datetime, is_recurring: bool = False) -> Optional[Dict]:
        """Create a new transaction."""
        try:
            res = self.supabase.table("transactions").insert({
                "user_id": user_id,
                "account_id": account_id,
                "amount": amount,
                "type": type_,
                "category": category,
                "description": description,
                "transaction_time": transaction_time.isoformat(),
                "is_recurring": is_recurring
            }).execute()
            return res.data[0] if res.data else None
        except Exception as e:
            raise Exception(f"Failed to create transaction: {e}")

    def get_category_stats(self, user_id: str, account_id: Optional[str] = None,
                          months_back: int = 6) -> pd.DataFrame:
        """Get mean/std stats per category for anomaly detection."""
        df = self.get_historical_expenses(user_id, account_id, months_back)
        if df.empty:
            return pd.DataFrame()

        stats = df.groupby('category')['amount'].agg(['mean', 'std']).reset_index()
        stats['std'] = stats['std'].fillna(0)
        return stats

    # ============ BUDGET OPERATIONS ============

    def get_account_budget(self, account_id: str) -> float:
        """Get monthly budget for an account."""
        account = self.get_account_by_id(account_id)
        return float(account.get('monthly_budget', 0) or 0) if account else 0

    def update_account_budget(self, account_id: str, budget: float) -> bool:
        """Update account monthly budget."""
        return self.update_account(account_id, {"monthly_budget": budget})

    # ============ AGGREGATE QUERIES ============

    def get_all_users_with_accounts(self) -> List[Dict]:
        """Get all users with their accounts (for alert engine)."""
        try:
            users_res = self.supabase.table("profiles").select("id, full_name, email").execute()
            accounts_res = self.supabase.table("accounts").select("*").execute()

            users = users_res.data or []
            accounts = accounts_res.data or []

            for user in users:
                user['accounts'] = [acc for acc in accounts if acc['user_id'] == user['id']]
            return users
        except Exception:
            return []


# Factory function for dependency injection
def get_db_service(supabase: Client) -> DatabaseService:
    """Factory to create DatabaseService instance."""
    return DatabaseService(supabase)