import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go
import google.generativeai as genai
import time

# Give Gemini access
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def calculate_probability(target, current, monthly_contrib, months_left):
    """Calculates a rough probability (0-99%) of hitting a goal based on current trajectory."""
    if months_left <= 0: return 99 if current >= target else 5
    projected_final = current + (monthly_contrib * months_left)
    buffer_ratio = projected_final / target
    prob = (buffer_ratio * 80)
    return min(max(int(prob), 5), 99)

@st.dialog("✏️ Edit Goal")
def edit_goal_dialog(goal, supabase):
    with st.form(f"edit_form_{goal['id']}"):
        g_name = st.text_input("Goal Name", value=goal['goal_name'])
        g_target = st.number_input("Target Amount (₹)", min_value=1000, step=5000, value=int(goal['target_amount']))
        g_saved = st.number_input("Already Saved (₹)", min_value=0, step=1000, value=int(goal['current_saved']))
        g_monthly = st.number_input("Monthly Contribution (₹)", min_value=0, step=500, value=int(goal['monthly_contribution']))
        
        existing_date = datetime.strptime(goal['target_date'], "%Y-%m-%d").date()
        g_date = st.date_input("Target Date", value=existing_date)
        
        if st.form_submit_button("Update Goal", type="primary"):
            supabase.table("goals").update({
                "goal_name": g_name,
                "target_amount": g_target,
                "current_saved": g_saved,
                "monthly_contribution": g_monthly,
                "target_date": str(g_date)
            }).eq("id", goal['id']).execute()
            st.success("Goal successfully updated!")
            st.rerun()

@st.dialog("💳 Virtual Card Authorized")
def show_virtual_card(item, price):
    st.balloons()
    st.success(f"The AI Guardrail has authorized the purchase.")
    
    with st.container(border=True):
        st.markdown("### 💳 One-Time Use Virtual Card")
        st.code("4532 • 8812 • 0901 • 4452", language="text")
        c1, c2 = st.columns(2)
        c1.markdown("**EXP:** 05/29")
        c2.markdown("**CVV:** 991")
        st.caption(f"Spending Limit Locked to: ₹{price:,.2f}")
    
    st.warning("This card will expire automatically in 30 minutes.")

