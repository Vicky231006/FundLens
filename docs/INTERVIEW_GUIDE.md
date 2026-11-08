# Interview Guide — FundLens (honest, defensible)

FundLens is an **analyst-support** (research review) analytics project — **not** an investment recommendation engine. Use this to explain what you built, what the evidence shows, and what it does *not* show.

## What the system does
- Ingests **genuine AMFI** mutual-fund NAV history into **PostgreSQL** (idempotent, provenance/fingerprints), checks **data quality** (13 automated rules; unresolved **CRITICAL** blocks analytics), computes metrics in SQL (rolling CAGRs, vol, max drawdown, XIRR, category percentiles), applies an **explainable** flag rule (k consecutive month-ends: bottom-quartile 3Y CAGR in category/plan **and** drawdown worse than median), and evaluates via **leakage-controlled walk-forward backtest** (60/40 split + purging, training-only tuning, baselines, fund-cluster & 12-month block bootstrap 95% CIs, permutation test). Plan types (**DIRECT/REGULAR**) are never mixed. Power BI PBIP reads `marts.dash_*`.

## What the backtest found (out-of-sample, preserved results 2026-11-07)
*y* = forward 12-month return − category median forward 12-month return. **Lower *y* among flagged funds = flags identified later underperformers** (the intended signal).

| Slice | Screen mean *y* | Fund-cluster 95% CI | Permutation p (`p_value_flagged_worse_than_random`) | Reading |
|---|---:|---:|---:|---|
| **Direct, default (primary)** | **+0.20%** (n=1,015) | [-0.99%, 1.60%] | 0.932 | **Inconclusive** (CI includes 0; not worse than random) |
| **Direct, tuned** | **+0.13%** (n=616) | [-1.41%, 1.96%] | 0.835 | **Inconclusive** |
| **Regular, default** | **+1.38%** (n=1,991) | [0.45%, 2.45%] | 1.000 | **Evidence in the opposite direction** (flagged outperformed; CI entirely > 0) |
| **Regular, tuned** | **+0.53%** (n=1,859) | [-2.86%, 1.43%]* | 0.962 | **Inconclusive** |

\*Use the exact values in `RESULTS.md`/JSON as source of truth; Regular tuned fund-cluster CI in JSON is `[-0.29%, 1.43%]` (crosses 0) — inconclusive.

**Bottom line:** The evaluation **does not validate** the intended underperformance-screening hypothesis. It is not “no result found and ignored” — disappointing/opposite-direction results are reported prominently.

## How to read the statistics (important)
- **CIs crossing zero:** inconclusive for that estimate/method.
- **Screen CI entirely above zero (positive *y*):** flagged funds *outperformed* peers on average — **opposite** of the screen’s intent.
- **Permutation p-value (direction/tail):** one-sided **lower-tail** on mean *y*: `p = P(null random-flag mean y <= observed) + 1 smoothing` (`stats.permutation_baseline`). **Small p** ⇒ observed is unusually **low** ⇒ flagged did **worse** than random. **Large p (e.g., 0.93, 1.00)** ⇒ observed is **not** worse than random (often higher/better). p=0.93 does **not** mean “93% chance it works.”
- **Baseline 1 (bottom-quartile 1Y):** in Direct OOS default, fund-cluster CI for baseline mean *y* is below zero ([-1.37%, -0.10%]) with permutation p≈0.0005, but **month-block bootstrap CI crosses zero** and dependence/regime effects matter — **do not claim the 1Y baseline is statistically validated** as a blanket conclusion.

## Limitations to state clearly
Survivorship bias (missing closed/merged funds, bias direction discussed but magnitude unknown), current AMFI category labels applied historically, overlapping 12M windows / dependent observations (neither bootstrap fully removes dependence), short Direct OOS window, parameter grid selection optimism (test reported for default and tuned). No clients/AUM/users; not production/GIPS-compliant.

## Reproducible anchors (cite if asked)
104 tests passing (fresh run; unit/property-Hypothesis/integration), 13 DQ rules, 779 schemes / 1,811,703 NAV rows / 85 source files, measured perf (e.g., 5×/16.1× index speedups; 129.9s MV refresh) — all in repo docs/results. `make reproduce` regenerates measured outputs from the DB.
