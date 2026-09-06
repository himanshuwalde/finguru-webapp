import os
import pandas as pd
from datetime import datetime
import calendar
from supabase import create_client, Client
import google.generativeai as genai
from utils.email_engine import send_financial_alert
from utils.ai_client import get_gemini_client, get_best_model, generate_content_safe

# --- INITIALIZE CONNECTIONS ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Initialize Gemini client lazily (only when needed)
_genai_client = None

def _get_genai_client():
    global _genai_client
    if _genai_client is None and GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        _genai_client = genai
    return _genai_client

def generate_ai_email_content(user_name, account_name, alert_type, budget_data, category_data):
    """Uses Gemini to draft a personalized, empathetic email tailored to a specific account."""
    genai_client = _get_genai_client() or get_gemini_client()
    target_model = get_best_model(genai_client, prefer_flash=True)
    model = genai_client.GenerativeModel(target_model)
    
    prompt = f"""
    You are an expert, empathetic AI Financial Advisor for {user_name}.
    You are reporting specifically on their bank account named: "{account_name}".
    
    Alert Type: {alert_type}
    Budget Data for this account: {budget_data}
    Category Breakdown for this account: {category_data}
    
    Task: Draft an HTML email body (do not include the <head> or <body> tags, just the inner HTML).
    
    Rules based on Alert Type:
    - If "80_PERCENT_WARNING": Gently warn them they hit 80% of the budget for their {account_name} account. Show their category breakdown. Give 2 actionable tips to slow down spending on this specific account.
    - If "EARLY_OVERSPEND_WARNING": Act as a strict but caring advisor. They spent over 60% of their {account_name} budget in the first 10 days. Tell them their "Daily Safe to Spend" must drop drastically.
    - If "END_OF_MONTH_REPORT": Summarize the total income, expenses, and net savings for their {account_name} account. Provide personalized insights on their category spending. End on an encouraging note.
    
    Make it look beautiful using basic inline CSS (use standard fonts, nice spacing, and perhaps a subtle pastel background for tables). Always refer to the specific account name so the user isn't confused.
    """
    response = model.generate_content(prompt)
    return response.text

def run_daily_checks():
    today = datetime.now()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    is_last_day = today.day == days_in_month
    
    print(f"🚀 Waking up Financial Alert Engine for {today.strftime('%Y-%m-%d')}...")

    # Fetch users, accounts, and all transactions
    users_res = supabase.table("profiles").select("id, full_name, email").execute()
    accounts_res = supabase.table("accounts").select("*").execute()
    
    for user in users_res.data:
        user_id = user['id']
        user_email = user.get('email')
        user_name = user.get('full_name', 'User').split(' ')[0] 
        
        print(f"\n--- Checking User: {user_name} | Email: {user_email} ---")
        
        if not user_email: 
            print(" -> Skipped: No email in profiles table.")
            continue

        user_accounts = [acc for acc in accounts_res.data if acc['user_id'] == user_id]
        if not user_accounts: 
            print(" -> Skipped: User has no bank accounts.")
            continue
            
        # Fetch ALL transactions for this user once to save database calls
        trans_res = supabase.table("transactions").select("*").eq("user_id", user_id).execute()
        all_tx_df = pd.DataFrame(trans_res.data)
        
        if all_tx_df.empty:
            print(" -> Skipped: User has zero transactions logged.")
            continue
            
        all_tx_df['amount'] = pd.to_numeric(all_tx_df['amount'])
        all_tx_df['transaction_time'] = pd.to_datetime(all_tx_df['transaction_time'], format='mixed', utc=True).dt.tz_localize(None)

        # 🔁 INNER LOOP: Check EACH account individually
        for account in user_accounts:
            acc_id = account['id']
            acc_name = account['account_name']
            acc_budget = float(account.get('monthly_budget', 0) or 0)
            
            print(f"  🔍 Evaluating Account: {acc_name}")
            
            if acc_budget == 0:
                print(f"   -> Skipped {acc_name}: Monthly budget is set to ₹0.")
                continue 
            
            # Filter transactions for THIS specific account, and THIS specific month/year
            acc_df = all_tx_df[(all_tx_df['account_id'] == acc_id) & 
                               (all_tx_df['transaction_time'].dt.month == today.month) & 
                               (all_tx_df['transaction_time'].dt.year == today.year)]
                               
            expense_df = acc_df[acc_df['type'] == 'Expense']
            
            total_expense = expense_df['amount'].sum() if not expense_df.empty else 0.0
            total_income = acc_df[acc_df['type'] == 'Income']['amount'].sum() if not acc_df.empty else 0.0
            percent_used = (total_expense / acc_budget) * 100
            
            print(f"   -> Math: Spent ₹{total_expense} of ₹{acc_budget} ({percent_used:.1f}%)")
            
            cat_spend = expense_df.groupby('category')['amount'].sum().to_dict() if not expense_df.empty else {}
            budget_data = {
                "Budget": acc_budget, 
                "Spent": total_expense, 
                "Remaining": acc_budget - total_expense, 
                "Percent_Used": round(percent_used, 1)
            }
            
            alert_type = None
            subject = ""

            # --- RULE 1: End of Month Report ---
            if is_last_day:
                alert_type = "END_OF_MONTH_REPORT"
                subject = f"📊 {acc_name}: Monthly Report - {today.strftime('%B %Y')}"
                budget_data["Income"] = total_income
                budget_data["Net"] = total_income - total_expense
                
            # --- RULE 2: 80% Budget Hit (Prioritized) ---
            elif percent_used >= 80.0 and percent_used < 100.0:
                alert_type = "80_PERCENT_WARNING"
                subject = f"⚠️ [{acc_name}] You've reached 80% of your budget!"

            # --- RULE 3: Early Overspending ---
            elif today.day <= 10 and percent_used >= 60.0:
                alert_type = "EARLY_OVERSPEND_WARNING"
                subject = f"🚨 [{acc_name}] Urgent: High Spending Velocity"

            # --- EXECUTE ALERT ---
            if alert_type:
                print(f"   -> Triggering {alert_type} email...")
                
                html_content = generate_ai_email_content(user_name, acc_name, alert_type, budget_data, cat_spend)
                
                full_html = f"""
                <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden;">
                    <div style="background: linear-gradient(45deg, #10b981, #3b82f6); padding: 20px; text-align: center; color: white;">
                        <h2 style="margin: 0;">FinGuru AI Alerts</h2>
                        <p style="margin: 5px 0 0 0; opacity: 0.9;">Account: {acc_name}</p>
                    </div>
                    <div style="padding: 30px; background-color: #ffffff; color: #333333;">
                        {html_content}
                    </div>
                    <div style="background-color: #f9fafb; padding: 15px; text-align: center; font-size: 12px; color: #6b7280;">
                        Automated Alert from your Financial Twin System.<br>
                    </div>
                </div>
                """
                
                send_financial_alert(user_email, subject, full_html)
            else:
                print("   -> No alert triggered. Finance metrics look okay.")

    print("\n💤 Alert Engine finished. Going back to sleep.")

if __name__ == "__main__":
    run_daily_checks()