"""End-to-end ATLAS demo — runs fully offline on synthetic data.

    python -m examples.demo      (from the atlas-engine directory)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import atlas
from atlas import optimize
from atlas.instruments import AssetClass
from atlas.stress import factor_sensitivity


def main() -> None:
    print("Generating 3y synthetic multi-asset market (fat-tailed, correlated)...\n")
    market = atlas.market_from_synthetic(days=756, jump_prob=0.01, seed=7)

    # A realistic institutional 60/40-ish multi-asset book with a short.
    book = atlas.Portfolio.from_weights(
        {
            "SPX": 0.28, "NDX": 0.12, "EFA": 0.10, "EEM": 0.06,
            "UST10": 0.18, "IG": 0.12, "HY": 0.08, "GOLD": 0.06,
            "WTI": 0.04, "USD": -0.04,   # small short USD hedge
        },
        nav=250_000_000,
        name="Global Multi-Asset Fund",
    )

    engine = atlas.RiskEngine(market, confidence=0.99, horizon_days=1,
                              cov_method="ewma", mc_distribution="t")
    report = engine.report(book)
    print(report.render())

    # ---- 10-day horizon VaR --------------------------------------------------
    print("\n10-DAY (REGULATORY) HORIZON")
    e10 = atlas.RiskEngine(market, confidence=0.99, horizon_days=10, mc_distribution="t")
    for v in e10.value_at_risk(book).values():
        print(f"    {v}")

    # ---- Optimisation --------------------------------------------------------
    print("\nPORTFOLIO CONSTRUCTION (annualised, EWMA covariance)")
    mu = market.mean_returns(annualized=True)
    cov = market.cov(method="ewma", annualized=True)
    syms = market.symbols
    for res in (
        optimize.min_variance(syms, cov, mu=mu),
        optimize.max_sharpe(syms, mu, cov, rf=0.02),
        optimize.risk_parity(syms, cov, mu=mu),
    ):
        print("   ", res)

    # ---- Single-factor sensitivity ------------------------------------------
    print("\nEQUITY SHOCK SENSITIVITY (P&L vs equity move)")
    for shock, pnl in factor_sensitivity(book, market, AssetClass.EQUITY,
                                         shocks=np.array([-0.20, -0.10, -0.05, 0.05, 0.10])):
        print(f"    equity {shock:+.0%}:  ${pnl:,.0f}")

    print("\nDone. All analytics computed offline, no market-data vendor required.")


if __name__ == "__main__":
    main()
