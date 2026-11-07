-- Business question: Within each category, which schemes had the best and the worst 3-year
-- CAGR at the latest month-end, and how far are they from the category median?
-- (Analyst screening aid only - past performance, not a recommendation.)
-- Demonstrates: parameter CTE, window ranking (rank, dense_rank, row_number) per category,
--               top/bottom-N with ties, join mart -> dim_scheme.
-- Parameters: edit the `params` CTE (plan type, month-end, N). Default month-end = latest
--             month-end that has a 3y CAGR in the mart.
WITH params AS (
    SELECT 'DIRECT'::text AS plan_type,
           (SELECT max(me_date) FROM marts.mv_scheme_month_metrics WHERE cagr_3y IS NOT NULL) AS as_of,
           3 AS top_n
), ranked AS (
    SELECT m.category, m.me_date, m.scheme_id, s.amfi_code, s.scheme_name, s.amc_name,
           m.cagr_3y, m.median_cagr_3y, m.peers_3y,
           rank()       OVER (PARTITION BY m.category ORDER BY m.cagr_3y DESC) AS rank_top,
           dense_rank() OVER (PARTITION BY m.category ORDER BY m.cagr_3y DESC) AS dense_rank_top,
           rank()       OVER (PARTITION BY m.category ORDER BY m.cagr_3y ASC)  AS rank_bottom,
           row_number() OVER (PARTITION BY m.category ORDER BY m.cagr_3y DESC, s.scheme_id) AS row_top
    FROM marts.mv_scheme_month_metrics m
    JOIN core.dim_scheme s USING (scheme_id)
    JOIN params p ON m.me_date = p.as_of AND m.plan_type = p.plan_type
    WHERE m.cagr_3y IS NOT NULL
      AND s.option_type = 'GROWTH'
)
SELECT r.category,
       CASE WHEN r.rank_top <= p.top_n THEN 'TOP' ELSE 'BOTTOM' END AS bucket,
       r.rank_top, r.dense_rank_top, r.rank_bottom,
       r.amfi_code, r.scheme_name, r.amc_name,
       round((r.cagr_3y * 100)::numeric, 2)                    AS cagr_3y_pct,
       round((r.median_cagr_3y * 100)::numeric, 2)             AS category_median_pct,
       round(((r.cagr_3y - r.median_cagr_3y) * 100)::numeric, 2) AS spread_vs_median_pp,
       r.peers_3y, r.me_date
FROM ranked r
CROSS JOIN params p
WHERE r.rank_top <= p.top_n OR r.rank_bottom <= p.top_n
ORDER BY r.category, r.rank_top, r.row_top;
