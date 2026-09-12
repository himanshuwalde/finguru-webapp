"""
Unit tests for engines/tax_engine.py — deterministic known-value cases.
Run with:  python -m pytest tests/test_tax.py -v
"""
import pytest
from engines.tax_engine import (
    compute_tax, compute_hra_exemption, compute_net_rental,
    compute_capital_gains_tax, default_inputs, load_rules,
)


def _base() -> dict:
    d = default_inputs()
    d["age"] = 30
    return d


def test_new_regime_below_rebate_threshold_is_zero():
    """Salaried ₹6L, no deductions: new regime (taxable ₹5.25L ≤ ₹12L) → ₹0 tax."""
    d = _base()
    d["income"]["salary"] = 600000
    r = compute_tax(d)
    assert r["regimes"]["new"]["total_tax"] == pytest.approx(0.0, abs=0.01)
    # Old regime: taxable ₹5.5L → ₹22,500 + 4% cess = ₹23,400
    assert r["regimes"]["old"]["total_tax"] == pytest.approx(23400.0, abs=0.01)
    assert r["recommended_regime"] == "new"
    assert r["potential_saving"] == pytest.approx(23400.0, abs=0.01)


def test_old_regime_slab_boundary():
    """Taxable ₹5.5L under old regime → 2.5-5L @5% + 5-5.5L @20% = ₹22,500."""
    d = _base()
    d["income"]["salary"] = 600000
    old = compute_tax(d)["regimes"]["old"]
    assert old["tax_before_rebate"] == pytest.approx(22500.0, abs=0.01)
    assert old["rebate_87a"] == pytest.approx(0.0)  # income above ₹5L rebate cap


def test_hra_exemption_formula():
    """HRA = min(actual, 50% metro basic, rent − 10% basic)."""
    d = _base()
    d["deductions"].update(hra_basic_salary=800000, hra_received=300000,
                           hra_rent_paid=400000, hra_is_metro=True)
    rules = load_rules("2026-27")
    ex = compute_hra_exemption(800000, 300000, 400000, True, rules)
    # min(3L, 4L, 3.2L)
    assert ex == pytest.approx(300000.0, abs=0.01)
    # fully connected through the engine
    old = compute_tax(d)["regimes"]["old"]
    assert old["deductions"]["HRA Exemption"] == pytest.approx(300000.0, abs=0.01)


def test_home_loan_interest_24b_cap():
    """Self-occupied 24(b) capped at ₹2,00,000 even if ₹5L paid."""
    d = _base()
    d["income"]["salary"] = 500000
    d["deductions"]["home_loan_interest"] = 500000
    old = compute_tax(d)["regimes"]["old"]
    assert old["deductions"]["24(b) Home Loan Interest"] == pytest.approx(200000.0)


def test_80c_cap():
    """80C capped at ₹1.5L even if ₹2L invested."""
    d = _base()
    d["income"]["salary"] = 500000
    d["deductions"]["sec_80c"] = 200000
    old = compute_tax(d)["regimes"]["old"]
    assert old["deductions"]["80C"] == pytest.approx(150000.0)


def test_capital_gains_tax():
    """LTCG ₹2L → (2L − 1.25L threshold) × 12.5% = ₹9,375. Regime-independent."""
    out = compute_capital_gains_tax(200000, 0, {
        "capital_gains": {"ltcg_equity_threshold": 125000,
                          "ltcg_equity_rate": 0.125, "stcg_equity_rate": 0.20}
    })
    assert out["total"] == pytest.approx(9375.0, abs=0.01)


def test_recommended_regime_picks_cheaper():
    d = _base()
    d["income"]["salary"] = 1200000
    d["deductions"].update(sec_80c=100000, sec_80d_self=25000,
                           home_loan_interest=120000)
    r = compute_tax(d)
    best = min(r["regimes"]["old"]["total_tax"],
               r["regimes"]["new"]["total_tax"])
    assert r["regimes"][r["recommended_regime"]]["total_tax"] == pytest.approx(best)
    assert r["potential_saving"] == pytest.approx(
        abs(r["regimes"]["old"]["total_tax"] - r["regimes"]["new"]["total_tax"]))
    # 80C used ≤ cap so the cap-aware suggestion list is generated.
    assert any("80C" in s for s in r["tax_saving_opportunities"])


def test_net_rental_self_occupied_vs_let_out():
    # Self-occupied: no rental income head → net rental 0
    assert compute_net_rental(0, 120000) == 0.0
    # Let-out: 30% std deduction then interest deducted (floored at 0)
    assert compute_net_rental(400000, 100000) == pytest.approx(180000.0)
    assert compute_net_rental(100000, 200000) == 0.0


def test_opportunities_when_old_regime_better():
    """
    Let-out property with heavy home-loan interest makes OLD regime cheaper:
    old deductible-interest wipes the rental head, new regime taxes rent gross.
    Old taxable ≈ ₹30L  vs new taxable ≈ ₹39.75L.
    """
    d = _base()
    d["income"]["salary"] = 3000000
    d["income"]["rental_income"] = 1500000
    d["deductions"]["home_loan_interest"] = 1000000
    r = compute_tax(d)
    old_tax = r["regimes"]["old"]["total_tax"]
    new_tax = r["regimes"]["new"]["total_tax"]
    assert old_tax < new_tax
    assert r["recommended_regime"] == "old"
    assert r["potential_saving"] == pytest.approx(new_tax - old_tax)