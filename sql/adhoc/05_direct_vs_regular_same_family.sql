-- Business question: For the same fund family, how much did the Direct plan's trailing returns
-- differ from the Regular plan's at the latest month-end (a rough proxy for the cost gap)?
-- Demonstrates: CTEs, regexp name normalisation, grouped matching with FILTER + HAVING for
--               uniqueness, self-join of dim_scheme, double join to the mart, window average.
-- MATCHING ASSUMPTION (not an official mapping): a Direct and a Regular scheme are treated as
--   the same family ONLY IF they have the same AMC, the same category, Growth option, and the
--   same name after lower-casing and stripping the words direct/regular/plan/growth/option/
--   reg/dir and all punctuation - AND that key has exactly one Direct and exactly one Regular
--   scheme. Anything ambiguous (e.g. "Plan A/Plan B" variants) is left unmatched. AMFI scheme
--   codes are never merged; this is an analyst heuristic for comparison, not a claim of identity.
-- Parameters: `params.as_of` (default = latest month-end at which Direct schemes have a 3y CAGR).
WITH params AS (
    SELECT (SELECT max(me_date) FROM marts.mv_scheme_month_metrics
            WHERE plan_type = 'DIRECT' AND cagr_3y IS NOT NULL) AS as_of
), norm AS (
    SELECT s.scheme_id, s.amc_name, s.category, s.plan_type,
           btrim(regexp_replace(
                   regexp_replace(lower(s.scheme_name),
                                  '\m(direct|regular|plan|growth|option|reg|dir)\M', ' ', 'g'),
                   '[^a-z0-9]+', ' ', 'g')) AS family_key
    FROM core.dim_scheme s
    WHERE s.option_type = 'GROWTH' AND s.plan_type IN ('DIRECT', 'REGULAR') AND s.amc_name IS NOT NULL
), pairs AS (
    SELECT n.amc_name, n.category, n.family_key,
           max(n.scheme_id) FILTER (WHERE n.plan_type = 'DIRECT')  AS direct_id,
           max(n.scheme_id) FILTER (WHERE n.plan_type = 'REGULAR') AS regular_id
    FROM norm n
    GROUP BY n.amc_name, n.category, n.family_key
    HAVING count(*) FILTER (WHERE n.plan_type = 'DIRECT') = 1
       AND count(*) FILTER (WHERE n.plan_type = 'REGULAR') = 1
), cmp AS (
    SELECT pr.amc_name, pr.category, pr.family_key,
           sd.amfi_code AS direct_code, sd.scheme_name AS direct_name,
           sr.amfi_code AS regular_code, sr.scheme_name AS regular_name,
           md.me_date,
           (md.cagr_1y - mr.cagr_1y) * 100 AS spread_1y_pp,
           (md.cagr_3y - mr.cagr_3y) * 100 AS spread_3y_pp,
           (md.cagr_5y - mr.cagr_5y) * 100 AS spread_5y_pp
    FROM pairs pr
    JOIN core.dim_scheme sd ON sd.scheme_id = pr.direct_id
    JOIN core.dim_scheme sr ON sr.scheme_id = pr.regular_id
    CROSS JOIN params p
    JOIN marts.mv_scheme_month_metrics md ON md.scheme_id = pr.direct_id  AND md.me_date = p.as_of
    JOIN marts.mv_scheme_month_metrics mr ON mr.scheme_id = pr.regular_id AND mr.me_date = p.as_of
)
SELECT c.me_date, c.category, c.amc_name, c.family_key,
       c.direct_code, c.regular_code, c.direct_name, c.regular_name,
       round(c.spread_1y_pp::numeric, 2) AS direct_minus_regular_1y_pp,
       round(c.spread_3y_pp::numeric, 2) AS direct_minus_regular_3y_pp,
       round(c.spread_5y_pp::numeric, 2) AS direct_minus_regular_5y_pp,
       round((avg(c.spread_3y_pp) OVER (PARTITION BY c.category))::numeric, 2) AS category_avg_3y_pp,
       count(*) OVER (PARTITION BY c.category) AS matched_pairs_in_category
FROM cmp c
ORDER BY c.category, c.amc_name, c.family_key;
