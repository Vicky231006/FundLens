# FundLens - JIRA Backlog Export

> **THIS IS AN EXPORT FILE. NO JIRA TICKETS HAVE BEEN CREATED.**
> No JIRA Cloud access or API credentials are available in this environment, so no JIRA
> project, epics, stories or sprints exist. The files `docs/jira_backlog.csv` and this
> document are a structured backlog prepared for a later manual import. Issue Key values
> are intentionally blank because JIRA assigns them on import.

Companion file: `docs/jira_backlog.csv` (same content in import-friendly CSV form).

## How to import into JIRA Cloud

1. Create a JIRA Cloud project for FundLens (a team-managed or company-managed software project).
2. Go to **Project settings > Import work items from CSV** (older UI wording: *System > External system import > CSV*).
3. Upload `docs/jira_backlog.csv` (UTF-8, comma delimiter).
4. Map the columns:

   | CSV column | JIRA field |
   |---|---|
   | Issue Type | Work type / Issue Type (Epic, Story) |
   | Issue Key | leave unmapped (blank; JIRA assigns keys) |
   | Summary | Summary |
   | Description | Description |
   | Epic Name/Epic Link | Epic Name on Epic rows; Epic Link on Story rows (see note) |
   | Priority | Priority |
   | Story Points | Story point estimate |
   | Sprint | Sprint |
   | Acceptance Criteria | Acceptance Criteria (custom field) or append to Description |
   | Labels | Labels (space-separated) |
   | Status | Status (optional; see note) |

5. Notes:
   - **Epic Link:** on Story rows the epic's *name* is given. JIRA's importer links stories to epics by key or by Epic Name depending on version. If names are not resolved, import the 10 Epic rows first, then re-import the stories using the generated epic keys.
   - **Status:** the importer can only set statuses that exist in the target workflow. Stories marked Done below should be transitioned to Done after import if the status column is not mapped.
   - **Sprints:** Sprint 1..Sprint 10 are created by the importer if missing; sprint dates must be set in JIRA. No dates are asserted here.
   - **Acceptance Criteria** may need a custom text field; create one first or map it to Description.
   - Multi-line cells are quoted in the CSV. A story's Description starts with its backlog Ref (for example ING-02) for cross-referencing with this document.

## Planning notes and honesty statement

- Story points are rough relative estimates (Fibonacci-style), **not** measured velocity. Sprint loads are uneven (see table) and Sprints 9-10 are the heaviest; if schedule slips, descope candidates are the dashboard publication story (AUT) and parts of the ad-hoc SQL library.
- Sprint 1..10 are one-week sprints in sequence; actual dates are not fixed here.
- **Status is taken from the actual repository state:** Done = Python 3.14 environment with pyproject/ruff/pytest; Docker Compose PostgreSQL 16 reachable from Python; AMFI endpoint verified; migrations 001-004 applied; AMFI parser, downloader and idempotent loader written (unit tests exist for the parser and downloader; database-level idempotency proof is still To Do); Phase 0 documents drafted (BRD, user stories, this backlog export). Everything else is To Do.
- The CSV has one column beyond the requested set (Status) so Done work can be represented.
- Backlog items reference BRD functional requirements (FR-A1..FR-A9), non-functional requirements (NFR-n), business objectives (BO-n) and user stories (US-xx-nn).

## Summary

- Epics: 10
- Stories: 61 (9 Done, 52 To Do)
- Estimated story points: 212 total, 32 Done, 180 To Do

### Epics

| Epic | Stories | Done | Points | Description |
|---|---|---|---|---|
| Infrastructure and architecture | 4 | 2 | 11 | Repository, environment, containerised PostgreSQL, CLI and architecture documentation. |
| Data ingestion | 8 | 4 | 30 | Retrieve genuine AMFI NAV data, preserve raw files, parse, validate and load idempotently. |
| Database engineering | 8 | 2 | 33 | PostgreSQL layers, constraints, scheme dimension and mapping, indexing, ad-hoc SQL. |
| Data quality | 7 | 0 | 23 | DQ checks, dq_issue persistence, severity, critical-failure blocking and resolution workflow. |
| Financial metrics | 8 | 0 | 30 | Rolling CAGR, volatility, drawdown, SIP XIRR and category percentile rank with tests. |
| Review-flag engine | 4 | 0 | 13 | Configurable, explainable, as-of review-flag rule. |
| Backtesting | 7 | 0 | 24 | Walk-forward evaluation, baselines, block-bootstrap CIs, limitations and RESULTS.md. |
| Dashboard | 5 | 0 | 19 | Analyst dashboard: review screen, drilldown, data-quality page, backtesting page. |
| Automation and deployment | 6 | 0 | 15 | CI, monthly GitHub Actions refresh, refresh report, hosting and publication. |
| Documentation and testing | 4 | 1 | 14 | BRD, user stories, data card, results documentation, test harness and honesty review. |

### Sprint plan

| Sprint | Theme | Stories | Points | Done |
|---|---|---|---|---|
| Sprint 1 | Environment, AMFI verification, Phase 0 docs | 4 | 12 | 4/4 |
| Sprint 2 | Core migrations, parser, downloader, loader | 6 | 22 | 5/6 |
| Sprint 3 | Idempotency proof, backfill, raw immutability, data card, CI | 7 | 24 | 0/7 |
| Sprint 4 | Scheme dimension and mapping, DQ framework, architecture docs | 5 | 21 | 0/5 |
| Sprint 5 | DQ checks, critical gate, resolution and mapping review workflows | 7 | 20 | 0/7 |
| Sprint 6 | DQ tests, metric conventions, CAGR, volatility, drawdown, dashboard scaffold | 6 | 20 | 0/6 |
| Sprint 7 | XIRR, percentile rank, metric tests, DQ page, flag config | 6 | 21 | 0/6 |
| Sprint 8 | Flag rule, explanations, look-ahead test, forward returns, ad-hoc SQL, workflow | 6 | 22 | 0/6 |
| Sprint 9 | Tuning, baselines, bootstrap, limitations, RESULTS, review screen | 7 | 26 | 0/7 |
| Sprint 10 | Drilldown, backtest page, orchestration, report, publication, performance, final review | 7 | 24 | 0/7 |

## Stories by sprint

### Sprint 1 - Environment, AMFI verification, Phase 0 docs

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| INF-01 | Infrastructure and architecture | Set up Python 3.14 environment, pyproject, ruff and pytest | 3 | High | Done |
| INF-02 | Infrastructure and architecture | Run PostgreSQL 16 with Docker Compose and connect from Python | 3 | High | Done |
| ING-01 | Data ingestion | Verify AMFI historical NAV endpoint and record limits | 3 | Highest | Done |
| DOC-01 | Documentation and testing | Draft Phase 0 documents: BRD, user stories and backlog export | 3 | Medium | Done |

