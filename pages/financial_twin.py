import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from utils.ai_client import get_gemini_client, get_best_model, generate_content_safe

# Initialize AI client
genai_client = get_gemini_client()

def run_monte_carlo(initial_amount, annual_contribution, years, mu, sigma, simulations=500):
    """Runs a Monte Carlo simulation for portfolio growth."""
    # Create an array to hold all simulation paths
    portfolio_paths = np.zeros((years + 1, simulations))
    portfolio_paths[0] = initial_amount
    
    # Simulate year-by-year growth
    for t in range(1, years + 1):
        # Random market return for this year across all simulations
        random_returns = np.random.normal(loc=mu, scale=sigma, size=simulations)
        # Apply growth and add the annual contribution
        portfolio_paths[t] = portfolio_paths[t-1] * (1 + random_returns) + annual_contribution
        
    return portfolio_paths

def render_page(supabase):
    # ✨ THE FIX: Moved gradient styles to a dedicated CSS class with !important tags to prevent Streamlit render glitches
    st.markdown("""
        <style>
        .twin-header-title {
            margin: 0 !important; 
            padding: 0 !important; 
            background: linear-gradient(45deg, #8b5cf6, #3b82f6) !important; 
            -webkit-background-clip: text !important; 
            background-clip: text !important; 
            -webkit-text-fill-color: transparent !important; 
            color: transparent !important; 
            display: inline-block !important; 
            width: fit-content !important;
        }
        </style>
        
        <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 5px;">
            <div style="font-size: 2.2rem; background: var(--secondary-background-color); padding: 12px; border-radius: 16px; box-shadow: 0 4px 10px rgba(0,0,0,0.05);">🤖</div>
            <h1 class="twin-header-title">Financial Twin Simulator</h1>
        </div>
        <p style="color: var(--text-color); opacity: 0.7; font-size: 1.1rem; margin-bottom: 2rem; padding-left: 5px;">Run thousands of probability-based market scenarios and chat with an AI simulation of your future self.</p>
    """, unsafe_allow_html=True)

    # --- 1. FETCH BASELINE DATA (PRIMARY ACCOUNT ONLY) ---
    try:
        acc_response = supabase.table("accounts").select("*").eq("user_id", st.session_state.user_id).order("created_at").execute()
        user_accounts = acc_response.data
        
        primary_acc = next((acc for acc in user_accounts if acc.get('is_primary')), None)
        
        if primary_acc:
            current_net_worth = float(primary_acc.get('balance', 0.0))
        elif len(user_accounts) > 0: # Fallback to first account if no primary is set
            current_net_worth = float(user_accounts[0].get('balance', 0.0))
        else:
            current_net_worth = 0.0
    except Exception:
        current_net_worth = 0.0

    # --- 2. USER INPUTS (SIMULATION PARAMETERS) ---
    st.write("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        current_age = st.number_input("Current Age", min_value=18, max_value=80, value=25)
        retirement_age = st.number_input("Target Retirement Age", min_value=current_age+1, max_value=100, value=60)
    with c2:
        monthly_saving = st.number_input("Monthly Contribution (₹)", min_value=0, value=15000, step=1000)
        # This forces the starting value to be at least 0.0
        starting_value = max(0.0, float(current_net_worth))

        starting_amount = st.number_input(
            "Starting Capital (₹)", 
            min_value=0.0, 
            value=starting_value, 
            step=10000.0
        )
    with c3:
        risk_profile = st.selectbox("Investment Risk Profile", ["Conservative (Low Risk)", "Balanced (Medium Risk)", "Aggressive (High Risk)"], index=1)
        
    years_to_grow = retirement_age - current_age
    annual_contribution = monthly_saving * 12

    # Map risk to Expected Return (mu) and Volatility (sigma)
    if risk_profile.startswith("Conservative"):
        mu, sigma = 0.06, 0.05
    elif risk_profile.startswith("Balanced"):
        mu, sigma = 0.10, 0.12
    else:
        mu, sigma = 0.14, 0.20

    # --- 3. RUN MONTE CARLO ---
    if st.button("🚀 Run Monte Carlo Simulation", type="primary", use_container_width=True):
        with st.spinner(f"Running 500 parallel market simulations over {years_to_grow} years..."):
            paths = run_monte_carlo(starting_amount, annual_contribution, years_to_grow, mu, sigma, simulations=500)
            
            # Calculate percentiles across the simulations for each year
            percentile_10 = np.percentile(paths, 10, axis=1) # Worst-case scenario (10th percentile)
            percentile_50 = np.percentile(paths, 50, axis=1) # Median scenario
            percentile_90 = np.percentile(paths, 90, axis=1) # Best-case scenario (90th percentile)
            
            years_array = np.arange(current_age, retirement_age + 1)

            # Store final values in session state for the AI Twin to use
            st.session_state.twin_context = {
                "age": retirement_age,
                "AGE": current_age,
                "worst_case": percentile_10[-1],
                "median": percentile_50[-1],
                "best_case": percentile_90[-1],
                "portfolio_return": mu * 100 # ✨ NEW: Save the actual percentage return to pass to the AI
            }

            # --- 4. PLOTLY PROJECTION CHART ---
            fig = go.Figure()

            # Add 90th Percentile (Upper Bound)
            fig.add_trace(go.Scatter(x=years_array, y=percentile_90, mode='lines', line=dict(width=0), showlegend=False))
            
            # Add 10th Percentile (Lower Bound) and fill up to the 90th percentile
            fig.add_trace(go.Scatter(x=years_array, y=percentile_10, mode='lines', line=dict(width=0), 
                                     fill='tonexty', fillcolor='rgba(46, 204, 113, 0.2)', name='Probability Range (10% - 90%)'))
            
            # Add Median (The Expected Path)
            fig.add_trace(go.Scatter(x=years_array, y=percentile_50, mode='lines', line=dict(color='#2563EB', width=3), name='Expected Trajectory (Median)'))

            # ✨ THE FIX: Transparent backgrounds for seamless dark/light mode integration
            fig.update_layout(
                title="Probability-Based Wealth Projection",
                xaxis_title="Age",
                yaxis_title="Net Worth (₹)",
                hovermode="x unified",
                margin=dict(t=40, b=10, l=10, r=10),
                height=450,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Show final outcome metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("📉 Pessimistic (Bottom 10%)", f"₹{percentile_10[-1]:,.0f}")
            m2.metric("🎯 Expected (Median)", f"₹{percentile_50[-1]:,.0f}")
            m3.metric("🚀 Optimistic (Top 10%)", f"₹{percentile_90[-1]:,.0f}")

    # --- 5. THE AI "FUTURE SELF" CHAT ---
    st.write("---")
    st.subheader("💬 Chat with your Future Self")
    st.markdown("Ask how a purchase today impacts your timeline (e.g., *'What happens if I buy a ₹20 Lakh car today instead of investing it?'*)")

    if 'twin_messages' not in st.session_state:
        st.session_state.twin_messages = []

    # Display chat history
    for msg in st.session_state.twin_messages:
        with st.chat_message(msg["role"], avatar="🧑‍🎓" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])

    # Handle new chat input
    if prompt := st.chat_input("Ask your future self a question..."):
        # 1. Show user message
        st.chat_message("user", avatar="👤").markdown(prompt)
        st.session_state.twin_messages.append({"role": "user", "content": prompt})

        # 2. Check if simulation was run to give AI context
        context_data = st.session_state.get('twin_context', None)
        if not context_data:
            err = "Please run the Monte Carlo simulation first so I know what our future looks like!"
            st.chat_message("assistant", avatar="🧑‍🎓").markdown(err)
            st.session_state.twin_messages.append({"role": "assistant", "content": err})
        else:
            # 3. Call Gemini
            with st.chat_message("assistant", avatar="🧑‍🎓"):
                message_placeholder = st.empty()
                with st.spinner("Your future self is calculating..."):
                    try:
                        target_model = get_best_model(genai_client, prefer_flash=True)
                        model = genai_client.GenerativeModel(target_model)

                        # Pass the chat history so the AI remembers if it asked a question
                        chat_history_str = "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in st.session_state.twin_messages])

                        # Optimized prompt with state-dependent logic and actual portfolio values
                        system_prompt = f"""
                        You are the user's "Financial Twin"—their future self at age {context_data['age']}. User's Current age: {context_data['AGE']}.
                        Current expected retirement net worth: ₹{context_data['median']:,.0f}
                        (Range: ₹{context_data['worst_case']:,.0f} to ₹{context_data['best_case']:,.0f}).
                        The user's actual current portfolio growth rate is {context_data['portfolio_return']}%.

                        Read the chat history to determine which phase you are in:

                        PHASE 1: THE WISDOM (Initial Response to a purchase idea)
                        - Speak in the first person ("I am you from the future...").
                        - Use very easy, simple, and understandable language. No complex financial jargon.
                        - Perform a "Time-Travel Cost Analysis" using their ACTUAL {context_data['portfolio_return']}% return rate to show exactly how much that money would have grown to by age {context_data['age']} if invested.
                        - Be empathetic but slightly dramatic about the "Opportunity Cost" (e.g., fleeting pleasure vs. a secure retirement).
                        - ALWAYS end Phase 1 by asking this exact question: "Anyhow, would you like me to guide you on how to buy this today with maximum benefits?"

                        PHASE 2: DAMAGE CONTROL (If the User says Yes/Agrees to be guided)
                        - Drop the dramatic act. Shift your tone to a highly supportive, savvy "Financial Strategist."
                        - Provide a step-by-step guide in simple language on how to buy the item smartly in the Indian market:
                          1. Mention using specific credit cards for high cashback or reward milestones.
                          2. Explain the "Arbitrage" concept simply: Compare typical loan interest rates (e.g., 8-9%) against their actual {context_data['portfolio_return']}% portfolio return. Explain why taking a loan might actually be smarter than paying cash if their investments grow faster than the loan interest.
                          3. Suggest timing the purchase (e.g., waiting for Diwali, year-end sales, or festive discounts).
                          4. Mention basic tax benefits if applicable.

                        Maintain a wise, protective, and easy-to-understand tone at all times.

                        --- CHAT HISTORY ---
                        {chat_history_str}
                        """

                        response_text = generate_content_safe(model, system_prompt)

                        if response_text:
                            message_placeholder.markdown(response_text)
                            st.session_state.twin_messages.append({"role": "assistant", "content": response_text})
                        else:
                            raise Exception("Empty response from model")

                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "Quota exceeded" in error_str:
                            st.error("⏳ **Traffic Jam!** Our AI is currently handling too many requests. Please wait 30 seconds and try again.")
                        else:
                            st.error(f"❌ **System Error:** {error_str}")                   