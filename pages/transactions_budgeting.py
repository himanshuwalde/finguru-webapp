"""Transactions & Budgeting — tabbed wrapper.

Groups: Transactions, Anomaly Finder, Ghost Spend Auditor,
        Safe-to-Spend Engine, Bank Sync (Live AA).
"""
import streamlit as st
import pages.transactions as transactions
import pages.anomalies as anomalies
import pages.ghost_auditor as ghost_auditor
import pages.safe_to_spend as safe_to_spend
import pages.account_aggregator as account_aggregator


def render_page(supabase):
    st.markdown("""
        <div class="page-header">
            <h2>Transactions & Budgeting</h2>
            <p>Track spending, detect anomalies, and manage bank connections</p>
        </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs([
        "📝 Transactions",
        "🔍 Anomaly Finder",
        "👻 Ghost Spend Auditor",
        "🚦 Safe to Spend",
        "🔗 Bank Sync",
    ])

    with tabs[0]:
        transactions.render_page(supabase)

    with tabs[1]:
        anomalies.render_page(supabase)

    with tabs[2]:
        ghost_auditor.render_page(supabase)

    with tabs[3]:
        safe_to_spend.render_page(supabase)

    with tabs[4]:
        account_aggregator.render_page(supabase)
