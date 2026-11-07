"""Data-quality framework (FR-A3).

Each check is a SQL SELECT returning the columns of ``core.dq_issue`` that describe an
issue (fingerprint, scheme_id, issue_category, severity, nav_date, observation,
explanation). Results are upserted by ``fingerprint`` so repeated runs never duplicate
issues. Observations are NEVER deleted or altered; the checks only report. Issues that a
later run no longer detects (e.g. a gap that was backfilled) are auto-resolved with a note;
issues a human resolved or marked WONT_FIX are left alone.

CRITICAL issues gate the analytics pipeline (see ``assert_no_critical``).
"""

from __future__ import annotations

import logging
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from fundlens.config import PROJECT_ROOT

log = logging.getLogger(__name__)
DQ_CONFIG_PATH = PROJECT_ROOT / "config" / "dq.toml"

BLOCKING_STATUSES = ("OPEN", "ACKNOWLEDGED")


class CriticalDataQualityError(RuntimeError):
    """Raised when unresolved CRITICAL data-quality issues must stop the pipeline."""


@dataclass(frozen=True, slots=True)
class Check:
    category: str
    sql: str  # may reference %(name)s parameters from dq.toml / _PATTERNS


def load_dq_config(path: Path = DQ_CONFIG_PATH) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


_MARKET_DAY_IDX = """
md AS (
    SELECT cal_date, row_number() OVER (ORDER BY cal_date) AS idx
    FROM core.market_day WHERE is_market_day
)"""

