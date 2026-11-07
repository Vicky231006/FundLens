"""Configurable, explainable review-flag algorithm (FR-A5).

A fund is flagged at month-end t when, for ``k`` consecutive month-ends ending at t,

1. its 3-year CAGR percentile rank within (category, plan type) is <= ``return_rank_threshold``
   (default 0.25: bottom quartile), AND
2. its 3-year max drawdown is worse (more negative) than the category median
   (only if ``require_drawdown_worse_than_median``).

Peer groups with fewer than ``min_peers`` measurable funds are not screened.

Point-in-time guarantee: the decision at month-end t uses only columns of the metrics table
for month-ends <= t (the table itself only uses NAVs dated <= t). No forward return enters
this module. ``tests/unit/test_screening.py`` verifies that truncating the data at t does not
change any flag at or before t.

The output is a research-review flag, not an investment recommendation.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import pandas as pd
import psycopg

from fundlens.config import PROJECT_ROOT

SCREENING_CONFIG_PATH = PROJECT_ROOT / "config" / "screening.toml"

METRIC_COLUMNS = [
    "scheme_id", "me_date", "category", "plan_type", "nav", "cagr_1y", "cagr_3y", "cagr_5y",
    "volatility_1y", "max_drawdown_3y", "sip_xirr_3y", "pct_rank_cagr_1y", "pct_rank_cagr_3y",
    "peers_1y", "peers_3y", "peers_dd", "median_cagr_3y", "median_max_drawdown_3y",
]  # fmt: skip

DISCLAIMER = "Research-review flag only; this is not an investment recommendation."


@dataclass(frozen=True, slots=True)
class ScreeningParams:
    k: int = 3
    return_rank_threshold: float = 0.25
    require_drawdown_worse_than_median: bool = True
    min_peers: int = 8
    plan_type: str = "DIRECT"

    def __post_init__(self) -> None:
        if self.k < 1:
            raise ValueError("k must be >= 1")
        if not 0 < self.return_rank_threshold < 1:
            raise ValueError("return_rank_threshold must be in (0, 1)")
        if self.min_peers < 2:
            raise ValueError("min_peers must be >= 2")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


def load_screening_config(path: Path = SCREENING_CONFIG_PATH) -> dict:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def default_params(path: Path = SCREENING_CONFIG_PATH) -> ScreeningParams:
    return ScreeningParams(**load_screening_config(path)["default"])


def load_metrics(conn: psycopg.Connection, plan_type: str | None = None) -> pd.DataFrame:
    cols = ", ".join(METRIC_COLUMNS)
    sql = f"SELECT {cols} FROM marts.mv_scheme_month_metrics"  # noqa: S608 - static column list
    params: tuple = ()
    if plan_type:
        sql += " WHERE plan_type = %s"
        params = (plan_type,)
    rows = conn.execute(sql + " ORDER BY scheme_id, me_date", params).fetchall()
    df = pd.DataFrame(rows, columns=METRIC_COLUMNS)
    df["me_date"] = pd.to_datetime(df["me_date"])
    for col in METRIC_COLUMNS[4:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def month_number(dates: pd.Series) -> pd.Series:
    return dates.dt.year * 12 + dates.dt.month


def evaluate_conditions(df: pd.DataFrame, params: ScreeningParams) -> pd.DataFrame:
    """Add boolean columns cond_return, cond_drawdown, cond_all (per month-end, no persistence)."""
    out = df.copy()
    peers_ok = out["peers_3y"].ge(params.min_peers)
    out["cond_return"] = (
        out["pct_rank_cagr_3y"].le(params.return_rank_threshold) & peers_ok & out["pct_rank_cagr_3y"].notna()
    )
    if params.require_drawdown_worse_than_median:
        dd_ok = out["peers_dd"].ge(params.min_peers)
        out["cond_drawdown"] = (
            out["max_drawdown_3y"].lt(out["median_max_drawdown_3y"]) & dd_ok & out["max_drawdown_3y"].notna()
        )
    else:
        out["cond_drawdown"] = True
    out["cond_all"] = out["cond_return"] & out["cond_drawdown"]
    return out


def add_streaks(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``streak``: consecutive calendar month-ends (per scheme) on which cond_all held."""
    out = df.sort_values(["scheme_id", "me_date"]).copy()
    out["month_no"] = month_number(out["me_date"])
    g = out.groupby("scheme_id", sort=False)
    prev_cond = g["cond_all"].shift(1, fill_value=False)
    prev_month = g["month_no"].shift(1)
    continues = out["cond_all"] & prev_cond & (out["month_no"] - prev_month).eq(1)
    run_id = (~continues).groupby(out["scheme_id"]).cumsum()
    out["streak"] = out["cond_all"].astype(int).groupby([out["scheme_id"], run_id]).cumsum()
    return out


