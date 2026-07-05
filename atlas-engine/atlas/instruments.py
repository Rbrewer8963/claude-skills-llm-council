"""Instrument and asset-class definitions for the ATLAS risk engine.

An :class:`Instrument` is the atomic security ATLAS knows how to price, expose
to factors, and aggregate into portfolios. The model is intentionally light —
ATLAS operates at the *portfolio / market-risk* layer (like Aladdin), not the
sub-ledger accounting layer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AssetClass(str, Enum):
    """Top-level asset taxonomy used for exposure aggregation and stress mapping."""

    EQUITY = "equity"
    RATES = "rates"
    CREDIT = "credit"
    FX = "fx"
    COMMODITY = "commodity"
    ALTERNATIVE = "alternative"
    CASH = "cash"


@dataclass(frozen=True)
class Instrument:
    """A single tradable security.

    Parameters
    ----------
    symbol:
        Unique ticker / identifier.
    name:
        Human-readable description.
    asset_class:
        Member of :class:`AssetClass`.
    currency:
        ISO currency code the instrument settles in.
    sector, region:
        Optional classification tags used for exposure buckets.
    factor_betas:
        Optional a-priori factor sensitivities (e.g. ``{"rates": -6.5}`` for a
        bond's duration). When omitted, ATLAS estimates betas statistically
        from return history (see :mod:`atlas.factors`).
    """

    symbol: str
    name: str = ""
    asset_class: AssetClass = AssetClass.EQUITY
    currency: str = "USD"
    sector: str = "n/a"
    region: str = "n/a"
    factor_betas: dict[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("Instrument requires a non-empty symbol")
        # ``frozen`` dataclass: use object.__setattr__ to normalise.
        object.__setattr__(self, "symbol", self.symbol.upper())
        if isinstance(self.asset_class, str) and not isinstance(self.asset_class, AssetClass):
            object.__setattr__(self, "asset_class", AssetClass(self.asset_class))


def universe_from_symbols(symbols: list[str]) -> dict[str, Instrument]:
    """Build a minimal equity universe from bare symbols (useful for quick tests)."""
    return {s.upper(): Instrument(symbol=s) for s in symbols}
