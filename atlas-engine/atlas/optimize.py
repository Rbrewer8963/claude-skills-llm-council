"""Portfolio construction and optimisation.

ATLAS provides the classic Markowitz toolkit plus **risk parity**, which
allocates by *risk contribution* rather than capital and underpins many of the
world's largest allocators. Closed-form solutions are used where they exist;
constrained problems fall back to SLSQP (SciPy) and, if SciPy is unavailable, a
projected-gradient solver so the engine degrades gracefully.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:  # SciPy is optional for constrained optimisation.
    from scipy.optimize import minimize
    _HAVE_SCIPY = True
except Exception:  # pragma: no cover
    _HAVE_SCIPY = False


@dataclass
class OptimizationResult:
    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe: float
    objective: str

    def __str__(self) -> str:
        top = sorted(self.weights.items(), key=lambda kv: -abs(kv[1]))[:6]
        holdings = ", ".join(f"{s} {w:.1%}" for s, w in top)
        return (f"[{self.objective}] E[r]={self.expected_return:.2%} "
                f"vol={self.volatility:.2%} Sharpe={self.sharpe:.2f} | {holdings}")


def _stats(w, mu, cov, rf):
    ret = float(w @ mu)
    vol = float(np.sqrt(w @ cov @ w))
    sharpe = (ret - rf) / vol if vol > 0 else 0.0
    return ret, vol, sharpe


def _pack(symbols, w, mu, cov, rf, objective) -> OptimizationResult:
    ret, vol, sharpe = _stats(w, mu, cov, rf)
    return OptimizationResult(dict(zip(symbols, w)), ret, vol, sharpe, objective)


def min_variance(symbols, cov: np.ndarray, long_only: bool = True,
                 mu: np.ndarray | None = None, rf: float = 0.02) -> OptimizationResult:
    """Global minimum-variance portfolio. ``mu`` is used only for reporting stats."""
    n = len(symbols)
    if not long_only:
        inv = np.linalg.pinv(cov)
        ones = np.ones(n)
        w = inv @ ones / (ones @ inv @ ones)
    else:
        w = _solve_qp(cov, np.zeros(n), n)
    mu = np.zeros(n) if mu is None else np.asarray(mu, float)
    return _pack(symbols, w, mu, cov, rf, "min-variance")


def max_sharpe(symbols, mu: np.ndarray, cov: np.ndarray, rf: float = 0.02,
               long_only: bool = True) -> OptimizationResult:
    """Tangency (maximum Sharpe) portfolio."""
    n = len(symbols)
    excess = mu - rf
    if not long_only:
        inv = np.linalg.pinv(cov)
        w = inv @ excess
        w = w / w.sum()
    else:
        def neg_sharpe(w):
            ret, vol, _ = _stats(w, mu, cov, rf)
            return -(ret - rf) / vol if vol > 0 else 1e6
        w = _solve_general(neg_sharpe, n)
    return _pack(symbols, w, mu, cov, rf, "max-sharpe")


def risk_parity(symbols, cov: np.ndarray, mu: np.ndarray | None = None,
                rf: float = 0.02) -> OptimizationResult:
    """Equal risk contribution (ERC) portfolio. ``mu`` is used only for reporting."""
    n = len(symbols)
    target = np.ones(n) / n

    def objective(w):
        w = np.abs(w)
        w = w / w.sum()
        port_vol = np.sqrt(w @ cov @ w)
        mrc = cov @ w / port_vol
        rc = w * mrc / port_vol            # normalised risk contributions
        return np.sum((rc - target) ** 2)

    w = _solve_general(objective, n)
    mu = np.zeros(n) if mu is None else np.asarray(mu, float)
    return _pack(symbols, w, mu, cov, rf, "risk-parity")


def efficient_frontier(symbols, mu: np.ndarray, cov: np.ndarray, n_points: int = 25,
                       long_only: bool = True) -> list[OptimizationResult]:
    """Trace the efficient frontier across target returns."""
    lo, hi = float(mu.min()), float(mu.max())
    targets = np.linspace(lo, hi, n_points)
    out = []
    n = len(symbols)
    for t in targets:
        if long_only and _HAVE_SCIPY:
            cons = [
                {"type": "eq", "fun": lambda w: w.sum() - 1.0},
                {"type": "eq", "fun": lambda w, t=t: w @ mu - t},
            ]
            res = minimize(lambda w: w @ cov @ w, np.ones(n) / n, method="SLSQP",
                           bounds=[(0.0, 1.0)] * n, constraints=cons,
                           options={"maxiter": 500, "ftol": 1e-10})
            w = res.x
        else:
            w = _frontier_analytic(mu, cov, t)
        out.append(_pack(symbols, w, mu, cov, 0.0, f"frontier@{t:.1%}"))
    return out


# --------------------------------------------------------------------- solvers
def _solve_general(objective, n: int) -> np.ndarray:
    """Long-only, fully-invested optimiser with SciPy or projected-gradient fallback."""
    x0 = np.ones(n) / n
    if _HAVE_SCIPY:
        cons = [{"type": "eq", "fun": lambda w: w.sum() - 1.0}]
        res = minimize(objective, x0, method="SLSQP", bounds=[(0.0, 1.0)] * n,
                       constraints=cons, options={"maxiter": 1000, "ftol": 1e-12})
        w = np.clip(res.x, 0, None)
        return w / w.sum()
    return _projected_gradient(objective, x0)


def _solve_qp(cov: np.ndarray, mu: np.ndarray, n: int) -> np.ndarray:
    """Long-only minimum-variance via SciPy or fallback."""
    return _solve_general(lambda w: w @ cov @ w, n)


def _projected_gradient(objective, x0, steps: int = 4000, lr: float = 0.05) -> np.ndarray:
    """Numerical-gradient projected descent onto the simplex (SciPy-free fallback)."""
    w = x0.copy()
    eps = 1e-6
    for _ in range(steps):
        g = np.zeros_like(w)
        f0 = objective(w)
        for i in range(len(w)):
            w[i] += eps
            g[i] = (objective(w) - f0) / eps
            w[i] -= eps
        w = _project_simplex(w - lr * g)
    return w


def _project_simplex(v: np.ndarray) -> np.ndarray:
    """Euclidean projection onto {w >= 0, sum w = 1} (Duchi et al., 2008)."""
    u = np.sort(v)[::-1]
    css = np.cumsum(u) - 1.0
    rho = np.nonzero(u - css / (np.arange(len(v)) + 1) > 0)[0][-1]
    theta = css[rho] / (rho + 1.0)
    return np.maximum(v - theta, 0.0)


def _frontier_analytic(mu, cov, target) -> np.ndarray:
    """Closed-form min-variance for a target return (allows shorts)."""
    inv = np.linalg.pinv(cov)
    ones = np.ones(len(mu))
    a = ones @ inv @ ones
    b = ones @ inv @ mu
    c = mu @ inv @ mu
    d = a * c - b * b
    if abs(d) < 1e-18:
        return inv @ ones / a
    lam = (c - b * target) / d
    gam = (a * target - b) / d
    return inv @ (lam * ones + gam * mu)
