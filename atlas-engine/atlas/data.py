"""Synthetic market data generation.

ATLAS ships a correlated multi-asset market simulator so the entire engine —
risk analytics, Monte Carlo, stress tests, optimisation — runs **fully
offline** with reproducible results and no market-data vendor. Real price
histories can be loaded instead via :meth:`atlas.market.MarketData.from_prices`
or :meth:`from_csv`.

The generator builds a correlated geometric-Brownian-motion (GBM) price path
with an optional Student-t innovation to inject realistic fat tails, plus an
occasional market-wide jump to mimic crash risk.
"""
from __future__ import annotations

import numpy as np

from .instruments import AssetClass, Instrument

_DEFAULT_ANNUAL_DAYS = 252


def _nearest_psd(corr: np.ndarray) -> np.ndarray:
    """Project a symmetric matrix onto the nearest positive-semidefinite corr matrix."""
    corr = (corr + corr.T) / 2.0
    vals, vecs = np.linalg.eigh(corr)
    vals = np.clip(vals, 1e-8, None)
    out = (vecs * vals) @ vecs.T
    d = np.sqrt(np.diag(out))
    out = out / np.outer(d, d)
    np.fill_diagonal(out, 1.0)
    return out


def known_instruments() -> dict[str, Instrument]:
    """Registry mapping symbol -> fully-classified :class:`Instrument`.

    Used to enrich CSV-loaded price data (which carries only symbols) with the
    correct asset class, sector and factor metadata so stress mapping and factor
    attribution work on real data, not just the synthetic universe.
    """
    return {ins.symbol: ins for ins in default_universe()}


def default_universe() -> list[Instrument]:
    """A diversified 12-instrument multi-asset universe used by the demo/tests."""
    return [
        Instrument("SPX", "US Large Cap Equity", AssetClass.EQUITY, sector="broad", region="US"),
        Instrument("NDX", "US Tech Equity", AssetClass.EQUITY, sector="technology", region="US"),
        Instrument("RUT", "US Small Cap Equity", AssetClass.EQUITY, sector="broad", region="US"),
        Instrument("EFA", "Developed ex-US Equity", AssetClass.EQUITY, sector="broad", region="INTL"),
        Instrument("EEM", "Emerging Markets Equity", AssetClass.EQUITY, sector="broad", region="EM"),
        Instrument("UST10", "US 10Y Treasury", AssetClass.RATES, sector="govt", region="US",
                   factor_betas={"rates": -8.0}),
        Instrument("UST2", "US 2Y Treasury", AssetClass.RATES, sector="govt", region="US",
                   factor_betas={"rates": -1.9}),
        Instrument("IG", "Investment Grade Credit", AssetClass.CREDIT, sector="corp", region="US",
                   factor_betas={"rates": -6.5, "credit": 1.0}),
        Instrument("HY", "High Yield Credit", AssetClass.CREDIT, sector="corp", region="US",
                   factor_betas={"rates": -3.5, "credit": 3.0}),
        Instrument("GOLD", "Gold", AssetClass.COMMODITY, sector="metals", region="GLOBAL"),
        Instrument("WTI", "Crude Oil", AssetClass.COMMODITY, sector="energy", region="GLOBAL"),
        Instrument("USD", "US Dollar Index", AssetClass.FX, sector="fx", region="US"),
    ]


# Plausible annualised drift / vol assumptions per instrument (decimal).
_MARKET_PARAMS: dict[str, tuple[float, float]] = {
    "SPX": (0.08, 0.16), "NDX": (0.11, 0.22), "RUT": (0.07, 0.21),
    "EFA": (0.06, 0.17), "EEM": (0.06, 0.23),
    "UST10": (0.02, 0.07), "UST2": (0.015, 0.02),
    "IG": (0.035, 0.06), "HY": (0.055, 0.11),
    "GOLD": (0.04, 0.15), "WTI": (0.05, 0.35), "USD": (0.005, 0.08),
}

