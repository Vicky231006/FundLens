"""Data-quality checks against hand-built (synthetic TEST FIXTURE) NAV series."""

from __future__ import annotations

from datetime import date, timedelta

import psycopg
import pytest

from fundlens.config import load_scope
from fundlens.ingestion.loader import load_file
from fundlens.validation.dq import (
    CriticalDataQualityError,
    assert_no_critical,
    run_checks,
)
from tests.integration.test_schema_and_ingestion import FIXTURE, make_download

pytestmark = pytest.mark.integration

START = date(2024, 1, 1)  # a Monday


def weekdays(n: int) -> list[date]:
    out, d = [], START
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


@pytest.fixture()
def file_id(conn):
    return conn.execute(
        """INSERT INTO raw.source_file (source_url, retrieved_at, from_date, to_date, http_status,
           file_path, sha256, byte_size, lines_total, data_lines_total, lines_in_scope,
           lines_out_of_scope, lines_malformed, scope_config_hash)
           VALUES ('test', now(), '2024-01-01', '2024-03-01', 200, 'x', repeat('a', 64), 1, 0, 0, 0, 0, 0,
                   repeat('b', 64)) RETURNING file_id"""
    ).fetchone()[0]


def add_scheme(conn, code: str) -> int:
    return conn.execute(
        "INSERT INTO core.dim_scheme (amfi_code, scheme_name, category, category_raw, plan_type,"
        " option_type) VALUES (%s, %s, 'Mid Cap', 'x', 'DIRECT', 'GROWTH') RETURNING scheme_id",
        (code, f"Scheme {code}"),
    ).fetchone()[0]


def add_navs(conn, scheme_id: int, file_id: int, series: dict[date, float]) -> None:
    for d, nav in series.items():
        conn.execute(
            "INSERT INTO core.fact_nav (scheme_id, nav_date, nav, file_id) VALUES (%s,%s,%s,%s)",
            (scheme_id, d, nav, file_id),
        )
    conn.execute(
        "UPDATE core.dim_scheme SET first_nav_date = (SELECT min(nav_date) FROM core.fact_nav WHERE scheme_id=%s),"
        " last_nav_date = (SELECT max(nav_date) FROM core.fact_nav WHERE scheme_id=%s) WHERE scheme_id=%s",
        (scheme_id, scheme_id, scheme_id),
    )


def smooth(days: list[date], start_nav: float = 100.0) -> dict[date, float]:
    return {d: start_nav + i * 0.1 for i, d in enumerate(days)}


def issues(conn, category: str):
    return conn.execute(
        "SELECT severity, nav_date, resolution_status FROM core.dq_issue "
        "WHERE issue_category = %s ORDER BY nav_date",
        (category,),
    ).fetchall()


def prepare(conn, file_id, series_by_code: dict[str, dict[date, float]]) -> dict[str, int]:
    ids = {}
    for code, series in series_by_code.items():
        ids[code] = add_scheme(conn, code)
        add_navs(conn, ids[code], file_id, series)
    conn.execute("SELECT core.refresh_market_day()")
    return ids


def test_clean_data_has_no_issues_except_staleness(conn, file_id):
    days = weekdays(30)
    prepare(conn, file_id, {"1": smooth(days), "2": smooth(days)})
    run_checks(conn)
    cats = {r[0] for r in conn.execute("SELECT DISTINCT issue_category FROM core.dq_issue")}
    assert cats <= {"STALE_DATASET"}  # fixture dates are in the past


def test_non_positive_nav_is_critical_and_blocks_pipeline(conn, file_id):
    days = weekdays(20)
    series = smooth(days)
    series[days[5]] = 0.0
    series[days[6]] = -3.0
    ids = prepare(conn, file_id, {"1": series, "2": smooth(days)})
    run_checks(conn)
    found = issues(conn, "NON_POSITIVE_NAV")
    assert [r[0] for r in found] == ["CRITICAL", "CRITICAL"]
    with pytest.raises(CriticalDataQualityError):
        assert_no_critical(conn)
    # the questionable observations are NOT deleted
    n = conn.execute("SELECT count(*) FROM core.fact_nav WHERE scheme_id=%s", (ids["1"],)).fetchone()[0]
    assert n == 20
    # resolving (by a human) lifts the block
    conn.execute(
        "UPDATE core.dq_issue SET resolution_status='WONT_FIX', resolved_at=now() "
        "WHERE issue_category='NON_POSITIVE_NAV'"
    )
    assert_no_critical(conn)


def test_missing_business_day_detected_with_gap_severity(conn, file_id):
    days = weekdays(30)
    one_gap = {d: v for d, v in smooth(days).items() if d != days[10]}
    big_gap = {d: v for d, v in smooth(days).items() if d not in days[15:21]}  # 6 missing days
    prepare(conn, file_id, {"1": one_gap, "2": big_gap, "3": smooth(days), "4": smooth(days)})
    run_checks(conn)
    rows = conn.execute(
        "SELECT s.amfi_code, i.severity, (i.observation->>'missing_market_days')::int "
        "FROM core.dq_issue i JOIN core.dim_scheme s USING (scheme_id) "
        "WHERE issue_category='MISSING_BUSINESS_DAY' ORDER BY 1"
    ).fetchall()
    assert rows == [("1", "WARNING", 1), ("2", "ERROR", 6)]


