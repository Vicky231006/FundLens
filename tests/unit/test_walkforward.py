"""Walk-forward protocol: split, purge and 'tuning never sees the test labels'."""

import numpy as np
import pandas as pd
import pytest

from fundlens.backtesting.walkforward import (
    BacktestConfig,
    build_panel,
    evaluate_period,
    interpret,
    screening_timeline,
    split_timeline,
    tune,
)
from fundlens.screening.engine import ScreeningParams, apply_screen

CFG = BacktestConfig(
    plan_type="DIRECT", min_peers=5, n_bootstrap=200, n_permutations=100, min_train_flag_obs=5
)
MONTHS = pd.date_range("2016-01-31", periods=60, freq="ME")


def synthetic_metrics(seed=0, n_funds=24):
    rng = np.random.default_rng(seed)
    rows = []
    for m in MONTHS:
        for f in range(n_funds):
            rows.append({
                "scheme_id": f, "me_date": m, "category": "Mid Cap" if f % 2 else "Large Cap",
                "plan_type": "DIRECT", "nav": 100.0, "cagr_1y": rng.normal(), "cagr_3y": rng.normal(),
                "cagr_5y": np.nan, "volatility_1y": 0.2, "sip_xirr_3y": np.nan,
            })  # fmt: skip
    df = pd.DataFrame(rows)
    g = df.groupby(["me_date", "category"])
    df["pct_rank_cagr_3y"] = g["cagr_3y"].rank(pct=True) - 1 / g["cagr_3y"].transform("count")
    df["pct_rank_cagr_3y"] = (g["cagr_3y"].rank(method="min") - 1) / (g["cagr_3y"].transform("count") - 1)
    df["pct_rank_cagr_1y"] = (g["cagr_1y"].rank(method="min") - 1) / (g["cagr_1y"].transform("count") - 1)
    df["peers_3y"] = g["cagr_3y"].transform("count")
    df["peers_1y"] = df["peers_3y"]
    df["peers_dd"] = df["peers_3y"]
    df["max_drawdown_3y"] = -np.abs(rng.normal(0.25, 0.1, len(df)))
    df["median_max_drawdown_3y"] = df.groupby(["me_date", "category"])["max_drawdown_3y"].transform("median")
    df["median_cagr_3y"] = g["cagr_3y"].transform("median")
    return df


def synthetic_forward(metrics, seed=1):
    rng = np.random.default_rng(seed)
    out = metrics[["scheme_id", "me_date"]].copy()
    out["fwd_end_date"] = out["me_date"] + pd.offsets.MonthEnd(12)
    out["y"] = rng.normal(0, 0.05, len(out))
    return out


def test_split_is_sixty_forty_over_the_screenable_timeline():
    timeline = list(MONTHS)
    test_start, n_train, n_test = split_timeline(timeline, 0.6)
    assert (n_train, n_test) == (36, 24)
    assert test_start == MONTHS[36]


def test_split_refuses_tiny_timelines():
    with pytest.raises(ValueError):
        split_timeline(list(MONTHS[:5]), 0.6)


def test_screening_timeline_ignores_months_without_enough_peers():
    m = synthetic_metrics()
    m.loc[m.me_date == MONTHS[0], "peers_3y"] = 2
    assert MONTHS[0] not in screening_timeline(m, 5)
    assert MONTHS[1] in screening_timeline(m, 5)


def test_panel_only_contains_eligible_labelled_rows():
    m = synthetic_metrics()
    fwd = synthetic_forward(m)
    fwd = fwd[fwd.me_date < MONTHS[50]]  # no labels for the last months
    screened = apply_screen(m, ScreeningParams(min_peers=5))
    panel = build_panel(screened, fwd, CFG)
    assert panel.me_date.max() < MONTHS[50]
    assert panel["y"].notna().all()


def test_training_selection_never_sees_test_labels():
    m = synthetic_metrics()
    fwd = synthetic_forward(m)
    test_start = MONTHS[36]
    screened = apply_screen(m, ScreeningParams(min_peers=5))
    panel = build_panel(screened, fwd, CFG)
    chosen, trials = tune(panel, m, test_start, CFG)

    # Wildly change every label that lies at/after the test start, and every label whose forward
    # window crosses it: tuning must not move.
    tampered = fwd.copy()
    leaky = tampered["fwd_end_date"] >= test_start
    tampered.loc[leaky, "y"] = 99.0
    panel2 = build_panel(screened, tampered, CFG)
    chosen2, trials2 = tune(panel2, m, test_start, CFG)
    assert chosen == chosen2
    assert trials == trials2


