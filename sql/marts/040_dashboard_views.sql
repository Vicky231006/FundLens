-- Stable, documented read-model for the Power BI dashboard (FR-A7). The dashboard connects
-- ONLY to these views, so the BI layer never depends on raw/staging internals, and every
-- dashboard figure can be reconciled with a SQL query against these same views.
-- Applying plan_type is the dashboard's responsibility: DIRECT and REGULAR must never be
-- shown mixed in one peer comparison.

DROP VIEW IF EXISTS marts.dash_refresh_info CASCADE;
DROP VIEW IF EXISTS marts.dash_flag CASCADE;
DROP VIEW IF EXISTS marts.dash_fund_month CASCADE;
DROP VIEW IF EXISTS marts.dash_dq_issue CASCADE;
DROP VIEW IF EXISTS marts.dash_dq_by_category CASCADE;
DROP VIEW IF EXISTS marts.dash_backtest_summary CASCADE;
DROP VIEW IF EXISTS marts.dash_backtest_dataset CASCADE;

-- One row: dataset freshness + the disclosure shown on every page.
CREATE VIEW marts.dash_refresh_info AS
SELECT
    (SELECT max(finished_at) FROM raw.ingestion_run WHERE status = 'SUCCEEDED') AS last_successful_refresh,
    (SELECT max(nav_date) FROM core.fact_nav)                                  AS latest_nav_date,
    (SELECT count(*) FROM core.fact_nav)                                       AS nav_rows,
    (SELECT count(*) FROM core.dim_scheme)                                     AS schemes,
    'Source: AMFI historical NAV data (personal, non-commercial portfolio project). '
    || 'Research-review flags only: not an investment recommendation. Survivorship bias: closed '
    || 'and merged schemes are largely absent. Categories are AMFI''s current labels. '
    || 'See docs/DATA_CARD.md.'                                                AS disclosure;

-- Flags from the LATEST screening run of each plan type (default parameters).
CREATE VIEW marts.dash_flag AS
WITH latest AS (SELECT DISTINCT ON (plan_type) run_id, plan_type, params
                FROM marts.screening_run WHERE label = 'default' ORDER BY plan_type, run_id DESC)
SELECT l.plan_type, f.me_date, s.scheme_id, s.amfi_code, s.scheme_name, s.amc_name, s.category,
       f.streak_months, f.cagr_3y, f.pct_rank_cagr_3y, f.max_drawdown_3y,
       f.median_max_drawdown_3y, f.peers_3y, f.explanation,
       m.cagr_1y, m.cagr_5y, m.volatility_1y, m.sip_xirr_3y,
       (f.me_date = (SELECT max(me_date) FROM marts.mv_scheme_month_metrics)) AS is_latest_month_end,
       (l.params->>'k')::int AS param_k
FROM latest l
JOIN marts.review_flag f ON f.run_id = l.run_id
JOIN core.dim_scheme s ON s.scheme_id = f.scheme_id
LEFT JOIN marts.mv_scheme_month_metrics m ON m.scheme_id = f.scheme_id AND m.me_date = f.me_date;

-- Month-end grain series for drill-down: metrics, category medians and flag status.
CREATE VIEW marts.dash_fund_month AS
WITH latest AS (SELECT DISTINCT ON (plan_type) run_id, plan_type
                FROM marts.screening_run WHERE label = 'default' ORDER BY plan_type, run_id DESC)
SELECT s.scheme_id, s.amfi_code, s.scheme_name, s.amc_name, m.category, m.plan_type, m.me_date,
       m.nav, m.cagr_1y, m.cagr_3y, m.cagr_5y, m.volatility_1y, m.max_drawdown_3y, m.sip_xirr_3y,
       m.pct_rank_cagr_1y, m.pct_rank_cagr_3y, m.pct_rank_cagr_5y, m.pct_rank_volatility_1y,
       m.pct_rank_max_drawdown_3y, m.peers_3y, m.median_cagr_3y, m.median_max_drawdown_3y,
       (f.scheme_id IS NOT NULL) AS is_flagged
FROM marts.mv_scheme_month_metrics m
JOIN core.dim_scheme s USING (scheme_id)
LEFT JOIN latest l ON l.plan_type = m.plan_type
LEFT JOIN marts.review_flag f ON f.run_id = l.run_id AND f.scheme_id = m.scheme_id AND f.me_date = m.me_date;

CREATE VIEW marts.dash_dq_issue AS
SELECT i.issue_id, i.issue_category, i.severity, i.resolution_status, i.detected_at, i.nav_date,
       i.explanation, i.observation::text AS observation, s.scheme_id, s.amfi_code, s.scheme_name,
       s.category, s.plan_type
