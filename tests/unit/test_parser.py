from datetime import date
from decimal import Decimal

import pytest

from fundlens.config import load_scope
from fundlens.ingestion.parser import (
    FileStats,
    derive_option,
    derive_plan,
    parse_amfi_date,
    parse_lines,
    parse_nav,
    parse_section_header,
)

SCOPE = load_scope()

SAMPLE = """Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Mid Cap Fund )

Alpha Mutual Fund
100001;Alpha Mid Cap Fund - Growth - Direct Plan;Direct Plan;GROWTH;INF000A00001;;840.79;01-Jan-2024
100001;Alpha Mid Cap Fund - Growth - Direct Plan;Direct Plan;GROWTH;INF000A00001;;835.26;02-Jan-2024
100001;Alpha Mid Cap Fund - Growth - Direct Plan;Direct Plan;GROWTH;INF000A00001;;835.26;02-Jan-2024
100002;Alpha Mid Cap Fund - IDCW - Direct Plan;Direct Plan;IDCW;INF000A00002;;40.00;01-Jan-2024
100003;Alpha Mid Cap Fund - Growth;;;;;120.5;01-Jan-2024
100004;Alpha Mid Cap Fund - Growth - Direct Plan;;;;;N.A.;01-Jan-2024
100005;Alpha Mid Cap Fund - Growth - Direct Plan;;;;;10.0;31-Feb-2024
100006;broken;line

Open Ended Schemes ( Debt Scheme - Liquid Fund )

Beta Mutual Fund
200001;Beta Liquid - Growth - Direct Plan;Direct Plan;GROWTH;;;1000.0;01-Jan-2024

Close Ended Schemes ( Equity Scheme - Mid Cap Fund )

Gamma Mutual Fund
300001;Gamma Closed - Growth - Direct Plan;Direct Plan;GROWTH;;;10.0;01-Jan-2024
"""


def run(text: str = SAMPLE):
    stats = FileStats()
    rows = list(parse_lines(text.splitlines(keepends=True), SCOPE, stats))
    return rows, stats


def test_section_header_equity_categories():
    s = parse_section_header("Open Ended Schemes ( Equity Scheme - Mid Cap Fund )", SCOPE)
    assert s is not None and s.category == "Mid Cap"
    s = parse_section_header("Open Ended Schemes ( Equity Schemes - ELSS- Tax Saver Fund )", SCOPE)
    assert s is not None and s.category == "ELSS"


@pytest.mark.parametrize(
    "header",
    [
        "Open Ended Schemes ( Equity Scheme - Sectoral/ Thematic )",
        "Open Ended Schemes ( Debt Scheme - Liquid Fund )",
        "Open Ended Schemes ( Growth )",
        "Close Ended Schemes ( Equity Scheme - Mid Cap Fund )",
    ],
)
def test_out_of_scope_headers_have_no_category(header):
    s = parse_section_header(header, SCOPE)
    assert s is not None and s.category is None


def test_non_header_returns_none():
    assert parse_section_header("Alpha Mutual Fund", SCOPE) is None


def test_date_and_nav_parsing():
    assert parse_amfi_date("01-Jan-2024") == date(2024, 1, 1)
    assert parse_amfi_date("29-FEB-2024") == date(2024, 2, 29)
    assert parse_amfi_date("31-Feb-2024") is None
    assert parse_amfi_date("2024-01-01") is None
    assert parse_amfi_date("") is None
    assert parse_nav("840.79") == Decimal("840.79")
    assert parse_nav("N.A.") is None
    assert parse_nav("NaN") is None
    assert parse_nav("") is None


def test_plan_and_option_derivation():
    assert derive_plan("Direct Plan", "x") == "DIRECT"
    assert derive_plan("", "Foo Fund - Direct Plan - Growth") == "DIRECT"
    assert derive_plan("Regular Plan", "Foo Direct") == "REGULAR"
    assert derive_plan("", "Foo Fund - Growth") == "REGULAR"
    assert derive_option("GROWTH", "x") == "GROWTH"
    assert derive_option("Growth Option", "x") == "GROWTH"
    assert derive_option("Monthly IDCW", "x") == "IDCW"
    assert derive_option("", "Foo Fund - Growth") == "GROWTH"
    assert derive_option("", "Foo Fund - Dividend Payout") == "IDCW"
    assert derive_option("", "Foo Fund") == "UNKNOWN"


def test_scope_filtering_counts():
    rows, stats = run()
    # Only the Mid Cap open-ended section is in scope; IDCW row is out of scope.
    assert stats.data_lines_total == 10
    assert stats.lines_in_scope == 7
    assert stats.lines_out_of_scope == 3
    assert stats.lines_malformed == 1
    assert {r.category for r in rows} == {"Mid Cap"}


def test_row_statuses_and_amc_tracking():
    rows, _ = run()
    by_line = {r.raw_text.split(";")[0] + r.raw_text.split(";")[-1]: r for r in rows}
    statuses = [r.parse_status for r in rows]
    assert statuses == ["VALID", "VALID", "DUPLICATE", "VALID", "REJECTED", "REJECTED", "REJECTED"]
    assert all(r.amc_name == "Alpha Mutual Fund" for r in rows)
    assert by_line["10000301-Jan-2024"].plan_type == "REGULAR"  # inferred from name
    assert by_line["10000401-Jan-2024"].reject_reason.startswith("unparseable NAV")
    assert "unparseable date" in by_line["10000531-Feb-2024"].reject_reason
    broken = rows[-1]
    assert broken.reject_reason == "expected 8 fields, found 3"


def test_crlf_and_blank_lines_ignored():
    rows, stats = run(SAMPLE.replace("\n", "\r\n"))
    assert stats.lines_in_scope == 7
    assert rows[0].nav == Decimal("840.79")
    assert rows[0].scheme_code == "100001"