CHECKS: list[Check] = [
    Check(
        "NON_POSITIVE_NAV",
        """
        SELECT 'NON_POSITIVE_NAV:' || f.scheme_id || ':' || f.nav_date AS fingerprint,
               f.scheme_id, 'NON_POSITIVE_NAV' AS issue_category, 'CRITICAL' AS severity,
               f.nav_date,
               jsonb_build_object('nav', f.nav, 'file_id', f.file_id) AS observation,
               'NAV is zero or negative; returns and drawdown cannot be computed from it.'
                   AS explanation
        FROM core.fact_nav f WHERE f.nav <= 0
        """,
    ),
    Check(
        "FUTURE_DATED_NAV",
        """
        SELECT 'FUTURE_DATED_NAV:' || f.scheme_id || ':' || f.nav_date, f.scheme_id,
               'FUTURE_DATED_NAV', 'CRITICAL', f.nav_date,
               jsonb_build_object('nav', f.nav, 'nav_date', f.nav_date, 'today', current_date),
               'NAV is dated in the future, which would leak look-ahead information.'
        FROM core.fact_nav f WHERE f.nav_date > current_date
        """,
    ),
    Check(
        "MISSING_BUSINESS_DAY",
        f"""
        WITH {_MARKET_DAY_IDX},
        obs AS (
            SELECT f.scheme_id, f.nav_date, md.idx
            FROM core.fact_nav f JOIN md ON md.cal_date = f.nav_date
        ), lagged AS (
            SELECT scheme_id, nav_date, idx,
                   lag(nav_date) OVER w AS prev_date, lag(idx) OVER w AS prev_idx
            FROM obs WINDOW w AS (PARTITION BY scheme_id ORDER BY nav_date)
        )
        SELECT 'MISSING_BUSINESS_DAY:' || scheme_id || ':' || prev_date, scheme_id,
               'MISSING_BUSINESS_DAY',
               CASE WHEN idx - prev_idx - 1 >= %(missing_error_gap)s THEN 'ERROR' ELSE 'WARNING' END,
               nav_date,
               jsonb_build_object('last_nav_before_gap', prev_date, 'next_nav_after_gap', nav_date,
                                  'missing_market_days', idx - prev_idx - 1),
               'No NAV for ' || (idx - prev_idx - 1) || ' market day(s) between '
                   || prev_date || ' and ' || nav_date || ' although the scheme published on both.'
        FROM lagged WHERE idx - prev_idx > 1
        """,
    ),
    Check(
        "ABNORMAL_NAV_MOVE",
        """
        WITH l AS (
            SELECT scheme_id, nav_date, nav,
                   lag(nav) OVER w AS prev_nav, lag(nav_date) OVER w AS prev_date
            FROM core.fact_nav WINDOW w AS (PARTITION BY scheme_id ORDER BY nav_date)
        )
        SELECT 'ABNORMAL_NAV_MOVE:' || scheme_id || ':' || nav_date, scheme_id,
               'ABNORMAL_NAV_MOVE',
               CASE WHEN abs(nav / prev_nav - 1) >= %(move_error)s THEN 'ERROR' ELSE 'WARNING' END,
               nav_date,
               jsonb_build_object('prev_date', prev_date, 'prev_nav', prev_nav, 'nav', nav,
                                  'change_pct', round((nav / prev_nav - 1) * 100, 2)),
               'NAV moved ' || round((nav / prev_nav - 1) * 100, 2) || '%% since the previous '
                   || 'observation; this may be a real market move, a corporate action or a data error.'
        FROM l WHERE prev_nav > 0 AND nav > 0 AND abs(nav / prev_nav - 1) >= %(move_warning)s
        """,
    ),
    Check(
        "STALE_NAV",
        f"""
        WITH {_MARKET_DAY_IDX},
        obs AS (
            SELECT f.scheme_id, f.nav_date, f.nav,
                   row_number() OVER (PARTITION BY f.scheme_id ORDER BY f.nav_date) AS rn
            FROM core.fact_nav f JOIN md ON md.cal_date = f.nav_date
        ), runs AS (
            SELECT *, rn - row_number() OVER (PARTITION BY scheme_id, nav ORDER BY nav_date) AS grp
            FROM obs
        ), agg AS (
            SELECT scheme_id, nav, min(nav_date) AS start_d, max(nav_date) AS end_d, count(*) AS n
            FROM runs GROUP BY scheme_id, nav, grp HAVING count(*) >= %(stale_warning)s
        )
        SELECT 'STALE_NAV:' || scheme_id || ':' || start_d, scheme_id, 'STALE_NAV',
               CASE WHEN n >= %(stale_error)s THEN 'ERROR' ELSE 'WARNING' END, end_d,
               jsonb_build_object('nav', nav, 'run_start', start_d, 'run_end', end_d,
                                  'consecutive_observations', n),
               'Identical NAV of ' || nav || ' on ' || n || ' consecutive market days ('
                   || start_d || ' to ' || end_d || ').'
        FROM agg
        """,
    ),
    Check(
        "DUPLICATE_SCHEME_DATE",
        """
        SELECT 'DUPLICATE_SCHEME_DATE:' || d.file_id || ':' || d.line_no, s.scheme_id,
               'DUPLICATE_SCHEME_DATE',
               CASE WHEN d.nav = v.nav THEN 'WARNING' ELSE 'ERROR' END, d.nav_date,
               jsonb_build_object('file_id', d.file_id, 'line_no', d.line_no,
                                  'duplicate_nav', d.nav, 'kept_nav', v.nav),
               'Scheme/date appeared more than once in one source file; ' ||
               CASE WHEN d.nav = v.nav THEN 'values identical, first occurrence kept.'
                    ELSE 'VALUES CONFLICT, first occurrence kept pending review.' END
        FROM staging.nav_parsed d
        JOIN staging.nav_parsed v ON v.file_id = d.file_id AND v.scheme_code = d.scheme_code
                                 AND v.nav_date = d.nav_date AND v.parse_status = 'VALID'
        LEFT JOIN core.dim_scheme s ON s.amfi_code = d.scheme_code
        WHERE d.parse_status = 'DUPLICATE'
        """,
    ),
    Check(
        "NAV_REVISION",
        """
        SELECT 'NAV_REVISION:' || c.scheme_id || ':' || c.nav_date || ':' || c.file_id, c.scheme_id,
               'NAV_REVISION', 'ERROR', c.nav_date,
               jsonb_build_object('existing_nav', c.existing_nav, 'incoming_nav', c.incoming_nav,
                                  'file_id', c.file_id),
               'A later download disagrees with the NAV already stored; the stored value was kept '
               || 'and the difference recorded in core.nav_revision_conflict.'
        FROM core.nav_revision_conflict c
        """,
    ),
    Check(
        "INVALID_SCHEME_ID",
        """
        SELECT 'INVALID_SCHEME_ID:' || p.file_id || ':' || p.line_no, NULL::bigint,
               'INVALID_SCHEME_ID', 'ERROR', p.nav_date,
               jsonb_build_object('file_id', p.file_id, 'line_no', p.line_no,
                                  'scheme_code', p.scheme_code, 'raw_text', left((SELECT n.raw_text FROM raw.nav_line n WHERE n.file_id = p.file_id AND n.line_no = p.line_no), 300)),
               'Scheme code is missing or not numeric: ' || p.reject_reason
        FROM staging.nav_parsed p
        WHERE p.parse_status = 'REJECTED' AND p.reject_reason LIKE %(pat_scheme)s
        """,
    ),
    Check(
        "INVALID_DATE",
        """
        SELECT 'INVALID_DATE:' || p.file_id || ':' || p.line_no, s.scheme_id, 'INVALID_DATE',
               'ERROR', NULL::date,
               jsonb_build_object('file_id', p.file_id, 'line_no', p.line_no,
                                  'date_raw', p.date_raw, 'raw_text', left((SELECT n.raw_text FROM raw.nav_line n WHERE n.file_id = p.file_id AND n.line_no = p.line_no), 300)),
               'Date could not be parsed or is outside the supported calendar: ' || p.reject_reason
        FROM staging.nav_parsed p LEFT JOIN core.dim_scheme s ON s.amfi_code = p.scheme_code
        WHERE p.parse_status = 'REJECTED'
          AND (p.reject_reason LIKE %(pat_date)s OR p.reject_reason LIKE %(pat_date_range)s)
        """,
    ),
    Check(
        "UNEXPECTED_DATA_TYPE",
        """
        SELECT 'UNEXPECTED_DATA_TYPE:' || p.file_id || ':' || p.line_no, s.scheme_id,
               'UNEXPECTED_DATA_TYPE', 'ERROR', p.nav_date,
               jsonb_build_object('file_id', p.file_id, 'line_no', p.line_no, 'nav_raw', p.nav_raw,
                                  'raw_text', left((SELECT n.raw_text FROM raw.nav_line n WHERE n.file_id = p.file_id AND n.line_no = p.line_no), 300)),
               'A field has an unexpected type or the line has the wrong number of fields: '
               || p.reject_reason
        FROM staging.nav_parsed p LEFT JOIN core.dim_scheme s ON s.amfi_code = p.scheme_code
        WHERE p.parse_status = 'REJECTED'
          AND (p.reject_reason LIKE %(pat_nav)s OR p.reject_reason LIKE %(pat_fields)s
               OR p.reject_reason LIKE %(pat_name)s)
        """,
    ),
    Check(
        "INGESTION_REJECT_RATE",
        """
        WITH per_file AS (
            SELECT file_id, count(*) AS total,
                   count(*) FILTER (WHERE parse_status = 'REJECTED') AS rejected
            FROM staging.nav_parsed GROUP BY file_id
        )
        SELECT 'INGESTION_REJECT_RATE:' || p.file_id, NULL::bigint, 'INGESTION_REJECT_RATE',
               'CRITICAL', NULL::date,
               jsonb_build_object('file_id', p.file_id, 'in_scope_lines', p.total,
                                  'rejected', p.rejected,
                                  'rejected_pct', round(100.0 * p.rejected / p.total, 2)),
               'More than ' || (%(reject_critical)s * 100) || '%% of in-scope lines in one source '
               || 'file were rejected, suggesting a source format change.'
        FROM per_file p WHERE p.total > 0 AND p.rejected::numeric / p.total > %(reject_critical)s
        """,
    ),
    Check(
        "LOW_COVERAGE_DAY",
        """
        SELECT 'LOW_COVERAGE_DAY:' || m.cal_date, NULL::bigint, 'LOW_COVERAGE_DAY', 'WARNING',
               m.cal_date,
               jsonb_build_object('n_nav', m.n_nav, 'n_active_schemes', m.n_active,
                                  'coverage', m.coverage),
               'Only ' || round(m.coverage * 100, 1) || '%% of active schemes published a NAV; the '
               || 'day is treated as a non-market day. A partially failed load would look like this.'
        FROM core.market_day m JOIN core.dim_date d USING (cal_date)
        WHERE NOT m.is_market_day AND m.n_nav > 0 AND d.is_weekday
        """,
    ),
    Check(
        "STALE_DATASET",
        """
        SELECT 'STALE_DATASET', NULL::bigint, 'STALE_DATASET',
               CASE WHEN current_date - max(nav_date) >= %(fresh_error)s THEN 'ERROR' ELSE 'WARNING' END,
               max(nav_date),
               jsonb_build_object('latest_nav_date', max(nav_date), 'today', current_date,
                                  'age_days', current_date - max(nav_date)),
               'Latest NAV in the database is ' || (current_date - max(nav_date)) || ' days old.'
        FROM core.fact_nav HAVING current_date - max(nav_date) >= %(fresh_warning)s
        """,
    ),
]


