-- Business question: Which schemes had a one-observation NAV move of 10% or more that was NOT
-- shared by their category peers that day (a possible corporate action, scheme restructuring
-- or data error rather than a market move), and were they already logged or in conflict?
-- Demonstrates: parameter CTE, lag(), percentile_cont per (category, plan, date) as a peer
--               benchmark, row_number top-N per category, LEFT JOINs to core.dq_issue and
--               core.nav_revision_conflict (4+ table join).
-- Parameters: `params` - look-back window, absolute move threshold, N per category,
--             the minimum deviation from the peer median to count as idiosyncratic, and
--             max_gap_days (moves spanning a longer hole in the history are not compared).
-- Notes: `move_pct` is vs the previous observation of the same scheme (not necessarily the
--        previous market day). `deviation_pp` = move minus the same-day category/plan median
--        move. An investigation aid: it does not say which value is correct.
WITH params AS (
    SELECT (SELECT max(nav_date) FROM core.fact_nav) AS d_max,
           2 AS window_years, 0.10::numeric AS move_threshold, 0.05::numeric AS min_deviation,
           5 AS top_n_per_category,
           10 AS max_gap_days   -- ignore 'moves' across a hole in the loaded history
), moves AS (
    SELECT f.scheme_id, f.nav_date, f.nav,
           lag(f.nav)      OVER w AS prev_nav,
           lag(f.nav_date) OVER w AS prev_date
    FROM core.fact_nav f
    CROSS JOIN params p
    WHERE f.nav_date > (p.d_max - make_interval(years => p.window_years) - interval '14 days')::date
      AND f.nav > 0
    WINDOW w AS (PARTITION BY f.scheme_id ORDER BY f.nav_date)
), scored AS (
    SELECT m.scheme_id, m.nav_date, m.prev_date, m.prev_nav, m.nav,
           (m.nav / m.prev_nav - 1) AS move, s.category, s.plan_type
    FROM moves m
    JOIN core.dim_scheme s USING (scheme_id)
    CROSS JOIN params p
    WHERE m.prev_nav > 0 AND m.nav_date > p.d_max - make_interval(years => p.window_years)
      AND m.nav_date - m.prev_date <= p.max_gap_days
), peer_med AS (
    SELECT sc.category, sc.plan_type, sc.nav_date,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY sc.move::double precision) AS peer_median_move
    FROM scored sc
    GROUP BY sc.category, sc.plan_type, sc.nav_date
), peer AS (
    SELECT sc.*, pm.peer_median_move
    FROM scored sc
    JOIN peer_med pm USING (category, plan_type, nav_date)
), cand AS (
    SELECT pe.*, (pe.move::double precision - pe.peer_median_move) AS deviation,
           row_number() OVER (PARTITION BY pe.category
                              ORDER BY abs(pe.move::double precision - pe.peer_median_move) DESC, pe.scheme_id, pe.nav_date)
               AS rn_in_category
    FROM peer pe
    CROSS JOIN params p
    WHERE abs(pe.move) >= p.move_threshold
      AND abs(pe.move::double precision - pe.peer_median_move) >= p.min_deviation
)
SELECT c.category, c.rn_in_category, s.amfi_code, s.scheme_name, s.plan_type,
       c.prev_date, c.nav_date, c.prev_nav, c.nav,
       round((c.move * 100)::numeric, 2)                      AS move_pct,
       round((c.peer_median_move * 100)::numeric, 2)          AS peer_median_move_pct,
       round((c.deviation * 100)::numeric, 2)                 AS deviation_pp,
       i.severity AS dq_severity, i.resolution_status AS dq_status,
       (i.issue_id IS NOT NULL)                               AS logged_in_dq_issue,
       (rc.conflict_id IS NOT NULL)                           AS has_revision_conflict
FROM cand c
JOIN core.dim_scheme s USING (scheme_id)
CROSS JOIN params p
LEFT JOIN core.dq_issue i
       ON i.scheme_id = c.scheme_id AND i.nav_date = c.nav_date
      AND i.issue_category = 'ABNORMAL_NAV_MOVE'
LEFT JOIN core.nav_revision_conflict rc
       ON rc.scheme_id = c.scheme_id AND rc.nav_date = c.nav_date
WHERE c.rn_in_category <= p.top_n_per_category
ORDER BY c.category, c.rn_in_category;
