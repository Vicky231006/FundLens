# FundLens

FundLens is a tool that helps **mutual fund research analysts** spot funds that may need a closer look.

It uses real historical NAV (Net Asset Value) data for Indian mutual funds from **AMFI** (Association of Mutual Funds in India). It loads that data into a **PostgreSQL** database, checks data quality, calculates performance and risk numbers in SQL, flags funds that meet clear review rules, and evaluates those rules with a careful backtest. Results can be explored in an interactive **Power BI** dashboard.

> **Important:** FundLens is for **research support only**. A “flag” means *“worth reviewing”* — it **never** means buy, sell, or hold. This is a portfolio/learning project: no real clients, accounts, or AUM, and it is **not** production-grade or GIPS-compliant.

---

## What you can do with it

- **Ingest real data:** Download and load genuine AMFI NAV history (idempotent — safe to re-run without duplicates).
- **Trust the data:** Run data-quality checks (missing days, abnormal moves, stale/invalid values, duplicates, etc.). Critical issues can stop the pipeline so bad data doesn’t flow into results.
- **Measure funds:** Compute rolling returns (e.g., 1Y/3Y/5Y CAGR), volatility, max drawdown, SIP XIRR, and category percentile ranks (in SQL).
- **Flag for review (explainable):** At each month-end, flag a fund when (by default) its **3-year rolling return** is in the **bottom quartile** of its category **and** its **drawdown** is **worse than the category median**, for **k** consecutive month-ends (configurable). Each flag includes the reason/figures.
- **Evaluate honestly:** Walk-forward backtest with no look-ahead, baselines (bottom-quartile 1Y return; random flags/permutation), 60/40 tuning/out-of-sample split, and 95% confidence intervals — with limitations disclosed (e.g., survivorship bias).
- **View in a dashboard:** Power BI report pages for Fund Review, Fund Drilldown, Data Quality, and Backtesting (connects to `marts` views).

---

## Data and licensing (please read)

- **Source:** AMFI historical NAV data (`portal.amfiindia.com`).
- **Not included in this repo:** AMFI’s terms restrict use and redistribution, so **no AMFI data is committed**. `data/raw/` and `data/processed/` are ignored — you download data yourself using the pipeline.
- More detail: `docs/DATA_CARD.md` and `docs/DECISIONS.md` (D-003).

---

## Project status (honest summary)

- Core pipeline, database (raw → staging → core → marts), data quality, metrics, screening, backtesting, tests, docs, and the Power BI **PBIP** report/model are implemented in this repository.
- The dashboard loads from local PostgreSQL (`marts.dash_*`, direct/regular handled as designed; default model wiring uses the filters documented in the semantic model). Your reference checks showed **28 flagged funds** (DIRECT, latest month-end) and **FundLens mean_y ~0.0020 (0.20%)** on the default/test slice — consistent with the current data.
- **Manual step (FR-A7):** the binary `.pbix` is produced by **saving in Power BI Desktop** (File → Save As). If `dashboard/FundLens/FundLens.pbix` exists locally, review it and commit if you want that artifact in the repo. Open `dashboard/FundLens/FundLens.pbip`, refresh against your local DB, then Save As `.pbix`.
- **Reproducibility:** reported numbers should come from `make reproduce` / `RESULTS.md` (generated, not hand-edited). Verify `make reproduce` and CI in your environment before treating all Definition-of-Done items as fully closed.

See `TODO.md`, `DEVELOPMENT_LOG.md`, and `docs/` (BRD, user stories, architecture, decisions, data card).

---

## How to set up and run (Windows / PowerShell)

**You’ll need:** Docker Desktop (running), Git, Python **3.12+**.

```powershell
git clone <your-repo-url> fundlens
cd fundlens

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

Copy-Item .env.example .env
# Edit .env: set POSTGRES_PASSWORD (and make sure DATABASE_URL uses the same password)

docker compose up -d db                 # PostgreSQL 16 (host port from .env, often 5433)
.\make.ps1 migrate                      # create schemas/tables
.\make.ps1 ingest                       # download AMFI history (first run can take 1–2 hours, ~2.5 GB raw)
.\make.ps1 pipeline                     # DQ gate → metrics → screening → backtest → RESULTS.md
.\make.ps1 test                         # unit + property + database integration tests
```

**Linux/macOS:** `make setup db-up migrate ingest pipeline test` (or `make reproduce` for the full chain).

**Common issue:** if `docker compose` fails with `docker-credential-desktop not found`, run from PowerShell/cmd where Docker Desktop’s helper is on PATH.

---

## Useful commands

| Command | What it does |
|---|---|
| `fundlens migrate` | Apply SQL migrations (checksummed, append-only) |
| `fundlens ingest [--from D --to D] [--force-refetch]` | Download + load NAV data (chunked, idempotent) |
| `fundlens verify-raw` | Check preserved raw files against the registry |
| `fundlens dq` | Run data-quality checks (exit code 2 if unresolved CRITICAL issues) |
| `fundlens build-marts` | (Re)build SQL functions and materialized views from `sql/marts` |
| `fundlens pipeline` | DQ gate → marts → screening → backtests → `RESULTS.md` |
| `.\make.ps1 reproduce` / `make reproduce` | `migrate + ingest + pipeline` — regenerates reported numbers |

---

## Dashboard (Power BI)

- Open `dashboard/FundLens/FundLens.pbip` in **Power BI Desktop**.
- The semantic model uses **PostgreSQL**: `localhost`, port from your setup (commonly **5433**), database `fundlens`, reading `marts.dash_*` views. Use credentials from `.env` and **Refresh**.
- Pages: **Fund Review**, **Fund Drilldown**, **Data Quality**, **Backtesting**.
- If Desktop overwrote files or you see connection errors, reopen the PBIP from disk (avoid saving a broken session over it). See `dashboard/README.md` for more.

---

## Repository layout (quick map)

```
config/        Scope, DQ thresholds, screening/backtest settings
sql/migrations Database schema (raw, staging, core, screening/backtest tables)
sql/marts      Metrics functions, month-end/forward-return MVs, dashboard views (dash_*)
sql/adhoc      Analyst SQL queries (each states the business question)
src/fundlens   ingestion / validation / metrics / screening / backtesting + pipeline & CLI
tests/         unit / property / integration
dashboard/     Power BI PBIP report + semantic model
docs/          BRD, user stories, data card, architecture, decisions, JIRA export
```

---

## Methodology (short version)

- Metrics at month-end *t* use only NAVs with date ≤ *t* (no look-ahead in flags).
- **Default flag:** for *k* consecutive month-ends (default 3), 3-year CAGR is in the **bottom quartile** of its (category, plan type) group **and** 3-year max drawdown is **worse than the group median**. Flags are explainable.
- **Backtest:** *y* = forward 12-month return minus category median forward return; 60/40 time split with purging; parameters tuned on training only; 95% CIs (fund-clustered/block bootstrap); baselines = bottom-quartile 1Y and permutation/random flags. Limitations (survivorship bias, overlapping windows, category labeling) are disclosed (see `RESULTS.md` / docs).

---

## Questions or changes

If a number on screen doesn’t match expectations, check: (1) PostgreSQL is running and refreshed, (2) you’re looking at the intended slice (e.g., DIRECT / latest month-end / default test period), and (3) the model loaded without errors. Share the page, visual, and exact error/value if you need help debugging.
