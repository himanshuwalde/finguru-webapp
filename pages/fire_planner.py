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
from utils.ui_components import render_gradient_header, render_alert_banner


def _inr(v) -> str:
    return f"₹{v:,.0f}"


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
            "Monthly expense (₹)", 0.0, 1e7,
            float(avg_expense if avg_expense else saved.get("monthly_expense", 30000)),
            key="fr_exp")
        corpus = st.number_input("Current corpus (₹)", 0.0, 1e11,
                                 float(saved.get("current_corpus", 0)), key="fr_corpus")
        ret = st.number_input("Expected return (% p.a.)", 0.0, 25.0,
                              float(saved.get("expected_return_pct", 10)), key="fr_ret")
    with c2:
        target_age = st.number_input("Target retirement age", cur_age, 90,
                                     int(saved.get("target_retirement_age", 45)),
                                     key="fr_target")
        invest = st.number_input("Monthly investment (₹)", 0.0, 1e7,
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
        payload = {
            "current_age": cur_age, "target_retirement_age": target_age,
            "monthly_expense": expense, "monthly_investment": invest,
            "current_corpus": corpus, "expected_return_pct": ret,
            "inflation_pct": infl, "safe_withdrawal_rate_pct": swr,
            "volatility_pct": vol, "n_simulations": int(n_sims),
        }
        svc.save_profile(user_id, payload)
        result = svc.run_and_save(user_id, payload, seed=42)  # reproducible demos
        if result:
            st.session_state.fire_result = result
            st.rerun()
        else:
            st.warning("Couldn't run — did you run migrations/001 in Supabase? "
                       "Tables `fire_profiles`/`fire_simulations` must exist.")
    with c2:
        if st.button("🗑 Clear last result", use_container_width=True):
            st.session_state.fire_result = None
            st.rerun()

    result = st.session_state.get("fire_result")
    if not result:
        if svc.get_profile(user_id) is None:
            render_alert_banner("No FIRE profile yet. Set your numbers above and "
                                "hit the run button.", "info")
        history = svc.get_recent_simulations(user_id)
        if history:
            st.markdown("##### Recent FIRE runs")
            hrows = [{"Target age": h["target_age"],
                      "Required corpus": _inr(h["required_corpus"]),
                      "Median corpus": _inr(h["projected_corpus"]),
                      "P(FIRE)": f"{h['probability_pct']:.0f}%",
                      "Run at": h["created_at"][:10]} for h in history]
            st.dataframe(pd.DataFrame(hrows), use_container_width=True, hide_index=True)
        return

    # ------------------------------------------------------------- results
    st.write("---")
    prob = result["probability_pct"]
    colour = "#22C55E" if prob >= 70 else "#F59E0B" if prob >= 40 else "#EF4444"
    st.markdown(
        f"<div style='background:linear-gradient(90deg,{colour}22,{colour}33);border:1px "
        f"solid {colour}55;border-radius:14px;padding:18px 22px;margin-bottom:14px'>"
        f"<span style='font-size:1.05rem'>Probability of FIRE</span> "
        f"<span style='font-size:2.6rem;font-weight:800;color:{colour}'> {prob:.0f}%</span>"
        f"<span style='color:#94a3b8'>  ·  {result['n_simulations']:,} Monte Carlo trials (seeded)</span>"
        f"</div>", unsafe_allow_html=True)
    st.progress(min(prob / 100.0, 1.0))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Required corpus @ retirement", _inr(result["required_corpus"]))
    c2.metric("Median projected corpus", _inr(result["median_corpus"]),
              f"{result['shortfall_vs_median']:,.0f} short" if not result["on_track"]
              else "✅ on track")
    c3.metric("p5 pessimist", _inr(result["p5_corpus"]))
    c4.metric("p95 optimist", _inr(result["p95_corpus"]))

    stat = st.columns(4)
    stat[0].metric("Projected FIRE age", f"{result['projected_fire_age'] or '∎'}")
    stat[1].metric("Years to FIRE", f"{result['years_to_retirement']:.0f}")
    stat[2].metric("Monthly expense then", _inr(result["future_monthly_expense"]))
    stat[3].metric("Annual expense then", _inr(result["annual_expense_at_retirement"]))

    # segmentation of "on track" narrative
    if result["on_track"]:
        msg = f"At {result['projected_fire_age'] or 'your target age'} your median "
        msg += "corpus clears the bar — you're likely on the path to FIRE."
    else:
        msg = f"Median corpus falls short of the target by "
        msg += _inr(result["shortfall_vs_median"]) + "."
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
                  annotation_text=f'Required {_inr(result["required_corpus"])}',
                  annotation_position="top left")
    fig.add_vline(x=result["median_corpus"] / 1e6,
                  line=dict(color="#22C55E", width=3),
                  annotation_text=f'Median {_inr(result["median_corpus"])}',
                  annotation_position="top right")
    fig.update_layout(height=360, margin=dict(t=10, b=10, l=10, r=10),
                      xaxis_title="Terminal corpus (₹ millions)",
                      yaxis_title="Trials",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      showlegend=False)
    st.plotly_chart(fig, use_container_width=True, key="fire_hist")

    # ------------------------------------------------------- run history
    history = svc.get_recent_simulations(user_id)
    if history:
        st.markdown("##### Recent FIRE runs")
        hrows = [{"Target age": h["target_age"],
                  "Required corpus": _inr(h["required_corpus"]),
                  "Median corpus": _inr(h["projected_corpus"]),
                  "P(FIRE)": f"{h['probability_pct']:.0f}%",
                  "p5–p95": f"{_inr(h['p5'])} – {_inr(h['p95'])}",
                  "Run at": h["created_at"][:10]} for h in history]
        st.dataframe(pd.DataFrame(hrows), use_container_width=True, hide_index=True)