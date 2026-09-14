import os
import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo
from utils.ai_persona import persona_and_currency_note
from utils.currency import fmt_label, fmt_money, symbol, to_display
from utils.security import decrypt_data
from services import recommendation_service

# Browser timezone reader — Streamlit Cloud runs Python in UTC, so a greeting
# needs the visitor's local clock, not the server's (8 PM IST must say Evening
# even though it's 2:30 PM in the server's UTC). The tiny tz_reader/ component
# reports the browser IANA timezone + local hour once per mount.
_TZ_READER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tz_reader")
_tz_reader = components.declare_component("tz_reader", path=_TZ_READER_DIR)
_DEFAULT_TZ = "Asia/Kolkata"  # app is India-focused (₹, NSE); sane fallback

# ==========================================
# 🧠 ML BUDGET ENGINE
# ==========================================
def generate_budget_baseline(df):
    """Analyzes variance over the last 6 months to generate a smart budget baseline."""
    if df.empty: return pd.DataFrame()
    
    # 1. Group by month and category to get monthly totals
    df['month_year'] = df['transaction_time'].dt.to_period('M')
    monthly_cat_spend = df.groupby(['month_year', 'category'])['amount'].sum().reset_index()
    
    # 2. Calculate Stats (Mean, Median, Standard Deviation for Volatility)
    stats = monthly_cat_spend.groupby('category')['amount'].agg(['mean', 'median', 'std']).fillna(0).reset_index()
    
    # 3. Apply Volatility Rules
    def smart_rule(row):
        # Stable/Fixed expense (Low Variance - std dev < 20% of mean)
        if row['std'] < (row['mean'] * 0.20): 
            return row['mean'] * 1.05 # Add 5% buffer for inflation
        else: 
            # Volatile/Discretionary expense (High Variance)
            # Use median to ignore spending spikes, cut by 10% to force savings
            return row['median'] * 0.90 

    stats['budget'] = stats.apply(smart_rule, axis=1).round(-2)
    
    # Clean up and round for UI display
    final_df = stats[['category', 'mean', 'budget']].copy()
    final_df['mean'] = final_df['mean'].round(-2)
    final_df.rename(columns={'category': 'Category', 'mean': '6-Mo Average', 'budget': 'AI Target'}, inplace=True)
    return final_df

# ==========================================
# ✨ GLOBAL CALLBACK FUNCTIONS
# ==========================================
def update_edited_budget_state():
    """
    On-change callback for the budget editor.
    Applies user edits and recalculates the TOTAL row in real-time.
    """
    if "budget_editor_state_key" not in st.session_state:
        return
        
    editor_state = st.session_state["budget_editor_state_key"]
    edited_rows = editor_state.get("edited_rows")
    
    if not edited_rows:
        return
        
    df_to_edit = st.session_state.edited_budget_df.copy()
    
    for row_idx, changed_cols in edited_rows.items():
        try:
            row_idx = int(row_idx)
        except ValueError:
            continue
            
        if row_idx < len(df_to_edit):
            # Prevent editing the TOTAL row directly
            if df_to_edit.iloc[row_idx]['Category'] == 'TOTAL':
                continue
                
            for col_name, new_val in changed_cols.items():
                if col_name == 'AI Target':
                    df_to_edit.loc[row_idx, col_name] = new_val

    # Recalculate total row: Exclude 'TOTAL' row from the sum
    data_only_df = df_to_edit[df_to_edit['Category'] != 'TOTAL']
    
    total_avg = data_only_df['6-Mo Average'].sum()
    total_target = data_only_df['AI Target'].sum()
    
    new_total_series = pd.Series({
        "Category": "TOTAL",
        "6-Mo Average": total_avg,
        "AI Target": total_target
    })
    
    final_with_total = pd.concat([data_only_df, new_total_series.to_frame().T], ignore_index=True)
    st.session_state.edited_budget_df = final_with_total

def on_account_view_change():
    """Callback to reset budget planning state when the user selects a new account view."""
    if st.session_state.get('show_budget_planner'):
        st.session_state.show_budget_planner = False

    st.session_state.pop("edited_budget_df", None)
    st.session_state.pop("budget_planner_initialized", None)


