# ATLAS — Asset, Trading, Liability, Analytics & Simulation

> An open, transparent, **offline-capable** institutional risk engine — a
> from-scratch reimplementation of the analytics core that makes a
> "trillion-dollar asset tool" like BlackRock's **Aladdin** valuable, in
> inspectable Python you can read, audit, and extend.

Aladdin's moat is not magic — it is the daily, disciplined application of a
handful of quantitative disciplines across an entire book: **correlated Monte
Carlo risk**, **multi-method Value-at-Risk**, **historically calibrated stress
testing**, **factor attribution**, **portfolio optimisation**, and
**risk-limit compliance**. ATLAS implements all of them, and does it in the
open.

## Why this is *superior* to a closed black box

| | Aladdin (closed) | **ATLAS (this engine)** |
|---|---|---|
| Transparency | Proprietary black box | Every formula readable in ~1,300 lines |
| VaR methodology | Vendor-defined | **3 independent methods** cross-checked (historical, parametric, Monte Carlo) — divergence itself is a flagged signal |
| Tail risk | Largely Gaussian workflows | **Student-t Monte Carlo** with fat tails + systemic jumps by default |
| Covariance | Fixed | **EWMA (regime-aware)** or sample, your choice |
| Data dependency | Requires the vendor's data spine | **Runs fully offline** on a built-in correlated market simulator; ingests your CSV when you have one |
| Cost | ~7–8 figures/yr in licensing | Free, MIT-licensed |
| Auditability | Trust us | Deterministic, seeded, 23 unit tests asserting the math |

This is a *core*, not a 3,000-engineer platform — but the analytics that drive
the risk numbers are real, correct, and tested.

## Install

```bash
cd atlas-engine
pip install -r requirements.txt      # numpy (required) + scipy (optional)
# or:  pip install -e .               # installs the `atlas` CLI entry point
```

SciPy is optional — it enables SLSQP-constrained optimisation. Without it,
ATLAS falls back to a pure-numpy projected-gradient solver.

## 60-second tour

```bash
python -m examples.demo               # full offline demo, synthetic market
python -m atlas report                # one-line risk report on a demo book
python -m atlas optimize --objective all
python -m atlas stress
python -m atlas simulate --paths 100000 --horizon 10
```

Run on **your** data (a wide price CSV + a portfolio JSON):

```bash
python -m atlas report --prices prices.csv --portfolio book.json --horizon 10 --json
```

`prices.csv` is `date, SYM1, SYM2, ...`; `book.json` is
`{"name": ..., "nav": ..., "weights": {"SPX": 0.3, ...}}`
(see [`examples/sample_portfolio.json`](examples/sample_portfolio.json)).

## What a report looks like

```
==============================================================================
  ATLAS RISK REPORT  —  Global Multi-Asset Fund
==============================================================================
  NAV: $250,000,000    Gross: $270,000,000    Net: $250,000,000    Leverage: 1.08x

  VALUE AT RISK
     historical VaR 99% / 1d: $7,553,101 (3.02%)  |  CVaR: $11,461,154 (4.58%)
     parametric VaR 99% / 1d: $6,648,706 (2.66%)  |  CVaR:  $7,605,794 (3.04%)
    monte-carlo/t VaR 99% / 1d: $7,389,859 (2.96%)  |  CVaR:  $9,811,018 (3.92%)

  TOP RISK CONTRIBUTORS (component VaR)
    SPX      $     2,779,197    42.3% of risk
    ...
  FACTOR EXPOSURE (per $1 NAV)
    equity  +0.593   rates +0.249   credit +0.063   commodity +0.097
  STRESS SCENARIOS
    2008 GFC (Sep–Nov)         P&L: $-76,200,000 (-30.48%)
    ...
  ⚠  COMPLIANCE / RISK ALERTS
    • Fat-tail warning: Monte-Carlo VaR is 1.6x parametric (non-normal tail risk).
==============================================================================
```

