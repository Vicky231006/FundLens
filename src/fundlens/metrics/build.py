"""Build / refresh the SQL analytical layer (functions, materialised views)."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import psycopg

from fundlens.config import PROJECT_ROOT

log = logging.getLogger(__name__)
MARTS_DIR = PROJECT_ROOT / "sql" / "marts"


def build_marts(conn: psycopg.Connection, marts_dir: Path = MARTS_DIR) -> dict[str, float]:
    """(Re)create every object in sql/marts/*.sql in filename order.

    Files are idempotent (DROP ... IF EXISTS / CREATE OR REPLACE). Returns seconds per file.
    Requires core.market_day to be current (``fundlens refresh-calendar``).
    """
    timings: dict[str, float] = {}
    for path in sorted(marts_dir.glob("*.sql")):
        started = time.perf_counter()
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
        timings[path.name] = round(time.perf_counter() - started, 2)
        log.info("Built %s in %.2fs", path.name, timings[path.name])
    return timings


def refresh_metrics(conn: psycopg.Connection) -> float:
    """Recompute the metric materialised views without dropping them (keeps dependants)."""
    started = time.perf_counter()
    with conn.transaction():
        conn.execute("REFRESH MATERIALIZED VIEW marts.mv_scheme_month_end_nav")
        conn.execute("REFRESH MATERIALIZED VIEW marts.mv_scheme_month_metrics")
    return round(time.perf_counter() - started, 2)
