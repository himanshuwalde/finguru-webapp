"""
Unit tests for engines/health_score.py — the weighted Financial Health Score.
Run with:  python -m pytest tests/test_health.py -v
"""
import pytest

from engines.health_score import compute_health_score


def _ctx(**kw):
    base = dict(
        monthly_income=100_000, monthly_expense=40_000,
        total_assets=5_000_000, total_liabilities=0,
        invested_current=2_000_000, portfolio_health_score=80,
        effective_tax_rate=5.0, has_tax_data=True,
        potential_tax_saving=0, recommended_regime="new",
        fire_probability_pct=75, has_fire_data=True,
    )
    base.update(kw)
    return base


def test_healthy_profile_scores_high():
    hs = compute_health_score(_ctx())
    assert hs["overall"] >= 70
    assert hs["verb"] in ("Good", "Excellent")


def test_high_savings_pillar_is_full():
    hs = compute_health_score(_ctx())  # savings rate 60% >> 30% cap
    savings = next(c for c in hs["components"] if c["key"] == "savings")
    assert savings["score"] == 100


def test_spending_within_income():
    hs = compute_health_score(_ctx(monthly_expense=50_000))
    spending = next(c for c in hs["components"] if c["key"] == "spending")
    assert spending["score"] == 100  # exactly 50% of income
    hs2 = compute_health_score(_ctx(monthly_expense=80_000))
    spending2 = next(c for c in hs2["components"] if c["key"] == "spending")
    assert spending2["score"] == 40  # (80/100 - 0.5)*200 = 60 → 100-60


def test_debt_crush_lowers_score():
    hs = compute_health_score(_ctx(total_liabilities=0))
    hs2 = compute_health_score(_ctx(total_liabilities=4_000_000))  # 80% of assets
    assert hs2["overall"] < hs["overall"]
    assert any(f["severity"] == "warning" for f in hs2["flags"])


def test_no_investments_triggers_warning_and_zero_pillar():
    hs = compute_health_score(_ctx(invested_current=0, portfolio_health_score=0))
    investment = next(c for c in hs["components"] if c["key"] == "investment")
    assert investment["score"] == 0
    assert any("No investments" in f["message"] for f in hs["flags"])
    assert hs["missing_data"] is True


def test_no_tax_data_drops_pillar():
    hs = compute_health_score(_ctx(has_tax_data=False))
    tax = next(c for c in hs["components"] if c["key"] == "tax")
    assert tax["score"] == 0
    assert hs["missing_data"] is True


def test_low_fire_probability_warned():
    hs = compute_health_score(_ctx(fire_probability_pct=20))
    assert any("chance of retiring" in f["message"] for f in hs["flags"])


def test_weights_sum_to_one():
    hs = compute_health_score(_ctx())
    total_w = sum(c["weight"] for c in hs["components"])
    assert total_w == pytest.approx(1.0)


def test_overall_is_weighted_average():
    hs = compute_health_score(_ctx())
    expected = sum(c["weight"] * c["score"] for c in hs["components"])
    assert hs["overall"] == round(expected)