def _params(cfg: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "missing_error_gap": cfg["missing_days"]["error_gap_days"],
        "move_warning": cfg["abnormal_move"]["warning_pct"],
        "move_error": cfg["abnormal_move"]["error_pct"],
        "stale_warning": cfg["stale"]["warning_days"],
        "stale_error": cfg["stale"]["error_days"],
        "fresh_warning": cfg["freshness"]["warning_days"],
        "fresh_error": cfg["freshness"]["error_days"],
        "reject_critical": cfg["reject_rate"]["critical_fraction"],
        "pat_scheme": "%scheme code%",
        "pat_date": "%unparseable date%",
        "pat_date_range": "%calendar range%",
        "pat_nav": "%unparseable NAV%",
        "pat_fields": "%expected % fields%",
        "pat_name": "%scheme name%",
    }


_DETECT_DDL = """
CREATE TEMP TABLE IF NOT EXISTS _dq_detect (
    fingerprint TEXT, scheme_id BIGINT, issue_category TEXT, severity TEXT,
    nav_date DATE, observation JSONB, explanation TEXT
) ON COMMIT DROP
"""

_UPSERT = """
INSERT INTO core.dq_issue (fingerprint, scheme_id, issue_category, severity, nav_date,
                           observation, explanation, run_id)
SELECT DISTINCT ON (fingerprint) fingerprint, scheme_id, issue_category, severity, nav_date,
       observation, explanation, %(run_id)s
FROM _dq_detect ORDER BY fingerprint
ON CONFLICT (fingerprint) DO UPDATE SET
    severity = EXCLUDED.severity, observation = EXCLUDED.observation,
    explanation = EXCLUDED.explanation, nav_date = EXCLUDED.nav_date
WHERE core.dq_issue.resolution_status IN ('OPEN', 'ACKNOWLEDGED')
"""

