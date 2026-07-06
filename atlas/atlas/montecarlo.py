"""Monte-Carlo simulation engine.

Simulates correlated multi-asset paths and aggregates them into a portfolio
P&L distribution, from which VaR, CVaR and percentile bands are read off. This
is the distribution-free workhorse behind the risk report: it makes no
normality assumption at the *portfolio* level even though the per-step shocks
are Gaussian, because path-dependency and rebalancing can be layered on top.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List

from . import stats
from .distributions import CorrelatedNormalGenerator
from .linalg import Matrix, Vector, dot
from .risk import historical_cvar, historical_var


@dataclass
class SimulationResult:
    horizon_days: int
    n_paths: int
    pnl: List[float]                 # simulated P&L per path, currency units
    terminal_values: List[float]     # simulated terminal portfolio values

    def var(self, confidence: float = 0.95) -> float:
        return historical_var(self.pnl, confidence)

    def cvar(self, confidence: float = 0.95) -> float:
        return historical_cvar(self.pnl, confidence)

    def percentile(self, q: float) -> float:
        return stats.quantile(self.terminal_values, q)

    def summary(self) -> Dict[str, float]:
        return {
            "mean_pnl": stats.mean(self.pnl),
            "pnl_stdev": stats.stdev(self.pnl),
            "var_95": self.var(0.95),
            "cvar_95": self.cvar(0.95),
            "var_99": self.var(0.99),
            "p05_value": self.percentile(0.05),
            "p50_value": self.percentile(0.50),
            "p95_value": self.percentile(0.95),
            "worst_path": min(self.pnl),
            "best_path": max(self.pnl),
        }


class MonteCarloEngine:
    """Correlated geometric-Brownian-motion simulator over a set of assets.

    Parameters
    ----------
    mu   : per-step (e.g. daily) expected return per asset
    cov  : per-step covariance matrix of returns
    seed : RNG seed for reproducibility
    """

    def __init__(self, mu: Vector, cov: Matrix, seed: int | None = None):
        self.mu = list(mu)
        self.cov = cov
        self._gen = CorrelatedNormalGenerator(self.mu, cov, seed=seed)

    def simulate(self, weights: Vector, total_value: float,
                 horizon_days: int = 1, n_paths: int = 10_000) -> SimulationResult:
        """Simulate portfolio P&L over ``horizon_days`` using GBM per asset.

        Each asset's price evolves multiplicatively via ``exp`` of the summed
        per-step log-ish shocks; the portfolio is marked at horizon assuming a
        buy-and-hold (no rebalancing) book with the given start weights.
        """
        k = len(weights)
        pnl: List[float] = []
        terminal: List[float] = []
        for _ in range(n_paths):
            # Compound each asset's growth factor over the horizon.
            growth = [1.0] * k
            for _step in range(horizon_days):
                shock = self._gen.draw()
                for i in range(k):
                    growth[i] *= math.exp(shock[i])
            # Portfolio return = weighted sum of per-asset growth minus 1.
            port_return = dot(weights, growth) - sum(weights)
            pnl_value = total_value * port_return
            pnl.append(pnl_value)
            terminal.append(total_value + pnl_value)
        return SimulationResult(horizon_days, n_paths, pnl, terminal)
