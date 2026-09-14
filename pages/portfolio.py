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
from services import market_data_service as mkt
from services.portfolio_service import get_portfolio_service
from utils.currency import fmt_label, fmt_money
from utils.ui_components import render_gradient_header, render_alert_banner

ASSET_TYPES = ["Stock", "Mutual Fund", "FD", "Gold", "Property", "Other"]


@st.dialog("Delete investment")
def confirm_delete_stock(svc, name, inv_id):
    """Ask before permanently deleting a holding from the portfolio."""
    st.warning(f"Permanently delete **{name}** from your portfolio? "
               "This cannot be undone.")
    c1, c2 = st.columns(2)
    if c1.button("Yes, delete", type="primary", use_container_width=True):
        svc.delete_investment(inv_id)
        st.rerun()
    if c2.button("Cancel", use_container_width=True):
        st.rerun()


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
            common["buy_price"] = c2.number_input(fmt_label("Buy price (₹)"), 0.0, 1e8, 0.0, key="pf_buy")
            common["current_price"] = c3.number_input(fmt_label("Current price (₹)"), 0.0, 1e8, 0.0, key="pf_cp")
        elif asset_type == "Mutual Fund":
            c1, c2, c3 = st.columns(3)
            common["units"] = c1.number_input("Units", 0.0, 1e8, 0.0, key="pf_units")
            common["purchase_nav"] = c2.number_input(fmt_label("Purchase NAV (₹)"), 0.0, 1e5, 0.0, key="pf_pnav")
            common["current_nav"] = c3.number_input(fmt_label("Current NAV (₹)"), 0.0, 1e5, 0.0, key="pf_cnav")
        elif asset_type == "FD":
            c1, c2, c3 = st.columns(3)
            common["principal"] = c1.number_input(fmt_label("Principal (₹)"), 0.0, 1e9, 0.0, key="pf_princ")
            common["interest_rate"] = c2.number_input("Interest rate (% p.a.)", 0.0, 20.0, 7.0, key="pf_rate")
            c3.write("")
            common["start_date"] = c3.date_input("Start date", value=date(2024, 1, 1), key="pf_std")
            common["maturity_date"] = st.date_input(
                "Maturity date (optional)", value=None, key="pf_mtd")
        elif asset_type in ("Gold", "Property", "Other"):
            c1, c2 = st.columns(2)
            common["invested_amount"] = c1.number_input(fmt_label("Invested amount (₹)"), 0.0, 1e9, 0.0, key="pf_inv")
            common["current_value"] = c2.number_input(fmt_label("Current value (₹)"), 0.0, 1e9, 0.0, key="pf_cv")
        if asset_type in ("Stock", "Mutual Fund"):
            common["ticker"] = st.text_input(
                "Ticker / MF code (optional)",
                placeholder="e.g. RELIANCE.NS   (Yahoo symbol; .NS / .BO for NSE/BSE)",
                help="Yahoo Finance symbol for live pricing, e.g. RELIANCE.NS or "
                     "HDFCBANK.BO. Leave blank to use the price you enter above. "
                     "Stocks & listed direct-equity MFs auto-update daily; schemes "
                     "Yahoo doesn't list fall back to your manual price.",
                key="pf_ticker",
            )
        else:
            common["ticker"] = None
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
    # Live prices overlay the stored manual values at READ time only — the DB
    # price stays the fallback. All metrics below therefore react to the real
    # market while a missing/offline ticker silently keeps the manual value.
    raw_investments = svc.get_investments(user_id)
    overlaid = mkt.overlay_live_prices(raw_investments)
    summary = portfolio_engine.portfolio_summary(overlaid)
    live_flags = []
    for h, raw in zip(summary["holdings"], raw_investments):
        ticker = (raw.get("ticker") or "").strip()
        live_flags.append(bool(ticker) and mkt.live_price(ticker) is not None)
    n_live = sum(live_flags)
    if n_live:
        st.toast(f"🟢 Live prices for {n_live} holding(s) · as of {summary['as_of']}")

    if not summary["holdings"]:
        render_alert_banner("No investments yet. Add your first stock, MF or FD "
                            "using the form above.", "info")
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Invested", fmt_money(summary["total_invested"]))
    c2.metric("Current Value", fmt_money(summary["total_current"]))
    c3.metric("Returns", fmt_money(summary["absolute_return"]),
              f"{summary['return_pct']:+.1f}%")
    c4.metric("Portfolio XIRR", f"{summary['xirr_pct']:.1f}%")
    c5.metric("As of", summary["as_of"])

    refresh_col, live_note = st.columns([1, 5])
    with refresh_col:
        if st.button("🔄 Refresh prices", use_container_width=True):
            mkt.clear_cache()
            st.rerun()
    with live_note:
        if n_live:
            st.caption(f"🟢 Live prices for {n_live} of "
                       f"{len(summary['holdings'])} holdings · "
                       f"as of {summary['as_of']} — refreshes on every visit.")
        else:
            st.caption("Showing your manual prices. Add a Yahoo ticker "
                       "(e.g. RELIANCE.NS) on a stock or MF for live prices.")

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
                 "Invested": fmt_money(h["invested_amount"]),
                 "Current": fmt_money(h["current_value"]),
                 "Price": "🟢 Live" if live_flags[i] else "⚪ Manual",
                 "Return": f"{h['return_pct']:+.1f}%",
                 "Date": h["date"] or "—"} for i, h in enumerate(summary["holdings"])]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # -------------------------------------------------------------- health
    st.write("---")
    score, insights = portfolio_engine.portfolio_health(overlaid, risk)
    st.markdown("##### Portfolio Health Score")
    st.progress(min(score / 100, 1.0))
    st.markdown(f"**{score} / 100**" + (" — ✅ healthy" if score >= 70
                else " — ⚠️ needs attention" if score >= 40 else " — 🚨 review"))
    for msg in insights:
        st.markdown(f"- {msg}")

    # --------------------------------------------------------------- delete
    st.write("---")
    st.markdown("##### Manage holdings")
    for idx, h in enumerate(summary["holdings"]):
        row = st.columns([4, 4, 2])
        row[0].markdown(f"**{h['name']}**   ·   {h['asset_type']}")
        row[1].markdown(f"{fmt_money(h['invested_amount'])} → {fmt_money(h['current_value'])}")
        # id comes from the same fetch order as the holdings list, so the live
        # price overlay never breaks the lookup (no name+amount guessing).
        inv_id = raw_investments[idx].get("id") if idx < len(raw_investments) else None
        if inv_id and row[2].button("Delete", key=f"del_{inv_id}"):
            confirm_delete_stock(svc, h["name"], inv_id)