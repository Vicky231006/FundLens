-- Business question: How big is the dataset? For each calendar year and category, how many
-- schemes (Direct vs Regular) were active, how many first appeared and how many stopped
-- publishing, and how many market days did that year have?
-- Demonstrates: CTEs, range join (dim_scheme x year), FILTER aggregates, 3-table join
--               (dim_date, market_day, dim_scheme).
-- Notes: "active in year" = [first_nav_date, last_nav_date] overlaps the year (it does not prove
--        a NAV on every day). "Ceased" = last_nav_date falls in that year AND is before the
--        dataset's latest NAV date (schemes still publishing at the dataset end are not ceased).
WITH dataset AS (
    SELECT min(first_nav_date) AS d_min, max(last_nav_date) AS d_max
    FROM core.dim_scheme
), years AS (
    SELECT d.year::int AS yr
    FROM core.dim_date d
    CROSS JOIN dataset ds
    WHERE d.cal_date BETWEEN ds.d_min AND ds.d_max
    GROUP BY d.year
), market_days AS (
    SELECT d.year::int AS yr, count(*) FILTER (WHERE m.is_market_day) AS market_days
    FROM core.market_day m
    JOIN core.dim_date d USING (cal_date)
    GROUP BY d.year
)
SELECT y.yr AS year,
       s.category,
       count(*) FILTER (WHERE s.plan_type = 'DIRECT')  AS active_direct,
       count(*) FILTER (WHERE s.plan_type = 'REGULAR') AS active_regular,
       count(*)                                         AS active_total,
       count(*) FILTER (WHERE extract(year FROM s.first_nav_date) = y.yr) AS first_nav_in_year,
       count(*) FILTER (WHERE extract(year FROM s.last_nav_date) = y.yr
                          AND s.last_nav_date < ds.d_max)               AS ceased_in_year,
       md.market_days
FROM years y
CROSS JOIN dataset ds
JOIN core.dim_scheme s
  ON s.first_nav_date <= make_date(y.yr, 12, 31)
 AND s.last_nav_date  >= make_date(y.yr, 1, 1)
LEFT JOIN market_days md ON md.yr = y.yr
GROUP BY y.yr, s.category, md.market_days
ORDER BY y.yr, s.category;
