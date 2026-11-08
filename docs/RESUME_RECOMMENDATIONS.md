# Resume Recommendations (reproducible figures only)

Use **only** figures that can be independently reproduced from this repository/database run (see `RESULTS.md`, `results/backtest_*.json`, `docs/PERFORMANCE.md`, `docs/DATA_CARD.md`). Do **not** claim predictive ability, clients/AUM/users, production/GIPS compliance, or statistical validation that the results do not support.

> **Honesty note (audit 2026-11-08):** The out-of-sample walk-forward evaluation **did not validate** the intended underperformance-screening hypothesis. Direct plans (primary spec): **inconclusive** (95% CIs include zero). Regular plans: **default params show evidence in the opposite direction** (flagged funds outperformed; fund-cluster 95% CI above zero), **tuned params inconclusive**. The simple 1-year bottom-quartile baseline shows negative mean *y* in Direct OOS (fund-cluster CI below zero) but mixed sensitivity across bootstrap methods/plan types — describe carefully, never as “statistically validated” without qualification.

## Safe, reproducible bullets (tailor wording; keep facts exact)

- Built **FundLens**, an explainable mutual-fund **research-review** analytics pipeline (not investment advice) ingesting genuine **AMFI** NAV history into **PostgreSQL 16**, with idempotent loads, raw-file provenance (SHA-256), and a **13-rule automated data-quality** framework (CRITICAL/ERROR/WARNING) where **unresolved CRITICAL issues gate** downstream analytics.
- Modeled and computed performance/risk in SQL (e.g., rolling CAGRs, volatility, max drawdown, SIP XIRR, category percentiles) over **779 schemes** / **1,811,703 NAV rows** (2006-04-02–2026-11-06, **85** registered source files), with **88,300** month-end metric rows (measured run 2026-11-07; see `RESULTS.md`/`docs/PERFORMANCE.md`).
- Implemented a configurable, explainable screen (k consecutive month-ends: bottom-quartile 3Y CAGR within category/plan **and** drawdown worse than median) and a **leakage-controlled walk-forward backtest** (60/40 split with label purging, training-only tuning, 30-candidate grid) with **fund-clustered and 12-month block bootstrap 95% CIs** and **permutation/random-flag** baselines (2,000 permutations, seed fixed).
- Reported results **transparently, by plan type** (Direct primary): OOS screen mean *y* (excess 12M forward return vs category median) **+0.20%** Direct default (n=1,015, 95% fund-cluster CI **[-0.99%, 1.60%]**, inconclusive) and **+1.38%** Regular default (n=1,991, CI **[0.45%, 2.45%]**, opposite of intended underperformance signal); documented limitations (survivorship bias, overlapping windows, current category labels, short Direct OOS window).
- Measured performance on the developer dataset (Docker Postgres 16, single user): e.g., **5.0×** speedup on scheme drilldown with index vs seq scan, **16.1×** on same-date NAV lookup, MV refresh **129.9 s** for 88,300 rows (median of 15 runs; see `docs/PERFORMANCE.md`).
- Maintained **104 automated tests** passing (fresh run: **104 passed in ~72s**, includes unit, **property-based [Hypothesis]**, and integration tests creating throwaway databases) plus CI workflows; Power BI PBIP dashboard validated (**0 errors**) against `marts` views.

## Avoid (not supported / not true)
- “Predicted/identified underperformers,” “alpha,” or any validated outperformance/underperformance claim from the screen.
- “Statistically validated 1-year baseline” as a blanket claim (report its CIs/method sensitivity; Direct OOS fund-cluster CI for baseline 1 is below zero, but block bootstrap crosses zero and results vary by context).
- Production-grade, GIPS-compliant, real clients/accounts/AUM/users.
