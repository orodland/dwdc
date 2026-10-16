"""Shared helpers for format-specific extractors.

Extractors never interpret values: they locate each cell, copy its text
verbatim (``raw``) and record where it came from (``loc``). Interpretation is
the job of the normalisation stage.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from ..config import BrokerConfig, TableConfig
from ..model import Cell, ExtractedRow


def compile_all(patterns: list[str]) -> list[re.Pattern]:
    return [re.compile(p) for p in patterns]


def build_row(
    row_id: str,
    table: TableConfig,
    by_label: dict[str, Cell],
    context: dict[str, Cell],
    row_loc: dict[str, Any],
) -> ExtractedRow:
    """Map header-labelled cells onto canonical field names."""
    cells: dict[str, Cell] = {}
    for fld, cell in context.items():
        cells[fld] = cell
    for fld, label in table.columns.items():
        if label in by_label:
            cells[fld] = by_label[label]
    for split in table.splits:
        src = by_label.get(split.column)
        if src is None:
            continue
        m = re.match(split.regex, src.raw.strip())
        for name in re.compile(split.regex).groupindex:
            value = m.group(name) if m else ""
            loc = dict(src.loc, split_of=split.column, split_rule=split.regex, source_text=src.raw)
            cells[name] = Cell(raw=value or "", loc=loc, verified=src.verified)
            if not m:
                cells[name].loc["split_failed"] = True
    for fld, value in table.constants.items():
        cells[fld] = Cell(raw=value, loc={"rule": "constant"})
    pt = table.product_type
    if pt.constant:
        cells["product_type"] = Cell(raw=pt.constant, loc={"rule": "constant"})
    elif pt.column and pt.column in by_label:
        cells["product_type"] = by_label[pt.column]
    return ExtractedRow(row_id=row_id, table=table.name, cells=cells, row_loc=row_loc)


def parse_control_number(raw: str, cfg: BrokerConfig) -> Decimal | None:
    """Lenient-but-exact number parse used only for document control totals."""
    from ..normalize import parse_number, NormError

    try:
        return parse_number(raw, cfg.formats, typed_number=False)
    except NormError:
        return None


def is_ref_ok(table: TableConfig, raw_ref: str) -> bool:
    if not raw_ref.strip():
        return False
    if table.row_ref_pattern and not re.fullmatch(table.row_ref_pattern, raw_ref.strip()):
        return False
    return True