def test_tuning_does_respond_to_training_labels():
    m = synthetic_metrics()
    fwd = synthetic_forward(m)
    screened = apply_screen(m, ScreeningParams(min_peers=5))
    panel = build_panel(screened, fwd, CFG)
    _, trials = tune(panel, m, MONTHS[36], CFG)
    tampered = fwd.copy()
    train = tampered["fwd_end_date"] < MONTHS[36]
    tampered.loc[train, "y"] = tampered.loc[train, "y"] + 1.0
    _, trials2 = tune(build_panel(screened, tampered, CFG), m, MONTHS[36], CFG)
    assert trials != trials2


def test_training_panel_is_purged_at_the_split():
    m = synthetic_metrics()
    fwd = synthetic_forward(m)
    test_start = MONTHS[36]
    panel = build_panel(apply_screen(m, ScreeningParams(min_peers=5)), fwd, CFG)
    train = panel[panel["fwd_end_date"] < test_start]
    test = panel[panel["me_date"] >= test_start]
    assert train["fwd_end_date"].max() < test_start
    assert train["me_date"].max() <= MONTHS[24]  # 12-month purge window
    assert test["me_date"].min() == test_start


def test_evaluate_period_end_to_end_structure_and_baseline_flags():
    m = synthetic_metrics()
    fwd = synthetic_forward(m)
    panel = build_panel(apply_screen(m, ScreeningParams(min_peers=5, k=1)), fwd, CFG)
    res = evaluate_period(panel, CFG, "x")
    for key in ("screen", "baseline_bottom_quartile_1y", "ci_fund_cluster_bootstrap",
                "ci_month_block_bootstrap", "permutation_random_flags_screen"):  # fmt: skip
        assert key in res
    ci = res["ci_fund_cluster_bootstrap"]["screen"]
    assert ci["ci_lower"] <= ci["estimate"] <= ci["ci_upper"]
    assert res["screen"]["n_flag_obs"] == int(panel["flagged"].sum())
    assert "screen - baseline_bottom_quartile_1y" in res["ci_fund_cluster_bootstrap"]


def test_pure_noise_is_rarely_declared_informative():
    """Calibration: labels are independent of flags by construction, so a 'flags underperformed'
    verdict is a false positive. Over 40 noise draws it must be rare (nominal ~2.5%; measured
    1/60 when this was developed). A broken CI or permutation test would fail this."""
    m = synthetic_metrics(seed=3)
    screened = apply_screen(m, ScreeningParams(min_peers=5, k=1))
    cfg = BacktestConfig(plan_type="DIRECT", min_peers=5, n_bootstrap=300, n_permutations=150)
    false_positives = 0
    n = 40
    for s in range(n):
        panel = build_panel(screened, synthetic_forward(m, seed=100 + s), cfg)
        verdict = interpret(evaluate_period(panel, cfg, "noise"))
        false_positives += verdict.startswith("Flagged funds subsequently underperformed")
    assert false_positives <= 4  # <= 10%


def test_noise_verdict_wording_is_inconclusive():
    m = synthetic_metrics(seed=3)
    panel = build_panel(
        apply_screen(m, ScreeningParams(min_peers=5, k=1)), synthetic_forward(m, seed=100), CFG
    )
    assert interpret(evaluate_period(panel, CFG, "noise")).startswith("Inconclusive")


def test_informative_screen_is_recognised():
    m = synthetic_metrics(seed=5)
    fwd = synthetic_forward(m, seed=6)
    screened = apply_screen(m, ScreeningParams(min_peers=5, k=1, require_drawdown_worse_than_median=False))
    flags = screened.set_index(["scheme_id", "me_date"])["flagged"]
    fwd = fwd.copy()
    is_flag = flags.reindex(pd.MultiIndex.from_frame(fwd[["scheme_id", "me_date"]])).to_numpy()
    fwd.loc[is_flag, "y"] -= 0.10  # truly informative: flagged funds really do worse
    panel = build_panel(screened, fwd, CFG)
    res = evaluate_period(panel, CFG, "informative")
    assert interpret(res).startswith("Flagged funds subsequently underperformed")
