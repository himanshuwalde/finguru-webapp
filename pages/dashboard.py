import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta
import json
from utils.security import decrypt_data
from services import recommendation_service

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

    # --- ✨ NEW ACTION CALLBACKS ---
    # These functions run BEFORE the screen is drawn, allowing us to update the widget state safely!
    def make_primary_callback(acc_id, acc_name):
        try:
            supabase.table("accounts").update({"is_primary": False}).eq("user_id", st.session_state.user_id).execute()
            supabase.table("accounts").update({"is_primary": True}).eq("id", acc_id).execute()
            # Safe to update this now because the selectbox hasn't been drawn yet!
            st.session_state["dashboard_account_view_selectbox"] = acc_name
            on_account_view_change()
        except Exception as e:
            st.error(f"Failed to update primary account: {e}")

    def delete_account_callback(acc_id, acc_name):
        try:
            supabase.table("accounts").delete().eq("id", acc_id).execute()
            st.session_state.pop(f"confirm_del_acc_{acc_id}", None)
            
            # If they deleted the account they are currently viewing, switch to "All Accounts"
            if st.session_state.get("dashboard_account_view_selectbox") == acc_name:
                st.session_state["dashboard_account_view_selectbox"] = "All Accounts Combined"
                on_account_view_change()
        except Exception as e:
            st.error(f"Failed to delete account: {e}")

    def cancel_delete_callback(acc_id):
        st.session_state.pop(f"confirm_del_acc_{acc_id}", None)


    def go_to_scanner():
        st.session_state.force_page = "add_transaction"

    # --- THE HEADER WITH BUTTON ---
    header_col1, header_col2 = st.columns([4, 1.2]) 
    
    with header_col1:
        st.markdown("""
            <style>
            .dashboard-header-title {
                margin: 0; 
                padding: 0; 
                background: linear-gradient(45deg, #10b981, #3b82f6) !important; 
                -webkit-background-clip: text !important; 
                background-clip: text !important; 
                -webkit-text-fill-color: transparent !important; 
                color: transparent !important; 
                display: inline-block !important; 
                width: fit-content !important;
            }
            </style>
            
            <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
                <div style="font-size: 2.2rem; background: var(--secondary-background-color); padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">📊</div>
                <h1 class="dashboard-header-title">Financial Dashboard</h1>
            </div>
            <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem; margin-bottom: 2rem; padding-left: 5px;">Track wealth, analyze spending, and manage accounts.</p>
        """, unsafe_allow_html=True)
        
    with header_col2:
        st.write("") 
        st.write("") 
        st.button("➕ Add Transaction", type="primary", use_container_width=True, on_click=go_to_scanner)

    # ==========================================
    #   🎯 FINANCIAL CO-PILOT HERO (unified health + KPIs)
    # ==========================================
    _render_health_hero(supabase)

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

            # --- TIME FILTERING ---
            today = datetime.now()
            this_month_df = df[
                (df['transaction_time'].dt.month == today.month) & 
                (df['transaction_time'].dt.year == today.year)
            ]

            # --- TOP-LEVEL KPIs ---
            total_income = this_month_df[this_month_df['type'] == 'Income']['amount'].sum()
            total_expense = this_month_df[this_month_df['type'] == 'Expense']['amount'].sum()
            net_savings = total_income - total_expense

            m1, m2, m3 = st.columns(3)
            m1.metric("💰 Monthly Income", f"₹{total_income:,.2f}")
            m2.metric("💸 Monthly Expenses", f"₹{total_expense:,.2f}")
            m3.metric("🏦 Monthly Net", f"₹{net_savings:,.2f}")

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
                                "6-Mo Average": st.column_config.NumberColumn("6-Mo Average (₹)", format="₹%d", disabled=True),
                                "AI Target": st.column_config.NumberColumn("Target Budget (₹)", format="₹%d", min_value=0, step=500)
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
                                    st.success(f"Budget saved! Your new limit for {selected_view} is ₹{total_new_budget:,.2f}.")
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
                            st.error(f"⚠️ Exceeded budget by ₹{spent_this_month - monthly_budget:,.2f}!")
                        elif percent_used >= 85:
                            bar_color = "#ffc107" 
                            st.warning(f"Careful! Only ₹{monthly_budget - spent_this_month:,.2f} remaining.")
                        else:
                            bar_color = "#2ecc71" 
                        
                        st.markdown(f"""
                        <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                            <span style="font-weight: bold; color: var(--text-color); opacity: 0.9;">₹{spent_this_month:,.2f} of ₹{monthly_budget:,.2f} spent</span>
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
                                    <span style="color: var(--text-color); opacity: 0.8;">₹{spent:,.0f} / ₹{target:,.0f}</span>
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
                    st.subheader("Recent Transactions")
                    
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
                            {arrow} ₹{row['amount']:,.2f}
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
                    margin=dict(t=10, b=10, l=10, r=10), xaxis_title="", yaxis_title="Amount (₹)",
                    xaxis=dict(type='category', categoryorder='array', categoryarray=ordered_categories),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color=st.get_option("theme.textColor") if st.get_option("theme.textColor") else None))
                st.plotly_chart(fig_bar, use_container_width=True)
            
        else: st.info(f"📊 No transactions found.")
            
    else: st.info("📊 Add a Bank Account below to see analytics!")

    st.write("---")

    # ==========================================
    #   SECTION 2: BANK ACCOUNTS MANAGER
    # ==========================================
    st.subheader("🏦 Your Bank Accounts")

    if len(user_accounts) > 0:
        cols = st.columns(min(len(user_accounts), 4))
        for index, acc in enumerate(user_accounts):
            with cols[index % 4]:
                is_primary = acc.get('is_primary', False)
                title = f"🌟 {acc['account_name']}" if is_primary else acc['account_name']
                st.metric(label=f"{title} ({acc['account_type']})", value=f"₹{acc['balance']:,.2f}")
                
                btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 1.2])
                
                if btn_col1.button("✏️", key=f"edit_{acc['id']}", help="Edit Account"):
                    st.session_state.editing_account = acc
                    st.rerun()
                
                if btn_col2.button("🗑️", key=f"del_init_{acc['id']}", help="Delete Account"):
                    st.session_state[f"confirm_del_acc_{acc['id']}"] = True
                
                if not is_primary:
                    # ✨ THE FIX: We use on_click here to trigger the callback safely BEFORE the screen evaluates
                    btn_col3.button("Make ⭐", key=f"pri_{acc['id']}", help="Set as Primary",
                                    on_click=make_primary_callback, args=(acc['id'], acc['account_name']))

                if st.session_state.get(f"confirm_del_acc_{acc['id']}", False):
                    st.error(f"Delete '{acc['account_name']}' account?")
                    warn_c1, warn_c2 = st.columns(2)
                    
                    # ✨ THE FIX: Safely route deletes through callbacks too
                    warn_c1.button("✅ Yes", key=f"yes_del_{acc['id']}", use_container_width=True, type="primary",
                                   on_click=delete_account_callback, args=(acc['id'], acc['account_name']))
                                   
                    warn_c2.button("❌ No", key=f"no_del_{acc['id']}", use_container_width=True,
                                   on_click=cancel_delete_callback, args=(acc['id'],))
    else: st.info("No accounts yet.")

    st.write("---")

    account_types = ["Savings", "Current", "Fixed Deposit (FD)", "Credit Card", "Wallet"]

    if st.session_state.editing_account:
        acc_to_edit = st.session_state.editing_account
        st.subheader(f"✏️ Editing: {acc_to_edit['account_name']}")
        with st.form("edit_account_form"):
            updated_name = st.text_input("Account Name", value=acc_to_edit['account_name'])
            try: type_index = account_types.index(acc_to_edit['account_type'])
            except ValueError: type_index = 0
            
            updated_type = st.selectbox("Account Type", account_types, index=type_index)
            updated_balance = st.number_input("Balance (₹)", value=float(acc_to_edit['balance']), step=100.0)
            
            current_budget = float(acc_to_edit.get('monthly_budget') or 0.0)
            updated_budget = st.number_input("Monthly Budget Limit (₹)", value=current_budget, step=1000.0, help="Set to 0 to disable.")
            
            c1, c2 = st.columns(2)
            with c1: save_edit = st.form_submit_button("Save Changes", type="primary")
            with c2: cancel_edit = st.form_submit_button("Cancel")
            
            if save_edit:
                if updated_name:
                    supabase.table("accounts").update({
                        "account_name": updated_name, "account_type": updated_type,
                        "balance": updated_balance, "monthly_budget": updated_budget
                    }).eq("id", acc_to_edit['id']).execute()
                    st.session_state.editing_account = None
                    st.rerun()
                else: st.error("Account name cannot be empty.")
            
            if cancel_edit:
                st.session_state.editing_account = None
                st.rerun()
    else:
        with st.expander("➕ Add New Bank Account", expanded=(len(user_accounts) == 0)):
            with st.form("add_account_form", clear_on_submit=True):
                new_acc_name = st.text_input("Account Name (e.g., HDFC Salary, SBI Savings)")
                new_acc_type = st.selectbox("Account Type", account_types)
                new_acc_balance = st.number_input("Initial Balance (₹)", min_value=0.0, step=100.0)
                new_acc_budget = st.number_input("Monthly Budget Limit (₹)", min_value=0.0, step=1000.0, help="Optional. Set a maximum spend limit for this account.")
                
                if st.form_submit_button("Save Account", type="primary"):
                    if new_acc_name:
                        try:
                            is_first_acc = (len(user_accounts) == 0)
                            supabase.table("accounts").insert({
                                "user_id": st.session_state.user_id, "account_name": new_acc_name,
                                "account_type": new_acc_type, "balance": new_acc_balance,
                                "monthly_budget": new_acc_budget, "is_primary": is_first_acc
                            }).execute()
                            st.success(f"Successfully added {new_acc_name}!")
                            st.rerun()
                        except Exception as e: st.error(f"Failed to save account: {e}")
                    else: st.error("Please provide an account name.")

# ==========================================================================
#  FINANCIAL CO-PILOT HERO — health score + unified KPIs (Phase 7)
# ==========================================================================
def _inr(v):
    try:
        return f"₹{float(v):,.0f}"
    except (TypeError, ValueError):
        return "₹0"


def _render_health_hero(supabase):
    """One source of truth: recommendation_service → same numbers as chat/AI."""
    try:
        context = recommendation_service.build_financial_context(
            supabase, st.session_state.user_id)
    except Exception as e:
        st.warning(f"Health summary unavailable: {e}")
        return

    hs = context["health_score"]
    kpis = context["kpis"]
    fin = context["financial"]

    st.markdown(
        f"""
        <div style='background:linear-gradient(120deg,#0ea5e9, #7c3aed 55%,#d946ef);
             border-radius:18px;padding:20px 24px;color:white;margin-bottom:12px'>
          <div style='display:flex;align-items:center;gap:28px;flex-wrap:wrap'>
            <div>
              <div style='font-size:.95rem;opacity:.85;letter-spacing:.3px'>FINANCIAL HEALTH SCORE</div>
              <div style='font-size:3.2rem;font-weight:800;line-height:1'>
                {hs['overall']}<span style='font-size:1.2rem;opacity:.75'>/100</span>
              </div>
              <div style='font-size:.95rem;opacity:.9'>{hs['verb']}
                {' · ⚠️ missing data recorded separately' if hs['missing_data'] else ''}</div>
            </div>
            <div style='flex:1;min-width:240px'>
              <div style='font-size:.85rem;opacity:.85;margin-bottom:6px'>
                Weighted from your real data — savings 25% · spending 20% ·
                debt 15% · investments 15% · tax 10% · FIRE 15%</div>
              <div style='background:rgba(255,255,255,.25);border-radius:99px;height:14px;overflow:hidden'>
                <div style='background:#fff;height:100%;width:{max(0,min(hs["overall"],100))}%;
                     border-radius:99px;transition:width .6s ease'></div>
              </div>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    c = st.columns(6)
    c[0].metric("🤖 Health Score", f"{hs['overall']}/100", delta=hs["verb"])
    c[1].metric("🏦 Net Worth", _inr(kpis["net_worth"]))
    c[2].metric("💸 Monthly Spend", _inr(kpis["monthly_expense"]),
                f"income {_inr(kpis['monthly_income'])}")
    c[3].metric("📈 Investments", _inr(kpis["invested_current"]))
    c[4].metric("🧾 Tax (eff. rate)",
                f"{kpis['effective_tax_rate']:.1f}%" if kpis["has_tax_data"] else "—",
                "record in Tax Planner" if not kpis["has_tax_data"] else None)
    c[5].metric("🔥 P(FIRE)",
                f"{kpis['fire_probability_pct']:.0f}%" if kpis["has_fire_data"] else "—",
                "save a FIRE plan" if not kpis["has_fire_data"] else None)

    st.write("")
    left, right = st.columns([1, 1])
    with left:
        st.markdown("###### Pillars")
        for comp in hs["components"]:
            bar = st.progress(min(comp["score"] / 100, 1.0))
            st.markdown(
                f"<div style='font-size:.82rem;color:var(--text-color);opacity:.75;"
                f"margin:-8px 0 10px'>{comp['label']} · "
                f"<b>{comp['score']}</b>/100 ({comp['weight']*100:.0f}%)</div>",
                unsafe_allow_html=True)
    with right:
        st.markdown("###### What the numbers say")
        for flag in hs["flags"]:
            emoji = {"positive": "✅", "warning": "⚠️", "danger": "🛑"}.get(
                flag["severity"], "•")
            st.markdown(f"- {emoji} {flag['message']}")

        with st.expander("✨ Explain by the AI (grounded in these numbers)"):
            if st.button("Generate summary", type="primary",
                         use_container_width=True, key="hero_ai"):
                summary = recommendation_service.explain_health(context)
                try:
                    from utils.ai_client import (get_gemini_client,
                                                 get_generative_model,
                                                 generate_content_safe)
                    genai = get_gemini_client()
                    model = get_generative_model(genai, prefer_flash=True)
                    payload = json.dumps({
                        "kpis": {k: v for k, v in kpis.items()},
                        "flags": hs["flags"],
                        "components": [{k: v for k, v in comp.items()
                                        if k in ("label", "score", "weight")}
                                       for comp in hs["components"]],
                    }, default=str)
                    ai = generate_content_safe(model, (
                        "You are FinGuru's copilot. Summarise this user's Financial "
                        "Health Score, name the two most actionable improvements, and "
                        "keep it under 120 words. Ground everything ONLY in this "
                        "data:\n\n" + payload), max_retries=1)
                    if ai:
                        summary = ai
                except Exception as e:
                    print(f"[dashboard] AI explain failed ({e}); deterministic used")
                st.markdown(summary)

    st.write("---")
