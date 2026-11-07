# FundLens architecture

FundLens is an analyst-support tool: it surfaces funds for **research review**. It never recommends buying
or selling anything.

## 1. System architecture

```mermaid
flowchart TD
    A[AMFI portal<br/>NAV history, date-chunked] --> B[Downloader<br/>gzip original + SHA-256]
    B --> C[(raw: source_file, nav_line<br/>append-only)]
    B --> F[data/raw/amfi/*.txt.gz<br/>git-ignored]
    C --> D[(staging.nav_parsed<br/>typed, VALID/REJECTED/DUPLICATE)]
    D --> E[(core: dim_scheme, fact_nav,<br/>scheme_mapping, dim_date, dq_issue)]
    E --> G[DQ checks]
    G -->|CRITICAL unresolved| X[Pipeline stops]
    G --> H[(marts: month-end metrics MV,<br/>forward-return MV)]
    H --> I[Screening engine]
    I --> J[(marts.review_flag)]
    H --> K[Walk-forward backtest]
    J --> K
    K --> L[(marts.backtest_run)]
    J --> M[marts.dash_* views]
    L --> M
    M --> N[Power BI dashboard]
    K --> O[RESULTS.md + results/]
```

## 2. Components

| Component | Location | Responsibility |
|---|---|---|
| Config | `config/*.toml`, `src/fundlens/config.py` | Scope (plans, options, categories), DQ thresholds, screening parameters. Config hash is stored per loaded file. |
| Downloader | `ingestion/download.py` | Deterministic 90-day chunk grid, retries, rejects non-NAV responses (HTML/redirects), preserves originals. |
| Parser | `ingestion/parser.py` | Pure functions; tracks section header (category) and AMC as state; derives plan/option; classifies lines. |
| Loader | `ingestion/loader.py` | One transaction per file: raw -> staging -> core; idempotent; records revision conflicts. |
| DQ framework | `validation/dq.py` | 13 SQL checks, upsert into `core.dq_issue` by fingerprint, auto-resolve, critical gate. |
| Metrics | `sql/marts/*.sql`, `metrics/build.py`, `metrics/reference.py` | SQL functions + materialised views; independent Python reference used by tests. |
| Screening | `screening/engine.py` | Configurable, point-in-time flag rules with explanations. |
| Backtesting | `backtesting/{stats,walkforward}.py` | Split/purge, tuning, baselines, bootstraps, permutation test. |
| Pipeline/reporting | `pipeline.py`, `reporting.py` | DQ gate -> marts -> screening -> backtests -> `RESULTS.md` strictly from computed numbers. |
| Dashboard | `dashboard/`, `sql/marts/040_dashboard_views.sql` | Power BI reads only `marts.dash_*` views. |
| Automation | `.github/workflows/` | `ci.yml` (lint+tests), `monthly_refresh.yml` (scheduled refresh). |

## 3. Data flow (one ingestion run)

1. `fundlens ingest` computes chunks anchored at the scope start date (so identical URLs recur) and skips
   settled chunks already loaded.
2. Each chunk is downloaded, hashed, stored as gzip; a hash already in `raw.source_file` makes the load a no-op.
3. Parser streams the file: out-of-scope lines are counted, in-scope lines become raw rows and staging rows.
4. Core upserts schemes (latest name/category by date), name history, inserts `fact_nav` (conflict -> ignored/recorded).
5. After all chunks `core.refresh_market_day()` rebuilds the calendar.
6. `fundlens pipeline` runs DQ -> gate -> marts -> screening -> backtests -> reports.

## 4. Database design

Schemas: `raw` (provenance, immutable), `staging` (parsed/rejected rows), `core` (standardised entities),
`marts` (analytics and read-models).

