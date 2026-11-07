from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from fundlens.ingestion.download import build_url, chunk_ranges


def test_chunks_cover_range_without_overlap_or_gap():
    ranges = chunk_ranges(date(2024, 1, 1), date(2024, 12, 31), 90)
    assert ranges[0][0] == date(2024, 1, 1)
    assert ranges[-1][1] == date(2024, 12, 31)
    for (_, prev_end), (next_start, _) in zip(ranges, ranges[1:], strict=False):
        assert next_start == prev_end + timedelta(days=1)
    assert all((b - a).days + 1 <= 90 for a, b in ranges)


def test_chunk_grid_is_deterministic():
    assert chunk_ranges(date(2006, 4, 1), date(2007, 1, 1), 90) == chunk_ranges(
        date(2006, 4, 1), date(2007, 1, 1), 90
    )


def test_empty_when_start_after_end():
    assert chunk_ranges(date(2024, 2, 1), date(2024, 1, 1), 90) == []


def test_invalid_chunk_size():
    with pytest.raises(ValueError):
        chunk_ranges(date(2024, 1, 1), date(2024, 2, 1), 0)


def test_url_format_is_locale_independent_english_months():
    url = build_url(date(2024, 1, 1), date(2024, 3, 30))
    assert url.endswith("frmdt=01-Jan-2024&todt=30-Mar-2024")


@given(
    start=st.dates(min_value=date(2006, 4, 1), max_value=date(2030, 1, 1)),
    span=st.integers(min_value=0, max_value=4000),
    size=st.integers(min_value=1, max_value=120),
)
def test_chunking_partition_property(start, span, size):
    end = start + timedelta(days=span)
    ranges = chunk_ranges(start, end, size)
    total_days = sum((b - a).days + 1 for a, b in ranges)
    assert total_days == span + 1
    assert all(a <= b for a, b in ranges)
