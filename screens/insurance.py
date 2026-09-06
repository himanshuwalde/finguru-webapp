import streamlit as st
import pandas as pd
from utils.ai_client import get_gemini_client, get_best_model, generate_content_safe

# Initialize AI client
genai_client = get_gemini_client()

# ==========================================
# ✨ THE MARKET MATCH ENGINE (Real-world Indian Policies)
# ==========================================
def get_market_term_policies(cover_amount, age):
    """Dynamically estimates premiums for real Term policies based on age & cover amount."""
    base_rate = 12 + (age - 25) * 1.5 if age > 25 else 10
    est_premium = int((cover_amount / 100000) * base_rate)

    return [
        {
            "name": "Click 2 Protect Super",
            "provider": "HDFC Life",
            "premium": est_premium,
            "features": ["Return of premium option", "Waiver on Critical Illness"]
        },
        {
            "name": "Smart Secure Plus",
            "provider": "Max Life",
            "premium": int(est_premium * 0.92),
            "features": ["Terminal Illness cover included", "Accident cover add-on"]
        },
        {
            "name": "iProtect Smart",
            "provider": "ICICI Prudential",
            "premium": int(est_premium * 1.05),
            "features": ["Covers 34 Critical Illnesses", "Discounted rates for women"]
        }
    ]

def get_market_health_policies(cover_amount, dependents):
    """Dynamically estimates premiums for real Health policies based on family size & cover."""
    base_premium = 600 + (dependents * 350)
    est_premium = int(base_premium * (max(cover_amount, 500000) / 500000))

    return [
        {
            "name": "Optima Secure",
            "provider": "HDFC ERGO",
            "premium": est_premium,
            "features": ["4X Cover from Day 1", "No sub-limits on room rent"]
        },
        {
            "name": "ReAssure 2.0",
            "provider": "Niva Bupa",
            "premium": int(est_premium * 0.88),
            "features": ["Lock the clock (age lock)", "Unconsumed cover carry forward"]
        },
        {
            "name": "Family Health Optima",
            "provider": "Star Health",
            "premium": int(est_premium * 1.1),
            "features": ["Auto-restoration of sum insured", "Newborn baby cover"]
        }
    ]

