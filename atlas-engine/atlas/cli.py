"""Command-line interface for the ATLAS risk engine.

Examples
--------
    python -m atlas report                       # synthetic demo book
    python -m atlas report --portfolio book.json --prices prices.csv
    python -m atlas optimize --objective max-sharpe
    python -m atlas stress --portfolio book.json --prices prices.csv
    python -m atlas simulate --paths 100000 --horizon 10
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

from . import optimize
from .engine import RiskEngine
from .market import MarketData
from .portfolio import Portfolio
from .data import generate_market


def _load_market(args) -> MarketData:
    if getattr(args, "prices", None):
        return MarketData.from_csv(args.prices)
    instruments, dates, prices = generate_market(days=args.days, jump_prob=0.01, seed=args.seed)
    return MarketData.from_prices(instruments, dates, prices)


def _load_portfolio(args, market: MarketData) -> Portfolio:
    if getattr(args, "portfolio", None):
        with open(args.portfolio) as fh:
            spec = json.load(fh)
        nav = float(spec.get("nav", 1_000_000))
        name = spec.get("name", "Portfolio")
        if "weights" in spec:
            return Portfolio.from_weights(spec["weights"], nav=nav, name=name)
        return Portfolio(spec.get("positions", {}), cash=spec.get("cash", 0.0), name=name)
    # Default demo book.
    return Portfolio.from_weights(
        {"SPX": 0.30, "NDX": 0.12, "EFA": 0.10, "EEM": 0.06, "UST10": 0.18,
         "IG": 0.12, "HY": 0.06, "GOLD": 0.06},
        nav=100_000_000, name="Demo Multi-Asset Book",
    )


def _engine(args, market: MarketData) -> RiskEngine:
    return RiskEngine(market, confidence=args.confidence, horizon_days=args.horizon,
                      cov_method=args.cov, mc_paths=args.paths, mc_distribution=args.dist,
                      seed=args.seed)


def cmd_report(args) -> None:
    market = _load_market(args)
    book = _load_portfolio(args, market)
    unknown = book.unknown_symbols(market)
    if unknown:
        print(f"warning: positions not in market, ignored: {unknown}", file=sys.stderr)
    report = _engine(args, market).report(book)
    if args.json:
        print(json.dumps(_report_to_dict(report), indent=2))
    else:
        print(report.render())


def cmd_optimize(args) -> None:
    market = _load_market(args)
    mu = market.mean_returns(annualized=True)
    cov = market.cov(method=args.cov, annualized=True)
    syms = market.symbols
    objectives = {
        "min-variance": lambda: optimize.min_variance(syms, cov, mu=mu, rf=args.rf),
        "max-sharpe": lambda: optimize.max_sharpe(syms, mu, cov, rf=args.rf),
        "risk-parity": lambda: optimize.risk_parity(syms, cov, mu=mu, rf=args.rf),
    }
    chosen = objectives if args.objective == "all" else {args.objective: objectives[args.objective]}
    for name, fn in chosen.items():
        print(fn())


def cmd_stress(args) -> None:
    from .stress import run_stress_suite

    market = _load_market(args)
    book = _load_portfolio(args, market)
    print(f"Stress test — {book.name}  (NAV ${book.nav:,.0f})\n")
    for res in sorted(run_stress_suite(book, market), key=lambda s: s.pnl_pct):
        print(f"  {res}")


def cmd_simulate(args) -> None:
    from .montecarlo import simulate

    market = _load_market(args)
    book = _load_portfolio(args, market)
    sim = simulate(market.mean_returns(annualized=True),
                   market.cov(method=args.cov, annualized=True),
                   n_paths=args.paths, horizon_days=args.horizon,
                   annual_days=market.annual_days, distribution=args.dist, seed=args.seed)
    pnl = sim.portfolio_pnl(book.exposure_vector(market))
    qs = [1, 5, 50, 95, 99]
    print(f"Monte Carlo — {sim.n_paths:,} paths, {args.horizon}d horizon, dist={sim.distribution}\n")
    print(f"  mean P&L      ${pnl.mean():,.0f}")
    print(f"  std  P&L      ${pnl.std():,.0f}")
    for q in qs:
        print(f"  {q:>3d}th pctile ${np.percentile(pnl, q):,.0f}")


def build_parser() -> argparse.ArgumentParser:
    # Shared options live on a parent parser so they may be passed either before
    # or after the subcommand (e.g. ``atlas simulate --paths 100000``).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--portfolio", help="portfolio JSON (weights or positions + nav)")
    common.add_argument("--prices", help="wide price CSV (date, sym1, sym2, ...); default synthetic")
    common.add_argument("--confidence", type=float, default=0.99)
    common.add_argument("--horizon", type=int, default=1, help="risk horizon in trading days")
    common.add_argument("--cov", choices=["ewma", "sample"], default="ewma")
    common.add_argument("--dist", choices=["t", "normal"], default="t")
    common.add_argument("--paths", type=int, default=50_000)
    common.add_argument("--days", type=int, default=756, help="synthetic history length")
    common.add_argument("--rf", type=float, default=0.02)
    common.add_argument("--seed", type=int, default=42)
    common.add_argument("--json", action="store_true", help="emit machine-readable JSON (report only)")

    p = argparse.ArgumentParser(prog="atlas", description="ATLAS institutional risk engine",
                                parents=[common])
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("report", parents=[common], help="full risk report").set_defaults(func=cmd_report)
    opt = sub.add_parser("optimize", parents=[common], help="portfolio construction")
    opt.add_argument("--objective", choices=["min-variance", "max-sharpe", "risk-parity", "all"],
                     default="all")
    opt.set_defaults(func=cmd_optimize)
    sub.add_parser("stress", parents=[common], help="stress-test suite").set_defaults(func=cmd_stress)
    sub.add_parser("simulate", parents=[common],
                   help="Monte Carlo P&L distribution").set_defaults(func=cmd_simulate)
    return p


def _report_to_dict(report) -> dict:
    return {
        "portfolio": report.portfolio,
        "nav": report.nav,
        "gross_exposure": report.gross_exposure,
        "net_exposure": report.net_exposure,
        "leverage": report.leverage,
        "var": {k: {"var_dollar": v.var_dollar, "cvar_dollar": v.cvar_dollar,
                    "var_pct": v.var_pct, "cvar_pct": v.cvar_pct,
                    "confidence": v.confidence, "horizon_days": v.horizon_days}
                for k, v in report.var.items()},
        "top_contributors": [{"symbol": s, "component_var": c, "pct": p}
                             for s, c, p in report.contributions.top(8)],
        "factor_exposure": report.factor_exposure,
        "stress": [{"scenario": s.scenario, "pnl": s.pnl, "pnl_pct": s.pnl_pct}
                   for s in report.stress],
        "performance": report.performance.as_dict(),
        "warnings": report.warnings,
    }


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