```mermaid
erDiagram
    ingestion_run ||--o{ source_file : "run_id"
    source_file ||--o{ nav_line : "file_id"
    source_file ||--o{ nav_parsed : "file_id"
    source_file ||--o{ fact_nav : "file_id"
    dim_scheme ||--o{ fact_nav : "scheme_id"
    dim_date ||--o{ fact_nav : "nav_date"
    dim_date ||--|| market_day : "cal_date"
    dim_scheme ||--o{ scheme_name_history : "scheme_id"
    dim_scheme ||--o{ scheme_mapping : "from/to"
    dim_scheme ||--o{ dq_issue : "scheme_id"
    dim_scheme ||--o{ nav_revision_conflict : "scheme_id"
    screening_run ||--o{ review_flag : "run_id"
    dim_scheme ||--o{ review_flag : "scheme_id"
    dim_scheme {
        bigint scheme_id PK
        text amfi_code UK
        text scheme_name
        text category
        text plan_type
        text option_type
    }
    fact_nav {
        bigint scheme_id PK
        date nav_date PK
        numeric nav
        bigint file_id FK
    }
    dq_issue {
        bigint issue_id PK
        text fingerprint UK
        text issue_category
        text severity
        text resolution_status
        jsonb observation
    }
```

Key constraints: `fact_nav` PK `(scheme_id, nav_date)`; `dim_scheme.amfi_code` unique; `source_file.sha256` unique;
`dq_issue.fingerprint` unique (idempotent DQ); CHECK constraints on severity, status, plan/option types;
append-only triggers on `raw.source_file` and `raw.nav_line`. Indexes: `fact_nav(nav_date)`,
`dim_scheme(category)`, partial index on open `dq_issue` by severity, materialised-view unique/lookup indexes.
Migrations are numbered SQL files with checksums in `public.schema_migration`; editing an applied file is an error.

## 5. Technology decisions

See `docs/DECISIONS.md`. In short: Python + pandas/NumPy/SciPy for orchestration and statistics; PostgreSQL 16 for
storage, window-function metrics and views; psycopg `COPY` for bulk loading; pytest + Hypothesis for tests;
Ruff for lint/format; Power BI for the dashboard; GitHub Actions for CI and the monthly refresh.

## 6. Conventions that affect every number

Actual/365 day count for CAGR and XIRR; sqrt(252) volatility annualisation; trailing-window definitions and
completeness rules (D-009); month-end = last market day of a completed month; percentile ranks within
(month-end, category, plan type).

## 7. Failure handling

| Failure | Behaviour |
|---|---|
| AMFI returns HTML / 3xx / network error | Retried with backoff, then the run is marked FAILED (`raw.ingestion_run`), exit non-zero; previously loaded files are kept. |
| Process killed mid-run | Each file loads in its own transaction (no partial file); next run marks stale RUNNING rows FAILED and resumes. |
| Malformed lines | Stored as REJECTED in staging with a reason; > 5% of a file rejected -> CRITICAL `INGESTION_REJECT_RATE`. |
| Non-positive or future-dated NAV, mass rejection | CRITICAL; `fundlens pipeline` exits with code 2 before building any output. |
| NAV revised upstream | Stored value kept; difference recorded; DQ ERROR `NAV_REVISION`. |
| Questionable observations | Never deleted; reported in `dq_issue` with the triggering observation. |
| Migration file edited after apply | Refused (checksum mismatch). |
| Monthly job failure | Red GitHub run + auto-created issue; report uploaded as an artifact. |

## 8. Database hosting for scheduled runs (FR-A8)

Runners are ephemeral, so scheduled refreshes need a persistent, TLS-reachable PostgreSQL. Any managed Postgres works
(Neon, Supabase, Azure Database for PostgreSQL). Steps: create the database; run `fundlens migrate` and an initial
`fundlens ingest` once from a trusted machine (or let the first scheduled run do it); add
`DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require` as a repository secret; enable the
workflow. No credentials are stored in the repository. **Status:** the workflow is written and linted but has not been run
remotely (no hosted database exists yet).
