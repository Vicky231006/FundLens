"""End-to-end analytics pipeline: DQ gate -> marts -> screening -> backtest -> reports."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg

from fundlens.backtesting.walkforward import BacktestConfig, run_backtest
from fundlens.config import PROJECT_ROOT
from fundlens.ingestion.loader import refresh_calendar_flags
from fundlens.metrics.build import build_marts
from fundlens.reporting import render_refresh_report, render_results_md
from fundlens.screening.engine import (
    ScreeningParams,
    apply_screen,
    default_params,
    flags_only,
    load_metrics,
    save_flags,
)
from fundlens.validation.dq import assert_no_critical, run_checks, summary

log = logging.getLogger(__name__)


def dataset_snapshot(conn: psycopg.Connection) -> dict[str, Any]:
    """Facts that identify exactly which data a result was computed from."""
    files = conn.execute(
        "SELECT file_path, sha256 FROM raw.source_file ORDER BY from_date, file_id"
    ).fetchall()
    fingerprint = hashlib.sha256("\n".join(f"{p}:{h.strip()}" for p, h in files).encode()).hexdigest()
    one = conn.execute(
        "SELECT (SELECT count(*) FROM core.fact_nav), (SELECT min(nav_date) FROM core.fact_nav),"
        " (SELECT max(nav_date) FROM core.fact_nav), (SELECT count(*) FROM core.dim_scheme),"
        " (SELECT max(finished_at) FROM raw.ingestion_run WHERE status = 'SUCCEEDED'),"
        " (SELECT count(*) FROM raw.source_file)"
    ).fetchone()
    by_plan = conn.execute("SELECT plan_type, count(*) FROM core.dim_scheme GROUP BY 1 ORDER BY 1").fetchall()
    return {
        "source_files": one[5],
        "source_files_fingerprint_sha256": fingerprint,
        "nav_rows": one[0],
        "first_nav_date": str(one[1]),
        "last_nav_date": str(one[2]),
        "schemes": one[3],
        "schemes_by_plan": {p: n for p, n in by_plan},
        "last_successful_ingestion": one[4].isoformat() if one[4] else None,
    }


def run_pipeline(
    conn: psycopg.Connection,
    *,
    backtest_plans: tuple[str, ...] = ("DIRECT", "REGULAR"),
    output_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Run everything downstream of ingestion. Raises CriticalDataQualityError on CRITICAL DQ."""
    t0 = time.perf_counter()
    report: dict[str, Any] = {"started_at": datetime.now(UTC).isoformat()}

    refresh_calendar_flags(conn)
    report["dq_detected"] = run_checks(conn)
    report["dq_summary"] = summary(conn)
    assert_no_critical(conn)  # critical issues stop the analytics pipeline here

    report["marts_seconds"] = build_marts(conn)
    report["snapshot"] = dataset_snapshot(conn)

    # Latest flags for the dashboard: default parameters, each plan type.
    base = default_params()
    flag_runs = {}
    for plan in backtest_plans:
        params = ScreeningParams(**{**asdict(base), "plan_type": plan})
        flagged = flags_only(apply_screen(load_metrics(conn, plan), params), params)
        flag_runs[plan] = save_flags(conn, "default", params, flagged)
    report["screening_runs"] = flag_runs

    backtests = {}
    for plan in backtest_plans:
        cfg = BacktestConfig(plan_type=plan)
        result = run_backtest(conn, cfg)
        result["dataset_snapshot"] = report["snapshot"]
        conn.execute(
            "INSERT INTO marts.backtest_run (plan_type, seed, config, dataset, results) "
            "VALUES (%s, %s, %s::jsonb, %s::jsonb, %s::jsonb)",
            (plan, cfg.seed, json.dumps(result["config"]), json.dumps(result["dataset"]),
             json.dumps(result, default=str)),
        )  # fmt: skip
        backtests[plan] = result
        results_dir = output_root / "results"
        results_dir.mkdir(exist_ok=True)
        (results_dir / f"backtest_{plan.lower()}.json").write_text(
            json.dumps(result, indent=2, default=str), encoding="utf-8"
        )
    report["backtests"] = backtests
    report["pipeline_seconds"] = round(time.perf_counter() - t0, 1)

    (output_root / "RESULTS.md").write_text(render_results_md(report), encoding="utf-8")
    (output_root / "results" / "refresh_report.md").write_text(
        render_refresh_report(report), encoding="utf-8"
    )
    return report