def apply_screen(metrics: pd.DataFrame, params: ScreeningParams) -> pd.DataFrame:
    """All (scheme, month-end) rows with flag status; ``flagged`` is True when streak >= k."""
    df = metrics[metrics["plan_type"] == params.plan_type] if params.plan_type else metrics
    df = add_streaks(evaluate_conditions(df, params))
    df["flagged"] = df["streak"] >= params.k
    return df


def explain(row: pd.Series, params: ScreeningParams) -> str:
    """Human-readable reason a fund was flagged, quoting the figures that triggered it."""
    parts = [
        f"3-year CAGR {row.cagr_3y * 100:.1f}% ranks at percentile {row.pct_rank_cagr_3y * 100:.0f} of "
        f"{int(row.peers_3y)} {row.category} ({row.plan_type.title()}) funds "
        f"(threshold: bottom {params.return_rank_threshold * 100:.0f}%)"
    ]
    if params.require_drawdown_worse_than_median:
        parts.append(
            f"3-year max drawdown {float(row.max_drawdown_3y) * 100:.1f}% is worse than the "
            f"category median {row.median_max_drawdown_3y * 100:.1f}%"
        )
    parts.append(f"conditions held for {int(row.streak)} consecutive month-end(s) (required k={params.k})")
    return "; ".join(parts) + f". {DISCLAIMER}"


def flags_only(screened: pd.DataFrame, params: ScreeningParams) -> pd.DataFrame:
    flagged = screened[screened["flagged"]].copy()
    if flagged.empty:
        flagged["explanation"] = pd.Series(dtype=str)
    else:
        flagged["explanation"] = flagged.apply(lambda row: explain(row, params), axis=1)
    return flagged


def save_flags(conn: psycopg.Connection, label: str, params: ScreeningParams, flagged: pd.DataFrame) -> int:
    """Persist a screening run and its flags; returns run_id."""
    with conn.transaction():
        run_id = conn.execute(
            "INSERT INTO marts.screening_run (label, plan_type, params, n_flags) "
            "VALUES (%s, %s, %s::jsonb, %s) RETURNING run_id",
            (label, params.plan_type, params.to_json(), len(flagged)),
        ).fetchone()[0]
        with (
            conn.cursor() as cur,
            cur.copy(
                "COPY marts.review_flag (run_id, scheme_id, me_date, streak_months, cagr_3y, pct_rank_cagr_3y,"
                " max_drawdown_3y, median_max_drawdown_3y, peers_3y, explanation) FROM STDIN"
            ) as cp,
        ):
            for r in flagged.itertuples(index=False):
                cp.write_row((
                    run_id, int(r.scheme_id), r.me_date.date(), int(r.streak), float(r.cagr_3y),
                    float(r.pct_rank_cagr_3y), r.max_drawdown_3y, float(r.median_max_drawdown_3y),
                    int(r.peers_3y), r.explanation,
                ))  # fmt: skip
    return run_id


def with_params(params: ScreeningParams, **changes) -> ScreeningParams:
    return replace(params, **changes)
