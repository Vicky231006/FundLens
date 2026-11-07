-- Business question: How do categories compare with each other over time? At each year-end,
-- what was the median 3-year CAGR per category, how did it change versus the previous
-- year-end, and how did the categories rank?
-- Demonstrates: parameter CTE, percentile_cont, FILTER aggregates, lag (year-over-year change),
--               dense_rank across categories per year-end, HAVING for minimum peer count.
-- Parameters: edit `params` (plan type, look-back years, min schemes per category).
-- Notes: year-end = the December month-end, plus the latest month-end of the mart (so the
--        current partial year is visible). prev_me_date shows which row the change is against.
WITH params AS (
    SELECT 'DIRECT'::text AS plan_type, 10 AS lookback_years, 3 AS min_peers,
           (SELECT max(me_date) FROM marts.mv_scheme_month_metrics) AS latest_me
), pts AS (
    SELECT m.category, m.me_date,
           count(m.cagr_3y)                                              AS n_with_cagr_3y,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY m.cagr_3y)         AS median_cagr_3y,
           avg(m.volatility_1y)                                           AS avg_vol_1y,
           count(*) FILTER (WHERE m.cagr_1y < 0)::numeric
               / nullif(count(m.cagr_1y), 0)                              AS share_negative_1y
    FROM marts.mv_scheme_month_metrics m
    JOIN params p ON m.plan_type = p.plan_type
                 AND m.me_date > p.latest_me - make_interval(years => p.lookback_years)
                 AND (extract(month FROM m.me_date) = 12 OR m.me_date = p.latest_me)
    GROUP BY m.category, m.me_date, p.min_peers
    HAVING count(m.cagr_3y) >= p.min_peers
)
SELECT t.me_date, t.category, t.n_with_cagr_3y,
       round((t.median_cagr_3y * 100)::numeric, 2)                              AS median_cagr_3y_pct,
       lag(t.me_date) OVER w                                                     AS prev_me_date,
       round(((t.median_cagr_3y - lag(t.median_cagr_3y) OVER w) * 100)::numeric, 2) AS change_vs_prev_pp,
       dense_rank() OVER (PARTITION BY t.me_date ORDER BY t.median_cagr_3y DESC)  AS rank_in_period,
       round((t.avg_vol_1y * 100)::numeric, 2)                                    AS avg_vol_1y_pct,
       round(t.share_negative_1y, 3)                                              AS share_negative_1y
FROM pts t
WINDOW w AS (PARTITION BY t.category ORDER BY t.me_date)
ORDER BY t.me_date, rank_in_period, t.category;
