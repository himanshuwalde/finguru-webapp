"""
Tax Planner page — Income Tax Engine (old vs new regime).
Deterministic computation via engines/tax_engine.py; persistence via
services/tax_service.py. Results are the SAME dict later used to ground the
AI CA chatbot (see ai/context_builder.py).
"""
from __future__ import annotations

import streamlit as st
import pandas as pd

from engines import tax_engine
from services.tax_service import get_tax_service
from utils.ui_components import render_gradient_header, render_alert_banner


def _income_keys() -> list:
    return ["salary", "bonus", "interest_income", "rental_income",
            "ltcg", "stcg", "other_income"]


def _deduction_keys() -> list:
    return ["sec_80c", "sec_80d_self", "sec_80d_parents", "sec_80ccd_1b",
            "sec_80g", "nps_employer", "home_loan_interest"]


def render_page(supabase):
    render_gradient_header(
        "🧾", "Tax Planner",
        "Compare your tax under the Old & New regimes with real deductions — "
        "80C, 80D, HRA and home-loan interest (Sec 24(b)).",
        gradient_colors=["#2563EB", "#9333EA"],
    )
    st.write("---")

    svc = get_tax_service(supabase)
    years = tax_engine.list_available_assessment_years() or ["2026-27"]

    # --- load existing declaration (if any) to prefill ---------------------
    fy = st.selectbox("Assessment Year", years, key="tax_fy")
    saved = svc.get_profile(st.session_state.user_id, fy)
    default = (svc.profile_to_inputs(saved, fy) if saved
               else tax_engine.default_inputs())
    default["financial_year"] = fy
    if saved:
        st.caption(f"✏️ Prefilled from your saved declaration for AY {fy}.")

    st.subheader("1️⃣ Personal & Income")
    c1, c2, c3 = st.columns(3)
    with c1:
        age = st.number_input("Age", 18, 90, int(default["age"]), key="tax_age")
    with c2:
        status = st.selectbox("Residential Status",
                              ["Resident", "NRI"],
                              key="tax_res",
                              index=0 if default.get("residential_status") == "Resident" else 1)
    with c3:
        st.write("")
        st.caption("Salaried individual assumed for standard deduction.")

    inc = default["income"]
    c1, c2, c3 = st.columns(3)
    income_vals = {}
    income_ui = {
        "salary": "Annual Salary (₹)", "bonus": "Bonus (₹)",
        "interest_income": "Interest Income (₹)", "rental_income": "Rental Income (₹)",
        "ltcg": "LTCG ₹ (equity)", "stcg": "STCG ₹ (equity)",
        "other_income": "Other Income ₹",
    }
    labels = list(income_ui.values())
    for i, k in enumerate(_income_keys()):
        col = [c1, c2, c3][i % 3]
        with col:
            income_vals[k] = st.number_input(labels[i], 0.0, 1e9,
                                             float(inc.get(k, 0) or 0),
                                             key=f"tax_inc_{k}")

    st.subheader("2️⃣ Deductions (Old Regime)")
    st.caption("Chapter VI-A deductions + exemptions. The new regime (Sec 115BAC) "
               "does NOT allow most of these.")
    ded = default["deductions"]
    c1, c2, c3 = st.columns(3)
    deduction_vals = {}
    ded_ui = {
        "sec_80c": "80C — ELSS/PPF/Life (max ₹1.5L)",
        "sec_80d_self": "80D — Health Insurance self (max ₹25k)",
        "sec_80ccd_1b": "80CCD(1B) — NPS extra (max ₹50k)",
        "sec_80g": "80G — Donations (₹)",
        "nps_employer": "NPS Employer 80CCD(2) (both regimes)",
        "home_loan_interest": "Home Loan Interest ₹ (Sec 24b)",
    }
    for i, k in enumerate(_deduction_keys()):
        col = [c1, c2, c3][i % 3]
        with col:
            if k in ded_ui:
                deduction_vals[k] = st.number_input(ded_ui[k], 0.0, 1e7,
                                                    float(ded.get(k, 0) or 0),
                                                    key=f"tax_ded_{k}")
    c1, c2 = st.columns(2)
    with c1:
        parents_senior = st.checkbox("Parents over 60? (80D parents cap ↑ ₹50k)",
                                     value=bool(ded.get("80d_parents_senior", False)),
                                     key="tax_ded_parents_senior")
        deduction_vals["80d_parents_senior"] = parents_senior
        deduction_vals["sec_80d_parents"] = st.number_input(
            "80D — Parents' Health Premium (₹)",
            0.0, 1e6, float(ded.get("sec_80d_parents", 0) or 0),
            key="tax_ded_80d_parents")

    st.subheader("3️⃣ HRA Exemption (Old Regime only)")
    c1, c2, c3 = st.columns(3)
    hra = ded
    with c1:
        hra_basic = st.number_input("Basic Salary / year (₹)", 0.0, 1e8,
                                    float(hra.get("hra_basic_salary", 0) or 0),
                                    key="tax_hra_basic")
    with c2:
        hra_recv = st.number_input("HRA received / year (₹)", 0.0, 1e8,
                                   float(hra.get("hra_received", 0) or 0),
                                   key="tax_hra_recv")
    with c3:
        rent = st.number_input("Annual Rent Paid (₹)", 0.0, 1e8,
                               float(hra.get("hra_rent_paid", 0) or 0),
                               key="tax_hra_rent")
    metro = st.checkbox("Metro city (Delhi/Mumbai/Chennai/Kolkata)", key="tax_hra_metro",
                        value=bool(hra.get("hra_is_metro", False)))

    st.write("---")
    compute_clicked = st.button("🧮 Compute & Compare Regimes",
                                type="primary", use_container_width=True,
                                key="tax_compute")

    if compute_clicked:
        inputs = {
            "age": int(age),
            "financial_year": fy,
            "residential_status": status,
            "income": {k: float(v or 0) for k, v in income_vals.items()},
            "deductions": {
                "sec_80c": float(deduction_vals["sec_80c"] or 0),
                "sec_80d_self": float(deduction_vals["sec_80d_self"] or 0),
                "sec_80d_parents": float(deduction_vals["sec_80d_parents"] or 0),
                "80d_parents_senior": bool(parents_senior),
                "sec_80ccd_1b": float(deduction_vals["sec_80ccd_1b"] or 0),
                "sec_80g": float(deduction_vals["sec_80g"] or 0),
                "nps_employer": float(deduction_vals["nps_employer"] or 0),
                "home_loan_interest": float(deduction_vals["home_loan_interest"] or 0),
                "hra_basic_salary": float(hra_basic or 0),
                "hra_received": float(hra_recv or 0),
                "hra_rent_paid": float(rent or 0),
                "hra_is_metro": bool(metro),
            },
        }
        try:
            result = tax_engine.compute_tax(inputs)
            st.session_state.tax_result = result
            st.session_state.tax_inputs_saved = inputs
        except Exception as e:
            st.error(f"Computation failed: {e}")

    if "tax_result" in st.session_state:
        _render_result(st.session_state.tax_result, svc)


