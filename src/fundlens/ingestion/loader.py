"""Idempotent loading: raw -> staging -> core, one transaction per source file."""

from __future__ import annotations

import gzip
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from time import sleep

import psycopg

from fundlens.config import PROJECT_ROOT, Scope, load_scope, raw_data_dir
from fundlens.db import connect
from fundlens.ingestion.download import (
    POLITE_DELAY_SECONDS,
    DownloadedFile,
    DownloadError,
    chunk_ranges,
    fetch_chunk,
    sha256_of_gz,
)
from fundlens.ingestion.parser import FileStats, StagedRow, parse_lines

log = logging.getLogger(__name__)
# Chunks that ended more than this many days ago and are already loaded are not re-fetched.
REFETCH_WINDOW_DAYS = 45


@dataclass(slots=True)
class LoadResult:
    file_id: int | None
    skipped_duplicate_file: bool
    stats: FileStats
    nav_rows_inserted: int = 0
    nav_conflicts: int = 0


def _registry_path(path: Path) -> str:
    """Store paths relative to the project root so the registry is machine-independent."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _read_lines(path: Path):
    with gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="") as fh:
        yield from fh


def _staging_tuple(file_id: int, r: StagedRow) -> tuple:
    return (
        file_id,
        r.line_no,
        r.section_header,
        r.amc_name,
        r.scheme_code,
        r.scheme_name,
        r.plan_raw,
        r.option_raw,
        r.isin_payout,
        r.isin_reinvest,
        r.nav_raw,
        r.date_raw,
        r.nav,
        r.nav_date,
        r.category,
        r.plan_type,
        r.option_type,
        r.parse_status,
        r.reject_reason,
    )


_STAGING_COLS = (
    "file_id, line_no, section_header, amc_name, scheme_code, scheme_name, plan_raw, option_raw, "
    "isin_payout, isin_reinvest, nav_raw, date_raw, nav, nav_date, category, plan_type, "
    "option_type, parse_status, reject_reason"
)

_UPSERT_SCHEME_SQL = """
WITH latest AS (
    SELECT DISTINCT ON (scheme_code)
           scheme_code, scheme_name, amc_name, category, section_header, plan_type, option_type,
           isin_payout, nav_date
    FROM staging.nav_parsed
    WHERE file_id = %(f)s AND parse_status = 'VALID'
    ORDER BY scheme_code, nav_date DESC
), span AS (
    SELECT scheme_code, min(nav_date) AS first_d, max(nav_date) AS last_d
    FROM staging.nav_parsed WHERE file_id = %(f)s AND parse_status = 'VALID'
    GROUP BY scheme_code
)
INSERT INTO core.dim_scheme (amfi_code, scheme_name, amc_name, category, category_raw,
                             plan_type, option_type, isin, first_nav_date, last_nav_date)
SELECT l.scheme_code, l.scheme_name, l.amc_name, l.category, l.section_header, l.plan_type,
       l.option_type, l.isin_payout, s.first_d, s.last_d
FROM latest l JOIN span s USING (scheme_code)
ON CONFLICT (amfi_code) DO UPDATE SET
    scheme_name = CASE WHEN EXCLUDED.last_nav_date >= core.dim_scheme.last_nav_date
                       THEN EXCLUDED.scheme_name ELSE core.dim_scheme.scheme_name END,
    amc_name = CASE WHEN EXCLUDED.last_nav_date >= core.dim_scheme.last_nav_date
                    THEN EXCLUDED.amc_name ELSE core.dim_scheme.amc_name END,
    category = CASE WHEN EXCLUDED.last_nav_date >= core.dim_scheme.last_nav_date
                    THEN EXCLUDED.category ELSE core.dim_scheme.category END,
    category_raw = CASE WHEN EXCLUDED.last_nav_date >= core.dim_scheme.last_nav_date
                        THEN EXCLUDED.category_raw ELSE core.dim_scheme.category_raw END,
    isin = COALESCE(EXCLUDED.isin, core.dim_scheme.isin),
    first_nav_date = LEAST(core.dim_scheme.first_nav_date, EXCLUDED.first_nav_date),
    last_nav_date = GREATEST(core.dim_scheme.last_nav_date, EXCLUDED.last_nav_date),
    updated_at = now()
