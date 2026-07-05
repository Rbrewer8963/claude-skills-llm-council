"""Portfolio representation and valuation.

A :class:`Portfolio` is a book of **dollar positions** (long or short) plus
cash. Working in currency exposures — rather than share counts — lets ATLAS
aggregate risk cleanly across heterogeneous asset classes and treat the linear
P&L map ``pnl = exposures · asset_returns`` exactly.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .market import MarketData


@dataclass
class Portfolio:
    """A multi-asset portfolio expressed in currency (dollar) exposures.

    Parameters
    ----------
    positions:
        Mapping of ``symbol -> market value``. Negative values are shorts.
    cash:
        Uninvested cash (adds to NAV, carries no market risk).
    name:
        Label used in reports.
    """

    positions: dict[str, float] = field(default_factory=dict)
    cash: float = 0.0
    name: str = "Portfolio"

    def __post_init__(self) -> None:
        self.positions = {k.upper(): float(v) for k, v in self.positions.items()}

    # ------------------------------------------------------------------ builders
    @classmethod
    def equal_weight(cls, symbols, nav: float = 1_000_000.0, name: str = "Equal Weight") -> "Portfolio":
        symbols = list(symbols)
        w = nav / len(symbols)
        return cls({s: w for s in symbols}, cash=0.0, name=name)

    @classmethod
    def from_weights(cls, weights: dict[str, float], nav: float = 1_000_000.0,
                     name: str = "Portfolio") -> "Portfolio":
        """Build from fractional weights (need not sum to 1; remainder is cash)."""
        pos = {s.upper(): w * nav for s, w in weights.items()}
        cash = nav - sum(pos.values())
        return cls(pos, cash=cash, name=name)

    # ------------------------------------------------------------------ metrics
    @property
    def nav(self) -> float:
        return sum(self.positions.values()) + self.cash

    @property
    def gross_exposure(self) -> float:
        return sum(abs(v) for v in self.positions.values())

    @property
    def net_exposure(self) -> float:
        return sum(self.positions.values())

    @property
    def leverage(self) -> float:
        nav = self.nav
        return self.gross_exposure / nav if nav else float("nan")

    def weights(self) -> dict[str, float]:
        nav = self.nav
        if nav == 0:
            raise ValueError("NAV is zero; weights undefined")
        return {s: v / nav for s, v in self.positions.items()}

    # ------------------------------------------------------------------ alignment
    def exposure_vector(self, market: MarketData) -> np.ndarray:
        """Dollar exposure aligned to ``market.symbols`` order (missing = 0)."""
        vec = np.zeros(market.n_assets)
        for s, v in self.positions.items():
            if s in market._index:
                vec[market.index(s)] = v
        return vec

    def weight_vector(self, market: MarketData) -> np.ndarray:
        nav = self.nav
        return self.exposure_vector(market) / nav if nav else np.zeros(market.n_assets)

    def unknown_symbols(self, market: MarketData) -> list[str]:
        return [s for s in self.positions if s not in market._index]

    # ------------------------------------------------------------------ mutation
    def trade(self, symbol: str, amount: float) -> "Portfolio":
        """Return a new portfolio after buying ``amount`` (funded from cash)."""
        symbol = symbol.upper()
        pos = dict(self.positions)
        pos[symbol] = pos.get(symbol, 0.0) + amount
        return Portfolio(pos, cash=self.cash - amount, name=self.name)
