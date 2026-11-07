-- Business question: Which schemes published the identical NAV for many consecutive market
-- days (a "stale" NAV - frozen feed, suspended scheme, or data error) in the recent window,
-- and which are the longest runs per category?
-- Demonstrates: parameter CTE, gaps-and-islands with a market-day index, row_number,
--               dense_rank per category, joins fact_nav + market_day + dim_scheme.
-- Parameters: `params.window_years` (look-back from the dataset's latest NAV date) and
--             `params.min_run` (consecutive market days with the same NAV to report).
-- Technique: within (scheme, nav) the difference mday_idx - row_number() is constant exactly
--            for NAVs on consecutive market days, so grouping by it finds each run.
-- Caveat: a flat NAV can be legitimate right after launch or for a closed scheme; investigate
--         before concluding it is an error.
WITH params AS (
    SELECT (SELECT max(nav_date) FROM core.fact_nav) AS d_max, 2 AS window_years, 5 AS min_run
), obs AS (
    SELECT f.scheme_id, f.nav_date, f.nav, md.mday_idx
    FROM core.fact_nav f
    JOIN core.market_day md ON md.cal_date = f.nav_date AND md.is_market_day
    CROSS JOIN params p
    WHERE f.nav_date > p.d_max - make_interval(years => p.window_years)
), islands AS (
    SELECT o.*, o.mday_idx - row_number() OVER (PARTITION BY o.scheme_id, o.nav ORDER BY o.nav_date) AS grp
    FROM obs o
), runs AS (
    SELECT i.scheme_id, i.nav, min(i.nav_date) AS run_start, max(i.nav_date) AS run_end,
           count(*) AS market_days_flat
    FROM islands i
    GROUP BY i.scheme_id, i.nav, i.grp
), ranked AS (
    SELECT r.*, s.amfi_code, s.scheme_name, s.category, s.plan_type,
           dense_rank() OVER (PARTITION BY s.category ORDER BY r.market_days_flat DESC) AS rank_in_category,
           row_number() OVER (ORDER BY r.market_days_flat DESC, r.run_end DESC) AS overall_row
    FROM runs r
    JOIN core.dim_scheme s USING (scheme_id)
    CROSS JOIN params p
    WHERE r.market_days_flat >= p.min_run
)
SELECT category, plan_type, amfi_code, scheme_name, nav AS repeated_nav,
       run_start, run_end, market_days_flat, rank_in_category,
       (run_end = (SELECT max(nav_date) FROM core.fact_nav)) AS run_is_ongoing_at_dataset_end
FROM ranked
ORDER BY market_days_flat DESC, run_end DESC, amfi_code
LIMIT 200;
