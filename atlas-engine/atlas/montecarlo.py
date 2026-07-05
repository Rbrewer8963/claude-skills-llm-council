"""Correlated Monte Carlo simulation engine.

This is the core of ATLAS's risk analytics — the same conceptual workload
Aladdin runs daily across trillions in assets. Given a covariance structure it
draws a large number of *jointly consistent* asset-return scenarios (Gaussian
or fat-tailed Student-t), each preserving the empirical correlation matrix via
a Cholesky factorisation.

Downstream, portfolios are revalued under every scenario to build a full P&L
distribution from which VaR, CVaR, and scenario percentiles are read.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class SimulationResult:
    """Container for a Monte Carlo run."""

    asset_returns: np.ndarray   # (n_paths, n_assets) horizon returns
    horizon_days: int
    n_paths: int
    distribution: str

    def portfolio_pnl(self, exposures: np.ndarray) -> np.ndarray:
        """Linear (delta) revaluation: dollar P&L per path."""
        return self.asset_returns @ np.asarray(exposures, float)


def _cholesky_psd(cov: np.ndarray) -> np.ndarray:
    """Robust Cholesky that repairs a non-PSD covariance via eigenvalue clipping."""
    cov = (cov + cov.T) / 2.0
    try:
        return np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        vals, vecs = np.linalg.eigh(cov)
        vals = np.clip(vals, 1e-12, None)
        repaired = (vecs * vals) @ vecs.T
        repaired = (repaired + repaired.T) / 2.0
        return np.linalg.cholesky(repaired)


def simulate(
    mean: np.ndarray,
    cov: np.ndarray,
    n_paths: int = 50_000,
    horizon_days: int = 1,
    annual_days: int = 252,
    distribution: str = "normal",
    student_t_df: float = 5.0,
    antithetic: bool = True,
    seed: int | None = 42,
) -> SimulationResult:
    """Draw correlated horizon returns.

    Parameters
    ----------
    mean, cov:
        **Annualised** expected returns and covariance matrix.
    n_paths:
        Number of Monte Carlo scenarios.
    horizon_days:
        Risk horizon in trading days (e.g. 1, 10, 21).
    distribution:
        ``"normal"`` or ``"t"`` (Student-t for heavier tails).
    antithetic:
        Use antithetic variates to cut sampling error roughly in half.
    """
    mean = np.asarray(mean, float)
    cov = np.asarray(cov, float)
    n = mean.shape[0]
    rng = np.random.default_rng(seed)

    h = horizon_days / annual_days
    mu_h = mean * h
    chol = _cholesky_psd(cov * h)

    m = n_paths // 2 if antithetic else n_paths
    z = rng.standard_normal(size=(m, n))
    if antithetic:
        z = np.vstack([z, -z])
    if z.shape[0] < n_paths:  # odd n_paths
        z = np.vstack([z, rng.standard_normal(size=(n_paths - z.shape[0], n))])

    if distribution == "t":
        df = student_t_df
        if df <= 2:
            raise ValueError("student_t_df must be > 2 for finite variance")
        # Correlated multivariate-t: scale Gaussian by an inverse-gamma mixing.
        g = rng.chisquare(df, size=(z.shape[0], 1)) / df
        z = z / np.sqrt(g)
        z *= np.sqrt((df - 2.0) / df)  # rescale to unit variance
    elif distribution != "normal":
        raise ValueError("distribution must be 'normal' or 't'")

    asset_returns = mu_h + z @ chol.T
    return SimulationResult(asset_returns, horizon_days, asset_returns.shape[0], distribution)