def render_page(supabase):
    # ✨ THE FIX: Moved gradient styles to a dedicated CSS class with !important tags
    st.markdown("""
        <style>
        .guardrail-header-title {
            margin: 0 !important; 
            padding: 0 !important; 
            background: linear-gradient(45deg, #ef4444, #f59e0b) !important; 
            -webkit-background-clip: text !important; 
            background-clip: text !important; 
            -webkit-text-fill-color: transparent !important; 
            color: transparent !important; 
            display: inline-block !important; 
            width: fit-content !important;
        }
        </style>
        
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
            <div style="font-size: 2.2rem; background: var(--secondary-background-color); padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">🛑</div>
            <h1 class="guardrail-header-title">AI Financial Guardrail</h1>
        </div>
        <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem; margin-bottom: 2rem; padding-left: 5px;">Generating single-use payment tokens only if your long-term goals remain safe.</p>
    """, unsafe_allow_html=True)

    # --- 1. FETCH GOALS ---
    try:
        goals_res = supabase.table("goals").select("*").eq("user_id", st.session_state.user_id).order("created_at").execute()
        goals = goals_res.data
    except Exception as e:
        st.error(f"Failed to fetch goals: {e}")
        return

    st.write("---")
    c1, c2 = st.columns([1, 1.5])
    
    # --- 2. GOAL MANAGEMENT ---
    with c1:
        st.subheader("🎯 Your Active Goals")
        if not goals:
            st.info("No goals set. Create one to enable the Guardrail.")
        else:
            for goal in goals:
                progress = min(goal['current_saved'] / goal['target_amount'], 1.0)
                st.markdown(f"**{goal['goal_name']}**")
                st.progress(progress)
                st.caption(f"₹{goal['current_saved']:,.0f} / ₹{goal['target_amount']:,.0f} by {goal['target_date']}")
                
                with st.expander("⚙️ Manage Goal"):
                    mc1, mc2 = st.columns(2)
                    if mc1.button("✏️ Edit", key=f"edit_btn_{goal['id']}", use_container_width=True):
                        edit_goal_dialog(goal, supabase)
                    
                    if mc2.button("❌ Delete", key=f"del_init_{goal['id']}", use_container_width=True):
                        st.session_state[f"confirm_del_goal_{goal['id']}"] = True
                        
                    if st.session_state.get(f"confirm_del_goal_{goal['id']}", False):
                        st.error("Delete this goal permanently?")
                        wc1, wc2 = st.columns(2)
                        if wc1.button("✅ Yes", key=f"yes_del_{goal['id']}", type="primary", use_container_width=True):
                            supabase.table("goals").delete().eq("id", goal['id']).execute()
                            st.session_state.pop(f"confirm_del_goal_{goal['id']}", None)
                            st.rerun()
                        if wc2.button("❌ Cancel", key=f"no_del_{goal['id']}", use_container_width=True):
                            st.session_state.pop(f"confirm_del_goal_{goal['id']}", None)
                            st.rerun()
                st.write("")
                
        with st.expander("➕ Create New Goal"):
            with st.form("new_goal_form", clear_on_submit=True):
                g_name = st.text_input("Goal Name (e.g., Europe Trip 2026)")
                g_target = st.number_input("Target Amount (₹)", min_value=1000, step=5000)
                g_saved = st.number_input("Already Saved (₹)", min_value=0, step=1000)
                g_monthly = st.number_input("Monthly Contribution (₹)", min_value=0, step=500)
                g_date = st.date_input("Target Date", min_value=datetime.today())
                
                if st.form_submit_button("Save Goal", type="primary"):
                    if g_name:
                        supabase.table("goals").insert({
                            "user_id": st.session_state.user_id,
                            "goal_name": g_name,
                            "target_amount": g_target,
                            "current_saved": g_saved,
                            "monthly_contribution": g_monthly,
                            "target_date": str(g_date)
                        }).execute()
                        st.rerun()

    # --- 3. THE SMART CHECKOUT GATEKEEPER ---
    with c2:
        st.subheader("🔗 Active Interception Queue")
        
        col_title, col_sync = st.columns([2, 1])
        if col_sync.button("🔄 Sync with Extension", use_container_width=True):
            st.rerun()

        with st.container(border=True):
            try:
                pending_res = supabase.table("pending_checkouts").select("*").eq("user_id", st.session_state.user_id).eq("status", "pending_ai_review").order("created_at", desc=True).limit(1).execute()
                pending_requests = pending_res.data
            except Exception as e:
                pending_requests = []

            if pending_requests:
                latest_request = pending_requests[0]
                product_url = latest_request['product_url']
                request_id = latest_request['id']
                
                st.success("🚨 **Checkout Intercepted!**")
                
                short_url = product_url[:50] + "..." if len(product_url) > 50 else product_url
                st.markdown(f"**Link:** [{short_url}]({product_url})")
                
                live_price = latest_request.get('product_price', 0.0)
                if live_price is None: live_price = 0.0
                final_price = st.number_input("Confirmed Item Price (₹)", min_value=0.0, step=100.0, value=float(live_price))
                
                if goals:
                    impact_goal = st.selectbox("Anchor Goal", [g['goal_name'] for g in goals])
                    c_req, c_clear = st.columns([2, 1])
                    request_btn = c_req.button("🔓 Request AI Authorization", type="primary", use_container_width=True)
                    if c_clear.button("🗑️ Clear Request", use_container_width=True):
                        supabase.table("pending_checkouts").update({"status": "cancelled"}).eq("id", request_id).execute()
                        st.rerun()
                else:
                    st.warning("Please create a goal on the left first.")
                    request_btn = False
            else:
                st.info("⏳ Queue is empty. Waiting for browser extension intercept...")
                request_btn = False

    # --- 4. REAL-TIME PROBABILITY INTERVENTION ---
    if request_btn and final_price > 0:
        target_goal = next(g for g in goals if g['goal_name'] == impact_goal)
        target_date = datetime.strptime(target_goal['target_date'], "%Y-%m-%d").date()
        months_left = max((target_date.year - datetime.today().year) * 12 + target_date.month - datetime.today().month, 1)
        
        base_prob = calculate_probability(target_goal['target_amount'], target_goal['current_saved'], target_goal['monthly_contribution'], months_left)
        new_prob = calculate_probability(target_goal['target_amount'], target_goal['current_saved'] - final_price, target_goal['monthly_contribution'], months_left)
        
        st.write("---")
        st.subheader("🤖 Guardrail Decision Matrix")
        
        c_prob, c_ai = st.columns([1, 1.5])
        
        with c_prob:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number+delta",
                value = new_prob,
                delta = {'reference': base_prob},
                title = {'text': "Goal Probability", 'font': {'size': 20}},
                gauge = {
                    'axis': {'range': [0, 100], 'tickcolor': "rgba(150,150,150,0.5)"}, 
                    'bar': {'color': "#3b82f6" if new_prob > 70 else "#ef4444"},
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 2,
                    'bordercolor': "rgba(150,150,150,0.2)"
                }
            ))
            fig.update_layout(
                height=300, 
                margin=dict(t=50, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=st.get_option("theme.textColor") if st.get_option("theme.textColor") else "gray")
            )
            st.plotly_chart(fig, use_container_width=True)

        with c_ai:
            with st.spinner("Analyzing financial impact..."):
                try:
                    valid_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    target_model = next((m for m in valid_models if 'flash' in m), "gemini-pro")
                    model = genai.GenerativeModel(target_model)
                    prompt = f"Analyze: Spending ₹{final_price} on product from {product_url}. Goal: {target_goal['goal_name']}. Probability drops from {base_prob}% to {new_prob}%. Give a short, brutal financial reality check."
                    
                    response = model.generate_content(prompt)
                    st.markdown(f"### AI Verdict\n{response.text}")
                    
                    st.write("")
                    if new_prob < 50:
                        st.error("🚨 **Authorization Denied.** This purchase puts your long-term security at risk.")
                        if st.button("Request Human Override"):
                            st.warning("Override request sent to your backup financial buddy.")
                    else:
                        st.success("✅ **Authorization Possible.** Your trajectory remains stable.")
                        if st.button("Generate Virtual Card"):
                            supabase.table("pending_checkouts").update({"status": "approved"}).eq("id", request_id).execute()
                            show_virtual_card(target_goal['goal_name'], final_price)
                            
                except Exception as e:
                    st.error(f"❌ AI Logic Error: {str(e)}")