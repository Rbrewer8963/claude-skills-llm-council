"""Statistics on return series.

Return matrices are stored row-per-period, column-per-asset:

    returns[t][i]  =  return of asset i during period t

which mirrors how time-series data actually arrives and keeps the covariance
estimator readable.
"""

from __future__ import annotations

import math
from typing import List, Sequence

from .linalg import Matrix, Vector

TRADING_DAYS = 252


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def variance(xs: Sequence[float], ddof: int = 1) -> float:
    n = len(xs)
    if n - ddof <= 0:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (n - ddof)


def stdev(xs: Sequence[float], ddof: int = 1) -> float:
    return math.sqrt(variance(xs, ddof))


def columns(returns: Matrix) -> List[Vector]:
    """Transpose a period-by-asset matrix into per-asset series."""
    return [list(col) for col in zip(*returns)]


def covariance_matrix(returns: Matrix, ddof: int = 1) -> Matrix:
    """Sample covariance across assets, given a period-by-asset return matrix."""
    cols = columns(returns)
    means = [mean(c) for c in cols]
    n_obs = len(returns)
    k = len(cols)
    denom = n_obs - ddof
    if denom <= 0:
        raise ValueError("not enough observations to estimate covariance")
    cov = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(i, k):
            s = sum(
                (cols[i][t] - means[i]) * (cols[j][t] - means[j])
                for t in range(n_obs)
            )
            cov[i][j] = cov[j][i] = s / denom
    return cov


def correlation_matrix(returns: Matrix) -> Matrix:
    cov = covariance_matrix(returns)
    k = len(cov)
    sd = [math.sqrt(cov[i][i]) if cov[i][i] > 0 else 0.0 for i in range(k)]
    corr = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(k):
            denom = sd[i] * sd[j]
            corr[i][j] = cov[i][j] / denom if denom > 0 else 0.0
    return corr


def annualize_return(mean_period_return: float, periods: int = TRADING_DAYS) -> float:
    """Geometric annualisation of a per-period mean return."""
    return (1.0 + mean_period_return) ** periods - 1.0


def annualize_vol(period_vol: float, periods: int = TRADING_DAYS) -> float:
    return period_vol * math.sqrt(periods)


def quantile(xs: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile (q in [0, 1]) of an unsorted sample."""
    if not xs:
        raise ValueError("empty sample")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    frac = pos - lo
    return s[lo] * (1 - frac) + s[hi] * frac


def skewness(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 3:
        return 0.0
    m = mean(xs)
    sd = stdev(xs)
    if sd == 0:
        return 0.0
    return (n / ((n - 1) * (n - 2))) * sum(((x - m) / sd) ** 3 for x in xs)


def kurtosis(xs: Sequence[float]) -> float:
    """Excess kurtosis (0 for a normal distribution)."""
    n = len(xs)
    if n < 4:
        return 0.0
    m = mean(xs)
    sd = stdev(xs)
    if sd == 0:
        return 0.0
    num = sum(((x - m) / sd) ** 4 for x in xs)
    a = (n * (n + 1)) / ((n - 1) * (n - 2) * (n - 3))
    b = (3 * (n - 1) ** 2) / ((n - 2) * (n - 3))
    return a * num - b
