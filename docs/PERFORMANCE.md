# Performance measurements

Measured 2026-11-07 14:05 UTC on the developer machine (Docker Desktop PostgreSQL 16, single user) by `scripts/measure_performance.py`. Median of 15 runs after one warm-up. Absolute times depend on the machine; the with/without ratio is the useful figure.

## Dataset size used for every figure below

| Item | Count |
|---|---:|
| fact_nav rows | 1,811,703 |
| schemes | 779 |
| month-end metric rows | 88,300 |
| raw.nav_line rows | 1,845,630 |
| dq_issue rows | 1,638 |

## Query latency, with and without the index

"Without" = index dropped inside a rolled-back transaction (database unchanged).

| Query | Index | With (ms) | Without (ms) | Slowdown without | Plan with | Plan without |
|---|---|---:|---:|---:|---|---|
| Fund review: one category at the latest month-end | `ix_mv_metrics_cat_date` | 1.97 | 2.62 | 1.3x | Index Scan using ix_mv_metrics_date on mv_scheme_month_metrics  (cost=0.29..41.00 rows=35  | Index Scan using ix_mv_metrics_date on mv_scheme_month_metrics  (cost=0.29..41.00 rows=35  |
| Fund drilldown: one scheme's month-end series | `ux_mv_metrics` | 2.81 | 14.16 | 5.0x | ->  Bitmap Heap Scan on mv_scheme_month_metrics  (cost=6.40..735.49 rows=256 width=24) | ->  Seq Scan on mv_scheme_month_metrics  (cost=0.00..3279.75 rows=256 width=24) |
| All NAVs published on one date | `ix_fact_nav_date` | 2.93 | 47.23 | 16.1x | Index Scan using ix_fact_nav_date on fact_nav  (cost=0.43..260.16 rows=369 width=14) | ->  Parallel Seq Scan on fact_nav  (cost=0.00..24533.83 rows=154 width=14) |
| Open ERROR/CRITICAL issues | `ix_dq_issue_open_severity` | 0.92 | 1.40 | 1.5x | ->  Index Scan using ix_dq_issue_open_severity on dq_issue  (cost=0.28..97.30 rows=260 wid | ->  Seq Scan on dq_issue  (cost=0.00..175.57 rows=260 width=19) |
| NAV history of one scheme (primary key) | `fact_nav_pkey` | 11.19 | 55.74 | 5.0x | ->  Bitmap Heap Scan on fact_nav  (cost=122.34..10354.12 rows=4892 width=10) | ->  Parallel Seq Scan on fact_nav  (cost=0.00..24533.83 rows=2038 width=10) |

## Materialised view refresh

`REFRESH MATERIALIZED VIEW` of `mv_scheme_month_end_nav` + `mv_scheme_month_metrics`: **129.9 s** (88,300 output rows).

## Ingestion runs (most recent successful)

| Started | Finished | Files fetched | New files | NAV rows loaded |
|---|---|---:|---:|---:|
| 2026-11-07 11:30 | 2026-11-07 13:29 | 84 | 84 | 1,777,789 |
| 2026-11-07 11:27 | 2026-11-07 11:27 | 1 | 0 | 0 |
| 2026-11-07 11:27 | 2026-11-07 11:27 | 0 | 0 | 0 |
