-- Business question: How persistent are review flags? For each scheme flagged in the latest
-- run of its plan type: how many month-ends was it flagged, in how many separate episodes,
-- what was the longest episode, how long was the break before it was re-flagged, and is it
-- flagged right now? (Review flags are research prompts, not advice.)
-- Demonstrates: gaps-and-islands over a dense month-end sequence, lag() between episodes,
--               aggregation with FILTER / bool_or, rank of schemes by persistence, cross-check
--               against the stored streak_months column, 4-table join.
-- Notes: the month-end sequence comes from marts.mv_scheme_month_metrics, so a month with no
--        metrics row breaks an episode. `stored_max_streak` is the engine's own counter; a
--        mismatch with `longest_episode` is worth investigating.
WITH latest_run AS (
    SELECT DISTINCT ON (sr.plan_type) sr.run_id, sr.plan_type
    FROM marts.screening_run sr
    ORDER BY sr.plan_type, sr.run_id DESC
), month_seq AS (
    SELECT me_date, dense_rank() OVER (ORDER BY me_date) AS me_seq
    FROM (SELECT DISTINCT me_date FROM marts.mv_scheme_month_metrics) d
), flags AS (
    SELECT lr.plan_type, rf.run_id, rf.scheme_id, rf.me_date, rf.streak_months, ms.me_seq,
           ms.me_seq - row_number() OVER (PARTITION BY rf.run_id, rf.scheme_id ORDER BY rf.me_date) AS grp
    FROM latest_run lr
    JOIN marts.review_flag rf ON rf.run_id = lr.run_id
    JOIN month_seq ms ON ms.me_date = rf.me_date
), episodes AS (
    SELECT f.plan_type, f.run_id, f.scheme_id, f.grp,
           min(f.me_date) AS ep_start, max(f.me_date) AS ep_end,
           min(f.me_seq)  AS start_seq, max(f.me_seq) AS end_seq,
           count(*)       AS ep_months,
           max(f.streak_months) AS stored_max_streak
    FROM flags f
    GROUP BY f.plan_type, f.run_id, f.scheme_id, f.grp
), episodes_gap AS (
    SELECT e.*,
           e.start_seq - lag(e.end_seq) OVER (PARTITION BY e.run_id, e.scheme_id ORDER BY e.ep_start) - 1
               AS months_unflagged_before
    FROM episodes e
), per_scheme AS (
    SELECT e.plan_type, e.run_id, e.scheme_id,
           sum(e.ep_months)              AS months_flagged,
           count(*)                      AS n_episodes,
           max(e.ep_months)              AS longest_episode,
           max(e.stored_max_streak)      AS stored_max_streak,
           min(e.ep_start)               AS first_flagged,
           max(e.ep_end)                 AS last_flagged,
           max(e.months_unflagged_before) AS longest_break_before_reflag,
           bool_or(e.end_seq = (SELECT max(me_seq) FROM month_seq)) AS flagged_now
    FROM episodes_gap e
    GROUP BY e.plan_type, e.run_id, e.scheme_id
)
SELECT ps.plan_type, ps.run_id,
       dense_rank() OVER (PARTITION BY ps.plan_type ORDER BY ps.longest_episode DESC, ps.months_flagged DESC) AS persistence_rank,
       s.category, s.amfi_code, s.scheme_name,
       ps.months_flagged, ps.n_episodes, ps.longest_episode, ps.stored_max_streak,
       (ps.longest_episode IS DISTINCT FROM ps.stored_max_streak) AS streak_mismatch,
       ps.first_flagged, ps.last_flagged, ps.longest_break_before_reflag, ps.flagged_now
FROM per_scheme ps
JOIN core.dim_scheme s ON s.scheme_id = ps.scheme_id
ORDER BY ps.plan_type, persistence_rank, s.category, s.amfi_code
LIMIT 300;
