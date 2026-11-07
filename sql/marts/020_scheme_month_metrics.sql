-- Month-end metrics per scheme (FR-A4). Materialised because every metric needs a window
-- over up to three years of daily NAVs per scheme per month-end (~10^8 row visits for the
-- full history): dashboards and the backtest read this once-built table instead.
-- It is rebuilt by `fundlens build-marts` after each ingestion.
--
-- Point-in-time safety: every column for month-end t uses only NAVs dated <= t. Forward
-- returns (which look into the future) are deliberately NOT here: see 030_forward_return.sql.
--
-- Incomplete data is never silently used:
--   * CAGR needs an anchor NAV within 5 calendar days before (t - N years), else NULL.
--   * volatility_1y / max_drawdown_3y need >= 95% of the market days in their window to
--     have a NAV, else NULL. Volatility only uses returns between CONSECUTIVE market days.
--   * SIP XIRR needs a NAV on each of 36 consecutive month-ends plus t, else NULL.

DROP MATERIALIZED VIEW IF EXISTS marts.mv_scheme_month_metrics CASCADE;
DROP VIEW IF EXISTS marts.v_month_end CASCADE;
DROP MATERIALIZED VIEW IF EXISTS marts.mv_scheme_month_end_nav CASCADE;

-- Completed month-ends only: the month containing the latest market day is still in
-- progress, so it is excluded.
CREATE VIEW marts.v_month_end AS
SELECT m.cal_date AS me_date, m.mday_idx
FROM core.market_day m
WHERE m.is_month_end
  AND m.cal_date < (SELECT date_trunc('month', max(cal_date))::date
                    FROM core.market_day WHERE is_market_day);

-- NAV exactly on each scheme's month-end market day.
CREATE MATERIALIZED VIEW marts.mv_scheme_month_end_nav AS
SELECT f.scheme_id, me.me_date, f.nav,
       (extract(year FROM me.me_date) * 12 + extract(month FROM me.me_date))::int AS month_no
FROM marts.v_month_end me
JOIN core.fact_nav f ON f.nav_date = me.me_date AND f.nav > 0;
CREATE UNIQUE INDEX ux_mv_me_nav ON marts.mv_scheme_month_end_nav (scheme_id, me_date);

