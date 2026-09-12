"""
Unit tests for engines/networth_engine.py — balance-sheet aggregation.
Run with:  python -m pytest tests/test_networth.py -v
"""
from datetime import date

import pytest
from engines.networth_engine import networth_snapshot, month_key


def test_snapshot_aggregates_assets_and_liabilities():
    snap = networth_snapshot(
        liquid_assets=50_000,
        investments_by_type={"Stock": 120_000, "FD": 80_000},
        liabilities=[
            {"name": "Car Loan", "liability_type": "Car", "outstanding_amount": 40_000},
            {"name": "Credit Card", "liability_type": "Credit Card", "outstanding_amount": 10_000},
        ],
    )
    assert snap["total_assets"] == pytest.approx(250_000)
    assert snap["investments_total"] == pytest.approx(200_000)
    assert snap["total_liabilities"] == pytest.approx(50_000)
    assert snap["net_worth"] == pytest.approx(200_000)


def test_assets_breakdown_is_sorted_desc():
    snap = networth_snapshot(
        liquid_assets=1000,
        investments_by_type={"Gold": 9000, "Stock": 5000},
        liabilities=[],
    )
    amounts = [a["amount"] for a in snap["assets_breakdown"]]
    assert amounts == sorted(amounts, reverse=True)
    # bank/cash is always present
    assert any(a["name"] == "Bank & Cash" for a in snap["assets_breakdown"])


def test_zero_investment_types_are_dropped():
    snap = networth_snapshot(10_000, {"Stock": 0, "Property": 20_000}, [])
    classes = {a["name"] for a in snap["assets_breakdown"]}
    assert "Stock" not in classes
    assert "Property" in classes


def test_negative_net_worth_when_debts_exceed_assets():
    snap = networth_snapshot(
        liquid_assets=10_000,
        investments_by_type={},
        liabilities=[{"name": "Loan", "outstanding_amount": 40_000}],
    )
    assert snap["net_worth"] == pytest.approx(-30_000)


def test_none_and_garbage_values_safely_default_to_zero():
    snap = networth_snapshot(None, {"Stock": None, "FD": "oops"}, [
        {"name": "X", "outstanding_amount": None},
    ])
    assert snap["total_assets"] == pytest.approx(0)
    assert snap["total_liabilities"] == pytest.approx(0)
    assert snap["net_worth"] == pytest.approx(0)


def test_month_key_is_first_of_month():
    assert month_key(date(2026, 9, 12)) == "2026-09-01"
    assert month_key(date(2026, 1, 2)) == "2026-01-01"