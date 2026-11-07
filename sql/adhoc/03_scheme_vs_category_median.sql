-- Business question: For one category, how does every scheme compare with the category median
-- on 3-year CAGR and 3-year max drawdown, and which quartile is it in?
-- (Analyst screening aid only - not investment advice.)
-- Demonstrates: parameter CTE, percent_rank, ntile, comparison with a precomputed median
--               column, CASE labelling, join mart -> dim_scheme.
-- Parameters: edit `params` (category, plan type, month-end). Default month-end = latest
--             month-end in the mart with a 3y CAGR.
-- Reading the output: spread_cagr_pp > 0 = better than median; dd_vs_median_pp > 0 = shallower
--             drawdown than median (drawdowns are negative numbers). Quartile 1 = best CAGR.
WITH params AS (
    SELECT 'Mid Cap'::text AS category,
           'DIRECT'::text  AS plan_type,
           (SELECT max(me_date) FROM marts.mv_scheme_month_metrics WHERE cagr_3y IS NOT NULL) AS as_of
), cohort AS (
    SELECT m.*, s.amfi_code, s.scheme_name, s.amc_name
    FROM marts.mv_scheme_month_metrics m
    JOIN core.dim_scheme s USING (scheme_id)
    JOIN params p ON m.me_date = p.as_of AND m.category = p.category AND m.plan_type = p.plan_type
    WHERE m.cagr_3y IS NOT NULL AND s.option_type = 'GROWTH'
)
SELECT c.me_date, c.amfi_code, c.scheme_name, c.amc_name,
       round((c.cagr_3y * 100)::numeric, 2)                          AS cagr_3y_pct,
       round((c.median_cagr_3y * 100)::numeric, 2)                   AS median_cagr_3y_pct,
       round(((c.cagr_3y - c.median_cagr_3y) * 100)::numeric, 2)     AS spread_cagr_pp,
       round(percent_rank() OVER (ORDER BY c.cagr_3y)::numeric, 3)   AS pct_rank_recomputed,
       round(c.pct_rank_cagr_3y::numeric, 3)                         AS pct_rank_in_mart,
       ntile(4) OVER (ORDER BY c.cagr_3y DESC)                       AS cagr_quartile,
       round((c.max_drawdown_3y * 100)::numeric, 2)                  AS max_dd_3y_pct,
       round((c.median_max_drawdown_3y * 100)::numeric, 2)           AS median_max_dd_3y_pct,
       round(((c.max_drawdown_3y::double precision - c.median_max_drawdown_3y) * 100)::numeric, 2)
                                                                     AS dd_vs_median_pp,
       CASE WHEN c.cagr_3y >= c.median_cagr_3y AND c.max_drawdown_3y::double precision >= c.median_max_drawdown_3y
                THEN 'above-median return, shallower drawdown'
            WHEN c.cagr_3y >= c.median_cagr_3y THEN 'above-median return, deeper drawdown'
            WHEN c.max_drawdown_3y::double precision >= c.median_max_drawdown_3y
                THEN 'below-median return, shallower drawdown'
            ELSE 'below-median return, deeper drawdown' END          AS profile,
       c.peers_3y
FROM cohort c
ORDER BY c.cagr_3y DESC;
