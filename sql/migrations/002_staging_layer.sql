-- 002: Staging layer. Parsing, typing, normalisation, duplicate identification and
-- invalid-record handling. Rows are derived from raw.nav_line and are rebuildable.

CREATE TABLE staging.nav_parsed (
    file_id          BIGINT NOT NULL REFERENCES raw.source_file (file_id),
    line_no          INTEGER NOT NULL,
    section_header   TEXT NOT NULL,
    amc_name         TEXT,
    scheme_code      TEXT,
    scheme_name      TEXT,
    plan_raw         TEXT,
    option_raw       TEXT,
    isin_payout      TEXT,
    isin_reinvest    TEXT,
    nav_raw          TEXT,
    date_raw         TEXT,
    nav              NUMERIC(20, 6),
    nav_date         DATE,
    category         TEXT,            -- normalised category (config/scope.toml)
    plan_type        TEXT,            -- DIRECT | REGULAR | UNKNOWN
    option_type      TEXT,            -- GROWTH | IDCW | UNKNOWN
    parse_status     TEXT NOT NULL CHECK (parse_status IN ('VALID', 'REJECTED', 'DUPLICATE')),
    reject_reason    TEXT,
    PRIMARY KEY (file_id, line_no)
);
CREATE INDEX ix_staging_status ON staging.nav_parsed (parse_status);
CREATE INDEX ix_staging_scheme_date ON staging.nav_parsed (scheme_code, nav_date);