"""

_NAME_HISTORY_SQL = """
INSERT INTO core.scheme_name_history (scheme_id, scheme_name, first_seen, last_seen)
SELECT s.scheme_id, p.scheme_name, min(p.nav_date), max(p.nav_date)
FROM staging.nav_parsed p JOIN core.dim_scheme s ON s.amfi_code = p.scheme_code
WHERE p.file_id = %(f)s AND p.parse_status = 'VALID'
GROUP BY s.scheme_id, p.scheme_name
ON CONFLICT (scheme_id, scheme_name) DO UPDATE SET
    first_seen = LEAST(core.scheme_name_history.first_seen, EXCLUDED.first_seen),
    last_seen = GREATEST(core.scheme_name_history.last_seen, EXCLUDED.last_seen)
"""

_FACT_SQL = """
INSERT INTO core.fact_nav (scheme_id, nav_date, nav, file_id)
SELECT s.scheme_id, p.nav_date, p.nav, p.file_id
FROM staging.nav_parsed p JOIN core.dim_scheme s ON s.amfi_code = p.scheme_code
WHERE p.file_id = %(f)s AND p.parse_status = 'VALID'
ON CONFLICT (scheme_id, nav_date) DO NOTHING
"""

_CONFLICT_SQL = """
INSERT INTO core.nav_revision_conflict (scheme_id, nav_date, existing_nav, incoming_nav, file_id)
SELECT f.scheme_id, f.nav_date, f.nav, p.nav, p.file_id
FROM staging.nav_parsed p
JOIN core.dim_scheme s ON s.amfi_code = p.scheme_code
JOIN core.fact_nav f ON f.scheme_id = s.scheme_id AND f.nav_date = p.nav_date
WHERE p.file_id = %(f)s AND p.parse_status = 'VALID' AND f.nav <> p.nav
ON CONFLICT DO NOTHING
"""


def load_file(conn: psycopg.Connection, dl: DownloadedFile, scope: Scope, run_id: int | None) -> LoadResult:
    """Register + load one downloaded file atomically. Re-loading identical content is a no-op."""
    with conn.transaction():
        existing = conn.execute(
            "SELECT file_id FROM raw.source_file WHERE sha256 = %s", (dl.sha256,)
        ).fetchone()
        if existing:
            log.info("Already loaded (sha256 %s): %s", dl.sha256[:12], dl.path.name)
            return LoadResult(existing[0], True, FileStats())

        stats = FileStats()
        rows = list(parse_lines(_read_lines(dl.path), scope, stats))
        file_id = conn.execute(
            """INSERT INTO raw.source_file
               (run_id, source_url, retrieved_at, from_date, to_date, http_status, file_path,
                sha256, byte_size, lines_total, data_lines_total, lines_in_scope,
                lines_out_of_scope, lines_malformed, scope_config_hash)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING file_id""",
            (
                run_id,
                dl.url,
                dl.retrieved_at,
                dl.from_date,
                dl.to_date,
                dl.http_status,
                _registry_path(dl.path),
                dl.sha256,
                dl.byte_size,
                stats.lines_total,
                stats.data_lines_total,
                stats.lines_in_scope,
                stats.lines_out_of_scope,
                stats.lines_malformed,
                scope.config_hash,
            ),
        ).fetchone()[0]

        with conn.cursor() as cur:
            with cur.copy(
                "COPY raw.nav_line (file_id, line_no, section_header, amc_name, raw_text) FROM STDIN"
            ) as cp:
                for r in rows:
                    cp.write_row((file_id, r.line_no, r.section_header, r.amc_name, r.raw_text))
            with cur.copy(f"COPY staging.nav_parsed ({_STAGING_COLS}) FROM STDIN") as cp:
                for r in rows:
                    cp.write_row(_staging_tuple(file_id, r))

            cur.execute(_UPSERT_SCHEME_SQL, {"f": file_id})
            cur.execute(_NAME_HISTORY_SQL, {"f": file_id})
            cur.execute(_FACT_SQL, {"f": file_id})
            inserted = cur.rowcount
            cur.execute(_CONFLICT_SQL, {"f": file_id})
            conflicts = cur.rowcount

    log.info(
        "Loaded %s: %d in-scope lines, %d NAV rows inserted, %d conflicts",
        dl.path.name,
        stats.lines_in_scope,
        inserted,
        conflicts,
    )
    return LoadResult(file_id, False, stats, inserted, conflicts)


def _already_loaded(conn: psycopg.Connection, start: date, end: date) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM raw.source_file WHERE from_date = %s AND to_date = %s LIMIT 1",
            (start, end),
        ).fetchone()
        is not None
    )


def refresh_calendar_flags(conn: psycopg.Connection) -> None:
    """Rebuild core.market_day (data-derived business-day calendar) and dim_date flags."""
    with conn.transaction():
        conn.execute("SELECT core.refresh_market_day()")


def ingest_range(
    start: date | None = None,
    end: date | None = None,
    *,
    force_refetch: bool = False,
    scope: Scope | None = None,
) -> dict[str, int]:
    """Download (date-chunked) and load [start, end]. Safe to re-run: identical files are
    skipped by SHA-256 and NAV rows are unique on (scheme_id, nav_date)."""
    scope = scope or load_scope()
    start = max(start or scope.start_date, scope.start_date)
    end = end or date.today()
    root = raw_data_dir()
    totals = {"chunks": 0, "downloaded": 0, "files_new": 0, "nav_rows": 0, "conflicts": 0}

    # autocommit: every load_file() transaction block is then a real, independently
    # committed transaction, so an interrupted run keeps all fully-loaded files.
    with connect(autocommit=True) as conn:
        conn.execute(
            "UPDATE raw.ingestion_run SET status='FAILED', finished_at=now(), "
            "error_message='abandoned: process ended before completion' WHERE status='RUNNING'"
        )
        run_id = conn.execute(
            "INSERT INTO raw.ingestion_run (requested_from, requested_to) VALUES (%s, %s) RETURNING run_id",
            (start, end),
        ).fetchone()[0]
        conn.commit()
        try:
            for c_from, c_to in chunk_ranges(start, end, scope.chunk_days):
                totals["chunks"] += 1
                settled = c_to < date.today() - timedelta(days=REFETCH_WINDOW_DAYS)
                if settled and not force_refetch and _already_loaded(conn, c_from, c_to):
                    log.info("Skip settled chunk %s..%s (already loaded)", c_from, c_to)
                    continue
                dl = fetch_chunk(c_from, c_to, root)
                totals["downloaded"] += 1
                res = load_file(conn, dl, scope, run_id)
                if not res.skipped_duplicate_file:
                    totals["files_new"] += 1
                    totals["nav_rows"] += res.nav_rows_inserted
                    totals["conflicts"] += res.nav_conflicts
                sleep(POLITE_DELAY_SECONDS)
            refresh_calendar_flags(conn)
            conn.execute(
                "UPDATE raw.ingestion_run SET status='SUCCEEDED', finished_at=now(), "
                "files_total=%s, files_new=%s, rows_loaded=%s WHERE run_id=%s",
                (totals["downloaded"], totals["files_new"], totals["nav_rows"], run_id),
            )
            conn.commit()
        except (DownloadError, psycopg.Error, OSError) as exc:
            conn.rollback()
            conn.execute(
                "UPDATE raw.ingestion_run SET status='FAILED', finished_at=now(), "
                "error_message=%s WHERE run_id=%s",
                (str(exc)[:2000], run_id),
            )
            conn.commit()
            raise
    return totals


def verify_raw_files(conn: psycopg.Connection) -> list[str]:
    """Re-hash preserved files and report any that no longer match the registered SHA-256."""
    problems = []
    for file_id, path, sha in conn.execute(
        "SELECT file_id, file_path, sha256 FROM raw.source_file ORDER BY file_id"
    ).fetchall():
        p = Path(path) if Path(path).is_absolute() else PROJECT_ROOT / path
        if not p.exists():
            problems.append(f"file {file_id}: missing {path}")
        elif sha256_of_gz(p) != sha.strip():
            problems.append(f"file {file_id}: checksum mismatch {path}")
    return problems
