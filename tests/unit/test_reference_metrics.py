"""Hand-computed checks and invariants for the reference implementations."""

import math
from datetime import date, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fundlens.metrics.reference import (
    annualised_volatility,
    cagr,
    max_drawdown,
    percent_rank,
    xirr,
)

nav_lists = st.lists(st.floats(min_value=0.01, max_value=1e6, allow_nan=False), min_size=3, max_size=60)


def test_cagr_hand_computed_two_years_ten_percent():
    # 100 -> 121 over exactly 730 days: 1.21 ** 0.5 - 1 = 0.10
    assert cagr(100, date(2021, 1, 1), 121, date(2023, 1, 1)) == pytest.approx(0.10, abs=1e-12)


def test_cagr_hand_computed_one_year_doubling():
    assert cagr(50, date(2021, 1, 1), 100, date(2022, 1, 1)) == pytest.approx(1.0, abs=1e-12)


def test_cagr_rejects_bad_inputs():
    assert cagr(0, date(2021, 1, 1), 1, date(2022, 1, 1)) is None
    assert cagr(1, date(2021, 1, 1), -1, date(2022, 1, 1)) is None
    assert cagr(1, date(2022, 1, 1), 1, date(2021, 1, 1)) is None


def test_xirr_matches_microsoft_documented_example():
    # Example from Microsoft's XIRR documentation; published answer 0.373362535.
    dates = [date(2008, 1, 1), date(2008, 3, 1), date(2008, 10, 30), date(2009, 2, 15), date(2009, 4, 1)]
    flows = [-10000, 2750, 4250, 3250, 2750]
    assert xirr(dates, flows) == pytest.approx(0.373362535, abs=1e-8)


def test_xirr_two_flows_equals_cagr_no_flow_agreement():
    d0, d1 = date(2020, 3, 1), date(2023, 9, 17)
    assert xirr([d0, d1], [-1000.0, 1731.0]) == pytest.approx(cagr(1000, d0, 1731, d1), abs=1e-10)


def test_xirr_none_without_sign_change():
    assert xirr([date(2020, 1, 1), date(2021, 1, 1)], [100.0, 200.0]) is None


def test_max_drawdown_hand_computed():
    # peak 120, trough 60 -> -50%; later recovery to 130 does not erase the drawdown
    assert max_drawdown([100, 120, 90, 110, 60, 130]) == pytest.approx(-0.5)


def test_max_drawdown_monotonic_rise_is_zero():
    assert max_drawdown([1, 2, 3, 4]) == 0.0


def test_volatility_hand_computed():
    # log returns of [100, 110, 99]: ln(1.1)=0.0953102, ln(0.9)=-0.1053605
    r1, r2 = math.log(1.1), math.log(0.9)
    mean = (r1 + r2) / 2
    sample_sd = math.sqrt(((r1 - mean) ** 2 + (r2 - mean) ** 2) / 1)
    assert annualised_volatility([100, 110, 99]) == pytest.approx(sample_sd * math.sqrt(252))


def test_percent_rank_matches_sql_definition():
    assert percent_rank([10, 30, 20, 40]) == [0.0, 2 / 3, 1 / 3, 1.0]
    assert percent_rank([5, 5, 9]) == [0.0, 0.0, 1.0]


# ---- invariants -------------------------------------------------------------------------


@given(st.floats(min_value=0.01, max_value=1e6, allow_nan=False), st.integers(min_value=3, max_value=100))
def test_constant_nav_has_zero_volatility_and_drawdown(level, n):
    assert annualised_volatility([level] * n) == 0.0
    assert max_drawdown([level] * n) == 0.0


@given(nav_lists)
def test_max_drawdown_never_positive_and_above_minus_one(navs):
    dd = max_drawdown(navs)
    assert -1.0 < dd <= 0.0


@settings(max_examples=60)
@given(nav_lists, st.floats(min_value=0.001, max_value=1e4))
def test_scaling_navs_does_not_change_returns_vol_or_drawdown(navs, k):
    scaled = [v * k for v in navs]
    assert max_drawdown(scaled) == pytest.approx(max_drawdown(navs), rel=1e-9, abs=1e-12)
    assert annualised_volatility(scaled) == pytest.approx(annualised_volatility(navs), rel=1e-6, abs=1e-9)
    d0, d1 = date(2020, 1, 1), date(2022, 1, 1)
    assert cagr(navs[0] * k, d0, navs[-1] * k, d1) == pytest.approx(cagr(navs[0], d0, navs[-1], d1), rel=1e-9)


@given(
    st.floats(min_value=1, max_value=1e5),
    st.floats(min_value=0.5, max_value=3.0),
    st.integers(min_value=180, max_value=4000),
)
def test_no_flow_xirr_equals_price_return_cagr(v0, growth, days):
    d0 = date(2015, 6, 1)
    d1 = d0 + timedelta(days=days)
    expected = cagr(v0, d0, v0 * growth, d1)
    got = xirr([d0, d1], [-v0, v0 * growth])
    assert got == pytest.approx(expected, rel=1e-6, abs=1e-9)
