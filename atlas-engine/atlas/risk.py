"""Value-at-Risk, Expected Shortfall and risk decomposition.

ATLAS computes VaR three complementary ways — **historical**, **parametric**
(variance-covariance) and **Monte Carlo** — because agreement across methods is
itself a risk signal, and divergence flags model fragility. It also decomposes
portfolio risk into **marginal**, **component**, and **incremental** VaR so a
risk officer can see *which* positions drive the tail, not just its size.

Sign convention: VaR and CVaR are reported as **positive loss magnitudes** at
the stated confidence level.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from .market import MarketData
from .montecarlo import SimulationResult, simulate
from .portfolio import Portfolio


@dataclass
class VaRResult:
    method: str
    confidence: float
    horizon_days: int
    var_dollar: float
    cvar_dollar: float
    var_pct: float
    cvar_pct: float
    nav: float

    def __str__(self) -> str:
        c = int(self.confidence * 100)
        return (f"{self.method:>11s} VaR {c}% / {self.horizon_days}d: "
                f"${self.var_dollar:,.0f} ({self.var_pct:.2%})  |  "
                f"CVaR: ${self.cvar_dollar:,.0f} ({self.cvar_pct:.2%})")


def _tail(pnl: np.ndarray, confidence: float) -> tuple[float, float]:
    """Return (VaR, CVaR) as positive losses from a P&L sample."""
    losses = -np.asarray(pnl, float)
    var = float(np.quantile(losses, confidence))
    tail = losses[losses >= var]
    cvar = float(tail.mean()) if tail.size else var
    return var, cvar


def historical_var(portfolio: Portfolio, market: MarketData, confidence: float = 0.99,
                   horizon_days: int = 1, kind: str = "log") -> VaRResult:
    """Full-revaluation VaR from the empirical return distribution."""
    exposures = portfolio.exposure_vector(market)
    rets = market.returns(kind)
    if horizon_days > 1:  # overlapping horizon aggregation
        rets = _aggregate_horizon(rets, horizon_days)
    pnl = rets @ exposures
    var, cvar = _tail(pnl, confidence)
    nav = portfolio.nav
    return VaRResult("historical", confidence, horizon_days, var, cvar,
                     var / nav, cvar / nav, nav)


def parametric_var(portfolio: Portfolio, market: MarketData, confidence: float = 0.99,
                   horizon_days: int = 1, cov_method: str = "ewma") -> VaRResult:
    """Gaussian variance-covariance VaR (closed form)."""
    exposures = portfolio.exposure_vector(market)
    cov = market.cov(method=cov_method, annualized=True)
    h = horizon_days / market.annual_days
    sigma = float(np.sqrt(exposures @ cov @ exposures) * np.sqrt(h))
    mu = float(portfolio.exposure_vector(market) @ market.mean_returns(annualized=True) * h)
    z = stats.norm.ppf(confidence)
    var = z * sigma - mu
    # Analytical Gaussian expected shortfall.
    cvar = sigma * stats.norm.pdf(z) / (1 - confidence) - mu
    nav = portfolio.nav
    return VaRResult("parametric", confidence, horizon_days, var, cvar,
                     var / nav, cvar / nav, nav)


def monte_carlo_var(portfolio: Portfolio, market: MarketData, confidence: float = 0.99,
                    horizon_days: int = 1, n_paths: int = 50_000,
                    distribution: str = "t", cov_method: str = "ewma",
                    seed: int | None = 42, sim: SimulationResult | None = None) -> VaRResult:
    """Monte Carlo VaR/CVaR from a correlated simulation (reuses ``sim`` if given)."""
    exposures = portfolio.exposure_vector(market)
    if sim is None:
        sim = simulate(
            mean=market.mean_returns(annualized=True),
            cov=market.cov(method=cov_method, annualized=True),
            n_paths=n_paths, horizon_days=horizon_days,
            annual_days=market.annual_days, distribution=distribution, seed=seed,
        )
    pnl = sim.portfolio_pnl(exposures)
    var, cvar = _tail(pnl, confidence)
    nav = portfolio.nav
    return VaRResult(f"monte-carlo/{distribution}", confidence, horizon_days, var, cvar,
                     var / nav, cvar / nav, nav)


# --------------------------------------------------------------------- decomposition
@dataclass
class RiskContribution:
    symbols: list[str]
    marginal: np.ndarray       # d(sigma)/d(exposure)
    component: np.ndarray      # component VaR in $ (sums to total VaR)
    percent: np.ndarray        # component share of total risk

    def top(self, k: int = 5) -> list[tuple[str, float, float]]:
        order = np.argsort(-np.abs(self.component))[:k]
        return [(self.symbols[i], float(self.component[i]), float(self.percent[i])) for i in order]


def risk_contributions(portfolio: Portfolio, market: MarketData, confidence: float = 0.99,
                       horizon_days: int = 1, cov_method: str = "ewma") -> RiskContribution:
    """Euler / component-VaR decomposition (Gaussian).

    Component VaR sums exactly to total parametric VaR, answering *"who owns the
    risk?"* — the question that matters when de-risking a book.
    """
    exposures = portfolio.exposure_vector(market)
    cov = market.cov(method=cov_method, annualized=True)
    h = horizon_days / market.annual_days
    port_var = float(exposures @ cov @ exposures) * h
    sigma = np.sqrt(port_var)
    z = stats.norm.ppf(confidence)
    if sigma == 0:
        n = market.n_assets
        return RiskContribution(market.symbols, np.zeros(n), np.zeros(n), np.zeros(n))
    marginal_sigma = (cov @ exposures) * h / sigma          # ∂σ/∂w_i
    component_sigma = exposures * marginal_sigma             # sums to σ
    component_var = z * component_sigma                      # sums to VaR
    total = component_var.sum()
    percent = component_var / total if total else np.zeros_like(component_var)
    return RiskContribution(market.symbols, z * marginal_sigma, component_var, percent)


def incremental_var(portfolio: Portfolio, market: MarketData, symbol: str, amount: float,
                    confidence: float = 0.99, horizon_days: int = 1,
                    cov_method: str = "ewma") -> float:
    """Change in parametric VaR from adding ``amount`` of ``symbol`` (pre-trade check)."""
    base = parametric_var(portfolio, market, confidence, horizon_days, cov_method).var_dollar
    after = parametric_var(portfolio.trade(symbol, amount), market, confidence,
                           horizon_days, cov_method).var_dollar
    return after - base


def _aggregate_horizon(rets: np.ndarray, horizon: int) -> np.ndarray:
    """Overlapping multi-day aggregation for horizon VaR.

    Uses rolling (overlapping) windows to retain ``T - h + 1`` observations —
    far more tail data than non-overlapping blocks at long horizons. Assumes
    ``rets`` are **log** returns, which sum additively across days.
    """
    t, n = rets.shape
    if horizon <= 1 or t <= horizon:
        return rets.sum(axis=0, keepdims=True) if t <= horizon else rets
    cs = np.vstack([np.zeros((1, n)), np.cumsum(rets, axis=0)])
    return cs[horizon:] - cs[:-horizon]
