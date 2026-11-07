-- Business question: For one category, what is the typical month-over-month return, the rolling
-- 12-month return of the "median fund", and how deep has that category-level path fallen from
-- its running peak?
-- Demonstrates: parameter CTE, lag() for month-over-month returns, percentile_cont,
--               FILTER aggregate, rolling window (ROWS BETWEEN 11 PRECEDING), running sum of
--               log returns (chain-linking), running max for drawdown.
-- Parameters: `params` (category, plan type, months of history).
-- Method/assumptions: month-end NAVs from marts.mv_scheme_month_end_nav; a monthly return is
--   only used when the scheme also has the immediately preceding month-end. The "category
--   path" chains each month's MEDIAN fund return (equal-weight, survivors present in the
--   data each month); it is an analytical index, not a published benchmark.
--   Rolling 12m is NULL until 12 monthly returns exist in the window.
WITH params AS (
    SELECT 'Mid Cap'::text AS category, 'DIRECT'::text AS plan_type, 60 AS months_back,
           (SELECT max(me_date) FROM marts.mv_scheme_month_end_nav) AS latest_me
), me AS (
    SELECT n.scheme_id, n.me_date, n.nav, n.month_no,
           lag(n.nav)      OVER w AS prev_nav,
           lag(n.month_no) OVER w AS prev_month_no
    FROM marts.mv_scheme_month_end_nav n
    JOIN core.dim_scheme s USING (scheme_id)
    CROSS JOIN params p
    WHERE s.category = p.category AND s.plan_type = p.plan_type AND s.option_type = 'GROWTH'
      AND n.me_date > p.latest_me - make_interval(months => p.months_back + 1)
    WINDOW w AS (PARTITION BY n.scheme_id ORDER BY n.me_date)
), mom AS (
    SELECT m.me_date,
           count(*)                                                    AS n_funds,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY (m.nav / m.prev_nav - 1)::double precision)
                                                                       AS median_mom,
           count(*) FILTER (WHERE m.nav > m.prev_nav)::numeric / count(*) AS share_funds_up,
           min((m.nav / m.prev_nav - 1)::double precision)             AS worst_fund_mom,
           max((m.nav / m.prev_nav - 1)::double precision)             AS best_fund_mom
    FROM me m
    WHERE m.prev_month_no = m.month_no - 1 AND m.prev_nav > 0
    GROUP BY m.me_date
), path AS (
    SELECT mm.*,
           sum(ln(1 + mm.median_mom)) OVER (ORDER BY mm.me_date) AS cum_log,
           sum(ln(1 + mm.median_mom)) OVER r12                   AS log_12m,
           count(*) OVER r12                                     AS n_in_12m
    FROM mom mm
    WINDOW r12 AS (ORDER BY mm.me_date ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)
)
SELECT pa.me_date, pa.n_funds,
       round((pa.median_mom * 100)::numeric, 2)       AS median_mom_pct,
       round(pa.share_funds_up, 3)                    AS share_funds_up,
       round((pa.worst_fund_mom * 100)::numeric, 2)   AS worst_fund_mom_pct,
       round((pa.best_fund_mom * 100)::numeric, 2)    AS best_fund_mom_pct,
       round((100 * (exp(pa.cum_log) - 1))::numeric, 2) AS category_path_cum_pct,
       CASE WHEN pa.n_in_12m = 12 THEN round((100 * (exp(pa.log_12m) - 1))::numeric, 2) END
                                                      AS rolling_12m_pct,
       round((100 * (exp(pa.cum_log - max(pa.cum_log) OVER (ORDER BY pa.me_date)) - 1))::numeric, 2)
                                                      AS drawdown_from_peak_pct
FROM path pa
ORDER BY pa.me_date;
