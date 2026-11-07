-- Business question: Is the raw AMFI download history complete and healthy? For each source
-- file: which run loaded it, what date range does it cover, are there gaps or overlaps versus
-- earlier ranges, how many lines were malformed or out of scope, and how many NAV rows ended
-- up in core.fact_nav?
-- Demonstrates: running max over date ranges (gap/overlap detection), running sum, lag(),
--               ratio columns, 3-table join (source_file, ingestion_run, aggregated fact_nav).
-- Notes: raw.source_file is append-only provenance. A positive gap_days_before means no file
--        covers those calendar days yet (expected while ingestion is still running);
--        a negative value means overlapping ranges. A row with nav_rows_in_core = 0 may be a
--        range with no in-scope lines or one not yet transformed.
WITH loaded AS (
    SELECT f.file_id, count(*) AS nav_rows_in_core
    FROM core.fact_nav f
    GROUP BY f.file_id
), files AS (
    SELECT sf.file_id, sf.run_id, ir.status AS run_status, ir.requested_from, ir.requested_to,
           sf.from_date, sf.to_date, sf.http_status, sf.retrieved_at,
           sf.data_lines_total, sf.lines_in_scope, sf.lines_out_of_scope, sf.lines_malformed,
           coalesce(l.nav_rows_in_core, 0) AS nav_rows_in_core,
           max(sf.to_date) OVER (ORDER BY sf.from_date, sf.file_id
                                 ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prev_max_to_date,
           sum(sf.lines_in_scope) OVER (ORDER BY sf.from_date, sf.file_id) AS running_in_scope_lines
    FROM raw.source_file sf
    LEFT JOIN raw.ingestion_run ir ON ir.run_id = sf.run_id
    LEFT JOIN loaded l ON l.file_id = sf.file_id
)
SELECT f.file_id, f.run_id, f.run_status, f.from_date, f.to_date,
       (f.to_date - f.from_date + 1)                  AS span_days,
       (f.from_date - f.prev_max_to_date - 1)         AS gap_days_before,
       f.http_status, f.data_lines_total, f.lines_in_scope, f.lines_out_of_scope, f.lines_malformed,
       round(100.0 * f.lines_malformed / nullif(f.data_lines_total, 0), 3) AS malformed_pct,
       f.nav_rows_in_core,
       round(f.nav_rows_in_core::numeric / nullif(f.lines_in_scope, 0), 3) AS core_rows_per_in_scope_line,
       f.running_in_scope_lines,
       f.retrieved_at
FROM files f
ORDER BY f.from_date, f.file_id;
