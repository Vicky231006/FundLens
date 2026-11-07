"""Backtest statistics on data with a KNOWN truth (synthetic simulation, not market data)."""

import numpy as np
import pytest

from fundlens.backtesting.stats import block_bootstrap, cluster_bootstrap, permutation_baseline


def make_panel(n_funds=60, n_months=40, seed=1, flagged_shift=0.0, noise=0.05):
    """Panel where flagged observations have true mean y == flagged_shift, others 0."""
    rng = np.random.default_rng(seed)
    fund = np.repeat(np.arange(n_funds), n_months)
    month = np.tile(np.arange(n_months), n_funds)
    cat = fund % 3
    group = month * 3 + cat
    flagged = rng.random(len(fund)) < 0.2
    # fund-level random effect creates within-fund dependence
    fund_effect = rng.normal(0, 0.02, n_funds)[fund]
    y = fund_effect + rng.normal(0, noise, len(fund)) + np.where(flagged, flagged_shift, 0.0)
    return y, fund, month, group, flagged


def test_cluster_bootstrap_ci_covers_truth_and_excludes_zero_when_effect_is_large():
    y, fund, _, _, flagged = make_panel(flagged_shift=-0.06)
    ci = cluster_bootstrap(y, fund, {"screen": flagged}, n_boot=2000, seed=3)["screen"]
    assert ci.lower < -0.06 < ci.upper
    assert ci.upper < 0  # correctly detects the true negative effect


def test_cluster_bootstrap_includes_zero_when_no_effect():
    y, fund, _, _, flagged = make_panel(flagged_shift=0.0, seed=5)
    ci = cluster_bootstrap(y, fund, {"screen": flagged}, n_boot=2000, seed=3)["screen"]
    assert ci.contains_zero()


def test_cluster_bootstrap_constant_y_collapses_ci():
    y = np.full(100, 0.03)
    fund = np.repeat(np.arange(10), 10)
    ci = cluster_bootstrap(y, fund, {"a": np.ones(100, bool)}, n_boot=500, seed=1)["a"]
    assert ci.lower == pytest.approx(0.03) and ci.upper == pytest.approx(0.03)


def test_cluster_bootstrap_is_reproducible_for_a_seed_and_differs_across_seeds():
    y, fund, _, _, flagged = make_panel()
    a = cluster_bootstrap(y, fund, {"s": flagged}, n_boot=500, seed=9)["s"]
    b = cluster_bootstrap(y, fund, {"s": flagged}, n_boot=500, seed=9)["s"]
    c = cluster_bootstrap(y, fund, {"s": flagged}, n_boot=500, seed=10)["s"]
    assert (a.lower, a.upper) == (b.lower, b.upper)
    assert (a.lower, a.upper) != (c.lower, c.upper)


def test_pairwise_difference_interval_is_reported_and_consistent():
    y, fund, _, _, flagged = make_panel(flagged_shift=-0.05)
    other = ~flagged
    res = cluster_bootstrap(y, fund, {"screen": flagged, "rest": other}, n_boot=1000, seed=2)
    d = res["screen - rest"]
    assert d.estimate == pytest.approx(res["screen"].estimate - res["rest"].estimate)
    assert d.upper < 0


def test_clustering_widens_ci_when_funds_are_dependent():
    # Large fund effect + all months flagged for half the funds: naive iid CI would be far too narrow.
    rng = np.random.default_rng(0)
    n_funds, n_months = 30, 60
    fund = np.repeat(np.arange(n_funds), n_months)
    effect = rng.normal(0, 0.05, n_funds)[fund]
    y = effect + rng.normal(0, 0.01, len(fund))
    flagged = fund < 15
    ci = cluster_bootstrap(y, fund, {"s": flagged}, n_boot=2000, seed=1)["s"]
    naive_se = y[flagged].std(ddof=1) / np.sqrt(flagged.sum())
    assert (ci.upper - ci.lower) > 2 * 1.96 * naive_se * 3


def test_block_bootstrap_runs_and_brackets_estimate():
    y, _, month, _, flagged = make_panel(flagged_shift=-0.04)
    ci = block_bootstrap(y, month, {"s": flagged}, block_len=12, n_boot=1000, seed=4)["s"]
    assert ci.lower <= ci.estimate <= ci.upper


def test_permutation_detects_flags_chosen_on_low_y():
    y, _, _, group, _ = make_panel(seed=11)
    # flag the lowest-y 20% inside each group: a genuinely informative screen
    flagged = np.zeros(len(y), bool)
    for g in np.unique(group):
        idx = np.where(group == g)[0]
        k = max(1, int(0.2 * len(idx)))
        flagged[idx[np.argsort(y[idx])[:k]]] = True
    res = permutation_baseline(y, group, flagged, n_perm=500, seed=1)
    assert res.p_value_lower < 0.01
    assert res.observed < res.null_lower


def test_permutation_does_not_reject_random_flags():
    y, _, _, group, flagged = make_panel(seed=12, flagged_shift=0.0)
    res = permutation_baseline(y, group, flagged, n_perm=500, seed=1)
    assert res.p_value_lower > 0.05
    assert res.null_lower <= res.observed <= res.null_upper


def test_permutation_flagging_everything_has_no_variance():
    y, _, _, group, _ = make_panel(n_funds=9, n_months=5)
    res = permutation_baseline(y, group, np.ones(len(y), bool), n_perm=50, seed=1)
    assert res.null_lower == pytest.approx(res.null_upper)
    assert res.null_mean == pytest.approx(y.mean())


def test_permutation_null_mean_matches_group_composition():
    # Group A has y=1 (flag quota 1 of 2), group B has y=0 (quota 1 of 2): any permutation
    # gives mean(1, 0) = 0.5 exactly - composition is preserved.
    y = np.array([1.0, 1.0, 0.0, 0.0])
    group = np.array([0, 0, 1, 1])
    flagged = np.array([True, False, True, False])
    res = permutation_baseline(y, group, flagged, n_perm=100, seed=3)
    assert res.null_mean == pytest.approx(0.5) and res.null_lower == pytest.approx(0.5)
