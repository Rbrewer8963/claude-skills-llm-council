"""Command-line interface for ATLAS.

    python -m atlas demo                 # run the full engine on the demo book
    python -m atlas analyze book.json    # analyse a portfolio from JSON
    python -m atlas frontier             # print the demo efficient frontier

A portfolio JSON file looks like::

    {
      "name": "My Fund",
      "cash": 0,
      "positions": [
        {"symbol": "SPX", "name": "US Equity", "asset_class": "equity",
         "sector": "broad_equity", "quantity": 1000, "price": 450.0}
      ],
      "prices": {"SPX": [448.0, 449.1, 450.0, ...]}
    }
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import List

from . import optimize, report
from .engine import AtlasEngine
from .market import PriceHistory
from .portfolio import Asset, Portfolio, Position
from .samples import demo_history, demo_portfolio


def _load_portfolio(path: str) -> tuple[Portfolio, PriceHistory]:
    with open(path) as fh:
        data = json.load(fh)
    pf = Portfolio(name=data.get("name", "Portfolio"), cash=data.get("cash", 0.0))
    for p in data["positions"]:
        asset = Asset(p["symbol"], p.get("name", p["symbol"]),
                      p["asset_class"], p.get("sector", "n/a"),
                      p.get("currency", "USD"))
        pf.add(Position(asset, p["quantity"], p["price"]))
    prices = data["prices"]
    history = PriceHistory(symbols=pf.symbols, prices={s: prices[s] for s in pf.symbols})
    return pf, history


def _cmd_demo(args: argparse.Namespace) -> int:
    engine = AtlasEngine(demo_portfolio(), demo_history(), seed=args.seed)
    result = engine.run(mc_horizon_days=args.horizon, mc_paths=args.paths)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(report.render(result))
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    pf, history = _load_portfolio(args.file)
    engine = AtlasEngine(pf, history, seed=args.seed)
    result = engine.run(mc_horizon_days=args.horizon, mc_paths=args.paths)
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(report.render(result))
    return 0


def _cmd_frontier(args: argparse.Namespace) -> int:
    hist = demo_history()
    mu = hist.expected_returns()
    cov = hist.covariance()
    pts = optimize.efficient_frontier(mu, cov, n_points=args.points)
    print(f"{'Ann.Return':>12}{'Ann.Vol':>12}")
    for pt in pts:
        ann_ret = (1 + pt.target_return) ** 252 - 1
        ann_vol = pt.volatility * (252 ** 0.5)
        print(f"{ann_ret * 100:>11.2f}%{ann_vol * 100:>11.2f}%")
    mv = optimize.min_variance(cov)
    print("\nGlobal minimum-variance weights:")
    for sym, w in zip(hist.symbols, mv):
        print(f"  {sym:<6}{w * 100:>8.2f}%")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atlas",
                                description="ATLAS portfolio risk & analytics engine")
    sub = p.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--horizon", type=int, default=10, help="MC horizon in days")
    common.add_argument("--paths", type=int, default=10_000, help="MC path count")
    common.add_argument("--seed", type=int, default=42, help="RNG seed")
    common.add_argument("--json", action="store_true", help="emit JSON instead of a report")

    d = sub.add_parser("demo", parents=[common], help="run the engine on the demo book")
    d.set_defaults(func=_cmd_demo)

    a = sub.add_parser("analyze", parents=[common], help="analyse a portfolio JSON file")
    a.add_argument("file", help="path to portfolio JSON")
    a.set_defaults(func=_cmd_analyze)

    f = sub.add_parser("frontier", help="print the demo efficient frontier")
    f.add_argument("--points", type=int, default=15)
    f.set_defaults(func=_cmd_frontier)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
