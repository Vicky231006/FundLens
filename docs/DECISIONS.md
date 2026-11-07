# Architectural decision log

Format: **context -> decision -> alternatives -> consequences**. Newest entries last. Decisions that
deviate from `PROMPT.md` are marked **[DEVIATION]** and need the owner's acknowledgement.

## D-001 Python 3.14 via `uv`, code compatible with >= 3.12
- **Context.** The PRD says Python 3.12; the owner then asked for "the latest Python version".
  `winget install Python.Python.3.14` was cancelled by the Windows installer (exit 1602, UAC).
- **Decision.** Install CPython 3.14.10 in user space with `uv` and use it for `.venv`. `pyproject.toml`
  keeps `requires-python >= 3.12` and CI runs 3.14.
- **Alternatives.** Stay on the installed 3.13.7; retry the MSI with admin rights.
- **Consequences.** All dependencies (pandas 3, numpy 2.5, SQLAlchemy 2.1, psycopg 3.3, scipy 1.18)
  installed and passed tests on 3.14. `uv` is only a bootstrap tool; plain `python -m venv` also works.

## D-002 Task runner: Makefile plus `make.ps1`
- **Context.** `make reproduce` is mandated; GNU make is not installed on the Windows machine and the
  Chocolatey/winget installers need elevation.
- **Decision.** A `Makefile` (used on Linux/CI and anywhere GNU make exists) and a PowerShell script
  `make.ps1` with identical targets. `.\make.ps1 reproduce` == `make reproduce`.
- **Alternatives.** Install make (needs admin); `just`/`invoke` (new dependency).

## D-003 Data licensing: nothing from AMFI is redistributed
- **Context.** AMFI's terms of use (https://www.amfiindia.com/terms-of-use, retrieved 2026-11-07) allow
  "personal and non-commercial use only" and prohibit publishing, transferring or creating derivative
  works from site content and storing "any significant portion" of it. The NAV download is a site
  feature; no separate data licence was found. Public accessibility is not a redistribution right.
- **Decision.** `data/raw/` and `data/processed/` are git-ignored; the repo contains no NAV data or
  per-fund series; users run the ingestion themselves. CI artifacts contain only aggregate outputs.
  Published material (RESULTS.md, dashboard screenshots) contains aggregates, not NAV series.
  A request pattern of one request per ~2 s with a descriptive User-Agent keeps load low.
- **Consequences.** A public hosted dashboard with per-fund NAV charts is NOT appropriate without
  AMFI's written permission; the Power BI file is meant to be run against the user's own database.
  The owner has approved this approach (conversation, 2026-11-07). Not legal advice.

## D-004 Scope: Direct and Regular Growth, analysed within plan type; history from 2006-04-01 [DEVIATION]
- **Context.** The PRD asks for Direct, Growth equity funds. The owner asked for history "till 2000".
  Verified 2026-11-07: AMFI's endpoint returns data only from **2006-04-01**; earlier requests return
  an HTML error page. SEBI introduced Direct plans on **2013-01-01**, so Direct-only history is <= ~13 years
  and the first 3-year rank exists only from 2016.
- **Decision.** Ingest Direct and Regular Growth plans from 2006-04-01. Never mix plan types in a peer
  group. The PRD's Direct specification is the **primary** analysis; Regular (2006+) is a clearly
  labelled sensitivity analysis that gives the backtest much more history.
- **Alternatives.** Direct only (short test window); Regular only (not the PRD's scope).
- **Consequences.** The earliest possible data is 2006 (not 2000) and this is documented in DATA_CARD.
  Two Direct-named schemes (Quantum) pre-date 2013 because that AMC historically sold without a
  distributor; they are kept as published.

## D-005 Category scope and normalisation
- **Decision.** Only `Open Ended Schemes ( Equity Scheme(s) - X )` sections are in scope, with X in the list in
  `config/scope.toml` (Large Cap, Large & Mid Cap, Mid Cap, Small Cap, Multi Cap, Flexi Cap, Focused, Value,
  Contra, Dividend Yield, ELSS). Sectoral/Thematic is excluded (not comparable peers). Legacy
  headers such as `( Growth )` / `( ELSS )` are excluded: they mostly hold schemes AMFI never re-categorised
  (largely closed or merged), and assigning them a category from the name would be guesswork.
- **Observed fact.** AMFI re-labels historical rows with a scheme's *current* category (e.g. 2010 data
  appears under "Equity Scheme - Sectoral/ Thematic"), so one scheme code has one category for all dates.
- **Consequences.** Survivorship bias (see DATA_CARD) and no point-in-time category membership.

## D-006 Scheme identity and mapping (FR-A2)
- **Decision.** `core.dim_scheme` is keyed by the AMFI scheme code, which identifies one share class
  (plan + option) and is stable across renames. Names are never used to merge schemes.
  `core.scheme_name_history` records every observed name. `core.scheme_mapping` holds RENAME / MERGE /
  SPLIT / REPLACED_BY relationships with mandatory evidence text and `CANDIDATE | CONFIRMED | REJECTED` status;
  nothing is auto-confirmed.