### Sprint 2 - Core migrations, parser, downloader, loader

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| DB-01 | Database engineering | Create raw, staging and core layer migrations (001-003) | 5 | Highest | Done |
| DB-02 | Database engineering | Seed dim_date calendar (migration 004) | 2 | High | Done |
| ING-02 | Data ingestion | Implement AMFI NAV parser with unit tests | 5 | Highest | Done |
| ING-03 | Data ingestion | Implement date-chunked AMFI downloader preserving raw files | 3 | High | Done |
| ING-04 | Data ingestion | Implement idempotent loader from raw files to staging and core | 5 | Highest | Done |
| INF-03 | Infrastructure and architecture | Add Makefile and .env.example | 2 | Medium | To Do |

### Sprint 3 - Idempotency proof, backfill, raw immutability, data card, CI

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| DOC-02 | Documentation and testing | Create test database fixture and pytest markers | 3 | High | To Do |
| ING-05 | Data ingestion | Add integration test proving idempotent re-ingestion | 3 | Highest | To Do |
| ING-06 | Data ingestion | Run full historical backfill from 2006-04-01 and record dataset size | 5 | High | To Do |
| ING-07 | Data ingestion | Add ingestion CLI summary, retries and loud failure on unexpected format | 3 | Medium | To Do |
| DB-03 | Database engineering | Enforce raw layer immutability and add schema integrity tests | 5 | High | To Do |
| DOC-03 | Documentation and testing | Write DATA_CARD.md (source, retrieval, dictionary, licensing, gaps) | 3 | High | To Do |
| AUT-01 | Automation and deployment | Add CI workflow running ruff and unit tests | 2 | Medium | To Do |

### Sprint 4 - Scheme dimension and mapping, DQ framework, architecture docs

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| DB-04 | Database engineering | Populate dim_scheme with scheme identity rules | 5 | Highest | To Do |
| DB-05 | Database engineering | Implement scheme_mapping for renames and mergers | 5 | Highest | To Do |
| ING-08 | Data ingestion | Record NAV revision conflicts instead of overwriting | 3 | High | To Do |
| DQ-01 | Data quality | Build DQ framework: dq_issue persistence and severity model | 5 | Highest | To Do |
| INF-04 | Infrastructure and architecture | Write ARCHITECTURE.md with ER diagram and start DECISIONS.md | 3 | Medium | To Do |

### Sprint 5 - DQ checks, critical gate, resolution and mapping review workflows

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| DQ-02 | Data quality | Check: missing business-day observations | 3 | High | To Do |
| DQ-03 | Data quality | Checks: non-positive NAV, abnormal day-over-day moves, stale NAV | 3 | High | To Do |
| DQ-04 | Data quality | Checks: duplicates, invalid scheme identifiers, invalid dates, unexpected types | 3 | High | To Do |
| DQ-05 | Data quality | Critical DQ failures stop the analytics pipeline | 3 | Highest | To Do |
| DQ-06 | Data quality | Issue resolution workflow for dq_issue | 3 | High | To Do |
| DB-06 | Database engineering | Scheme mapping review workflow | 3 | High | To Do |
| AUT-02 | Automation and deployment | Document hosting strategy for remote scheduled PostgreSQL | 2 | Medium | To Do |

### Sprint 6 - DQ tests, metric conventions, CAGR, volatility, drawdown, dashboard scaffold

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| DQ-07 | Data quality | DQ tests with injected faults (synthetic, clearly labelled) | 3 | High | To Do |
| MET-01 | Financial metrics | Document metric conventions and insufficient-history rules | 3 | Highest | To Do |
| MET-02 | Financial metrics | Rolling 1-, 3- and 5-year CAGR views | 5 | Highest | To Do |
| MET-03 | Financial metrics | Annualised volatility view | 3 | High | To Do |
| MET-04 | Financial metrics | Maximum drawdown view | 3 | High | To Do |
| DSH-01 | Dashboard | Dashboard scaffold with last-refresh banner and disclosure | 3 | High | To Do |

### Sprint 7 - XIRR, percentile rank, metric tests, DQ page, flag config

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| MET-05 | Financial metrics | Standardised SIP XIRR | 5 | High | To Do |
| MET-06 | Financial metrics | Category percentile rank at each month-end | 3 | High | To Do |
| MET-07 | Financial metrics | Financial calculation tests: hand-computed and independent references | 5 | Highest | To Do |
| MET-08 | Financial metrics | Property-based tests for metric invariants | 3 | High | To Do |
| DSH-02 | Dashboard | Data-quality page | 3 | High | To Do |
| FLG-01 | Review-flag engine | Define flag configuration with validation | 2 | High | To Do |

### Sprint 8 - Flag rule, explanations, look-ahead test, forward returns, ad-hoc SQL, workflow

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| FLG-02 | Review-flag engine | Implement as-of review-flag rule | 5 | Highest | To Do |
| FLG-03 | Review-flag engine | Generate explanation text for every flag | 3 | Highest | To Do |
| FLG-04 | Review-flag engine | Test that flags use no future information | 3 | Highest | To Do |
| BT-01 | Backtesting | Forward 12-month return, excess return target y and time split | 3 | Highest | To Do |
| DB-07 | Database engineering | Ad-hoc SQL library (at least ten queries) | 5 | Medium | To Do |
| AUT-03 | Automation and deployment | Create monthly_refresh.yml workflow (scheduled and manual) | 3 | High | To Do |

### Sprint 9 - Tuning, baselines, bootstrap, limitations, RESULTS, review screen

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| BT-02 | Backtesting | Tune parameters on training period only | 3 | Highest | To Do |
| BT-03 | Backtesting | Baselines: bottom-quartile 1-year return and permutation random flags | 5 | Highest | To Do |
| BT-04 | Backtesting | Fund-clustered block bootstrap and 95% confidence intervals | 5 | Highest | To Do |
| BT-05 | Backtesting | Document survivorship bias, look-ahead and other limitations | 2 | High | To Do |
| BT-06 | Backtesting | Backtesting correctness tests | 3 | High | To Do |
| BT-07 | Backtesting | Generate RESULTS.md and make reproduce | 3 | Highest | To Do |
| DSH-03 | Dashboard | Fund review screen with filters, trigger reasons and CSV export | 5 | Highest | To Do |

### Sprint 10 - Drilldown, backtest page, orchestration, report, publication, performance, final review