def _fmt(v: float) -> str:
    return f"₹{v:,.0f}"


def _render_result(result: dict, svc):
    st.write("---")
    st.subheader("📊 Old vs New Regime — Tax Comparison")

    old, new = result["regimes"]["old"], result["regimes"]["new"]
    rows = {
        "Gross Income": [old["gross_income"], new["gross_income"]],
        "Standard Deduction": [-old["standard_deduction"], -new["standard_deduction"]],
        "Net Rental Income": [old["net_rental_income"], new["net_rental_income"]],
        "Total Deductions": [-old["total_deductions"], -new["total_deductions"]],
        "Taxable Income": [old["taxable_income"], new["taxable_income"]],
        "Tax (before rebate)": [old["tax_before_rebate"], new["tax_before_rebate"]],
        "87A Rebate": [-old["rebate_87a"], -new["rebate_87a"]],
        "Capital Gains Tax": [old["capital_gains"]["total"], new["capital_gains"]["total"]],
        "Cess (4%)": [old["cess"], new["cess"]],
        "**Final Tax**": [old["total_tax"], new["total_tax"]],
    }
    df = pd.DataFrame(rows).T.reset_index()
    df.columns = ["Line item", "Old Regime (₹)", "New Regime (₹)"]
    st.dataframe(df, use_container_width=True, hide_index=True)

    rec = result["recommended_regime"]
    rec_name = "OLD" if rec == "old" else "NEW"
    msg = (f"✅ **Recommended regime: {rec_name}** — saves "
           f"**{_fmt(result['potential_saving'])}** vs the other regime.")
    render_alert_banner(msg, "success")
    with st.expander(f"📑 Full breakdown — {rec_name} regime"):
        regime = result["regimes"][rec]
        cols = st.columns(3)
        cols[0].metric("Taxable Income", _fmt(regime["taxable_income"]))
        cols[1].metric("Tax", _fmt(regime["total_tax"] - regime["cess"]))
        cols[2].metric("Effective Rate", f"{result['effective_tax_rate']:.1f}%")
        st.markdown("##### Deduction detail")
        for label, amount in regime["deductions"].items():
            if amount > 0:
                st.markdown(f"- **{label}**: {_fmt(amount)}")

    with st.expander("💡 Deterministic tax-saving opportunities"):
        if result["tax_saving_opportunities"]:
            for opp in result["tax_saving_opportunities"]:
                st.markdown(f"- {opp}")
        else:
            st.success("No obvious gaps — you look tax-optimised.")

    if saved_inputs := st.session_state.get("tax_inputs_saved"):
        c1, c2 = st.columns([1, 5])
        with c1:
            if st.button("💾 Save declaration", type="primary", key="tax_save"):
                ok_pr = svc.save_profile(st.session_state.user_id,
                                         result["financial_year"], saved_inputs)
                ok_calc = svc.save_calculation(st.session_state.user_id, result)
                if ok_pr and ok_calc:
                    st.success("Saved! You can reload this from the FY dropdown.")
                else:
                    st.warning("Couldn't save — is the migration SQL run in Supabase? "
                               "Tables `tax_profiles` / `tax_calculations` must exist.")
        with c2:
            st.caption("Your computation is deterministic and saved for the AI CA chatbot "
                       "so it can explain *these exact numbers*.")