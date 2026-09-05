import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import calendar
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression
from utils.security import decrypt_data

def predict_upcoming_bills(df, current_date):
    """
    Uses Linear Regression to forecast the exact date and amount of upcoming recurring bills 
    for the rest of the current month based on historical transaction data.
    """
    end_of_month = current_date.replace(day=calendar.monthrange(current_date.year, current_date.month)[1])
    upcoming_bills = []

    # Find recurring or frequently repeated expenses
    expense_df = df[df['type'] == 'Expense'].copy()
    
    # Group by description to find patterns
    for desc, group in expense_df.groupby('description'):
        if len(group) >= 2: # Need at least 2 data points for a trend
            group = group.sort_values('transaction_time')
            
            # Feature engineering for ML
            group['days_since_start'] = (group['transaction_time'] - group['transaction_time'].min()).dt.days
            X = np.arange(len(group)).reshape(-1, 1) # Transaction index (0, 1, 2...)
            
            # Predict Next Date (Linear Regression on intervals)
            y_days = group['days_since_start'].values
            date_model = LinearRegression().fit(X, y_days)
            predicted_days_offset = date_model.predict([[len(group)]])[0]
            predicted_date = group['transaction_time'].min() + timedelta(days=float(predicted_days_offset))
            
            # Predict Next Amount (Linear Regression to catch subscription price hikes)
            y_amount = group['amount'].values
            amount_model = LinearRegression().fit(X, y_amount)
            predicted_amount = amount_model.predict([[len(group)]])[0]
            
            # Check if this predicted bill falls within the REMAINING days of this month
            if current_date <= predicted_date <= end_of_month:
                upcoming_bills.append({
                    "description": desc,
                    "predicted_date": predicted_date,
                    "predicted_amount": predicted_amount,
                    "category": group['category'].iloc[0]
                })

    return pd.DataFrame(upcoming_bills)