| Ref | Epic | Summary | Pts | Priority | Status |
|---|---|---|---|---|---|
| DSH-04 | Dashboard | Fund drilldown with category comparison and flag timeline | 5 | High | To Do |
| DSH-05 | Dashboard | Backtesting page with baselines, CIs, dataset size and limitations | 3 | High | To Do |
| AUT-04 | Automation and deployment | Orchestrate end-to-end refresh with critical-failure gate | 3 | High | To Do |
| AUT-05 | Automation and deployment | Generate refresh report | 2 | Medium | To Do |
| AUT-06 | Automation and deployment | Publish dashboard and record last-refresh metadata | 3 | Low | To Do |
| DB-08 | Database engineering | Indexing review and measured query performance | 3 | Medium | To Do |
| DOC-04 | Documentation and testing | Final documentation, honesty review and pre-publication checks | 5 | High | To Do |

## Story details

### Epic: Infrastructure and architecture

Repository, environment, containerised PostgreSQL, CLI and architecture documentation.

#### INF-01 - Set up Python 3.14 environment, pyproject, ruff and pytest

- **Status:** Done | **Sprint:** 1 | **Priority:** High | **Points:** 3 | **Labels:** setup python tooling
- **Linked:** NFR-1, NFR-7
- **Description:** Create the project virtual environment (Python 3.14) and pyproject.toml with dependencies, ruff lint configuration and pytest configuration.
- **Acceptance criteria:**
  - Virtual environment exists and project installs in editable mode
  - pyproject.toml declares runtime and dev dependencies plus ruff and pytest settings
  - ruff check and pytest both run from the project root

#### INF-02 - Run PostgreSQL 16 with Docker Compose and connect from Python

- **Status:** Done | **Sprint:** 1 | **Priority:** High | **Points:** 3 | **Labels:** setup docker postgres
- **Linked:** NFR-5
- **Description:** Provide docker-compose.yml for PostgreSQL 16 with a named volume and confirm the Python code can connect using environment-based settings.
- **Acceptance criteria:**
  - docker compose up starts PostgreSQL 16
  - A Python connection test succeeds using settings from environment variables
  - No credentials are hard-coded in committed files

#### INF-03 - Add Makefile and .env.example

- **Status:** To Do | **Sprint:** 2 | **Priority:** Medium | **Points:** 2 | **Labels:** setup tooling
- **Linked:** NFR-1, NFR-5
- **Description:** Add Makefile targets (lint, test, migrate, ingest, reproduce placeholder) and a committed .env.example containing placeholders only.
- **Acceptance criteria:**
  - make lint and make test run ruff and pytest
  - .env.example lists every required variable with placeholder values only
  - .env is git-ignored
  - make reproduce exists and clearly states what it does not yet cover

#### INF-04 - Write ARCHITECTURE.md with ER diagram and start DECISIONS.md

- **Status:** To Do | **Sprint:** 4 | **Priority:** Medium | **Points:** 3 | **Labels:** docs architecture
- **Linked:** NFR-2, NFR-3
- **Description:** Create docs/ARCHITECTURE.md (components, data flow, database design with ER diagram, technology decisions, failure handling) and docs/DECISIONS.md (decision log with alternatives, including plan-scope and chunking decisions already made).
- **Acceptance criteria:**
  - ER diagram matches the migrated schema
  - Data flow from AMFI to dashboard is described
  - Each decision has context, choice and alternatives considered
  - Failure handling per stage is described

### Epic: Data ingestion

Retrieve genuine AMFI NAV data, preserve raw files, parse, validate and load idempotently.

#### ING-01 - Verify AMFI historical NAV endpoint and record limits

- **Status:** Done | **Sprint:** 1 | **Priority:** Highest | **Points:** 3 | **Labels:** amfi research
- **Linked:** FR-A1
- **Description:** Investigate the official AMFI historical NAV download, confirm available metadata and retrieval limits. Findings recorded in config/scope.toml: history begins 2006-04-01; a request of 105 days works, 366 days is rejected; chunk size set to 90 days. Verified 2026-11-07. Terms of use review is a separate story.
- **Acceptance criteria:**
  - Endpoint URL and parameters documented with retrieval date
  - Earliest available date and maximum request span determined by test requests
  - Scope (categories, plan, option) captured in config/scope.toml

#### ING-02 - Implement AMFI NAV parser with unit tests

- **Status:** Done | **Sprint:** 2 | **Priority:** Highest | **Points:** 5 | **Labels:** python ingestion testing
- **Linked:** FR-A1
- **Description:** Parse the AMFI semicolon-separated NAV text into typed records, track section headers (fund type and category), and apply the scope filters from config/scope.toml. Unit tests in tests/unit/test_parser.py.
- **Acceptance criteria:**
  - Parser converts sample AMFI text into typed records with scheme code, name, NAV and date
  - Category sections are mapped using config/scope.toml; out-of-scope sections are excluded from the database
  - Malformed lines are reported, not silently dropped
  - Unit tests pass

#### ING-03 - Implement date-chunked AMFI downloader preserving raw files

- **Status:** Done | **Sprint:** 2 | **Priority:** High | **Points:** 3 | **Labels:** python ingestion testing
- **Linked:** FR-A1
- **Description:** Download history in chunks of at most 90 days, save each original response to the raw data directory, and handle the HTML error page AMFI returns for unsupported ranges. Unit tests in tests/unit/test_download.py.
- **Acceptance criteria:**
  - Requested ranges are split into chunks no longer than the configured chunk_days
  - Each response is stored unmodified as a raw file
  - An HTML error response is detected and reported as a failure, not parsed as NAV data
  - Unit tests pass

#### ING-04 - Implement idempotent loader from raw files to staging and core

- **Status:** Done | **Sprint:** 2 | **Priority:** Highest | **Points:** 5 | **Labels:** python ingestion postgres
- **Linked:** FR-A1
- **Description:** Load parsed records into raw.nav_line, staging and core.fact_nav using insert-if-absent semantics, recording ingestion run metadata and a file hash. Code is written; database-level proof of idempotency is a separate To Do story (integration test).
- **Acceptance criteria:**
  - Loader records an ingestion_run and source_file row per file with a content hash
  - Loading is written with conflict-safe inserts keyed on scheme and date
  - Loader code exists and lints cleanly

#### ING-05 - Add integration test proving idempotent re-ingestion

- **Status:** To Do | **Sprint:** 3 | **Priority:** Highest | **Points:** 3 | **Labels:** testing ingestion
- **Linked:** FR-A1, US-DO-06
- **Description:** Load a fixed sample file twice into the test database and prove the second load changes nothing. Also test the changed-NAV (revision) case.
- **Acceptance criteria:**
  - Given a loaded sample, when it is loaded again, then fact_nav row count is unchanged
  - Every fact_nav row traces to a source_file and ingestion_run
  - Original sample file is byte-identical after both loads

#### ING-06 - Run full historical backfill from 2006-04-01 and record dataset size

