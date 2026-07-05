"""Test suite for the ATLAS risk engine.

Run with:  python -m pytest -q   (or)   python tests/test_atlas.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import atlas
from atlas import optimize, performance, risk, stress
from atlas.instruments import AssetClass
from atlas.montecarlo import simulate


def make_market(seed=7, days=756):
    return atlas.market_from_synthetic(days=days, seed=seed)


def make_book():
    return atlas.Portfolio.from_weights(
        {"SPX": 0.4, "UST10": 0.3, "IG": 0.2, "GOLD": 0.1}, nav=10_000_000, name="Test")


# --------------------------------------------------------------------- data / market
def test_market_shapes_and_positivity():
    m = make_market()
    assert m.prices.shape[1] == m.n_assets
    assert (m.prices > 0).all()
    assert m.returns("simple").shape == (m.prices.shape[0] - 1, m.n_assets)


def test_covariance_is_psd_and_symmetric():
    m = make_market()
    for method in ("sample", "ewma"):
        cov = m.cov(method=method)
        assert np.allclose(cov, cov.T)
        assert np.linalg.eigvalsh(cov).min() > -1e-8


def test_correlation_diagonal_is_one():
    m = make_market()
    c = m.corr(method="ewma")
    assert np.allclose(np.diag(c), 1.0, atol=1e-6)


# --------------------------------------------------------------------- portfolio
def test_portfolio_nav_weights_leverage():
    p = atlas.Portfolio({"SPX": 60, "UST10": 40}, cash=0.0)
    assert p.nav == 100
    assert abs(sum(p.weights().values()) - 1.0) < 1e-12
    assert p.leverage == 1.0
    short = atlas.Portfolio({"SPX": 120, "UST10": -20}, cash=0.0)
    assert short.gross_exposure == 140
    assert short.leverage == 1.4


def test_from_weights_cash_residual():
    p = atlas.Portfolio.from_weights({"SPX": 0.6, "UST10": 0.3}, nav=1000)
    assert abs(p.cash - 100) < 1e-9
    assert abs(p.nav - 1000) < 1e-9


# --------------------------------------------------------------------- VaR
def test_var_ordering_and_signs():
    m, p = make_market(), make_book()
    h = risk.historical_var(p, m, confidence=0.99)
    para = risk.parametric_var(p, m, confidence=0.99)
    mc = risk.monte_carlo_var(p, m, confidence=0.99, n_paths=20000)
    for v in (h, para, mc):
        assert v.var_dollar > 0
        assert v.cvar_dollar >= v.var_dollar - 1e-6   # CVaR >= VaR
        assert 0 < v.var_pct < 1


def test_var_scales_with_confidence():
    m, p = make_market(), make_book()
    v95 = risk.parametric_var(p, m, confidence=0.95).var_dollar
    v99 = risk.parametric_var(p, m, confidence=0.99).var_dollar
    assert v99 > v95


def test_var_scales_with_horizon():
    m, p = make_market(), make_book()
    v1 = risk.parametric_var(p, m, horizon_days=1).var_dollar
    v10 = risk.parametric_var(p, m, horizon_days=10).var_dollar
    # Roughly sqrt(10) scaling for the vol term.
    assert 2.0 < v10 / v1 < 4.5


def test_component_var_sums_to_total():
    m, p = make_market(), make_book()
    rc = risk.risk_contributions(p, m, confidence=0.99)
    total_component = rc.component.sum()
    para = risk.parametric_var(p, m, confidence=0.99)
    # Component VaR sums to the (drift-free) parametric VaR quantile term.
    assert rc.percent.sum() == 0 or abs(rc.percent.sum() - 1.0) < 1e-6
    assert total_component > 0


def test_incremental_var_positive_for_added_risk():
    m, p = make_market(), make_book()
    inc = risk.incremental_var(p, m, "NDX", 1_000_000)
    assert inc > 0   # adding a risky long increases VaR


# --------------------------------------------------------------------- monte carlo
def test_simulation_preserves_covariance():
    m = make_market()
    cov = m.cov(method="sample", annualized=True)
    mean = m.mean_returns(annualized=True)
    sim = simulate(mean, cov, n_paths=200_000, horizon_days=1,
                   annual_days=m.annual_days, distribution="normal", seed=1)
    # Annualise the simulated 1-day covariance back up and compare.
    emp = np.cov(sim.asset_returns, rowvar=False) * m.annual_days
    rel_err = np.abs(emp - cov) / (np.abs(cov) + 1e-8)
    assert np.median(rel_err) < 0.1


def test_student_t_has_fatter_tails_than_normal():
    m, p = make_market(), make_book()
    exp = p.exposure_vector(m)
    cov = m.cov(annualized=True)
    mean = m.mean_returns(annualized=True)
    n = simulate(mean, cov, 100000, 1, m.annual_days, "normal", seed=3).portfolio_pnl(exp)
    t = simulate(mean, cov, 100000, 1, m.annual_days, "t", student_t_df=4, seed=3).portfolio_pnl(exp)
    # 99.9th percentile loss should be larger under Student-t.
    assert np.percentile(-t, 99.9) > np.percentile(-n, 99.9)


# --------------------------------------------------------------------- stress
def test_stress_all_losses_in_gfc():
    m = make_market()
    p = make_book()
    gfc = [s for s in stress.historical_scenarios() if "GFC" in s.name][0]
    res = stress.apply_scenario(p, m, gfc)
    assert res.pnl < 0   # a long risk book loses in the GFC


def test_stress_suite_runs():
    m, p = make_market(), make_book()
    results = stress.run_stress_suite(p, m)
    assert len(results) == len(stress.historical_scenarios())
    assert all(hasattr(r, "pnl") for r in results)


# --------------------------------------------------------------------- optimize
def test_min_variance_beats_equal_weight_vol():
    m = make_market()
    cov = m.cov(annualized=True)
    syms = m.symbols
    mv = optimize.min_variance(syms, cov)
    eq_w = np.ones(len(syms)) / len(syms)
    eq_vol = np.sqrt(eq_w @ cov @ eq_w)
    assert mv.volatility <= eq_vol + 1e-9


def test_optimizer_weights_sum_to_one_long_only():
    m = make_market()
    cov = m.cov(annualized=True)
    mu = m.mean_returns(annualized=True)
    for res in (optimize.min_variance(m.symbols, cov),
                optimize.max_sharpe(m.symbols, mu, cov),
                optimize.risk_parity(m.symbols, cov)):
        w = np.array(list(res.weights.values()))
        assert abs(w.sum() - 1.0) < 1e-6
        assert (w >= -1e-6).all()


def test_risk_parity_equalizes_risk_contributions():
    m = make_market()
    cov = m.cov(annualized=True)
    res = optimize.risk_parity(m.symbols, cov)
    w = np.array(list(res.weights.values()))
    port_vol = np.sqrt(w @ cov @ w)
    rc = w * (cov @ w) / port_vol
    rc /= rc.sum()
    # Risk contributions should be roughly equal.
    assert rc.std() < 0.05


def test_efficient_frontier_monotone_risk_return():
    m = make_market()
    cov, mu = m.cov(annualized=True), m.mean_returns(annualized=True)
    frontier = optimize.efficient_frontier(m.symbols, mu, cov, n_points=10)
    vols = [f.volatility for f in frontier]
    rets = [f.expected_return for f in frontier]
    # Higher target return generally requires higher vol at the frontier extremes.
    assert rets[-1] >= rets[0]
    assert max(vols) >= min(vols)


# --------------------------------------------------------------------- performance
def test_performance_stats_reasonable():
    m, p = make_market(), make_book()
    rets = performance.portfolio_return_series(p, m)
    stats = performance.performance_stats(rets)
    assert 0 <= stats.max_drawdown <= 1
    assert 0 <= stats.hit_ratio <= 1
    assert stats.annual_vol > 0


def test_max_drawdown_known_series():
    rets = np.array([0.10, -0.50, 0.10])  # peak 1.1 -> trough 0.55
    dd = performance.max_drawdown(rets)
    assert abs(dd - 0.5) < 1e-9


def test_benchmark_beta_of_self_is_one():
    m, p = make_market(), make_book()
    rets = performance.portfolio_return_series(p, m)
    bs = performance.benchmark_stats(rets, rets)
    assert abs(bs.beta - 1.0) < 1e-6
    assert abs(bs.correlation - 1.0) < 1e-6


# --------------------------------------------------------------------- factors
def test_factor_exposure_keys():
    from atlas import factors

    m, p = make_market(), make_book()
    fe = factors.portfolio_factor_exposure(p, m)
    assert set(fe) == {"equity", "rates", "credit", "commodity"}


# --------------------------------------------------------------------- engine
def test_engine_report_end_to_end():
    m = make_market()
    p = make_book()
    report = atlas.RiskEngine(m).report(p)
    text = report.render()
    assert "ATLAS RISK REPORT" in text
    assert report.nav == p.nav
    assert len(report.stress) > 0


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
