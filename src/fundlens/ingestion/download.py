"""Date-chunked download of AMFI historical NAV files, preserving every original file."""

from __future__ import annotations

import gzip
import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import requests

log = logging.getLogger(__name__)

BASE_URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx"
USER_AGENT = "FundLens/0.1 (portfolio research project; personal non-commercial use)"
HEADER_PREFIX = b"Scheme Code;NAV Name"
POLITE_DELAY_SECONDS = 2.0


class DownloadError(RuntimeError):
    """The source returned something that is not a NAV history file."""


@dataclass(frozen=True, slots=True)
class DownloadedFile:
    url: str
    from_date: date
    to_date: date
    retrieved_at: datetime
    http_status: int
    path: Path
    sha256: str
    byte_size: int


def chunk_ranges(start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    """Deterministic, non-overlapping grid anchored at ``start`` (so re-runs request
    identical URLs and historical chunks hash identically)."""
    if chunk_days < 1:
        raise ValueError("chunk_days must be >= 1")
    ranges: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        stop = min(cursor + timedelta(days=chunk_days - 1), end)
        ranges.append((cursor, stop))
        cursor = stop + timedelta(days=1)
    return ranges


def build_url(from_date: date, to_date: date) -> str:
    fmt = "%d-%b-%Y"
    return f"{BASE_URL}?frmdt={from_date.strftime(fmt)}&todt={to_date.strftime(fmt)}"


def raw_path(root: Path, from_date: date, to_date: date, sha256: str) -> Path:
    name = f"amfi_nav_{from_date:%Y%m%d}_{to_date:%Y%m%d}_{sha256[:12]}.txt.gz"
    return root / "amfi" / f"{from_date:%Y}" / name


def fetch_chunk(
    from_date: date, to_date: date, raw_root: Path, *, retries: int = 4, timeout: int = 300
) -> DownloadedFile:
    """Download one range. The original bytes are stored gzip-compressed (lossless); the
    SHA-256 is of the *uncompressed original* bytes. Existing files are never overwritten."""
    url = build_url(from_date, to_date)
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=False
            )
            retrieved_at = datetime.now(UTC)
            if resp.status_code != 200:
                raise DownloadError(
                    f"HTTP {resp.status_code} for {url} (a 3xx usually means the date range is "
                    "too long or the endpoint changed)"
                )
            body = resp.content
            if not body.startswith(HEADER_PREFIX):
                raise DownloadError(
                    f"Response for {url} is not a NAV history file (starts {body[:60]!r}). "
                    "AMFI returns an HTML page for ranges before 2006-04-01."
                )
            digest = hashlib.sha256(body).hexdigest()
            path = raw_path(raw_root, from_date, to_date, digest)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                with gzip.open(tmp, "wb", compresslevel=6) as fh:
                    fh.write(body)
                tmp.replace(path)
            return DownloadedFile(url, from_date, to_date, retrieved_at, 200, path, digest, len(body))
        except (requests.RequestException, DownloadError) as exc:
            last_error = exc
            log.warning("Attempt %d/%d failed for %s..%s: %s", attempt, retries, from_date, to_date, exc)
            if attempt < retries:
                time.sleep(5 * attempt)
    raise DownloadError(f"Giving up on {from_date}..{to_date}: {last_error}")


def sha256_of_gz(path: Path) -> str:
    h = hashlib.sha256()
    with gzip.open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()