- **Status:** To Do | **Sprint:** 3 | **Priority:** High | **Points:** 5 | **Labels:** ingestion data
- **Linked:** FR-A1, NFR-4
- **Description:** Run the chunked ingestion over the full available history for in-scope schemes. Record row counts, scheme counts, date range and elapsed time in the ingestion log. Do not publish raw files until the licensing review in DATA_CARD is complete.
- **Acceptance criteria:**
  - Backfill completes with every chunk logged in raw.ingestion_run
  - Row counts per layer and elapsed time are recorded with the dataset size
  - Failed or empty chunks are listed and not silently skipped
  - Raw files are stored locally and excluded from version control

#### ING-07 - Add ingestion CLI summary, retries and loud failure on unexpected format

- **Status:** To Do | **Sprint:** 3 | **Priority:** Medium | **Points:** 3 | **Labels:** python ingestion cli
- **Linked:** FR-A1, FR-A8
- **Description:** Expose an ingest command that prints a run summary (files, rows loaded, rows rejected, duration). Add bounded retries with delay for network errors and fail loudly if the source format is unrecognised.
- **Acceptance criteria:**
  - CLI prints files, loaded, rejected and duration for each run
  - Network errors are retried a bounded number of times then reported as failure
  - An unrecognised response format exits non-zero with a clear message

#### ING-08 - Record NAV revision conflicts instead of overwriting

- **Status:** To Do | **Sprint:** 4 | **Priority:** High | **Points:** 3 | **Labels:** ingestion data-quality
- **Linked:** FR-A1, US-DO-06
- **Description:** When a re-ingested NAV differs from the stored NAV for the same scheme and date, write a row to core.nav_revision_conflict, keep the original, and surface a data issue.
- **Acceptance criteria:**
  - Given a different NAV for an existing scheme-date, then the original fact_nav row is unchanged
  - A nav_revision_conflict row records old value, new value, and source file
  - The conflict is reported in the run summary

### Epic: Database engineering

PostgreSQL layers, constraints, scheme dimension and mapping, indexing, ad-hoc SQL.

#### DB-01 - Create raw, staging and core layer migrations (001-003)

- **Status:** Done | **Sprint:** 2 | **Priority:** Highest | **Points:** 5 | **Labels:** sql migrations schema
- **Linked:** FR-A1, FR-A2, FR-A3
- **Description:** SQL migrations 001_raw_layer, 002_staging_layer and 003_core_layer creating the raw, staging, core and marts schemas and tables (raw ingestion_run, source_file, nav_line; staging nav_parsed; core dim_scheme, scheme_name_history, scheme_mapping, dim_date, fact_nav, nav_revision_conflict, dq_issue). Applied to local PostgreSQL 16.
- **Acceptance criteria:**
  - Migrations 001-003 apply cleanly to an empty database
  - Primary keys, foreign keys and uniqueness constraints are defined
  - Tables for dq_issue and scheme_mapping exist (structure only; logic is in later stories)

#### DB-02 - Seed dim_date calendar (migration 004)

- **Status:** Done | **Sprint:** 2 | **Priority:** High | **Points:** 2 | **Labels:** sql migrations
- **Linked:** FR-A3, FR-A4
- **Description:** Migration 004_seed_dim_date populates the date dimension used for business-day and month-end logic. Applied locally.
- **Acceptance criteria:**
  - dim_date is populated for the history range
  - Weekend flag and month-end flag columns are populated
  - Migration is idempotent or guarded against re-application

#### DB-03 - Enforce raw layer immutability and add schema integrity tests

- **Status:** To Do | **Sprint:** 3 | **Priority:** High | **Points:** 5 | **Labels:** sql security testing
- **Linked:** FR-A1, NFR-3
- **Description:** Restrict the application role so normal ingestion can INSERT but not UPDATE or DELETE on raw tables, and add tests that check constraints, foreign keys and uniqueness behave as designed.
- **Acceptance criteria:**
  - Given the ingestion role, when it attempts UPDATE or DELETE on a raw table, then the database rejects it
  - Tests confirm duplicate scheme-date inserts into fact_nav are prevented
  - Tests confirm foreign key violations are rejected

#### DB-04 - Populate dim_scheme with scheme identity rules

- **Status:** To Do | **Sprint:** 4 | **Priority:** Highest | **Points:** 5 | **Labels:** sql python schemes
- **Linked:** FR-A2
- **Description:** Populate core.dim_scheme from staged data using AMFI scheme code as the natural key, with AMC, category, name, Direct/Regular plan and Growth/IDCW option derived explicitly. Never merge schemes on name similarity.
- **Acceptance criteria:**
  - Each AMFI scheme code maps to exactly one dim_scheme row
  - Plan and option are derived by documented rules with unit tests
  - Given two similarly named schemes with different codes, then they remain separate rows
  - Name changes for the same code are stored in scheme_name_history

#### DB-05 - Implement scheme_mapping for renames and mergers

- **Status:** To Do | **Sprint:** 4 | **Priority:** Highest | **Points:** 5 | **Labels:** sql schemes testing
- **Linked:** FR-A2, US-DO-05
- **Description:** Add the mechanism to record rename and merger relations as explicit scheme_mapping rows with effective date, evidence note and status (proposed, approved, rejected). Only approved mappings are used to build continuous histories.
- **Acceptance criteria:**
  - Mappings are stored only as explicit rows, never inferred automatically from name similarity
  - Status values are constrained to proposed, approved, rejected
  - A query returns a continuous history across an approved mapping and excludes proposed or rejected ones
  - Tests cover rename, merger and rejected-mapping cases

#### DB-06 - Scheme mapping review workflow

- **Status:** To Do | **Sprint:** 5 | **Priority:** High | **Points:** 3 | **Labels:** sql schemes cli
- **Linked:** FR-A2, US-DO-05
- **Description:** List proposed rename and merger mappings with supporting evidence and allow approve or reject with a note, so only human-confirmed mappings take effect.
- **Acceptance criteria:**
  - Proposed mappings can be listed with evidence
  - Approve and reject actions update status and record who and when (as a label, no real identities needed)
  - Rejected mappings never affect histories

#### DB-07 - Ad-hoc SQL library (at least ten queries)

- **Status:** To Do | **Sprint:** 8 | **Priority:** Medium | **Points:** 5 | **Labels:** sql adhoc
- **Linked:** FR-A9, US-RA-08
- **Description:** Write at least ten SQL files in sql/adhoc, each starting with the business question. Cover CTEs, window functions, aggregations, joins, ranking, time-series analysis, data-quality investigation and performance comparison. Test each against the actual schema.
- **Acceptance criteria:**
  - At least ten files exist in sql/adhoc
  - Each file begins with a business-question comment
  - An automated check executes every file against the database without error
  - Listed techniques are each used by at least one query

#### DB-08 - Indexing review and measured query performance

