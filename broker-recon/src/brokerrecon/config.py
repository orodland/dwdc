"""Broker format configurations ("templates") and their approval control.

A config describes how one broker's statement layout maps to the canonical
trade schema. Configs are data, kept in version control, and are only usable
by the engine once a named person has approved them: approval stores a hash
of the config body, so any later edit silently invalidates the approval and
the engine refuses the config (CONFIG_NOT_APPROVED).
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .hashing import sha256_obj

CANONICAL_FIELDS = (
    "broker_ref",
    "account",
    "exchange",
    "instrument_code",
    "contract_month",
    "put_call",
    "strike",
    "ccy_pair",
    "value_date",
    "side",
    "quantity",
    "price",
    "trade_date",
    "aps_flag",
    # internal-list-only fields
    "internal_id",
    "broker_id",
    "aps_group_id",
    "product_type",
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Fingerprint(_Strict):
    filename_regex: str | None = None
    must_contain: list[str] = Field(default_factory=list)


class ColumnSplit(_Strict):
    column: str  # source header label
    regex: str  # named groups are canonical field names


class ProductTypeRule(_Strict):
    constant: str | None = None
    column: str | None = None  # source header label
    map: dict[str, str] = Field(default_factory=dict)
    opt_if_present: str | None = None  # canonical field; OPT when non-empty, else FUT


class TotalsRule(_Strict):
    regex: str  # named groups: count, quantity
    quantity_abs: bool = True


class TableConfig(_Strict):
    name: str
    sheet: str | None = None
    header: list[str]
    columns: dict[str, str]  # canonical field -> header label
    splits: list[ColumnSplit] = Field(default_factory=list)
    constants: dict[str, str] = Field(default_factory=dict)
    product_type: ProductTypeRule
    end_patterns: list[str] = Field(default_factory=list)
    skip_patterns: list[str] = Field(default_factory=list)
    section_patterns: list[str] = Field(default_factory=list)
    totals: list[TotalsRule] = Field(default_factory=list)
    row_ref_pattern: str | None = None  # a trade row must carry a reference matching this
    format_overrides: dict = Field(default_factory=dict)  # table-specific Formats fields


class PagePatterns(_Strict):
    page_number: str | None = None  # regex with groups n, m
    ignore: list[str] = Field(default_factory=list)


class Formats(_Strict):
    date: str = "%Y-%m-%d"
    decimal_separator: Literal[".", ","] = "."
    thousands_separator: Literal["", ",", ".", " ", "'"] = ","
    contract_month: Literal["MONYY", "MON-YYYY", "MONYYYY", "YYYY-MM", "CODE_Y1", "CODE_Y2"] = "YYYY-MM"
    side_map: dict[str, str] = Field(default_factory=dict)
    signed_quantity: bool = False
    put_call_map: dict[str, str] = Field(default_factory=lambda: {"C": "C", "P": "P"})
    price_format: dict[str, Literal["decimal", "eighths_apostrophe"]] = Field(default_factory=dict)
    price_unit: dict[str, Literal["dollars", "cents", "units"]] = Field(default_factory=dict)
    aps_true_values: list[str] = Field(default_factory=list)


class Approval(_Strict):
    approved_by: str
    approved_on: str
    body_sha256: str


class BrokerConfig(_Strict):
    config_id: str
    broker_id: str
    broker_name: str
    version: int
    status: Literal["approved", "proposed"]
    format: Literal["xlsx", "pdf", "csv"]
    fingerprint: Fingerprint
    page_patterns: PagePatterns = Field(default_factory=PagePatterns)
    tables: list[TableConfig]
    formats: Formats = Field(default_factory=Formats)
    symbology: dict[str, str] = Field(default_factory=dict)
    approval: Approval | None = None
    proposal: dict | None = None

    def body(self) -> dict:
        d = self.model_dump(mode="json")
        for k in ("approval", "status", "proposal"):
            d.pop(k, None)
        return d

    def body_sha256(self) -> str:
        return sha256_obj(self.body())

    def approval_problem(self) -> str | None:
        if self.status != "approved" or self.approval is None:
            return "config has not been approved"
        if self.approval.body_sha256 != self.body_sha256():
            return "config body changed after approval (hash mismatch)"
        return None


def load_config(path: Path) -> BrokerConfig:
    with open(path, encoding="utf-8") as fh:
        return BrokerConfig.model_validate(yaml.safe_load(fh))


def save_config(cfg: BrokerConfig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg.model_dump(mode="json", exclude_none=True), fh, sort_keys=False, allow_unicode=True)


def approve(cfg: BrokerConfig, approver: str, on: str | None = None) -> BrokerConfig:
    on = on or dt.date.today().isoformat()
    cfg = cfg.model_copy(deep=True)
    cfg.status = "approved"
    cfg.approval = Approval(approved_by=approver, approved_on=on, body_sha256=cfg.body_sha256())
    return cfg


def load_broker_configs(config_dir: Path) -> list[tuple[Path, BrokerConfig]]:
    """All configs directly in config/brokers (proposals live in a subfolder)."""
    out = []
    for p in sorted((config_dir / "brokers").glob("*.yaml")):
        out.append((p, load_config(p)))
    return out


def load_internal_config(config_dir: Path) -> BrokerConfig:
    return load_config(config_dir / "internal.yaml")
