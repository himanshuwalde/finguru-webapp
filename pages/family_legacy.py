"""Family & Legacy — tabbed wrapper.

Groups: Family Wealth Dashboard, Legacy Agent (Asset Discovery).
"""
import streamlit as st
import pages.family_wealth as family_wealth
import pages.legacy_agent as legacy_agent


def render_page(supabase):
    st.markdown("""
        <div class="page-header">
            <h2>Family & Legacy</h2>
            <p>Family finances and intergenerational wealth transfer</p>
        </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs([
        "👨‍👩‍👧 Family Dashboard",
        "🌳 Legacy Agent",
    ])

    with tabs[0]:
        family_wealth.render_page(supabase)

    with tabs[1]:
        legacy_agent.render_page(supabase)