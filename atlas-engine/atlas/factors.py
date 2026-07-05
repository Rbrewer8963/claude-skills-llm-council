"""Factor modelling and exposure attribution.

ATLAS estimates each instrument's sensitivity to a set of risk factors via OLS,
then aggregates to portfolio-level factor exposures. This is how a risk officer
learns their book is, say, ``+1.2`` beta to equities and ``-4y`` duration to
rates — the exposures that actually move P&L — independent of position labels.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .market import MarketData
from .portfolio import Portfolio


@dataclass
class FactorModel:
    factor_names: list[str]
    betas: np.ndarray          # (n_assets, n_factors)
    alpha: np.ndarray          # (n_assets,)
    r_squared: np.ndarray      # (n_assets,)
    resid_vol: np.ndarray      # (n_assets,) annualised idiosyncratic vol

    def asset_exposure(self, symbol_index: int) -> dict[str, float]:
        return dict(zip(self.factor_names, self.betas[symbol_index]))


def build_factor_returns(market: MarketData) -> tuple[list[str], np.ndarray]:
    """Construct simple statistical factor return series from the universe itself.

    Factors:
      * ``equity``    — average equity-class return (market factor)
      * ``rates``     — average rates-class return (duration factor)
      * ``credit``    — high-yield minus investment-grade (credit spread factor)
      * ``commodity`` — average commodity return
    """
    from .instruments import AssetClass

    rets = market.returns("simple")
    cls = [ins.asset_class for ins in market.instruments]

    def avg(target: AssetClass) -> np.ndarray:
        idx = [i for i, c in enumerate(cls) if c == target]
        return rets[:, idx].mean(axis=1) if idx else np.zeros(rets.shape[0])

    equity = avg(AssetClass.EQUITY)
    rates = avg(AssetClass.RATES)
    commodity = avg(AssetClass.COMMODITY)
    syms = market.symbols
    credit = np.zeros(rets.shape[0])
    if "HY" in syms and "IG" in syms:
        credit = rets[:, syms.index("HY")] - rets[:, syms.index("IG")]

    names = ["equity", "rates", "credit", "commodity"]
    factors = np.column_stack([equity, rates, credit, commodity])
    return names, factors


def estimate_factor_model(market: MarketData, annual_days: int = 252) -> FactorModel:
    names, F = build_factor_returns(market)
    R = market.returns("simple")
    t, n = R.shape
    X = np.column_stack([np.ones(t), F])          # design matrix with intercept
    coef, *_ = np.linalg.lstsq(X, R, rcond=None)  # (n_factors+1, n_assets)
    fitted = X @ coef
    resid = R - fitted
    ss_res = (resid ** 2).sum(axis=0)
    ss_tot = ((R - R.mean(axis=0)) ** 2).sum(axis=0)
    r2 = 1.0 - ss_res / np.where(ss_tot == 0, np.nan, ss_tot)
    resid_vol = resid.std(axis=0, ddof=1) * np.sqrt(annual_days)
    return FactorModel(names, coef[1:].T, coef[0], np.nan_to_num(r2), resid_vol)


def portfolio_factor_exposure(portfolio: Portfolio, market: MarketData,
                              model: FactorModel | None = None) -> dict[str, float]:
    """Aggregate weighted factor betas to portfolio level (per $1 of NAV)."""
    model = model or estimate_factor_model(market)
    w = portfolio.weight_vector(market)
    exposure = w @ model.betas
    return dict(zip(model.factor_names, exposure.tolist()))
