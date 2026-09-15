"""
FIRE Planner page — Financial Independence, Retire Early.
Deterministic corpus math + Monte Carlo (vectorised numpy) probability of
FIRE, plus a terminal-corpus histogram. Deterministic from fire_engine.py;
profile + run history persisted via services/fire_service.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engines import fire_engine
from services.fire_service import get_fire_service
from utils.ai_client import get_gemini_client, get_best_model, generate_content_safe
from utils.ai_persona import persona_and_currency_note
from utils.currency import fmt_input_label, fmt_label, fmt_money, symbol, to_inr
from utils.ui_components import render_gradient_header, render_alert_banner

# Future-self chat client (same pattern the old Financial Twin page used).
genai_client = get_gemini_client()


@st.dialog("Clear last result")
def confirm_clear_last_result():
    """Ask before wiping the current FIRE simulation result."""
    st.warning("Clear the current FIRE simulation result? "
               "You'll have to run the simulation again.")
    c1, c2 = st.columns(2)
    if c1.button("Yes, clear", type="primary", use_container_width=True):
        st.session_state.fire_result = None
        st.session_state.pop("twin_context", None)
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


def _render_future_self_chat():
    """💬 'Chat with your Future Self' — a Gemini persona grounded in the last
    FIRE run (expected return + p5 / median / p95 corpus). This is the chat the
    old Financial Twin page offered, now fed by the FIRE result instead of a
    duplicate unseeded Monte Carlo."""
    st.subheader("💬 Chat with your Future Self")
    ctx = st.session_state.get("twin_context")
    if not ctx:
        st.info("Run the FIRE simulation first — your future self needs your "
                "numbers to answer.")
        return

    st.markdown(
        f"Ask how a purchase today impacts your timeline (e.g., *'What happens "
        f"if I buy a {fmt_money(2000000)} car today instead of investing it?'*)")

    if "twin_messages" not in st.session_state:
        st.session_state.twin_messages = []

    for msg in st.session_state.twin_messages:
        with st.chat_message(msg["role"],
                             avatar="🧑‍🎓" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask your future self a question..."):
        st.chat_message("user", avatar="👤").markdown(prompt)
        st.session_state.twin_messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant", avatar="🧑‍🎓"):
            message_placeholder = st.empty()
            with st.spinner("Your future self is calculating..."):
                try:
                    target_model = get_best_model(genai_client, prefer_flash=True)
                    model = genai_client.GenerativeModel(target_model)

                    chat_history_str = "\n".join(
                        f"{msg['role'].upper()}: {msg['content']}"
                        for msg in st.session_state.twin_messages)

                    persona_cur = persona_and_currency_note()
                    system_prompt = f"""
                    {persona_cur}

                    You are the user's "Financial Twin"—their future self at age {ctx['age']}. User's Current age: {ctx['AGE']}.
                    Current expected retirement net worth: {fmt_money(ctx['median'])}
                    (Range: {fmt_money(ctx['worst_case'])} to {fmt_money(ctx['best_case'])}).
                    The user's actual current portfolio growth rate is {ctx['portfolio_return']}%.

                    Read the chat history to determine which phase you are in:

                    PHASE 1: THE WISDOM (Initial Response to a purchase idea)
                    - Speak in the first person ("I am you from the future...").
                    - Use very easy, simple, and understandable language. No complex financial jargon.
                    - Perform a "Time-Travel Cost Analysis" using their ACTUAL {ctx['portfolio_return']}% return rate to show exactly how much that money would have grown to by age {ctx['age']} if invested.
                    - Be empathetic but slightly dramatic about the "Opportunity Cost" (e.g., fleeting pleasure vs. a secure retirement).
                    - ALWAYS end Phase 1 by asking this exact question: "Anyhow, would you like me to guide you on how to buy this today with maximum benefits?"

                    PHASE 2: DAMAGE CONTROL (If the User says Yes/Agrees to be guided)
                    - Drop the dramatic act. Shift your tone to a highly supportive, savvy "Financial Strategist."
                    - Provide a step-by-step guide in simple language on how to buy the item smartly in the Indian market:
                      1. Mention using specific credit cards for high cashback or reward milestones.
                      2. Explain the "Arbitrage" concept simply: Compare typical loan interest rates (e.g., 8-9%) against their actual {ctx['portfolio_return']}% portfolio return. Explain why taking a loan might actually be smarter than paying cash if their investments grow faster than the loan interest.
                      3. Suggest timing the purchase (e.g., waiting for Diwali, year-end sales, or festive discounts).
                      4. Mention basic tax benefits if applicable.

                    Maintain a wise, protective, and easy-to-understand tone at all times.

                    --- CHAT HISTORY ---
                    {chat_history_str}
                    """

                    response_text = generate_content_safe(model, system_prompt)
                    if response_text:
                        message_placeholder.markdown(response_text)
                        st.session_state.twin_messages.append(
                            {"role": "assistant", "content": response_text})
                    else:
                        raise Exception("Empty response from model")

                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str or "Quota exceeded" in error_str:
                        st.error("⏳ **Traffic Jam!** Our AI is currently handling "
                                 "too many requests. Please wait 30 seconds and "
                                 "try again.")
                    else:
                        st.error(f"❌ **System Error:** {error_str}")


def render_page(supabase):
    render_gradient_header(
        "🔥", "FIRE Planner",
        "How close are you to Financial Independence & Retire Early? We run "
        "1,000s of Monte Carlo market trials to give a probability, not a guess.",
        gradient_colors=["#EF4444", "#F59E0B"],
    )
    st.write("---")

    svc = get_fire_service(supabase)
    user_id = st.session_state.user_id
    saved = svc.get_profile(user_id) or fire_engine.default_profile()
    avg_expense = svc.estimate_monthly_expense(user_id)

    c1, c2 = st.columns(2)
    with c1:
        cur_age = st.number_input("Current age", 18, 80,
                                  int(saved.get("current_age", 22)), key="fr_age")
        expense = st.number_input(
            fmt_input_label("Monthly expense"), 0.0, 1e7,
            float(avg_expense if avg_expense else saved.get("monthly_expense", 30000)),
            key="fr_exp")
        corpus = st.number_input(fmt_input_label("Current corpus"), 0.0, 1e11,
                                 float(saved.get("current_corpus", 0)), key="fr_corpus")
        ret = st.number_input("Expected return (% p.a.)", 0.0, 25.0,
                              float(saved.get("expected_return_pct", 10)), key="fr_ret")
    with c2:
        target_age = st.number_input("Target retirement age", cur_age, 90,
                                     int(saved.get("target_retirement_age", 45)),
                                     key="fr_target")
        invest = st.number_input(fmt_input_label("Monthly investment"), 0.0, 1e7,
                                 float(saved.get("monthly_investment", 20000)),
                                 key="fr_invest")
        infl = st.number_input("Inflation (% p.a.)", 0.0, 15.0,
                               float(saved.get("inflation_pct", 6)), key="fr_infl")
        swr = st.number_input("Safe withdrawal rate (% p.a.)", 1.0, 8.0,
                              float(saved.get("safe_withdrawal_rate_pct", 4)),
                              key="fr_swr")

    with st.expander("⚙️ Advanced (Monte Carlo settings)"):
        c1, c2 = st.columns(2)
        vol = c1.number_input("Portfolio volatility (% p.a.)", 1.0, 40.0,
                              fire_engine.DEFAULT_VOLATILITY_PCT, key="fr_vol")
        n_sims = c2.number_input("Number of simulations", 500, 20000, 3000,
                                 step=500, key="fr_nsim")

    c1, c2 = st.columns(2)
    if c1.button("▶️ Save profile & run FIRE simulation",
                 type="primary", use_container_width=True):
        # Convert from user's display currency to INR for storage
        payload = {
            "current_age": cur_age, "target_retirement_age": target_age,
            "monthly_expense": to_inr(expense), "monthly_investment": to_inr(invest),
            "current_corpus": to_inr(corpus), "expected_return_pct": ret,
            "inflation_pct": infl, "safe_withdrawal_rate_pct": swr,
            "volatility_pct": vol, "n_simulations": int(n_sims),
        }
        svc.save_profile(user_id, payload)
        result = svc.run_and_save(user_id, payload, seed=42)  # reproducible demos
        if result:
            st.session_state.fire_result = result
            # Ground the "Future Self" chat on this run — the old Financial Twin
            # re-simulated the same numbers; now it just re-reads the FIRE result.
            st.session_state.twin_context = {
                "age": target_age,
                "AGE": cur_age,
                "worst_case": result.get("p5_corpus") or 0.0,
                "median": result.get("median_corpus") or 0.0,
                "best_case": result.get("p95_corpus") or 0.0,
                "portfolio_return": ret,
            }
            st.rerun()
        else:
            st.warning("Couldn't run — did you run migrations/001 in Supabase? "
                       "Tables `fire_profiles`/`fire_simulations` must exist.")
    with c2:
        if st.button("🗑 Clear last result", use_container_width=True):
            confirm_clear_last_result()

    result = st.session_state.get("fire_result")
    if not result:
        if svc.get_profile(user_id) is None:
            render_alert_banner("No FIRE profile yet. Set your numbers above and "
                                "hit the run button.", "info")
        history = svc.get_recent_simulations(user_id)
        if history:
            st.markdown("##### Recent FIRE runs")
            hrows = [{"Target age": h["target_age"],
                      "Required corpus": fmt_money(h["required_corpus"]),
                      "Median corpus": fmt_money(h["projected_corpus"]),
                      "P(FIRE)": f"{h['probability_pct']:.0f}%",
                      "Run at": h["created_at"][:10]} for h in history]
            st.dataframe(pd.DataFrame(hrows), use_container_width=True, hide_index=True)
        st.write("---")
        _render_future_self_chat()
        return

    # ------------------------------------------------------------- results
    st.write("---")
    prob = result["probability_pct"]
    colour = "#22C55E" if prob >= 70 else "#F59E0B" if prob >= 40 else "#EF4444"
    st.markdown(
        f"<div style='background:var(--secondary-background-color);border:1px solid "
        f"{colour}33;border-radius:8px;padding:16px 20px;margin-bottom:14px'>"
        f"<span style='font-size:.95rem;color:var(--text-color);opacity:.7'>Probability of FIRE</span> "
        f"<span style='font-size:2rem;font-weight:700;color:{colour}'> {prob:.0f}%</span>"
        f"<span style='color:#94a3b8;font-size:.85rem'>  ·  {result['n_simulations']:,} Monte Carlo trials (seeded)</span>"
        f"</div>", unsafe_allow_html=True)
    st.progress(min(prob / 100.0, 1.0))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Required corpus @ retirement", fmt_money(result["required_corpus"]))
    c2.metric("Median projected corpus", fmt_money(result["median_corpus"]),
              f"{result['shortfall_vs_median']:,.0f} short" if not result["on_track"]
              else "✅ on track")
    c3.metric("p5 pessimist", fmt_money(result["p5_corpus"]))
    c4.metric("p95 optimist", fmt_money(result["p95_corpus"]))

    stat = st.columns(4)
    stat[0].metric("Projected FIRE age", f"{result['projected_fire_age'] or '∎'}")
    stat[1].metric("Years to FIRE", f"{result['years_to_retirement']:.0f}")
    stat[2].metric("Monthly expense then", fmt_money(result["future_monthly_expense"]))
    stat[3].metric("Annual expense then", fmt_money(result["annual_expense_at_retirement"]))

    # segmentation of "on track" narrative
    if result["on_track"]:
        msg = f"At {result['projected_fire_age'] or 'your target age'} your median "
        msg += "corpus clears the bar — you're likely on the path to FIRE."
    else:
        msg = f"Median corpus falls short of the target by "
        msg += fmt_money(result["shortfall_vs_median"]) + "."
    render_alert_banner(msg, "success" if result["on_track"] else "warning")

    # ------------------------------------------------------- histogram draw
    st.write("---")
    st.markdown("##### Terminal corpus distribution (Monte Carlo)")
    terminal = fire_engine.monte_carlo_terminal(
        corpus, invest, result["years_to_retirement"], ret, vol, int(n_sims), seed=42)
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=terminal / 1e6, nbinsx=60,
                               marker_color="#F59E0B", opacity=0.7, name="trials"))
    fig.add_vline(x=result["required_corpus"] / 1e6,
                  line=dict(color="#EF4444", width=3, dash="dash"),
                  annotation_text=f'Required {fmt_money(result["required_corpus"])}',
                  annotation_position="top left")
    fig.add_vline(x=result["median_corpus"] / 1e6,
                  line=dict(color="#22C55E", width=3),
                  annotation_text=f'Median {fmt_money(result["median_corpus"])}',
                  annotation_position="top right")
    fig.update_layout(height=360, margin=dict(t=10, b=10, l=10, r=10),
                      xaxis_title=f"Terminal corpus ({symbol()} millions)",
                      yaxis_title="Trials",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=False)
    st.plotly_chart(fig, use_container_width=True, key="fire_hist")

    # ------------------------------------------------------- run history
    history = svc.get_recent_simulations(user_id)
    if history:
        st.markdown("##### Recent FIRE runs")
        hrows = [{"Target age": h["target_age"],
                  "Required corpus": fmt_money(h["required_corpus"]),
                  "Median corpus": fmt_money(h["projected_corpus"]),
                  "P(FIRE)": f"{h['probability_pct']:.0f}%",
                  "p5–p95": f"{fmt_money(h['p5'])} – {fmt_money(h['p95'])}",
                  "Run at": h["created_at"][:10]} for h in history]
        st.dataframe(pd.DataFrame(hrows), use_container_width=True, hide_index=True)

    # ------------------------------------------------------ future self chat
    st.write("---")
    _render_future_self_chat()