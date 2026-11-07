-- Forward 12-month returns for backtest EVALUATION ONLY.
--
-- !! These columns look into the future of me_date. They must never be used to compute
-- !! flags, ranks or any input to a screening decision (that would be look-ahead bias).
-- !! They are kept out of mv_scheme_month_metrics on purpose.
--
-- fwd_return_12m  : NAV(me_date + 12 months, as-of within 5 calendar days) / NAV(me_date) - 1.
--                   Defined only when the forward end date has actually occurred in the data.
-- excess_fwd      : y = fwd_return_12m - median fwd_return_12m of the same (category, plan type,
--                   month-end) group. Median is over funds present in the dataset (survivors:
--                   see docs/DATA_CARD.md survivorship note).

DROP MATERIALIZED VIEW IF EXISTS marts.mv_forward_return_12m CASCADE;

CREATE MATERIALIZED VIEW marts.mv_forward_return_12m AS
WITH last_day AS (
    SELECT max(cal_date) AS d FROM core.market_day WHERE is_market_day
), fwd AS (
    SELECT n.scheme_id, n.me_date, s.category, s.plan_type,
           f.nav_date AS fwd_end_date,
           (f.nav / n.nav - 1)::double precision AS fwd_return_12m
    FROM marts.mv_scheme_month_end_nav n
    JOIN core.dim_scheme s USING (scheme_id)
    CROSS JOIN last_day
    JOIN LATERAL marts.nav_asof(n.scheme_id, (n.me_date + interval '12 months')::date) f ON true
    WHERE (n.me_date + interval '12 months')::date <= last_day.d
), med AS (
    SELECT me_date, category, plan_type, count(*) AS peers_fwd,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY fwd_return_12m) AS median_fwd_return_12m
    FROM fwd GROUP BY me_date, category, plan_type
)
SELECT f.scheme_id, f.me_date, f.category, f.plan_type, f.fwd_end_date, f.fwd_return_12m,
       m.peers_fwd, m.median_fwd_return_12m,
       f.fwd_return_12m - m.median_fwd_return_12m AS excess_fwd
FROM fwd f JOIN med m USING (me_date, category, plan_type);

CREATE UNIQUE INDEX ux_mv_fwd ON marts.mv_forward_return_12m (scheme_id, me_date);
CREATE INDEX ix_mv_fwd_date ON marts.mv_forward_return_12m (me_date);
