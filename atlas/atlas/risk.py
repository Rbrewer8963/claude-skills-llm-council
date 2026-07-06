"""Risk analytics: volatility, VaR/CVaR, and risk decomposition.

Three independent VaR methodologies are provided so results can be
cross-checked against each other:

* **parametric** (variance-covariance) — fast, assumes normality
* **historical** — empirical, distribution-free
* **Monte-Carlo** — see :mod:`atlas.montecarlo`

Risk decomposition (marginal and component VaR) answers the question Aladdin is
really built to answer: *where is my risk actually coming from?*
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List

from . import stats
from .distributions import norm_ppf
from .linalg import Matrix, Vector, matvec, quad_form


def portfolio_variance(weights: Vector, cov: Matrix) -> float:
    """w^T Σ w — the single most-used number in portfolio risk."""
    return quad_form(weights, cov)


def portfolio_volatility(weights: Vector, cov: Matrix, annualize: bool = True,
                         periods: int = stats.TRADING_DAYS) -> float:
    vol = math.sqrt(max(portfolio_variance(weights, cov), 0.0))
    return stats.annualize_vol(vol, periods) if annualize else vol


def parametric_var(value: float, weights: Vector, cov: Matrix,
                   confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Variance-covariance VaR as a positive loss figure in currency units.

    Assumes returns are normal with zero drift over the horizon (a standard
    conservative simplification for short horizons).
    """
    period_vol = math.sqrt(max(portfolio_variance(weights, cov), 0.0))
    horizon_vol = period_vol * math.sqrt(horizon_days)
    z = norm_ppf(confidence)
    return value * z * horizon_vol


def parametric_cvar(value: float, weights: Vector, cov: Matrix,
                    confidence: float = 0.95, horizon_days: int = 1) -> float:
    """Expected shortfall under the normal assumption (closed form)."""
    from .distributions import norm_pdf
    period_vol = math.sqrt(max(portfolio_variance(weights, cov), 0.0))
    horizon_vol = period_vol * math.sqrt(horizon_days)
    alpha = 1.0 - confidence
    es_multiplier = norm_pdf(norm_ppf(confidence)) / alpha
    return value * es_multiplier * horizon_vol


def historical_var(pnl: List[float], confidence: float = 0.95) -> float:
    """Empirical VaR from a P&L (or return-scaled P&L) sample.

    Returns a positive loss figure at the given confidence level.
    """
    if not pnl:
        raise ValueError("empty P&L sample")
    loss_quantile = stats.quantile(pnl, 1.0 - confidence)
    return max(-loss_quantile, 0.0)


def historical_cvar(pnl: List[float], confidence: float = 0.95) -> float:
    """Empirical expected shortfall: mean loss beyond the VaR threshold."""
    if not pnl:
        raise ValueError("empty P&L sample")
    threshold = stats.quantile(pnl, 1.0 - confidence)
    tail = [x for x in pnl if x <= threshold]
    if not tail:
        return max(-threshold, 0.0)
    return max(-(sum(tail) / len(tail)), 0.0)


def marginal_var(value: float, weights: Vector, cov: Matrix,
                 confidence: float = 0.95, horizon_days: int = 1) -> Vector:
    """dVaR/dw_i — sensitivity of parametric VaR to each weight.

    Marginal VaR_i = z * sqrt(h) * value * (Σ w)_i / sqrt(w^T Σ w)
    """
    var_p = portfolio_variance(weights, cov)
    sigma_p = math.sqrt(var_p) if var_p > 0 else 0.0
    if sigma_p == 0:
        return [0.0] * len(weights)
    z = norm_ppf(confidence)
    cov_w = matvec(cov, weights)
    scale = z * math.sqrt(horizon_days) * value / sigma_p
    return [scale * cw for cw in cov_w]


def component_var(value: float, weights: Vector, cov: Matrix,
                  confidence: float = 0.95, horizon_days: int = 1) -> Vector:
    """Per-position contribution to total VaR; these sum to total parametric VaR.

    Component VaR_i = w_i * Marginal VaR_i (Euler allocation).
    """
    mvar = marginal_var(value, weights, cov, confidence, horizon_days)
    return [w * m for w, m in zip(weights, mvar)]


def risk_contributions(weights: Vector, cov: Matrix) -> Vector:
    """Fractional contribution of each position to total portfolio variance.

    Contributions sum to 1.0 and are the basis of risk-parity construction.
    """
    total = portfolio_variance(weights, cov)
    if total == 0:
        return [0.0] * len(weights)
    cov_w = matvec(cov, weights)
    return [w * cw / total for w, cw in zip(weights, cov_w)]


def beta(asset_returns: List[float], benchmark_returns: List[float]) -> float:
    """OLS beta of an asset (or portfolio) series against a benchmark."""
    bench_var = stats.variance(benchmark_returns)
    if bench_var == 0:
        return 0.0
    mb = stats.mean(benchmark_returns)
    ma = stats.mean(asset_returns)
    cov = sum((a - ma) * (b - mb) for a, b in zip(asset_returns, benchmark_returns))
    cov /= (len(asset_returns) - 1)
    return cov / bench_var


def max_drawdown(equity_curve: List[float]) -> float:
    """Largest peak-to-trough decline as a positive fraction (0.20 == -20%)."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    mdd = 0.0
    for v in equity_curve:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd


def sharpe_ratio(returns: List[float], risk_free: float = 0.0,
                 periods: int = stats.TRADING_DAYS) -> float:
    """Annualised Sharpe ratio from a per-period return series."""
    excess = [r - risk_free / periods for r in returns]
    sd = stats.stdev(excess)
    if sd == 0:
        return 0.0
    return (stats.mean(excess) / sd) * math.sqrt(periods)


def sortino_ratio(returns: List[float], risk_free: float = 0.0,
                  periods: int = stats.TRADING_DAYS) -> float:
    """Like Sharpe but penalising only downside deviation."""
    target = risk_free / periods
    excess = [r - target for r in returns]
    downside = [min(e, 0.0) ** 2 for e in excess]
    dd = math.sqrt(sum(downside) / len(downside)) if downside else 0.0
    if dd == 0:
        return 0.0
    return (stats.mean(excess) / dd) * math.sqrt(periods)


@dataclass
class RiskReport:
    total_value: float
    annualized_vol: float
    var_95_1d: float
    cvar_95_1d: float
    var_99_1d: float
    component_var: Dict[str, float]
    risk_contributions: Dict[str, float]

    def as_dict(self) -> dict:
        return {
            "total_value": self.total_value,
            "annualized_vol": self.annualized_vol,
            "var_95_1d": self.var_95_1d,
            "cvar_95_1d": self.cvar_95_1d,
            "var_99_1d": self.var_99_1d,
            "component_var": self.component_var,
            "risk_contributions": self.risk_contributions,
        }