def render_page(supabase):
    # ✨ THE FIX: Moved gradient styles to a dedicated CSS class with !important tags
    st.markdown("""
        <style>
        .safe-header-title {
            margin: 0 !important; 
            padding: 0 !important; 
            background: linear-gradient(45deg, #10b981, #f59e0b) !important; 
            -webkit-background-clip: text !important; 
            background-clip: text !important; 
            -webkit-text-fill-color: transparent !important; 
            color: transparent !important; 
            display: inline-block !important; 
            width: fit-content !important;
        }
        </style>
        
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
            <div style="font-size: 2.2rem; background: var(--secondary-background-color); padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">🚦</div>
            <h1 class="safe-header-title">Safe-to-Spend Engine</h1>
        </div>
        <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem; margin-bottom: 2rem; padding-left: 5px;">Dynamic liquidity modeling based on spending velocity and AI bill forecasting.</p>
    """, unsafe_allow_html=True)

    # --- 1. FETCH & FILTER DATA ---
    try:
        acc_response = supabase.table("accounts").select("*").eq("user_id", st.session_state.user_id).order("created_at").execute()
        user_accounts = acc_response.data
        
        primary_acc = next((acc for acc in user_accounts if acc.get('is_primary')), None)
        if not primary_acc:
            if len(user_accounts) > 0:
                primary_acc = user_accounts[0]
            else:
                st.warning("📊 You need to add a Bank Account in the Dashboard first!")
                return
        
        account_id = primary_acc['id']
        account_name = primary_acc['account_name']
        current_balance = float(primary_acc['balance']) if primary_acc.get('balance') else 0.0
        
        # Pull the target budget
        monthly_budget = float(primary_acc.get('monthly_budget') or 0.0)
        
        trans_res = supabase.table("transactions").select("*").eq("user_id", st.session_state.user_id).execute()
        all_transactions = trans_res.data
        account_transactions = [t for t in all_transactions if t.get('account_id') == account_id]
        
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return

    if not account_transactions:
        st.info(f"Log transactions in {account_name} to enable AI forecasting.")
        return

    df = pd.DataFrame(account_transactions)
    df['amount'] = pd.to_numeric(df['amount'])
    df['description'] = df['description'].apply(lambda x: decrypt_data(str(x)) if pd.notnull(x) else "")
    df['transaction_time'] = pd.to_datetime(df['transaction_time'], format='mixed', utc=True).dt.tz_localize(None)

    today = datetime.now()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_passed = today.day
    days_remaining = days_in_month - days_passed

    # --- 2. CALCULATE SPENDING VELOCITY ---
    this_month_expenses = df[(df['transaction_time'].dt.month == today.month) & 
                             (df['transaction_time'].dt.year == today.year) & 
                             (df['type'] == 'Expense')]
    
    spent_so_far = this_month_expenses['amount'].sum() if not this_month_expenses.empty else 0.0
    spending_velocity = spent_so_far / days_passed if days_passed > 0 else 0.0

    # --- 3. FORECAST UPCOMING BILLS ---
    with st.spinner(f"AI is forecasting hidden bills..."):
        predicted_bills_df = predict_upcoming_bills(df, today)
        total_upcoming_liabilities = predicted_bills_df['predicted_amount'].sum() if not predicted_bills_df.empty else 0.0

    # --- 4. THE SAFE-TO-SPEND MATH ---
    if monthly_budget > 0:
        remaining_budget = monthly_budget - spent_so_far
        true_liquidity = remaining_budget - total_upcoming_liabilities
    else:
        true_liquidity = 0.0

    # If true_liquidity goes negative, you have no safe spend left!
    daily_safe_spend = true_liquidity / days_remaining if days_remaining > 0 else true_liquidity
    if daily_safe_spend < 0:
        daily_safe_spend = 0.0

    # --- 5. UI: DYNAMIC DASHBOARD ---
    st.write("---")
    
    col_main, col_sub = st.columns([1, 1])
    with col_main:
        st.markdown("<h3 style='color: var(--text-color); opacity: 0.7;'>Daily Safe-to-Spend Limit</h3>", unsafe_allow_html=True)
        
        if monthly_budget == 0:
            st.warning("⚠️ No Monthly Budget set. Please configure a budget in your Dashboard.")
            st.markdown("<h1 style='color: gray; font-size: 4rem;'>₹0</h1>", unsafe_allow_html=True)
        else:
            color = "#2ECC71" if daily_safe_spend >= spending_velocity else "#E74C3C"
            st.markdown(f"<h1 style='color: {color}; font-size: 4rem; text-shadow: 0 2px 15px {color}33;'>₹{daily_safe_spend:,.0f}</h1>", unsafe_allow_html=True)
            
            if daily_safe_spend < spending_velocity:
                st.error(f"⚠️ **Velocity Warning:** Slow down! You are overspending your daily limit.")
            else:
                st.success(f"✅ Your spending velocity is within safe limits.")

    with col_sub:
        with st.container(border=True):
            st.markdown(f"#### Budget Breakdown ({account_name})")
            st.markdown(f"**Monthly Limit:** ₹{monthly_budget:,.2f}")
            st.markdown(f"**Spent So Far:** -₹{spent_so_far:,.2f}")
            st.markdown(f"**Forecasted Bills:** -₹{total_upcoming_liabilities:,.2f}")
            st.markdown("---")
            st.markdown(f"**Safe Remaining:** ₹{true_liquidity:,.2f}")

    st.write("---")
    c1, c2 = st.columns([1.5, 1])

    # Left Column: ✨ IMPROVED SPEEDOMETER
    with c1:
        st.subheader("Spending Velocity Gauge")
        
        # Safely handle the max bounds of the gauge
        max_gauge_val = max(spending_velocity, daily_safe_spend) * 1.5
        if max_gauge_val <= 0: max_gauge_val = 1000 # Fallback so the chart doesn't break if everything is 0
        
        fig = go.Figure(go.Indicator(
            mode = "gauge+number+delta",
            value = spending_velocity,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Daily Spend Velocity", 'font': {'size': 20}},
            delta = {'reference': daily_safe_spend, 'increasing': {'color': "#FF3131"}, 'decreasing': {'color': "#39FF14"}},
            gauge = {
                'axis': {'range': [None, max_gauge_val], 'tickwidth': 2, 'tickcolor': "gray"},
                'bar': {'color': "#00D4FF", 'thickness': 0.25}, # Bright Neon Blue indicator
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "rgba(150,150,150,0.3)",
                'steps': [
                    {'range': [0, daily_safe_spend * 0.8], 'color': '#16A34A'}, # Solid Deep Green
                    {'range': [daily_safe_spend * 0.8, daily_safe_spend], 'color': '#F59E0B'}, # Solid Vibrant Amber
                    {'range': [daily_safe_spend, max_gauge_val], 'color': '#DC2626'} # Solid Bright Red
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.8,
                    'value': spending_velocity}
            }
        ))
        
        fig.update_layout(
            height=350, 
            margin=dict(t=50, b=10, l=10, r=10),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=st.get_option("theme.textColor") if st.get_option("theme.textColor") else "gray")
        )
        st.plotly_chart(fig, use_container_width=True)

    # Right Column: AI Forecasted Bills
    with c2:
        st.subheader("🤖 AI Forecasted Bills")
        if not predicted_bills_df.empty:
            predicted_bills_df = predicted_bills_df.sort_values('predicted_date')
            html = "<div style='display:flex; flex-direction:column; gap:10px;'>"
            
            # ✨ THE FIX: We concatenate the HTML strings directly to prevent Markdown from interpreting indentation as a code block.
            for _, row in predicted_bills_df.iterrows():
                date_str = row['predicted_date'].strftime("%b %d")
                desc = str(row['description']).title()
                
                html += f"<div style='background: rgba(231, 76, 60, 0.1); padding: 12px; border-left: 4px solid #e74c3c; border-radius: 4px;'>"
                html += f"<div style='display:flex; justify-content:space-between; font-weight:bold; color: var(--text-color);'>"
                html += f"<span>{desc}</span>"
                html += f"<span style='color:#e74c3c;'>₹{row['predicted_amount']:,.0f}</span>"
                html += f"</div>"
                html += f"<div style='font-size:0.85em; color: var(--text-color); opacity: 0.7;'>Due approx: {date_str}</div>"
                html += f"</div>"
                
            html += "</div>"
            st.markdown(html, unsafe_allow_html=True)
        else:
            st.success("No hidden bills forecasted!")