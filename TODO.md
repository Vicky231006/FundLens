# TODO — FundLens outstanding work

Living list of unfinished work. Update this file as the project progresses; the authoritative
requirements live in `PROMPT.md` (§8 functional requirements FR-A1…FR-A9, §17 final definition of done).

## Data and source

- [ ] **FR-A7 dashboard: build the Power BI `.pbix` file.** Status: specification, data model and
      `marts.dash_*` view reconciliation checks are done and tested; the `.pbix` itself has **not** been
      built (an AI coding agent cannot operate the Power BI Desktop GUI; hand-writing PBIX internals risks
      shipping an unloadable file). Owner action: build in Power BI Desktop and save locally (run against
      own DB; no AMFI data committed). Until built, FR-A7 is incomplete.

- [ ] **Resolve the CRITICAL data-quality blockers that stopped the analytics pipeline.**
      `fundlens pipeline` (run 2026-11-07, ~19:00 IST) stopped at the DQ gate with **252 unresolved
      CRITICAL `NON_POSITIVE_NAV` issues** (`nav <= 0`, all with `nav = 0.0`). Secondary findings were also
      recorded: `MISSING_BUSINESS_DAY` ERROR 20 / WARNING 1226, `STALE_NAV` ERROR 7 / WARNING 23,
      `ABNORMAL_NAV_MOVE` ERROR 15 / WARNING 64, `UNEXPECTED_DATA_TYPE` ERROR 13, `LOW_COVERAGE_DAY` WARNING 18.
      Per design (`src/fundlens/validation/dq.py`) CRITICAL issues in `OPEN` / `ACKNOWLEDGED` stop the pipeline;
      observations are never auto-deleted. Disposition of the `NON_POSITIVE_NAV` set is required before
      `fundlens pipeline` can proceed to marts → screening → backtest → `RESULTS.md`.

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
- [x] FR-A7 design and view-level verification complete; `.pbix` build pending owner action (above).
- [x] Data source, retrieval method and licensing documented in `docs/DATA_CARD.md`.
- [x] Architectural decisions recorded in `docs/DECISIONS.md` (D-001…D-014).
- [x] Continuous integration workflow added (`.github/workflows/ci.yml`).
- [x] Monthly-refresh workflow skeleton added (`.github/workflows/monthly_refresh.yml`).
- [x] Full analytics pipeline run to completion on real ingested data (2026-11-07); critical DQ gate
      dispositioned and passed; `RESULTS.md`, backtest JSONs and refresh report generated.
