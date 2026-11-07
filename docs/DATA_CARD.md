# Data Card — AMFI mutual-fund NAV history (FundLens)

Source of truth for **what data FundLens ingests, how it was retrieved, and what it does not cover**.
Every other document that quotes numbers or data scope should link here rather than restate the details.

## 1. Source

- **Provider:** Association of Mutual Funds in India (AMFI) — <https://www.amfiindia.com/>
- **Endpoint used (verified 2026-11-07):** `https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx`
  with query parameters `frmdt` / `todt` formatted `%d-%b-%Y`.
- **Retrieval method:** historical NAV history report, downloaded in **date chunks** and loaded through
  `fundlens.ingestion.download` + `fundlens.ingestion.parser` + `fundlens.ingestion.loader`.

## 2. Retrieval

- **Retrieval date:** 2026-11-07 (per `docs/DECISIONS.md` D-003 / D-004).
- **Date range covered:** `2006-04-01` → present (bounded in code by `CALENDAR_MAX = 2040-12-31`;
  `CALENDAR_MIN = 2006-01-01` for parsing).
- **Chunking:** fixed grid of 90 days per request (`config/scope.toml` `history.chunk_days`);
  105 days was verified to work while 366 days was rejected (HTTP 302) by the source.
- **Politeness / integrity:** 2 s delay between requests, descriptive `User-Agent`
  (`FundLens/0.1 (portfolio research project; personal non-commercial use)`), retries with backoff.
- **Immutability:** original downloads are preserved byte-for-byte as gzip under
  `data/raw/amfi/<year>/amfi_nav_<from>_<to>_<sha256[:12]>.txt.gz`; the SHA-256 recorded is of the
  **uncompressed** original bytes and lives in `raw.source_file`. Files are never overwritten.
  Database triggers reject UPDATE / DELETE / TRUNCATE on raw tables.

## 3. Data dictionary

### 3.1 File naming

```
amfi_nav_<YYYYMMDD_from>_<YYYYMMDD_to>_<sha256[:12]>.txt.gz
```

stored under `data/raw/amfi/<YYYY>/<YYYY>/…` (year foldered by from-date year).

### 3.2 Line format

Semicolon-delimited, CRLF line endings, header row beginning with `Scheme Code;`:

```
Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date
```

- **Fields (8, `EXPECTED_FIELDS`):** `0` scheme code, `1` NAV name, `2` plan, `3` option,
  `4` ISIN (dividend payout / growth), `5` ISIN (dividend reinvestment), `6` net asset value, `7` date.
- **Section headers:** `Open Ended Schemes ( Equity Scheme(s) - X )`, `Close Ended Schemes ( ... )`,
  `Interval Fund Schemes ( ... )`. AMC name lines appear between headers and data lines.
- **Dates:** `DD-Mon-YYYY` (e.g. `01-Jan-2024`).

### 3.3 Normalised fields produced downstream

- `dim_scheme`: AMC, scheme name, plan type (`DIRECT` / `REGULAR`), option type (`GROWTH` / `IDCW` / `UNKNOWN`).
- `fact_nav`: scheme + NAV date + NAV (Decimal), with source provenance and revision-conflict tracking.

## 4. Coverage and scope

- **Plan types in scope:** `DIRECT` and `REGULAR` (`config/scope.toml` `[plan] include`).
  Analytics always compute **within** a plan type and never mix plan types; the analysis default is
  `DIRECT` (per PRD / `screening.toml`).
- **Option types in scope:** `GROWTH` only.
- **Categories in scope:** Large Cap, Large & Mid Cap, Mid Cap, Small Cap, Multi Cap, Flexi Cap, Focused,
  Value, Contra, Dividend Yield, ELSS — mapped from AMFI section-header text via `config/scope.toml`
  `[categories]`. Sectoral/Thematic and legacy `( Growth )` / `( ELSS )` headers are excluded (see D-005).

## 5. Licensing and redistribution

- AMFI's terms of use (retrieved 2026-11-07) permit **personal, non-commercial use only** and prohibit
  publishing, transferring or creating derivative works from the site content.
- **Decision:** nothing from AMFI is redistributed. `data/raw/` and `data/processed/` are git-ignored;
  the repository contains no AMFI NAV data. Published material (RESULTS.md, dashboard screenshots,
  aggregates) contains aggregates only, not NAV series.
- **Not legal advice.**

## 6. Known gaps and limitations

- **History starts 2006-04-01.** Earlier AMFI requests return an HTML error page, not NAV data
  (D-004). Earlier history cannot be analysed.
- **SEBI Direct-plan history is short:** Direct plans existed from 2013-01-01, so pre-2013 history is
  only `REGULAR`; the earliest month-end with a full three-year ranking window is ~2016 (D-004).
- **Survivorship bias:** schemes that closed or merged drop out of later months; historical
  month-end category labels reflect current categorisation, not point-in-time membership (D-005).
- **No holiday calendar:** `core.market_day` treats a date as a market day when ≥50% of active schemes
  published a NAV; days with 0 < coverage < 50% are flagged `LOW_COVERAGE_DAY` (possible partial load);
  days with no coverage look like holidays (D-008).
- **Missing observations:** gaps ≥ `dq.toml` `missing_days.error_gap_days` (5) are ERROR; shorter are
  WARNING. No-flow / insufficient-history periods yield NULL metrics rather than fabricated values.
- **IDCW options** are out of scope (GROWTH only); **Close Ended / Interval Fund / Sectoral** sections are
  out of scope.

## 7. Honest-data rules

FundLens never substitutes fabricated NAVs, synthetic returns or random numbers for real market data
(`PROMPT.md` §3). Any test or report involving numbers must state whether it used real data, injected
faults, or synthetic data.
