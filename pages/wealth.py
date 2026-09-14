"""Wealth — tabbed wrapper.

Groups: Investment Portfolio, Net Worth Tracker, Trust Engine (Loan Predictor).
"""
import streamlit as st
import pages.portfolio as portfolio
import pages.net_worth as net_worth
import pages.trust_engine as trust_engine


def render_page(supabase):
    st.markdown("""
        <div class="page-header">
            <h2>Wealth</h2>
            <p>Your investments, net worth, and borrowing power in one place</p>
        </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs([
        "📈 Portfolio",
        "🏦 Net Worth",
        "🏦 Trust Engine",
    ])

    with tabs[0]:
        portfolio.render_page(supabase)

    with tabs[1]:
        net_worth.render_page(supabase)

    with tabs[2]:
        trust_engine.render_page(supabase)