import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas import optimize, risk


class TestRisk(unittest.TestCase):
    def setUp(self):
        # Two-asset covariance (per-period), equal weights.
        self.cov = [[0.04, 0.006], [0.006, 0.09]]  # vols 0.2 and 0.3, corr 0.1
        self.w = [0.5, 0.5]
        self.value = 1_000_000.0

    def test_portfolio_variance_matches_formula(self):
        # w^T Σ w = .25*.04 + .25*.09 + 2*.25*.006 = .01 + .0225 + .003 = .0355
        self.assertAlmostEqual(risk.portfolio_variance(self.w, self.cov), 0.0355)

    def test_component_var_sums_to_total(self):
        total = risk.parametric_var(self.value, self.w, self.cov, 0.95, 1)
        comps = risk.component_var(self.value, self.w, self.cov, 0.95, 1)
        self.assertAlmostEqual(sum(comps), total, places=6)

    def test_risk_contributions_sum_to_one(self):
        rc = risk.risk_contributions(self.w, self.cov)
        self.assertAlmostEqual(sum(rc), 1.0, places=9)

    def test_parametric_var_scales_with_horizon(self):
        v1 = risk.parametric_var(self.value, self.w, self.cov, 0.95, 1)
        v4 = risk.parametric_var(self.value, self.w, self.cov, 0.95, 4)
        self.assertAlmostEqual(v4, v1 * 2.0, places=4)  # sqrt(4) = 2

    def test_cvar_greater_than_var(self):
        var = risk.parametric_var(self.value, self.w, self.cov, 0.95, 1)
        cvar = risk.parametric_cvar(self.value, self.w, self.cov, 0.95, 1)
        self.assertGreater(cvar, var)

    def test_historical_var_positive_loss(self):
        pnl = [-100.0, -50.0, 0.0, 50.0, 100.0, 20.0, -30.0, 10.0, -80.0, 60.0]
        v = risk.historical_var(pnl, 0.90)
        self.assertGreater(v, 0.0)

    def test_max_drawdown(self):
        curve = [100.0, 120.0, 90.0, 110.0, 60.0, 80.0]
        # peak 120 -> trough 60 => 50% drawdown
        self.assertAlmostEqual(risk.max_drawdown(curve), 0.5)

    def test_beta_of_series_with_itself_is_one(self):
        s = [0.01, -0.02, 0.03, -0.01, 0.005]
        self.assertAlmostEqual(risk.beta(s, s), 1.0, places=9)


class TestOptimize(unittest.TestCase):
    def setUp(self):
        self.cov = [[0.04, 0.006], [0.006, 0.09]]
        self.mu = [0.10, 0.14]

    def test_min_variance_weights_sum_to_one(self):
        w = optimize.min_variance(self.cov)
        self.assertAlmostEqual(sum(w), 1.0, places=9)

    def test_min_variance_lower_var_than_equal_weight(self):
        w_mv = optimize.min_variance(self.cov)
        w_eq = optimize.equal_weight(2)
        self.assertLessEqual(risk.portfolio_variance(w_mv, self.cov),
                             risk.portfolio_variance(w_eq, self.cov) + 1e-12)

    def test_mean_variance_hits_target_return(self):
        w = optimize.mean_variance(self.mu, self.cov, 0.12)
        realized = sum(wi * mi for wi, mi in zip(w, self.mu))
        self.assertAlmostEqual(realized, 0.12, places=9)

    def test_risk_parity_equalizes_contributions(self):
        w = optimize.risk_parity(self.cov)
        rc = risk.risk_contributions(w, self.cov)
        self.assertAlmostEqual(rc[0], rc[1], places=4)
        self.assertAlmostEqual(sum(w), 1.0, places=9)

    def test_max_sharpe_weights_sum_to_one(self):
        w = optimize.max_sharpe(self.mu, self.cov, risk_free=0.02)
        self.assertAlmostEqual(sum(w), 1.0, places=9)


if __name__ == "__main__":
    unittest.main()
