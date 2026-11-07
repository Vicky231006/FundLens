"""Parser for AMFI historical NAV files (``DownloadNAVHistoryReport_Po.aspx``).

File structure (semicolon-delimited, CRLF)::

    Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

    Open Ended Schemes ( Equity Scheme - Mid Cap Fund )        <- section header (category)

    Some Mutual Fund                                            <- AMC name line
    119436;Some Fund - Growth - Direct Plan;Direct Plan;GROWTH;INF...;;840.79;01-Jan-2024

There is no category or AMC column, so the parser tracks both as state while streaming.
Pure functions only: no database or network access, so everything here is unit-testable.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from fundlens.config import Scope

COLUMN_HEADER_PREFIX = "Scheme Code;"
EXPECTED_FIELDS = 8
CALENDAR_MIN = date(2006, 1, 1)
CALENDAR_MAX = date(2040, 12, 31)

_SECTION_RE = re.compile(r"^(Open Ended|Close Ended|Interval Fund) Schemes?\s*\((.*)\)\s*$", re.I)
_EQUITY_SUB_RE = re.compile(r"^Equity Schemes?\s*-\s*(.+)$", re.I)
_MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1
    )
}
_DATE_RE = re.compile(r"^(\d{1,2})-([A-Za-z]{3})-(\d{4})$")
_IDCW_WORDS = ("idcw", "dividend", "payout", "reinvest")


@dataclass(frozen=True, slots=True)
class Section:
    kind: str  # "open ended" | "close ended" | "interval fund"
    header: str  # original header line
    category: str | None  # normalised category if the section is in scope, else None


@dataclass(frozen=True, slots=True)
class StagedRow:
    line_no: int
    section_header: str
    amc_name: str | None
    raw_text: str
    scheme_code: str | None
    scheme_name: str | None
    plan_raw: str | None
    option_raw: str | None
    isin_payout: str | None
    isin_reinvest: str | None
    nav_raw: str | None
    date_raw: str | None
    nav: Decimal | None
    nav_date: date | None
    category: str | None
    plan_type: str | None
    option_type: str | None
    parse_status: str  # VALID | REJECTED | DUPLICATE
    reject_reason: str | None


@dataclass(slots=True)
class FileStats:
    lines_total: int = 0
    data_lines_total: int = 0
    lines_in_scope: int = 0
    lines_out_of_scope: int = 0
    lines_malformed: int = 0


def parse_section_header(line: str, scope: Scope) -> Section | None:
    m = _SECTION_RE.match(line.strip())
    if not m:
        return None
    kind, inner = m.group(1).lower(), m.group(2).strip()
    category: str | None = None
    if kind == "open ended":
        sub = _EQUITY_SUB_RE.match(inner)
        if sub:
            key = re.sub(r"\s+", " ", sub.group(1)).strip().lower()
            category = scope.categories.get(key)
    return Section(kind=kind, header=line.strip(), category=category)


def parse_amfi_date(text: str | None) -> date | None:
    if not text:
        return None
    m = _DATE_RE.match(text.strip())
    if not m:
        return None
    month = _MONTHS.get(m.group(2).lower())
    if month is None:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1)))
    except ValueError:
        return None


def parse_nav(text: str | None) -> Decimal | None:
    if text is None or not text.strip():
        return None
    try:
        value = Decimal(text.strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def derive_plan(plan_raw: str | None, name: str | None) -> str:
    """DIRECT / REGULAR. The Plan column is often blank, so fall back to the scheme name.

    A scheme whose plan column and name never mention "direct" is classed REGULAR: Direct
    plans must be labelled as such. This is an inference and is documented in DATA_CARD.md.
    """
    text = (plan_raw or "").lower()
    if "direct" in text:
        return "DIRECT"
    if "regular" in text:
        return "REGULAR"
    return "DIRECT" if "direct" in (name or "").lower() else "REGULAR"


def derive_option(option_raw: str | None, name: str | None) -> str:
    """GROWTH / IDCW / UNKNOWN from the Option column, falling back to the name."""
    for text in ((option_raw or "").lower(), (name or "").lower()):
        if not text:
            continue
        if any(w in text for w in _IDCW_WORDS):
            return "IDCW"
        if "growth" in text:
            return "GROWTH"
    return "UNKNOWN"


def _clean(value: str) -> str | None:
    value = value.strip()
    return value or None


def _stage_line(
    line_no: int, raw_text: str, section: Section, amc: str | None, scope: Scope
) -> tuple[StagedRow | None, bool]:
    """Return (row, malformed). ``row`` is None when the line is out of scope."""
    fields = raw_text.split(";")
    if len(fields) != EXPECTED_FIELDS:
        row = StagedRow(
            line_no,
            section.header,
            amc,
            raw_text,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            section.category,
            None,
            None,
            "REJECTED",
            f"expected {EXPECTED_FIELDS} fields, found {len(fields)}",
        )
        return row, True

    code, name, plan_raw, option_raw, isin_p, isin_r, nav_raw, date_raw = (f.strip() for f in fields)
    plan_type = derive_plan(plan_raw, name)
    option_type = derive_option(option_raw, name)
    if plan_type not in scope.plans or option_type not in scope.options:
        return None, False

    reasons: list[str] = []
    if not code or not code.isdigit():
        reasons.append("missing or non-numeric scheme code")
    if not name:
        reasons.append("missing scheme name")
    nav = parse_nav(nav_raw)
    if nav is None:
        reasons.append(f"unparseable NAV {nav_raw!r}")
    nav_date = parse_amfi_date(date_raw)
    if nav_date is None:
        reasons.append(f"unparseable date {date_raw!r}")
    elif not CALENDAR_MIN <= nav_date <= CALENDAR_MAX:
        reasons.append(f"date {nav_date} outside supported calendar range")

    row = StagedRow(
        line_no,
        section.header,
        amc,
        raw_text,
        code or None,
        name or None,
        _clean(plan_raw),
        _clean(option_raw),
        _clean(isin_p),
        _clean(isin_r),
        nav_raw or None,
        date_raw or None,
        nav,
        nav_date,
        section.category,
        plan_type,
        option_type,
        "REJECTED" if reasons else "VALID",
        "; ".join(reasons) or None,
    )
    return row, False


def parse_lines(lines: Iterable[str], scope: Scope, stats: FileStats) -> Iterator[StagedRow]:
    """Stream a file's lines, yielding staged rows for in-scope data lines only.

    Out-of-scope lines (debt, hybrid, regular-IDCW, ...) are counted but not yielded; they
    remain in the original file preserved on disk. Within one file, a repeated
    (scheme_code, date) is marked DUPLICATE and never loaded.
    """
    section: Section | None = None
    amc: str | None = None
    seen: set[tuple[str, date]] = set()

    for line_no, line in enumerate(lines, start=1):
        stats.lines_total += 1
        text = line.rstrip("\r\n")
        if not text.strip() or text.startswith(COLUMN_HEADER_PREFIX):
            continue
        header = parse_section_header(text, scope)
        if header is not None:
            section, amc = header, None
            continue
        if ";" not in text:
            amc = text.strip()
            continue

        stats.data_lines_total += 1
        if section is None or section.category is None:
            stats.lines_out_of_scope += 1
            continue

        row, malformed = _stage_line(line_no, text, section, amc, scope)
        if row is None:
            stats.lines_out_of_scope += 1
            continue
        stats.lines_in_scope += 1
        if malformed:
            stats.lines_malformed += 1
        if row.parse_status == "VALID" and row.scheme_code and row.nav_date:
            key = (row.scheme_code, row.nav_date)
            if key in seen:
                row = _as_duplicate(row)
            else:
                seen.add(key)
        yield row


def _as_duplicate(row: StagedRow) -> StagedRow:
    from dataclasses import replace

    return replace(
        row,
        parse_status="DUPLICATE",
        reject_reason="repeated (scheme_code, date) within the same file",
    )
