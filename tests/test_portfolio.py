"""
Unit tests for engines/portfolio_engine.py — returns, allocation, health, FD.
Run with:  python -m pytest tests/test_portfolio.py -v
"""
from datetime import date, timedelta

import pytest
from engines.portfolio_engine import (
    portfolio_summary, portfolio_health, resolve_holdings, fd_current_value,
    rebalancing_plan,
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


# ------------------------------------------------------------ rebalancing


def _r(fixture, risk="Moderate"):
    """Small helper so tests read like a list of raw DB rows."""
    return rebalancing_plan(fixture, risk)


def test_rebalance_balanced_portfolio():
    invs = [
        {"asset_type": "Stock", "name": "Reliance", "quantity": 10,
         "buy_price": 100, "current_price": 200},              # value 2000, +100%
        {"asset_type": "FD", "name": "SBI FD", "principal": 2000,
         "interest_rate": 0, "start_date": date.today()},       # value 2000
    ]
    plan = _r(invs)  # Moderate → 50% equity, exactly matched
    assert plan["plan_status"] == "balanced"
    assert not plan["trades"] and not plan["adds"]


def test_rebalance_over_equity_trim_stock_add_stable():
    invs = [
        {"asset_type": "Stock", "name": "Winner", "quantity": 20,
         "buy_price": 100, "current_price": 200},               # value 4000
        {"asset_type": "Stock", "name": "Loser", "quantity": 20,
         "buy_price": 100, "current_price": 150},               # value 3000
        {"asset_type": "FD", "name": "SBI FD", "principal": 1000,
         "interest_rate": 0, "start_date": date.today()},       # value 1000
    ]
    plan = _r(invs)
    assert plan["plan_status"] == "rebalance"
    assert plan["equity_delta"] < 0                      # over-allocated to equity
    assert plan["trades"]                                # funded moves exist
    for t in plan["trades"]:
        assert t["from"]["asset_type"] in ("Stock", "Mutual Fund")   # trims equity
        assert t["to"]["asset_type"] == "FD"                        # funds stable
        assert t["amount"] >= 1000
    trimmed = sum(t["amount"] for t in plan["trades"])
    assert trimmed == pytest.approx(abs(plan["equity_delta"]), rel=0.15)


def test_rebalance_under_equity_add_equity():
    invs = [
        {"asset_type": "Stock", "name": "Nifty", "quantity": 10,
         "buy_price": 100, "current_price": 200},               # value 2000
        {"asset_type": "FD", "name": "SBI FD", "principal": 5000,
         "interest_rate": 0, "start_date": date.today()},       # value 5000
    ]
    plan = _r(invs)
    assert plan["plan_status"] == "rebalance"
    assert plan["equity_delta"] > 0                      # under-allocated to equity
    assert plan["trades"]
    for t in plan["trades"]:
        assert t["from"]["asset_type"] == "FD"                  # trims stable
        assert t["to"]["asset_type"] in ("Stock", "Mutual Fund")  # funds equity
        assert t["amount"] >= 1000


def test_rebalance_tilts_toward_winners():
    invs = [
        {"asset_type": "Stock", "name": "Win", "quantity": 100,
         "buy_price": 100, "current_price": 150},               # +50%, value 15000
        {"asset_type": "Stock", "name": "Lag", "quantity": 100,
         "buy_price": 100, "current_price": 80},                # -20%, value 8000
        {"asset_type": "FD", "name": "FD", "principal": 30000,
         "interest_rate": 0, "start_date": date.today()},       # value 30000
    ]
    plan = _r(invs)
    adds = {t["to"]["name"]: t["amount"] for t in plan["trades"]}
    assert adds["Win"] > adds["Lag"]    # the +50% holding gets a strictly larger add


def test_rebalance_single_holding_skips():
    invs = [{"asset_type": "Stock", "name": "Only", "quantity": 10,
             "buy_price": 100, "current_price": 200}]
    plan = _r(invs)
    assert plan["plan_status"] == "skip"
    assert not plan["trades"]


def test_rebalance_single_class_suggests_diversify():
    invs = [
        {"asset_type": "Stock", "name": "S1", "quantity": 10,
         "buy_price": 100, "current_price": 200},
        {"asset_type": "Mutual Fund", "name": "S2", "units": 100,
         "purchase_nav": 50, "current_nav": 60},
    ]
    plan = _r(invs)
    assert plan["plan_status"] == "diversify"    # all-equity vs a 50% stable target
    assert plan["warnings"]


def test_rebalance_closed_form_net_zero():
    invs = [
        {"asset_type": "Stock", "name": "A", "quantity": 25,
         "buy_price": 100, "current_price": 180},               # +80%, value 4500
        {"asset_type": "Mutual Fund", "name": "B", "units": 500,
         "purchase_nav": 40, "current_nav": 36},                # -10%, value 18000
        {"asset_type": "FD", "name": "C", "principal": 20000,
         "interest_rate": 0, "start_date": date.today()},       # value 20000
        {"asset_type": "Gold", "name": "D", "invested_amount": 10000,
         "current_value": 10500},                               # +5%, value 10500
    ]
    plan = _r(invs)
    assert plan["plan_status"] == "rebalance"
    # Rebalancing is a pure transfer: every trade moves the same ₹ out of its
    # source and into its target, so applying them leaves total value unchanged.
    values = {"A": 4500.0, "B": 18000.0, "C": 20000.0, "D": 10500.0}
    for t in plan["trades"]:
        values[t["from"]["name"]] -= t["amount"]
        values[t["to"]["name"]] += t["amount"]
    assert sum(values.values()) == pytest.approx(53000.0, abs=1.0)
    # No holding is suggested to go below zero.
    assert all(v >= 0 for v in values.values())