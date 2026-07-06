"""Runtime configuration, sourced from environment variables with safe defaults.

Twelve-factor style: everything that varies between environments (host, port,
limits, log level) is read from the environment so the same artifact runs in
dev, staging and prod without code changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"environment variable {name}={raw!r} is not an integer")


@dataclass(frozen=True)
class Config:
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"
    log_format: str = "json"           # "json" or "text"
    # Guardrails so a single request cannot exhaust the box.
    max_paths: int = 200_000           # cap on Monte-Carlo paths per request
    max_horizon_days: int = 3_650      # cap on simulation horizon
    max_positions: int = 5_000         # cap on portfolio size
    max_history_points: int = 20_000   # cap on price-series length
    max_body_bytes: int = 25_000_000   # request-body size limit (~25 MB)
    default_seed: int = 42

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            host=os.environ.get("ATLAS_HOST", cls.host),
            port=_int("ATLAS_PORT", cls.port),
            log_level=os.environ.get("ATLAS_LOG_LEVEL", cls.log_level).upper(),
            log_format=os.environ.get("ATLAS_LOG_FORMAT", cls.log_format).lower(),
            max_paths=_int("ATLAS_MAX_PATHS", cls.max_paths),
            max_horizon_days=_int("ATLAS_MAX_HORIZON_DAYS", cls.max_horizon_days),
            max_positions=_int("ATLAS_MAX_POSITIONS", cls.max_positions),
            max_history_points=_int("ATLAS_MAX_HISTORY_POINTS", cls.max_history_points),
            max_body_bytes=_int("ATLAS_MAX_BODY_BYTES", cls.max_body_bytes),
            default_seed=_int("ATLAS_DEFAULT_SEED", cls.default_seed),
        )
