import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas import service
from atlas.config import Config
from atlas.samples import demo_history, demo_portfolio


def _payload():
    pf = demo_portfolio()
    hist = demo_history()
    return {
        "name": pf.name,
        "positions": [
            {"symbol": p.asset.symbol, "name": p.asset.name,
             "asset_class": p.asset.asset_class, "sector": p.asset.sector,
             "quantity": p.quantity, "price": p.price}
            for p in pf.positions
        ],
        "prices": {s: hist.prices[s] for s in hist.symbols},
    }


class TestService(unittest.TestCase):
    def setUp(self):
        self.config = Config()
        self.body = _payload()

    def test_health(self):
        status, resp = service.route("GET", "/health", None, self.config)
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "ok")

    def test_version(self):
        status, resp = service.route("GET", "/version", None, self.config)
        self.assertEqual(status, 200)
        self.assertEqual(resp["name"], "atlas")

    def test_analyze_full(self):
        body = dict(self.body, horizon_days=3, n_paths=500)
        status, resp = service.route("POST", "/analyze", body, self.config)
        self.assertEqual(status, 200)
        self.assertIn("risk", resp)
        self.assertIn("stress", resp)
        self.assertGreater(resp["risk"]["var_95_1d"], 0)

    def test_risk_only(self):
        status, resp = service.route("POST", "/risk", self.body, self.config)
        self.assertEqual(status, 200)
        self.assertIn("component_var", resp)

    def test_optimize_min_variance(self):
        body = dict(self.body, method="min_variance")
        status, resp = service.route("POST", "/optimize", body, self.config)
        self.assertEqual(status, 200)
        self.assertAlmostEqual(sum(resp["weights"].values()), 1.0, places=6)

    def test_unknown_route_404(self):
        status, resp = service.route("POST", "/nope", {}, self.config)
        self.assertEqual(status, 404)

    def test_validation_error_maps_to_400(self):
        status, resp = service.route("POST", "/risk", {"positions": []}, self.config)
        self.assertEqual(status, 400)
        self.assertEqual(resp["error"], "validation_error")

    def test_sim_param_limit_enforced(self):
        body = dict(self.body, n_paths=10 ** 12)
        status, resp = service.route("POST", "/analyze", body, self.config)
        self.assertEqual(status, 400)

    def test_missing_price_series_400(self):
        body = dict(self.body)
        body["prices"] = {k: v for k, v in body["prices"].items() if k != "SPX"}
        status, resp = service.route("POST", "/risk", body, self.config)
        self.assertEqual(status, 400)
        self.assertIn("SPX", resp["detail"])

    def test_response_is_json_serializable(self):
        _, resp = service.route("POST", "/analyze",
                                dict(self.body, n_paths=300, horizon_days=2), self.config)
        json.dumps(resp)  # must not raise


if __name__ == "__main__":
    unittest.main()
