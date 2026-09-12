import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta
from utils.ai_client import get_gemini_client, get_best_model, generate_content_safe
from utils.security import decrypt_data

# Initialize AI client
genai_client = get_gemini_client()

def clean_upi_string(desc):
    """Cleans messy Indian UPI strings using Regex."""
    desc = str(desc).upper()
    if desc.startswith('UPI/'):
        parts = desc.split('/')
        if len(parts) >= 4:
            return parts[3] 
    match = re.search(r'([A-Z0-9.-]+@[A-Z0-9.-]+)', desc)
    if match:
        return match.group(1).split('@')[0] 
    return desc

def categorize_merchant(merchant_name):
    """NLP Heuristic keyword mapping to categorize Indian micro-spends."""
    name = merchant_name.upper()
    
    if any(keyword in name for keyword in ['ZOMATO', 'SWIGGY', 'EATCLUB', 'MCDONALDS', 'DOMINOS', 'PIZZAHUT', 'KFC', 'STARBUCKS', 'BARBEQUE', 'CAFE', 'CHAI', 'TEA', 'COFFEE', 'FOOD', 'RESTAURANT', 'DHABA', 'BAKER', 'SWEETS', 'MITHAI', 'DAIRY', 'VADAPAV', 'DOSA', 'BIRYANI', 'TIFFIN', 'BHOJANALAYA']):
        return "Street Food & Dining"
        
    elif any(keyword in name for keyword in ['BLINKIT', 'ZEPTO', 'INSTAMART', 'BBNOW', 'BIGBASKET', 'DMART', 'RELIANCE SMART', 'SPENCERS', 'MORE', 'KIRANA', 'STORE', 'RETAIL', 'SUPERMARKET', 'MART', 'GROCERY', 'SABZI', 'FRUITS', 'GENERAL STORE']):
        return "Kirana & Quick Commerce"

    elif any(keyword in name for keyword in ['UBER', 'OLA', 'RAPIDO', 'YULU', 'BLUSMART', 'NAMA YATRI', 'METRO', 'AUTO', 'IRCTC', 'REDBUS', 'MAKEMYTRIP', 'GOIBIBO', 'TICKET', 'RICKSHAW', 'NMMC', 'BMTC', 'BEST']):
        return "Transit & Travel"

    elif any(keyword in name for keyword in ['PETROL', 'DIESEL', 'FUEL', 'HPCL', 'BPCL', 'INDIANOIL', 'SHELL', 'NAYARA', 'FASTAG', 'TOLL', 'PARKING']):
        return "Fuel & Auto"

    elif any(keyword in name for keyword in ['JIO', 'AIRTEL', 'VI', 'VODAFONE', 'BSNL', 'RECHARGE', 'PREPAID', 'POSTPAID', 'BROADBAND', 'ACT', 'HATHWAY', 'EXCITEL', 'ELECTRICITY', 'WATER', 'GAS', 'IGL', 'MGL', 'BESCOM', 'MAHAVITARAN', 'TATA POWER']):
        return "Bills & Utilities"

    elif any(keyword in name for keyword in ['APOLLO', 'NETMEDS', 'PHARMEASY', '1MG', 'TATA 1MG', 'MEDICAL', 'PHARMA', 'CHEMIST', 'HOSPITAL', 'CLINIC', 'DIAGNOSTIC', 'PATHOLOGY', 'DR.', 'HEALTH']):
        return "Health & Pharmacy"

    elif any(keyword in name for keyword in ['AMAZON', 'FLIPKART', 'MYNTRA', 'AJIO', 'NYKAA', 'MEESHO', 'TATACLIQ', 'SHOPPERS', 'LIFESTYLE', 'TRENDS', 'PANTALOONS', 'MAX']):
        return "Shopping & E-commerce"

    elif any(keyword in name for keyword in ['NETFLIX', 'SPOTIFY', 'AMAZON PRIME', 'HOTSTAR', 'JIOCINEMA', 'SONYLIV', 'ZEE5', 'YOUTUBE', 'AUDIBLE', 'GAANA', 'BOOKMYSHOW', 'PVR', 'INOX', 'SUBSCRIPTION']):
        return "Digital Subscriptions"

    else:
        return "Uncategorized UPI"

