"""ATLAS engine — the orchestrator.

This is the single entry point that mirrors what an institutional risk platform
does end to end: take a portfolio and its market history, then produce a unified
view spanning risk analytics, Monte-Carlo simulation, stress testing, factor
exposure and compliance. Each sub-analysis is also usable on its own; the engine
just wires them together and hands back a structured report object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import compliance, risk, stats, stress
from .compliance import Rule
from .market import PriceHistory
from .montecarlo import MonteCarloEngine, SimulationResult
from .portfolio import Portfolio
from .stress import Scenario, StressResult


@dataclass
class AnalysisReport:
    portfolio: str
    total_value: float
    risk: risk.RiskReport
    simulation: Optional[SimulationResult]
    stress: List[StressResult] = field(default_factory=list)
    compliance: Optional[compliance.ComplianceResult] = None

    def as_dict(self) -> dict:
        return {
            "portfolio": self.portfolio,
            "total_value": self.total_value,
            "risk": self.risk.as_dict(),
            "simulation": self.simulation.summary() if self.simulation else None,
            "stress": [s.as_dict() for s in self.stress],
            "compliance": self.compliance.as_dict() if self.compliance else None,
        }


class AtlasEngine:
    """End-to-end analytics over a portfolio and its market history."""

    def __init__(self, portfolio: Portfolio, history: PriceHistory,
                 seed: int | None = 42):
        if portfolio.symbols != history.symbols:
            raise ValueError(
                "portfolio and price history must reference the same symbols "
                f"in the same order: {portfolio.symbols} vs {history.symbols}"
            )
        self.portfolio = portfolio
        self.history = history
        self.seed = seed
        self._cov = history.covariance()
        self._mu = history.expected_returns()

    # -- individual analyses ------------------------------------------------

    def risk_report(self) -> risk.RiskReport:
        w = self.portfolio.weights()
        value = self.portfolio.total_value
        cov = self._cov
        symbols = self.portfolio.symbols
        cvar_by_symbol = risk.component_var(value, w, cov, 0.95, 1)
        rc = risk.risk_contributions(w, cov)
        return risk.RiskReport(
            total_value=value,
            annualized_vol=risk.portfolio_volatility(w, cov, annualize=True),
            var_95_1d=risk.parametric_var(value, w, cov, 0.95, 1),
            cvar_95_1d=risk.parametric_cvar(value, w, cov, 0.95, 1),
            var_99_1d=risk.parametric_var(value, w, cov, 0.99, 1),
            component_var=dict(zip(symbols, cvar_by_symbol)),
            risk_contributions=dict(zip(symbols, rc)),
        )

    def monte_carlo(self, horizon_days: int = 10,
                    n_paths: int = 10_000) -> SimulationResult:
        mc = MonteCarloEngine(self._mu, self._cov, seed=self.seed)
        return mc.simulate(self.portfolio.weights(), self.portfolio.total_value,
                           horizon_days=horizon_days, n_paths=n_paths)

    def stress_test(self, scenarios: Optional[List[Scenario]] = None) -> List[StressResult]:
        scenarios = scenarios or stress.historical_library()
        return stress.run_stress_suite(self.portfolio, scenarios)

    def check_compliance(self, rules: Optional[List[Rule]] = None) -> compliance.ComplianceResult:
        rules = rules if rules is not None else compliance.default_mandate()
        return compliance.evaluate(self.portfolio, rules)

    # -- the full run -------------------------------------------------------

    def run(self, mc_horizon_days: int = 10, mc_paths: int = 10_000,
            scenarios: Optional[List[Scenario]] = None,
            rules: Optional[List[Rule]] = None,
            with_simulation: bool = True) -> AnalysisReport:
        return AnalysisReport(
            portfolio=self.portfolio.name,
            total_value=self.portfolio.total_value,
            risk=self.risk_report(),
            simulation=self.monte_carlo(mc_horizon_days, mc_paths) if with_simulation else None,
            stress=self.stress_test(scenarios),
            compliance=self.check_compliance(rules),
        )