CREATE MATERIALIZED VIEW marts.mv_scheme_month_metrics AS
WITH base AS (
    SELECT n.scheme_id, n.me_date, n.nav, s.category, s.plan_type
    FROM marts.mv_scheme_month_end_nav n
    JOIN core.dim_scheme s USING (scheme_id)
), returns AS (
    SELECT b.*,
           a1.nav AS nav_1y, a1.nav_date AS date_1y,
           a3.nav AS nav_3y, a3.nav_date AS date_3y,
           a5.nav AS nav_5y, a5.nav_date AS date_5y
    FROM base b
    LEFT JOIN LATERAL marts.nav_asof(b.scheme_id, (b.me_date - interval '1 year')::date) a1 ON true
    LEFT JOIN LATERAL marts.nav_asof(b.scheme_id, (b.me_date - interval '3 years')::date) a3 ON true
    LEFT JOIN LATERAL marts.nav_asof(b.scheme_id, (b.me_date - interval '5 years')::date) a5 ON true
), risk AS (
    SELECT r.scheme_id, r.me_date, w.*
    FROM returns r
    LEFT JOIN LATERAL (
        SELECT
            CASE WHEN count(*) >= 0.95 * (
                     SELECT count(*) FROM core.market_day m
                     WHERE m.is_market_day AND m.cal_date BETWEEN r.me_date - interval '3 years' AND r.me_date)
                 AND min(x.nav_date) <= r.me_date - interval '3 years' + interval '7 days'
                 THEN min(x.dd) END AS max_drawdown_3y,
            CASE WHEN count(x.lr) FILTER (WHERE x.nav_date > r.me_date - interval '1 year'
                                            AND x.prev_idx = x.mday_idx - 1) >= 0.95 * (
                     SELECT count(*) FROM core.market_day m
                     WHERE m.is_market_day AND m.cal_date > r.me_date - interval '1 year'
                       AND m.cal_date <= r.me_date)
                 THEN stddev_samp(x.lr) FILTER (WHERE x.nav_date > r.me_date - interval '1 year'
                                                  AND x.prev_idx = x.mday_idx - 1) * sqrt(252.0)
            END AS volatility_1y,
            count(*) AS obs_3y
        FROM (
            SELECT f.nav_date, md.mday_idx,
                   f.nav / max(f.nav) OVER (ORDER BY f.nav_date) - 1 AS dd,
                   ln((f.nav / lag(f.nav) OVER (ORDER BY f.nav_date))::double precision) AS lr,
                   lag(md.mday_idx) OVER (ORDER BY f.nav_date) AS prev_idx
            FROM core.fact_nav f
            JOIN core.market_day md ON md.cal_date = f.nav_date AND md.is_market_day
            WHERE f.scheme_id = r.scheme_id AND f.nav > 0
              AND f.nav_date BETWEEN r.me_date - interval '3 years' AND r.me_date
        ) x
    ) w ON true
    WHERE r.nav_3y IS NOT NULL            -- drawdown/vol windows are only meaningful with 3y history
), sip AS (
    SELECT scheme_id, me_date,
           CASE WHEN n_prior = 36 AND month_no - first_month_no = 36
                THEN marts.xirr(
                        dates || me_date,
                        array_fill(-10000.0::double precision, ARRAY[36])
                           || (units * nav)::double precision)
           END AS sip_xirr_3y
    FROM (
        SELECT scheme_id, me_date, nav, month_no,
               count(*) OVER w AS n_prior,
               first_value(month_no) OVER w AS first_month_no,
               array_agg(me_date) OVER w AS dates,
               sum(10000.0 / nav) OVER w AS units
        FROM marts.mv_scheme_month_end_nav
        WINDOW w AS (PARTITION BY scheme_id ORDER BY me_date ROWS BETWEEN 36 PRECEDING AND 1 PRECEDING)
    ) z
), joined AS (
    SELECT r.scheme_id, r.me_date, r.category, r.plan_type, r.nav,
           marts.cagr(r.nav_1y, r.date_1y, r.nav, r.me_date) AS cagr_1y,
           marts.cagr(r.nav_3y, r.date_3y, r.nav, r.me_date) AS cagr_3y,
           marts.cagr(r.nav_5y, r.date_5y, r.nav, r.me_date) AS cagr_5y,
           k.volatility_1y, k.max_drawdown_3y, sip.sip_xirr_3y
    FROM returns r
    LEFT JOIN risk k USING (scheme_id, me_date)
    LEFT JOIN sip USING (scheme_id, me_date)
), medians AS (
    SELECT me_date, category, plan_type,
           count(cagr_1y) AS peers_1y, count(cagr_3y) AS peers_3y, count(cagr_5y) AS peers_5y,
           count(volatility_1y) AS peers_vol, count(max_drawdown_3y) AS peers_dd,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY cagr_3y) AS median_cagr_3y,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY max_drawdown_3y) AS median_max_drawdown_3y
    FROM joined GROUP BY me_date, category, plan_type
)
SELECT j.scheme_id, j.me_date, j.category, j.plan_type, j.nav,
       j.cagr_1y, j.cagr_3y, j.cagr_5y, j.volatility_1y, j.max_drawdown_3y, j.sip_xirr_3y,
       -- Percentile rank within (month-end, category, plan type): 0 = worst, 1 = best.
       -- For volatility and drawdown, "best" = lowest volatility / shallowest drawdown.
       CASE WHEN j.cagr_1y IS NOT NULL THEN percent_rank() OVER (
            PARTITION BY j.me_date, j.category, j.plan_type, (j.cagr_1y IS NULL) ORDER BY j.cagr_1y) END
            AS pct_rank_cagr_1y,
       CASE WHEN j.cagr_3y IS NOT NULL THEN percent_rank() OVER (
            PARTITION BY j.me_date, j.category, j.plan_type, (j.cagr_3y IS NULL) ORDER BY j.cagr_3y) END
            AS pct_rank_cagr_3y,
       CASE WHEN j.cagr_5y IS NOT NULL THEN percent_rank() OVER (
            PARTITION BY j.me_date, j.category, j.plan_type, (j.cagr_5y IS NULL) ORDER BY j.cagr_5y) END
            AS pct_rank_cagr_5y,
       CASE WHEN j.volatility_1y IS NOT NULL THEN percent_rank() OVER (
            PARTITION BY j.me_date, j.category, j.plan_type, (j.volatility_1y IS NULL)
            ORDER BY j.volatility_1y DESC) END AS pct_rank_volatility_1y,
       CASE WHEN j.max_drawdown_3y IS NOT NULL THEN percent_rank() OVER (
            PARTITION BY j.me_date, j.category, j.plan_type, (j.max_drawdown_3y IS NULL)
            ORDER BY j.max_drawdown_3y) END AS pct_rank_max_drawdown_3y,
       m.peers_1y, m.peers_3y, m.peers_5y, m.peers_vol, m.peers_dd,
       m.median_cagr_3y, m.median_max_drawdown_3y
FROM joined j
JOIN medians m USING (me_date, category, plan_type);

CREATE UNIQUE INDEX ux_mv_metrics ON marts.mv_scheme_month_metrics (scheme_id, me_date);
CREATE INDEX ix_mv_metrics_cat_date ON marts.mv_scheme_month_metrics (category, plan_type, me_date);
CREATE INDEX ix_mv_metrics_date ON marts.mv_scheme_month_metrics (me_date);