## D-007 Raw layer
- **Decision.** Every original download is preserved byte-for-byte as gzip (`data/raw/amfi/<year>/...txt.gz`; SHA-256 is
  of the *uncompressed original*, stored in `raw.source_file`, verified by `fundlens verify-raw`). In-scope lines are
  also stored verbatim in `raw.nav_line`. Out-of-scope lines (debt, hybrid, ...) remain only in the file on disk.
  Database triggers reject UPDATE/DELETE/TRUNCATE on the raw tables. Files are never overwritten.
- **Idempotency.** The file hash is unique; `fact_nav` is unique on `(scheme_id, nav_date)` with
  `ON CONFLICT DO NOTHING`. A later download that disagrees with a stored NAV is recorded in
  `core.nav_revision_conflict` (and surfaces as a DQ ERROR); the stored value is not silently replaced.

## D-008 Business-day calendar derived from the data
- **Context.** AMFI publishes no holiday calendar and "missing business day" needs one.
- **Decision.** `core.market_day`: a date is a market day when >= 50% of schemes active on that date published a
  NAV. Days with 0 < coverage < 50% are reported as `LOW_COVERAGE_DAY` (possible partial load). Month-end = last
  market day of the month; the in-progress month is excluded from analytics.
- **Consequences.** A day on which *no* scheme published looks like a holiday - documented limitation.

## D-009 Metric conventions (FR-A4)
- Day count actual/365 for CAGR and XIRR (so a two-cash-flow XIRR equals CAGR, and XIRR matches Excel).
- Volatility = sample std-dev of daily log returns x sqrt(252), 1-year window, using only returns between
  consecutive market days. Max drawdown over a trailing 3-year window of daily NAVs.
- CAGR anchor = last NAV on/before (t - N years) within 5 calendar days, else NULL.
- Volatility/drawdown windows need >= 95% of market days present, else NULL. SIP XIRR = 36 monthly instalments of 10,000
  on the 36 month-ends before t, redeemed at t, all 37 dates needing an exact month-end NAV, else NULL.
- Percentile rank = `percent_rank()` within (month-end, category, plan type); 0 = worst, 1 = best.
- **Why a materialised view:** each metric needs a window over up to 3 years of daily NAVs per scheme per month-end;
  rebuild after each ingestion, dashboards read the result. XIRR is a PL/pgSQL Newton/bisection function; an
  independent SciPy implementation and Microsoft's documented XIRR example are used to test it.

## D-010 Screening implemented in Python, persisted to SQL
- **Decision.** Persistence logic (k consecutive month-ends) and parameter grids are pure pandas functions
  (`fundlens.screening.engine`), results persisted to `marts.review_flag` with an explanation string.
- **Alternatives.** Pure SQL views. Rejected because the backtest evaluates hundreds of parameter sets and
  needs fast, unit-testable logic; the dashboard still reads persisted rows through SQL views.

## D-011 Backtest protocol (FR-A6)
- 60/40 split over the *screenable* timeline; training labels purged if their 12-month window ends on/after the first
  test month; tuning grid on training data only; **both default and tuned parameters reported on the test set**.
- Baseline 1 = bottom-quartile 1-year return; Baseline 2 = random flags with identical per-(month, category) counts
  (permutation test).
- 95% CIs: fund-clustered bootstrap (primary, preserves within-fund overlap dependence) and a circular
  month-block bootstrap (sensitivity; captures common shocks). Neither is claimed to remove all dependence.
- The wording of conclusions is rule-based: "inconclusive" unless the CI excludes zero AND the permutation test agrees,
  and even then results are labelled survivorship-biased evidence, not proof of predictive ability.

## D-012 BI platform: Power BI Desktop
- **Context.** Windows machine; Power BI Desktop (Store version) is installed; free; native PostgreSQL connector;
  no Tableau installation.
- **Decision.** Power BI, connected to the `marts.dash_*` views only. See `dashboard/README.md` for what has and has not
  been verified (an AI agent cannot open the Desktop GUI).

## D-013 Hosting for the scheduled monthly refresh
- GitHub Actions runners are ephemeral, so the scheduled job needs a **hosted PostgreSQL** reachable over TLS
  (e.g. Neon, Supabase, or Azure Database for PostgreSQL free/low tiers) with the connection string in the
  `DATABASE_URL` repository secret. The first run against an empty hosted database downloads the full history
  (~1 hour); later runs fetch only the unsettled recent chunks. See `docs/ARCHITECTURE.md`.

## D-014 Local PostgreSQL host port 5433
- Port 5432 showed a lingering connection on the development machine; Compose maps container 5432 to host
  **5433** (override with `POSTGRES_PORT`).