def test_abnormal_move_thresholds(conn, file_id):
    days = weekdays(20)
    series = smooth(days)
    base = series[days[4]]
    series[days[5]] = base * 1.20  # +20% -> WARNING (>=15%)
    series[days[6]] = series[days[5]] * 0.60  # -40% -> ERROR (>=30%)
    for d in days[7:]:
        series[d] = series[days[6]] + 0.1
    prepare(conn, file_id, {"1": series, "2": smooth(days)})
    run_checks(conn)
    got = [(r[1], r[0]) for r in issues(conn, "ABNORMAL_NAV_MOVE")]
    assert got[:2] == [(days[5], "WARNING"), (days[6], "ERROR")]


def test_stale_nav_runs(conn, file_id):
    days = weekdays(30)
    s1 = smooth(days)
    for d in days[3:9]:  # 6 identical values -> WARNING
        s1[d] = 50.0
    s2 = smooth(days)
    for d in days[12:23]:  # 11 identical values -> ERROR
        s2[d] = 70.0
    prepare(conn, file_id, {"1": s1, "2": s2, "3": smooth(days)})
    run_checks(conn)
    assert sorted(r[0] for r in issues(conn, "STALE_NAV")) == ["ERROR", "WARNING"]


def test_running_checks_twice_is_idempotent(conn, file_id):
    days = weekdays(20)
    series = smooth(days)
    series[days[5]] = 0.0
    prepare(conn, file_id, {"1": series, "2": smooth(days)})
    run_checks(conn)
    first = conn.execute("SELECT count(*) FROM core.dq_issue").fetchone()[0]
    run_checks(conn)
    assert conn.execute("SELECT count(*) FROM core.dq_issue").fetchone()[0] == first


def test_backfilled_gap_is_auto_resolved(conn, file_id):
    days = weekdays(30)
    gap_series = {d: v for d, v in smooth(days).items() if d != days[10]}
    ids = prepare(conn, file_id, {"1": gap_series, "2": smooth(days), "3": smooth(days)})
    run_checks(conn)
    assert [r[2] for r in issues(conn, "MISSING_BUSINESS_DAY")] == ["OPEN"]
    add_navs(conn, ids["1"], file_id, {days[10]: 101.0})
    run_checks(conn)
    assert [r[2] for r in issues(conn, "MISSING_BUSINESS_DAY")] == ["RESOLVED"]


def test_human_resolution_is_not_reopened(conn, file_id):
    days = weekdays(30)
    gap_series = {d: v for d, v in smooth(days).items() if d != days[10]}
    prepare(conn, file_id, {"1": gap_series, "2": smooth(days), "3": smooth(days)})
    run_checks(conn)
    conn.execute(
        "UPDATE core.dq_issue SET resolution_status='WONT_FIX', resolution_note='holiday' "
        "WHERE issue_category='MISSING_BUSINESS_DAY'"
    )
    run_checks(conn)
    assert [r[2] for r in issues(conn, "MISSING_BUSINESS_DAY")] == ["WONT_FIX"]


def test_every_issue_has_required_fields(conn, file_id):
    days = weekdays(20)
    series = smooth(days)
    series[days[5]] = -1.0
    prepare(conn, file_id, {"1": series, "2": smooth(days)})
    run_checks(conn)
    rows = conn.execute(
        "SELECT issue_id, issue_category, detected_at, severity, observation, explanation,"
        " resolution_status FROM core.dq_issue"
    ).fetchall()
    assert rows
    for row in rows:
        assert all(v is not None and v != "" for v in row)


def test_staging_rejections_become_issues(conn, tmp_path):
    bad = (
        FIXTURE
        + "100003;Alpha Mid Cap Growth Direct;Direct Plan;GROWTH;;;12.5;31-Feb-2024\n"
        + "abc;Alpha Mid Cap Growth Direct;Direct Plan;GROWTH;;;12.5;02-Jan-2024\n"
        + "100005;too;few;fields\n"
    )
    load_file(conn, make_download(tmp_path, bad), load_scope(), None)
    run_checks(conn)
    assert len(issues(conn, "DUPLICATE_SCHEME_DATE")) == 1
    assert len(issues(conn, "INVALID_DATE")) == 1
    assert len(issues(conn, "INVALID_SCHEME_ID")) == 1
    # "N.A." NAV and the 4-field line are both unexpected data types / shapes
    assert len(issues(conn, "UNEXPECTED_DATA_TYPE")) == 2


def test_mass_rejection_is_critical(conn, tmp_path):
    lines = "\n".join(f"{i};x;Direct Plan;GROWTH;;;oops;01-Jan-2024" for i in range(1, 30))
    text = (
        "Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;"
        "Net Asset Value;Date\n\nOpen Ended Schemes ( Equity Scheme - Mid Cap Fund )\n\nA MF\n" + lines
    )
    load_file(conn, make_download(tmp_path, text), load_scope(), None)
    run_checks(conn)
    assert [r[0] for r in issues(conn, "INGESTION_REJECT_RATE")] == ["CRITICAL"]
    with pytest.raises(CriticalDataQualityError):
        assert_no_critical(conn)


def test_issue_table_rejects_bad_severity(conn):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO core.dq_issue (fingerprint, issue_category, severity, observation, explanation)"
            " VALUES ('x', 'X', 'SEVERE', '{}', 'x')"
        )
