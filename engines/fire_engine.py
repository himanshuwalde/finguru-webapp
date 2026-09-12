"""
FinGuru FIRE Engine
===================
Pure, deterministic-to-the-seed retirement math used to answer
"will I be financially independent, retire early, and when?"

  required_corpus = (monthly_expense inflated to retirement) × 12 / SWR

Two views are produced:
  * Deterministic projection  -> projected FIRE age (when compounding reaches the corpus)
  * Monte Carlo (vectorised numpy) -> probability of FIRE, median & p5/p95 terminal corpus

Unlike an LLM, this is 100% reproducible math: pass a fixed `seed` and the
same inputs always give the same answer (unit-testable, defensible in viva).
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

# Realistic annualised volatility of a broad equity-heavy portfolio (default).
DEFAULT_VOLATILITY_PCT = 14.0


def _years_between(current_age: float, target_age: float) -> float:
    return max(0.0, target_age - current_age)


# ------------------------------------------------------------ deterministic


def required_corpus(monthly_expense: float, inflation_pct: float,
                    years_to_retirement: float,
                    safe_withdrawal_rate_pct: float = 4.0) -> float:
    """
    The lump-sum needed at retirement such that a 4%-style withdrawal rate
    covers the (inflation-grown) annual expense forever.
    """
    future_monthly = monthly_expense * (1.0 + inflation_pct / 100.0) ** years_to_retirement
    annual_expense = future_monthly * 12.0
    return annual_expense / (safe_withdrawal_rate_pct / 100.0)


def projected_fire_age(current_age: float, current_corpus: float,
                       monthly_investment: float, target_corpus: float,
                       expected_return_pct: float) -> Optional[float]:
    """
    Earliest age (year granularity) at which deterministic compounding crosses
    the target corpus; returns None if never reached within 100 years.
    One monthly-safe approximation: corpus grows at r%, contributions monthly.
    """
    corpus = current_corpus
    if corpus >= target_corpus:
        return current_age
    r_annual = 1.0 + expected_return_pct / 100.0
    # monthly-equivalent growth each year (12 monthly contributions)
    r_month = r_annual ** (1.0 / 12.0) - 1.0
    age = current_age
    for _ in range(1000):  # 1000 months
        corpus = corpus * (1.0 + r_month) + monthly_investment
        age += 1.0 / 12.0
        if corpus >= target_corpus:
            return round(age, 1)
    return None


# ------------------------------------------------------------ Monte Carlo


def monte_carlo_terminal(current_corpus: float, monthly_investment: float,
                         years: float, expected_return_pct: float,
                         volatility_pct: float = DEFAULT_VOLATILITY_PCT,
                         n_simulations: int = 3000,
                         seed: Optional[int] = None) -> np.ndarray:
    """
    Vectorised Monte Carlo of terminal (pre-withdrawal) corpus.

    Model: monthly random returns ~ N(mu_month, sigma_month) where
      mu_month    = effective monthly return of the annual expected return
      sigma_month = annual vol / sqrt(12)   (independent log-normal-ish paths)
    Each trial compounds `current_corpus` monthly and adds `monthly_investment`.
    Returns a (n_simulations,) array of terminal corpus values.
    """
    months = max(1, int(round(years * 12)))
    r_month = (1.0 + expected_return_pct / 100.0) ** (1.0 / 12.0) - 1.0
    sigma_month = (volatility_pct / 100.0) / np.sqrt(12.0)

    rng = np.random.default_rng(seed)
    returns = rng.normal(r_month, sigma_month, size=(n_simulations, months))

    corpus = np.full(n_simulations, float(current_corpus), dtype=float)
    for t in range(months):
        corpus = corpus * (1.0 + returns[:, t]) + monthly_investment
    return corpus


def fire_simulation(current_age: float, target_retirement_age: float,
                    monthly_expense: float, monthly_investment: float,
                    current_corpus: float, expected_return_pct: float,
                    inflation_pct: float,
                    safe_withdrawal_rate_pct: float = 4.0,
                    volatility_pct: float = DEFAULT_VOLATILITY_PCT,
                    n_simulations: int = 3000,
                    seed: Optional[int] = None) -> Dict:
    """
    Full FIRE run: deterministic corpus target + Monte Carlo probability.

    `seed` makes the run reproducible for tests/demos (None = fresh randomness).
    """
    years = _years_between(current_age, target_retirement_age)
    req = required_corpus(monthly_expense, inflation_pct, years,
                          safe_withdrawal_rate_pct)

    terminal = monte_carlo_terminal(
        current_corpus, monthly_investment, years, expected_return_pct,
        volatility_pct, n_simulations, seed)

    prob = float(np.mean(terminal >= req) * 100.0)
    median = float(np.median(terminal))
    p5 = float(np.percentile(terminal, 5))
    p95 = float(np.percentile(terminal, 95))

    fire_age = projected_fire_age(current_age, current_corpus,
                                  monthly_investment, req, expected_return_pct)

    future_monthly = monthly_expense * (1.0 + inflation_pct / 100.0) ** years

    return {
        "current_age": current_age,
        "target_retirement_age": target_retirement_age,
        "years_to_retirement": years,
        "future_monthly_expense": round(future_monthly, 2),
        "annual_expense_at_retirement": round(future_monthly * 12.0, 2),
        "required_corpus": round(req, 2),
        "median_corpus": round(median, 2),
        "p5_corpus": round(p5, 2),
        "p95_corpus": round(p95, 2),
        "probability_pct": round(prob, 2),
        "projected_fire_age": fire_age,
        "on_track": median >= req,
        "shortfall_vs_median": round(max(0.0, req - median), 2),
        "n_simulations": n_simulations,
        "seeded": seed is not None,
    }


def default_profile() -> Dict:
    return {
        "current_age": 22, "target_retirement_age": 45,
        "monthly_expense": 30000, "monthly_investment": 20000,
        "current_corpus": 0, "expected_return_pct": 10,
        "inflation_pct": 6, "safe_withdrawal_rate_pct": 4,
    }