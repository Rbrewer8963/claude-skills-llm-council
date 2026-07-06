"""Input validation for the API / data boundary.

Every externally-supplied payload passes through here before it reaches the
engine, so the analytics code can assume well-formed inputs. Failures raise
:class:`ValidationError`, which the server maps to a 400 with a clear message —
never a 500 stack trace.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .config import Config
from .market import PriceHistory
from .portfolio import Asset, Portfolio, Position


class ValidationError(ValueError):
    """Raised when a client-supplied payload is malformed or violates a limit."""


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValidationError(msg)


def _num(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"'{field}' must be a number, got {type(value).__name__}")
    f = float(value)
    if f != f or f in (float("inf"), float("-inf")):
        raise ValidationError(f"'{field}' must be finite")
    return f


def parse_portfolio(data: Dict[str, Any], config: Config) -> Portfolio:
    _require(isinstance(data, dict), "payload must be a JSON object")
    positions = data.get("positions")
    _require(isinstance(positions, list) and positions, "'positions' must be a non-empty list")
    _require(len(positions) <= config.max_positions,
             f"too many positions ({len(positions)} > {config.max_positions})")

    pf = Portfolio(name=str(data.get("name", "Portfolio")),
                   cash=_num(data.get("cash", 0.0), "cash"))
    seen = set()
    for i, p in enumerate(positions):
        _require(isinstance(p, dict), f"positions[{i}] must be an object")
        for key in ("symbol", "asset_class", "quantity", "price"):
            _require(key in p, f"positions[{i}] missing required field '{key}'")
        symbol = str(p["symbol"])
        _require(symbol not in seen, f"duplicate symbol '{symbol}'")
        seen.add(symbol)
        asset = Asset(
            symbol=symbol,
            name=str(p.get("name", symbol)),
            asset_class=str(p["asset_class"]),
            sector=str(p.get("sector", "n/a")),
            currency=str(p.get("currency", "USD")),
        )
        qty = _num(p["quantity"], f"positions[{i}].quantity")
        price = _num(p["price"], f"positions[{i}].price")
        _require(price >= 0, f"positions[{i}].price must be non-negative")
        pf.add(Position(asset, qty, price))
    return pf


def parse_history(data: Dict[str, Any], symbols: List[str], config: Config) -> PriceHistory:
    prices = data.get("prices")
    _require(isinstance(prices, dict), "'prices' must be an object mapping symbol -> price list")
    series: Dict[str, List[float]] = {}
    length = None
    for sym in symbols:
        _require(sym in prices, f"'prices' missing series for symbol '{sym}'")
        raw = prices[sym]
        _require(isinstance(raw, list), f"prices['{sym}'] must be a list")
        _require(len(raw) >= 3, f"prices['{sym}'] needs at least 3 points to estimate risk")
        _require(len(raw) <= config.max_history_points,
                 f"prices['{sym}'] too long ({len(raw)} > {config.max_history_points})")
        if length is None:
            length = len(raw)
        _require(len(raw) == length, "all price series must have equal length")
        vals = [_num(x, f"prices['{sym}'][]") for x in raw]
        _require(all(v > 0 for v in vals), f"prices['{sym}'] must be strictly positive")
        series[sym] = vals
    return PriceHistory(symbols=list(symbols), prices=series)


def validate_sim_params(horizon_days: Any, n_paths: Any, config: Config) -> tuple[int, int]:
    h = int(horizon_days)
    n = int(n_paths)
    _require(1 <= h <= config.max_horizon_days,
             f"horizon_days must be in [1, {config.max_horizon_days}]")
    _require(1 <= n <= config.max_paths,
             f"n_paths must be in [1, {config.max_paths}]")
    return h, n
