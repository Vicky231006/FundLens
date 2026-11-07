-- Business question: In hindsight, did schemes carrying a review flag subsequently do better or
-- worse over the next 12 months, relative to their category median, than unflagged schemes?
-- (Retrospective evaluation of the screen only - not advice, not a forecast.)
-- !! EVALUATION ONLY - FORWARD-LOOKING DATA !!
-- !! This query uses marts.mv_forward_return_12m (fwd_return_12m, excess_fwd), which looks
-- !! 12 months AFTER each month-end. It must never feed a flag, rank or screening decision;
-- !! here it is used purely to judge past flags. Survivorship caveat: peers are funds present
-- !! in the dataset (see docs/DATA_CARD.md).
-- Demonstrates: CTEs, DISTINCT ON latest run, LEFT JOIN flag membership, FILTER aggregates
--               incl. FILTERed percentile_cont, grouping by year, 4-table join.
-- Universe: month-ends where the scheme was screenable (3y CAGR present) and a forward 12m
--           return exists. A scheme is "flagged" if it has a row in the latest run's
--           review_flag for that month-end. Sample sizes are shown so thin cells are visible.
WITH latest_run AS (
    SELECT DISTINCT ON (sr.plan_type) sr.run_id, sr.plan_type
    FROM marts.screening_run sr
    ORDER BY sr.plan_type, sr.run_id DESC
), obs AS (
    SELECT lr.plan_type, f.me_date, f.scheme_id, f.fwd_return_12m, f.excess_fwd,
           (rf.scheme_id IS NOT NULL) AS flagged
    FROM latest_run lr
    JOIN marts.mv_forward_return_12m f ON f.plan_type = lr.plan_type            -- EVALUATION ONLY
    JOIN marts.mv_scheme_month_metrics m ON m.scheme_id = f.scheme_id
                                        AND m.me_date = f.me_date
                                        AND m.cagr_3y IS NOT NULL
    LEFT JOIN marts.review_flag rf ON rf.run_id = lr.run_id
                                  AND rf.scheme_id = f.scheme_id
                                  AND rf.me_date = f.me_date
)
SELECT o.plan_type,
       extract(year FROM o.me_date)::int AS me_year,
       count(*) FILTER (WHERE o.flagged)      AS n_flagged,
       count(*) FILTER (WHERE NOT o.flagged)  AS n_unflagged,
       round((100 * avg(o.excess_fwd) FILTER (WHERE o.flagged))::numeric, 2)       AS flagged_avg_excess_pp,
       round((100 * avg(o.excess_fwd) FILTER (WHERE NOT o.flagged))::numeric, 2)   AS unflagged_avg_excess_pp,
       round((100 * (percentile_cont(0.5) WITHIN GROUP (ORDER BY o.excess_fwd) FILTER (WHERE o.flagged)))::numeric, 2)
                                                                                   AS flagged_median_excess_pp,
       round((100 * (percentile_cont(0.5) WITHIN GROUP (ORDER BY o.excess_fwd) FILTER (WHERE NOT o.flagged)))::numeric, 2)
                                                                                   AS unflagged_median_excess_pp,
       round((count(*) FILTER (WHERE o.flagged AND o.excess_fwd < 0))::numeric
             / nullif(count(*) FILTER (WHERE o.flagged), 0), 3)                    AS flagged_share_below_median
FROM obs o
GROUP BY o.plan_type, extract(year FROM o.me_date)
ORDER BY o.plan_type, me_year;
