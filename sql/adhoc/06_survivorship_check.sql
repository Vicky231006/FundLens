-- Business question: Which schemes stopped publishing NAVs well before the end of the dataset
-- (possible mergers/closures), and what share of each category/plan group is that? This tells
-- an analyst how much survivorship bias a "currently existing funds only" view would carry.
-- Demonstrates: parameter CTE, CTE aggregation with FILTER, join back to detail, 3+ table join
--               (dim_scheme, scheme_name_history, scheme_mapping), LATERAL string_agg.
-- Parameters: `params.stale_after_days` (default 90 days before the dataset's latest NAV date).
-- Notes: "ceased" is a data observation (no later NAV in our dataset), not a statement about why.
--        While ingestion is still running, schemes whose later history is not loaded yet can
--        look ceased. Mapping candidates come from core.scheme_mapping (never inferred by name).
WITH params AS (
    SELECT (SELECT max(last_nav_date) FROM core.dim_scheme) AS dataset_max,
           90 AS stale_after_days
), flagged AS (
    SELECT s.*, p.dataset_max,
           (p.dataset_max - s.last_nav_date) AS days_before_dataset_end,
           (s.last_nav_date < p.dataset_max - p.stale_after_days) AS ceased
    FROM core.dim_scheme s CROSS JOIN params p
), cat_stats AS (
    SELECT category, plan_type,
           count(*)                                    AS schemes_in_group,
           count(*) FILTER (WHERE ceased)              AS ceased_in_group,
           round(100.0 * count(*) FILTER (WHERE ceased) / count(*), 1) AS ceased_pct_in_group
    FROM flagged
    GROUP BY category, plan_type
)
SELECT f.category, f.plan_type, f.amfi_code, f.scheme_name, f.amc_name,
       f.first_nav_date, f.last_nav_date, f.days_before_dataset_end,
       round((f.last_nav_date - f.first_nav_date) / 365.25, 1) AS years_of_history,
       (SELECT count(*) FROM core.scheme_name_history h WHERE h.scheme_id = f.scheme_id) AS names_seen,
       mp.mapping_candidates,
       cs.schemes_in_group, cs.ceased_in_group, cs.ceased_pct_in_group
FROM flagged f
JOIN cat_stats cs USING (category, plan_type)
LEFT JOIN LATERAL (
    SELECT string_agg(m.relation_type || '/' || m.status || ' -> ' || t.amfi_code, '; ') AS mapping_candidates
    FROM core.scheme_mapping m
    JOIN core.dim_scheme t ON t.scheme_id = m.to_scheme_id
    WHERE m.from_scheme_id = f.scheme_id
) mp ON true
WHERE f.ceased
ORDER BY f.category, f.plan_type, f.last_nav_date, f.amfi_code
LIMIT 500;
