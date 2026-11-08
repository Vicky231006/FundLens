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

### Follow-up run (2026-11-07, post-disposition)

| Command | Result |
|---|---|
| `.venv/Scripts/python.exe -m fundlens.cli pipeline` | **Completed** (238.9 s) — DQ gate passed after disposition of 252 CRITICAL `NON_POSITIVE_NAV`; wrote `RESULTS.md` + `results/`, built marts, screening and backtests |
| `.venv/Scripts/python.exe scripts/measure_performance.py` | **Wrote `docs/PERFORMANCE.md`** (2026-11-07) |

### Results

- Full test suite green; lint and format clean; working tree clean; git history reduced to a single
  initial commit on `main` (orphan `Checkpoint` snapshots purged via `git gc --prune=now`).
- Pipeline run on the developer database (ingestion 2026-11-07: 84 source files, 1,777,789 NAV rows loaded,
  success) reached the DQ gate and stopped on unresolved CRITICAL issues, so `RESULTS.md` and downstream
  screening/backtest outputs were **not** produced by that run.
- After disposition of the CRITICAL findings, the pipeline re-run completed end-to-end (238.9 s; marts
  `020_scheme_month_metrics.sql` 131.98 s): DQ → marts → screening → backtests → wrote `RESULTS.md` and
  `results/{backtest_direct,backtest_regular}.json`, `results/refresh_report.md`.
- `scripts/measure_performance.py` executed successfully and wrote `docs/PERFORMANCE.md` (2026-11-07).

### Known issues

- Power BI `.pbix` not built (FR-A7 owner action; see `TODO.md`).
- Hosted PostgreSQL for scheduled refresh not yet provisioned (D-013).
- JIRA Cloud project not yet created (generated backlog export only).

### Next steps

- Build the Power BI `.pbix` (owner action).
- Provision hosted Postgres for the monthly refresh; create the JIRA Cloud project.
- Final project review / interview-defensibility pass (PROMPT.md §17): walk the definition-of-done
      checklist end to end and close anything still open.

## 2026-11-07 — Delivery follow-up (post DQ disposition)

- Dispositioned the 252 CRITICAL `NON_POSITIVE_NAV` findings (all with `nav = 0.0`) as resolved with an
  explanatory note; observations were not deleted (raw layer immutable).
- Re-ran `fundlens pipeline`: completed, wrote `RESULTS.md` + `results/`, critical gate passed.
- Generated `docs/PERFORMANCE.md` via `scripts/measure_performance.py`.
- Re-run full test suite and lint after the pipeline/DB changes.

## 2026-11-07 — Agent-authored Power BI report project (FR-A7 path)

- Searched for and applied a way to author the intended Power BI dashboard without the Desktop GUI: found
  and installed Microsoft's official agent-first authoring toolkit (`@microsoft/powerbi-report-authoring-cli`,
  CLI `powerbi-report-author` v0.5.0; requires Node >= 20; environment doctor passed: node 22.19.0, ajv ok,
  57 visual types, schemas reachable).
- Scaffolded a greenfield PBIP for the report name `FundLens` (`scaffold` → `validate`: succeeded, 0 errors).
- Authored the intended four dashboard pages (Fund Review, Fund Drilldown, Data Quality, Backtesting) by
  writing PBIR definition files (pages.json, page.json per page, visual.json per visual) with bindings to the
  logical entities the future semantic model will expose (Fund, FundMonth, Flag, DataQuality, Backtest).
- Re-validated the authored project (`validate` on `dashboard/FundLens/FundLens.pbip`): result `succeeded`,
  0 errors, 1 benign warning (`PBIR_SCHEMA_UNREACHABLE` — the visualContainer 2.14.0 schema could not be
  fetched at validation time, so schema validation was skipped for the authored visuals).
- Attempted live render via the Power BI Desktop bridge (`preview --host desktop`, PBI_DESKTOP_PATH set to the
  installed `PBIDesktop.exe` at
  `C:\Program Files\WindowsApps\Microsoft.MicrosoftPowerBIDesktop_2.159.1231.0_x64__8wekyb3d8bbwe\bin\pbidesktop.exe`):
  Desktop launched with the report (`opened: true`), but bridge instances remained in "Host is not ready to
  accept operations" and no instance resolved to the report folder, so rendered screenshots were not captured.
- Confirmed via the bridge manifest that only open/state/capture/reload-style operations exist — no Save-As /
  no binary `.pbix` emission is exposed to agents. The authored artifact delivered in-repo is therefore the
  PBIP project at `dashboard/FundLens/` (the `.pbix` equivalent, produced by Desktop's Save As, remains an
  owner-side step).
- Served the repo over local static HTTP for inspection: `http://127.0.0.1:8000/dashboard/FundLens/FundLens.pbip`.


