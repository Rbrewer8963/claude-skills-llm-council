"""Performance and return analytics.

Risk-adjusted return metrics (Sharpe, Sortino, Calmar), drawdown analysis and
benchmark-relative statistics (alpha, beta, tracking error, information ratio).
All operate on a periodic return series and annualise consistently.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np

from .market import MarketData
from .portfolio import Portfolio


@dataclass
class PerformanceStats:
    total_return: float
    annual_return: float
    annual_vol: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    var_95_1d: float
    hit_ratio: float
    skew: float
    kurtosis: float
    best_day: float
    worst_day: float

    def as_dict(self) -> dict:
        return asdict(self)


def portfolio_return_series(portfolio: Portfolio, market: MarketData, kind: str = "simple") -> np.ndarray:
    """Time series of portfolio returns using fixed current weights (buy-and-hold proxy)."""
    w = portfolio.weight_vector(market)
    return market.returns(kind) @ w


def max_drawdown(returns: np.ndarray) -> float:
    """Maximum peak-to-trough drawdown (positive fraction) from a return series."""
    equity = np.cumprod(1.0 + returns)
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    return float(-dd.min())


def performance_stats(returns: np.ndarray, rf: float = 0.02, annual_days: int = 252) -> PerformanceStats:
    r = np.asarray(returns, float)
    n = len(r)
    ann_return = float(r.mean() * annual_days)
    ann_vol = float(r.std(ddof=1) * np.sqrt(annual_days))
    rf_daily = rf / annual_days
    downside = r[r < rf_daily]
    downside_dev = float(downside.std(ddof=1) * np.sqrt(annual_days)) if downside.size > 1 else 0.0
    mdd = max_drawdown(r)
    total = float(np.prod(1.0 + r) - 1.0)
    sharpe = (ann_return - rf) / ann_vol if ann_vol else 0.0
    sortino = (ann_return - rf) / downside_dev if downside_dev else 0.0
    calmar = ann_return / mdd if mdd else 0.0
    return PerformanceStats(
        total_return=total,
        annual_return=ann_return,
        annual_vol=ann_vol,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        max_drawdown=mdd,
        var_95_1d=float(-np.quantile(r, 0.05)),
        hit_ratio=float((r > 0).mean()),
        skew=_skew(r),
        kurtosis=_kurtosis(r),
        best_day=float(r.max()),
        worst_day=float(r.min()),
    )


@dataclass
class BenchmarkStats:
    beta: float
    alpha_annual: float
    correlation: float
    tracking_error: float
    information_ratio: float
    up_capture: float
    down_capture: float


def benchmark_stats(returns: np.ndarray, benchmark: np.ndarray, rf: float = 0.02,
                    annual_days: int = 252) -> BenchmarkStats:
    r = np.asarray(returns, float)
    b = np.asarray(benchmark, float)
    cov = np.cov(r, b, ddof=1)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] else 0.0
    rf_daily = rf / annual_days
    alpha_daily = (r - rf_daily).mean() - beta * (b - rf_daily).mean()
    active = r - b
    te = float(active.std(ddof=1) * np.sqrt(annual_days))
    ir = float(active.mean() * annual_days / te) if te else 0.0
    up = b > 0
    down = b < 0
    up_cap = float(r[up].mean() / b[up].mean()) if up.any() and b[up].mean() else 0.0
    down_cap = float(r[down].mean() / b[down].mean()) if down.any() and b[down].mean() else 0.0
    return BenchmarkStats(
        beta=float(beta),
        alpha_annual=float(alpha_daily * annual_days),
        correlation=float(np.corrcoef(r, b)[0, 1]),
        tracking_error=te,
        information_ratio=ir,
        up_capture=up_cap,
        down_capture=down_cap,
    )


def _skew(x: np.ndarray) -> float:
    m = x - x.mean()
    s = x.std()
    return float((m ** 3).mean() / s ** 3) if s else 0.0


def _kurtosis(x: np.ndarray) -> float:
    """Excess kurtosis (0 for a normal distribution)."""
    m = x - x.mean()
    s = x.std()
    return float((m ** 4).mean() / s ** 4 - 3.0) if s else 0.0
