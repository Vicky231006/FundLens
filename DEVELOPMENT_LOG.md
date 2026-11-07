# Development Log — FundLens

Format per `PROMPT.md` §16: work completed, files created or modified, tests executed, results, known
issues, next steps.

## 2026-11-07 — Session snapshot (agent-assisted build of FundLens)

### Work completed

- Rebuilt the complete FundLens application from the master prompt (`PROMPT.md`) through phase-ordered
  implementation (Phases 0–9 of the implementation strategy).
- Delivered: ingestion (`src/fundlens/ingestion/{download,loader,parser}.py`), validation (`validation/dq.py`),
  metrics (`metrics/{build,reference}.py`), screening (`screening/engine.py`), backtesting
  (`backtesting/{stats,walkforward}.py`), pipeline (`pipeline.py`), reporting (`reporting.py`), CLI
  (`cli.py`), config (`config.py`), DB (`db.py`).
- Delivered SQL: `sql/migrations/001–007`, `sql/staging/`, `sql/marts/010–040`, `sql/adhoc/01–16`.
- Delivered tests: `tests/unit/`, `tests/property/`, `tests/integration/` (incl. `conftest.py`).
- Delivered automation/docs: `.github/workflows/ci.yml`, `.github/workflows/monthly_refresh.yml`,
  `Makefile`, `make.ps1`, `docker-compose.yml`, `.env.example`, `README.md`, `docs/{BRD,USER_STORIES,ARCHITECTURE,DECISIONS,JIRA_BACKLOG}.md`.
- Added `scripts/measure_performance.py` and expanded `README.md`.

### Files created / modified

- Created: all source, SQL, tests, workflows, configs, docs listed above; `scripts/measure_performance.py`;
  later-added `docs/DATA_CARD.md`, `TODO.md`, `DEVELOPMENT_LOG.md`.
- Initial repository commit created after consolidating the pre-existing orphan `Checkpoint` snapshots:
  `92eab05` — `feat: initial FundLens implementation - ingestion, DQ, metrics, screening, backtesting, dashboard, tests`
  (98 files, +9073 lines).

### Tests executed

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q tests/unit tests/property` | **73 passed** (11.00 s) |
| `.venv/Scripts/python.exe -m pytest -q` (full suite incl. integration) | **104 passed** (67.33 s) — integration tests ran against the live Docker PostgreSQL 16 (`fundlens-db`, healthy on host :5433) |
| `.venv/Scripts/python.exe -m ruff check src tests` | **All checks passed** |
| `.venv/Scripts/python.exe -m ruff format --check src tests` | **36 files already formatted** |
| `.venv/Scripts/python.exe -m fundlens.cli pipeline` | **Stopped at DQ gate** (exit 2) — 252 CRITICAL `NON_POSITIVE_NAV` unresolved |

### Results

- Full test suite green; lint and format clean; working tree clean; git history reduced to a single
  initial commit on `main` (orphan `Checkpoint` snapshots purged via `git gc --prune=now`).
- Pipeline run on the developer database (ingestion 2026-11-07: 84 source files, 1,777,789 NAV rows loaded,
  success) reached the DQ gate and stopped on unresolved CRITICAL issues, so `RESULTS.md` and downstream
  screening/backtest outputs were **not** produced by that run.
- `scripts/measure_performance.py` writes `docs/PERFORMANCE.md` and was written to consume
  `marts.mv_scheme_month_metrics` / `marts.mv_scheme_month_end_nav`; those object names were not present in
  the migrated database (current marts objects: `v_month_end` plus `backtest_run`, `review_flag`,
  `screening_run`), so the script could not be executed against this database as-is.

### Known issues

- `RESULTS.md` not yet generated (no pipeline run has produced measured outcomes).
- Power BI `.pbix` not built (FR-A7 owner action; see `TODO.md`).
- Hosted PostgreSQL for scheduled refresh not yet provisioned (D-013).
- JIRA Cloud project not yet created (generated backlog export only).
- Pipeline currently blocked by unresolved CRITICAL `NON_POSITIVE_NAV` data-quality findings (252).

### Next steps

- Disposition of the CRITICAL `NON_POSITIVE_NAV` findings (investigate source, then resolve / acknowledge /
      mark WONT_FIX as appropriate) and re-run `fundlens pipeline`.
- Run `scripts/measure_performance.py` once the marts view names it expects exist, then commit
      `docs/PERFORMANCE.md`.
- Run `.\make.ps1 reproduce` on real ingested data and commit the genuine `RESULTS.md`.
- Build the Power BI `.pbix` (owner action).
- Provision hosted Postgres for the monthly refresh; create the JIRA Cloud project.

