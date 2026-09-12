"""
Portfolio page — Manual Investment Tracker.
Track stocks / mutual funds / FDs / gold / property; visualise allocation,
returns (incl. XIRR) and a Portfolio Health Score. Deterministic analytics from
engines/portfolio_engine.py; CRUD via services/portfolio_service.py.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from engines import portfolio_engine
from services.portfolio_service import get_portfolio_service
from utils.ui_components import render_gradient_header, render_alert_banner

ASSET_TYPES = ["Stock", "Mutual Fund", "FD", "Gold", "Property", "Other"]


def _inr(v) -> str:
    return f"₹{v:,.0f}"


def render_page(supabase):
    render_gradient_header(
        "📈", "Investment Portfolio",
        "Track stocks, mutual funds, FDs and more manually — with returns, "
        "allocation and a data-driven Portfolio Health Score.",
        gradient_colors=["#059669", "#2563EB"],
    )
    st.write("---")

    svc = get_portfolio_service(supabase)
    user_id = st.session_state.user_id

    risk = st.selectbox("Your declared risk tolerance (for the health score)",
                        list(portfolio_engine.RISK_TARGET.keys()), index=1)

    # ------------------------------------------------------------- add form
    with st.expander("➕ Add an investment", expanded=False):
        c1, c2 = st.columns([1, 2])
        with c1:
            asset_type = st.selectbox("Asset type", ASSET_TYPES)
        with c2:
            name = st.text_input("Name", placeholder="e.g. HDFC Flexi Cap")
        common = {}
        if asset_type == "Stock":
            c1, c2, c3 = st.columns(3)
            common["quantity"] = c1.number_input("Quantity", 0.0, 1e6, 1.0, key="pf_qty")
            common["buy_price"] = c2.number_input("Buy price (₹)", 0.0, 1e8, 0.0, key="pf_buy")
            common["current_price"] = c3.number_input("Current price (₹)", 0.0, 1e8, 0.0, key="pf_cp")
        elif asset_type == "Mutual Fund":
            c1, c2, c3 = st.columns(3)
            common["units"] = c1.number_input("Units", 0.0, 1e8, 0.0, key="pf_units")
            common["purchase_nav"] = c2.number_input("Purchase NAV (₹)", 0.0, 1e5, 0.0, key="pf_pnav")
            common["current_nav"] = c3.number_input("Current NAV (₹)", 0.0, 1e5, 0.0, key="pf_cnav")
        elif asset_type == "FD":
            c1, c2, c3 = st.columns(3)
            common["principal"] = c1.number_input("Principal (₹)", 0.0, 1e9, 0.0, key="pf_princ")
            common["interest_rate"] = c2.number_input("Interest rate (% p.a.)", 0.0, 20.0, 7.0, key="pf_rate")
            c3.write("")
            common["start_date"] = c3.date_input("Start date", value=date(2024, 1, 1), key="pf_std")
            common["maturity_date"] = st.date_input(
                "Maturity date (optional)", value=None, key="pf_mtd")
        elif asset_type in ("Gold", "Property", "Other"):
            c1, c2 = st.columns(2)
            common["invested_amount"] = c1.number_input("Invested amount (₹)", 0.0, 1e9, 0.0, key="pf_inv")
            common["current_value"] = c2.number_input("Current value (₹)", 0.0, 1e9, 0.0, key="pf_cv")
        common["purchased_on"] = st.date_input("Purchase date",
                                               value=date.today(), key="pf_date")
        common["notes"] = st.text_input("Notes (optional)", key="pf_notes")

        if st.button("Save investment", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Please enter a name for the investment.")
            elif asset_type == "Stock" and not (common["buy_price"] and common["current_price"]):
                st.error("Enter both buy price and current price for a stock.")
            elif asset_type == "Mutual Fund" and not (common["units"] and common["current_nav"]):
                st.error("Enter units and current NAV for a mutual fund.")
            else:
                payload = {"asset_type": asset_type, "name": name.strip(), **common}
                if svc.add_investment(user_id, payload):
                    st.success(f"Added {name.strip()} ✅")
                    st.rerun()
                else:
                    st.warning("Couldn't save — did you run migrations/001 in Supabase? "
                               "Table `investments` must exist.")

    # ------------------------------------------------------------- analytics
    summary = svc.get_summary(user_id)

    if not summary["holdings"]:
        render_alert_banner("No investments yet. Add your first stock, MF or FD "
                            "using the form above.", "info")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Invested", _inr(summary["total_invested"]))
    c2.metric("Current Value", _inr(summary["total_current"]))
    c3.metric("Returns", _inr(summary["absolute_return"]),
              f"{summary['return_pct']:+.1f}%")
    c4.metric("Portfolio XIRR", f"{summary['xirr_pct']:.1f}%")
    c5.metric("As of", summary["as_of"])

    st.write("---")
    left, right = st.columns([1, 1])
    with left:
        st.markdown("##### Allocation by asset class")
        alloc = summary["allocation"]
        fig = px.pie(
            pd.DataFrame(alloc),
            names="asset_type", values="current", hole=0.5,
            color_discrete_sequence=px.colors.qualitative.Bold,
        )
        fig.update_traces(textinfo="percent+label")
        fig.update_layout(height=320, margin=dict(t=10, b=10, l=10, r=10),
                          showlegend=False,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True, key="pf_donut")
    with right:
        st.markdown("##### Holdings")
        rows = [{"Name": h["name"], "Type": h["asset_type"],
                 "Invested": _inr(h["invested_amount"]),
                 "Current": _inr(h["current_value"]),
                 "Return": f"{h['return_pct']:+.1f}%",
                 "Date": h["date"] or "—"} for h in summary["holdings"]]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # -------------------------------------------------------------- health
    st.write("---")
    score, insights = svc.get_health(user_id, risk)
    st.markdown("##### Portfolio Health Score")
    st.progress(min(score / 100, 1.0))
    st.markdown(f"**{score} / 100**" + (" — ✅ healthy" if score >= 70
                else " — ⚠️ needs attention" if score >= 40 else " — 🚨 review"))
    for msg in insights:
        st.markdown(f"- {msg}")

    # --------------------------------------------------------------- delete
    st.write("---")
    st.markdown("##### Manage holdings")
    for h in summary["holdings"]:
        row = st.columns([4, 4, 2])
        row[0].markdown(f"**{h['name']}**   ·   {h['asset_type']}")
        row[1].markdown(f"{_inr(h['invested_amount'])} → {_inr(h['current_value'])}")
        inv_id = None
        # find the real row id for a robust delete (match by name+amount)
        for raw in svc.get_investments(user_id):
            if raw["name"] == h["name"] and float(raw["current_value"]) == h["current_value"]:
                inv_id = raw["id"]
                break
        if inv_id and row[2].button("Delete", key=f"del_{inv_id}"):
            svc.delete_investment(inv_id)
            st.rerun()