"""Service layer: pure request handling, independent of any web framework.

Each handler takes a decoded JSON body (a dict) and returns a
``(status_code, response_dict)`` tuple. :func:`route` dispatches by method and
path. Keeping this transport-agnostic means the same logic is exercised by unit
tests (calling ``route`` directly) and by the HTTP server, with no sockets in
the test path.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from . import __version__, optimize
from .config import Config
from .engine import AtlasEngine
from .validation import (
    ValidationError,
    parse_history,
    parse_portfolio,
    validate_sim_params,
)

Response = Tuple[int, Dict[str, Any]]


def _build_engine(body: Dict[str, Any], config: Config) -> AtlasEngine:
    pf = parse_portfolio(body, config)
    history = parse_history(body, pf.symbols, config)
    seed = int(body.get("seed", config.default_seed))
    return AtlasEngine(pf, history, seed=seed)


def handle_health() -> Response:
    return 200, {"status": "ok"}


def handle_version() -> Response:
    return 200, {"name": "atlas", "version": __version__}


def handle_analyze(body: Dict[str, Any], config: Config) -> Response:
    engine = _build_engine(body, config)
    horizon = body.get("horizon_days", 10)
    paths = body.get("n_paths", 10_000)
    with_sim = bool(body.get("with_simulation", True))
    if with_sim:
        horizon, paths = validate_sim_params(horizon, paths, config)
    result = engine.run(mc_horizon_days=horizon, mc_paths=paths,
                        with_simulation=with_sim)
    return 200, result.as_dict()


def handle_risk(body: Dict[str, Any], config: Config) -> Response:
    engine = _build_engine(body, config)
    return 200, engine.risk_report().as_dict()


def handle_stress(body: Dict[str, Any], config: Config) -> Response:
    engine = _build_engine(body, config)
    return 200, {"stress": [s.as_dict() for s in engine.stress_test()]}


def handle_optimize(body: Dict[str, Any], config: Config) -> Response:
    """Portfolio construction over a supplied price history.

    ``method`` selects the objective: min_variance | max_sharpe | risk_parity.
    """
    pf = parse_portfolio(body, config) if "positions" in body else None
    # Optimisation only needs the covariance/returns, which come from history.
    from .validation import _require
    _require("prices" in body, "optimize requires a 'prices' object")
    symbols = list(body["prices"].keys())
    history = parse_history(body, symbols, config)
    mu = history.expected_returns()
    cov = history.covariance()

    method = str(body.get("method", "min_variance"))
    if method == "min_variance":
        weights = optimize.min_variance(cov)
    elif method == "max_sharpe":
        weights = optimize.max_sharpe(mu, cov, risk_free=float(body.get("risk_free", 0.0)))
    elif method == "risk_parity":
        weights = optimize.risk_parity(cov)
    else:
        raise ValidationError(
            f"unknown optimize method '{method}'; "
            "expected one of min_variance, max_sharpe, risk_parity")

    from . import risk
    return 200, {
        "method": method,
        "symbols": symbols,
        "weights": dict(zip(symbols, weights)),
        "annualized_vol": risk.portfolio_volatility(weights, cov, annualize=True),
    }


def route(method: str, path: str, body: Dict[str, Any] | None,
          config: Config) -> Response:
    """Dispatch a request to its handler, mapping errors to clean responses."""
    body = body or {}
    try:
        if method == "GET" and path == "/health":
            return handle_health()
        if method == "GET" and path in ("/version", "/"):
            return handle_version()
        if method == "POST" and path == "/analyze":
            return handle_analyze(body, config)
        if method == "POST" and path == "/risk":
            return handle_risk(body, config)
        if method == "POST" and path == "/stress":
            return handle_stress(body, config)
        if method == "POST" and path == "/optimize":
            return handle_optimize(body, config)
        return 404, {"error": "not_found", "detail": f"no route for {method} {path}"}
    except ValidationError as exc:
        return 400, {"error": "validation_error", "detail": str(exc)}
    except ValueError as exc:
        # Domain errors (e.g. singular covariance) are client-fixable -> 400.
        return 400, {"error": "bad_request", "detail": str(exc)}
