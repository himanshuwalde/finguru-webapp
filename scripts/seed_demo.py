"""
FinGuru seed script — one command to populate a rich, realistic demo dataset.
Best used on a DISPOSABLE demo account just before your viva presentation.

  python scripts/seed_demo.py --user-id <auth-users-uuid>

Seeds (for that user):
  • 2 budget accounts + ~3 months of income/expense transactions
  • 4 investments (Stock / Mutual Fund / FD / Gold)
  • 1 liability (car loan)
  • a tax declaration (old/new regime inputs)
  • a FIRE profile (retirement plan)
  • today's net-worth snapshot

Needs env: SUPABASE_URL + SUPABASE_SERVICE_KEY (bypasses RLS — do NOT run this
against your real personal account).

Uses the same ENCRYPTION_KEY as the app (read from .streamlit/secrets.toml) so
transactions render with readable descriptions in the dashboard.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptography.fernet import Fernet
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
DEMO_USER_ID_TIP = "Pass --user-id <uuid> from Supabase → Authentication → Users."


def _load_fernet() -> Fernet | None:
    """Reuse the app's ENCRYPTION_KEY so descriptions decrypt in the UI."""
    try:
        secrets_path = ROOT / ".streamlit" / "secrets.toml"
        if secrets_path.exists():
            with open(secrets_path, "rb") as fh:
                secrets = tomllib.load(fh)
            key = secrets.get("ENCRYPTION_KEY")
            if key:
                # secrets.toml may store with or without quotes
                return Fernet(key.strip('\'"').encode())
    except Exception as e:
        print(f"(warning: encryption key not loaded — {e})")
    return None


def _enc(fernet: Fernet | None, text: str) -> str:
    return fernet.encrypt(text.encode()).decode() if fernet else text


def _cli():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--user-id", required=True, help="UUID of the Supabase auth user")
    p.add_argument("--clear", action="store_true",
                   help="Delete existing investments/liabilities/tax/FIRE for the user first")
    return p.parse_args()


