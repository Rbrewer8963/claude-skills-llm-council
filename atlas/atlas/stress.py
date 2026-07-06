"""Stress testing and scenario analysis.

A :class:`Scenario` is a set of shocks — either per asset class or per symbol —
applied instantaneously to a portfolio to estimate mark-to-market impact. A
library of historical replays (2008 GFC, COVID crash, 2022 rate shock) ships
built in, and hypothetical scenarios are trivial to author.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .portfolio import Portfolio


@dataclass
class Scenario:
    name: str
    description: str = ""
    # Shock as a fractional price move, keyed by asset class ...
    class_shocks: Dict[str, float] = field(default_factory=dict)
    # ... and/or overridden per symbol (symbol shocks take precedence).
    symbol_shocks: Dict[str, float] = field(default_factory=dict)

    def shock_for(self, asset_class: str, symbol: str) -> float:
        if symbol in self.symbol_shocks:
            return self.symbol_shocks[symbol]
        return self.class_shocks.get(asset_class, 0.0)


@dataclass
class StressResult:
    scenario: str
    total_pnl: float
    pct_impact: float
    position_pnl: Dict[str, float]

    def as_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "total_pnl": self.total_pnl,
            "pct_impact": self.pct_impact,
            "position_pnl": self.position_pnl,
        }


def apply_scenario(portfolio: Portfolio, scenario: Scenario) -> StressResult:
    """Mark the book under a scenario and return the P&L impact."""
    position_pnl: Dict[str, float] = {}
    total = 0.0
    for pos in portfolio.positions:
        shock = scenario.shock_for(pos.asset.asset_class, pos.asset.symbol)
        pnl = pos.market_value * shock
        position_pnl[pos.asset.symbol] = pnl
        total += pnl
    base = portfolio.net_market_value
    pct = (total / base) if base else 0.0
    return StressResult(scenario.name, total, pct, position_pnl)


def run_stress_suite(portfolio: Portfolio, scenarios: List[Scenario]) -> List[StressResult]:
    return [apply_scenario(portfolio, s) for s in scenarios]


# ---------------------------------------------------------------------------
# Built-in historical replays. Shocks are broad, illustrative approximations of
# the asset-class moves observed during each episode, not precise reconstructions.
# ---------------------------------------------------------------------------

def historical_library() -> List[Scenario]:
    return [
        Scenario(
            name="2008 Global Financial Crisis",
            description="Sep-Nov 2008 credit-driven equity collapse; flight to quality.",
            class_shocks={
                "equity": -0.45, "bond": 0.08, "credit": -0.30,
                "commodity": -0.35, "real_estate": -0.40, "cash": 0.0,
            },
        ),
        Scenario(
            name="2020 COVID Crash",
            description="Feb-Mar 2020 pandemic shock; broad risk-off, oil collapse.",
            class_shocks={
                "equity": -0.34, "bond": 0.06, "credit": -0.20,
                "commodity": -0.55, "real_estate": -0.30, "cash": 0.0,
            },
        ),
        Scenario(
            name="2022 Rate Shock",
            description="2022 inflation-driven synchronised bond and equity drawdown.",
            class_shocks={
                "equity": -0.20, "bond": -0.17, "credit": -0.15,
                "commodity": 0.20, "real_estate": -0.25, "cash": 0.0,
            },
        ),
        Scenario(
            name="Hypothetical: -10% Equity Shock",
            description="Single-factor equity drawdown, all else held flat.",
            class_shocks={"equity": -0.10},
        ),
    ]
