# ATLAS

**Asset, Treasury, Liability & Analytics System** — a portfolio risk and
analytics engine in the spirit of BlackRock's Aladdin, built from scratch in
**pure Python** with **zero external dependencies**.

Aladdin's job is to answer three questions for institutional capital: *how much
risk am I running, where is it coming from, and what happens if the world
breaks?* ATLAS answers the same three questions with a clean, auditable,
dependency-free codebase you can read end to end in an afternoon.

> **Honest framing.** Aladdin is a planet-scale platform with decades of data
> pipelines, security, and operational tooling behind it, monitoring ~$21T of
> real assets. ATLAS is not that and does not pretend to be. What it *is*: a
> correct, well-tested implementation of the quantitative core — the risk math,
> Monte-Carlo, optimisation, stress and compliance logic — that such platforms
> are built on, with every number verified by unit tests.

---

## What it does

| Pillar | Module | Highlights |
|---|---|---|
| **Risk analytics** | `risk.py` | Parametric / historical VaR & CVaR, annualised vol, marginal & component VaR, risk contributions, beta, drawdown, Sharpe/Sortino |
| **Monte-Carlo** | `montecarlo.py` | Correlated GBM simulation → full P&L distribution, VaR/CVaR, percentile bands |
| **Stress testing** | `stress.py` | Scenario engine + built-in historical replays (2008 GFC, 2020 COVID, 2022 rate shock) |
| **Construction** | `optimize.py` | Min-variance, max-Sharpe (tangency), target-return Markowitz, risk parity, efficient frontier |
| **Factor exposure** | `factor.py` | OLS multi-factor regression → betas, alpha, R² |
| **Compliance** | `compliance.py` | Composable mandate rules (position/sector/asset-class caps, leverage, cash floor) with breach reporting |
| **Orchestration** | `engine.py` | One call runs the full institutional report |

The numerics underneath (`linalg.py`, `stats.py`, `distributions.py`) are also
dependency-free: Cholesky factorisation, Gauss-Jordan inverse, sample
covariance, and an Acklam inverse-normal-CDF for VaR z-scores.

---

## Quick start

No install, no dependencies. From the `atlas/` directory:

```bash
python3 -m atlas demo                       # full risk report on a demo $100mm book
python3 -m atlas demo --json                # same, as JSON
python3 -m atlas frontier                    # efficient frontier + min-variance weights
python3 -m atlas analyze examples/sample_portfolio.json
```

As a library:

```python
from atlas import AtlasEngine, report
from atlas.samples import demo_portfolio, demo_history

engine = AtlasEngine(demo_portfolio(), demo_history())
print(report.render(engine.run()))
```

Build your own book:

```python
from atlas import Asset, Portfolio, Position, PriceHistory, AtlasEngine

pf = Portfolio("My Fund")
pf.add(Position(Asset("SPX", "US Equity", "equity", "broad_equity"), qty=1000, price=450.0))
pf.add(Position(Asset("TLT", "Treasuries", "bond", "rates"), qty=5000, price=95.0))

history = PriceHistory(symbols=["SPX", "TLT"],
                       prices={"SPX": [...], "TLT": [...]})   # aligned price series

engine = AtlasEngine(pf, history)
r = engine.run()
print(r.risk.var_95_1d, r.risk.risk_contributions)
```

---

## Sample output

```
  RISK ANALYTICS (1-day, parametric)
  Annualised volatility        10.35%
  VaR  95%                     $1,072,305
  CVaR 95% (expected shortfall)     $1,344,713

  RISK CONTRIBUTION BY POSITION
  Symbol         Component VaR     % of Risk
  SPX                 $399,919        37.30%
  TECH                $330,526        30.82%
  ...

  STRESS TESTS
  2008 Global Financial Crisis            $-32,510,000     -32.51%
  2020 COVID Crash                        $-26,520,000     -26.52%
```

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

37 tests cover the linear algebra, statistics, distributions, risk metrics,
optimisers, and the end-to-end engine. Key invariants asserted:

- component VaR sums to total parametric VaR (Euler allocation)
- risk contributions sum to 1.0; risk-parity equalises them
- min-variance ≤ equal-weight variance; mean-variance hits its target return
- the correlated generator recovers its input covariance (MC convergence)
- `norm_ppf` matches known z-scores (1.645 @ 95%, 2.326 @ 99%)

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for methodology and design notes.
