"""Compliance / investment-guideline engine.

Institutional mandates are expressed as rules (max single-name weight, sector
caps, asset-class floors/ceilings, cash minimums, leverage limits). The engine
evaluates a portfolio against a rule set and returns a pass/fail breach report —
the pre-trade and post-trade check that sits in front of every order in a
platform like this.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List

from .portfolio import Portfolio


@dataclass
class Breach:
    rule: str
    detail: str
    observed: float
    limit: float

    def __str__(self) -> str:
        return f"[BREACH] {self.rule}: {self.detail} (observed {self.observed:.4f}, limit {self.limit:.4f})"


@dataclass
class ComplianceResult:
    passed: bool
    breaches: List[Breach]

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "breaches": [b.__dict__ for b in self.breaches],
        }


Rule = Callable[[Portfolio], List[Breach]]

# Comparisons use a small tolerance so a position sitting exactly on its limit
# is not flagged as a breach by floating-point rounding.
_EPS = 1e-9


def max_position_weight(limit: float) -> Rule:
    def rule(pf: Portfolio) -> List[Breach]:
        out = []
        for sym, w in pf.weight_map().items():
            if abs(w) > limit + _EPS:
                out.append(Breach("max_position_weight",
                                  f"{sym} weight exceeds cap", abs(w), limit))
        return out
    return rule


def max_sector_weight(limit: float) -> Rule:
    def rule(pf: Portfolio) -> List[Breach]:
        base = pf.net_market_value
        out = []
        for sector, mv in pf.exposures_by("sector").items():
            w = abs(mv) / base if base else 0.0
            if w > limit + _EPS:
                out.append(Breach("max_sector_weight",
                                  f"sector '{sector}' exceeds cap", w, limit))
        return out
    return rule


def max_asset_class_weight(asset_class: str, limit: float) -> Rule:
    def rule(pf: Portfolio) -> List[Breach]:
        base = pf.net_market_value
        mv = pf.exposures_by("asset_class").get(asset_class, 0.0)
        w = abs(mv) / base if base else 0.0
        if w > limit + _EPS:
            return [Breach("max_asset_class_weight",
                           f"asset class '{asset_class}' exceeds cap", w, limit)]
        return []
    return rule


def min_cash_weight(limit: float) -> Rule:
    def rule(pf: Portfolio) -> List[Breach]:
        base = pf.net_market_value
        w = pf.cash / base if base else 0.0
        if w < limit - _EPS:
            return [Breach("min_cash_weight", "cash below floor", w, limit)]
        return []
    return rule


def max_leverage(limit: float) -> Rule:
    """Gross exposure / NAV must not exceed ``limit`` (1.0 == no leverage)."""
    def rule(pf: Portfolio) -> List[Breach]:
        base = pf.net_market_value
        lev = pf.gross_market_value / base if base else 0.0
        if lev > limit + _EPS:
            return [Breach("max_leverage", "gross leverage exceeds cap", lev, limit)]
        return []
    return rule


def evaluate(portfolio: Portfolio, rules: List[Rule]) -> ComplianceResult:
    breaches: List[Breach] = []
    for rule in rules:
        breaches.extend(rule(portfolio))
    return ComplianceResult(passed=not breaches, breaches=breaches)


def default_mandate() -> List[Rule]:
    """A conventional balanced-mandate rule set for demos."""
    return [
        max_position_weight(0.25),
        max_sector_weight(0.40),
        max_leverage(1.0),
    ]
