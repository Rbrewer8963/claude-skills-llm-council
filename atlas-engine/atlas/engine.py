"""ATLAS orchestration layer.

:class:`RiskEngine` is the single entry point that composes market data,
portfolio, Monte Carlo, VaR, stress, factor and performance analytics into one
coherent **risk report** — the daily deliverable an institutional risk desk
lives on.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import factors, performance, risk, stress
from .market import MarketData
from .montecarlo import simulate
from .portfolio import Portfolio


@dataclass
class RiskReport:
    portfolio: str
    nav: float
    gross_exposure: float
    net_exposure: float
    leverage: float
    var: dict[str, risk.VaRResult]
    contributions: risk.RiskContribution
    stress: list[stress.StressResult]
    factor_exposure: dict[str, float]
    performance: performance.PerformanceStats
    warnings: list[str] = field(default_factory=list)

    def render(self) -> str:
        return render_report(self)


class RiskEngine:
    """High-availability risk engine facade.

    Parameters
    ----------
    market:
        A :class:`MarketData` instance (real or synthetic).
    confidence:
        VaR confidence level.
    horizon_days:
        Risk horizon in trading days.
    cov_method:
        ``"ewma"`` (default, regime-aware) or ``"sample"``.
    """

    def __init__(self, market: MarketData, confidence: float = 0.99, horizon_days: int = 1,
                 cov_method: str = "ewma", rf: float = 0.02, mc_paths: int = 50_000,
                 mc_distribution: str = "t", seed: int | None = 42):
        self.market = market
        self.confidence = confidence
        self.horizon_days = horizon_days
        self.cov_method = cov_method
        self.rf = rf
        self.mc_paths = mc_paths
        self.mc_distribution = mc_distribution
        self.seed = seed
        self._factor_model = factors.estimate_factor_model(market, market.annual_days)

    # ------------------------------------------------------------------ analytics
    def value_at_risk(self, portfolio: Portfolio) -> dict[str, risk.VaRResult]:
        sim = simulate(
            mean=self.market.mean_returns(annualized=True),
            cov=self.market.cov(method=self.cov_method, annualized=True),
            n_paths=self.mc_paths, horizon_days=self.horizon_days,
            annual_days=self.market.annual_days, distribution=self.mc_distribution, seed=self.seed,
        )
        kw = dict(confidence=self.confidence, horizon_days=self.horizon_days)
        return {
            "historical": risk.historical_var(portfolio, self.market, **kw),
            "parametric": risk.parametric_var(portfolio, self.market, cov_method=self.cov_method, **kw),
            "monte_carlo": risk.monte_carlo_var(portfolio, self.market, sim=sim, **kw),
        }

    def report(self, portfolio: Portfolio) -> RiskReport:
        var = self.value_at_risk(portfolio)
        contrib = risk.risk_contributions(portfolio, self.market, self.confidence,
                                          self.horizon_days, self.cov_method)
        stress_results = stress.run_stress_suite(portfolio, self.market)
        exposure = factors.portfolio_factor_exposure(portfolio, self.market, self._factor_model)
        rets = performance.portfolio_return_series(portfolio, self.market)
        perf = performance.performance_stats(rets, rf=self.rf, annual_days=self.market.annual_days)

        warnings = self._risk_checks(portfolio, var, stress_results)
        return RiskReport(
            portfolio=portfolio.name, nav=portfolio.nav,
            gross_exposure=portfolio.gross_exposure, net_exposure=portfolio.net_exposure,
            leverage=portfolio.leverage, var=var, contributions=contrib,
            stress=stress_results, factor_exposure=exposure, performance=perf, warnings=warnings,
        )

    # ------------------------------------------------------------------ compliance
    def _risk_checks(self, portfolio, var, stress_results, var_limit_pct: float = 0.05,
                     leverage_limit: float = 3.0, stress_limit_pct: float = -0.35) -> list[str]:
        out = []
        mc = var["monte_carlo"]
        if mc.var_pct > var_limit_pct:
            out.append(f"VaR breach: {mc.var_pct:.2%} exceeds {var_limit_pct:.0%} limit.")
        if portfolio.leverage > leverage_limit:
            out.append(f"Leverage {portfolio.leverage:.2f}x exceeds {leverage_limit:.1f}x limit.")
        worst = min(stress_results, key=lambda s: s.pnl_pct)
        if worst.pnl_pct < stress_limit_pct:
            out.append(f"Stress breach: '{worst.scenario}' loses {worst.pnl_pct:.1%} "
                       f"(> {abs(stress_limit_pct):.0%} limit).")
        divergence = mc.var_dollar / var["parametric"].var_dollar if var["parametric"].var_dollar else 1
        if divergence > 1.5:
            out.append(f"Fat-tail warning: Monte-Carlo VaR is {divergence:.1f}x parametric "
                       f"(non-normal tail risk).")
        return out


def render_report(rep: RiskReport) -> str:
    L = []
    bar = "=" * 78
    L.append(bar)
    L.append(f"  ATLAS RISK REPORT  —  {rep.portfolio}")
    L.append(bar)
    L.append(f"  NAV: ${rep.nav:,.0f}    Gross: ${rep.gross_exposure:,.0f}    "
             f"Net: ${rep.net_exposure:,.0f}    Leverage: {rep.leverage:.2f}x")
    L.append("")
    L.append("  VALUE AT RISK")
    for v in rep.var.values():
        L.append(f"    {v}")
    L.append("")
    L.append("  TOP RISK CONTRIBUTORS (component VaR)")
    for sym, cvar, pct in rep.contributions.top(5):
        L.append(f"    {sym:<8s} ${cvar:>14,.0f}   {pct:>6.1%} of risk")
    L.append("")
    L.append("  FACTOR EXPOSURE (per $1 NAV)")
    for name, beta in rep.factor_exposure.items():
        L.append(f"    {name:<12s} {beta:+.3f}")
    L.append("")
    L.append("  STRESS SCENARIOS")
    for s in sorted(rep.stress, key=lambda x: x.pnl_pct):
        L.append(f"    {s}")
    L.append("")
    p = rep.performance
    L.append("  PERFORMANCE (in-sample, buy-and-hold)")
    L.append(f"    Ann.Return {p.annual_return:>7.2%}   Ann.Vol {p.annual_vol:>7.2%}   "
             f"Sharpe {p.sharpe:>5.2f}   Sortino {p.sortino:>5.2f}")
    L.append(f"    MaxDD {p.max_drawdown:>7.2%}   Calmar {p.calmar:>5.2f}   "
             f"Skew {p.skew:>+5.2f}   ExKurt {p.kurtosis:>5.2f}")
    L.append("")
    if rep.warnings:
        L.append("  ⚠  COMPLIANCE / RISK ALERTS")
        for w in rep.warnings:
            L.append(f"    • {w}")
    else:
        L.append("  ✓  All risk limits within tolerance.")
    L.append(bar)
    return "\n".join(L)
