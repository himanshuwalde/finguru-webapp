"""
Unit tests for engines/portfolio_engine.py — returns, allocation, health, FD.
Run with:  python -m pytest tests/test_portfolio.py -v
"""
from datetime import date, timedelta

import pytest
from engines.portfolio_engine import (
    portfolio_summary, portfolio_health, resolve_holdings, fd_current_value,
)


A_YEAR_AGO = date.today() - timedelta(days=365)


def test_summary_returns_and_allocation():
    invs = [
        {"asset_type": "Stock", "name": "TCS", "quantity": 10,
         "buy_price": 100, "current_price": 130, "purchased_on": A_YEAR_AGO},
        {"asset_type": "FD", "name": "HDFC FD", "principal": 1000,
         "interest_rate": 10, "start_date": A_YEAR_AGO},
    ]
    s = portfolio_summary(invs, as_of=date.today())
    assert s["total_invested"] == pytest.approx(2000.0)
    assert s["total_current"] == pytest.approx(2400.0, rel=0.02)  # 1300 + ~1100
    assert s["absolute_return"] == pytest.approx(400.0, rel=0.1)
    assert s["return_pct"] == pytest.approx(20.0, rel=0.1)
    classes = {a["asset_type"]: a["pct"] for a in s["allocation"]}
    assert sum(classes.values()) == pytest.approx(100.0, abs=0.5)
    assert classes["Stock"] > classes["FD"]


def test_fd_current_value_approximation():
    principal, rate = 1000.0, 10.0
    v = fd_current_value(principal, rate, A_YEAR_AGO, date.today())
    assert v == pytest.approx(1100.0, rel=0.02)


def test_resolve_holdings_derives_amounts():
    row = {"asset_type": "Mutual Fund", "name": "FlexiCap",
           "units": 100, "purchase_nav": 50, "current_nav": 60}
    h = resolve_holdings([row])
    assert h[0]["invested_amount"] == pytest.approx(5000.0)
    assert h[0]["current_value"] == pytest.approx(6000.0)


def test_health_scores_diversified_higher_than_concentrated():
    concentrated = [{"asset_type": "Stock", "name": "Only", "quantity": 1,
                     "buy_price": 100, "current_price": 200}]
    diversified = [
        {"asset_type": "Stock", "name": "A", "quantity": 1,
         "buy_price": 100, "current_price": 200},
        {"asset_type": "FD", "name": "B", "principal": 1000,
         "interest_rate": 7, "start_date": A_YEAR_AGO},
        {"asset_type": "Gold", "name": "C", "invested_amount": 2000,
         "current_value": 2100},
    ]
    s_conc, _ = portfolio_health(concentrated, "Moderate")
    s_div, insights = portfolio_health(diversified, "Moderate")
    assert s_div > s_conc
    assert insights  # non-empty insight list


def test_health_empty_portfolio():
    score, insights = portfolio_health([], "Moderate")
    assert score == 0
    assert insights