def render_page(supabase):

    # State initializations
    if 'show_budget_planner' not in st.session_state:
        st.session_state.show_budget_planner = False
    if 'show_cat_budget' not in st.session_state:
        st.session_state.show_cat_budget = False
    if 'custom_cat_budgets' not in st.session_state:
        st.session_state.custom_cat_budgets = {}
    if 'edited_budget_df' not in st.session_state:
        st.session_state.edited_budget_df = None
    if 'budget_planner_initialized' not in st.session_state:
        st.session_state.budget_planner_initialized = False

    def go_to_scanner():
        st.session_state.force_page = "add_transaction"

    # --- GREETING WITH DATE (browser-local time) ---
    # Streamlit Cloud's server clock is UTC, so datetime.now() alone can't tell
    # the user's local hour — 8 PM IST renders as 14:30 UTC → "Good Afternoon".
    # tz_reader/ reports the browser's IANA timezone + local hour from JS; we
    # cache it and fall back to Asia/Kolkata (India-focused app) then UTC.
    tz_info = st.session_state.get("_tz_info")
    if not isinstance(tz_info, dict):
        tz_info = _tz_reader()
        if isinstance(tz_info, dict) and tz_info.get("timeZone"):
            st.session_state["_tz_info"] = tz_info

    tz_name = None
    hour = None
    if isinstance(tz_info, dict):
        tz_name = tz_info.get("timeZone") or None
        if tz_info.get("hour") is not None:
            hour = int(tz_info["hour"])

    if tz_name:
        try:
            local_now = datetime.now(ZoneInfo(tz_name))
            if hour is None:
                hour = local_now.hour
        except Exception:
            try:
                local_now = datetime.now(ZoneInfo(_DEFAULT_TZ))
            except Exception:
                local_now = datetime.now()
    else:
        try:
            local_now = datetime.now(ZoneInfo(_DEFAULT_TZ))
        except Exception:
            local_now = datetime.now()

    if hour is None:
        hour = local_now.hour
    date_str = local_now.strftime("%b %d, %Y")

    if hour < 12:
        greeting = "Good Morning"
    elif hour < 17:
        greeting = "Good Afternoon"
    else:
        greeting = "Good Evening"
    # Use the user's full name from profiles if available, otherwise fall back to email
    try:
        prof_res = supabase.table("profiles").select("full_name").eq("id", st.session_state.user_id).execute()
        full_name = prof_res.data[0].get("full_name", "") if prof_res.data else ""
    except Exception:
        full_name = ""
    display_name = full_name if full_name else st.session_state.user_email.split("@")[0].replace(".", " ").title()

    st.markdown(f"""
        <div style='margin-bottom:16px'>
          <div style='font-size:1.5rem;font-weight:700;color:var(--text-color);letter-spacing:-0.3px'>
            {greeting}, {display_name} <span style='opacity:.4;font-weight:400'>·</span> <span style='opacity:.55;font-size:1rem;font-weight:500'>{date_str}</span>
          </div>
          <div style='font-size:.88rem;color:var(--text-color);opacity:.5;margin-top:2px'>
            Track wealth, analyze spending, and manage accounts.
          </div>
        </div>
    """, unsafe_allow_html=True)

    # --- THE HEADER WITH BUTTON ---
    header_col1, header_col2 = st.columns([4, 1.2])

    with header_col1:
        pass  # greeting handled above
        
    with header_col2:
        st.write("") 
        st.write("") 
        st.button("➕ Add Transaction", type="primary", use_container_width=True, on_click=go_to_scanner)

    # ==========================================
    #   🎯 FINANCIAL CO-PILOT HERO (unified health + KPIs)
    # ==========================================
    # _render_health_hero(supabase)

    # --- FETCH ACCOUNTS ---
    try:
        acc_response = supabase.table("accounts").select("*").eq("user_id", st.session_state.user_id).order("created_at").execute()
        user_accounts = acc_response.data
    except Exception as e:
        st.error("Could not fetch accounts.")
        user_accounts = []

    # ==========================================
    #   SECTION 1: VISUAL ANALYTICS
    # ==========================================
    try:
        res = supabase.table("transactions").select("*").eq("user_id", st.session_state.user_id).execute()
        all_transactions = res.data
    except Exception as e:
        st.error(f"Failed to fetch transactions: {e}")
        all_transactions = []

    # Always have a transactions frame in scope for the sections below
    # (Upcoming Bills + Insights render even when the account is empty).
    df = pd.DataFrame()
    today = datetime.now()

    if len(user_accounts) > 0:
        st.write("---")
        
        # --- THE ACCOUNT FILTER ---
        primary_acc = next((acc for acc in user_accounts if acc.get('is_primary')), None)
        account_options = ["All Accounts Combined"] + [acc['account_name'] for acc in user_accounts]
        default_idx = account_options.index(primary_acc['account_name']) if primary_acc else 0
            
        selected_view = st.selectbox("👁️ View Data For:", account_options, index=default_idx, on_change=on_account_view_change, key="dashboard_account_view_selectbox")
        
        if selected_view == "All Accounts Combined":
            filtered_transactions = all_transactions
        else:
            selected_acc_id = next(acc['id'] for acc in user_accounts if acc['account_name'] == selected_view)
            filtered_transactions = [t for t in all_transactions if t['account_id'] == selected_acc_id]

        if len(filtered_transactions) > 0:
            df = pd.DataFrame(filtered_transactions)
            df['amount'] = pd.to_numeric(df['amount'])
            df['transaction_time'] = pd.to_datetime(df['transaction_time'], format='mixed', utc=True).dt.tz_localize(None)
            
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at'])

            # --- TIME FILTERING (today is defined at module scope in render_page) ---
            this_month_df = df[
                (df['transaction_time'].dt.month == today.month) & 
                (df['transaction_time'].dt.year == today.year)
            ]

            # --- TOP-LEVEL KPIs ---
            total_income = this_month_df[this_month_df['type'] == 'Income']['amount'].sum()
            total_expense = this_month_df[this_month_df['type'] == 'Expense']['amount'].sum()
            net_savings = total_income - total_expense

            # --- MONTH-OVER-MONTH COMPARISON ---
            prev_month_date = today - relativedelta(months=1)
            prev_month_df = df[
                (df['transaction_time'].dt.month == prev_month_date.month) &
                (df['transaction_time'].dt.year == prev_month_date.year)
            ]
            prev_income = prev_month_df[prev_month_df['type'] == 'Income']['amount'].sum()
            prev_expense = prev_month_df[prev_month_df['type'] == 'Expense']['amount'].sum()
            prev_net = prev_income - prev_expense

            def mom(a, b):
                """Compute % change from prior month b to current a. None when no baseline."""
                if b == 0:
                    return None
                return ((a - b) / abs(b)) * 100

            def mom_str(cur, prev):
                """Human string like '↑ 8.4% this month'. Arrow = actual direction;
                the metric's delta_color conveys good/bad."""
                pct = mom(cur, prev)
                if pct is None:
                    return None
                arrow = "↑" if pct >= 0 else "↓"
                return f"{arrow} {abs(pct):.1f}% this month"

            m1, m2, m3 = st.columns(3)
            m1.metric("💰 Monthly Income", fmt_money(total_income, dp=2),
                      delta=mom_str(total_income, prev_income),
                      delta_color="normal")
            # Expense: spending up is bad → inverse colors so a rise shows red
            m2.metric("💸 Monthly Expenses", fmt_money(total_expense, dp=2),
                      delta=mom_str(total_expense, prev_expense),
                      delta_color="inverse")
            m3.metric("🏦 Monthly Net", fmt_money(net_savings, dp=2),
                      delta=mom_str(net_savings, prev_net),
                      delta_color="normal")

            # ==========================================
            # 🎯 MONTHLY BUDGET PROGRESS BAR & AI PLANNER
            # ==========================================
            st.write("")
            with st.container(border=True):
                # Adjusted columns to fit the drop-down toggle button
                b_head1, b_head2, b_head3 = st.columns([2.8, 1, 0.4])
                with b_head1:
                    st.subheader(f"Monthly Budget ({selected_view})")
                with b_head2:
                    if st.button("✨ AI Auto-Plan" if not st.session_state.show_budget_planner else "❌ Cancel", use_container_width=True):
                        st.session_state.show_budget_planner = not st.session_state.show_budget_planner
                        st.rerun()
                with b_head3:
                    toggle_icon = "🔼" if st.session_state.show_cat_budget else "🔽"
                    if st.button(toggle_icon, use_container_width=True):
                        st.session_state.show_cat_budget = not st.session_state.show_cat_budget
                        st.rerun()
                
                # --- MODE 1: AI BUDGET PLANNER (EDITABLE) ---
                if st.session_state.show_budget_planner:
                    st.markdown("🛠️ **AI Budget Architect:** We've calculated a baseline using your historical spending variance. Edit any field below to finalize your targets.")
                    
                    six_mo_ago = today - relativedelta(months=6)
                    hist_df = df[(df['type'] == 'Expense') & (df['transaction_time'] >= six_mo_ago)]
                    
                    _current_df = st.session_state.edited_budget_df
                    
                    if _current_df is None and not st.session_state.get('budget_planner_initialized', False):
                        planned_df = generate_budget_baseline(hist_df)
                        
                        if planned_df.empty:
                            st.warning("Not enough history to generate a variance-based budget.")
                            _current_df = pd.DataFrame() 
                        else:
                            total_avg = planned_df['6-Mo Average'].sum()
                            total_target = planned_df['AI Target'].sum()
                            planned_df.loc[len(planned_df.index)] = ["TOTAL", total_avg, total_target]
                            
                            st.session_state.edited_budget_df = planned_df
                            _current_df = st.session_state.edited_budget_df 
                            st.session_state.budget_planner_initialized = True

                    if _current_df is not None and not _current_df.empty:
                        new_budget_df = st.data_editor(
                            _current_df,
                            on_change=update_edited_budget_state,
                            key="budget_editor_state_key",
                            column_config={
                                "Category": st.column_config.TextColumn("Category", disabled=True),
                                "6-Mo Average": st.column_config.NumberColumn(fmt_label("6-Mo Average (₹)"), format=f"{symbol()}%d", disabled=True),
                                "AI Target": st.column_config.NumberColumn(fmt_label("Target Budget (₹)"), format=f"{symbol()}%d", min_value=0, step=500)
                            },
                            hide_index=True, use_container_width=True
                        )
                        
                        if st.button("💾 Save Budget Limits to Dashboard", type="primary"):
                            if selected_view == "All Accounts Combined":
                                st.warning("Please select a specific account from the dropdown above to save budgets.")
                            else:
                                _final_saved_df = st.session_state.edited_budget_df.copy()
                                valid_budgets_df = _final_saved_df[_final_saved_df['Category'] != 'TOTAL']
                                total_new_budget = valid_budgets_df['AI Target'].sum()
                                
                                try:
                                    supabase.table("accounts").update({"monthly_budget": total_new_budget}).eq("id", selected_acc_id).execute()
                                    st.session_state.custom_cat_budgets[selected_acc_id] = valid_budgets_df[['Category', 'AI Target']].to_dict('records')
                                    
                                    st.session_state.show_budget_planner = False
                                    st.success(f"Budget saved! Your new limit for {selected_view} is {fmt_money(total_new_budget, dp=2)}.")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to update budget: {e}")

                # --- MODE 2: STANDARD PROGRESS BAR VIEW ---
                else:
                    if selected_view == "All Accounts Combined":
                        monthly_budget = sum(acc.get('monthly_budget', 0) or 0 for acc in user_accounts)
                    else:
                        selected_acc = next(acc for acc in user_accounts if acc['account_name'] == selected_view)
                        monthly_budget = selected_acc.get('monthly_budget', 0) or 0

                    if monthly_budget > 0:
                        spent_this_month = this_month_df[this_month_df['type'] == 'Expense']['amount'].sum()
                        percent_used = (spent_this_month / monthly_budget) * 100
                        capped_percent = min(percent_used, 100.0) 

                        if percent_used >= 100:
                            bar_color = "#dc3545" 
                            st.error(f"⚠️ Exceeded budget by {fmt_money(spent_this_month - monthly_budget, dp=2)}!")
                        elif percent_used >= 85:
                            bar_color = "#ffc107" 
                            st.warning(f"Careful! Only {fmt_money(monthly_budget - spent_this_month, dp=2)} remaining.")
                        else:
                            bar_color = "#2ecc71" 
                        
                        st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span style="font-weight: bold; color: var(--text-color); opacity: 0.9;">{fmt_money(spent_this_month, dp=2)} of {fmt_money(monthly_budget, dp=2)} spent</span>
                            <span style="color: var(--text-color); opacity: 0.7; font-size: 0.9em;">{percent_used:.1f}% used</span>
                        </div>
                        <div style="background-color: rgba(150, 150, 150, 0.2); border-radius: 8px; height: 12px; width: 100%; margin-bottom: 5px; overflow: hidden;">
                            <div style="background-color: {bar_color}; height: 100%; width: {capped_percent}%; transition: width 0.5s ease-in-out;"></div>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.info("No budget set. Click '✨ AI Auto-Plan' to generate one!")

                # --- CATEGORY-WISE PROGRESS BARS (DROPDOWN EXPANDER) ---
                if st.session_state.show_cat_budget:
                    st.markdown("<hr style='margin:10px 0; border: none; border-bottom: 1px solid rgba(150,150,150,0.2);' />", unsafe_allow_html=True)
                    st.markdown("<h5 style='margin-bottom: 15px;'>Category Breakdown</h5>", unsafe_allow_html=True)
                    
                    custom_targets_exist = False
                    
                    if selected_view != "All Accounts Combined" and selected_acc_id in st.session_state.custom_cat_budgets:
                        _data = st.session_state.custom_cat_budgets[selected_acc_id]
                        cat_targets = pd.DataFrame(_data)
                        if not cat_targets.empty:
                            cat_targets = cat_targets[cat_targets['Category'] != 'TOTAL']
                            custom_targets_exist = not cat_targets.empty
                        
                    if not custom_targets_exist:
                        six_mo_ago = today - relativedelta(months=6)
                        hist_df = df[(df['type'] == 'Expense') & (df['transaction_time'] >= six_mo_ago)]
                        cat_targets = generate_budget_baseline(hist_df)
                    
                    current_spend_cat = this_month_df[this_month_df['type'] == 'Expense'].groupby('category')['amount'].sum().reset_index()
                    
                    if not cat_targets.empty:
                        merged_cats = pd.merge(cat_targets, current_spend_cat, left_on='Category', right_on='category', how='outer').fillna(0)
                        
                        for _, row in merged_cats.iterrows():
                            cat_name = row['Category'] if row['Category'] != 0 else row['category']
                            if cat_name == 'TOTAL': continue
                            
                            target = row['AI Target']
                            spent = row['amount']
                            
                            if target == 0 and spent == 0: continue
                            
                            display_target = target if target > 0 else spent
                            pct = (spent / display_target) * 100 if display_target > 0 else 0
                            capped_pct = min(pct, 100.0)
                            b_color = "#dc3545" if pct >= 100 else "#ffc107" if pct >= 85 else "#2ecc71"
                            
                            st.markdown(f"""
                            <div style="margin-bottom: 12px;">
                                <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 4px;">
                                    <span style="color: var(--text-color); font-weight: 500;">{cat_name}</span>
                                    <span style="color: var(--text-color); opacity: 0.8;">{fmt_money(spent)} / {fmt_money(target)}</span>
                                </div>
                                <div style="background-color: rgba(150, 150, 150, 0.2); border-radius: 4px; height: 6px; width: 100%; overflow: hidden;">
                                    <div style="background-color: {b_color}; height: 100%; width: {capped_pct}%; transition: width 0.5s ease-in-out;"></div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                    else:
                        st.info("No varied expense history found.")

            # --- THE DASHBOARD LAYOUT ---
            st.write("")
            c1, c2 = st.columns([1.2, 1]) 

            # LEFT COLUMN: Recent Transactions Feed
            with c1:
                with st.container(border=True):
                    tx_head1, tx_head2 = st.columns([3, 1.2])
                    with tx_head1:
                        st.subheader("Recent Transactions")

                    def go_to_transactions():
                        st.session_state.sidebar_choice = "💳 Transactions & Budgeting"
                        st.session_state.force_page = None
                    with tx_head2:
                        st.button("View All", use_container_width=True, on_click=go_to_transactions)

                    if 'created_at' in df.columns:
                        recent_df = df.sort_values(by=["transaction_time", "created_at"], ascending=[False, False]).head(6)
                    else:
                        recent_df = df.sort_values(by="transaction_time", ascending=False).head(6)
                    
                    if not recent_df.empty:
                        html_list = "<div style='display: flex; flex-direction: column; gap: 0px;'>"
                        for _, row in recent_df.iterrows():
                            date_str = row['transaction_time'].strftime("%b %d, %Y")
                            
                            raw_desc = row['description']
                            desc = decrypt_data(raw_desc).title()
                            
                            if row.get('is_recurring'):
                                desc += " <span style='font-size: 0.8em; color: var(--text-color); opacity: 0.5;'>(Recur)</span>"
                            
                            amt_color = "#2ecc71" if row['type'] == 'Income' else "#e74c3c"
                            arrow = "↗" if row['type'] == 'Income' else "↘"
                                
                            html_list += f"""<div style='display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(150,150,150,0.2);'>
                            <div style='line-height: 1.3;'>
                            <div style='font-weight: 600; font-size: 0.95rem; color: var(--text-color);'>{desc}</div>
                            <div style='font-size: 0.8rem; color: var(--text-color); opacity: 0.7;'>{date_str} • {row['category']}</div>
                            </div>
                            <div style='text-align: right; color: {amt_color}; font-weight: 700; font-size: 1.05rem;'>
                            {arrow} {fmt_money(row['amount'], dp=2)}
                            </div>
                            </div>"""
                        html_list += "</div>"
                        st.markdown(html_list, unsafe_allow_html=True)
                    else:
                        st.info("No recent transactions found.")

            # RIGHT COLUMN: Monthly Expense Pie Chart
            with c2:
                with st.container(border=True):
                    st.subheader("Monthly Expense Breakdown")
                    expense_this_month = this_month_df[this_month_df['type'] == 'Expense']
                    
                    if not expense_this_month.empty:
                        cat_df = expense_this_month.groupby('category')['amount'].sum().reset_index()
                        fig_pie = px.pie(cat_df, values='amount', names='category', hole=0.4, 
                                         color_discrete_sequence=px.colors.qualitative.Pastel)
                        fig_pie.update_layout(
                            margin=dict(t=10, b=10, l=10, r=10), showlegend=True, height=320,
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("No expenses logged.")

            # --- FULL WIDTH: TREND CHART ---
            st.write("")
            with st.container(border=True):
                header_col, filter_col = st.columns([4, 1])
                with header_col: st.subheader("Income vs Expense Trend")
                with filter_col:
                    time_granularity = st.selectbox(
                        "Timeframe", ["Daily", "Weekly", "Monthly", "Quarterly", "Yearly"], 
                        index=2, label_visibility="collapsed")

                # Continuous plotting for the Trend Chart correctly sorted
                if time_granularity == "Daily":
                    df['trend_date'] = df['transaction_time'].dt.strftime('%a, %b %d, %Y')
                    df['sort_date'] = df['transaction_time'].dt.date
                elif time_granularity == "Weekly":
                    df['week_period'] = df['transaction_time'].dt.to_period('W')
                    df['trend_date'] = df['week_period'].apply(lambda x: f"{x.start_time.strftime('%b %d')} - {x.end_time.strftime('%b %d, %Y')}")
                    df['sort_date'] = df['week_period'].apply(lambda x: x.start_time)
                elif time_granularity == "Monthly":
                    df['trend_date'] = df['transaction_time'].dt.strftime('%b %Y')
                    df['sort_date'] = df['transaction_time'].dt.to_period('M').apply(lambda x: x.start_time)
                elif time_granularity == "Quarterly":
                    def get_q_str(d): return f"Q{((d.month-1)//3)+1} {d.year}"
                    df['trend_date'] = df['transaction_time'].apply(get_q_str)
                    df['sort_date'] = df['transaction_time'].dt.to_period('Q').apply(lambda x: x.start_time)
                elif time_granularity == "Yearly":
                    df['trend_date'] = df['transaction_time'].dt.strftime('%Y')
                    df['sort_date'] = df['transaction_time'].dt.year

                # Explicitly map dates chronologically so Plotly respects category order
                date_mapping = df[['sort_date', 'trend_date']].drop_duplicates().sort_values('sort_date')
                ordered_categories = date_mapping['trend_date'].tolist()

                trend_df = df.groupby(['trend_date', 'sort_date', 'type'])['amount'].sum().reset_index()
                
                # Plot with categorical X-axis to keep bars touching, but use categoryarray to ensure chronological sorting
                fig_bar = px.bar(trend_df, x='trend_date', y='amount', color='type', 
                                 barmode='group', color_discrete_map={'Income': '#2ecc71', 'Expense': '#e74c3c'})
                                 
                fig_bar.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10), xaxis_title="", yaxis_title=fmt_label("Amount (₹)"),
                    xaxis=dict(type='category', categoryorder='array', categoryarray=ordered_categories),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color=st.get_option("theme.textColor") if st.get_option("theme.textColor") else None))
                st.plotly_chart(fig_bar, use_container_width=True)
            
        else: st.info(f"📊 No transactions found.")
            
    else: st.info("📊 Add a Bank Account in Settings to see analytics!")

    st.write("---")

    # ==========================================
    #   SECTION 2: UPCOMING BILLS + FINGURU INSIGHTS (2-col)
    # ==========================================
    col_left, col_right = st.columns(2)
    with col_left:
        _render_upcoming_bills(df, today, user_accounts)
    with col_right:
        _render_finguru_insights(supabase, df, today)

# ==========================================================================
#  SECTION 2: UPCOMING BILLS + FINGURU INSIGHTS
# ==========================================================================


def _render_upcoming_bills(df, today, user_accounts):
    """Show forecasted recurring bills for the rest of the month (same engine as
    the Safe-to-Spend page) so the user never misses a silent out-flow.
    Designed to render inside a column container."""
    st.subheader("Upcoming Bills")

    bills_df = pd.DataFrame()
    for acc in user_accounts:
        acc_df = df[df["account_id"] == acc["id"]] if "account_id" in df.columns else df
        acc_bills = _predict_upcoming_bills(acc_df, today, acc)
        if not acc_bills.empty:
            bills_df = pd.concat([bills_df, acc_bills], ignore_index=True)

    if bills_df.empty:
        st.info("No recurring bills forecasted for the rest of this month. "
                "Repeating expenses appear here automatically once you log two or more.")
        return

    bills_df = bills_df.sort_values("predicted_date")
    total_liability = bills_df["predicted_amount"].sum()

    with st.container(border=True):
        html = "<div style='display:flex;flex-direction:column;gap:8px;'>"
        for _, row in bills_df.iterrows():
            date_str = row["predicted_date"].strftime("%b %d")
            desc = str(row["description"]).title()
            html += (
                "<div style='display:flex;justify-content:space-between;align-items:center;"
                "background:rgba(231,76,60,0.08);border-left:4px solid #e74c3c;"
                "border-radius:6px;padding:10px 14px;'>"
                f"<div><div style='font-weight:600;font-size:.92rem;color:var(--text-color)'>{desc}</div>"
                f"<div style='font-size:.8rem;color:var(--text-color);opacity:.6'>Due approx: {date_str} "
                f"· {row['category']}</div></div>"
                f"<div style='font-weight:700;color:#e74c3c'>{fmt_money(float(row['predicted_amount']))}</div>"
                "</div>"
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        st.markdown(f"""
        <div style='display:flex;justify-content:space-between;align-items:center;
             border-top:1px solid rgba(150,150,150,.15);padding-top:10px;margin-top:6px'>
          <span style='font-size:.85rem;color:var(--text-color);opacity:.6'>Total forecasted</span>
          <span style='font-size:1.15rem;font-weight:700;color:#e74c3c'>{fmt_money(total_liability)}</span>
        </div>
        """, unsafe_allow_html=True)


def _predict_upcoming_bills(df, current_date, acc=None):
    """Forecast the next occurrence + amount for every expense that repeated at
    least twice, filtering to bills due inside the rest of this month. Mirrors
    safe_to_spend.predict_upcoming_bills but scoped per-account label."""
    try:
        from sklearn.linear_model import LinearRegression
    except Exception:
        return pd.DataFrame()

    if df.empty or "transaction_time" not in df.columns:
        return pd.DataFrame()

    end_of_month = current_date.replace(
        day=pd.Timestamp(current_date.year, current_date.month,
                         1).days_in_month)
    upcoming = []
    expense_df = df[df["type"] == "Expense"].copy()
    if expense_df.empty:
        return pd.DataFrame()

    for desc, group in expense_df.groupby("description"):
        if len(group) < 2:
            continue
        group = group.sort_values("transaction_time")
        base = group["transaction_time"].min()
        days = (group["transaction_time"] - base).dt.days.astype(float).values
        X = np.arange(len(group)).reshape(-1, 1)
        try:
            date_model = LinearRegression().fit(X, days)
            predicted_offset = date_model.predict([[len(group)]])[0]
            predicted_date = base + pd.Timedelta(days=float(predicted_offset))
            amount_model = LinearRegression().fit(
                X, group["amount"].astype(float).values)
            predicted_amount = float(amount_model.predict([[len(group)]])[0])
        except Exception:
            continue
        if current_date <= predicted_date <= end_of_month:
            acc_label = f" · {acc['account_name']}" if acc else ""
            upcoming.append({
                "description": f"{desc.title()}{acc_label}",
                "predicted_date": predicted_date,
                "predicted_amount": max(predicted_amount, 0.0),
                "category": group["category"].iloc[0],
            })
    return pd.DataFrame(upcoming)


def _render_finguru_insights(supabase, df, today):
    """Data-grounded FinGuru insights: combines the health-engine flags with a
    few deterministic, per-user observations. No invented numbers.
    Designed to render inside a column container."""
    st.subheader("FinGuru Insights")

    # --- Anchor: the health engine's verified flags (same numbers as chat/AI) ---
    flags = []
    kpis = {}
    try:
        context = recommendation_service.build_financial_context(
            supabase, st.session_state.user_id)
        flags = context["health_score"].get("flags", [])
        kpis = context.get("kpis", {})
    except Exception:
        pass

    # Severity → accent colour for left border (no emoji)
    severity_color = {
        "positive": "#2ecc71",
        "warning":  "#f1c40f",
        "danger":   "#e74c3c",
    }
    insights = []

    for flag in flags:
        insights.append({
            "color": severity_color.get(flag.get("severity"), "#888"),
            "text": flag.get("message", ""),
        })

    # --- Data-derived observations (only when we actually have transactions) ---
    if not df.empty and "transaction_time" in df.columns:
        exp = df[df["type"] == "Expense"]
        if not exp.empty:
            top_cat = (exp.groupby("category")["amount"].sum()
                       .sort_values(ascending=False).head(1))
            if not top_cat.empty:
                cat, amt = top_cat.index[0], float(top_cat.iloc[0])
                pct = (amt / exp["amount"].sum() * 100) if exp["amount"].sum() else 0
                insights.append({
                    "color": "#3498db",
                    "text": f"<b>{cat}</b> is your biggest all-time spend at "
                            f"{fmt_money(amt)} ({pct:.0f}% of all expenses). "
                            f"Consider whether this category deserves a budget cap.",
                })

        emonth = exp[exp["transaction_time"].dt.month == today.month]
        if not emonth.empty:
            emonth_amt = emonth["amount"].sum()
            n_exp = len(emonth)
            avg_txn = emonth_amt / n_exp if n_exp else 0
            insights.append({
                "color": "#9b59b6",
                "text": f"This month you've logged <b>{n_exp}</b> expense(s) averaging "
                        f"<b>{fmt_money(avg_txn)}</b> each.",
            })

        if "is_recurring" in exp.columns:
            recur = exp[exp["is_recurring"].fillna(False).astype(bool)]
        else:
            recur = exp.iloc[0:0]
        if not recur.empty:
            recurring_total = recur["amount"].sum()
            insights.append({
                "color": "#e67e22",
                "text": f"Recurring charges total <b>~{fmt_money(recurring_total)}</b> — "
                        f"check that each subscription is still worth it.",
            })

    # --- Health-score based insight ---
    if kpis.get("monthly_income"):
        mi = float(kpis["monthly_income"])
        me = float(kpis.get("monthly_expense") or 0)
        sr = ((mi - me) / mi * 100) if mi else 0
        if sr >= 0:
            insights.append({
                "color": "#2ecc71",
                "text": f"You keep about <b>{sr:.0f}%</b> of your monthly income "
                        f"after expenses. Aim for 20%+ to stay on track.",
            })
        else:
            insights.append({
                "color": "#e74c3c",
                "text": f"You're spending <b>{fmt_money(abs(me - mi))}</b> more than "
                        f"you earn this month. Trim discretionary categories first.",
            })

    if not insights:
        st.info("Add a few transactions to unlock personalized FinGuru insights.")
        return

    with st.container(border=True):
        for ins in insights:
            if not ins["text"]:
                continue
            st.markdown(
                f"<div style='display:flex;gap:10px;align-items:flex-start;"
                f"padding:10px 12px;margin-bottom:6px;'>"
                f"<div style='width:4px;border-radius:4px;background:{ins['color']};flex-shrink:0'></div>"
                f"<div style='font-size:.9rem;color:var(--text-color);line-height:1.55'>"
                f"{ins['text']}</div></div>",
                unsafe_allow_html=True)


# ==========================================================================
#  FINANCIAL CO-PILOT HERO — health score + unified KPIs (Phase 7)
# ==========================================================================


# def _render_health_hero(supabase):
#     """One source of truth: recommendation_service → same numbers as chat/AI."""
#     try:
#         context = recommendation_service.build_financial_context(
#             supabase, st.session_state.user_id)
#     except Exception as e:
#         st.warning(f"Health summary unavailable: {e}")
#         return

#     hs = context["health_score"]
#     kpis = context["kpis"]
#     fin = context["financial"]

#     st.markdown(
#         f"""
#         <div style='background:var(--secondary-background-color);border:1px solid rgba(150,150,150,.12);
#              border-radius:8px;padding:18px 22px;margin-bottom:12px'>
#           <div style='display:flex;align-items:center;gap:24px;flex-wrap:wrap'>
#             <div>
#               <div style='font-size:.78rem;opacity:.55;letter-spacing:.8px;text-transform:uppercase;font-weight:600'>Financial Health Score</div>
#               <div style='font-size:2rem;font-weight:700;line-height:1.2;color:var(--text-color)'>
#                 {hs['overall']}<span style='font-size:1rem;opacity:.6'>/100</span>
#               </div>
#               <div style='font-size:.88rem;opacity:.75'>{hs['verb']}
#                 {' · ⚠️ missing data' if hs['missing_data'] else ''}</div>
#             </div>
#             <div style='flex:1;min-width:240px'>
#               <div style='font-size:.8rem;opacity:.6;margin-bottom:6px'>
#                 Weighted — savings 25% · spending 20% · debt 15% · investments 15% · tax 10% · FIRE 15%</div>
#               <div style='background:rgba(150,150,150,.2);border-radius:99px;height:8px;overflow:hidden'>
#                 <div style='background:var(--primary-color);height:100%;width:{max(0,min(hs["overall"],100))}%;
#                      border-radius:99px'></div>
#               </div>
#             </div>
#           </div>
#         </div>
#         """, unsafe_allow_html=True)

#     c = st.columns(6)
#     c[0].metric("🤖 Health Score", f"{hs['overall']}/100", delta=hs["verb"])
#     c[1].metric("🏦 Net Worth", fmt_money(kpis["net_worth"]))
#     c[2].metric("💸 Monthly Spend", fmt_money(kpis["monthly_expense"]),
#                 f"income {fmt_money(kpis['monthly_income'])}")
#     c[3].metric("📈 Investments", fmt_money(kpis["invested_current"]))
#     c[4].metric("🧾 Tax (eff. rate)",
#                 f"{kpis['effective_tax_rate']:.1f}%" if kpis["has_tax_data"] else "—",
#                 "record in Tax Planner" if not kpis["has_tax_data"] else None)
#     c[5].metric("🔥 P(FIRE)",
#                 f"{kpis['fire_probability_pct']:.0f}%" if kpis["has_fire_data"] else "—",
#                 "save a FIRE plan" if not kpis["has_fire_data"] else None)

#     st.write("")
#     left, right = st.columns([1, 1])
#     with left:
#         st.markdown("###### Pillars")
#         for comp in hs["components"]:
#             bar = st.progress(min(comp["score"] / 100, 1.0))
#             st.markdown(
#                 f"<div style='font-size:.82rem;color:var(--text-color);opacity:.75;"
#                 f"margin:-8px 0 10px'>{comp['label']} · "
#                 f"<b>{comp['score']}</b>/100 ({comp['weight']*100:.0f}%)</div>",
#                 unsafe_allow_html=True)
#     with right:
#         st.markdown("###### What the numbers say")
#         for flag in hs["flags"]:
#             emoji = {"positive": "✅", "warning": "⚠️", "danger": "🛑"}.get(
#                 flag["severity"], "•")
#             st.markdown(f"- {emoji} {flag['message']}")

#         with st.expander("✨ Explain by the AI (grounded in these numbers)"):
#             if st.button("Generate summary", type="primary",
#                          use_container_width=True, key="hero_ai"):
#                 summary = recommendation_service.explain_health(context)
#                 try:
#                     from utils.ai_client import (get_gemini_client,
#                                                  get_generative_model,
#                                                  generate_content_safe)
#                     genai = get_gemini_client()
#                     model = get_generative_model(genai, prefer_flash=True)
#                     _money_kpis = {"net_worth", "monthly_expense", "monthly_income",
#                                    "invested_current", "potential_tax_saving",
#                                    "total_assets", "total_liabilities"}
#                     payload = json.dumps({
#                         "kpis": {k: (to_display(v) if k in _money_kpis else v)
#                                  for k, v in kpis.items()},
#                         "flags": hs["flags"],
#                         "components": [{k: v for k, v in comp.items()
#                                         if k in ("label", "score", "weight")}
#                                        for comp in hs["components"]],
#                     }, default=str)
#                     ai = generate_content_safe(model, persona_and_currency_note() + (
#                         "\n\nYou are FinGuru's copilot. Summarise this user's Financial "
#                         "Health Score, name the two most actionable improvements, and "
#                         "keep it under 120 words. Ground everything ONLY in this "
#                         "data:\n\n" + payload), max_retries=1)
#                     if ai:
#                         summary = ai
#                 except Exception as e:
#                     print(f"[dashboard] AI explain failed ({e}); deterministic used")
#                 st.markdown(summary)

#     st.write("---")
