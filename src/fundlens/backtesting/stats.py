"""Statistical machinery for the walk-forward evaluation (pure numpy, no I/O).

Observation = one (fund, month-end). ``y`` = fund's forward 12-month return minus its
category median forward 12-month return. A *lower* mean y among flagged funds means flagged
funds went on to underperform their peers by more (what a useful review flag should do).

Dependence structure and how it is handled
------------------------------------------
* Forward windows are 12 months long and month-ends are 1 month apart, so consecutive
  observations of the same fund share 11/12 of their window: strong serial dependence.
* Funds in one category share market shocks: cross-sectional dependence within months.

Primary CI: **cluster (fund-level) bootstrap**. Whole funds are resampled with replacement and
keep all their months, so within-fund serial dependence is preserved. It does NOT capture
common shocks across funds in the same month, so a **moving circular block bootstrap over
calendar months** (block length >= the 12-month overlap) is reported as a sensitivity check.
Neither is a perfect substitute for many independent periods; with a short out-of-sample
window both will be wide, and that is the honest answer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class Interval:
    estimate: float
    lower: float
    upper: float

    def contains_zero(self) -> bool:
        return self.lower <= 0.0 <= self.upper

    def as_dict(self) -> dict[str, float]:
        return {"estimate": self.estimate, "ci_lower": self.lower, "ci_upper": self.upper}


def mean_over(y: np.ndarray, mask: np.ndarray) -> float:
    n = int(mask.sum())
    return float(y[mask].mean()) if n else float("nan")


def _group_sums(
    codes: np.ndarray, n_groups: int, y: np.ndarray, mask: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    sums = np.bincount(codes, weights=np.where(mask, y, 0.0), minlength=n_groups)
    counts = np.bincount(codes, weights=mask.astype(float), minlength=n_groups)
    return sums, counts


def cluster_bootstrap(
    y: np.ndarray,
    fund_codes: np.ndarray,
    masks: dict[str, np.ndarray],
    *,
    n_boot: int,
    seed: int,
    alpha: float = 0.05,
) -> dict[str, Interval]:
    """Fund-clustered bootstrap CIs for the mean of y over each mask, plus pairwise differences.

    Returns intervals keyed by mask name and by ``"<a> - <b>"`` for each ordered pair (a, b)
    in ``masks`` order (e.g. ``"screen - baseline_bottom_quartile_1y"``).
    """
    rng = np.random.default_rng(seed)
    n_funds = int(fund_codes.max()) + 1
    stats = {name: _group_sums(fund_codes, n_funds, y, m) for name, m in masks.items()}
    draws = rng.integers(0, n_funds, size=(n_boot, n_funds))

    means: dict[str, np.ndarray] = {}
    for name, (sums, counts) in stats.items():
        s, c = sums[draws].sum(axis=1), counts[draws].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            means[name] = np.where(c > 0, s / c, np.nan)

    out = {name: _interval(mean_over(y, masks[name]), means[name], alpha) for name in masks}
    names = list(masks)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            diff = means[a] - means[b]
            out[f"{a} - {b}"] = _interval(mean_over(y, masks[a]) - mean_over(y, masks[b]), diff, alpha)
    return out


def block_bootstrap(
    y: np.ndarray,
    month_codes: np.ndarray,
    masks: dict[str, np.ndarray],
    *,
    block_len: int,
    n_boot: int,
    seed: int,
    alpha: float = 0.05,
) -> dict[str, Interval]:
    """Circular moving-block bootstrap over calendar months (sensitivity check)."""
    rng = np.random.default_rng(seed)
    n_months = int(month_codes.max()) + 1
    block_len = max(1, min(block_len, n_months))
    n_blocks = int(np.ceil(n_months / block_len))
    starts = rng.integers(0, n_months, size=(n_boot, n_blocks))
    idx = ((starts[:, :, None] + np.arange(block_len)[None, None, :]) % n_months).reshape(n_boot, -1)

    stats = {name: _group_sums(month_codes, n_months, y, m) for name, m in masks.items()}
    means: dict[str, np.ndarray] = {}
    for name, (sums, counts) in stats.items():
        s, c = sums[idx].sum(axis=1), counts[idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            means[name] = np.where(c > 0, s / c, np.nan)

    out = {name: _interval(mean_over(y, masks[name]), means[name], alpha) for name in masks}
    names = list(masks)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            out[f"{a} - {b}"] = _interval(
                mean_over(y, masks[a]) - mean_over(y, masks[b]), means[a] - means[b], alpha
            )
    return out


def _interval(estimate: float, draws: np.ndarray, alpha: float) -> Interval:
    d = draws[~np.isnan(draws)]
    if d.size == 0:
        return Interval(estimate, float("nan"), float("nan"))
    lo, hi = np.quantile(d, [alpha / 2, 1 - alpha / 2])
    return Interval(estimate, float(lo), float(hi))


@dataclass(frozen=True, slots=True)
class PermutationResult:
    observed: float
    null_mean: float
    null_lower: float
    null_upper: float
    p_value_lower: float  # P(null <= observed): small => flagged did WORSE than random
    n_permutations: int

    def as_dict(self) -> dict[str, float]:
        return {
            "observed_mean_y": self.observed,
            "random_flags_mean_y": self.null_mean,
            "random_flags_ci_lower": self.null_lower,
            "random_flags_ci_upper": self.null_upper,
            "p_value_flagged_worse_than_random": self.p_value_lower,
            "n_permutations": self.n_permutations,
        }


def permutation_baseline(
    y: np.ndarray,
    group_codes: np.ndarray,
    flagged: np.ndarray,
    *,
    n_perm: int,
    seed: int,
) -> PermutationResult:
    """Random flags at the same flag rate.

    Within every (month-end, category) group, the same NUMBER of funds is flagged as in the
    real screen but chosen uniformly at random. The distribution of mean-y under that null is
    compared with the observed mean-y. Preserving the per-group counts keeps the comparison
    free of month/category composition effects.
    """
    rng = np.random.default_rng(seed)
    n = len(y)
    order_by_group = np.argsort(group_codes, kind="stable")
    g_sorted = group_codes[order_by_group]
    y_sorted = y[order_by_group]
    flagged_sorted = flagged[order_by_group]
    n_groups = int(group_codes.max()) + 1
    group_start = np.searchsorted(g_sorted, np.arange(n_groups))
    quota = np.bincount(g_sorted, weights=flagged_sorted.astype(float), minlength=n_groups).astype(int)
    quota_per_row = quota[g_sorted]
    position_in_group = np.arange(n) - group_start[g_sorted]
    total_flagged = int(quota.sum())

    observed = float(y_sorted[flagged_sorted].mean()) if total_flagged else float("nan")
    null = np.empty(n_perm)
    for i in range(n_perm):
        keys = rng.random(n)
        # random order within each group: sort by (group, key), then take the first `quota` rows
        shuffled = np.lexsort((keys, g_sorted))
        chosen = position_in_group < quota_per_row  # in sorted-by-(group,key) order
        null[i] = y_sorted[shuffled][chosen].mean() if total_flagged else np.nan
    lo, hi = np.quantile(null, [0.025, 0.975])
    # +1 smoothing so a p-value is never reported as exactly 0
    p_lower = (1 + float((null <= observed).sum())) / (n_perm + 1)
    return PermutationResult(observed, float(null.mean()), float(lo), float(hi), p_lower, n_perm)
