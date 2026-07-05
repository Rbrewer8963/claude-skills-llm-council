"""ATLAS — Asset, Trading, Liability, Analytics & Simulation.

An open, offline-capable institutional risk engine: correlated Monte Carlo,
multi-method Value-at-Risk, historically calibrated stress testing, factor
attribution, portfolio optimisation and performance analytics — the core of
what a "trillion-dollar asset tool" like BlackRock's Aladdin does at the
portfolio / market-risk layer, in transparent, inspectable Python.
"""
from __future__ import annotations

from .data import default_universe, generate_market
from .engine import RiskEngine, RiskReport
from .instruments import AssetClass, Instrument
from .market import MarketData
from .montecarlo import simulate
from .optimize import (
    efficient_frontier,
    max_sharpe,
    min_variance,
    risk_parity,
)
from .portfolio import Portfolio
from .risk import (
    historical_var,
    incremental_var,
    monte_carlo_var,
    parametric_var,
    risk_contributions,
)
from .stress import Scenario, historical_scenarios, run_stress_suite

__version__ = "0.1.0"

__all__ = [
    "AssetClass", "Instrument", "MarketData", "Portfolio",
    "RiskEngine", "RiskReport", "simulate",
    "historical_var", "parametric_var", "monte_carlo_var",
    "risk_contributions", "incremental_var",
    "Scenario", "historical_scenarios", "run_stress_suite",
    "min_variance", "max_sharpe", "risk_parity", "efficient_frontier",
    "generate_market", "default_universe",
    "__version__",
]


def market_from_synthetic(**kwargs) -> MarketData:
    """Convenience: generate a synthetic market and wrap it in :class:`MarketData`."""
    instruments, dates, prices = generate_market(**kwargs)
    return MarketData.from_prices(instruments, dates, prices)