- **Status:** To Do | **Sprint:** 10 | **Priority:** Medium | **Points:** 3 | **Labels:** sql performance
- **Linked:** NFR-4
- **Description:** Measure ingestion time, row counts, key query and dashboard query latency, and materialised view refresh time; add indexes where justified and compare before and after. State dataset size for every measurement.
- **Acceptance criteria:**
  - Each measurement states the dataset size and hardware context
  - Before and after latency is recorded for each added index
  - No figure is quoted unless it was measured by a re-runnable script

### Epic: Data quality

DQ checks, dq_issue persistence, severity, critical-failure blocking and resolution workflow.

#### DQ-01 - Build DQ framework: dq_issue persistence and severity model

- **Status:** To Do | **Sprint:** 4 | **Priority:** Highest | **Points:** 5 | **Labels:** python sql data-quality
- **Linked:** FR-A3
- **Description:** Create the DQ check runner interface, the severity model (for example critical, error, warning, info; to be documented) and persistence into core.dq_issue with all required fields: issue id, scheme id where applicable, category, detection timestamp, severity, observation, explanation, resolution status.
- **Acceptance criteria:**
  - Each persisted issue has issue id, category, detection timestamp, severity, observation, explanation, status and scheme id when applicable
  - Re-running a check does not create a duplicate open issue for the same problem
  - Severity per check type is documented

#### DQ-02 - Check: missing business-day observations

- **Status:** To Do | **Sprint:** 5 | **Priority:** High | **Points:** 3 | **Labels:** data-quality python sql
- **Linked:** FR-A3
- **Description:** Detect scheme-level gaps where a business day (per dim_date) has no NAV between a scheme's first and last observation. Define how market holidays are handled and document it.
- **Acceptance criteria:**
  - Given a gap in a scheme's NAV series, then a dq_issue is created for the missing date range
  - Holiday handling rule is documented and tested
  - The check does not insert or delete any NAV rows

#### DQ-03 - Checks: non-positive NAV, abnormal day-over-day moves, stale NAV

- **Status:** To Do | **Sprint:** 5 | **Priority:** High | **Points:** 3 | **Labels:** data-quality python
- **Linked:** FR-A3
- **Description:** Detect NAV <= 0, absolute day-over-day change above a configurable threshold, and NAV unchanged for more than a configurable number of business days. Thresholds are placed in config with rationale recorded.
- **Acceptance criteria:**
  - Non-positive NAV creates a critical issue
  - A move above the configured threshold creates an issue and the observation is retained
  - A stale run longer than the configured limit creates an issue
  - Thresholds are read from config, not hard-coded

#### DQ-04 - Checks: duplicates, invalid scheme identifiers, invalid dates, unexpected types

- **Status:** To Do | **Sprint:** 5 | **Priority:** High | **Points:** 3 | **Labels:** data-quality python sql
- **Linked:** FR-A3
- **Description:** Implement structural checks: duplicate scheme-date combinations, missing or invalid scheme identifiers, invalid dates, and unexpected data types, including at the staging layer where rejected records are held.
- **Acceptance criteria:**
  - Each of the four conditions produces an issue of the documented category
  - Rejected staging records remain stored with a reason
  - Duplicate scheme-date detection is severity critical

#### DQ-05 - Critical DQ failures stop the analytics pipeline

- **Status:** To Do | **Sprint:** 5 | **Priority:** Highest | **Points:** 3 | **Labels:** data-quality pipeline testing
- **Linked:** FR-A3, US-DO-03
- **Description:** Add a gate after DQ checks: if any open critical issue exists, the pipeline exits non-zero before metrics, flags or backtests refresh. Print the critical issues.
- **Acceptance criteria:**
  - Given at least one open critical issue, when the pipeline runs, then it exits non-zero before metrics refresh
  - Critical issues are printed in the log
  - Given only non-critical issues, then the pipeline continues
  - Gate is covered by an integration test

#### DQ-06 - Issue resolution workflow for dq_issue

- **Status:** To Do | **Sprint:** 5 | **Priority:** High | **Points:** 3 | **Labels:** data-quality sql cli
- **Linked:** FR-A3, US-DO-02
- **Description:** Allow status transitions (open, investigating, resolved, accepted) with a note and timestamp, via CLI or SQL function. Original observation and explanation stay unchanged.
- **Acceptance criteria:**
  - Status changes record the new status, a note and a timestamp
  - Invalid status values are rejected by a constraint
  - Original observation and explanation are not modified by a status change

#### DQ-07 - DQ tests with injected faults (synthetic, clearly labelled)

- **Status:** To Do | **Sprint:** 6 | **Priority:** High | **Points:** 3 | **Labels:** testing data-quality synthetic
- **Linked:** FR-A3, US-DO-08
- **Description:** Build small synthetic fixtures with deliberately injected faults for each check. Fixtures are labelled synthetic; detection results are described as performance on injected faults, never as real-world performance.
- **Acceptance criteria:**
  - Each DQ check has at least one fixture containing a known injected fault
  - Fixtures are labelled synthetic in file names and docs
  - Tests assert the expected issue count and category per fixture
  - A test shows DQ runs do not change row counts in fact_nav

### Epic: Financial metrics

Rolling CAGR, volatility, drawdown, SIP XIRR and category percentile rank with tests.

#### MET-01 - Document metric conventions and insufficient-history rules

- **Status:** To Do | **Sprint:** 6 | **Priority:** Highest | **Points:** 3 | **Labels:** metrics docs
- **Linked:** FR-A4
- **Description:** Write the conventions document: month-end definition (last NAV on or before month-end), calendar vs trading-day year, annualisation factor, minimum observation counts and the explicit null result for insufficient or incomplete history.
- **Acceptance criteria:**
  - Conventions are documented and referenced from SQL view comments
  - Rule for insufficient history returns null plus a reason, never a computed value
  - Rule for missing observations inside a window is stated

#### MET-02 - Rolling 1-, 3- and 5-year CAGR views

- **Status:** To Do | **Sprint:** 6 | **Priority:** Highest | **Points:** 5 | **Labels:** metrics sql
- **Linked:** FR-A4
- **Description:** SQL views (or justified materialised views) for rolling CAGR at month-end for 1, 3 and 5 years, using the documented conventions. Record view-vs-materialised-view choice and measured refresh time in DECISIONS.md.
- **Acceptance criteria:**
  - CAGR matches hand-computed example for a small NAV series
  - Funds with insufficient history return null with a reason
  - The calculation uses only NAVs on or before the month-end
  - Choice between view and materialised view is documented with measured refresh duration and dataset size

#### MET-03 - Annualised volatility view

