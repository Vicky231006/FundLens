-- 001: Raw layer. Original AMFI downloads (files on disk) are registered here with
-- provenance; in-scope raw lines are stored verbatim. Raw tables are append-only:
-- triggers reject UPDATE/DELETE/TRUNCATE from the normal ingestion workflow.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS marts;

CREATE TABLE raw.ingestion_run (
    run_id          BIGSERIAL PRIMARY KEY,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL DEFAULT 'RUNNING'
                    CHECK (status IN ('RUNNING', 'SUCCEEDED', 'FAILED')),
    requested_from  DATE NOT NULL,
    requested_to    DATE NOT NULL,
    files_total     INTEGER NOT NULL DEFAULT 0,
    files_new       INTEGER NOT NULL DEFAULT 0,
    rows_loaded     BIGINT NOT NULL DEFAULT 0,
    error_message   TEXT,
    CHECK (requested_from <= requested_to)
);

CREATE TABLE raw.source_file (
    file_id             BIGSERIAL PRIMARY KEY,
    run_id              BIGINT REFERENCES raw.ingestion_run (run_id),
    source_name         TEXT NOT NULL DEFAULT 'AMFI',
    source_url          TEXT NOT NULL,
    retrieved_at        TIMESTAMPTZ NOT NULL,
    from_date           DATE NOT NULL,
    to_date             DATE NOT NULL,
    http_status         INTEGER NOT NULL,
    file_path           TEXT NOT NULL,
    sha256              CHAR(64) NOT NULL,
    byte_size           BIGINT NOT NULL,
    lines_total         BIGINT NOT NULL,
    data_lines_total    BIGINT NOT NULL,   -- scheme-code;...;date lines in the file
    lines_in_scope      BIGINT NOT NULL,   -- stored in raw.nav_line
    lines_out_of_scope  BIGINT NOT NULL,   -- present on disk only
    lines_malformed     BIGINT NOT NULL,
    scope_config_hash   CHAR(64) NOT NULL,
    CONSTRAINT uq_source_file_sha UNIQUE (sha256),
    CHECK (from_date <= to_date)
);
CREATE INDEX ix_source_file_range ON raw.source_file (from_date, to_date);

-- One row per in-scope data line, verbatim, with the section context it appeared under.
CREATE TABLE raw.nav_line (
    line_id         BIGSERIAL PRIMARY KEY,
    file_id         BIGINT NOT NULL REFERENCES raw.source_file (file_id),
    line_no         INTEGER NOT NULL,
    section_header  TEXT NOT NULL,   -- e.g. "Open Ended Schemes ( Equity Scheme - Mid Cap Fund )"
    amc_name        TEXT,            -- AMC line preceding the block
    raw_text        TEXT NOT NULL,   -- original semicolon-delimited line
    CONSTRAINT uq_nav_line UNIQUE (file_id, line_no)
);

CREATE OR REPLACE FUNCTION raw.reject_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'raw layer is append-only: % on %.% is not permitted',
        TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_source_file_immutable
    BEFORE UPDATE OR DELETE ON raw.source_file
    FOR EACH ROW EXECUTE FUNCTION raw.reject_mutation();
CREATE TRIGGER trg_source_file_no_truncate
    BEFORE TRUNCATE ON raw.source_file
    FOR EACH STATEMENT EXECUTE FUNCTION raw.reject_mutation();
CREATE TRIGGER trg_nav_line_immutable
    BEFORE UPDATE OR DELETE ON raw.nav_line
    FOR EACH ROW EXECUTE FUNCTION raw.reject_mutation();
CREATE TRIGGER trg_nav_line_no_truncate
    BEFORE TRUNCATE ON raw.nav_line
    FOR EACH STATEMENT EXECUTE FUNCTION raw.reject_mutation();
