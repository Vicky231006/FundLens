"""End-to-end pipeline on a SYNTHETIC TEST FIXTURE (seeded random walks, not market data).

Checks wiring and invariants only: the DQ gate, point-in-time metrics, flag persistence and
report generation. No number from this fixture is ever published as a result.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from fundlens.pipeline import run_pipeline
from fundlens.validation.dq import CriticalDataQualityError

pytestmark = pytest.mark.integration


def weekdays(a: date, b: date):
    return [a + timedelta(days=i) for i in range((b - a).days + 1) if (a + timedelta(days=i)).weekday() < 5]


def load_synthetic(conn, n_funds=14, start=date(2012, 1, 2), end=date(2021, 6, 30), poison=False):
    rng = np.random.default_rng(11)
    days = weekdays(start, end)
    file_id = conn.execute(
        """INSERT INTO raw.source_file (source_url, retrieved_at, from_date, to_date, http_status,
           file_path, sha256, byte_size, lines_total, data_lines_total, lines_in_scope,
           lines_out_of_scope, lines_malformed, scope_config_hash)
           VALUES ('t', now(), %s, %s, 200, 'x', repeat('a', 64), 1, 0, 0, 0, 0, 0, repeat('b', 64))
           RETURNING file_id""",
        (start, end),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO raw.ingestion_run (status, finished_at, requested_from, requested_to) "
        "VALUES ('SUCCEEDED', now(), %s, %s)",
        (start, end),
    )
    for i in range(n_funds):
        navs = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.008 + 0.0004 * i, len(days))))
        sid = conn.execute(
            "INSERT INTO core.dim_scheme (amfi_code, scheme_name, category, category_raw, plan_type,"
            " option_type, first_nav_date, last_nav_date) VALUES (%s, %s, 'Mid Cap', 'x', 'DIRECT',"
            " 'GROWTH', %s, %s) RETURNING scheme_id",
            (str(i + 1), f"F{i}", days[0], days[-1]),
        ).fetchone()[0]
        with (
            conn.cursor() as cur,
            cur.copy("COPY core.fact_nav (scheme_id, nav_date, nav, file_id) FROM STDIN") as cp,
        ):
            for j, (d, v) in enumerate(zip(days, navs, strict=True)):
                nav = -5.0 if (poison and i == 0 and j == 500) else round(float(v), 4)
                cp.write_row((sid, d, nav, file_id))


def test_pipeline_end_to_end(conn, tmp_path):
    load_synthetic(conn)
    report = run_pipeline(conn, backtest_plans=("DIRECT",), output_root=tmp_path)

    results = (tmp_path / "RESULTS.md").read_text(encoding="utf-8")
    assert "not** an investment recommendation" in results
    assert "Survivorship bias" in results
    assert "Baseline 1" in results and "Baseline 2" in results
    assert "95% CI" in results
    assert (tmp_path / "results" / "backtest_direct.json").exists()
    assert (tmp_path / "results" / "refresh_report.md").exists()

    bt = report["backtests"]["DIRECT"]
    d = bt["dataset"]
    assert d["train_month_ends"] + d["test_month_ends"] == d["screenable_month_ends"]
    assert abs(d["train_month_ends"] / d["screenable_month_ends"] - 0.6) < 0.02

    n_flags = conn.execute("SELECT n_flags FROM marts.screening_run").fetchone()[0]
    stored = conn.execute("SELECT count(*) FROM marts.review_flag").fetchone()[0]
    assert n_flags == stored
    if stored:
        expl = conn.execute("SELECT explanation FROM marts.review_flag LIMIT 1").fetchone()[0]
        assert "not an investment recommendation" in expl
    assert conn.execute("SELECT count(*) FROM marts.backtest_run").fetchone()[0] == 1

    # Dashboard read-model reconciles with the stored backtest JSON.
    rows = conn.execute(
        "SELECT method, n_obs, mean_y FROM marts.dash_backtest_summary "
        "WHERE param_set = 'default' AND period = 'test' ORDER BY method"
    ).fetchall()
    methods = {r[0] for r in rows}
    assert {"FundLens screen", "Baseline 1: bottom-quartile 1-year return"} <= methods
    test = bt["periods"]["default"]["test"]
    screen_row = next(r for r in rows if r[0] == "FundLens screen")
    assert screen_row[1] == test["screen"]["n_flag_obs"]
    assert screen_row[2] == pytest.approx(test["ci_fund_cluster_bootstrap"]["screen"]["estimate"])
    info = conn.execute("SELECT last_successful_refresh, disclosure FROM marts.dash_refresh_info").fetchone()
    assert info[0] is not None and "not an investment recommendation" in info[1]


def test_pipeline_is_reproducible_for_the_same_data(conn, tmp_path):
    load_synthetic(conn)
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    out_a.mkdir()
    out_b.mkdir()
    a = run_pipeline(conn, backtest_plans=("DIRECT",), output_root=out_a)
    b = run_pipeline(conn, backtest_plans=("DIRECT",), output_root=out_b)
    assert a["backtests"]["DIRECT"]["periods"] == b["backtests"]["DIRECT"]["periods"]


def test_critical_dq_issue_stops_pipeline_before_any_output(conn, tmp_path):
    load_synthetic(conn, poison=True)
    with pytest.raises(CriticalDataQualityError):
        run_pipeline(conn, backtest_plans=("DIRECT",), output_root=tmp_path)
    assert not (tmp_path / "RESULTS.md").exists()
    assert conn.execute("SELECT count(*) FROM marts.screening_run").fetchone()[0] == 0
