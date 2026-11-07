"""Schema, raw-layer immutability and ingestion idempotency.

The NAV file below is a TEST FIXTURE written by hand (synthetic, values meaningless). It
exists only to exercise the loader; no result in RESULTS.md is derived from it.
"""

from __future__ import annotations

import gzip
import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import psycopg
import pytest

from fundlens.config import load_scope
from fundlens.db import apply_migrations
from fundlens.ingestion.download import DownloadedFile
from fundlens.ingestion.loader import load_file

pytestmark = pytest.mark.integration

FIXTURE = """Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Mid Cap Fund )

Alpha Mutual Fund
100001;Alpha Mid Cap Fund - Growth - Direct Plan;Direct Plan;GROWTH;INF000A00001;;100.00;01-Jan-2024
100001;Alpha Mid Cap Fund - Growth - Direct Plan;Direct Plan;GROWTH;INF000A00001;;101.00;02-Jan-2024
100001;Alpha Mid Cap Fund - Growth - Direct Plan;Direct Plan;GROWTH;INF000A00001;;101.00;02-Jan-2024
100002;Alpha Mid Cap Fund - Growth;;;;;50.00;01-Jan-2024
100002;Alpha Mid Cap Fund - Growth;;;;;N.A.;02-Jan-2024
"""


def make_download(tmp_path: Path, text: str, name: str = "f.txt.gz") -> DownloadedFile:
    body = text.encode("utf-8")
    path = tmp_path / name
    with gzip.open(path, "wb") as fh:
        fh.write(body)
    return DownloadedFile(
        url="test://fixture",
        from_date=date(2024, 1, 1),
        to_date=date(2024, 1, 31),
        retrieved_at=datetime.now(UTC),
        http_status=200,
        path=path,
        sha256=hashlib.sha256(body).hexdigest(),
        byte_size=len(body),
    )


def count(conn: psycopg.Connection, sql: str) -> int:
    return conn.execute(sql).fetchone()[0]


def test_migrations_are_idempotent(db_url):
    assert apply_migrations(url=db_url) == []


def test_expected_tables_exist(conn):
    tables = {
        r[0] + "." + r[1]
        for r in conn.execute(
            "SELECT table_schema, table_name FROM information_schema.tables "
            "WHERE table_schema IN ('raw','staging','core')"
        )
    }
    for expected in [
        "raw.source_file",
        "raw.nav_line",
        "raw.ingestion_run",
        "staging.nav_parsed",
        "core.dim_scheme",
        "core.dim_date",
        "core.fact_nav",
        "core.scheme_mapping",
        "core.dq_issue",
    ]:
        assert expected in tables


def test_load_populates_layers(conn, tmp_path):
    res = load_file(conn, make_download(tmp_path, FIXTURE), load_scope(), None)
    assert not res.skipped_duplicate_file
    assert count(conn, "SELECT count(*) FROM core.fact_nav") == 3
    assert count(conn, "SELECT count(*) FROM core.dim_scheme") == 2
    status = dict(conn.execute("SELECT parse_status, count(*) FROM staging.nav_parsed GROUP BY 1"))
    assert status == {"VALID": 3, "DUPLICATE": 1, "REJECTED": 1}
    assert count(conn, "SELECT count(*) FROM raw.nav_line") == 5
    plans = dict(conn.execute("SELECT amfi_code, plan_type FROM core.dim_scheme"))
    assert plans == {"100001": "DIRECT", "100002": "REGULAR"}


def test_reloading_identical_file_creates_no_duplicates(conn, tmp_path):
    dl = make_download(tmp_path, FIXTURE)
    load_file(conn, dl, load_scope(), None)
    before = {
        t: count(conn, f"SELECT count(*) FROM {t}")
        for t in ["raw.source_file", "raw.nav_line", "staging.nav_parsed", "core.fact_nav"]
    }
    again = load_file(conn, dl, load_scope(), None)
    assert again.skipped_duplicate_file
    after = {t: count(conn, f"SELECT count(*) FROM {t}") for t in before}
    assert before == after


def test_overlapping_file_with_same_values_adds_no_fact_rows(conn, tmp_path):
    load_file(conn, make_download(tmp_path, FIXTURE, "a.txt.gz"), load_scope(), None)
    # A different file (different bytes) re-delivering the same observations.
    overlap = FIXTURE + "\n"  # trailing blank line changes the hash but not the data
    res = load_file(conn, make_download(tmp_path, overlap, "b.txt.gz"), load_scope(), None)
    assert not res.skipped_duplicate_file
    assert res.nav_rows_inserted == 0 and res.nav_conflicts == 0
    assert count(conn, "SELECT count(*) FROM core.fact_nav") == 3
    assert count(conn, "SELECT count(*) FROM raw.source_file") == 2


def test_revised_nav_is_recorded_not_overwritten(conn, tmp_path):
    load_file(conn, make_download(tmp_path, FIXTURE, "a.txt.gz"), load_scope(), None)
    revised = FIXTURE.replace(";101.00;02-Jan-2024\n100001", ";999.00;02-Jan-2024\n100001", 1)
    res = load_file(conn, make_download(tmp_path, revised, "b.txt.gz"), load_scope(), None)
    assert res.nav_conflicts == 1
    stored = conn.execute(
        "SELECT nav FROM core.fact_nav f JOIN core.dim_scheme s USING (scheme_id) "
        "WHERE s.amfi_code='100001' AND nav_date='2024-01-02'"
    ).fetchone()[0]
    assert float(stored) == 101.0
    assert count(conn, "SELECT count(*) FROM core.nav_revision_conflict") == 1


def test_failed_load_rolls_back_completely(conn, tmp_path):
    dl = make_download(tmp_path, FIXTURE)
    dl.path.unlink()  # file vanished -> parse fails after nothing was written
    with pytest.raises(OSError):
        load_file(conn, dl, load_scope(), None)
    assert count(conn, "SELECT count(*) FROM raw.source_file") == 0


def test_raw_layer_is_immutable(conn, tmp_path):
    load_file(conn, make_download(tmp_path, FIXTURE), load_scope(), None)
    for stmt in [
        "UPDATE raw.nav_line SET raw_text = 'x'",
        "DELETE FROM raw.nav_line",
        "TRUNCATE raw.nav_line",
        "UPDATE raw.source_file SET sha256 = repeat('0', 64)",
        "DELETE FROM raw.source_file",
        "TRUNCATE raw.source_file CASCADE",
    ]:
        with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
            conn.execute(stmt)
    assert count(conn, "SELECT count(*) FROM raw.nav_line") == 5


def test_fact_nav_primary_key_prevents_duplicates(conn, tmp_path):
    load_file(conn, make_download(tmp_path, FIXTURE), load_scope(), None)
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            "INSERT INTO core.fact_nav (scheme_id, nav_date, nav, file_id) "
            "SELECT scheme_id, nav_date, nav, file_id FROM core.fact_nav LIMIT 1"
        )