def render_page(supabase):
    # ✨ THE FIX: Moved gradient styles to a dedicated CSS class with !important tags
    st.markdown("""
        <style>
        .insurance-header-title {
            margin: 0 !important; 
            padding: 0 !important; 
            background: linear-gradient(45deg, #2563EB, #9333EA) !important; 
            -webkit-background-clip: text !important; 
            background-clip: text !important; 
            -webkit-text-fill-color: transparent !important; 
            color: transparent !important; 
            display: inline-block !important; 
            width: fit-content !important;
        }
        </style>
        
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
            <div style="font-size: 2.2rem; background: var(--secondary-background-color); padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">🛡️</div>
            <h1 class="insurance-header-title">AI Insurance Advisor</h1>
        </div>
        <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem; margin-bottom: 2rem; padding-left: 5px;">Discover exactly how much coverage your family needs based on your actual lifestyle.</p>
    """, unsafe_allow_html=True)

    # --- 1. COLLECT USER PROFILE DATA ---
    if 'user_age' not in st.session_state: st.session_state.user_age = 30
    if 'user_dependents' not in st.session_state: st.session_state.user_dependents = 0
    if 'profile_saved' not in st.session_state: st.session_state.profile_saved = False
    
    if 'ai_advice' not in st.session_state: st.session_state.ai_advice = None

    if not st.session_state.profile_saved:
        with st.container(border=True):
            st.subheader("👨‍👩‍👧 Tell us about yourself")
            st.markdown("We need two quick details to calculate your Human Life Value.")
            
            c1, c2 = st.columns(2)
            age = c1.number_input("Your Age", min_value=18, max_value=80, value=st.session_state.user_age)
            dependents = c2.number_input("Number of Dependents (Kids, Parents, Spouse)", min_value=0, max_value=10, value=st.session_state.user_dependents)
            
            if st.button("Calculate My Coverage", type="primary"):
                st.session_state.user_age = age
                st.session_state.user_dependents = dependents
                st.session_state.profile_saved = True
                st.session_state.ai_advice = None 
                st.rerun()
        return 

    # --- 2. FETCH FINANCIAL DATA (PRIMARY ACCOUNT ONLY) ---
    try:
        acc_res = supabase.table("accounts").select("*").eq("user_id", st.session_state.user_id).order("created_at").execute()
        user_accounts = acc_res.data
        
        primary_acc = next((acc for acc in user_accounts if acc.get('is_primary')), None)
        if not primary_acc:
            if len(user_accounts) > 0:
                primary_acc = user_accounts[0]
            else:
                st.warning("📊 You need to add a Bank Account in the Dashboard first!")
                return
                
        account_id = primary_acc['id']
        account_name = primary_acc['account_name']
        
        total_liability = float(primary_acc['balance']) if primary_acc.get('account_type') == 'Credit Card' else 0.0
        
        trans_res = supabase.table("transactions").select("*").eq("user_id", st.session_state.user_id).execute()
        all_transactions = trans_res.data
        
        transactions = [t for t in all_transactions if t.get('account_id') == account_id]
        
    except Exception as e:
        st.error(f"Failed to fetch data: {e}")
        return

    if not transactions:
        st.warning(f"We need some transaction data in your primary account ({account_name}) to analyze your lifestyle! Please log some income and expenses first.")
        if st.button("Reset Profile"):
            st.session_state.profile_saved = False
            st.rerun()
        return

    # --- 3. THE MATH ENGINE (HLV & EXPENSE RATIOS) ---
    df = pd.DataFrame(transactions)
    df['amount'] = pd.to_numeric(df['amount'])
    
    total_income = df[df['type'] == 'Income']['amount'].sum()
    total_expense = df[df['type'] == 'Expense']['amount'].sum()
    
    annual_income = total_income * 12
    annual_expense = total_expense * 12
    
    medical_keywords = ['hospital', 'clinic', 'pharmacy', 'medicine', 'doctor', 'health']
    medical_expenses = df[(df['type'] == 'Expense') & 
                          (df['description'].str.contains('|'.join(medical_keywords), case=False, na=False))]['amount'].sum()

    years_to_retirement = max(60 - st.session_state.user_age, 5) 
    family_support_needed = annual_income * 0.70 
    hlv = family_support_needed * min(years_to_retirement, 15) 
    
    recommended_term_life = hlv + total_liability

    base_health_cover = 500000 
    dependent_cover = st.session_state.user_dependents * 200000
    recommended_health = base_health_cover + dependent_cover
    
    if medical_expenses > (total_income * 0.05): 
        health_note = "⚠️ High medical expenses detected. We strongly recommend a Super Top-Up."
        recommended_health += 500000 
    else:
        health_note = "✅ Standard medical expenses detected. A comprehensive base plan is sufficient."

    term_policies = get_market_term_policies(recommended_term_life, st.session_state.user_age)
    health_policies = get_market_health_policies(recommended_health, st.session_state.user_dependents)

    # --- 4. THE UI DASHBOARD ---
    h_col1, h_col2 = st.columns([4, 1])
    with h_col1:
        st.subheader(f"Recommendations for a {st.session_state.user_age}-year-old with {st.session_state.user_dependents} dependents")
        st.caption(f"Analyzing primary account: **{account_name}**")
    with h_col2:
        if st.button("✏️ Edit Profile"):
            st.session_state.profile_saved = False
            st.session_state.ai_advice = None 
            st.rerun()
        
    st.write("---")

    c1, c2 = st.columns(2)
    
    with c1:
        with st.container(border=True):
            st.markdown("### ☂️ Term Life Insurance")
            st.markdown("To protect your family's lifestyle and clear outstanding debts if you are not around.")
            
            st.markdown(f"""
            <div style="background: linear-gradient(145deg, var(--secondary-background-color), transparent); padding: 25px 20px; border-radius: 16px; text-align: center; border: 1px solid rgba(150, 150, 150, 0.2); margin-top: 15px; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.03);">
                <p style="color: var(--text-color); opacity: 0.6; margin: 0; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">Recommended Cover</p>
                <h2 style="color: var(--primary-color); margin: 5px 0 0 0; font-size: 3rem; font-weight: 900;">₹{recommended_term_life:,.0f}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("**How we calculated this:**")
            st.caption(f"• **Human Life Value (HLV):** ₹{hlv:,.0f} (Based on ₹{annual_income:,.0f}/yr income)")
            st.caption(f"• **Liability Clearance:** ₹{total_liability:,.0f} (Credit Cards & Loans)")

            st.write("")
            st.markdown("#### ✨ Top Market Matches")
            
            for i, policy in enumerate(term_policies):
                with st.container(border=True):
                    pc1, pc2 = st.columns([2.5, 1.5])
                    with pc1:
                        st.markdown(f"<div style='color: var(--text-color); font-weight: 800; font-size: 1.1rem;'>{policy['name']}</div>", unsafe_allow_html=True)
                        st.caption(f"by {policy['provider']}")
                        st.markdown(f"<div style='background: var(--secondary-background-color); border: 1px solid rgba(150,150,150,0.2); color: var(--primary-color); padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 700; margin-top: 4px; display: inline-block;'>✓ {policy['features'][0]}</div>", unsafe_allow_html=True)
                    with pc2:
                        st.markdown(f"<div style='text-align: right; color: var(--text-color); font-weight: 800; font-size: 1.2rem; margin-bottom: 8px;'>₹{policy['premium']}<span style='font-size:0.8rem; font-weight: 500; opacity:0.6;'>/mo</span></div>", unsafe_allow_html=True)
                        search_url = f"https://www.google.com/search?q={policy['name'].replace(' ', '+')}+{policy['provider'].replace(' ', '+')}+insurance"
                        st.link_button("View Plan →", url=search_url, use_container_width=True)

    with c2:
        with st.container(border=True):
            st.markdown("### 🏥 Health Insurance")
            st.markdown("To cover hospital bills for you and your dependents without draining savings.")
            
            st.markdown(f"""
            <div style="background: linear-gradient(145deg, var(--secondary-background-color), transparent); padding: 25px 20px; border-radius: 16px; text-align: center; border: 1px solid rgba(150, 150, 150, 0.2); margin-top: 15px; margin-bottom: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.03);">
                <p style="color: var(--text-color); opacity: 0.6; margin: 0; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">Recommended Cover</p>
                <h2 style="color: var(--primary-color); margin: 5px 0 0 0; font-size: 3rem; font-weight: 900;">₹{recommended_health:,.0f}</h2>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("**How we calculated this:**")
            st.caption(f"• **Base Individual Cover:** ₹5,00,000")
            st.caption(f"• **Dependent Add-on:** ₹{dependent_cover:,.0f} ({st.session_state.user_dependents} dependents)")
            
            st.markdown(f"<div style='font-size: 0.85rem; color: #e67e22; font-weight: 600; margin-top: 5px;'>{health_note}</div>", unsafe_allow_html=True)

            st.write("")
            st.markdown("#### ✨ Top Market Matches")
            
            for i, policy in enumerate(health_policies):
                with st.container(border=True):
                    hc1, hc2 = st.columns([2.5, 1.5])
                    with hc1:
                        st.markdown(f"<div style='color: var(--text-color); font-weight: 800; font-size: 1.1rem;'>{policy['name']}</div>", unsafe_allow_html=True)
                        st.caption(f"by {policy['provider']}")
                        st.markdown(f"<div style='background: var(--secondary-background-color); border: 1px solid rgba(150,150,150,0.2); color: var(--primary-color); padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 700; margin-top: 4px; display: inline-block;'>✓ {policy['features'][0]}</div>", unsafe_allow_html=True)
                    with hc2:
                        st.markdown(f"<div style='text-align: right; color: var(--text-color); font-weight: 800; font-size: 1.2rem; margin-bottom: 8px;'>₹{policy['premium']}<span style='font-size:0.8rem; font-weight: 500; opacity:0.6;'>/mo</span></div>", unsafe_allow_html=True)
                        search_url = f"https://www.google.com/search?q={policy['name'].replace(' ', '+')}+{policy['provider'].replace(' ', '+')}+health+insurance"
                        st.link_button("View Plan →", url=search_url, use_container_width=True)

    # --- 5. AI ADVISOR SUMMARY (DYNAMIC MODEL SELECTION) ---
    st.write("---")
    st.subheader("🤖 AI Advisor's Note")
    
    if st.session_state.ai_advice:
        st.info(st.session_state.ai_advice)
        
        if st.button("🔄 Clear & Regenerate Advice"):
            st.session_state.ai_advice = None
            st.rerun()
            
    else:
        if st.button("Generate Personalized Advice", type="primary"):
            with st.spinner("Analyzing your financial profile with Gemini..."):
                prompt = f"""
                You are a sympathetic, expert financial advisor. Review this user's profile and write a short, 2-paragraph summary explaining WHY they need this insurance.
                Profile: Age {st.session_state.user_age}, {st.session_state.user_dependents} dependents.
                Annual Income: ₹{annual_income}. Debt: ₹{total_liability}.
                Recommended Term Life: ₹{recommended_term_life}. Recommended Health: ₹{recommended_health}.
                Keep it professional, empathetic, and strictly financial. Do not use markdown formatting like **bold**, just pure text.
                """

                try:
                    target_model = get_best_model(genai_client, prefer_flash=True)
                    model = genai_client.GenerativeModel(target_model)
                    response_text = generate_content_safe(model, prompt)

                    if response_text:
                        st.session_state.ai_advice = response_text
                    else:
                        raise Exception("Empty response from model")

                except Exception as e:
                    print(f"Gemini API Generation Error: {e}")
                    fallback_text = f"Based on your profile as a {st.session_state.user_age}-year-old with {st.session_state.user_dependents} dependents, securing a Term Life cover of ₹{recommended_term_life:,.0f} is highly recommended. This ensures that your annual income of ₹{annual_income:,.0f} is replaced and your outstanding liabilities of ₹{total_liability:,.0f} are cleared if you are not around.\n\nAdditionally, a Health Insurance cover of ₹{recommended_health:,.0f} is crucial. {health_note} This protects your primary savings from being drained by sudden medical emergencies."
                    st.session_state.ai_advice = fallback_text

                st.rerun()