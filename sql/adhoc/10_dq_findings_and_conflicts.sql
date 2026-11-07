-- Business question: What is the current data-quality picture? How many issues are logged by
-- category / severity / resolution status, and have any re-downloads disagreed with NAVs we
-- already stored (core.nav_revision_conflict), and from which ingestion run / file?
-- Demonstrates: CTEs, UNION ALL of two evidence sources, FILTER aggregates, JSONB access
--               (->> and array_agg of observations), joins dq_issue/ingestion_run and
--               nav_revision_conflict/source_file/ingestion_run (3-table joins).
-- Notes: both source tables are empty until the DQ run / a conflicting re-download happens,
--        so zero rows is a valid result. Stored NAVs are never overwritten on conflict.
WITH issues AS (
    SELECT 'core.dq_issue'::text AS source,
           i.issue_category AS category, i.severity, i.resolution_status AS status,
           count(*) AS n_rows,
           count(DISTINCT i.scheme_id) AS n_schemes,
           min(i.nav_date) AS first_nav_date, max(i.nav_date) AS last_nav_date,
           max(abs((i.observation ->> 'change_pct')::numeric))
               FILTER (WHERE i.issue_category = 'ABNORMAL_NAV_MOVE') AS max_abs_change_pct,
           (array_agg(i.observation ORDER BY i.nav_date DESC NULLS LAST))[1] AS latest_observation,
           array_agg(DISTINCT i.run_id) FILTER (WHERE i.run_id IS NOT NULL) AS ingestion_runs,
           count(*) FILTER (WHERE ir.status IS DISTINCT FROM 'SUCCEEDED') AS rows_from_unsuccessful_runs
    FROM core.dq_issue i
    LEFT JOIN raw.ingestion_run ir ON ir.run_id = i.run_id
    GROUP BY i.issue_category, i.severity, i.resolution_status
), conflicts AS (
    SELECT 'core.nav_revision_conflict'::text AS source,
           'NAV_REVISION_CONFLICT'::text AS category,
           'n/a'::text AS severity, 'n/a'::text AS status,
           count(*) AS n_rows,
           count(DISTINCT c.scheme_id) AS n_schemes,
           min(c.nav_date) AS first_nav_date, max(c.nav_date) AS last_nav_date,
           max(abs((c.incoming_nav / nullif(c.existing_nav, 0) - 1) * 100)) AS max_abs_change_pct,
           (array_agg(jsonb_build_object('scheme_id', c.scheme_id, 'nav_date', c.nav_date,
                                         'existing_nav', c.existing_nav, 'incoming_nav', c.incoming_nav,
                                         'file', sf.file_path)
                      ORDER BY c.detected_at DESC))[1] AS latest_observation,
           array_agg(DISTINCT sf.run_id) FILTER (WHERE sf.run_id IS NOT NULL) AS ingestion_runs,
           count(*) FILTER (WHERE ir.status IS DISTINCT FROM 'SUCCEEDED') AS rows_from_unsuccessful_runs
    FROM core.nav_revision_conflict c
    JOIN raw.source_file sf ON sf.file_id = c.file_id
    LEFT JOIN raw.ingestion_run ir ON ir.run_id = sf.run_id
)
SELECT u.*
FROM (SELECT * FROM issues UNION ALL SELECT * FROM conflicts WHERE n_rows > 0) u
ORDER BY CASE u.severity WHEN 'CRITICAL' THEN 1 WHEN 'ERROR' THEN 2 WHEN 'WARNING' THEN 3
                         WHEN 'INFO' THEN 4 ELSE 5 END,
         u.n_rows DESC, u.category;