def main() -> int:
    args = _cli()
    url = os.environ.get("SUPABASE_URL") or os.environ.get("VITE_SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not service_key:
        print("ERROR: set SUPABASE_URL and SUPABASE_SERVICE_KEY.")
        return 1
    fernet = _load_fernet()
    sb = create_client(url, service_key)
    uid = args.user_id

    today = dt.date.today()
    # ------------------------------------------------------------ clear demo
    if args.clear:
        for table in ("investments", "liabilities", "net_worth_snapshots",
                      "fire_profiles", "fire_simulations"):
            sb.table(table).delete().eq("user_id", uid).execute()
        sb.table("tax_profiles").delete().eq("user_id", uid) \
            .eq("financial_year", "2026-27").execute()
        print("Cleared prior demo rows for investments/liabilities/tax/FIRE/nw.")

    # ------------------------------------------------------------ accounts
    acc_defs = [("HDFC Salary", "Savings", 240_000, 40_000, True),
                ("Rupee Wallet", "Wallet", 15_000, 8_000, False)]
    created = []
    for name, atype, balance, budget, primary in acc_defs:
        exists = sb.table("accounts").select("id").eq("user_id", uid) \
            .eq("account_name", name).execute()
        if exists.data:
            created.append(exists.data[0]["id"])
            print(f"account exists: {name}")
            continue
        res = sb.table("accounts").insert({
            "user_id": uid, "account_name": name, "account_type": atype,
            "balance": balance, "monthly_budget": budget, "is_primary": primary,
        }).execute()
        created.append(res.data[0]["id"])
        print(f"created account: {name}")
    salary_acc, wallet_acc = created

    # ------------------------------------------------------------ transactions
    def add_tx(account_id, amount, type_, category, desc, days_ago):
        t = today - dt.timedelta(days=days_ago)
        sb.table("transactions").insert({
            "user_id": uid, "account_id": account_id, "amount": amount,
            "type": type_, "category": category,
            "description": _enc(fernet, desc),
            "transaction_time": f"{t.isoformat()}T09:{min(59,58):02d}:00",
            "is_recurring": False,
        }).execute()

    # incomes
    for age in (95, 62, 35, 3):
        add_tx(salary_acc, 120_000, "Income", "Salary", "Monthly salary credit", age)
    # expenses across categories over ~3 months
    expenses = [
        (salary_acc, 18_000, "Expense", "Rent", "Rent — 2BHK", 95),
        (salary_acc, 7_500, "Expense", "Groceries", "BigBasket weekly", 90),
        (wallet_acc, 1_200, "Expense", "Food & Dining", "Cafe meetup", 86),
        (salary_acc, 12_000, "Expense", "Rent", "Rent — 2BHK", 60),
        (salary_acc, 6_200, "Expense", "Groceries", "DMart stock-up", 55),
        (salary_acc, 3_400, "Expense", "Transport", "Metro + fuel", 40),
        (salary_acc, 8_900, "Expense", "Health", "Insurance premium", 30),
        (salary_acc, 13_000, "Expense", "Rent", "Rent — 2BHK", 25),
        (salary_acc, 2_100, "Expense", "Entertainment", "Movie + dinner", 20),
        (wallet_acc, 950, "Expense", "Food & Dining", "Zomato order", 14),
        (salary_acc, 5_600, "Expense", "Shopping", "Festive shopping", 9),
        (wallet_acc, 1_800, "Expense", "Entertainment", "Weekend plan", 5),
    ]
    for account_id, amt, type_, cat, desc, ago in expenses:
        add_tx(account_id, amt, type_, cat, desc, ago)
    print(f"seeded {1 + len(expenses)} transactions")

    # ------------------------------------------------------------ investments
    inv = [
        dict(asset_type="Stock", name="TCS", quantity=15, buy_price=3200,
             current_price=3880, purchased_on=f"{today.year - 2}-06-10"),
        dict(asset_type="Mutual Fund", name="HDFC Flexi Cap", units=320,
             purchase_nav=58.4, current_nav=74.2, purchased_on=f"{today.year - 3}-01-15"),
        dict(asset_type="FD", name="SBI FD", principal=100_000, interest_rate=7.1,
             start_date=f"{today.year - 1}-04-01"),
        dict(asset_type="Gold", name="Sovereign Gold Bond", invested_amount=50_000,
             current_value=57_800, purchased_on=f"{today.year - 2}-02-20"),
    ]
    for row in inv:
        row["user_id"] = uid
        sb.table("investments").insert(row).execute()
    print("seeded 4 investments (Stock / MF / FD / Gold)")

    # ------------------------------------------------------------ liabilities
    sb.table("liabilities").insert({
        "user_id": uid, "liability_type": "Car", "name": "Maruti Car Loan",
        "outstanding_amount": 220_000, "interest_rate": 9.2,
    }).execute()
    print("seeded 1 liability (car loan ₹2.2L @ 9.2%)")

    # ------------------------------------------------------------ tax profile
    tax_inputs = {
        "financial_year": "2026-27",
        "age": 29, "residential_status": "Resident",
        "income": {"salary": 1_200_000, "bonus": 50_000, "interest_income": 15_000,
                   "rental_income": 0, "ltcg": 30_000, "stcg": 0, "other_income": 0},
        "deductions": {"sec_80c": 150_000, "sec_80d_self": 25_000,
                       "sec_80d_parents": 0, "80d_parents_senior": False,
                       "sec_80ccd_1b": 50_000, "sec_80g": 10_000,
                       "nps_employer": 0, "home_loan_interest": 0,
                       "hra_basic_salary": 360_000, "hra_received": 120_000,
                       "hra_rent_paid": 216_000, "hra_is_metro": True},
    }
    sb.table("tax_profiles").upsert({
        "user_id": uid, "financial_year": "2026-27",
        "age": tax_inputs["age"], "residential_status": "Resident",
        "income": json.dumps(tax_inputs["income"]),
        "deductions": json.dumps(tax_inputs["deductions"]),
    }, on_conflict="user_id,financial_year").execute()
    print("seeded tax declaration (FY 2026-27)")

    # ------------------------------------------------------------ fire profile
    sb.table("fire_profiles").upsert({
        "user_id": uid, "current_age": 29, "target_retirement_age": 50,
        "monthly_expense": 45_000, "monthly_investment": 45_000,
        "current_corpus": 600_000, "expected_return_pct": 11,
        "inflation_pct": 6, "safe_withdrawal_rate_pct": 4,
    }, on_conflict="user_id").execute()
    print("seeded FIRE profile")

    # ------------------------------------------------------------ net worth snapshot
    sb.table("net_worth_snapshots").upsert({
        "user_id": uid, "snapshot_date": today.isoformat(),
        "total_assets": 1_950_000, "total_liabilities": 220_000,
        "net_worth": 1_730_000,
        "breakdown": {"note": "seeded by scripts/seed_demo.py"},
    }, on_conflict="user_id,snapshot_date").execute()
    print("seeded today's net-worth snapshot")

    print("\n✅ Demo data ready. Sign in as this user in the app and visit "
          "Dashboard / Tax Planner / Portfolio / Net Worth / FIRE Planner / "
          "AI CA Advisor.")
    if not fernet:
        print("⚠️ descriptions not encrypted (no ENCRYPTION_KEY found) — they "
              "will show as '***' in the dashboard.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())