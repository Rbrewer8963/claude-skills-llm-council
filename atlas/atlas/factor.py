"""Factor exposure via multiple linear regression.

Regresses an asset's (or portfolio's) return series on a set of factor return
series to recover factor betas, alpha and R². Solved with the normal equations
``β = (XᵀX)⁻¹ Xᵀy`` — exact OLS, no external solver needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from . import stats
from .linalg import Matrix, Vector, dot, inverse, matvec, transpose


@dataclass
class FactorModel:
    factor_names: List[str]
    alpha: float
    betas: Dict[str, float]
    r_squared: float
    residual_vol: float

    def as_dict(self) -> dict:
        return {
            "alpha": self.alpha,
            "betas": self.betas,
            "r_squared": self.r_squared,
            "residual_vol": self.residual_vol,
        }


def fit_factor_model(asset_returns: List[float],
                     factor_returns: Dict[str, List[float]],
                     intercept: bool = True) -> FactorModel:
    """OLS regression of ``asset_returns`` on the supplied factors."""
    names = list(factor_returns.keys())
    n = len(asset_returns)
    # Design matrix X: rows = observations, cols = [1?, factor_1, ..., factor_k]
    X: Matrix = []
    for t in range(n):
        row = [1.0] if intercept else []
        row.extend(factor_returns[name][t] for name in names)
        X.append(row)
    y = list(asset_returns)

    Xt = transpose(X)
    XtX = _matmul(Xt, X)          # XᵀX
    Xty = matvec(Xt, y)
    coef = matvec(inverse(XtX), Xty)

    idx = 0
    alpha = 0.0
    if intercept:
        alpha = coef[0]
        idx = 1
    betas = {name: coef[idx + i] for i, name in enumerate(names)}

    # Fit diagnostics.
    fitted = matvec(X, coef)
    resid = [yi - fi for yi, fi in zip(y, fitted)]
    ss_res = sum(r * r for r in resid)
    y_mean = stats.mean(y)
    ss_tot = sum((yi - y_mean) ** 2 for yi in y)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    dof = max(n - len(coef), 1)
    resid_vol = (ss_res / dof) ** 0.5

    return FactorModel(names, alpha, betas, r2, resid_vol)


def _matmul(A: Matrix, B: Matrix) -> Matrix:
    Bt = transpose(B)
    return [[dot(row, col) for col in Bt] for row in A]
