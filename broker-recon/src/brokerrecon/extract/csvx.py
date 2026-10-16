"""Deterministic CSV extraction."""

from __future__ import annotations

import csv
import re
from decimal import Decimal
from pathlib import Path

from ..config import BrokerConfig
from ..model import Cell, DocIssue, DocumentExtraction, UNCLASSIFIED_CONTENT
from .common import build_row, compile_all, is_ref_ok, parse_control_number


def extract_csv(path: Path, cfg: BrokerConfig, doc: DocumentExtraction) -> None:
    table = cfg.tables[0]
    end_re = compile_all(table.end_patterns)
    skip_re = compile_all(table.skip_patterns)
    totals_re = [(t, re.compile(t.regex)) for t in table.totals]
    ctl = {"rows": 0, "quantity_sum": Decimal(0), "quantity_unparsed": 0, "footer": None}
    header: dict[str, int] | None = None
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for line_no, fields in enumerate(csv.reader(fh), start=1):
            fields = [f.strip() for f in fields]
            if header is None:
                if all(lbl in fields for lbl in table.header):
                    header = {lbl: fields.index(lbl) for lbl in table.header}
                continue
            if not any(fields):
                continue
            text = " ".join(f for f in fields if f)
            tot = [(r, m) for r, p in totals_re if (m := p.search(text))]
            if tot:
                ctl["footer"] = tot[0][1].groupdict()
                ctl["footer_loc"] = {"line": line_no}
                ctl["quantity_abs"] = tot[0][0].quantity_abs
            if any(r.search(text) for r in end_re):
                break
            if tot or any(r.search(text) for r in skip_re):
                continue
            by_label = {
                lbl: Cell(raw=fields[i] if i < len(fields) else "",
                          loc={"line": line_no, "column": lbl, "col_index": i, "type": "text"})
                for lbl, i in header.items()
            }
            ref_label = table.columns.get("broker_ref")
            if ref_label and not is_ref_ok(table, by_label[ref_label].raw):
                doc.issues.append(DocIssue(UNCLASSIFIED_CONTENT, f"row not recognised as a trade: {text[:120]}", {"line": line_no}))
                continue
            er = build_row(f"line{line_no}", table, by_label, {}, {"line": line_no})
            doc.rows.append(er)
            ctl["rows"] += 1
            q = er.cells.get("quantity")
            if q is not None:
                v = parse_control_number(q.raw, cfg)
                if v is None:
                    ctl["quantity_unparsed"] += 1
                else:
                    ctl["quantity_sum"] += abs(v)
    if header is None:
        doc.issues.append(DocIssue(UNCLASSIFIED_CONTENT, "header row not found"))
    doc.controls["tables"] = {table.name: ctl}
    doc.controls["rows_extracted"] = ctl["rows"]
