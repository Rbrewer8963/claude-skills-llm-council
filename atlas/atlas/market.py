"""Market data: price histories and return computation.

A ``PriceHistory`` holds aligned price series for a set of symbols. It produces
the return matrix (period-by-asset) that every downstream estimator consumes,
plus per-asset expected returns and the covariance matrix.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List

from . import stats
from .linalg import Matrix, Vector


@dataclass
class PriceHistory:
    symbols: List[str]
    # prices[symbol] = chronological list of prices (oldest first), all equal length
    prices: Dict[str, List[float]]

    def __post_init__(self) -> None:
        lengths = {len(v) for v in self.prices.values()}
        if len(lengths) != 1:
            raise ValueError("all price series must have equal length")
        if set(self.prices) != set(self.symbols):
            raise ValueError("prices keys must match symbols exactly")

    @property
    def n_periods(self) -> int:
        return len(next(iter(self.prices.values()))) - 1

    def returns(self, log: bool = False) -> Matrix:
        """Return a period-by-asset matrix of simple (or log) returns."""
        out: Matrix = []
        series = [self.prices[s] for s in self.symbols]
        n = len(series[0])
        for t in range(1, n):
            row = []
            for s in series:
                if log:
                    row.append(math.log(s[t] / s[t - 1]))
                else:
                    row.append(s[t] / s[t - 1] - 1.0)
            out.append(row)
        return out

    def expected_returns(self, log: bool = False) -> Vector:
        """Per-asset mean period return."""
        cols = stats.columns(self.returns(log=log))
        return [stats.mean(c) for c in cols]

    def covariance(self, log: bool = False) -> Matrix:
        return stats.covariance_matrix(self.returns(log=log))

    def correlation(self, log: bool = False) -> Matrix:
        return stats.correlation_matrix(self.returns(log=log))

    def latest_prices(self) -> Dict[str, float]:
        return {s: self.prices[s][-1] for s in self.symbols}
