# FundLens task runner. On Windows without GNU make use `.\make.ps1 <target>` (same targets).
PY ?= .venv/Scripts/python
ifeq ($(OS),Windows_NT)
else
PY = .venv/bin/python
endif

.PHONY: help setup db-up db-down migrate ingest dq marts pipeline test test-unit lint format reproduce clean-results

help:
	@echo "setup        create venv and install dependencies"
	@echo "db-up        start PostgreSQL 16 (docker compose)"
	@echo "migrate      apply SQL migrations"
	@echo "ingest       download AMFI NAV history and load it (idempotent, date-chunked)"
	@echo "dq           run data-quality checks (exit 2 on unresolved CRITICAL issues)"
	@echo "pipeline     DQ gate -> marts -> screening -> backtest -> RESULTS.md"
	@echo "test         run all tests (needs the database for integration tests)"
	@echo "reproduce    migrate + ingest + pipeline: regenerates every number in RESULTS.md"

setup:
	python -m venv .venv
	$(PY) -m pip install -e ".[dev]"

db-up:
	docker compose up -d db

db-down:
	docker compose down

migrate:
	$(PY) -m fundlens.cli migrate

ingest:
	$(PY) -m fundlens.cli ingest

dq:
	$(PY) -m fundlens.cli dq

marts:
	$(PY) -m fundlens.cli build-marts

pipeline:
	$(PY) -m fundlens.cli pipeline

test-unit:
	$(PY) -m pytest tests/unit tests/property -q

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check src tests
	$(PY) -m ruff format --check src tests

format:
	$(PY) -m ruff format src tests

# One command that regenerates RESULTS.md from AMFI source data. Seeds are fixed in
# fundlens.backtesting.walkforward.BacktestConfig, so identical source files give identical numbers.
reproduce: db-up migrate ingest pipeline
	@echo "Done. See RESULTS.md and results/."
