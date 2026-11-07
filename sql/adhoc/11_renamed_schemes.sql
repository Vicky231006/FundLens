-- Business question: Which schemes (AMFI codes) have been published under more than one name,
-- in what order, for how long was each name in use, and is there an explicit relationship
-- recorded for them in core.scheme_mapping?
-- Demonstrates: lag/lead/row_number over a per-scheme name timeline, windowed count, LATERAL
--               string_agg, 3+ table join (scheme_name_history, dim_scheme, scheme_mapping).
-- Notes: the AMFI code is the identity and is stable across renames, so a name change on the
--        same code is a rename, never a new fund. Relationships BETWEEN different codes
--        (merge, replacement) live in core.scheme_mapping and only count when CONFIRMED;
--        candidates are shown with their status and are not inferred from names.
WITH timeline AS (
    SELECT h.scheme_id, h.scheme_name, h.first_seen, h.last_seen,
           count(*)       OVER w_all AS n_names,
           row_number()   OVER w     AS name_seq,
           lag(h.scheme_name)  OVER w AS prev_name,
           lag(h.last_seen)    OVER w AS prev_last_seen,
           lead(h.scheme_name) OVER w AS next_name
    FROM core.scheme_name_history h
    WINDOW w     AS (PARTITION BY h.scheme_id ORDER BY h.first_seen, h.last_seen),
           w_all AS (PARTITION BY h.scheme_id)
)
SELECT s.amfi_code, s.amc_name, s.category, s.plan_type,
       t.name_seq, t.n_names,
       t.prev_name, t.scheme_name AS name_in_use,
       t.first_seen, t.last_seen,
       (t.last_seen - t.first_seen)       AS days_in_use,
       (t.first_seen - t.prev_last_seen)  AS days_since_prev_name_last_seen,
       (t.next_name IS NULL)              AS is_latest_name,
       (t.scheme_name = s.scheme_name)    AS matches_dim_scheme_name,
       rel.related_schemes
FROM timeline t
JOIN core.dim_scheme s USING (scheme_id)
LEFT JOIN LATERAL (
    SELECT string_agg(m.relation_type || '/' || m.status || ' ' || fs.amfi_code || ' -> ' || ts.amfi_code,
                      '; ' ORDER BY m.mapping_id) AS related_schemes
    FROM core.scheme_mapping m
    JOIN core.dim_scheme fs ON fs.scheme_id = m.from_scheme_id
    JOIN core.dim_scheme ts ON ts.scheme_id = m.to_scheme_id
    WHERE m.from_scheme_id = t.scheme_id OR m.to_scheme_id = t.scheme_id
) rel ON true
WHERE t.n_names > 1
ORDER BY s.amc_name, s.amfi_code, t.name_seq
LIMIT 500;
