# Project Management — FundLens (Jira)

This document maps FundLens planned requirements to **Atlassian Jira**. Per project rules: the **Jira backlog** is the source of planned requirements; the **repository, executable code, and automated tests** are the source of truth for implementation completion. Jira status is updated only when actual implementation progress supports it (never marked Done until all acceptance criteria are verified in Jira). This file records the mapping provided for the project; it does **not** imply Jira was updated by this commit.

## Jira workspace / project

| Field | Value |
|---|---|
| Workspace | https://bickyboi09.atlassian.net |
| Project | FundLens |
| Project key | **FNDL** |
| Project URL / backlog | https://bickyboi09.atlassian.net/jira/software/projects/FNDL/boards/2/backlog |
| Board | FNDL board |
| Workflow (as provided) | To Do, In Progress, Done |

## Epics (10)

| Key | Epic |
|---|---|
| FNDL-1 | Infrastructure & Architecture |
| FNDL-2 | AMFI Data Ingestion |
| FNDL-3 | PostgreSQL Database Engineering |
| FNDL-4 | Data Quality Framework |
| FNDL-5 | Financial Metrics Engine |
| FNDL-6 | Review-Flag Algorithm |
| FNDL-7 | Walk-Forward Backtesting |
| FNDL-8 | Power BI Dashboard |
| FNDL-9 | Automation & Deployment |
| FNDL-10 | Documentation & Testing |

## Stories

- **27 implementation stories** created under these epics: **FNDL-11 through FNDL-37**.
- Every story has a description and acceptance criteria (confirm details/AC in Jira; not duplicated here to avoid drift).

## Sprint

| Sprint | State | Stories |
|---|---|---|
| FNDL Sprint 1 | Future (not started) | FNDL-11, FNDL-12, FNDL-13, FNDL-14 |

**Sprint 1 scope (as provided):**
1. **FNDL-11** — Establish local PostgreSQL development environment.
2. **FNDL-12** — Create Python package, virtual environment and developer tooling.
3. **FNDL-13** — Document FundLens architecture and technical decisions.
4. **FNDL-14** — Verify AMFI historical NAV access and publish data card.

## Repository

- GitHub: https://github.com/Vicky231006/FundLens.git (remote `origin` configured locally)

## Evidence pointers (repo)

- Environment/DB: `docker-compose.yml`, `.env.example`, `db.py`, `make.ps1`/`Makefile`
- Package/tooling: `pyproject.toml`, `src/fundlens/` (CLI, ingestion, validation, metrics, screening, backtesting, pipeline), `tests/`, `ruff`/`pytest` config
- Architecture/decisions: `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`
- AMFI/data card: `docs/DATA_CARD.md`, `config/scope.toml`, `src/fundlens/ingestion/`
- Project history: `DEVELOPMENT_LOG.md`, `TODO.md`, `README.md`, `RESULTS.md`, `docs/PERFORMANCE.md`
- Dashboard: `dashboard/FundLens/` (PBIP + semantic model targeting PostgreSQL `marts.dash_*`)

*Last updated in-repo:* 2026-11-08 (audit against Sprint 1 scope; verify current Jira statuses/AC in Jira).