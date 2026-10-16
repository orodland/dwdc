"""Versioned instrument reference data."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import yaml

from .hashing import sha256_file


@dataclass(frozen=True)
class Instrument:
    root: str
    name: str
    exchange: str
    exchange_aliases: tuple[str, ...]
    quote_unit: str  # "cents" or "units"
    currency: str
    multiplier: int
    tick: Decimal
    aps_price_decimals: int
    product_types: tuple[str, ...]


@dataclass(frozen=True)
class Reference:
    version: str
    sha256: str
    instruments: dict[str, Instrument]
    currencies: frozenset[str]


def load_reference(config_dir: Path) -> Reference:
    path = config_dir / "reference" / "instruments.yaml"
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    instruments = {}
    for root, d in raw["instruments"].items():
        instruments[root] = Instrument(
            root=root,
            name=d["name"],
            exchange=d["exchange"],
            exchange_aliases=tuple(d["exchange_aliases"]),
            quote_unit=d["quote_unit"],
            currency=d["currency"],
            multiplier=int(d["multiplier"]),
            tick=Decimal(str(d["tick"])),
            aps_price_decimals=int(d["aps_price_decimals"]),
            product_types=tuple(d["product_types"]),
        )
    return Reference(
        version=str(raw["version"]),
        sha256=sha256_file(path),
        instruments=instruments,
        currencies=frozenset(raw["currencies"]),
    )
