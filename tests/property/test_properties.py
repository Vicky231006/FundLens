"""Hypothesis property tests: invariants that must hold for ANY input."""

from datetime import date

import numpy as np
import pandas as pd
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from fundlens.config import load_scope
from fundlens.ingestion.parser import FileStats, parse_amfi_date, parse_lines, parse_nav
from fundlens.screening.engine import ScreeningParams, apply_screen

SCOPE = load_scope()

# ---- parser ----------------------------------------------------------------------------

line_text = st.text(
    alphabet=st.characters(blacklist_characters="\r\n", blacklist_categories=("Cs",)), max_size=120
)
semi_line = st.lists(line_text.filter(lambda t: ";" not in t), min_size=1, max_size=10).map(";".join)
any_line = st.one_of(
    line_text,
    semi_line,
    st.just("Open Ended Schemes ( Equity Scheme - Mid Cap Fund )"),
    st.just("Open Ended Schemes ( Debt Scheme - Liquid Fund )"),
    st.just(""),
    st.builds(
        lambda c, n, p, o, v, d: f"{c};{n};{p};{o};;;{v};{d}",
        st.integers(100000, 999999),
        st.text(alphabet="ABCabc -", min_size=1, max_size=20),
        st.sampled_from(["Direct Plan", "Regular Plan", ""]),
        st.sampled_from(["GROWTH", "IDCW", ""]),
        st.one_of(st.floats(0.01, 5000).map(lambda f: f"{f:.4f}"), st.just("N.A."), st.just("")),
        st.one_of(
            st.dates(date(2005, 1, 1), date(2041, 6, 1)).map(lambda d: d.strftime("%d-%b-%Y")),
            st.just("32-Jan-2024"),
        ),
    ),
)


@settings(max_examples=300, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(any_line, max_size=60))
def test_parser_never_raises_and_accounts_for_every_data_line(lines):
    stats = FileStats()
    rows = list(
        parse_lines([*lines, "Open Ended Schemes ( Equity Scheme - Mid Cap Fund )", *lines], SCOPE, stats)
    )
    assert stats.lines_in_scope + stats.lines_out_of_scope == stats.data_lines_total
    assert len(rows) == stats.lines_in_scope
    assert stats.lines_malformed <= stats.lines_in_scope
    for r in rows:
        assert r.parse_status in {"VALID", "REJECTED", "DUPLICATE"}
        if r.parse_status == "VALID":
            assert r.nav is not None and r.nav_date is not None and r.scheme_code
        else:
            assert r.reject_reason


@given(st.text(max_size=30))
def test_date_and_nav_parsers_total_functions(text):
    d = parse_amfi_date(text)
    assert d is None or isinstance(d, date)
    n = parse_nav(text)
    assert n is None or n.is_finite()


@given(st.dates(date(2006, 1, 1), date(2040, 12, 31)))
def test_date_roundtrip(d):
    assert parse_amfi_date(d.strftime("%d-%b-%Y")) == d


# ---- screening monotonicity --------------------------------------------------------------


@st.composite
def metric_frames(draw):
    n_funds = draw(st.integers(2, 6))
    n_months = draw(st.integers(3, 10))
    months = pd.date_range("2020-01-31", periods=n_months, freq="ME")
    rng = np.random.default_rng(draw(st.integers(0, 10_000)))
    rows = []
    for f in range(n_funds):
        for m in months:
            rows.append(
                {
                    "scheme_id": f, "me_date": m, "category": "Mid Cap", "plan_type": "DIRECT",
                    "nav": 100.0, "cagr_1y": 0.0, "cagr_3y": 0.0, "cagr_5y": None,
                    "volatility_1y": 0.2, "sip_xirr_3y": None, "pct_rank_cagr_1y": 0.5,
                    "pct_rank_cagr_3y": float(rng.uniform()), "peers_1y": 10, "peers_3y": 10,
                    "peers_dd": 10, "max_drawdown_3y": -float(rng.uniform(0.05, 0.5)),
                    "median_max_drawdown_3y": -0.25, "median_cagr_3y": 0.0,
                }
            )  # fmt: skip
    return pd.DataFrame(rows)


def n_flags(df, **kw):
    return int(apply_screen(df, ScreeningParams(min_peers=5, **kw))["flagged"].sum())


@settings(max_examples=60, deadline=None)
@given(metric_frames(), st.integers(1, 5))
def test_larger_k_never_creates_flags(df, k):
    assert n_flags(df, k=k + 1) <= n_flags(df, k=k)


@settings(max_examples=60, deadline=None)
@given(metric_frames(), st.floats(0.05, 0.6))
def test_looser_rank_threshold_never_removes_flags(df, thr):
    assert n_flags(df, return_rank_threshold=min(thr + 0.2, 0.99)) >= n_flags(df, return_rank_threshold=thr)


@settings(max_examples=60, deadline=None)
@given(metric_frames())
def test_dropping_drawdown_condition_never_removes_flags(df):
    assert n_flags(df, require_drawdown_worse_than_median=False) >= n_flags(df)
