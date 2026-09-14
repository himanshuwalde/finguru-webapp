"""Goals & Predictions — tabbed wrapper.

Groups: FIRE Planner, AI Insurance Advisor, Financial Twin Simulation,
        Financial Guardrail.
"""
import streamlit as st
import pages.fire_planner as fire_planner
import pages.insurance as insurance
import pages.financial_twin as financial_twin
import pages.financial_guardrail as financial_guardrail


def render_page(supabase):
    st.markdown("""
        <div class="page-header">
            <h2>Goals & Predictions</h2>
            <p>Plan your retirement, protect yourself, and simulate your future</p>
        </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs([
        "🔥 FIRE Planner",
        "🛡️ Insurance Advisor",
        "🤖 Financial Twin",
        "🛑 Guardrail",
    ])

    with tabs[0]:
        fire_planner.render_page(supabase)

    with tabs[1]:
        insurance.render_page(supabase)

    with tabs[2]:
        financial_twin.render_page(supabase)

    with tabs[3]:
        financial_guardrail.render_page(supabase)