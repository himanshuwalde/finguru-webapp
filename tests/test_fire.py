"""
Unit tests for engines/fire_engine.py — corpus formula, Monte Carlo, FIRE age.
Run with:  python -m pytest tests/test_fire.py -v
"""
import numpy as np
import pytest

from engines.fire_engine import (
    fire_simulation, monte_carlo_terminal, projected_fire_age, required_corpus,
)


def test_required_corpus_matches_hand_calc():
    # 30k/mo inflated 6% over 20y = 30k*1.06^20 = 96,214 ; ×12 = 1,154,571 ; /4% = 28,864,250
    target = required_corpus(monthly_expense=30_000, inflation_pct=6,
                             years_to_retirement=20, safe_withdrawal_rate_pct=4)
    assert target == pytest.approx(28_864_250, rel=0.005)


def test_higher_swr_needs_smaller_corpus():
    a = required_corpus(30_000, 6, 20, safe_withdrawal_rate_pct=4)
    b = required_corpus(30_000, 6, 20, safe_withdrawal_rate_pct=5)
    assert b < a


def test_monte_carlo_deterministic_under_fixed_seed():
    a = monte_carlo_terminal(10_000, 5_000, 15, 10, seed=99)
    b = monte_carlo_terminal(10_000, 5_000, 15, 10, seed=99)
    assert np.array_equal(a, b)


def test_fire_probability_within_bounds():
    r = fire_simulation(current_age=22, target_retirement_age=45,
                        monthly_expense=30_000, monthly_investment=50_000,
                        current_corpus=2_000_000, expected_return_pct=10,
                        inflation_pct=6, n_simulations=1500, seed=7)
    assert 0 <= r["probability_pct"] <= 100
    assert r["p5_corpus"] <= r["median_corpus"] <= r["p95_corpus"]
    assert r["n_simulations"] == 1500


def test_rich_investor_more_likely_to_fire():
    poor = fire_simulation(22, 45, 30_000, 5_000, 0, 10, 6, n_simulations=1500, seed=7)
    rich = fire_simulation(22, 45, 30_000, 80_000, 5_000_000, 10, 6, n_simulations=1500, seed=8)
    assert rich["probability_pct"] > poor["probability_pct"]


def test_projected_fire_age_higher_investment_earlier():
    base = projected_fire_age(22, 0, 10_000, 1_000_000, 10)
    fast = projected_fire_age(22, 0, 50_000, 1_000_000, 10)
    assert fast is not None and base is not None
    assert fast <= base


def test_projected_fire_age_already_there():
    assert projected_fire_age(22, 5_000_000, 0, 1_000_000, 10) == 22