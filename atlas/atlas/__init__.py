"""ATLAS — Asset, Treasury, Liability & Analytics System.

A dependency-free portfolio risk and analytics engine: risk analytics
(VaR/CVaR, volatility, risk decomposition), Monte-Carlo simulation, stress
testing, mean-variance / risk-parity construction, factor exposure and a
compliance rules engine — the pillars an institutional platform is built on,
implemented in pure Python so it runs anywhere.

Quick start
-----------
    from atlas import AtlasEngine, report
    from atlas.samples import demo_portfolio, demo_history

    engine = AtlasEngine(demo_portfolio(), demo_history())
    print(report.render(engine.run()))
"""

from .engine import AnalysisReport, AtlasEngine
from .market import PriceHistory
from .montecarlo import MonteCarloEngine
from .portfolio import Asset, Portfolio, Position

__version__ = "0.1.0"

__all__ = [
    "AtlasEngine",
    "AnalysisReport",
    "PriceHistory",
    "MonteCarloEngine",
    "Portfolio",
    "Position",
    "Asset",
    "__version__",
]
