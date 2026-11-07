"""FundLens command line: ``fundlens <command>``."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from fundlens.db import apply_migrations, connect
from fundlens.ingestion.loader import ingest_range, refresh_calendar_flags, verify_raw_files
from fundlens.metrics.build import build_marts
from fundlens.validation.dq import critical_issues, run_checks


def _date(text: str) -> date:
    return date.fromisoformat(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fundlens", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="apply SQL migrations")

    ing = sub.add_parser("ingest", help="download AMFI NAV history and load it (idempotent)")
    ing.add_argument("--from", dest="start", type=_date, help="YYYY-MM-DD (default: scope start)")
    ing.add_argument("--to", dest="end", type=_date, help="YYYY-MM-DD (default: today)")
    ing.add_argument("--force-refetch", action="store_true", help="re-download settled chunks")

    sub.add_parser("verify-raw", help="re-hash preserved raw files against the registry")
    sub.add_parser("refresh-calendar", help="rebuild the data-derived market-day calendar")
    sub.add_parser("build-marts", help="(re)build SQL analytical views from sql/marts")
    sub.add_parser(
        "pipeline",
        help="DQ gate -> marts -> screening -> backtest -> RESULTS.md (exit 2 on CRITICAL DQ)",
    )
    sub.add_parser("dq", help="run data-quality checks; exit 2 if CRITICAL issues are unresolved")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.command == "migrate":
        applied = apply_migrations()
        print("Applied:", ", ".join(applied) if applied else "nothing (up to date)")
    elif args.command == "ingest":
        print(ingest_range(args.start, args.end, force_refetch=args.force_refetch))
    elif args.command == "refresh-calendar":
        with connect(autocommit=True) as conn:
            refresh_calendar_flags(conn)
        print("core.market_day rebuilt")
    elif args.command == "build-marts":
        with connect(autocommit=True) as conn:
            for name, secs in build_marts(conn).items():
                print(f"{name:<40}{secs:>8.2f}s")
    elif args.command == "pipeline":
        from fundlens.pipeline import run_pipeline
        from fundlens.validation.dq import CriticalDataQualityError

        with connect(autocommit=True) as conn:
            try:
                rep = run_pipeline(conn)
            except CriticalDataQualityError as exc:
                print(f"PIPELINE STOPPED: {exc}", file=sys.stderr)
                return 2
        print(f"Pipeline complete in {rep['pipeline_seconds']}s; wrote RESULTS.md and results/")
    elif args.command == "dq":
        with connect(autocommit=True) as conn:
            counts = run_checks(conn)
            for cat, n in counts.items():
                print(f"{cat:<26}{n:>8}")
            crit = critical_issues(conn)
        if crit:
            print(f"\n{len(crit)} unresolved CRITICAL issue(s) - analytics pipeline must stop.")
            return 2
    elif args.command == "verify-raw":
        with connect() as conn:
            problems = verify_raw_files(conn)
        print("\n".join(problems) if problems else "All raw files match their registered SHA-256.")
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
