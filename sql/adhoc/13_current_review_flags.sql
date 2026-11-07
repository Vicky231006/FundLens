-- Business question: Which funds are currently carrying a research-review flag (latest
-- screening run per plan type, latest month-end), why, and how do their trailing numbers look?
-- A review flag is a prompt to look closer - it is NOT advice to buy, sell or hold.
-- Demonstrates: DISTINCT ON to pick the latest run per plan type (highest run_id), joins across
--               review_flag, screening_run, dim_scheme and the metrics mart (4 tables),
--               row_number ranking per category, explanation text.
-- Notes: "currently flagged" = a flag row at the latest month-end present in
--        marts.mv_scheme_month_metrics. If screening has not been run, or nothing is flagged
--        at that month-end, the result is empty.
WITH latest_run AS (
    SELECT DISTINCT ON (sr.plan_type) sr.run_id, sr.plan_type, sr.label, sr.created_at
    FROM marts.screening_run sr
    ORDER BY sr.plan_type, sr.run_id DESC
), latest_me AS (
    SELECT max(me_date) AS me_date FROM marts.mv_scheme_month_metrics
)
SELECT lr.plan_type, lr.run_id, lr.label AS run_label,
       s.category, s.amfi_code, s.scheme_name, s.amc_name,
       rf.me_date, rf.streak_months,
       row_number() OVER (PARTITION BY lr.plan_type, s.category
                          ORDER BY rf.streak_months DESC, rf.pct_rank_cagr_3y, s.scheme_id) AS rank_in_category_by_streak,
       round((rf.cagr_3y * 100)::numeric, 2)                  AS cagr_3y_pct,
       round(rf.pct_rank_cagr_3y::numeric, 3)                 AS pct_rank_cagr_3y,
       round((rf.max_drawdown_3y * 100)::numeric, 2)          AS max_dd_3y_pct,
       round((rf.median_max_drawdown_3y * 100)::numeric, 2)   AS median_max_dd_3y_pct,
       rf.peers_3y,
       round((m.cagr_1y * 100)::numeric, 2)                   AS cagr_1y_pct,
       round((m.volatility_1y * 100)::numeric, 2)             AS volatility_1y_pct,
       rf.explanation
FROM latest_run lr
CROSS JOIN latest_me lm
JOIN marts.review_flag rf ON rf.run_id = lr.run_id AND rf.me_date = lm.me_date
JOIN core.dim_scheme s ON s.scheme_id = rf.scheme_id
LEFT JOIN marts.mv_scheme_month_metrics m ON m.scheme_id = rf.scheme_id AND m.me_date = rf.me_date
ORDER BY lr.plan_type, s.category, rank_in_category_by_streak;
