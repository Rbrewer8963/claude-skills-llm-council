"""Market data container and estimation of return moments.

:class:`MarketData` is the single source of truth for prices, returns, and the
covariance structure consumed by every downstream analytic. It supports both a
plain **sample** covariance and an **EWMA** (RiskMetrics) covariance that
weights recent observations more heavily — critical for capturing volatility
regime shifts that sink slower engines.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .instruments import Instrument

ANNUAL_DAYS = 252


@dataclass
class MarketData:
    instruments: list[Instrument]
    dates: np.ndarray
    prices: np.ndarray  # shape (T, N)
    annual_days: int = ANNUAL_DAYS

    def __post_init__(self) -> None:
        self.prices = np.asarray(self.prices, dtype=float)
        if self.prices.ndim != 2:
            raise ValueError("prices must be a 2-D (T, N) array")
        if self.prices.shape[1] != len(self.instruments):
            raise ValueError("prices columns must match number of instruments")
        if np.any(self.prices <= 0):
            raise ValueError("prices must be strictly positive")
        self._symbols = [ins.symbol for ins in self.instruments]
        self._index = {s: i for i, s in enumerate(self._symbols)}

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_prices(cls, instruments, dates, prices, annual_days: int = ANNUAL_DAYS) -> "MarketData":
        return cls(list(instruments), np.asarray(dates), np.asarray(prices, float), annual_days)

    @classmethod
    def from_csv(cls, path: str, annual_days: int = ANNUAL_DAYS) -> "MarketData":
        """Load a wide CSV: first column = date, remaining columns = instrument prices."""
        import csv

        with open(path, newline="") as fh:
            reader = csv.reader(fh)
            header = next(reader)
            rows = [r for r in reader if r]
        symbols = header[1:]
        dates = np.array([r[0] for r in rows])
        prices = np.array([[float(x) for x in r[1:]] for r in rows], dtype=float)
        # Enrich known tickers with their asset-class / factor metadata so stress
        # mapping and factor attribution are correct; unknown symbols stay equity.
        from .data import known_instruments

        registry = known_instruments()
        instruments = [registry.get(s.upper(), Instrument(s)) for s in symbols]
        return cls(instruments, dates, prices, annual_days)

    # ------------------------------------------------------------------ accessors
    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

    @property
    def n_assets(self) -> int:
        return len(self._symbols)

    def index(self, symbol: str) -> int:
        return self._index[symbol.upper()]

    def latest_prices(self) -> dict[str, float]:
        return {s: float(self.prices[-1, i]) for i, s in enumerate(self._symbols)}

    # ------------------------------------------------------------------ returns
    def returns(self, kind: str = "simple") -> np.ndarray:
        """Period return matrix of shape (T-1, N)."""
        p = self.prices
        if kind == "log":
            return np.diff(np.log(p), axis=0)
        if kind == "simple":
            return p[1:] / p[:-1] - 1.0
        raise ValueError("kind must be 'simple' or 'log'")

    def mean_returns(self, annualized: bool = True, kind: str = "simple") -> np.ndarray:
        m = self.returns(kind).mean(axis=0)
        return m * self.annual_days if annualized else m

    def vols(self, annualized: bool = True, kind: str = "simple") -> np.ndarray:
        s = self.returns(kind).std(axis=0, ddof=1)
        return s * np.sqrt(self.annual_days) if annualized else s

    # ------------------------------------------------------------------ covariance
    def cov(self, method: str = "sample", annualized: bool = True,
            ewma_lambda: float = 0.94, kind: str = "simple") -> np.ndarray:
        r = self.returns(kind)
        if method == "sample":
            c = np.cov(r, rowvar=False, ddof=1)
        elif method == "ewma":
            c = _ewma_cov(r, ewma_lambda)
        else:
            raise ValueError("method must be 'sample' or 'ewma'")
        c = np.atleast_2d(c)
        return c * self.annual_days if annualized else c

    def corr(self, method: str = "sample", ewma_lambda: float = 0.94, kind: str = "simple") -> np.ndarray:
        c = self.cov(method=method, annualized=False, ewma_lambda=ewma_lambda, kind=kind)
        d = np.sqrt(np.clip(np.diag(c), 1e-18, None))
        return c / np.outer(d, d)


def _ewma_cov(r: np.ndarray, lam: float) -> np.ndarray:
    """RiskMetrics exponentially-weighted covariance of a (T, N) return matrix."""
    r = r - r.mean(axis=0)
    t = r.shape[0]
    weights = (1 - lam) * lam ** np.arange(t - 1, -1, -1)
    weights /= weights.sum()
    return (r * weights[:, None]).T @ r
