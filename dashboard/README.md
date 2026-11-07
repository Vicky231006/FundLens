# FundLens Power BI dashboard (FR-A7)

> **Status: specification and data model are ready and tested; the `.pbix` file has NOT been built.**
> An AI coding agent cannot operate Power BI Desktop's GUI, and hand-writing `.pbip`/PBIR internals without
> being able to open them risks shipping a file that does not load. What *is* verified: every `marts.dash_*`
> view exists, runs, and reconciles with the stored backtest JSON (`tests/integration/test_pipeline.py`).
> Building the four pages below in Desktop takes roughly 45-60 minutes. Until then FR-A7 is **not complete**.

## Why Power BI

Windows machine, Power BI Desktop (Microsoft Store) already installed, free, native PostgreSQL connector,
no extra server. See `docs/DECISIONS.md` D-012.

## Licensing note

The dashboard shows per-fund NAV-derived series. AMFI's terms restrict redistribution (`docs/DATA_CARD.md`),
so the `.pbix` must be **run against your own database**; do not publish it to the public web or commit it with
imported data. Screenshots should show aggregates only. Remove cached data before sharing a file.

## Connect

1. `.\make.ps1 db-up; .\make.ps1 pipeline` so the `marts.dash_*` views contain data.
2. Power BI Desktop -> Get data -> PostgreSQL database. Server `localhost:5433`, database `fundlens`,
   Data Connectivity mode **Import**. Credentials: `POSTGRES_USER` / `POSTGRES_PASSWORD` from your local `.env`.
3. Import these views (schema `marts`) and nothing else:

| View | Grain | Used on page |
|---|---|---|
| `dash_refresh_info` | 1 row | every page (last refresh + disclosure) |
| `dash_flag` | flag per fund per month-end (latest default run per plan type) | A Review, B Drilldown |
| `dash_fund_month` | fund x month-end metrics + `is_flagged` | B Drilldown |
| `dash_dq_issue` | one row per DQ issue | C Data quality |
| `dash_dq_by_category` | issue category x severity x status | C Data quality |
| `dash_backtest_summary` | run x param set x period x method | D Backtesting |
| `dash_backtest_dataset` | run | D Backtesting |

4. Model: relate `dash_flag[scheme_id]` and `dash_dq_issue[scheme_id]` to a distinct `dash_fund_month[scheme_id]`
   dimension (create a `Fund` table in DAX: `Fund = DISTINCT(SELECTCOLUMNS(dash_fund_month, "scheme_id", [scheme_id], "scheme_name", [scheme_name], "category", [category], "plan_type", [plan_type]))`).
   Create a `MonthEnd` table: `MonthEnd = DISTINCT(dash_fund_month[me_date])` related to `dash_flag[me_date]` and
   `dash_fund_month[me_date]`.
5. **Plan type slicer on every page, single-select, default `DIRECT`.** Never show DIRECT and REGULAR peers together.

## Measures (also in `dashboard/measures.dax`)

See `measures.dax`. Every percentage shown must come from the views (no re-derivation in DAX), so the dashboard
can be reconciled against SQL.

## Pages

### Every page: header strip
Card `Last successful refresh` (`dash_refresh_info[last_successful_refresh]`), card `Latest NAV date`, and a text box
bound to `dash_refresh_info[disclosure]`. Title text: "Research-review flags - not investment recommendations".

### A. Fund review
- Slicers: plan type (single), category (multi), month-end (single, default latest complete month-end: use
  `is_latest_month_end = TRUE` default, otherwise dropdown from `MonthEnd`).
- Table (from `dash_flag`): scheme name, AMC, category, streak months, 3y CAGR, 3y percentile rank, 3y max drawdown,
  category median drawdown, peers, 1y CAGR, volatility, SIP XIRR, **explanation** (trigger reason).
- Card: number of flagged funds; bar: flags by category.
- CSV export: table visual -> "..." -> Export data (enable in Options -> Report settings, or use "Analyze in Excel").
  Also available without Power BI: `psql \copy (select * from marts.dash_flag where is_latest_month_end) to 'flags.csv' csv header`.

### B. Fund drilldown
- Fund slicer (search). Line charts over `dash_fund_month[me_date]` for the selected fund: NAV; 1y/3y/5y CAGR; 1y
  volatility; 3y max drawdown, each with the category median (`median_cagr_3y`, `median_max_drawdown_3y`) as a second line.
- Historical flag timeline: column chart of `is_flagged` (0/1) by month-end, plus table of flag months with explanation.
- Category comparison: scatter of 3y CAGR (x) vs 3y max drawdown (y) for all funds in the fund's category at the chosen month-end.

### C. Data quality
- Cards: open issues, open CRITICAL, open ERROR; table of `dash_dq_by_category` (category, severity, status, issues, schemes).
- Bar: issues by category colored by severity; bar: top 15 affected schemes (count of `dash_dq_issue` by scheme).
- Donut: resolution status. Detail table with `explanation`, `nav_date`, `observation`.
- Card: `Last successful ingestion` (`dash_refresh_info[last_successful_refresh]`).

### D. Backtesting
- Slicers: plan type, parameter set (`default` / `tuned`), period (`test` default; `train` shown as selection-optimistic).
- Clustered bar with error bars of `mean_y` by `method` using `ci_lower_fund_cluster` / `ci_upper_fund_cluster`
  (shows the screen, Baseline 1, Baseline 2 and all-eligible).
- Table: method, flagged observations, mean y, both CIs, interpretation.
- Dataset size and evaluation period cards from `dash_backtest_dataset` (schemes, scheme-month rows, test start, first/last month-end).
- Methodology text box (copy from `docs/ARCHITECTURE.md` section 1 and `RESULTS.md`) and **Limitations** text box
  (copy from the "Limitations and disclosures" section of `RESULTS.md`): survivorship bias, overlapping windows,
  short OOS window, current category labels.

## Reconciliation checks (run after building)
- Flag count on page A equals `SELECT count(*) FROM marts.dash_flag WHERE plan_type='DIRECT' AND me_date='<date>'`.
- Backtest table equals `RESULTS.md` (generated from the same run).
- Open issue counts equal `SELECT severity, count(*) FROM core.dq_issue WHERE resolution_status IN ('OPEN','ACKNOWLEDGED') GROUP BY 1`.
