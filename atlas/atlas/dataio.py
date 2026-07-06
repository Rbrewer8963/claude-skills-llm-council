"""Data ingestion adapters.

Turns real-world data files into the domain objects the engine consumes. Two
formats ship in:

* **portfolio JSON** — positions + aligned price history (see :mod:`atlas.cli`)
* **wide CSV** — a date column plus one price column per symbol

The CSV path is the seam where a live market-data feed would plug in: implement
the same ``symbols`` / ``prices`` contract from your source of truth and the
rest of the engine is unchanged.
"""

from __future__ import annotations

import csv
import json
from typing import Dict, List, Tuple

from .config import Config
from .market import PriceHistory
from .portfolio import Portfolio
from .validation import ValidationError, parse_history, parse_portfolio


def load_portfolio_json(path: str, config: Config | None = None) -> Tuple[Portfolio, PriceHistory]:
    config = config or Config()
    with open(path) as fh:
        data = json.load(fh)
    pf = parse_portfolio(data, config)
    history = parse_history(data, pf.symbols, config)
    return pf, history


def load_prices_csv(path: str, date_column: str = "date") -> PriceHistory:
    """Read a wide CSV (date + one column per symbol) into a PriceHistory.

    Rows are assumed chronological (oldest first). The date column is used only
    for ordering/labelling and is otherwise ignored by the risk math.
    """
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValidationError("CSV has no header row")
        symbols = [c for c in reader.fieldnames if c != date_column]
        if not symbols:
            raise ValidationError("CSV has no price columns besides the date column")
        prices: Dict[str, List[float]] = {s: [] for s in symbols}
        n_rows = 0
        for row in reader:
            n_rows += 1
            for s in symbols:
                cell = row.get(s, "")
                try:
                    val = float(cell)
                except (TypeError, ValueError):
                    raise ValidationError(
                        f"non-numeric price {cell!r} for '{s}' at row {n_rows}")
                if val <= 0:
                    raise ValidationError(f"non-positive price for '{s}' at row {n_rows}")
                prices[s].append(val)
    if n_rows < 3:
        raise ValidationError("need at least 3 price rows to estimate risk")
    return PriceHistory(symbols=symbols, prices=prices)