# A hand-built, economically sensible correlation seed keyed by asset class.
_CLASS_CORR = {
    (AssetClass.EQUITY, AssetClass.EQUITY): 0.80,
    (AssetClass.EQUITY, AssetClass.CREDIT): 0.45,
    (AssetClass.EQUITY, AssetClass.RATES): -0.30,
    (AssetClass.EQUITY, AssetClass.COMMODITY): 0.25,
    (AssetClass.EQUITY, AssetClass.FX): -0.35,
    (AssetClass.RATES, AssetClass.RATES): 0.85,
    (AssetClass.RATES, AssetClass.CREDIT): 0.30,
    (AssetClass.RATES, AssetClass.COMMODITY): -0.10,
    (AssetClass.RATES, AssetClass.FX): 0.20,
    (AssetClass.CREDIT, AssetClass.CREDIT): 0.75,
    (AssetClass.CREDIT, AssetClass.COMMODITY): 0.20,
    (AssetClass.CREDIT, AssetClass.FX): -0.15,
    (AssetClass.COMMODITY, AssetClass.COMMODITY): 0.40,
    (AssetClass.COMMODITY, AssetClass.FX): -0.25,
    (AssetClass.FX, AssetClass.FX): 1.00,
}


def _seed_correlation(instruments: list[Instrument]) -> np.ndarray:
    n = len(instruments)
    corr = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = instruments[i].asset_class, instruments[j].asset_class
            rho = _CLASS_CORR.get((a, b), _CLASS_CORR.get((b, a), 0.0))
            corr[i, j] = corr[j, i] = rho
    return _nearest_psd(corr)


def generate_market(
    instruments: list[Instrument] | None = None,
    days: int = 3 * _DEFAULT_ANNUAL_DAYS,
    start_price: float = 100.0,
    dt: float = 1.0 / _DEFAULT_ANNUAL_DAYS,
    student_t_df: float | None = 6.0,
    jump_prob: float = 0.0,
    jump_mean: float = -0.06,
    jump_vol: float = 0.03,
    seed: int | None = 7,
):
    """Generate a correlated synthetic price history.

    Returns a tuple ``(instruments, dates, prices)`` where ``prices`` is a
    ``(days+1, n_instruments)`` array. Fat tails come from a Student-t
    innovation (``student_t_df``); systemic crash risk from Poisson-style
    market-wide jumps (``jump_prob`` per day).
    """
    instruments = instruments or default_universe()
    rng = np.random.default_rng(seed)
    n = len(instruments)

    mu = np.array([_MARKET_PARAMS.get(ins.symbol, (0.06, 0.18))[0] for ins in instruments])
    vol = np.array([_MARKET_PARAMS.get(ins.symbol, (0.06, 0.18))[1] for ins in instruments])
    corr = _seed_correlation(instruments)
    chol = np.linalg.cholesky(corr)

    # daily log-return parameters
    drift = (mu - 0.5 * vol ** 2) * dt
    daily_vol = vol * np.sqrt(dt)

    if student_t_df and student_t_df > 2:
        # Standardise Student-t so it has unit variance, preserving vol targets.
        scale = np.sqrt(student_t_df / (student_t_df - 2.0))
        z = rng.standard_t(student_t_df, size=(days, n)) / scale
    else:
        z = rng.standard_normal(size=(days, n))

    correlated = z @ chol.T
    log_rets = drift + daily_vol * correlated

    if jump_prob > 0:
        jumps = rng.random(days) < jump_prob
        shock = rng.normal(jump_mean, jump_vol, size=days) * jumps
        # Equity/credit-beta scaled systemic shock.
        beta = np.array([_systemic_beta(ins) for ins in instruments])
        log_rets += np.outer(shock, beta)

    prices = np.empty((days + 1, n))
    prices[0] = start_price
    prices[1:] = start_price * np.exp(np.cumsum(log_rets, axis=0))
    dates = np.arange(days + 1)
    return instruments, dates, prices


def _systemic_beta(ins: Instrument) -> float:
    return {
        AssetClass.EQUITY: 1.0,
        AssetClass.CREDIT: 0.7,
        AssetClass.COMMODITY: 0.4,
        AssetClass.ALTERNATIVE: 0.5,
        AssetClass.RATES: -0.3,
        AssetClass.FX: -0.2,
        AssetClass.CASH: 0.0,
    }[ins.asset_class]
