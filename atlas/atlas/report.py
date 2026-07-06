"""Human-readable rendering of an :class:`~atlas.engine.AnalysisReport`.

Plain-text tables, zero dependencies — suitable for a terminal, a log, or the
body of an email. Currency figures are rendered with thousands separators.
"""

from __future__ import annotations

from typing import List

from .engine import AnalysisReport


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _pct(x: float) -> str:
    return f"{x * 100:,.2f}%"


def _rule(width: int = 64) -> str:
    return "-" * width


def render(report: AnalysisReport) -> str:
    lines: List[str] = []
    add = lines.append

    add("=" * 64)
    add(f"  ATLAS RISK REPORT — {report.portfolio}")
    add("=" * 64)
    add(f"  Net asset value: {_money(report.total_value)}")
    add("")

    r = report.risk
    add("  RISK ANALYTICS (1-day, parametric)")
    add(_rule())
    add(f"  Annualised volatility        {_pct(r.annualized_vol)}")
    add(f"  VaR  95%                     {_money(r.var_95_1d)}")
    add(f"  CVaR 95% (expected shortfall){_money(r.cvar_95_1d):>15}")
    add(f"  VaR  99%                     {_money(r.var_99_1d)}")
    add("")

    add("  RISK CONTRIBUTION BY POSITION")
    add(_rule())
    add(f"  {'Symbol':<10}{'Component VaR':>18}{'% of Risk':>14}")
    for sym in r.component_var:
        cv = r.component_var[sym]
        rc = r.risk_contributions[sym]
        add(f"  {sym:<10}{_money(cv):>18}{_pct(rc):>14}")
    add("")

    if report.simulation:
        s = report.simulation.summary()
        add(f"  MONTE-CARLO SIMULATION ({report.simulation.n_paths:,} paths, "
            f"{report.simulation.horizon_days}-day horizon)")
        add(_rule())
        add(f"  Mean P&L                     {_money(s['mean_pnl'])}")
        add(f"  VaR  95%                     {_money(s['var_95'])}")
        add(f"  CVaR 95%                     {_money(s['cvar_95'])}")
        add(f"  VaR  99%                     {_money(s['var_99'])}")
        add(f"  5th / 50th / 95th pctile NAV {_money(s['p05_value'])} / "
            f"{_money(s['p50_value'])} / {_money(s['p95_value'])}")
        add(f"  Worst / best path P&L        {_money(s['worst_path'])} / "
            f"{_money(s['best_path'])}")
        add("")

    if report.stress:
        add("  STRESS TESTS")
        add(_rule())
        add(f"  {'Scenario':<38}{'P&L':>14}{'Impact':>12}")
        for st in report.stress:
            add(f"  {st.scenario[:36]:<38}{_money(st.total_pnl):>14}{_pct(st.pct_impact):>12}")
        add("")

    if report.compliance:
        c = report.compliance
        add("  COMPLIANCE")
        add(_rule())
        if c.passed:
            add("  PASS — all mandate rules satisfied.")
        else:
            add(f"  FAIL — {len(c.breaches)} breach(es):")
            for b in c.breaches:
                add(f"    {b}")
        add("")

    add("=" * 64)
    return "\n".join(lines)
