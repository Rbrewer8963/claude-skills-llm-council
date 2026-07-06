"""Distribution helpers and a seedable correlated-normal generator.

Everything the risk models need from a stats package: the standard-normal PDF,
CDF, and its inverse (for parametric VaR z-scores), plus a generator that turns
independent normals into correlated draws via a Cholesky factor.
"""

from __future__ import annotations

import math
import random
from typing import List

from .linalg import Matrix, Vector, cholesky, matvec

SQRT2PI = math.sqrt(2.0 * math.pi)


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / SQRT2PI


def norm_cdf(x: float) -> float:
    """Standard-normal CDF via the erf identity."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse standard-normal CDF (Acklam's rational approximation).

    Accurate to ~1e-9 across the open interval (0, 1), which is far more than
    enough for VaR confidence levels.
    """
    if not 0.0 < p < 1.0:
        raise ValueError("p must be in the open interval (0, 1)")

    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]

    plow = 0.02425
    phigh = 1 - plow
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
               (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)


class CorrelatedNormalGenerator:
    """Draw vectors of correlated normals with a fixed mean and covariance.

    The covariance is factored once via Cholesky; each draw is then a cheap
    matrix-vector product against a vector of independent standard normals.
    """

    def __init__(self, mean: Vector, cov: Matrix, seed: int | None = None):
        self.mean = list(mean)
        self.L = cholesky(cov)
        self.k = len(mean)
        self._rng = random.Random(seed)

    def draw(self) -> Vector:
        z = [self._rng.gauss(0.0, 1.0) for _ in range(self.k)]
        correlated = matvec(self.L, z)
        return [m + c for m, c in zip(self.mean, correlated)]

    def draws(self, n: int) -> List[Vector]:
        return [self.draw() for _ in range(n)]