- **Status:** To Do | **Sprint:** 6 | **Priority:** High | **Points:** 3 | **Labels:** metrics sql
- **Linked:** FR-A4
- **Description:** SQL view for annualised volatility of periodic returns using the documented annualisation assumption.
- **Acceptance criteria:**
  - Constant NAV series gives volatility of zero
  - Result matches an independently computed reference on a fixed series
  - Insufficient history returns null with a reason

#### MET-04 - Maximum drawdown view

- **Status:** To Do | **Sprint:** 6 | **Priority:** High | **Points:** 3 | **Labels:** metrics sql
- **Linked:** FR-A4
- **Description:** SQL view for maximum drawdown over a defined window using running peak NAV.
- **Acceptance criteria:**
  - Maximum drawdown is never positive
  - Result matches a manually constructed NAV sequence with known peak and trough
  - A monotonically rising series gives drawdown of zero

#### MET-05 - Standardised SIP XIRR

- **Status:** To Do | **Sprint:** 7 | **Priority:** High | **Points:** 5 | **Labels:** metrics sql python
- **Linked:** FR-A4
- **Description:** Implement standardised SIP XIRR (fixed monthly instalment schedule defined in documentation) for each scheme over defined horizons, with explicit handling for incomplete history.
- **Acceptance criteria:**
  - XIRR matches an Excel-compatible independent calculation on a fixed example
  - SIP schedule and horizons are documented
  - A zero-return series gives an XIRR of approximately zero within a stated tolerance
  - Insufficient history returns null with a reason

#### MET-06 - Category percentile rank at each month-end

- **Status:** To Do | **Sprint:** 7 | **Priority:** High | **Points:** 3 | **Labels:** metrics sql
- **Linked:** FR-A4
- **Description:** Compute category percentile rank for the chosen metric at each month-end, within category and plan type, using only funds with valid metrics at that date.
- **Acceptance criteria:**
  - Ranks are computed within category and plan type only
  - Funds with null metrics are excluded and the peer count is exposed
  - A hand-computed example of five funds matches

#### MET-07 - Financial calculation tests: hand-computed and independent references

- **Status:** To Do | **Sprint:** 7 | **Priority:** Highest | **Points:** 5 | **Labels:** testing metrics
- **Linked:** FR-A4
- **Description:** Collect hand-computed test cases and independent Python reference implementations for CAGR, volatility, drawdown, XIRR and percentile rank, and compare SQL outputs against them.
- **Acceptance criteria:**
  - Each formula has at least one hand-computed example with workings in the test
  - SQL outputs agree with independent Python implementations within a stated tolerance
  - Tests run in CI against the test database

#### MET-08 - Property-based tests for metric invariants

- **Status:** To Do | **Sprint:** 7 | **Priority:** High | **Points:** 3 | **Labels:** testing property metrics
- **Linked:** FR-A4
- **Description:** Use Hypothesis to test invariants: constant NAV gives zero volatility; maximum drawdown is never positive; scaling all NAVs by a positive constant leaves percentage returns unchanged; no-flow performance agrees with price return.
- **Acceptance criteria:**
  - All four invariants are covered by property tests
  - Hypothesis settings and seeds are recorded for reproducibility
  - Property tests run under the property marker

### Epic: Review-flag engine

Configurable, explainable, as-of review-flag rule.

#### FLG-01 - Define flag configuration with validation

- **Status:** To Do | **Sprint:** 7 | **Priority:** High | **Points:** 2 | **Labels:** screening config
- **Linked:** FR-A5, US-DL-01
- **Description:** Configuration file for k, return-quartile cut-off, drawdown comparison and plan/category scope, with validation and recorded values per flag run.
- **Acceptance criteria:**
  - k, quartile cut-off and drawdown threshold are changeable without code changes
  - Invalid values (for example k less than 1) are rejected with a clear error
  - Parameters used are stored with each flag run

#### FLG-02 - Implement as-of review-flag rule

- **Status:** To Do | **Sprint:** 8 | **Priority:** Highest | **Points:** 5 | **Labels:** screening sql python
- **Linked:** FR-A5
- **Description:** Default rule: at month-end t flag a fund when its 3-year rolling return is in the bottom quartile of its category, its drawdown is worse than the category median, and both hold for k consecutive month-ends. All inputs are as of t.
- **Acceptance criteria:**
  - Given a fund meeting both conditions for k consecutive month-ends, then it is flagged at the kth month-end
  - A fund meeting the conditions for fewer than k month-ends is not flagged
  - Increasing k yields a subset of the flags produced by a smaller k
  - Funds with null inputs are not flagged and are marked not eligible

#### FLG-03 - Generate explanation text for every flag

- **Status:** To Do | **Sprint:** 8 | **Priority:** Highest | **Points:** 3 | **Labels:** screening explainability
- **Linked:** FR-A5, US-RA-03
- **Description:** Each flag row stores a structured and human-readable explanation naming the triggering conditions with values and wording that makes clear it is a research-review flag, not a recommendation.
- **Acceptance criteria:**
  - Every flag has a non-empty explanation
  - Explanation contains 3-year return, category quartile, drawdown vs category median and k count
  - Explanation text never uses buy, sell or recommend wording

#### FLG-04 - Test that flags use no future information

- **Status:** To Do | **Sprint:** 8 | **Priority:** Highest | **Points:** 3 | **Labels:** screening testing look-ahead
- **Linked:** FR-A5, US-DL-04
- **Description:** Add correctness tests that alter NAV data after month-end t and verify that metrics and flags at t are unchanged.
- **Acceptance criteria:**
  - Altering data after t does not change flags at t
  - Test covers both the metrics layer and the flag layer
  - Test failure message names the offending month-end

### Epic: Backtesting

Walk-forward evaluation, baselines, block-bootstrap CIs, limitations and RESULTS.md.

#### BT-01 - Forward 12-month return, excess return target y and time split

- **Status:** To Do | **Sprint:** 8 | **Priority:** Highest | **Points:** 3 | **Labels:** backtesting sql
- **Linked:** FR-A6
- **Description:** Compute each fund's forward 12-month return and y = fund forward return minus category median forward return. Define the chronological split (about 60% tuning, remainder out-of-sample) and record the split date.
- **Acceptance criteria:**
  - y is computed only where the full 12-month forward window exists
  - Forward returns are used only for evaluation, never for flag computation
  - Split date is recorded and the out-of-sample period starts strictly after it

#### BT-02 - Tune parameters on training period only

- **Status:** To Do | **Sprint:** 9 | **Priority:** Highest | **Points:** 3 | **Labels:** backtesting screening
- **Linked:** FR-A5, FR-A6
- **Description:** Implement parameter search (for example k and quartile cut-off) using only training-period data, store chosen parameters and the search grid, and freeze them before any out-of-sample evaluation.
- **Acceptance criteria:**
  - Tuning reads no observations after the split date
  - Chosen parameters and search grid are stored in results
  - Out-of-sample evaluation uses the frozen parameters

