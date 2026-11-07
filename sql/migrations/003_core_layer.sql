-- 003: Standardised analytical layer.

-- Scheme identity: AMFI scheme code identifies one share class (plan + option) and is
-- stable across renames. Name similarity is NEVER used to merge schemes (FR-A2).
CREATE TABLE core.dim_scheme (
    scheme_id        BIGSERIAL PRIMARY KEY,
    amfi_code        TEXT NOT NULL UNIQUE,
    scheme_name      TEXT NOT NULL,          -- most recent name seen
    amc_name         TEXT,
    category         TEXT NOT NULL,          -- normalised category (see ADR D-005)
    category_raw     TEXT NOT NULL,          -- section header as published by AMFI
    plan_type        TEXT NOT NULL CHECK (plan_type IN ('DIRECT', 'REGULAR', 'UNKNOWN')),
    option_type      TEXT NOT NULL CHECK (option_type IN ('GROWTH', 'IDCW', 'UNKNOWN')),
    isin             TEXT,
    first_nav_date   DATE,
    last_nav_date    DATE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_dim_scheme_category ON core.dim_scheme (category);

-- Every distinct name observed for a scheme code (evidence of renames).
CREATE TABLE core.scheme_name_history (
    scheme_id    BIGINT NOT NULL REFERENCES core.dim_scheme (scheme_id),
    scheme_name  TEXT NOT NULL,
    first_seen   DATE NOT NULL,
    last_seen    DATE NOT NULL,
    PRIMARY KEY (scheme_id, scheme_name)
);

-- Explicit, evidence-backed relationships between schemes. Never inferred from name
-- similarity. Candidates need review before status = 'CONFIRMED'.
CREATE TABLE core.scheme_mapping (
    mapping_id       BIGSERIAL PRIMARY KEY,
    from_scheme_id   BIGINT NOT NULL REFERENCES core.dim_scheme (scheme_id),
    to_scheme_id     BIGINT NOT NULL REFERENCES core.dim_scheme (scheme_id),
    relation_type    TEXT NOT NULL CHECK (relation_type IN ('RENAME', 'MERGE', 'SPLIT', 'REPLACED_BY')),
    effective_date   DATE,
    evidence         TEXT NOT NULL,          -- source document / reasoning
    status           TEXT NOT NULL DEFAULT 'CANDIDATE' CHECK (status IN ('CANDIDATE', 'CONFIRMED', 'REJECTED')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (from_scheme_id <> to_scheme_id),
    UNIQUE (from_scheme_id, to_scheme_id, relation_type)
);

CREATE TABLE core.dim_date (
    date_key         INTEGER PRIMARY KEY,    -- YYYYMMDD
    cal_date         DATE NOT NULL UNIQUE,
    year             SMALLINT NOT NULL,
    quarter          SMALLINT NOT NULL,
    month            SMALLINT NOT NULL,
    day_of_month     SMALLINT NOT NULL,
    iso_weekday      SMALLINT NOT NULL,
    is_weekday       BOOLEAN NOT NULL,
    is_observed_day  BOOLEAN NOT NULL DEFAULT false,  -- NAV published for the market (derived)
    is_month_end     BOOLEAN NOT NULL DEFAULT false   -- last observed day of its month
);

CREATE TABLE core.fact_nav (
    scheme_id   BIGINT NOT NULL REFERENCES core.dim_scheme (scheme_id),
    nav_date    DATE NOT NULL REFERENCES core.dim_date (cal_date),
    nav         NUMERIC(20, 6) NOT NULL,
    file_id     BIGINT NOT NULL REFERENCES raw.source_file (file_id),
    loaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (scheme_id, nav_date)
);
CREATE INDEX ix_fact_nav_date ON core.fact_nav (nav_date);

-- A re-download that disagrees with an already-loaded NAV is recorded, never silently applied.
CREATE TABLE core.nav_revision_conflict (
    conflict_id  BIGSERIAL PRIMARY KEY,
    scheme_id    BIGINT NOT NULL REFERENCES core.dim_scheme (scheme_id),
    nav_date     DATE NOT NULL,
    existing_nav NUMERIC(20, 6) NOT NULL,
    incoming_nav NUMERIC(20, 6) NOT NULL,
    file_id      BIGINT NOT NULL REFERENCES raw.source_file (file_id),
    detected_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (scheme_id, nav_date, file_id)
);

CREATE TABLE core.dq_issue (
    issue_id           BIGSERIAL PRIMARY KEY,
    fingerprint        TEXT NOT NULL UNIQUE,   -- makes repeated DQ runs idempotent
    scheme_id          BIGINT REFERENCES core.dim_scheme (scheme_id),
    issue_category     TEXT NOT NULL,
    severity           TEXT NOT NULL CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL')),
    detected_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    nav_date           DATE,
    observation        JSONB NOT NULL,         -- the relevant observation(s)
    explanation        TEXT NOT NULL,
    resolution_status  TEXT NOT NULL DEFAULT 'OPEN'
                       CHECK (resolution_status IN ('OPEN', 'ACKNOWLEDGED', 'RESOLVED', 'WONT_FIX')),
    resolved_at        TIMESTAMPTZ,
    resolution_note    TEXT,
    run_id             BIGINT REFERENCES raw.ingestion_run (run_id)
);
CREATE INDEX ix_dq_issue_scheme ON core.dq_issue (scheme_id);
CREATE INDEX ix_dq_issue_open_severity ON core.dq_issue (severity) WHERE resolution_status = 'OPEN';
