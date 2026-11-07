# FundLens

**Explainable mutual-fund review-flag analytics engine.** FundLens ingests genuine AMFI (India) mutual-fund NAV
history into PostgreSQL, checks its quality, computes performance and risk metrics in SQL, flags funds that meet
configurable review criteria (persistent bottom-quartile 3-year return **and** worse-than-median drawdown), and
evaluates that screen with a leakage-controlled walk-forward backtest against two baselines.

> **This is an analyst-support tool, not an investment recommendation engine.** A flag means "worth a research
> look". It never means buy, sell or hold. FundLens has no clients, accounts, AUM or users and is not
> production-grade or GIPS-compliant.

## Status

See `TODO.md` (outstanding work) and `DEVELOPMENT_LOG.md` (what was run and what passed). Results live in
`RESULTS.md`, generated from the database by `make reproduce`; nothing in it is typed by hand.

## Data and licensing

Data source: AMFI historical NAV download (`portal.amfiindia.com`). AMFI's terms of use restrict use to personal,
non-commercial purposes and prohibit republishing, so **this repository contains no AMFI data**; `data/raw/` is
git-ignored and you download it yourself with the pipeline. Details: `docs/DATA_CARD.md`, `docs/DECISIONS.md` (D-003).

## Setup (Windows / PowerShell)

Prerequisites: Docker Desktop (running), Git, Python >= 3.12 (developed on 3.14).

```powershell
git clone <your-fork-url> fundlens; cd fundlens
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Copy-Item .env.example .env        # then set POSTGRES_PASSWORD and the same password inside DATABASE_URL
docker compose up -d db            # PostgreSQL 16 on localhost:5433
.\make.ps1 migrate                 # create raw / staging / core / marts schemas
.\make.ps1 ingest                  # download AMFI history 2006 -> today (about 1-2 hours first time, ~2.5 GB raw)
.\make.ps1 pipeline                # DQ gate -> metrics -> screening -> backtest -> RESULTS.md
.\make.ps1 test                    # unit + property + database integration tests
```

On Linux/macOS use `make setup db-up migrate ingest pipeline test` (or `make reproduce` for the whole chain).
If `docker compose` fails with `docker-credential-desktop not found`, run it from PowerShell/cmd (Docker Desktop's
helper is on their PATH) or fix your Docker credential-helper PATH.

### Commands

| Command | What it does |
|---|---|
| `fundlens migrate` | Apply numbered SQL migrations (checksummed, append-only) |
| `fundlens ingest [--from D --to D] [--force-refetch]` | Date-chunked, idempotent download + load |
| `fundlens verify-raw` | Re-hash preserved files against the registry |
| `fundlens dq` | Run data-quality checks; exit code 2 if unresolved CRITICAL issues exist |
| `fundlens build-marts` | (Re)build SQL functions and materialised views from `sql/marts` |
| `fundlens pipeline` | DQ gate -> marts -> screening -> backtests -> `RESULTS.md` (exit 2 on CRITICAL DQ) |
| `.\make.ps1 reproduce` / `make reproduce` | migrate + ingest + pipeline: regenerates every reported number |

## Reproducibility

Seeds are fixed (`BacktestConfig.seed`); identical source files (fingerprinted in RESULTS.md) give identical results.
AMFI may revise or extend history, so numbers can legitimately change between downloads; RESULTS.md records the
file-set fingerprint, NAV date range and row counts each result was computed from.

## Layout

```
config/        scope.toml (plans/categories/history), dq.toml (thresholds), screening.toml (methodology, tuning grid)
sql/migrations numbered DDL (raw, staging, core, market-day calendar, screening/backtest tables)
sql/marts      functions (CAGR, XIRR), month-end metrics MV, forward-return MV, dashboard views
sql/adhoc      analyst SQL queries, each opening with the business question
src/fundlens   ingestion/ validation/ metrics/ screening/ backtesting/ + pipeline.py, reporting.py, cli.py
tests/         unit/ property/ integration/ (integration tests create throw-away databases fundlens_test_*)
dashboard/     Power BI build specification + DAX measures (see its README for status)
docs/          BRD, USER_STORIES, DATA_CARD, ARCHITECTURE, DECISIONS, JIRA backlog export
```

## Methodology in one paragraph

At each completed month-end t, metrics use only NAVs dated <= t. A fund is flagged when, for k consecutive
month-ends (default 3), its 3-year CAGR is in the bottom quartile of its (category, plan type) peer group **and** its
3-year max drawdown is worse than the group median. Each flag carries a sentence quoting the triggering figures. The
backtest defines y = forward 12-month return minus the category median forward return, splits the timeline 60/40 with
purging, tunes parameters on training data only, and reports 95% confidence intervals (fund-clustered and block
bootstrap), a bottom-quartile-1-year baseline and a permutation test against random flags. Limitations (survivorship
bias, overlapping windows, current category labels) are disclosed in `RESULTS.md`.