def render_page(supabase):
    # ✨ THE FIX: Moved gradient styles to a dedicated CSS class with !important tags to prevent Streamlit render glitches
    st.markdown("""
        <style>
        .ghost-header-title {
            margin: 0; 
            padding: 0; 
            background: linear-gradient(45deg, #e74c3c, #f39c12) !important; 
            -webkit-background-clip: text !important; 
            background-clip: text !important; 
            -webkit-text-fill-color: transparent !important; 
            color: transparent !important; 
            display: inline-block !important; 
            width: fit-content !important;
        }
        </style>
        
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
            <div style="font-size: 2.2rem; background: var(--secondary-background-color); padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">👻</div>
            <h1 class="ghost-header-title">UPI Ghost Spend Auditor</h1>
        </div>
        <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem; margin-bottom: 2rem; padding-left: 5px;">Uncover the invisible micro-transactions that are silently draining your surplus.</p>
    """, unsafe_allow_html=True)

    # --- 1. FETCH & PREP DATA (PRIMARY ACCOUNT ONLY) ---
    with st.spinner("Scanning transaction history..."):
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

            trans_res = supabase.table("transactions").select("*").eq("user_id", st.session_state.user_id).execute()
            all_transactions = trans_res.data
            
            account_transactions = [t for t in all_transactions if t.get('account_id') == account_id]

            if not account_transactions:
                st.info(f"No transactions found in your primary account ({account_name}) to audit.")
                return
                
            df = pd.DataFrame(account_transactions)
            df['amount'] = pd.to_numeric(df['amount'])
            
            # Decrypt the description and handle timestamps safely
            df['description'] = df['description'].apply(lambda x: decrypt_data(str(x)) if pd.notnull(x) else "")
            df['transaction_time'] = pd.to_datetime(df['transaction_time'], format='mixed', utc=True).dt.tz_localize(None)
            
            # Filter for expenses only
            expenses = df[df['type'] == 'Expense'].copy()
            
        except Exception as e:
            st.error(f"Failed to fetch data: {e}")
            return

    # --- 2. TIME PERIOD FILTERING ---
    st.write("---")
    c_filter, _ = st.columns([1, 2])
    with c_filter:
        time_filter = st.selectbox(
            "⏳ Select Time Period", 
            ["This Month", "Last Month", "Past 3 Months", "Past 6 Months", "This Year", "All Time"],
            index=0
        )
    
    today = datetime.now()
    
    # Apply the time filter logic
    if time_filter == "This Month":
        filtered_expenses = expenses[(expenses['transaction_time'].dt.month == today.month) & (expenses['transaction_time'].dt.year == today.year)]
    elif time_filter == "Last Month":
        first_day_this_month = today.replace(day=1)
        last_month_last_day = first_day_this_month - timedelta(days=1)
        filtered_expenses = expenses[(expenses['transaction_time'].dt.month == last_month_last_day.month) & (expenses['transaction_time'].dt.year == last_month_last_day.year)]
    elif time_filter == "Past 3 Months":
        filtered_expenses = expenses[expenses['transaction_time'] >= (today - timedelta(days=90))]
    elif time_filter == "Past 6 Months":
        filtered_expenses = expenses[expenses['transaction_time'] >= (today - timedelta(days=180))]
    elif time_filter == "This Year":
        filtered_expenses = expenses[expenses['transaction_time'].dt.year == today.year]
    else:
        filtered_expenses = expenses.copy() # All Time

    if filtered_expenses.empty:
        st.info(f"No expenses found for the selected time period: **{time_filter}**.")
        return

    # --- 3. NLP CLEANING & CATEGORIZATION ---
    filtered_expenses['clean_merchant'] = filtered_expenses['description'].apply(clean_upi_string)
    filtered_expenses['smart_category'] = filtered_expenses['clean_merchant'].apply(categorize_merchant)
    
    micro_spends = filtered_expenses[filtered_expenses['amount'] <= 100]
    total_micro_spend = micro_spends['amount'].sum()
    total_overall_spend = filtered_expenses['amount'].sum()
    micro_spend_percentage = (total_micro_spend / total_overall_spend) * 100 if total_overall_spend > 0 else 0

    # --- 4. UI DASHBOARD ---
    st.write("---")
    
    col_main, col_sub = st.columns([1, 1])
    with col_main:
        st.markdown(f"<h3 style='color: var(--text-color); opacity: 0.7;'>Micro-Transactions (<₹100) Total</h3>", unsafe_allow_html=True)
        st.caption(f"Analyzing primary account: **{account_name}** | Period: **{time_filter}**")
        st.markdown(f"<h1 style='color: #e74c3c; font-size: 4rem; font-weight: 900; text-shadow: 0 2px 10px rgba(231,76,60,0.2);'>₹{total_micro_spend:,.0f}</h1>", unsafe_allow_html=True)
        st.error(f"⚠️ **Warning:** {micro_spend_percentage:.1f}% of your total spending is disappearing in micro-transactions.")

    with col_sub:
        with st.container(border=True):
            st.markdown("#### The Invisible Drain")
            st.markdown(f"**Total Expenses:** ₹{total_overall_spend:,.2f}")
            st.markdown(f"**Micro-Spends (<₹100):** ₹{total_micro_spend:,.2f}")
            st.markdown("---")
            
            # Prevent division by zero if there are no micro-spends
            avg_micro = micro_spends['amount'].mean() if not micro_spends.empty else 0.0
            
            st.markdown(f"**Average UPI Micro-Spend Size:** ₹{avg_micro:,.2f}")
            st.markdown(f"**Total Number of Micro-Spends:** {len(micro_spends)}")

    st.write("---")
    
    c1, c2 = st.columns([1.5, 1])

    # Left Column: The Breakdown Chart
    with c1:
        st.subheader("Where is the money going?")
        
        if not micro_spends.empty:
            category_breakdown = micro_spends.groupby('smart_category')['amount'].sum().reset_index()
            category_breakdown = category_breakdown.sort_values(by='amount', ascending=False)
            
            fig = px.bar(category_breakdown, x='smart_category', y='amount', 
                         title=f"UPI Micro-Spends ({time_filter})", color='smart_category',
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            
            fig.update_layout(
                xaxis_title="", 
                yaxis_title="Amount (₹)", 
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No micro-spends found to display in the chart.")

    # Right Column: The AI Ghost Auditor Insights
    with c2:
        st.subheader("🤖 The Ghost Auditor")
        st.markdown("Our AI analyzes your exact spending patterns and compares them to real-world investments.")
        
        if total_micro_spend > 0:
            if st.button("Generate Audit Report", type="primary", use_container_width=True):
                with st.spinner("AI is calculating your 'Latte Factor'..."):
                    try:
                        target_model = get_best_model(genai_client, prefer_flash=True)
                        model = genai_client.GenerativeModel(target_model)

                        top_categories = category_breakdown.head(3).to_dict('records')
                        context_str = ", ".join([f"₹{cat['amount']} on {cat['smart_category']}" for cat in top_categories])

                        system_prompt = f"""
                        You are a strict but helpful Indian financial auditor. The user has spent ₹{total_micro_spend}
                        in the {time_filter.lower()} purely on micro-transactions under ₹100 via UPI.

                        Their top drains are: {context_str}.

                        Write a short, punchy 2-paragraph audit report.
                        In the first paragraph, call out their specific habits over this {time_filter.lower()} period.
                        In the second paragraph, tell them exactly what that total ₹{total_micro_spend} could have bought them
                        in the Indian stock market (e.g., 'That's 2 units of a Nifty 50 Bluechip ETF' or 'That's X shares of Reliance').
                        Be specific, realistic with current market prices, and inspiring.
                        """

                        response_text = generate_content_safe(model, system_prompt)

                        if response_text:
                            st.success(response_text)
                        else:
                            raise Exception("Empty response from model")

                    except Exception as e:
                        st.error(f"Audit failed. **System Error:** `{str(e)}`")
        else:
            st.success("You have zero micro-spends to audit! Great job.")