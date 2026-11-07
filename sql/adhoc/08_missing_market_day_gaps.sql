-- Business question: Which schemes have gaps in their NAV history - market days on which the
-- scheme published nothing although it published before and after - and have those gaps
-- already been logged in core.dq_issue?
-- Demonstrates: parameter CTE, lag() over a per-scheme market-day index, window sum/rank per
--               scheme, LEFT JOIN to the DQ log via JSONB, 3-table join
--               (fact_nav, market_day, dim_scheme).
-- Parameters: `params.window_years` (look-back from latest NAV date), `params.min_gap`
--             (minimum number of missing market days to report).
-- Notes: market days are derived from the data itself (>= 50% of active schemes published),
--        see sql/migrations/005_market_day.sql. The first observation in the window has no
--        predecessor, so a gap straddling the window start is not reported.
WITH params AS (
    SELECT (SELECT max(nav_date) FROM core.fact_nav) AS d_max, 3 AS window_years, 3 AS min_gap
), obs AS (
    SELECT f.scheme_id, f.nav_date, md.mday_idx
    FROM core.fact_nav f
    JOIN core.market_day md ON md.cal_date = f.nav_date AND md.is_market_day
    CROSS JOIN params p
    WHERE f.nav_date > p.d_max - make_interval(years => p.window_years)
), lagged AS (
    SELECT o.scheme_id, o.nav_date,
           lag(o.nav_date) OVER w AS prev_date,
           o.mday_idx - lag(o.mday_idx) OVER w - 1 AS missing_market_days
    FROM obs o
    WINDOW w AS (PARTITION BY o.scheme_id ORDER BY o.nav_date)
), gaps AS (
    SELECT l.*,
           sum(l.missing_market_days) OVER (PARTITION BY l.scheme_id) AS scheme_total_missing,
           count(*) OVER (PARTITION BY l.scheme_id)                    AS scheme_gap_count
    FROM lagged l
    CROSS JOIN params p
    WHERE l.missing_market_days >= p.min_gap
)
SELECT dense_rank() OVER (ORDER BY g.scheme_total_missing DESC, g.scheme_id) AS scheme_rank,
       s.amfi_code, s.scheme_name, s.category, s.plan_type,
       g.prev_date AS last_nav_before_gap, g.nav_date AS next_nav_after_gap,
       g.missing_market_days, g.scheme_gap_count, g.scheme_total_missing,
       i.severity AS dq_severity, i.resolution_status AS dq_status,
       (i.issue_id IS NOT NULL) AS logged_in_dq_issue
FROM gaps g
JOIN core.dim_scheme s USING (scheme_id)
LEFT JOIN core.dq_issue i
       ON i.scheme_id = g.scheme_id
      AND i.issue_category = 'MISSING_BUSINESS_DAY'
      AND i.observation ->> 'last_nav_before_gap' = g.prev_date::text
ORDER BY scheme_rank, g.prev_date
LIMIT 300;