#### BT-03 - Baselines: bottom-quartile 1-year return and permutation random flags

- **Status:** To Do | **Sprint:** 9 | **Priority:** Highest | **Points:** 5 | **Labels:** backtesting statistics
- **Linked:** FR-A6
- **Description:** Implement Baseline 1 (bottom-quartile one-year return screen) and Baseline 2 (random flags at the same flag rate per month-end, via permutation with recorded seeds).
- **Acceptance criteria:**
  - Baseline 1 uses only 1-year return as of each month-end
  - Baseline 2 preserves the number of flags per month-end and uses a recorded seed
  - Both baselines produce results on the same evaluation set as the main rule

#### BT-04 - Fund-clustered block bootstrap and 95% confidence intervals

- **Status:** To Do | **Sprint:** 9 | **Priority:** Highest | **Points:** 5 | **Labels:** backtesting statistics
- **Linked:** FR-A6, US-DL-02
- **Description:** Implement the block bootstrap clustered by fund to account for overlapping 12-month windows and dependence, report 95% CIs for mean excess return of flagged funds and differences vs baselines. Document assumptions and block length choice.
- **Acceptance criteria:**
  - CIs are reported for the rule, both baselines and differences
  - Resampling unit and block length are documented
  - Bootstrap seed is recorded and results are reproducible
  - A synthetic known-answer test confirms the bootstrap behaves sensibly (clearly labelled synthetic)

#### BT-05 - Document survivorship bias, look-ahead and other limitations

- **Status:** To Do | **Sprint:** 9 | **Priority:** High | **Points:** 2 | **Labels:** backtesting docs
- **Linked:** FR-A6, US-DL-03
- **Description:** Write a limitations section covering survivorship bias, missing closed or merged schemes, excluded legacy categories, overlapping windows, data gaps and the limits of what the results can show. Make it available to the dashboard.
- **Acceptance criteria:**
  - Limitations text names survivorship bias and excluded closed or merged schemes
  - Text states that results do not by themselves demonstrate predictive ability
  - Text is stored once and reused by RESULTS.md and the dashboard

#### BT-06 - Backtesting correctness tests

- **Status:** To Do | **Sprint:** 9 | **Priority:** High | **Points:** 3 | **Labels:** backtesting testing
- **Linked:** FR-A6, US-DL-04
- **Description:** Test the evaluation framework: no look-ahead, correct forward-window alignment, correct train/test split, flag-rate matching for Baseline 2, and handling of funds that end before their forward window.
- **Acceptance criteria:**
  - Perturbing post-t data leaves flags and metrics at t unchanged
  - Forward-window alignment is verified on a hand-built example
  - Funds with incomplete forward windows are excluded and counted

#### BT-07 - Generate RESULTS.md and make reproduce

- **Status:** To Do | **Sprint:** 9 | **Priority:** Highest | **Points:** 3 | **Labels:** backtesting docs reproducibility
- **Linked:** NFR-1, NFR-8
- **Description:** Produce RESULTS.md from the backtest outputs and implement make reproduce so each reported figure has measured value, baseline, dataset size and evaluation period. Report negative or inconclusive outcomes as such.
- **Acceptance criteria:**
  - make reproduce regenerates every figure in RESULTS.md
  - Each figure states measured value, baseline, dataset size and evaluation period
  - Wording does not claim predictive ability unless the evidence supports it
  - Any synthetic data used is labelled

### Epic: Dashboard

Analyst dashboard: review screen, drilldown, data-quality page, backtesting page.

#### DSH-01 - Dashboard scaffold with last-refresh banner and disclosure

- **Status:** To Do | **Sprint:** 6 | **Priority:** High | **Points:** 3 | **Labels:** dashboard
- **Linked:** FR-A7, US-RA-06, US-RA-07
- **Description:** Create the dashboard app skeleton and shared layout: last successful refresh date, research-review disclosure with data limitations, and connection to a read-only database role. Framework choice recorded in DECISIONS.md.
- **Acceptance criteria:**
  - Every page shows the last successful refresh date
  - Every page shows the disclosure that flags are research-review indicators, not advice
  - Dashboard connects with a read-only database role

#### DSH-02 - Data-quality page

- **Status:** To Do | **Sprint:** 7 | **Priority:** High | **Points:** 3 | **Labels:** dashboard data-quality
- **Linked:** FR-A7, US-DO-01
- **Description:** Dashboard page showing issue counts by category, severity and resolution status, affected schemes, the last successful ingestion and latest NAV date.
- **Acceptance criteria:**
  - Counts by category, severity and status equal COUNT(*) queries on dq_issue
  - Selecting a category lists the affected schemes
  - Last successful ingestion and latest NAV date are displayed

#### DSH-03 - Fund review screen with filters, trigger reasons and CSV export

- **Status:** To Do | **Sprint:** 9 | **Priority:** Highest | **Points:** 5 | **Labels:** dashboard screening
- **Linked:** FR-A7, US-RA-01, US-RA-02, US-RA-03
- **Description:** Dashboard section A: flagged funds with category and month-end filters, trigger reasons, performance metrics and CSV export including refresh date and disclosure. Figures validated against SQL.
- **Acceptance criteria:**
  - Category and month-end filters change the list and the displayed count
  - Trigger reasons are shown for each flagged fund
  - CSV export matches the filtered rows and includes the refresh date and disclosure
  - Sampled values match the underlying SQL

#### DSH-04 - Fund drilldown with category comparison and flag timeline

- **Status:** To Do | **Sprint:** 10 | **Priority:** High | **Points:** 5 | **Labels:** dashboard metrics
- **Linked:** FR-A7, US-RA-04, US-RA-05
- **Description:** Dashboard section B: NAV history, rolling returns, volatility, drawdown, category median and quartile comparison, percentile rank, and flag timeline. Values validated against SQL.
- **Acceptance criteria:**
  - Charts show NAV, rolling CAGR, volatility and drawdown
  - Category median, quartile bounds and peer count are shown
  - Insufficient history is displayed explicitly
  - Flag timeline lists past flagged month-ends

#### DSH-05 - Backtesting page with baselines, CIs, dataset size and limitations

- **Status:** To Do | **Sprint:** 10 | **Priority:** High | **Points:** 3 | **Labels:** dashboard backtesting
- **Linked:** FR-A7, US-DL-02, US-DL-03
- **Description:** Dashboard section D: methodology, out-of-sample results, baseline comparisons, confidence intervals, dataset size, evaluation period and limitations, with inconclusive results labelled as such.
- **Acceptance criteria:**
  - Rule and both baselines are shown with 95% confidence intervals
  - Dataset size and evaluation period are displayed
  - Limitations are visible on the same page
  - Results whose intervals include zero are labelled inconclusive

