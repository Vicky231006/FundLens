-- 007: Persisted outputs of the screening engine and the backtest. These are results of
-- computations over marts, stored so the dashboard and RESULTS.md read exactly what was run.

CREATE TABLE marts.screening_run (
    run_id      BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    label       TEXT NOT NULL,                 -- 'default' | 'tuned' | custom
    plan_type   TEXT NOT NULL CHECK (plan_type IN ('DIRECT', 'REGULAR')),
    params      JSONB NOT NULL,
    n_flags     INTEGER NOT NULL DEFAULT 0
);

-- One row per flagged (scheme, month-end). A flag is a RESEARCH-REVIEW flag, not advice.
CREATE TABLE marts.review_flag (
    run_id                 BIGINT NOT NULL REFERENCES marts.screening_run (run_id) ON DELETE CASCADE,
    scheme_id              BIGINT NOT NULL REFERENCES core.dim_scheme (scheme_id),
    me_date                DATE NOT NULL,
    streak_months          INTEGER NOT NULL CHECK (streak_months >= 1),
    cagr_3y                DOUBLE PRECISION,
    pct_rank_cagr_3y       DOUBLE PRECISION,
    max_drawdown_3y        NUMERIC,
    median_max_drawdown_3y DOUBLE PRECISION,
    peers_3y               INTEGER,
    explanation            TEXT NOT NULL,
    PRIMARY KEY (run_id, scheme_id, me_date)
);
CREATE INDEX ix_review_flag_date ON marts.review_flag (run_id, me_date);

CREATE TABLE marts.backtest_run (
    run_id      BIGSERIAL PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    plan_type   TEXT NOT NULL,
    seed        INTEGER NOT NULL,
    config      JSONB NOT NULL,
    dataset     JSONB NOT NULL,
    results     JSONB NOT NULL
);
