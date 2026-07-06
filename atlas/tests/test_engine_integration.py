import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas import compliance, factor, report, stress
from atlas.engine import AtlasEngine
from atlas.samples import demo_history, demo_portfolio


class TestEngineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pf = demo_portfolio()
        cls.hist = demo_history()
        cls.engine = AtlasEngine(cls.pf, cls.hist, seed=42)

    def test_portfolio_symbols_align_with_history(self):
        self.assertEqual(self.pf.symbols, self.hist.symbols)

    def test_weights_sum_to_one(self):
        self.assertAlmostEqual(sum(self.pf.weights()), 1.0, places=6)

    def test_full_run_produces_report(self):
        result = self.engine.run(mc_horizon_days=5, mc_paths=2000)
        self.assertGreater(result.risk.annualized_vol, 0.0)
        self.assertGreater(result.risk.var_95_1d, 0.0)
        self.assertLess(result.risk.var_95_1d, result.risk.var_99_1d)
        self.assertEqual(len(result.stress), 4)
        # Rendering must not raise and must mention the portfolio name.
        text = report.render(result)
        self.assertIn("Global Diversified Fund", text)

    def test_component_var_sums_to_total(self):
        rr = self.engine.risk_report()
        self.assertAlmostEqual(sum(rr.component_var.values()), rr.var_95_1d, places=2)

    def test_monte_carlo_deterministic_with_seed(self):
        r1 = self.engine.monte_carlo(horizon_days=3, n_paths=1500)
        engine2 = AtlasEngine(self.pf, self.hist, seed=42)
        r2 = engine2.monte_carlo(horizon_days=3, n_paths=1500)
        self.assertEqual(r1.pnl[:10], r2.pnl[:10])

    def test_stress_gfc_is_a_loss(self):
        results = self.engine.stress_test()
        gfc = next(r for r in results if "2008" in r.scenario)
        self.assertLess(gfc.total_pnl, 0.0)

    def test_symbol_mismatch_raises(self):
        bad = demo_portfolio()
        bad.positions.reverse()  # reorder symbols
        with self.assertRaises(ValueError):
            AtlasEngine(bad, self.hist)

    def test_factor_model_recovers_exposure(self):
        # y = 2*f + noise-free -> beta ~ 2, r2 ~ 1
        f = [0.01, -0.02, 0.03, 0.0, -0.01, 0.015, -0.005]
        y = [2 * x for x in f]
        fm = factor.fit_factor_model(y, {"MKT": f})
        self.assertAlmostEqual(fm.betas["MKT"], 2.0, places=6)
        self.assertAlmostEqual(fm.r_squared, 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
