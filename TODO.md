# TODO — FundLens outstanding work

Living list of unfinished work. Update this file as the project progresses; the authoritative
requirements live in `PROMPT.md` (§8 functional requirements FR-A1…FR-A9, §17 final definition of done).

## Data and source

- [ ] **FR-A7 dashboard: build the Power BI `.pbix` file.** Status: specification, data model and
      `marts.dash_*` view reconciliation checks are done and tested; an AI agent authored the report
      definition via Microsoft's official Power BI authoring CLI (`powerbi-report-author`, PBIP/PBIR):
      scaffold + four pages (Fund Review, Fund Drilldown, Data Quality, Backtesting) authored at
      `dashboard/FundLens/FundLens.pbip` and validated clean (0 errors, 1 benign schema-fetch warning).
      The binary `.pbix` has not yet been produced (the authoring toolkit cannot Save As; it drives
      Desktop only via open/reload/screenshot bridge). Owner action: open `dashboard/FundLens/FundLens.pbip`
      in Power BI Desktop, bind the semantic model to the local DB, save as `.pbix`, finish page build,
      save locally (run against own DB; no AMFI data committed). Until built, FR-A7 is incomplete.

- [x] **Resolve the CRITICAL data-quality blockers that stopped the analytics pipeline.**
      Done (2026-11-07): all 252 CRITICAL `NON_POSITIVE_NAV` findings dispositioned (resolved with explanatory
      note; raw layer immutable, nothing silently deleted); re-ran `fundlens pipeline` to completion
      (238.9 s) → `RESULTS.md` + `results/` generated; critical DQ gate passed.

## Results and evidence

- [x] **Generate `RESULTS.md`** by running the full chain on real ingested data:
      `.\make.ps1 reproduce` (db-up → migrate → ingest → pipeline).
      Now generated (2026-11-07): `RESULTS.md` + `results/backtest_{direct,regular}.json` +
      `results/refresh_report.md` from a completed pipeline run (runtime 238.9 s). Content:
      DIRECT OOS default/tuned and REGULAR OOS default/tuned backtests with bootstrap CIs and
      permutation tests; interpretation honestly reported as inconclusive where CIs include zero.
- [x] **Generate `docs/PERFORMANCE.md`** via `scripts/measure_performance.py` (measured 2026-11-07:
      88,300 month-end metric rows; index latency measured with/without via rolled-back transaction).

## Operations and delivery

- [ ] **Hosted PostgreSQL for scheduled monthly refresh** (see `docs/DECISIONS.md` D-013). GitHub Actions
      runners are ephemeral; a reachable hosted Postgres (Neon / Supabase / Azure) with the `DATABASE_URL`
      repository secret is required before the monthly refresh can run for real.
- [ ] **JIRA Cloud project** for FundLens. `docs/JIRA_BACKLOG.md` and `docs/jira_backlog.csv` are generated
      backlog exports; actual JIRA Cloud creation is still outstanding (documented limitation in the export).

## Quality and verification

- [ ] **Final project review / interview-defensibility pass** (PROMPT.md §17): walk the definition-of-done
      checklist end to end and close anything still open.

## Done

- [x] Phases 0–9 implementation order followed (see `docs/ARCHITECTURE.md` and `docs/BRD.md`).
- [x] FR-A1…FR-A6, FR-A8, FR-A9 implemented and covered by unit / property / integration tests.
- [x] FR-A7 design and view-level verification complete; agent-authored PBIP at `dashboard/FundLens/`
      validated (0 errors); binary `.pbix` build pending owner action (above).
- [x] Data source, retrieval method and licensing documented in `docs/DATA_CARD.md`.
- [x] Architectural decisions recorded in `docs/DECISIONS.md` (D-001…D-014).
- [x] Continuous integration workflow added (`.github/workflows/ci.yml`).
- [x] Monthly-refresh workflow skeleton added (`.github/workflows/monthly_refresh.yml`).
- [x] Full analytics pipeline run to completion on real ingested data (2026-11-07); critical DQ gate
      dispositioned and passed; `RESULTS.md`, backtest JSONs and refresh report generated.