### Epic: Automation and deployment

CI, monthly GitHub Actions refresh, refresh report, hosting and publication.

#### AUT-01 - Add CI workflow running ruff and unit tests

- **Status:** To Do | **Sprint:** 3 | **Priority:** Medium | **Points:** 2 | **Labels:** ci github-actions
- **Linked:** NFR-7
- **Description:** GitHub Actions workflow that runs ruff and the unit tests on push and pull request. Integration tests are added once a service container is configured.
- **Acceptance criteria:**
  - Workflow runs on push and pull request
  - A lint error or failing unit test turns the run red
  - No secrets are required by this workflow

#### AUT-02 - Document hosting strategy for remote scheduled PostgreSQL

- **Status:** To Do | **Sprint:** 5 | **Priority:** Medium | **Points:** 2 | **Labels:** docs deployment security
- **Linked:** FR-A8, NFR-5
- **Description:** Evaluate free-tier hosted PostgreSQL options, document how GitHub Actions will connect (secrets, network access, SSL), the data-loading approach and the fallback of local-only reproduction.
- **Acceptance criteria:**
  - Options, costs and constraints are compared in writing
  - A chosen approach is recorded in DECISIONS.md
  - Secrets handling is described and no secret values are stored in the repository

#### AUT-03 - Create monthly_refresh.yml workflow (scheduled and manual)

- **Status:** To Do | **Sprint:** 8 | **Priority:** High | **Points:** 3 | **Labels:** automation github-actions
- **Linked:** FR-A8, US-DO-04
- **Description:** GitHub Actions workflow with monthly cron and manual dispatch: retrieve latest NAV, load, run DQ checks, fail when critical issues exist. Uses repository secrets for the database; extended later with analytics refresh and report.
- **Acceptance criteria:**
  - Workflow is triggered by schedule and workflow_dispatch
  - A simulated critical issue makes the run fail
  - Database credentials are read from repository secrets only

#### AUT-04 - Orchestrate end-to-end refresh with critical-failure gate

- **Status:** To Do | **Sprint:** 10 | **Priority:** High | **Points:** 3 | **Labels:** automation pipeline
- **Linked:** FR-A3, FR-A8
- **Description:** Single pipeline command: ingest, validate, load, DQ checks, gate, refresh metrics, flags and backtest outputs. Wire it into the monthly workflow.
- **Acceptance criteria:**
  - One command runs all stages in order
  - Pipeline stops before analytics when a critical issue exists
  - Workflow calls the same command used locally

#### AUT-05 - Generate refresh report

- **Status:** To Do | **Sprint:** 10 | **Priority:** Medium | **Points:** 2 | **Labels:** automation reporting
- **Linked:** FR-A8, US-DO-07
- **Description:** Produce a refresh report (rows downloaded, loaded, rejected, issues by severity, duration, status) and upload as a workflow artefact, including on failure.
- **Acceptance criteria:**
  - Report contains row counts, issue counts by severity, duration and status
  - Report is produced on failure and states the reason
  - Report is uploaded as a workflow artefact

#### AUT-06 - Publish dashboard and record last-refresh metadata

- **Status:** To Do | **Sprint:** 10 | **Priority:** Low | **Points:** 3 | **Labels:** deployment dashboard
- **Linked:** FR-A7, NFR-5, NFR-6
- **Description:** Choose a hosting option for the dashboard, publish it with a read-only database connection and expose last successful refresh date. Only publish derived data permitted by the licensing review.
- **Acceptance criteria:**
  - Published dashboard shows last successful refresh date and disclosure
  - Published data respects the AMFI terms review in DATA_CARD
  - No secrets are present in the repository or client-side code

### Epic: Documentation and testing

BRD, user stories, data card, results documentation, test harness and honesty review.

#### DOC-01 - Draft Phase 0 documents: BRD, user stories and backlog export

- **Status:** Done | **Sprint:** 1 | **Priority:** Medium | **Points:** 3 | **Labels:** docs phase0
- **Linked:** All FR
- **Description:** Draft docs/BRD.md, docs/USER_STORIES.md and the JIRA backlog export (this file set). Drafts only; they will be revised as implementation proceeds. DATA_CARD, ARCHITECTURE and DECISIONS are separate stories.
- **Acceptance criteria:**
  - BRD contains all sections required by the master prompt and an RTM
  - User stories cover Research Analyst, Desk Lead and Data Operations with acceptance criteria
  - Backlog export lists ten epics and sprinted stories and states that no JIRA tickets exist

#### DOC-02 - Create test database fixture and pytest markers

- **Status:** To Do | **Sprint:** 3 | **Priority:** High | **Points:** 3 | **Labels:** testing postgres
- **Linked:** NFR-7
- **Description:** Provide a pytest fixture that creates an isolated test database or schema, applies migrations and tears down without touching development data. Add markers for unit, integration and property tests.
- **Acceptance criteria:**
  - Integration tests run against an isolated database, not the development data
  - Fixture applies migrations 001-004 and cleans up after the session
  - Markers allow running unit, integration and property tests separately

#### DOC-03 - Write DATA_CARD.md (source, retrieval, dictionary, licensing, gaps)

- **Status:** To Do | **Sprint:** 3 | **Priority:** High | **Points:** 3 | **Labels:** docs data licensing
- **Linked:** NFR-6
- **Description:** Create docs/DATA_CARD.md covering AMFI as source, retrieval method and date, data dictionary, licensing and terms-of-use findings, known gaps and limitations (including survivorship). Read and cite AMFI terms before any publication of data.
- **Acceptance criteria:**
  - Source URL, retrieval method and retrieval date are stated
  - Every ingested field appears in a data dictionary
  - AMFI terms-of-use conclusion is recorded and states what may and may not be redistributed
  - Known gaps list includes pre-2006 history, excluded legacy categories and missing closed or merged schemes

#### DOC-04 - Final documentation, honesty review and pre-publication checks

- **Status:** To Do | **Sprint:** 10 | **Priority:** High | **Points:** 5 | **Labels:** docs honesty review
- **Linked:** NFR-8, BO-6
- **Description:** Finalise README, ARCHITECTURE, DECISIONS, DATA_CARD, BRD RTM statuses and USER_STORIES; check no secrets are committed; check claims against the honesty rules (no real clients, AUM or users; no production-grade or GIPS-compliant claims; every resume statement supported by RESULTS.md).
- **Acceptance criteria:**
  - BRD traceability matrix statuses match actual repository state
  - Secret scan finds no credentials in the repository history
  - Text search finds no claim of real clients, AUM, users, production-grade or GIPS compliance
  - Every metric quoted in the README appears in RESULTS.md
