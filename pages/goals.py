"""Goals & Protection — tabbed wrapper.

Groups: FIRE Planner (with the AI Future-Self chat), AI Insurance Advisor,
        Financial Guardrail.
"""
import streamlit as st
import pages.fire_planner as fire_planner
import pages.insurance as insurance
import pages.financial_guardrail as financial_guardrail


def render_page(supabase):
    st.markdown("""
        <div class="page-header">
            <h2>Goals & Protection</h2>
            <p>Plan your retirement, protect yourself, and simulate your future</p>
        </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs([
        "🔥 FIRE Planner",
        "🛡️ Insurance Advisor",
        "🛑 Guardrail",
    ])

    with tabs[0]:
        fire_planner.render_page(supabase)

    with tabs[1]:
        insurance.render_page(supabase)

    with tabs[2]:
        financial_guardrail.render_page(supabase)