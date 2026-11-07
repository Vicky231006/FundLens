"""SQL metrics vs independent Python references.

Data are a deterministic SYNTHETIC TEST FIXTURE (seeded random walks on a weekday calendar).
Nothing here is real market data and nothing in RESULTS.md derives from it; its only job is
to check that the SQL views implement the documented formulas.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from fundlens.metrics.build import build_marts
from fundlens.metrics.reference import (
    annualised_volatility,
    cagr,
    max_drawdown,
    percent_rank,
    xirr,
)

pytestmark = pytest.mark.integration

START, END = date(2015, 1, 1), date(2021, 12, 31)
CODES = ["1", "2", "3", "4", "5", "6"]


def weekday_range(a: date, b: date) -> list[date]:
    return [a + timedelta(days=i) for i in range((b - a).days + 1) if (a + timedelta(days=i)).weekday() < 5]


@pytest.fixture()
def series() -> dict[str, dict[date, float]]:
    rng = np.random.default_rng(20240607)
    days = weekday_range(START, END)
    out = {}
    for i, code in enumerate(CODES):
        steps = rng.normal(0.0003 + 0.00005 * i, 0.009 + 0.001 * i, len(days))
        navs = 100.0 * np.exp(np.cumsum(steps))
        out[code] = {d: round(float(v), 4) for d, v in zip(days, navs, strict=True)}
    return out


@pytest.fixture()
def loaded(conn, series):
    file_id = conn.execute(
        """INSERT INTO raw.source_file (source_url, retrieved_at, from_date, to_date, http_status,
           file_path, sha256, byte_size, lines_total, data_lines_total, lines_in_scope,
           lines_out_of_scope, lines_malformed, scope_config_hash)
           VALUES ('test', now(), '2015-01-01', '2021-12-31', 200, 'x', repeat('a', 64), 1, 0, 0, 0, 0, 0,
                   repeat('b', 64)) RETURNING file_id"""
    ).fetchone()[0]
    ids = {}
    for code, navs in series.items():
        sid = conn.execute(
            "INSERT INTO core.dim_scheme (amfi_code, scheme_name, category, category_raw, plan_type,"
            " option_type, first_nav_date, last_nav_date) VALUES (%s, %s, 'Mid Cap', 'x', 'DIRECT',"
            " 'GROWTH', %s, %s) RETURNING scheme_id",
            (code, f"S{code}", min(navs), max(navs)),
        ).fetchone()[0]
        ids[code] = sid
        with (
            conn.cursor() as cur,
            cur.copy("COPY core.fact_nav (scheme_id, nav_date, nav, file_id) FROM STDIN") as cp,
        ):
            for d, v in navs.items():
                cp.write_row((sid, d, v, file_id))
    conn.execute("SELECT core.refresh_market_day()")
    build_marts(conn)
    return ids


def month_ends(days: list[date]) -> list[date]:
    by_month: dict[tuple[int, int], date] = {}
    for d in days:
        by_month[(d.year, d.month)] = d
    return sorted(by_month.values())


def asof(navs: dict[date, float], target: date, tol: int = 5):
    cands = [d for d in navs if target - timedelta(days=tol) <= d <= target]
    if not cands:
        return None
    d = max(cands)
    return d, navs[d]


def minus_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # 29 Feb
        return d.replace(year=d.year - years, day=28)


def metrics_row(conn, sid, me):
    cols = (
        "cagr_1y, cagr_3y, cagr_5y, volatility_1y, max_drawdown_3y, sip_xirr_3y,"
        " pct_rank_cagr_3y, peers_3y, nav"
    )
    row = conn.execute(
        f"SELECT {cols} FROM marts.mv_scheme_month_metrics WHERE scheme_id=%s AND me_date=%s", (sid, me)
    ).fetchone()
    return None if row is None else tuple(None if v is None else float(v) for v in row)


def test_month_ends_are_complete_months_only(conn, loaded, series):
    me = [r[0] for r in conn.execute("SELECT me_date FROM marts.v_month_end ORDER BY 1")]
    expected = month_ends(weekday_range(START, END))[:-1]  # December 2021 is the in-progress month
    assert me == expected


@pytest.mark.parametrize("me", [date(2020, 6, 30), date(2019, 12, 31), date(2021, 11, 30)])
def test_metrics_match_independent_reference(conn, loaded, series, me):
    for code in CODES:
        navs = series[code]
        row = metrics_row(conn, loaded[code], me)
        assert row is not None
        c1, c3, c5, vol, dd, sip, _, _, nav = row
        assert nav == pytest.approx(navs[me])

        for years, got in ((1, c1), (3, c3), (5, c5)):
            a = asof(navs, minus_years(me, years))
            want = cagr(a[1], a[0], navs[me], me) if a else None
            assert got == pytest.approx(want, rel=1e-9, abs=1e-12) if want is not None else got is None

        ds = sorted(d for d in navs if d <= me)
        # volatility: returns for dates in (me-1y, me], base = last day on/before me-1y
        base = max(d for d in ds if d <= minus_years(me, 1))
        vol_navs = [navs[d] for d in ds if d >= base]
        assert vol == pytest.approx(annualised_volatility(vol_navs), rel=1e-9)

        # drawdown over [me-3y, me]
        dd_navs = [navs[d] for d in ds if d >= minus_years(me, 3)]
        assert dd == pytest.approx(max_drawdown(dd_navs), abs=1e-9)

        # standardised SIP: 36 month-ends before me, 10000 each, redeem at me
        mes = [d for d in month_ends(ds) if d < me][-36:]
        if len(mes) == 36 and sip is not None:
            units = sum(10000.0 / navs[d] for d in mes)
            want_sip = xirr([*mes, me], [-10000.0] * 36 + [units * navs[me]])
            assert sip == pytest.approx(want_sip, abs=1e-7)


def test_percentile_rank_matches_reference(conn, loaded, series):
    me = date(2020, 6, 30)
    c3 = {code: metrics_row(conn, loaded[code], me)[1] for code in CODES}
    want = percent_rank([c3[c] for c in CODES])
    got = [metrics_row(conn, loaded[c], me)[6] for c in CODES]
    assert got == pytest.approx(want, abs=1e-12)
    assert all(metrics_row(conn, loaded[c], me)[7] == 6.0 for c in CODES)


def test_insufficient_history_gives_null_not_a_number(conn, loaded):
    early = date(2015, 12, 31)  # < 3y history, 1y available only just
    row = metrics_row(conn, loaded["1"], early)
    c1, c3, c5, vol, dd, sip = row[:6]
    assert c3 is None and c5 is None and dd is None and sip is None
    mid = metrics_row(conn, loaded["1"], date(2017, 6, 30))
    assert mid[2] is None  # 5y CAGR needs 5 years


def test_gap_withholds_volatility_when_window_below_95pct_complete(conn, series):
    # Remove ~30 weekdays from scheme 1 in the year before 2020-06-30.
    gap = set(weekday_range(date(2020, 1, 6), date(2020, 2, 14)))
    series["1"] = {d: v for d, v in series["1"].items() if d not in gap}
    file_id = conn.execute(
        """INSERT INTO raw.source_file (source_url, retrieved_at, from_date, to_date, http_status,
           file_path, sha256, byte_size, lines_total, data_lines_total, lines_in_scope,
           lines_out_of_scope, lines_malformed, scope_config_hash)
           VALUES ('t', now(), '2015-01-01', '2021-12-31', 200, 'x', repeat('a', 64), 1, 0, 0, 0, 0, 0,
                   repeat('b', 64)) RETURNING file_id"""
    ).fetchone()[0]
    ids = {}
    for code in ("1", "2", "3"):
        navs = series[code]
        ids[code] = conn.execute(
            "INSERT INTO core.dim_scheme (amfi_code, scheme_name, category, category_raw, plan_type,"
            " option_type, first_nav_date, last_nav_date) VALUES (%s, 'S', 'Mid Cap', 'x', 'DIRECT',"
            " 'GROWTH', %s, %s) RETURNING scheme_id",
            (code, min(navs), max(navs)),
        ).fetchone()[0]
        with (
            conn.cursor() as cur,
            cur.copy("COPY core.fact_nav (scheme_id, nav_date, nav, file_id) FROM STDIN") as cp,
        ):
            for d, v in navs.items():
                cp.write_row((ids[code], d, v, file_id))
    conn.execute("SELECT core.refresh_market_day()")
    build_marts(conn)
    me = date(2020, 6, 30)
    gappy = metrics_row(conn, ids["1"], me)
    clean = metrics_row(conn, ids["2"], me)
    # 30 missing days = ~11% of the 1y window (vol withheld, needs >=95%) but only ~4% of the
    # 3y window (drawdown still computed, within the documented 95% completeness rule).
    assert gappy[3] is None
    assert gappy[4] is not None
    assert gappy[0] is not None and gappy[1] is not None  # endpoint-based CAGR still defined
    assert clean[3] is not None and clean[4] is not None