## Use it as a library

```python
import atlas

market = atlas.market_from_synthetic(days=756)          # or MarketData.from_csv("prices.csv")
book   = atlas.Portfolio.from_weights(
    {"SPX": 0.4, "UST10": 0.3, "IG": 0.2, "GOLD": 0.1}, nav=100_000_000)

engine = atlas.RiskEngine(market, confidence=0.99, horizon_days=10, cov_method="ewma")
print(engine.report(book).render())

# Or reach for individual analytics:
atlas.monte_carlo_var(book, market, confidence=0.99, distribution="t")
atlas.risk_contributions(book, market)          # who owns the risk
atlas.run_stress_suite(book, market)            # 2008, COVID, 2022, ...
atlas.max_sharpe(market.symbols, market.mean_returns(), market.cov())
```

## Architecture

```
atlas/
├── instruments.py   Instrument & AssetClass taxonomy
├── data.py          Correlated fat-tailed market simulator (offline engine)
├── market.py        Prices → returns, sample/EWMA covariance & correlation
├── portfolio.py     Dollar-exposure book: NAV, gross/net, leverage, weights
├── montecarlo.py    Cholesky-correlated Normal / Student-t simulation
├── risk.py          Historical / parametric / Monte-Carlo VaR + CVaR,
│                    component/marginal/incremental VaR decomposition
├── stress.py        Historically calibrated scenario library + sensitivity sweeps
├── optimize.py      Min-variance, max-Sharpe, risk-parity, efficient frontier
├── performance.py   Sharpe/Sortino/Calmar, drawdown, benchmark alpha/beta/IR
├── factors.py       OLS factor model → portfolio factor exposures
├── engine.py        RiskEngine orchestrator + formatted RiskReport + limit checks
└── cli.py           `python -m atlas {report,optimize,stress,simulate}`
```

## The methodology, briefly

- **Value-at-Risk, three ways.** Historical (empirical quantile, overlapping
  horizons), parametric (closed-form Gaussian variance-covariance with
  analytic Expected Shortfall), and Monte Carlo (full simulation). ATLAS
  reports all three and *flags their divergence* — when Monte-Carlo VaR pulls
  well above parametric, your tail is non-normal and the Gaussian number is
  lying to you.
- **Correlated Monte Carlo.** Cholesky factorisation of the covariance matrix
  generates jointly consistent scenarios; a Student-t innovation injects fat
  tails; antithetic variates halve sampling error. Non-PSD covariances are
  auto-repaired via eigenvalue clipping.
- **Risk decomposition.** Euler/component VaR answers *"which positions own the
  tail?"* — it sums exactly to total VaR. Incremental VaR pre-checks a trade
  before you put it on.
- **Stress testing.** Six historically calibrated scenarios (2008 GFC, COVID,
  2022 rate shock, taper tantrum, stagflation, flight-to-quality) mapped onto
  your actual asset-class exposures, plus custom scenarios and single-factor
  sweeps.
- **Portfolio construction.** Global minimum-variance, tangency (max-Sharpe),
  and equal-risk-contribution (risk parity), with long-only constraints and
  the full efficient frontier.

## Tests

```bash
python tests/test_atlas.py     # 23 assertions, no pytest needed
# or:  python -m pytest -q
```

The suite asserts the *math*, not just that code runs: covariance is PSD,
component VaR sums to total, Student-t tails exceed Gaussian, risk parity
equalises risk contributions, simulated covariance recovers the input,
beta-vs-self is 1.0, and more.

## Scope & honesty

ATLAS models linear (delta) P&L, which is exact for cash instruments and a
first-order approximation for options — a convexity/Greeks layer is the natural
next module. The bundled market is synthetic (seeded, reproducible) so the
engine runs anywhere with zero data cost; point it at real price history via
CSV for production use. It is an analytics core, not a trade-execution or
order-management system. What it *does* do, it does correctly and in the open.

MIT-licensed.