FROM core.dq_issue i LEFT JOIN core.dim_scheme s USING (scheme_id);

CREATE VIEW marts.dash_dq_by_category AS
SELECT issue_category, severity, resolution_status, count(*) AS n_issues,
       count(DISTINCT scheme_id) AS n_schemes
FROM core.dq_issue GROUP BY 1, 2, 3;

-- Latest backtest run per plan type, flattened to one row per (param set, period, method).
CREATE VIEW marts.dash_backtest_summary AS
WITH latest AS (SELECT DISTINCT ON (plan_type) * FROM marts.backtest_run ORDER BY plan_type, run_id DESC),
per AS (
    SELECT l.run_id, l.plan_type, ps.key AS param_set, pe.key AS period, pe.value AS r
    FROM latest l, jsonb_each(l.results -> 'periods') ps, jsonb_each(ps.value) pe
    WHERE (pe.value ->> 'n_obs')::int > 0
), methods(method, mask_key) AS (
    VALUES ('FundLens screen', 'screen'),
           ('Baseline 1: bottom-quartile 1-year return', 'baseline_bottom_quartile_1y'),
           ('All eligible observations', 'all_eligible')
)
SELECT p.run_id, p.plan_type, p.param_set, p.period, m.method,
       p.r ->> 'first_month_end' AS first_month_end, p.r ->> 'last_month_end' AS last_month_end,
       (p.r ->> 'n_obs')::int AS n_eligible_obs,
       CASE m.mask_key WHEN 'screen' THEN (p.r -> 'screen' ->> 'n_flag_obs')::int
                       WHEN 'baseline_bottom_quartile_1y' THEN (p.r -> 'baseline_bottom_quartile_1y' ->> 'n_flag_obs')::int
                       ELSE (p.r ->> 'n_obs')::int END AS n_obs,
       (p.r -> 'ci_fund_cluster_bootstrap' -> m.mask_key ->> 'estimate')::double precision AS mean_y,
       (p.r -> 'ci_fund_cluster_bootstrap' -> m.mask_key ->> 'ci_lower')::double precision AS ci_lower_fund_cluster,
       (p.r -> 'ci_fund_cluster_bootstrap' -> m.mask_key ->> 'ci_upper')::double precision AS ci_upper_fund_cluster,
       (p.r -> 'ci_month_block_bootstrap' -> m.mask_key ->> 'ci_lower')::double precision AS ci_lower_month_block,
       (p.r -> 'ci_month_block_bootstrap' -> m.mask_key ->> 'ci_upper')::double precision AS ci_upper_month_block,
       p.r ->> 'interpretation' AS interpretation
FROM per p CROSS JOIN methods m
UNION ALL
SELECT p.run_id, p.plan_type, p.param_set, p.period, 'Baseline 2: random flags (permutation mean)',
       p.r ->> 'first_month_end', p.r ->> 'last_month_end', (p.r ->> 'n_obs')::int,
       (p.r -> 'screen' ->> 'n_flag_obs')::int,
       (p.r -> 'permutation_random_flags_screen' ->> 'random_flags_mean_y')::double precision,
       (p.r -> 'permutation_random_flags_screen' ->> 'random_flags_ci_lower')::double precision,
       (p.r -> 'permutation_random_flags_screen' ->> 'random_flags_ci_upper')::double precision,
       NULL, NULL, p.r ->> 'interpretation'
FROM per p WHERE p.r -> 'permutation_random_flags_screen' IS NOT NULL
  AND jsonb_typeof(p.r -> 'permutation_random_flags_screen') = 'object';

CREATE VIEW marts.dash_backtest_dataset AS
SELECT run_id, plan_type, created_at,
       results -> 'dataset' ->> 'n_schemes_with_metrics' AS schemes,
       results -> 'dataset' ->> 'n_scheme_month_rows' AS scheme_month_rows,
       results -> 'dataset' ->> 'first_screenable_month_end' AS first_month_end,
       results -> 'dataset' ->> 'last_screenable_month_end' AS last_month_end,
       results -> 'dataset' ->> 'train_month_ends' AS train_month_ends,
       results -> 'dataset' ->> 'test_month_ends' AS test_month_ends,
       results -> 'dataset' ->> 'test_start' AS test_start,
       results -> 'default_params' AS default_params, results -> 'tuned_params' AS tuned_params
FROM (SELECT DISTINCT ON (plan_type) * FROM marts.backtest_run ORDER BY plan_type, run_id DESC) l;
