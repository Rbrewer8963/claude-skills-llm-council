"""Portfolio domain model: assets, positions, and the portfolio itself.

These are plain dataclasses with a handful of derived properties. All the
quantitative machinery lives in the risk / optimisation modules and consumes
weight vectors produced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .linalg import Vector


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    asset_class: str          # e.g. "equity", "bond", "commodity", "cash"
    sector: str = "n/a"
    currency: str = "USD"


@dataclass
class Position:
    asset: Asset
    quantity: float
    price: float              # current mark price per unit

    @property
    def market_value(self) -> float:
        return self.quantity * self.price


@dataclass
class Portfolio:
    name: str
    positions: List[Position] = field(default_factory=list)
    cash: float = 0.0

    def add(self, position: Position) -> "Portfolio":
        self.positions.append(position)
        return self

    @property
    def symbols(self) -> List[str]:
        return [p.asset.symbol for p in self.positions]

    @property
    def gross_market_value(self) -> float:
        return sum(abs(p.market_value) for p in self.positions)

    @property
    def net_market_value(self) -> float:
        return sum(p.market_value for p in self.positions) + self.cash

    @property
    def total_value(self) -> float:
        """Alias for net market value including cash — the NAV of the book."""
        return self.net_market_value

    def weights(self) -> Vector:
        """Fraction of net market value in each position (cash excluded).

        Weights sum to the invested fraction of the book, which is 1.0 when
        there is no cash and no leverage.
        """
        total = self.net_market_value
        if total == 0:
            raise ValueError("portfolio has zero net value; weights undefined")
        return [p.market_value / total for p in self.positions]

    def exposures_by(self, attr: str) -> Dict[str, float]:
        """Aggregate signed market value by an Asset attribute (e.g. sector)."""
        out: Dict[str, float] = {}
        for p in self.positions:
            key = getattr(p.asset, attr)
            out[key] = out.get(key, 0.0) + p.market_value
        return out

    def weight_map(self) -> Dict[str, float]:
        return dict(zip(self.symbols, self.weights()))
