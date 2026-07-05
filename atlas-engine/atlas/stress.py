"""Scenario and stress testing.

Monte Carlo answers *"how bad is a normal-ish bad day?"*. Stress testing
answers *"what happens in a specific catastrophe?"* — a 2008-style credit
seizure, a COVID liquidity crash, a 2022 rate shock. ATLAS ships a library of
**historically calibrated** shocks defined at the asset-class level and maps
them onto the portfolio's actual holdings, plus supports fully custom scenarios
and single-factor sensitivity sweeps.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .instruments import AssetClass
from .market import MarketData
from .portfolio import Portfolio


@dataclass
class Scenario:
    """A named instantaneous shock.

    ``asset_class_shocks`` maps an :class:`AssetClass` to a decimal return
    shock (e.g. ``-0.40`` = down 40%). ``symbol_shocks`` overrides individual
    instruments. Anything unspecified is treated as unshocked (0%).
    """

    name: str
    description: str = ""
    asset_class_shocks: dict[AssetClass, float] = field(default_factory=dict)
    symbol_shocks: dict[str, float] = field(default_factory=dict)

    def shock_vector(self, market: MarketData) -> np.ndarray:
        vec = np.zeros(market.n_assets)
        for i, ins in enumerate(market.instruments):
            if ins.symbol in self.symbol_shocks:
                vec[i] = self.symbol_shocks[ins.symbol]
            elif ins.asset_class in self.asset_class_shocks:
                vec[i] = self.asset_class_shocks[ins.asset_class]
        return vec


@dataclass
class StressResult:
    scenario: str
    pnl: float
    pnl_pct: float
    contributions: dict[str, float]

    def __str__(self) -> str:
        return f"{self.scenario:<26s} P&L: ${self.pnl:,.0f} ({self.pnl_pct:+.2%})"


def apply_scenario(portfolio: Portfolio, market: MarketData, scenario: Scenario) -> StressResult:
    exposures = portfolio.exposure_vector(market)
    shocks = scenario.shock_vector(market)
    contrib = exposures * shocks
    pnl = float(contrib.sum())
    nav = portfolio.nav
    contributions = {market.symbols[i]: float(contrib[i]) for i in range(market.n_assets) if contrib[i] != 0}
    return StressResult(scenario.name, pnl, pnl / nav if nav else float("nan"), contributions)


def run_stress_suite(portfolio: Portfolio, market: MarketData,
                     scenarios: list[Scenario] | None = None) -> list[StressResult]:
    scenarios = scenarios or historical_scenarios()
    return [apply_scenario(portfolio, market, s) for s in scenarios]


def factor_sensitivity(portfolio: Portfolio, market: MarketData, asset_class: AssetClass,
                       shocks: np.ndarray | None = None) -> list[tuple[float, float]]:
    """Sweep a single asset class's shock and return ``[(shock, pnl), ...]``."""
    if shocks is None:
        shocks = np.linspace(-0.25, 0.25, 11)
    out = []
    for s in shocks:
        sc = Scenario(f"{asset_class.value} {s:+.0%}", asset_class_shocks={asset_class: float(s)})
        out.append((float(s), apply_scenario(portfolio, market, sc).pnl))
    return out


def historical_scenarios() -> list[Scenario]:
    """Library of historically calibrated stress scenarios."""
    A = AssetClass
    return [
        Scenario(
            "2008 GFC (Sep–Nov)",
            "Lehman collapse: equities −45%, HY blows out, flight to Treasuries.",
            {A.EQUITY: -0.45, A.CREDIT: -0.28, A.COMMODITY: -0.40,
             A.RATES: 0.12, A.FX: 0.15, A.ALTERNATIVE: -0.30},
            symbol_shocks={"GOLD": 0.06},
        ),
        Scenario(
            "COVID Crash (Feb–Mar 2020)",
            "Pandemic liquidity crash and 34% S&P drawdown in 23 trading days.",
            {A.EQUITY: -0.34, A.CREDIT: -0.14, A.COMMODITY: -0.55,
             A.RATES: 0.08, A.FX: 0.09, A.ALTERNATIVE: -0.22},
        ),
        Scenario(
            "2022 Rate Shock",
            "Hawkish Fed: rates and equities fall together (60/40 breakdown).",
            {A.EQUITY: -0.20, A.CREDIT: -0.15, A.RATES: -0.17,
             A.COMMODITY: 0.10, A.FX: 0.10, A.ALTERNATIVE: -0.10},
        ),
        Scenario(
            "2013 Taper Tantrum",
            "Bond rout on QE-taper signal; EM and rates hit hardest.",
            {A.RATES: -0.09, A.CREDIT: -0.05, A.EQUITY: -0.06, A.FX: 0.06},
        ),
        Scenario(
            "Stagflation Shock",
            "Persistent inflation: bonds and equities down, commodities up.",
            {A.EQUITY: -0.18, A.RATES: -0.12, A.CREDIT: -0.10,
             A.COMMODITY: 0.30, A.FX: -0.05},
        ),
        Scenario(
            "Risk-Off Flight to Quality",
            "Sharp de-risking with a bond/gold bid.",
            {A.EQUITY: -0.12, A.CREDIT: -0.06, A.RATES: 0.05,
             A.COMMODITY: -0.05, A.FX: 0.06, A.ALTERNATIVE: -0.08},
            symbol_shocks={"GOLD": 0.05},
        ),
    ]
