-- 006: sequential index over market days (used to detect gaps between consecutive
-- observations and to compare observation counts with the number of market days).

ALTER TABLE core.market_day ADD COLUMN mday_idx INTEGER;

CREATE OR REPLACE FUNCTION core.refresh_market_day(min_coverage NUMERIC DEFAULT 0.5)
RETURNS void AS $$
BEGIN
    TRUNCATE core.market_day;

    INSERT INTO core.market_day (cal_date, n_nav, n_active, coverage, is_market_day, is_month_end,
                                 mday_idx)
    WITH bounds AS (
        SELECT min(nav_date) AS d0, max(nav_date) AS d1 FROM core.fact_nav
    ), nav_counts AS (
        SELECT nav_date, count(*) AS n FROM core.fact_nav GROUP BY nav_date
    ), active AS (
        SELECT d.cal_date, count(s.scheme_id) AS n_active
        FROM core.dim_date d
        JOIN bounds b ON d.cal_date BETWEEN b.d0 AND b.d1
        JOIN core.dim_scheme s ON d.cal_date BETWEEN s.first_nav_date AND s.last_nav_date
        GROUP BY d.cal_date
    ), cov AS (
        SELECT a.cal_date, coalesce(c.n, 0) AS n_nav, a.n_active,
               round(coalesce(c.n, 0)::numeric / a.n_active, 4) AS coverage
        FROM active a LEFT JOIN nav_counts c ON c.nav_date = a.cal_date
    ), flagged AS (
        SELECT *, coverage >= min_coverage AS is_market_day FROM cov
    )
    SELECT f.cal_date, f.n_nav, f.n_active, f.coverage, f.is_market_day,
           f.is_market_day AND f.cal_date = max(f.cal_date) FILTER (WHERE f.is_market_day)
               OVER (PARTITION BY date_trunc('month', f.cal_date)),
           CASE WHEN f.is_market_day
                THEN (count(*) FILTER (WHERE f.is_market_day) OVER (ORDER BY f.cal_date))::int END
    FROM flagged f;

    UPDATE core.dim_date d
       SET is_observed_day = m.is_market_day, is_month_end = m.is_month_end
      FROM core.market_day m WHERE m.cal_date = d.cal_date;
    UPDATE core.dim_date d SET is_observed_day = false, is_month_end = false
     WHERE NOT EXISTS (SELECT 1 FROM core.market_day m WHERE m.cal_date = d.cal_date);
END;
$$ LANGUAGE plpgsql;

CREATE UNIQUE INDEX ux_market_day_idx ON core.market_day (mday_idx) WHERE mday_idx IS NOT NULL;
