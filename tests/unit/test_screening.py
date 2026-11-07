"""Screening logic on hand-built metric frames (no database)."""

import numpy as np
import pandas as pd
import pytest

from fundlens.screening.engine import (
    ScreeningParams,
    add_streaks,
    apply_screen,
    evaluate_conditions,
    explain,
    flags_only,
)

MONTHS = pd.date_range("2020-01-31", periods=8, freq="ME")


def frame(rows):
    base = {
        "category": "Mid Cap", "plan_type": "DIRECT", "nav": 100.0, "peers_3y": 10, "peers_dd": 10,
        "median_max_drawdown_3y": -0.20, "median_cagr_3y": 0.10, "cagr_1y": 0.0,
        "pct_rank_cagr_1y": 0.5, "volatility_1y": 0.2, "cagr_5y": None, "cagr_3y": 0.05,
        "sip_xirr_3y": None,
    }  # fmt: skip
    return pd.DataFrame([{**base, **r} for r in rows])


def fund_rows(scheme_id, ranks, dd=-0.30, months=MONTHS):
    return [
        {"scheme_id": scheme_id, "me_date": m, "pct_rank_cagr_3y": r, "max_drawdown_3y": dd}
        for m, r in zip(months, ranks, strict=False)
    ]


P = ScreeningParams(k=3, return_rank_threshold=0.25, min_peers=8)


def test_flag_requires_k_consecutive_months():
    df = frame(fund_rows(1, [0.1, 0.1, 0.9, 0.1, 0.1, 0.1, 0.1, 0.9]))
    out = apply_screen(df, P).set_index("me_date")
    assert out["streak"].tolist() == [1, 2, 0, 1, 2, 3, 4, 0]
    assert out["flagged"].tolist() == [False, False, False, False, False, True, True, False]


def test_k_is_configurable():
    df = frame(fund_rows(1, [0.1] * 8))
    assert apply_screen(df, ScreeningParams(k=1))["flagged"].all()
    assert apply_screen(df, ScreeningParams(k=8))["flagged"].tolist() == [False] * 7 + [True]
    assert not apply_screen(df, ScreeningParams(k=9))["flagged"].any()


def test_rank_threshold_boundary_is_inclusive():
    df = frame(fund_rows(1, [0.25] * 3))
    assert apply_screen(df, P)["flagged"].tolist() == [False, False, True]
    assert not apply_screen(df, ScreeningParams(k=3, return_rank_threshold=0.20))["flagged"].any()


def test_drawdown_must_be_worse_than_median_strictly():
    same = frame(fund_rows(1, [0.1] * 4, dd=-0.20))  # equal to median: not worse
    assert not apply_screen(same, P)["flagged"].any()
    better = frame(fund_rows(1, [0.1] * 4, dd=-0.10))
    assert not apply_screen(better, P)["flagged"].any()
    worse = frame(fund_rows(1, [0.1] * 4, dd=-0.25))
    assert apply_screen(worse, P)["flagged"].any()


def test_drawdown_condition_can_be_disabled():
    df = frame(fund_rows(1, [0.1] * 4, dd=-0.05))
    relaxed = ScreeningParams(k=3, require_drawdown_worse_than_median=False)
    assert apply_screen(df, relaxed)["flagged"].any()


def test_small_peer_groups_are_not_screened():
    df = frame(fund_rows(1, [0.0] * 5))
    df["peers_3y"] = 4
    assert not apply_screen(df, P)["flagged"].any()


def test_missing_metrics_never_flag():
    df = frame(fund_rows(1, [np.nan] * 4))
    assert not apply_screen(df, P)["flagged"].any()


def test_calendar_gap_breaks_streak():
    months = [MONTHS[0], MONTHS[1], MONTHS[3], MONTHS[4]]  # Mar-2020 missing
    df = frame(fund_rows(1, [0.1] * 4, months=months))
    assert apply_screen(df, ScreeningParams(k=3))["streak"].tolist() == [1, 2, 1, 2]


def test_funds_are_independent():
    df = frame(fund_rows(1, [0.1] * 4) + fund_rows(2, [0.9, 0.1, 0.1, 0.1]))
    out = apply_screen(df, P)
    assert out[out.scheme_id == 1]["streak"].tolist() == [1, 2, 3, 4]
    assert out[out.scheme_id == 2]["streak"].tolist() == [0, 1, 2, 3]


def test_plan_types_are_never_mixed():
    df = frame(fund_rows(1, [0.1] * 4))
    df.loc[:, "plan_type"] = "REGULAR"
    assert apply_screen(df, ScreeningParams(plan_type="DIRECT")).empty


def test_no_look_ahead_truncating_future_does_not_change_past_flags():
    rng = np.random.default_rng(7)
    rows = []
    for sid in range(1, 6):
        rows += fund_rows(sid, rng.uniform(0, 1, len(MONTHS)), dd=-rng.uniform(0.1, 0.4))
    df = frame(rows)
    full = apply_screen(df, P).set_index(["scheme_id", "me_date"])["flagged"]
    for cut in MONTHS[2:-1]:
        part = apply_screen(df[df.me_date <= cut], P).set_index(["scheme_id", "me_date"])["flagged"]
        assert part.equals(full.loc[part.index])


def test_explanation_quotes_triggering_figures_and_disclaimer():
    df = frame(fund_rows(1, [0.1] * 3, dd=-0.3))
    df["cagr_3y"] = 0.042
    flagged = flags_only(apply_screen(df, P), P)
    assert len(flagged) == 1
    text = flagged.iloc[0]["explanation"]
    assert "3-year CAGR 4.2%" in text and "percentile 10" in text and "10 Mid Cap (Direct)" in text
    assert "-30.0% is worse than the category median -20.0%" in text
    assert "3 consecutive month-end(s) (required k=3)" in text
    assert "not an investment recommendation" in text


def test_evaluate_conditions_columns():
    df = evaluate_conditions(frame(fund_rows(1, [0.1, 0.9])), P)
    assert df["cond_return"].tolist() == [True, False]
    assert df["cond_all"].tolist() == [True, False]
    assert "streak" in add_streaks(df).columns


def test_invalid_params_rejected():
    with pytest.raises(ValueError):
        ScreeningParams(k=0)
    with pytest.raises(ValueError):
        ScreeningParams(return_rank_threshold=1.5)
    assert explain  # imported for explicitness
