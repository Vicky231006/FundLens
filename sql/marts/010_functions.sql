-- Financial helper functions. Conventions (documented in docs/ARCHITECTURE.md):
--   * Day count: actual/365 for every annualisation of returns (CAGR and XIRR agree, and
--     XIRR matches Excel's XIRR).
--   * Volatility annualisation: sqrt(252) applied to the sample standard deviation of daily
--     log returns (252 = conventional trading days; India has ~247-250 NSE sessions).

-- Latest NAV on or before p_date, but no more than p_tolerance calendar days earlier.
-- Returns no row (so the calling metric is NULL) when history is insufficient or missing:
-- a missing anchor NAV is never silently replaced by a distant one.
CREATE OR REPLACE FUNCTION marts.nav_asof(p_scheme BIGINT, p_date DATE, p_tolerance INT DEFAULT 5)
RETURNS TABLE (nav_date DATE, nav NUMERIC) AS $$
    SELECT f.nav_date, f.nav
    FROM core.fact_nav f
    WHERE f.scheme_id = p_scheme AND f.nav_date <= p_date AND f.nav_date >= p_date - p_tolerance
    ORDER BY f.nav_date DESC
    LIMIT 1
$$ LANGUAGE sql STABLE;

-- Annualised growth from v0 on d0 to v1 on d1 (actual/365). NULL for non-positive inputs.
CREATE OR REPLACE FUNCTION marts.cagr(v0 NUMERIC, d0 DATE, v1 NUMERIC, d1 DATE)
RETURNS DOUBLE PRECISION AS $$
    SELECT CASE WHEN v0 > 0 AND v1 > 0 AND d1 > d0
                THEN power((v1 / v0)::double precision, 365.0 / (d1 - d0)) - 1 END
$$ LANGUAGE sql IMMUTABLE;

-- XIRR (Excel-compatible): the rate r solving sum(cf_i / (1+r)^((d_i - d_0)/365)) = 0, where
-- d_0 is the FIRST element's date. Newton's method safeguarded by a bisection bracket.
-- Returns NULL when there is no sign change (no root) or on non-convergence.
CREATE OR REPLACE FUNCTION marts.xirr(p_dates DATE[], p_flows DOUBLE PRECISION[])
RETURNS DOUBLE PRECISION AS $$
DECLARE
    n INT := array_length(p_dates, 1);
    t DOUBLE PRECISION[];
    lo DOUBLE PRECISION := -0.999999;
    hi DOUBLE PRECISION := 1000;
    r DOUBLE PRECISION := 0.1;
    f DOUBLE PRECISION; df DOUBLE PRECISION; f_lo DOUBLE PRECISION; f_hi DOUBLE PRECISION;
    step DOUBLE PRECISION; base DOUBLE PRECISION; p DOUBLE PRECISION;
    i INT; it INT;
    has_pos BOOLEAN := false; has_neg BOOLEAN := false;
BEGIN
    IF n IS NULL OR n < 2 OR n <> array_length(p_flows, 1) THEN RETURN NULL; END IF;
    FOR i IN 1..n LOOP
        IF p_flows[i] > 0 THEN has_pos := true; ELSIF p_flows[i] < 0 THEN has_neg := true; END IF;
    END LOOP;
    IF NOT (has_pos AND has_neg) THEN RETURN NULL; END IF;

    t := ARRAY(SELECT (d - p_dates[1])::double precision / 365.0 FROM unnest(p_dates) AS d);

    -- f(r) at the bracket ends
    f_lo := 0; f_hi := 0;
    FOR i IN 1..n LOOP
        f_lo := f_lo + p_flows[i] / power(1 + lo, t[i]);
        f_hi := f_hi + p_flows[i] / power(1 + hi, t[i]);
    END LOOP;
    IF f_lo * f_hi > 0 THEN RETURN NULL; END IF;

    FOR it IN 1..200 LOOP
        f := 0; df := 0; base := 1 + r;
        FOR i IN 1..n LOOP
            p := power(base, t[i]);
            f := f + p_flows[i] / p;
            df := df - t[i] * p_flows[i] / (p * base);
        END LOOP;
        IF abs(f) < 1e-9 THEN RETURN r; END IF;
        -- shrink the bracket using the sign of f
        IF (f > 0) = (f_lo > 0) THEN lo := r; f_lo := f; ELSE hi := r; f_hi := f; END IF;
        IF df = 0 THEN
            step := NULL;
        ELSE
            step := r - f / df;
        END IF;
        IF step IS NULL OR step <= lo OR step >= hi THEN
            r := (lo + hi) / 2;          -- bisection fallback
        ELSE
            r := step;
        END IF;
        IF hi - lo < 1e-14 THEN RETURN r; END IF;
    END LOOP;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
