"""
Unit tests for engines/portfolio_engine.py::xirr.
Run with:  python -m pytest tests/test_xirr.py -v
"""
from datetime import date

import pytest
from engines.portfolio_engine import xirr


def test_xirr_single_year():
    """₹1,000 invested, ₹1,100 after exactly one year → 10%."""
    irr = xirr([-1000.0, 1100.0], [date(2024, 1, 1), date(2025, 1, 1)])
    assert irr is not None
    assert irr == pytest.approx(0.10, abs=0.005)


def test_xirr_multi_year_cashflow():
    """-10k now, +5k @1y, +5k @2y, +3k @3y → IRR in (14%, 18%)."""
    ds = [date(2024, 1, 1), date(2025, 1, 1), date(2026, 1, 1), date(2027, 1, 1)]
    irr = xirr([-10000.0, 5000.0, 5000.0, 3000.0], ds)
    assert irr is not None
    assert 0.14 < irr < 0.18


def test_xirr_no_root_returns_none():
    """All outflows (no sign change) → None."""
    ds = [date(2024, 1, 1), date(2025, 1, 1)]
    assert xirr([-1000.0, -500.0], ds) is None


def test_xirr_zero_amount_fails_safely():
    assert xirr([], []) is None