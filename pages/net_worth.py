"""
Net Worth page — unified balance sheet dashboard.
Assets = bank balances (existing accounts) + investments (portfolio tracker),
Liabilities = debts entered here. Shows a hero net-worth figure and a monthly
growth chart of snapshots. Deterministic math from engines/networth_engine.py.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from services.networth_service import get_networth_service
from utils.ui_components import render_gradient_header, render_alert_banner

LIABILITY_TYPES = ["Home", "Education", "Car", "Credit Card", "Personal", "Other"]


def _inr(v) -> str:
    return f"₹{v:,.0f}"


def render_page(supabase):
    render_gradient_header(
        "🏦", "Net Worth Tracker",
        "Your total balance sheet in one place: assets minus liabilities, "
        "with a monthly snapshot growth chart.",
        gradient_colors=["#7C3AED", "#2563EB"],
    )
    st.write("---")

    svc = get_networth_service(supabase)
    user_id = st.session_state.user_id

    # ------------------------------------------------------------ liabilities entry
    with st.expander("➕ Add a liability (loan / debt)", expanded=False):
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            liability_type = st.selectbox("Type", LIABILITY_TYPES, key="nw_type")
        with c2:
            name = st.text_input("Name / lender", placeholder="e.g. HDFC Home Loan", key="nw_name")
        with c3:
            rate = st.number_input("Interest rate (% p.a.)", 0.0, 40.0, 0.0, key="nw_rate")
        amount = st.number_input("Outstanding amount (₹)", 0.0, 1e9, 0.0, key="nw_amount")

        if st.button("Save liability", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Please name the liability.")
            elif amount <= 0:
                st.error("Outstanding amount must be greater than zero.")
            else:
                ok = svc.add_liability(user_id, {
                    "liability_type": liability_type,
                    "name": name.strip(),
                    "outstanding_amount": amount,
                    "interest_rate": rate,
                })
                if ok:
                    st.success(f"Saved {name.strip()} ✅")
                    st.rerun()
                else:
                    st.warning("Couldn't save — did you run migrations/001 in Supabase? "
                               "Table `liabilities` must exist.")

    # ------------------------------------------------------------- net worth body
    net = svc.compute_networth(user_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net Worth", _inr(net["net_worth"]),
              f"Liabilities {_inr(net['total_liabilities'])}")
    c2.metric("Total Assets", _inr(net["total_assets"]))
    c3.metric("Bank & Cash", _inr(net["liquid_assets"]))
    c4.metric("Investments", _inr(net["investments_total"]))

    st.write("---")
    left, right = st.columns([1, 1])
    with left:
        st.markdown("##### Assets")
        rows = [{"Asset": a["name"], "Type": a["category"], "Value": _inr(a["amount"])}
                for a in net["assets_breakdown"]]
        if not rows:
            render_alert_banner("No assets yet — add a budget account in the "
                                "Dashboard or an investment in the Portfolio page.",
                                "info")
        else:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    with right:
        st.markdown("##### Liabilities")
        lrows = [{"Liability": l["name"], "Type": l["type"],
                  "Outstanding": _inr(l["outstanding_amount"])}
                 for l in net["liabilities_breakdown"]]
        if not lrows:
            render_alert_banner("No liabilities recorded 🎉", "success")
        else:
            st.dataframe(pd.DataFrame(lrows), use_container_width=True, hide_index=True)

    if net["liabilities_breakdown"]:
        st.markdown("##### Manage liabilities")
        for lrow in net["liabilities_breakdown"]:
            col = st.columns([4, 4, 2])
            col[0].markdown(f"**{lrow['name']}**   ·   {lrow['type']}")
            col[1].markdown(_inr(lrow["outstanding_amount"]))
            raw_id = next((r["id"] for r in svc.get_liabilities(user_id)
                           if r["name"] == lrow["name"]
                           and float(r["outstanding_amount"]) == lrow["outstanding_amount"]), None)
            if raw_id and col[2].button("Delete", key=f"nw_del_{raw_id}"):
                svc.delete_liability(raw_id)
                st.rerun()

    # ------------------------------------------------------------- growth chart
    st.write("---")
    st.markdown("##### Net worth growth (monthly snapshots)")
    c1, c2 = st.columns([3, 1])
    with c2:
        if st.button("📸 Record this month's snapshot", use_container_width=True):
            if svc.record_snapshot(user_id):
                st.success("Snapshot saved ✅")
                st.rerun()
            else:
                st.warning("Couldn't save — `net_worth_snapshots` table missing?")
    with c1:
        history = svc.get_snapshot_history(user_id)
        if history:
            df = pd.DataFrame(history)
            df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=df["snapshot_date"], y=df["net_worth"],
                                     name="Net Worth", mode="lines+markers",
                                     line=dict(color="#7C3AED", width=3),
                                     fill="tozeroy", fillcolor="rgba(124,58,237,0.10)"),
                          secondary_y=False)
            fig.add_trace(go.Bar(x=df["snapshot_date"], y=df["total_liabilities"],
                                 name="Liabilities", marker_color="#F59E0B",
                                 opacity=0.55), secondary_y=True)
            fig.update_layout(height=330, margin=dict(t=10, b=10, l=10, r=10),
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                              legend=dict(orientation="h", yanchor="bottom", y=1.02))
            fig.update_xaxes(title_text="")
            fig.update_yaxes(title_text="₹", secondary_y=False)
            fig.update_yaxes(title_text="Liabilities (₹)", secondary_y=True)
            st.plotly_chart(fig, use_container_width=True, key="nw_growth")
        else:
            render_alert_banner(
                "No snapshots yet. Record one now — do it monthly to build your "
                "wealth trajectory chart.", "info")