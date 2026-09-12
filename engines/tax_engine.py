"""
FinGuru Income Tax Engine
=========================
Deterministic, regulation-driven tax computation for the OLD and NEW regimes.

Design rules (see plan):
  * Engines are PURE — no Supabase, no Streamlit. They take plain dicts and
    return plain dicts, so they are fully unit-testable.
  * All slab/limit/rebase values live in `data/tax_rules/<ay>.json`, never
    hard-coded as `if income > X`. Update values in the JSON — not here.
  * The returned breakdown dict is the SINGLE source of truth that (a) feeds
    the UI and (b) is serialized into the AI CA chatbot prompt as grounding.

The LLM never computes tax; it only explains what this engine computes.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

# ---------------------------------------------------------------- loading


@lru_cache(maxsize=8)
def load_rules(financial_year: str = "2026-27") -> Dict:
    """Load tax rules for an assessment year from data/tax_rules/<ay>.json."""
    fname = f"ay_{financial_year.replace('-', '_')}.json"
    path = Path(__file__).resolve().parent.parent / "data" / "tax_rules" / fname
    if not path.exists():
        raise FileNotFoundError(
            f"No tax rules file for {financial_year}. Expected {path}"
        )
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def list_available_assessment_years() -> list:
    """Assessment years with a rules file, e.g. ['2026-27']."""
    folder = Path(__file__).resolve().parent.parent / "data" / "tax_rules"
    out = []
    for p in sorted(folder.glob("ay_*.json")):
        name = p.stem.replace("ay_", "").replace("_", "-")
        if name and name != "template":
            out.append(name)
    return out


# ------------------------------------------------------------- small helpers


def _clamp(value: float, lower: float, upper: Optional[float] = None) -> float:
    value = max(value, lower)
    if upper is not None:
        value = min(value, upper)
    return value


def tax_on_slabs(taxable_income: float, slabs: list) -> float:
    """Apply a slab table [{from,to,rate}] and sum the tax."""
    tax = 0.0
    for band in slabs:
        lo, hi, rate = band["from"], band["to"], band["rate"]
        if taxable_income <= lo:
            continue
        top = hi if hi is not None else taxable_income
        tax += (min(taxable_income, top) - lo) * rate
    return tax


def apply_rebate(tax_before_rebate: float, taxable_income: float, rebate_cfg: Dict) -> float:
    """Section 87A: full tax rebate when income ≤ threshold (capped)."""
    if taxable_income <= rebate_cfg["threshold"]:
        cap = rebate_cfg["max_amount"]
        return min(tax_before_rebate, cap)
    return 0.0


def compute_hra_exemption(basic_salary: float, hra_received: float,
                          rent_paid: float, is_metro: bool, rules: Dict) -> float:
    """
    HRA exemption = min of:
      1. actual HRA received
      2. 50% (metro) / 40% (non-metro) of Basic Salary
      3. rent paid - 10% of Basic Salary
    Applies only to the amount of rent exceeding 10% of basic (i.e. formula 3).
    """
    if rent_paid <= 0:
        return 0.0
    cfg = rules["old_regime"]["hra"]
    frac = cfg["metro_fraction"] if is_metro else cfg["non_metro_fraction"]
    one = hra_received
    two = frac * basic_salary
    three = rent_paid - cfg["rent_excess_over_basic"] * basic_salary
    return max(0.0, min(one, two, three))


def compute_net_rental(gross_rental: float, home_loan_interest: float) -> float:
    """
    Rental income (let-out property): 30% standard deduction on gross rent,
    then deduct full home-loan interest. Net is floored at 0 for v1 (set-off
    of losses from other heads is out of scope and documented as an assumption).
    """
    if gross_rental <= 0:
        return 0.0
    net = gross_rental * 0.70 - home_loan_interest
    return max(0.0, net)


def compute_capital_gains_tax(ltcg: float, stcg: float, rules: Dict) -> Dict:
    """Regime-independent capital-gains tax on equity (FY 2025-26 figures)."""
    cfg = rules["capital_gains"]
    taxable_ltcg = max(0.0, ltcg - cfg["ltcg_equity_threshold"])
    ltcg_tax = taxable_ltcg * cfg["ltcg_equity_rate"]
    stcg_tax = max(0.0, stcg) * cfg["stcg_equity_rate"]
    return {
        "gross_ltcg": ltcg,
        "ltcg_exempted": min(ltcg, cfg["ltcg_equity_threshold"]),
        "taxable_ltcg": taxable_ltcg,
        "ltcg_tax": ltcg_tax,
        "stcg_tax": stcg_tax,
        "total": ltcg_tax + stcg_tax,
    }


# --------------------------------------------------------------- old regime


def _age_group(age: int) -> str:
    if age >= 80:
        return "super_senior"
    if age >= 60:
        return "senior"
    return "general"


def compute_old_regime(inputs: Dict, rules: Dict) -> Dict:
    """Compute tax under the old regime with its full deduction list."""
    inc = inputs["income"]
    ded = inputs["deductions"]
    age_group = _age_group(inputs["age"])
    slabs = rules["old_regime"]["slabs_by_age"][age_group]
    caps = rules["old_regime"]["deduction_caps"]

    # --- gross income and standard deduction ------------------------------
    gross = (inc["salary"] + inc["bonus"] + inc["interest_income"]
             + inc["other_income"])
    std_ded = rules["old_regime"]["standard_deduction_salaried"]

    # --- rental income (let-out) + self-occupied home-loan interest --------
    # Property income is handled in ONE place to avoid double-counting interest:
    #   * Let-out (rent > 0):  net rental = 70% of gross rent − FULL interest
    #     (floored at 0 — a loss set-off against salary is out of scope).
    #   * Self-occupied:       net rental = 0; 24(b) capped at ₹2,00,000.
    home_loan_interest = ded["home_loan_interest"]
    gross_rental = inc["rental_income"]
    if gross_rental > 0:
        net_rental = compute_net_rental(gross_rental, home_loan_interest)
        deduction_24b = 0.0  # already absorbed inside net_rental
    else:
        net_rental = 0.0
        deduction_24b = _clamp(home_loan_interest, 0,
                               caps["home_loan_interest_self_occupied"])

    # --- Chapter VI-A deductions (all capped) ------------------------------
    d_80c = _clamp(ded["sec_80c"], 0, caps["sec_80c"])
    d_80ccd_1b = _clamp(ded["sec_80ccd_1b"], 0, caps["sec_80ccd_1b"])
    cap80d_self = (caps["sec_80d_self_senior"] if inputs["age"] >= 60
                   else caps["sec_80d_self_under60"])
    cap80d_parents = (caps["sec_80d_parents_senior"] if ded["80d_parents_senior"]
                      else caps["sec_80d_parents_under60"])
    d_80d = _clamp(ded["sec_80d_self"], 0, cap80d_self) \
        + _clamp(ded["sec_80d_parents"], 0, cap80d_parents)
    # 80G on eligible 50%/100% donations: no cap, use amount as-is
    d_80g = max(0.0, ded["sec_80g"])

    hra = compute_hra_exemption(
        ded["hra_basic_salary"], ded["hra_received"], ded["hra_rent_paid"],
        ded["hra_is_metro"], rules,
    )

    all_deductions = {
        "80C": d_80c,
        "80CCD(1B) NPS": d_80ccd_1b,
        "80D Self+Family": d_80d,
        "80G": d_80g,
        "HRA Exemption": hra,
        "24(b) Home Loan Interest": deduction_24b,
    }
    total_deductions = sum(all_deductions.values())

    taxable = max(0.0, gross - std_ded + net_rental - total_deductions)

    # --- tax, rebate, gains, cess -----------------------------------------
    tax_before_rebate = tax_on_slabs(taxable, slabs)
    rebate = apply_rebate(tax_before_rebate, taxable,
                          rules["old_regime"]["rebate_87a"])
    gains = compute_capital_gains_tax(inc["ltcg"], inc["stcg"], rules)
    tax_after_rebate = max(0.0, tax_before_rebate - rebate) + gains["total"]
    cess = tax_after_rebate * rules["cess_rate"]

    return {
        "regime": "old",
        "gross_income": gross,
        "standard_deduction": std_ded,
        "net_rental_income": net_rental,
        "deductions": all_deductions,
        "total_deductions": total_deductions,
        "taxable_income": taxable,
        "age_group": age_group,
        "capital_gains": gains,
        "tax_before_rebate": tax_before_rebate,
        "rebate_87a": rebate,
        "tax_after_rebate": tax_after_rebate,
        "cess": cess,
        "total_tax": tax_after_rebate + cess,
    }


# --------------------------------------------------------------- new regime


def compute_new_regime(inputs: Dict, rules: Dict) -> Dict:
    """
    New regime (Sec 115BAC). Standard deduction applies; most exemptions
    (HRA, 24(b), 80C/80D) are NOT allowed. Employer NPS 80CCD(2) is in.
    """
    inc = inputs["income"]
    ded = inputs["deductions"]
    slabs = rules["new_regime"]["slabs"]

    gross = (inc["salary"] + inc["bonus"] + inc["interest_income"]
             + inc["other_income"])
    std_ded = rules["new_regime"]["standard_deduction_salaried"]

    # Gross rent enters income only for let-out property; self-occupied → 0.
    net_rental = compute_net_rental(inc["rental_income"], 0.0)

    # Only employer NPS (80CCD(2)) is deductible in the new regime.
    d_80ccd_2 = max(0.0, ded["nps_employer"])
    total_deductions = d_80ccd_2

    taxable = max(0.0, gross - std_ded + net_rental - total_deductions)

    tax_before_rebate = tax_on_slabs(taxable, slabs)
    rebate = apply_rebate(tax_before_rebate, taxable,
                          rules["new_regime"]["rebate_87a"])
    gains = compute_capital_gains_tax(inc["ltcg"], inc["stcg"], rules)
    tax_after_rebate = max(0.0, tax_before_rebate - rebate) + gains["total"]
    cess = tax_after_rebate * rules["cess_rate"]

    return {
        "regime": "new",
        "gross_income": gross,
        "standard_deduction": std_ded,
        "net_rental_income": net_rental,
        "deductions": {"80CCD(2) Employer NPS": d_80ccd_2},
        "total_deductions": total_deductions,
        "taxable_income": taxable,
        "age_group": "n/a",
        "capital_gains": gains,
        "tax_before_rebate": tax_before_rebate,
        "rebate_87a": rebate,
        "tax_after_rebate": tax_after_rebate,
        "cess": cess,
        "total_tax": tax_after_rebate + cess,
    }


# ------------------------------------------------------- comparison + deps


def default_inputs() -> Dict:
    """A clean template matching what the UI form collects."""
    return {
        "age": 30,
        "financial_year": "2026-27",
        "income": {
            "salary": 0.0, "bonus": 0.0, "interest_income": 0.0,
            "rental_income": 0.0, "ltcg": 0.0, "stcg": 0.0, "other_income": 0.0,
        },
        "deductions": {
            "sec_80c": 0.0, "sec_80d_self": 0.0, "sec_80d_parents": 0.0,
            "80d_parents_senior": False, "sec_80ccd_1b": 0.0, "sec_80g": 0.0,
            "nps_employer": 0.0, "home_loan_interest": 0.0,
            "hra_basic_salary": 0.0, "hra_received": 0.0,
            "hra_rent_paid": 0.0, "hra_is_metro": False,
        },
    }


def compute_tax(inputs: Dict) -> Dict:
    """
    Top-level entry point. Computes BOTH regimes, picks the cheaper one and
    returns a full breakdown — this exact dict feeds the UI and the chatbot.
    """
    rules = load_rules(inputs.get("financial_year", "2026-27"))
    old = compute_old_regime(inputs, rules)
    new = compute_new_regime(inputs, rules)

    recommended = "new" if new["total_tax"] <= old["total_tax"] else "old"
    saving = abs(old["total_tax"] - new["total_tax"])

    gross = old["gross_income"]
    return {
        "financial_year": inputs.get("financial_year", "2026-27"),
        "inputs": inputs,
        "regimes": {"old": old, "new": new},
        "recommended_regime": recommended,
        "potential_saving": saving,
        "effective_tax_rate": (old["total_tax"] / gross * 100) if gross else 0.0,
        "tax_saving_opportunities": _find_opportunities(old, new, inputs, rules),
    }


def _find_opportunities(old: Dict, new: Dict, inputs: Dict, rules: Dict) -> list:
    """Deterministic, evidence-based tax-saving suggestions (no AI)."""
    opp = []
    ded = inputs["deductions"]
    caps = rules["old_regime"]["deduction_caps"]

    used_80c = old["deductions"].get("80C", 0)
    remaining_80c = caps["sec_80c"] - used_80c
    if remaining_80c > 0:
        opp.append(f"Unused 80C capacity of ₹{remaining_80c:,.0f} — "
                   "consider ELSS / PPF / life insurance premium.")

    used_80d = old["deductions"].get("80D Self+Family", 0)
    self_cap = (caps["sec_80d_self_senior"] if inputs["age"] >= 60
                else caps["sec_80d_self_under60"])
    if used_80d < self_cap:
        opp.append(f"Unused 80D health-insurance room of up to "
                   f"₹{self_cap - used_80d:,.0f} for self/family premiums.")

    if ded["hra_rent_paid"] > 0 and old["deductions"].get("HRA Exemption", 0) == 0:
        opp.append("You pay rent but got no HRA exemption — switch to the new "
                   "regime or ask your employer to include HRA in your CTC.")

    if old["deductions"].get("24(b) Home Loan Interest", 0) < 200000 \
            and ded["home_loan_interest"] > 0:
        opp.append("You claimed less than the ₹2,00,000 home-loan-interest "
                   "limit — retained 24(b) makes the old regime attractive.")

    if new["total_tax"] > 0 and new["total_tax"] < old["total_tax"]:
        opp.append(f"New regime saves ₹{old['total_tax'] - new['total_tax']:,.0f} "
                   "already — no deductions to lock in.")
    return opp


# ----------------------------------------------------------- CLI sanity check
if __name__ == "__main__":
    import pprint
    sample = default_inputs()
    sample["income"] = {"salary": 1200000, "bonus": 0, "interest_income": 0,
                        "rental_income": 0, "ltcg": 50000, "stcg": 0,
                        "other_income": 0}
    sample["deductions"].update({"sec_80c": 150000, "sec_80d_self": 25000,
                                 "home_loan_interest": 120000,
                                 "hra_basic_salary": 500000, "hra_received": 150000,
                                 "hra_rent_paid": 180000, "hra_is_metro": True})
    pprint.pprint(compute_tax(sample))