_AUTO_RESOLVE = """
UPDATE core.dq_issue i
   SET resolution_status = 'RESOLVED', resolved_at = now(),
       resolution_note = 'Auto-resolved: no longer detected by a later DQ run'
 WHERE i.resolution_status = 'OPEN'
   AND i.issue_category = ANY(%(cats)s)
   AND NOT EXISTS (SELECT 1 FROM _dq_detect d WHERE d.fingerprint = i.fingerprint)
"""


def run_checks(
    conn: psycopg.Connection,
    run_id: int | None = None,
    cfg: Mapping[str, Any] | None = None,
    categories: list[str] | None = None,
) -> dict[str, int]:
    """Run the checks, persist issues, return {category: detected_count}."""
    cfg = cfg or load_dq_config()
    params = _params(cfg)
    selected = [c for c in CHECKS if categories is None or c.category in categories]
    counts: dict[str, int] = {}
    with conn.transaction():
        conn.execute(_DETECT_DDL)
        conn.execute("TRUNCATE _dq_detect")
        for check in selected:
            cur = conn.execute(
                f"INSERT INTO _dq_detect {check.sql}",  # noqa: S608 - static SQL, bound params
                params,
            )
            counts[check.category] = cur.rowcount
            log.info("DQ %-24s detected %d", check.category, cur.rowcount)
        conn.execute(_UPSERT, {"run_id": run_id})
        conn.execute(_AUTO_RESOLVE, {"cats": [c.category for c in selected]})
    return counts


def critical_issues(conn: psycopg.Connection) -> list[tuple[int, str, str]]:
    rows = conn.execute(
        "SELECT issue_id, issue_category, explanation FROM core.dq_issue "
        "WHERE severity = 'CRITICAL' AND resolution_status = ANY(%s) ORDER BY issue_id",
        (list(BLOCKING_STATUSES),),
    ).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def assert_no_critical(conn: psycopg.Connection) -> None:
    """Stop the analytics pipeline if any CRITICAL issue is unresolved."""
    crit = critical_issues(conn)
    if crit:
        sample = "; ".join(f"#{i} {cat}" for i, cat, _ in crit[:5])
        raise CriticalDataQualityError(
            f"{len(crit)} unresolved CRITICAL data-quality issue(s) block analytics: {sample}"
        )


def summary(conn: psycopg.Connection) -> list[tuple[str, str, str, int]]:
    return [
        tuple(r)
        for r in conn.execute(
            "SELECT issue_category, severity, resolution_status, count(*) FROM core.dq_issue "
            "GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"
        ).fetchall()
    ]
