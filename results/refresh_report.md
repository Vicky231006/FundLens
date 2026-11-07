# FundLens refresh report

- Started: 2026-11-07T13:58:41.906590+00:00
- Runtime: 238.9 s
- Latest NAV date: 2026-11-06
- NAV rows: 1,811,703; schemes: 779
- Source files: 85

## Data-quality issues detected this run

| Check | Detected |
|---|---:|
| NON_POSITIVE_NAV | 252 |
| FUTURE_DATED_NAV | 0 |
| MISSING_BUSINESS_DAY | 1246 |
| ABNORMAL_NAV_MOVE | 79 |
| STALE_NAV | 30 |
| DUPLICATE_SCHEME_DATE | 0 |
| NAV_REVISION | 0 |
| INVALID_SCHEME_ID | 0 |
| INVALID_DATE | 0 |
| UNEXPECTED_DATA_TYPE | 13 |
| INGESTION_REJECT_RATE | 0 |
| LOW_COVERAGE_DAY | 18 |
| STALE_DATASET | 0 |

## Marts build (seconds)

| File | Seconds |
|---|---:|
| 010_functions.sql | 0.01 |
| 020_scheme_month_metrics.sql | 131.98 |
| 030_forward_return.sql | 0.68 |
| 040_dashboard_views.sql | 0.02 |

Critical data-quality gate: **passed** (the pipeline stops before this point otherwise).
