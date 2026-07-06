import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from atlas import dataio
from atlas.config import Config
from atlas.validation import ValidationError


class TestDataIO(unittest.TestCase):
    def test_load_prices_csv(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("date,AAA,BBB\n2020-01-01,100,50\n2020-01-02,101,49\n"
                     "2020-01-03,102,51\n2020-01-04,101,52\n")
            path = fh.name
        try:
            hist = dataio.load_prices_csv(path)
            self.assertEqual(hist.symbols, ["AAA", "BBB"])
            self.assertEqual(len(hist.prices["AAA"]), 4)
            self.assertEqual(hist.n_periods, 3)
        finally:
            os.unlink(path)

    def test_csv_rejects_non_numeric(self):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("date,AAA\n2020-01-01,100\n2020-01-02,oops\n2020-01-03,102\n")
            path = fh.name
        try:
            with self.assertRaises(ValidationError):
                dataio.load_prices_csv(path)
        finally:
            os.unlink(path)

    def test_load_portfolio_json_roundtrip(self):
        data = {
            "name": "T",
            "positions": [
                {"symbol": "AAA", "asset_class": "equity", "quantity": 10, "price": 100.0},
                {"symbol": "BBB", "asset_class": "bond", "quantity": 20, "price": 50.0},
            ],
            "prices": {
                "AAA": [100, 101, 102, 101, 103],
                "BBB": [50, 49, 51, 52, 50],
            },
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(data, fh)
            path = fh.name
        try:
            pf, hist = dataio.load_portfolio_json(path, Config())
            self.assertEqual(pf.symbols, ["AAA", "BBB"])
            self.assertEqual(hist.symbols, ["AAA", "BBB"])
            self.assertAlmostEqual(pf.total_value, 10 * 100.0 + 20 * 50.0)
        finally:
            os.unlink(path)

    def test_duplicate_symbol_rejected(self):
        from atlas.validation import parse_portfolio
        data = {"positions": [
            {"symbol": "AAA", "asset_class": "equity", "quantity": 1, "price": 1.0},
            {"symbol": "AAA", "asset_class": "equity", "quantity": 1, "price": 1.0},
        ]}
        with self.assertRaises(ValidationError):
            parse_portfolio(data, Config())


if __name__ == "__main__":
    unittest.main()
