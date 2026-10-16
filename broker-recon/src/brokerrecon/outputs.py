"""Standardised outputs: identical structure whatever the broker or format.

All files are written deterministically (sorted rows, fixed line endings, no
timestamps; the Excel workbook is re-zipped with fixed metadata) so that the
same inputs and configuration always produce byte-identical output files.
"""

from __future__ import annotations

import csv
import gzip
import datetime as dt
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable

from .hashing import canonical_json
from .model import ExceptionItem, Record

TRADE_COLUMNS = [
    "record_id", "origin", "broker_id", "status", "code", "match_group", "exception_id", "counterparts",
    "diff_fields", "product_type", "account", "exchange", "root", "contract_month", "put_call", "strike",
    "ccy_pair", "value_date", "side", "quantity", "price", "trade_date", "broker_ref", "aps_flag",
    "aps_group_id", "internal_id", "source_file", "source_location", "rule_detail",
]
EXCEPTION_COLUMNS = ["exception_id", "level", "code", "status", "broker_id", "record_ids", "diff_fields", "source_file", "detail"]


def source_location(r: Record) -> str:
    locs = []
    for v in r.raw.values():
        loc = v["loc"]
        if "page" in loc and "bbox" in loc and not loc.get("section_line"):
            locs.append(f"page {loc['page']}")
            break
        if "cell" in loc:
            locs.append(f"{loc['sheet']}!row {loc['cell'].lstrip('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}")
            break
        if "line" in loc:
            locs.append(f"line {loc['line']}")
            break
    return f"{r.source_file} :: {r.source_row}" + (f" ({locs[0]})" if locs else "")


def trade_row(r: Record) -> dict[str, Any]:
    d = r.canonical()
    d.update(
        record_id=r.record_id, origin=r.origin, broker_id=r.broker_id, status=r.status, code=r.code,
        match_group=r.match_group, exception_id=r.exception_id, counterparts=";".join(r.counterparts),
        diff_fields=";".join(r.diff_fields), source_file=r.source_file, source_location=source_location(r),
        rule_detail=r.rule_detail, aps_flag="Y" if r.aps_flag else "",
    )
    return {k: ("" if d.get(k) is None else d.get(k)) for k in TRADE_COLUMNS}


def exception_row(e: ExceptionItem) -> dict[str, Any]:
    return {
        "exception_id": e.exception_id, "level": e.level, "code": e.code, "status": e.status,
        "broker_id": e.broker_id, "record_ids": ";".join(e.record_ids), "diff_fields": ";".join(e.diff_fields),
        "source_file": e.source_file, "detail": e.detail,
    }


def write_csv(path: Path, columns: list[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_jsonl(path: Path, items: Iterable[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for it in items:
            fh.write(canonical_json(it) + "\n")


def write_jsonl_gz(path: Path, items: Iterable[Any]) -> None:
    """Gzipped JSONL with a fixed header (mtime=0, no filename) so bytes are reproducible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as gz:
        for it in items:
            gz.write((canonical_json(it) + "\n").encode("utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True, ensure_ascii=False, default=str)
        fh.write("\n")


def write_xlsx(path: Path, sheets: list[tuple[str, list[str], list[dict]]]) -> None:
    """Write a workbook, then re-zip with fixed timestamps/metadata for byte stability."""
    import openpyxl
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font

    wb = openpyxl.Workbook(write_only=True)
    bold = Font(bold=True)
    for title, cols, rows in sheets:
        ws = wb.create_sheet(title=title[:31])
        header = []
        for c in cols:
            cell = WriteOnlyCell(ws, value=c)
            cell.font = bold
            header.append(cell)
        ws.append(header)
        for row in rows:
            ws.append([row.get(c, "") for c in cols])
    fixed = dt.datetime(2000, 1, 1)
    wb.properties.created = fixed
    wb.properties.modified = fixed
    wb.properties.creator = "brokerrecon"
    wb.properties.lastModifiedBy = "brokerrecon"
    buf = io.BytesIO()
    wb.save(buf)
    src = zipfile.ZipFile(io.BytesIO(buf.getvalue()))
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for name in sorted(src.namelist()):
            data = src.read(name)
            if name == "docProps/core.xml":
                data = re.sub(rb"<dcterms:(created|modified)[^>]*>[^<]*</dcterms:\1>",
                              lambda m: m.group(0).split(b">")[0] + b">2000-01-01T00:00:00Z</dcterms:" + m.group(1) + b">", data)
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            dst.writestr(info, data)
