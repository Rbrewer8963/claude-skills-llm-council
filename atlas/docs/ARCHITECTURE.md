# ATLAS — Architecture & Methodology

ATLAS is layered so each tier depends only on the ones beneath it. Every layer
is pure standard-library Python.

```
        ┌─────────────────────────────────────────────┐
        │  cli.py / report.py        (interface)        │
        ├─────────────────────────────────────────────┤
        │  engine.py                 (orchestration)    │
        ├──────────┬──────────┬──────────┬─────────────┤
        │ risk     │ montecarlo│ stress   │ optimize    │  (analytics)
        │ factor   │ compliance│          │             │
        ├──────────┴──────────┴──────────┴─────────────┤
        │  portfolio.py   market.py   samples.py        │  (domain / data)
        ├─────────────────────────────────────────────┤
        │  linalg.py   stats.py   distributions.py      │  (numerics)
        └─────────────────────────────────────────────┘
```

## Data conventions

- **Return matrices** are period-by-asset: `returns[t][i]` is asset `i`'s return
  in period `t`. This matches how time-series data arrives and keeps the
  covariance estimator readable.
- **Weights** are fractions of net asset value; a fully-invested unlevered book
  sums to 1.0. Shorts are negative, leverage pushes the gross above 1.0.
- **VaR/CVaR** are returned as *positive loss figures* in currency units.

## Numerics (`linalg`, `stats`, `distributions`)

- **Cholesky** factorisation (`L Lᵀ = Σ`) drives correlated Monte-Carlo draws and
  doubles as a positive-definiteness check on estimated covariances.
- **Gauss-Jordan** inverse with partial pivoting backs every closed-form
  optimiser and the factor regression's normal equations.
- **Inverse normal CDF** uses Acklam's rational approximation (~1e-9 accuracy),
  giving exact VaR z-scores without SciPy.

## Risk analytics (`risk`)

Three independent VaR methods let results cross-check each other:

1. **Parametric** — `VaR = value · z_α · σ · √h`, from `σ = √(wᵀΣw)`.
2. **Historical** — empirical quantile of a realised P&L sample.
3. **Monte-Carlo** — quantile of a simulated P&L distribution.

**Risk decomposition** uses the Euler allocation: marginal VaR is the gradient
`∂VaR/∂wᵢ ∝ (Σw)ᵢ / σ`, and component VaR `= wᵢ · MVaRᵢ`. Because VaR is
homogeneous of degree 1 in the weights, the component VaRs **sum exactly to
total VaR** — asserted in the test suite. This is the "where is my risk coming
from" view.

## Monte-Carlo (`montecarlo`)

Assets evolve as correlated geometric Brownian motion: each step draws a
correlated normal shock vector (mean `μ`, covariance `Σ`) via the shared
Cholesky factor and applies it multiplicatively. The book is marked buy-and-hold
at the horizon, producing a P&L distribution from which VaR, CVaR and percentile
bands are read empirically — no portfolio-level normality assumption. A fixed
seed makes every run reproducible.

## Construction (`optimize`)

- **Global minimum variance** — `w = Σ⁻¹1 / (1ᵀΣ⁻¹1)`.
- **Max-Sharpe / tangency** — `w ∝ Σ⁻¹(μ − r_f·1)`.
- **Target-return Markowitz** — the two-constraint frontier solved via the
  A/B/C/D scalars; hits the requested expected return exactly.
- **Risk parity** — multiplicative fixed-point iteration converging to equal
  risk contributions (`1/n` each).

These are the exact unconstrained solutions; adding long-only or box
constraints would call for a quadratic-programming layer, a natural next step.

## Stress & compliance

- **Stress** applies instantaneous per-asset-class (or per-symbol) shocks and
  reports mark-to-market impact. Historical replays approximate the broad
  asset-class moves of 2008, 2020 and 2022.
- **Compliance** composes small rule closures (`Portfolio → [Breach]`) into a
  mandate; the engine runs them pre/post-trade and returns a pass/fail report.

## Deliberate limitations

Honesty about scope is part of the design:

- Gaussian shocks; no fat tails, jumps, or regime switching (a Student-t or
  historical-bootstrap shock model would slot into `distributions`).
- No optimisation constraints beyond the analytical solutions.
- Covariance is a plain sample estimator — no Ledoit-Wolf shrinkage or
  exponential weighting yet.
- Stress shocks are illustrative approximations, not tick-level replays.

Each is a clearly bounded extension point, not a hidden gap.
