# Ad-hoc analyst queries

Read-only `SELECT` queries for analysts exploring FundLens. Nothing here is investment advice;
review flags and rankings are research prompts. Each file starts with its business question and
the SQL techniques it demonstrates. Parameters live in a labelled `params` CTE at the top of a file.

Run one with e.g. `psql -U fundlens -d fundlens -f sql/adhoc/02_top_bottom_3y_cagr_by_category.sql`.

Queries return few or zero rows while the database is only partially loaded or while a mart or
screening run has not been built yet.

| # | File | Business question |
|---|------|-------------------|
| 01 | `01_dataset_profile_by_year.sql` | How many Direct/Regular schemes per category were active, new or ceased in each year, and how many market days did the year have? |
| 02 | `02_top_bottom_3y_cagr_by_category.sql` | Which schemes are best/worst on 3y CAGR in each category at the latest month-end, and how far from the category median? |
| 03 | `03_scheme_vs_category_median.sql` | For one category, how does each scheme compare with the median on 3y CAGR and 3y max drawdown (quartile, percent rank)? |
| 04 | `04_category_vs_category_trend.sql` | How do category median 3y CAGRs compare at each year-end, how did they change, and how do categories rank? |
| 05 | `05_direct_vs_regular_same_family.sql` | For safely matched Direct/Regular pairs of the same fund (AMC + normalised name, an assumption, not an official mapping), how do trailing returns differ? |
| 06 | `06_survivorship_check.sql` | Which schemes stopped publishing well before the dataset end, and what share of each category/plan group is that? |
| 07 | `07_stale_nav_runs.sql` | Which schemes published an identical NAV for many consecutive market days? |
| 08 | `08_missing_market_day_gaps.sql` | Which schemes have missing market days inside their history, and are the gaps logged in `core.dq_issue`? |
| 09 | `09_abnormal_nav_moves.sql` | Which large single-observation NAV moves deviate from the category's same-day median move (possible corporate action or data error)? |
| 10 | `10_dq_findings_and_conflicts.sql` | What is the DQ picture by category/severity/status, and have re-downloads disagreed with stored NAVs? |
| 11 | `11_renamed_schemes.sql` | Which AMFI codes were published under several names, and are explicit mappings recorded? |
| 12 | `12_category_monthly_returns_rolling.sql` | For one category, what are the median month-over-month return, rolling 12m return and drawdown of the chained median-fund path? |
| 13 | `13_current_review_flags.sql` | Which funds carry a review flag in the latest run/month-end, with the explanation text and trailing metrics? |
| 14 | `14_flag_persistence_streaks.sql` | How persistent are flags: months flagged, episodes, longest episode, gaps before re-flagging, flagged now? |
| 15 | `15_flag_vs_forward_return_eval.sql` | **Evaluation only (uses forward-looking `mv_forward_return_12m`).** Did flagged schemes do better or worse than peers over the next 12 months? |
| 16 | `16_ingestion_file_coverage.sql` | Is the raw download history complete: ranges, gaps/overlaps, malformed lines, NAV rows landed per file? |
