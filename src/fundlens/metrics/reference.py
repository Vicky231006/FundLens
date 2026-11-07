"""Independent pure-Python reference implementations of the financial formulas.

These deliberately share NO code with the SQL implementations in ``sql/marts``. They exist
so tests can cross-check SQL results, and to give hand-verifiable semantics:

* CAGR     : (V1 / V0) ** (365 / days) - 1                          (actual/365)
* XIRR     : root of sum(cf_i / (1 + r) ** ((d_i - d_0) / 365)) = 0  (Excel-compatible)
* Max DD   : min over t of NAV_t / max(NAV_0..NAV_t) - 1             (always <= 0)
* Vol      : sample std-dev of daily log returns * sqrt(252)
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date

import numpy as np
from scipy.optimize import brentq

TRADING_DAYS_PER_YEAR = 252


def cagr(v0: float, d0: date, v1: float, d1: date) -> float | None:
    days = (d1 - d0).days
    if v0 <= 0 or v1 <= 0 or days <= 0:
        return None
    return (v1 / v0) ** (365.0 / days) - 1.0


def xirr(dates: Sequence[date], flows: Sequence[float]) -> float | None:
    if len(dates) != len(flows) or len(flows) < 2:
        return None
    if not (any(f > 0 for f in flows) and any(f < 0 for f in flows)):
        return None
    t = [(d - dates[0]).days / 365.0 for d in dates]

    def npv(r: float) -> float:
        return sum(f / (1.0 + r) ** ti for f, ti in zip(flows, t, strict=True))

    # Search bracket: rates below -99.9999% or above +100000% are reported as None.
    lo, hi = -0.999999, 1000.0
    if npv(lo) * npv(hi) > 0:
        return None
    return brentq(npv, lo, hi, xtol=1e-14, rtol=1e-14, maxiter=500)


def max_drawdown(navs: Sequence[float]) -> float:
    peak = -math.inf
    worst = 0.0
    for v in navs:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1.0)
    return worst


def annualised_volatility(navs: Sequence[float]) -> float | None:
    if len(navs) < 3:
        return None
    arr = np.asarray(navs, dtype=float)
    log_returns = np.diff(np.log(arr))
    return float(np.std(log_returns, ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))


def percent_rank(values: Sequence[float]) -> list[float]:
    """Same definition as SQL percent_rank(): (rank - 1) / (n - 1), ties share the lowest rank."""
    n = len(values)
    if n <= 1:
        return [0.0] * n
    ordered = sorted(values)
    return [ordered.index(v) / (n - 1) for v in values]
