"""Worked example: construct three portfolios and compare their risk.

Run from the ``atlas/`` directory:

    python3 examples/optimize_and_analyze.py

Shows how the building blocks compose: estimate the covariance from history,
build minimum-variance / risk-parity / max-Sharpe books, then push each through
the risk engine and compare volatility and VaR side by side.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas import optimize, risk, stats
from atlas.samples import demo_history


def annual_vol(w, cov):
    return risk.portfolio_volatility(w, cov, annualize=True)


def annual_return(w, mu):
    period = sum(wi * mi for wi, mi in zip(w, mu))
    return stats.annualize_return(period)


def main():
    hist = demo_history()
    mu = hist.expected_returns()
    cov = hist.covariance()
    symbols = hist.symbols
    nav = 100_000_000.0

    books = {
        "Equal weight": optimize.equal_weight(len(symbols)),
        "Min variance": optimize.min_variance(cov),
        "Risk parity": optimize.risk_parity(cov),
        "Max Sharpe": optimize.max_sharpe(mu, cov, risk_free=0.02),
    }

    print(f"{'Strategy':<16}{'Ann.Return':>12}{'Ann.Vol':>12}{'VaR 95% 1d':>16}")
    print("-" * 56)
    for name, w in books.items():
        ar = annual_return(w, mu)
        av = annual_vol(w, cov)
        var = risk.parametric_var(nav, w, cov, 0.95, 1)
        print(f"{name:<16}{ar * 100:>11.2f}%{av * 100:>11.2f}%{'$' + format(var, ',.0f'):>16}")

    print("\nRisk-parity weights (equal risk contribution):")
    rp = books["Risk parity"]
    rc = risk.risk_contributions(rp, cov)
    for s, w, c in zip(symbols, rp, rc):
        print(f"  {s:<6}{w * 100:>8.2f}%   risk share {c * 100:>6.2f}%")


if __name__ == "__main__":
    main()
