"""Walk-forward evaluation of the review-flag screen (FR-A6).

Protocol
--------
1. At every month-end t the screen sees only metrics computed from NAVs dated <= t
   (point-in-time metrics in ``marts.mv_scheme_month_metrics``).
2. y(t) = forward 12-month return - category median forward 12-month return, taken from
   ``marts.mv_forward_return_12m`` and used ONLY to evaluate, never to decide.
3. Timeline split: the first ``train_fraction`` (default 60%) of the month-ends on which the
   screen can operate are TRAIN, the rest are TEST (out-of-sample).
4. Purging: a training observation is used only if its 12-month forward window ENDS before the
   first test month-end, so no training label contains information from the test period.
5. Parameters are tuned on TRAIN only (grid in config/screening.toml); the default
   parameters and the tuned parameters are both reported on TEST, so tuning cannot hide behind
   a cherry-picked comparison.
6. Baselines on the same eligible universe: (1) bottom-quartile 1-year return,
   (2) random flags at the same per-(month, category) flag counts (permutation test).
7. 95% CIs: fund-clustered bootstrap (primary) + circular block bootstrap over months.

Results are descriptive evidence about THIS dataset (which suffers from survivorship bias;
see docs/DATA_CARD.md), not proof of predictive ability.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
import psycopg

from fundlens.backtesting.stats import (
    block_bootstrap,
    cluster_bootstrap,
    permutation_baseline,
)
from fundlens.screening.engine import (
    ScreeningParams,
    apply_screen,
    default_params,
    load_metrics,
    load_screening_config,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    plan_type: str = "DIRECT"
    train_fraction: float = 0.60
    min_peers: int = 8
    baseline_rank_threshold: float = 0.25
    min_train_flag_obs: int = 100
    n_bootstrap: int = 5000
    n_permutations: int = 2000
    block_len_months: int = 12
    seed: int = 20240607


def load_forward(conn: psycopg.Connection, plan_type: str) -> pd.DataFrame:
    rows = conn.execute(
        "SELECT scheme_id, me_date, fwd_end_date, fwd_return_12m, median_fwd_return_12m, excess_fwd "
        "FROM marts.mv_forward_return_12m WHERE plan_type = %s",
        (plan_type,),
    ).fetchall()
    df = pd.DataFrame(
        rows,
        columns=["scheme_id", "me_date", "fwd_end_date", "fwd_return_12m", "median_fwd", "y"],
    )
    df["me_date"] = pd.to_datetime(df["me_date"])
    df["fwd_end_date"] = pd.to_datetime(df["fwd_end_date"])
    for c in ("fwd_return_12m", "median_fwd", "y"):
        df[c] = pd.to_numeric(df[c])
    return df


def screening_timeline(metrics: pd.DataFrame, min_peers: int) -> list[pd.Timestamp]:
    """Month-ends on which the screen can operate (a 3y return rank exists for >= min_peers)."""
    ok = metrics[metrics["pct_rank_cagr_3y"].notna() & metrics["peers_3y"].ge(min_peers)]
    return sorted(ok["me_date"].unique())


def split_timeline(timeline: list[pd.Timestamp], train_fraction: float) -> tuple[pd.Timestamp, int, int]:
    """Return (first test month-end, n_train_months, n_test_months)."""
    if len(timeline) < 10:
        raise ValueError("Too few screenable month-ends for a train/test split")
    n_train = int(np.floor(len(timeline) * train_fraction))
    return timeline[n_train], n_train, len(timeline) - n_train


def build_panel(screened: pd.DataFrame, forward: pd.DataFrame, cfg: BacktestConfig) -> pd.DataFrame:
    """Eligible observations (3y metrics present, enough peers, forward label present)."""
    panel = screened.merge(
        forward[["scheme_id", "me_date", "fwd_end_date", "y"]], on=["scheme_id", "me_date"], how="inner"
    )
    eligible = panel["pct_rank_cagr_3y"].notna() & panel["peers_3y"].ge(cfg.min_peers) & panel["y"].notna()
    panel = panel[eligible].copy()
    panel["baseline_b1"] = panel["pct_rank_cagr_1y"].le(cfg.baseline_rank_threshold) & panel["peers_1y"].ge(
        cfg.min_peers
    )
    return panel


def _evaluate_mask(panel: pd.DataFrame, mask_name: str) -> dict[str, Any]:
    m = panel[mask_name].to_numpy()
    y = panel["y"].to_numpy()
    n = int(m.sum())
    return {
        "n_flag_obs": n,
        "n_funds": int(panel.loc[m, "scheme_id"].nunique()) if n else 0,
        "n_month_ends": int(panel.loc[m, "me_date"].nunique()) if n else 0,
        "mean_y": float(y[m].mean()) if n else None,
        "median_y": float(np.median(y[m])) if n else None,
        "share_underperforming_peer_median": float((y[m] < 0).mean()) if n else None,
    }


def tune(
    panel_all: pd.DataFrame, metrics: pd.DataFrame, test_start: pd.Timestamp, cfg: BacktestConfig
) -> tuple[ScreeningParams, list[dict]]:
    """Choose parameters using TRAIN observations only (labels purged before test_start)."""
    grid = load_screening_config()["tuning_grid"]
    base = default_params()
    base = ScreeningParams(**{**asdict(base), "plan_type": cfg.plan_type, "min_peers": cfg.min_peers})
    train_labels = panel_all[panel_all["fwd_end_date"] < test_start]
    trials: list[dict] = []
    for k, thr, dd in itertools.product(
        grid["k"], grid["return_rank_threshold"], grid["require_drawdown_worse_than_median"]
    ):
        params = ScreeningParams(**{**asdict(base), "k": k, "return_rank_threshold": thr,
                                    "require_drawdown_worse_than_median": dd})  # fmt: skip
        scr = apply_screen(metrics, params)[["scheme_id", "me_date", "flagged"]]
        joined = train_labels[["scheme_id", "me_date", "y"]].merge(
            scr, on=["scheme_id", "me_date"], how="left"
        )
        flagged = joined[joined["flagged"].fillna(False).astype(bool)]
        trials.append({
            "k": k, "return_rank_threshold": thr, "require_drawdown_worse_than_median": dd,
            "train_flag_obs": len(flagged),
            "train_mean_y": float(flagged["y"].mean()) if len(flagged) else None,
        })  # fmt: skip
    eligible = [t for t in trials if t["train_flag_obs"] >= cfg.min_train_flag_obs]
    if not eligible:
        log.warning(
            "No grid point reached %d training flag observations; using defaults", cfg.min_train_flag_obs
        )
        return base, trials
    best = min(eligible, key=lambda t: (t["train_mean_y"], t["train_flag_obs"]))
    chosen = ScreeningParams(**{**asdict(base), "k": best["k"],
                                "return_rank_threshold": best["return_rank_threshold"],
                                "require_drawdown_worse_than_median": best["require_drawdown_worse_than_median"]})  # fmt: skip
    return chosen, trials


def _codes(series: pd.Series) -> np.ndarray:
    return pd.factorize(series, sort=True)[0].astype(np.int64)


def evaluate_period(panel: pd.DataFrame, cfg: BacktestConfig, label: str) -> dict[str, Any]:
    """Evaluate screen flags vs baselines on one period (expects columns flagged, baseline_b1, y)."""
    if panel.empty:
        return {"label": label, "n_obs": 0}
    y = panel["y"].to_numpy()
    screen = panel["flagged"].to_numpy().astype(bool)
    b1 = panel["baseline_b1"].to_numpy().astype(bool)
    fund_codes = _codes(panel["scheme_id"])
    month_codes = _codes(panel["me_date"])
    group_codes = _codes(panel["me_date"].astype(str) + "|" + panel["category"])

    masks = {"screen": screen, "baseline_bottom_quartile_1y": b1, "all_eligible": np.ones(len(y), bool)}
    fund_ci = cluster_bootstrap(y, fund_codes, masks, n_boot=cfg.n_bootstrap, seed=cfg.seed)
    month_ci = block_bootstrap(y, month_codes, masks, block_len=cfg.block_len_months,
                               n_boot=cfg.n_bootstrap, seed=cfg.seed + 1)  # fmt: skip
    perm = (
        permutation_baseline(y, group_codes, screen, n_perm=cfg.n_permutations, seed=cfg.seed + 2)
        if screen.any()
        else None
    )
    perm_b1 = (
        permutation_baseline(y, group_codes, b1, n_perm=cfg.n_permutations, seed=cfg.seed + 3)
        if b1.any()
        else None
    )
    return {
        "label": label,
        "n_obs": int(len(y)),
        "n_funds": int(panel["scheme_id"].nunique()),
        "n_month_ends": int(panel["me_date"].nunique()),
        "first_month_end": str(panel["me_date"].min().date()),
        "last_month_end": str(panel["me_date"].max().date()),
        "mean_y_all_eligible": float(y.mean()),
        "screen": _evaluate_mask(panel.assign(screen=screen), "screen"),
        "baseline_bottom_quartile_1y": _evaluate_mask(panel, "baseline_b1"),
        "ci_fund_cluster_bootstrap": {k: v.as_dict() for k, v in fund_ci.items()},
        "ci_month_block_bootstrap": {k: v.as_dict() for k, v in month_ci.items()},
        "permutation_random_flags_screen": perm.as_dict() if perm else None,
        "permutation_random_flags_baseline1": perm_b1.as_dict() if perm_b1 else None,
        "screen_vs_baseline_ci_includes_zero_fund_cluster": (
            fund_ci["screen - baseline_bottom_quartile_1y"].contains_zero()
        ),
    }


def interpret(result: dict[str, Any]) -> str:
    """Rule-based, deliberately conservative wording for a test-period result."""
    if not result.get("n_obs") or not result["screen"]["n_flag_obs"]:
        return "No flagged observations in the evaluation period: nothing to conclude."
    ci = result["ci_fund_cluster_bootstrap"]["screen"]
    p = (result["permutation_random_flags_screen"] or {}).get("p_value_flagged_worse_than_random")
    if ci["ci_upper"] < 0 and p is not None and p < 0.05:
        return (
            "Flagged funds subsequently underperformed their category median on average and the "
            "fund-clustered 95% CI excludes zero. This is evidence about this sample only; it is "
            "survivorship-biased and not a demonstration of predictive ability."
        )
    if ci["ci_lower"] > 0:
        return "Flagged funds did NOT underperform: they outperformed their category median on average."
    return (
        "Inconclusive: the 95% CI for the flagged funds' excess forward return includes zero, so "
        "the data do not show that flagged funds behave differently from peers."
    )


def run_backtest(conn: psycopg.Connection, cfg: BacktestConfig) -> dict[str, Any]:
    metrics = load_metrics(conn, cfg.plan_type)
    forward = load_forward(conn, cfg.plan_type)
    if metrics.empty or forward.empty:
        raise RuntimeError(f"No metrics/forward returns for plan type {cfg.plan_type}; run build-marts first")

    timeline = screening_timeline(metrics, cfg.min_peers)
    test_start, n_train, n_test = split_timeline(timeline, cfg.train_fraction)

    base = default_params()
    default = ScreeningParams(**{**asdict(base), "plan_type": cfg.plan_type, "min_peers": cfg.min_peers})
    base_panel = build_panel(apply_screen(metrics, default), forward, cfg)
    tuned, trials = tune(base_panel, metrics, test_start, cfg)

    out: dict[str, Any] = {
        "plan_type": cfg.plan_type,
        "config": asdict(cfg),
        "dataset": {
            "n_schemes_with_metrics": int(metrics["scheme_id"].nunique()),
            "n_scheme_month_rows": int(len(metrics)),
            "screenable_month_ends": len(timeline),
            "first_screenable_month_end": str(timeline[0].date()),
            "last_screenable_month_end": str(timeline[-1].date()),
            "train_month_ends": n_train,
            "test_month_ends": n_test,
            "test_start": str(test_start.date()),
            "train_labels_purged_before": str(test_start.date()),
            "n_categories": int(metrics["category"].nunique()),
        },
        "tuning_trials": trials,
        "default_params": asdict(default),
        "tuned_params": asdict(tuned),
        "periods": {},
    }
    for name, params in (("default", default), ("tuned", tuned)):
        panel = build_panel(apply_screen(metrics, params), forward, cfg)
        train = panel[panel["fwd_end_date"] < test_start]
        test = panel[panel["me_date"] >= test_start]
        res_test = evaluate_period(test, cfg, f"{name}/test")
        res_test["interpretation"] = interpret(res_test)
        out["periods"][name] = {
            "train": evaluate_period(train, cfg, f"{name}/train"),
            "test": res_test,
        }
    return out
