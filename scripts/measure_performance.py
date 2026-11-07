"""Measure query latency with and without indexes and write docs/PERFORMANCE.md.

"Without index" is measured inside a transaction that DROPs the index and is always ROLLED BACK,
so the database is never changed. Every figure is a measured median over repeated runs on the
current database; the dataset size is printed alongside. Nothing is estimated.

Usage:  .venv\\Scripts\\python.exe scripts/measure_performance.py
"""

from __future__ import annotations

import statistics
import time
from datetime import UTC, datetime
from pathlib import Path

import psycopg

from fundlens.db import connect

RUNS = 15
OUT = Path(__file__).resolve().parents[1] / "docs" / "PERFORMANCE.md"


def timed(conn: psycopg.Connection, sql: str, params: tuple = ()) -> float:
    t0 = time.perf_counter()
    conn.execute(sql, params).fetchall()
    return (time.perf_counter() - t0) * 1000


def median_ms(conn: psycopg.Connection, sql: str, params: tuple = ()) -> float:
    conn.execute(sql, params).fetchall()  # warm cache
    return statistics.median(timed(conn, sql, params) for _ in range(RUNS))


def plan_node(conn: psycopg.Connection, sql: str, params: tuple) -> str:
    rows = conn.execute("EXPLAIN " + sql, params).fetchall()
    first = rows[0][0] if rows else ""
    uses = [r[0].strip() for r in rows if "Scan" in r[0]]
    return (uses[0] if uses else first)[:90]


def main() -> None:
    with connect(autocommit=True) as conn:
        sizes = {
            "fact_nav rows": conn.execute("SELECT count(*) FROM core.fact_nav").fetchone()[0],
            "schemes": conn.execute("SELECT count(*) FROM core.dim_scheme").fetchone()[0],
            "month-end metric rows": conn.execute(
                "SELECT count(*) FROM marts.mv_scheme_month_metrics"
            ).fetchone()[0],
            "raw.nav_line rows": conn.execute("SELECT count(*) FROM raw.nav_line").fetchone()[0],
            "dq_issue rows": conn.execute("SELECT count(*) FROM core.dq_issue").fetchone()[0],
        }
        sid = conn.execute(
            "SELECT scheme_id FROM core.dim_scheme WHERE plan_type='DIRECT' "
            "ORDER BY last_nav_date DESC, first_nav_date LIMIT 1"
        ).fetchone()[0]
        me = conn.execute("SELECT max(me_date) FROM marts.mv_scheme_month_metrics").fetchone()[0]
        d = conn.execute("SELECT max(nav_date) FROM core.fact_nav").fetchone()[0]

        cases = [
            (
                "Fund review: one category at the latest month-end",
                "ix_mv_metrics_cat_date",
                "SELECT * FROM marts.mv_scheme_month_metrics WHERE category = 'Mid Cap' "
                "AND plan_type = 'DIRECT' AND me_date = %s",
                (me,),
            ),
            (
                "Fund drilldown: one scheme's month-end series",
                "ux_mv_metrics",
                "SELECT me_date, cagr_3y, max_drawdown_3y FROM marts.mv_scheme_month_metrics "
                "WHERE scheme_id = %s ORDER BY me_date",
                (sid,),
            ),
            (
                "All NAVs published on one date",
                "ix_fact_nav_date",
                "SELECT scheme_id, nav FROM core.fact_nav WHERE nav_date = %s",
                (d,),
            ),
            (
                "Open ERROR/CRITICAL issues",
                "ix_dq_issue_open_severity",
                "SELECT issue_category, count(*) FROM core.dq_issue WHERE resolution_status = 'OPEN' "
                "AND severity IN ('ERROR', 'CRITICAL') GROUP BY 1",
                (),
            ),
            (
                "NAV history of one scheme (primary key)",
                "fact_nav_pkey",
                "SELECT nav_date, nav FROM core.fact_nav WHERE scheme_id = %s ORDER BY nav_date",
                (sid,),
            ),
        ]
        rows = []
        for label, index, sql, params in cases:
            with_idx = median_ms(conn, sql, params)
            plan_with = plan_node(conn, sql, params)
            conn.execute("BEGIN")
            try:
                if index.endswith("_pkey"):
                    conn.execute(f"ALTER TABLE core.fact_nav DROP CONSTRAINT {index} CASCADE")
                else:
                    conn.execute(f"DROP INDEX {'marts.' if 'mv_' in index else 'core.'}{index}")
                without = median_ms(conn, sql, params)
                plan_without = plan_node(conn, sql, params)
            finally:
                conn.execute("ROLLBACK")
            rows.append((label, index, with_idx, without, plan_with, plan_without))

        # Refresh durations are measured by `fundlens build-marts` / pipeline; read the latest runs here.
        mv_t0 = time.perf_counter()
        conn.execute("REFRESH MATERIALIZED VIEW marts.mv_scheme_month_end_nav")
        conn.execute("REFRESH MATERIALIZED VIEW marts.mv_scheme_month_metrics")
        mv_secs = time.perf_counter() - mv_t0
        ing = conn.execute(
            "SELECT started_at, finished_at, files_total, files_new, rows_loaded FROM raw.ingestion_run "
            "WHERE status = 'SUCCEEDED' ORDER BY run_id DESC LIMIT 3"
        ).fetchall()

    lines = [
        "# Performance measurements",
        "",
        f"Measured {datetime.now(UTC):%Y-%m-%d %H:%M UTC} on the developer machine (Docker Desktop PostgreSQL 16, "
        f"single user) by `scripts/measure_performance.py`. Median of {RUN_COUNT} runs after one warm-up. "
        "Absolute times depend on the machine; the with/without ratio is the useful figure.",
        "",
        "## Dataset size used for every figure below",
        "",
        "| Item | Count |",
        "|---|---:|",
        *[f"| {k} | {v:,} |" for k, v in sizes.items()],
        "",
        "## Query latency, with and without the index",
        "",
        '"Without" = index dropped inside a rolled-back transaction (database unchanged).',
        "",
        "| Query | Index | With (ms) | Without (ms) | Slowdown without | Plan with | Plan without |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for label, index, w, wo, pw, pwo in rows:
        lines.append(
            f"| {label} | `{index}` | {w:.2f} | {wo:.2f} | {wo / w:.1f}x | {pw.replace('|', '/')} | {pwo.replace('|', '/')} |"
        )
    lines += [
        "",
        "## Materialised view refresh",
        "",
        f"`REFRESH MATERIALIZED VIEW` of `mv_scheme_month_end_nav` + `mv_scheme_month_metrics`: **{mv_secs:.1f} s** "
        f"({sizes['month-end metric rows']:,} output rows).",
        "",
        "## Ingestion runs (most recent successful)",
        "",
        "| Started | Finished | Files fetched | New files | NAV rows loaded |",
        "|---|---|---:|---:|---:|",
        *[f"| {a:%Y-%m-%d %H:%M} | {b:%Y-%m-%d %H:%M} | {c} | {e} | {f:,} |" for a, b, c, e, f in ing],
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


RUN_COUNT = RUNS

if __name__ == "__main__":
    main()
