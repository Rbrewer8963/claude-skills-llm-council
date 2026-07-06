"""Portfolio construction / optimisation.

Closed-form solutions where they exist (global minimum-variance, unconstrained
tangency) and a projected-gradient iteration for risk parity. All optimisers
return fully-invested long weight vectors that sum to 1.

These are the analytical Markowitz results; they are exact for the
unconstrained problem and give the textbook efficient frontier.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from . import risk
from .linalg import Matrix, Vector, dot, inverse, matvec


def _normalize(w: Vector) -> Vector:
    s = sum(w)
    if s == 0:
        raise ValueError("weights sum to zero")
    return [x / s for x in w]


def min_variance(cov: Matrix) -> Vector:
    """Global minimum-variance portfolio:  w = Σ⁻¹1 / (1ᵀΣ⁻¹1)."""
    n = len(cov)
    inv = inverse(cov)
    ones = [1.0] * n
    inv_ones = matvec(inv, ones)
    denom = dot(ones, inv_ones)
    return [x / denom for x in inv_ones]


def max_sharpe(mu: Vector, cov: Matrix, risk_free: float = 0.0) -> Vector:
    """Tangency (maximum-Sharpe) portfolio for the unconstrained problem.

    w ∝ Σ⁻¹(μ − r_f·1), renormalised to sum to 1.
    """
    n = len(mu)
    inv = inverse(cov)
    excess = [m - risk_free for m in mu]
    raw = matvec(inv, excess)
    return _normalize(raw)


def mean_variance(mu: Vector, cov: Matrix, target_return: float) -> Vector:
    """Minimum-variance portfolio achieving a target expected return.

    Solves the classic two-constraint Markowitz problem (fully invested,
    expected return = target) in closed form via the frontier's A/B/C/D scalars.
    """
    n = len(mu)
    inv = inverse(cov)
    ones = [1.0] * n
    inv_one = matvec(inv, ones)
    inv_mu = matvec(inv, mu)
    A = dot(ones, inv_mu)     # 1ᵀ Σ⁻¹ μ
    B = dot(mu, inv_mu)       # μᵀ Σ⁻¹ μ
    C = dot(ones, inv_one)    # 1ᵀ Σ⁻¹ 1
    D = B * C - A * A
    if abs(D) < 1e-18:
        raise ValueError("degenerate frontier (assets are collinear)")
    lam = (C * target_return - A) / D
    gam = (B - A * target_return) / D
    return [lam * im + gam * io for im, io in zip(inv_mu, inv_one)]


def risk_parity(cov: Matrix, max_iter: int = 10_000, tol: float = 1e-10) -> Vector:
    """Equal-risk-contribution weights via a multiplicative fixed-point update.

    Each position ends up contributing the same share of total portfolio
    variance — the construction underpinning "all-weather" style books.
    """
    n = len(cov)
    w = [1.0 / n] * n
    target = 1.0 / n
    for _ in range(max_iter):
        cov_w = matvec(cov, w)
        port_var = dot(w, cov_w)
        if port_var <= 0:
            break
        # Multiplicative update nudging each weight toward equal risk share.
        new = []
        for i in range(n):
            rc = w[i] * cov_w[i] / port_var           # current risk contribution
            factor = (target / rc) ** 0.5 if rc > 0 else 1.0
            new.append(w[i] * factor)
        new = _normalize(new)
        if max(abs(a - b) for a, b in zip(new, w)) < tol:
            w = new
            break
        w = new
    return w


def equal_weight(n: int) -> Vector:
    return [1.0 / n] * n


@dataclass
class FrontierPoint:
    target_return: float
    volatility: float
    weights: Vector


def efficient_frontier(mu: Vector, cov: Matrix, n_points: int = 25) -> List[FrontierPoint]:
    """Sample the mean-variance efficient frontier between the min and max μ."""
    lo, hi = min(mu), max(mu)
    pts: List[FrontierPoint] = []
    for i in range(n_points):
        t = lo + (hi - lo) * i / (n_points - 1) if n_points > 1 else lo
        try:
            w = mean_variance(mu, cov, t)
        except ValueError:
            continue
        vol = risk.portfolio_volatility(w, cov, annualize=False)
        pts.append(FrontierPoint(t, vol, w))
    return pts
