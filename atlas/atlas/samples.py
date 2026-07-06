"""Reproducible demo data.

Builds a diversified multi-asset book and a synthetic-but-realistic price
history (seeded correlated GBM), so every example and test runs deterministically
with no data files or network access.
"""

from __future__ import annotations

import math
import random
from typing import Dict, List

from .market import PriceHistory
from .portfolio import Asset, Portfolio, Position

# symbol, name, asset_class, sector, annual drift, annual vol, start price
_UNIVERSE = [
    ("SPX",  "US Large Cap Equity", "equity",      "broad_equity", 0.08, 0.16, 450.0),
    ("TECH", "Technology Equity",    "equity",      "technology",   0.12, 0.26, 320.0),
    ("EAFE", "Intl Developed Equity","equity",      "broad_equity", 0.06, 0.18, 210.0),
    ("TLT",  "Long Treasury Bond",   "bond",        "rates",        0.03, 0.11, 95.0),
    ("LQD",  "Investment-Grade Credit","credit",    "credit",       0.04, 0.08, 110.0),
    ("GLD",  "Gold",                 "commodity",   "metals",       0.05, 0.15, 185.0),
    ("REIT", "Real Estate",          "real_estate", "real_estate",  0.07, 0.20, 88.0),
]

# Pairwise correlation blocks used to shape the synthetic history.
_CORR = {
    ("SPX", "TECH"): 0.85, ("SPX", "EAFE"): 0.78, ("SPX", "REIT"): 0.65,
    ("TECH", "EAFE"): 0.62, ("SPX", "LQD"): 0.25, ("SPX", "TLT"): -0.30,
    ("SPX", "GLD"): 0.05, ("TLT", "LQD"): 0.55, ("TLT", "GLD"): 0.20,
    ("REIT", "TLT"): 0.10, ("EAFE", "REIT"): 0.55, ("TECH", "REIT"): 0.50,
    ("LQD", "GLD"): 0.15, ("EAFE", "LQD"): 0.20, ("EAFE", "GLD"): 0.10,
    ("EAFE", "TLT"): -0.20, ("TECH", "TLT"): -0.28, ("TECH", "LQD"): 0.20,
    ("TECH", "GLD"): 0.05, ("REIT", "LQD"): 0.30, ("REIT", "GLD"): 0.15,
}


def _correlation_matrix(symbols: List[str]) -> List[List[float]]:
    n = len(symbols)
    C = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = symbols[i], symbols[j]
            rho = _CORR.get((a, b), _CORR.get((b, a), 0.15))
            C[i][j] = C[j][i] = rho
    return C


def _cholesky(A: List[List[float]]) -> List[List[float]]:
    # Local copy to keep this module import-light and self-contained.
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                L[i][j] = math.sqrt(max(A[i][i] - s, 1e-12))
            else:
                L[i][j] = (A[i][j] - s) / L[j][j]
    return L


def demo_history(n_days: int = 756, seed: int = 7) -> PriceHistory:
    """Three years (~756 trading days) of seeded correlated daily prices."""
    symbols = [row[0] for row in _UNIVERSE]
    drift = {row[0]: row[4] for row in _UNIVERSE}
    vol = {row[0]: row[5] for row in _UNIVERSE}
    start = {row[0]: row[6] for row in _UNIVERSE}

    L = _cholesky(_correlation_matrix(symbols))
    rng = random.Random(seed)
    prices: Dict[str, List[float]] = {s: [start[s]] for s in symbols}
    dt = 1.0 / 252.0

    for _ in range(n_days):
        z = [rng.gauss(0.0, 1.0) for _ in symbols]
        corr_z = [sum(L[i][k] * z[k] for k in range(len(symbols))) for i in range(len(symbols))]
        for i, s in enumerate(symbols):
            mu, sig = drift[s], vol[s]
            shock = (mu - 0.5 * sig * sig) * dt + sig * math.sqrt(dt) * corr_z[i]
            prices[s].append(prices[s][-1] * math.exp(shock))

    return PriceHistory(symbols=symbols, prices=prices)


def demo_portfolio(nav: float = 100_000_000.0) -> Portfolio:
    """A $100mm diversified institutional book marked at latest demo prices."""
    hist = demo_history()
    latest = hist.latest_prices()
    # Target allocation weights (sum to 1.0, fully invested).
    target = {
        "SPX": 0.28, "TECH": 0.15, "EAFE": 0.12, "TLT": 0.18,
        "LQD": 0.12, "GLD": 0.08, "REIT": 0.07,
    }
    pf = Portfolio(name="Global Diversified Fund")
    meta = {row[0]: row for row in _UNIVERSE}
    for sym, w in target.items():
        _, name, cls, sector, *_ = meta[sym]
        price = latest[sym]
        qty = (nav * w) / price
        pf.add(Position(Asset(sym, name, cls, sector), qty, price))
    return pf
