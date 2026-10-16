"""Deterministic extraction from native (text-layer) PDF statements.

Layout handling is template-driven: the broker config names the header
labels; column boundaries are derived from where those labels sit on each
page, and every word is assigned to a column by its horizontal centre.

Completeness control: *every* text line on every page must be classified by
the config (page furniture, header, section, total, skip, or trade row).
Anything else becomes an UNCLASSIFIED_CONTENT issue instead of being dropped.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pdfplumber

from ..config import BrokerConfig, TableConfig
from ..model import Cell, COMPLETENESS_FAIL, DocIssue, DocumentExtraction, UNCLASSIFIED_CONTENT
from .common import build_row, compile_all, is_ref_ok, parse_control_number


def _group_lines(words: list[dict], tol: float = 2.0) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if lines and abs(lines[-1][0]["top"] - w["top"]) <= tol:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _header_spans(line: list[dict], labels: list[str]) -> list[tuple[float, float]] | None:
    """Locate each header label (possibly multi-word) in order; return x-spans."""
    texts = [w["text"] for w in line]
    spans = []
    i = 0
    for label in labels:
        parts = label.split()
        found = False
        while i + len(parts) <= len(texts):
            if texts[i:i + len(parts)] == parts:
                spans.append((line[i]["x0"], line[i + len(parts) - 1]["x1"]))
                i += len(parts)
                found = True
                break
            i += 1
        if not found:
            return None
    return spans


def _boundaries(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    bounds = []
    for k, (x0, x1) in enumerate(spans):
        left = -1e9 if k == 0 else (spans[k - 1][1] + x0) / 2
        right = 1e9 if k == len(spans) - 1 else (x1 + spans[k + 1][0]) / 2
        bounds.append((left, right))
    return bounds


def extract_pdf(path: Path, cfg: BrokerConfig, doc: DocumentExtraction) -> None:
    page_re = re.compile(cfg.page_patterns.page_number) if cfg.page_patterns.page_number else None
    ignore_re = compile_all(cfg.page_patterns.ignore)
    tables = cfg.tables
    t_rx = {
        t.name: {
            "end": compile_all(t.end_patterns),
            "skip": compile_all(t.skip_patterns),
            "section": compile_all(t.section_patterns),
            "totals": [(r, re.compile(r.regex)) for r in t.totals],
        }
        for t in tables
    }
    active: TableConfig | None = None
    bounds: list[tuple[float, float]] | None = None
    context: dict[str, Cell] = {}
    pages_declared: set[int] = set()
    page_total: int | None = None
    ctl = {"rows": 0, "quantity_sum": Decimal(0), "quantity_unparsed": 0, "footer": None}

    with pdfplumber.open(path) as pdf:
        doc.controls["pages_in_file"] = len(pdf.pages)
        for pno, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False)
            for l_idx, line in enumerate(_group_lines(words), start=1):
                text = " ".join(w["text"] for w in line)
                loc_line = {"page": pno, "line": l_idx}
                if page_re and (m := page_re.search(text)):
                    pages_declared.add(int(m.group("n")))
                    page_total = int(m.group("m"))
                    continue
                if any(rx.search(text) for rx in ignore_re):
                    continue
                header_hit = False
                for t in tables:
                    spans = _header_spans(line, t.header)
                    if spans:
                        active, bounds, header_hit = t, _boundaries(spans), True
                        break
                if header_hit:
                    continue
                rx = t_rx[active.name] if active else None
                if rx is None:
                    # Before the first header: only section lines are allowed.
                    sec = next((m for t in tables for r in t_rx[t.name]["section"] if (m := r.search(text))), None)
                    if sec:
                        context = _context_from(sec, line, pno)
                        continue
                    doc.issues.append(DocIssue(UNCLASSIFIED_CONTENT, f"unrecognised text: {text[:120]}", loc_line))
                    continue
                sec = next((m for r in rx["section"] if (m := r.search(text))), None)
                if sec:
                    context = _context_from(sec, line, pno)
                    continue
                tot = [(r, m) for r, p in rx["totals"] if (m := p.search(text))]
                if tot:
                    rule, m = tot[0]
                    ctl["footer"] = m.groupdict()
                    ctl["footer_loc"] = loc_line
                    ctl["quantity_abs"] = rule.quantity_abs
                    continue
                if any(r.search(text) for r in rx["end"]):
                    active, bounds = None, None
                    continue
                if any(r.search(text) for r in rx["skip"]):
                    continue
                by_label = _cells_for_line(line, active.header, bounds, pno)
                ref_label = active.columns.get("broker_ref")
                if not ref_label or not is_ref_ok(active, by_label[ref_label].raw):
                    doc.issues.append(DocIssue(UNCLASSIFIED_CONTENT, f"line not recognised as a trade: {text[:120]}", loc_line))
                    continue
                row_id = f"p{pno}-l{l_idx}"
                er = build_row(row_id, active, by_label, context, dict(loc_line, text=text))
                doc.rows.append(er)
                ctl["rows"] += 1
                qcell = er.cells.get("quantity")
                if qcell is not None:
                    q = parse_control_number(qcell.raw, cfg)
                    if q is None:
                        ctl["quantity_unparsed"] += 1
                    else:
                        ctl["quantity_sum"] += abs(q)

    doc.controls["tables"] = {tables[0].name if len(tables) == 1 else "all": ctl}
    doc.controls["rows_extracted"] = ctl["rows"]
    doc.controls["pages_declared_total"] = page_total
    doc.controls["pages_declared_seen"] = sorted(pages_declared)
    if page_re is not None:
        n_file = doc.controls["pages_in_file"]
        if page_total is None:
            doc.issues.append(DocIssue(COMPLETENESS_FAIL, "no 'page n of m' markers found"))
        elif page_total != n_file or sorted(pages_declared) != list(range(1, page_total + 1)):
            doc.issues.append(DocIssue(
                COMPLETENESS_FAIL,
                f"page sequence incomplete: file has {n_file} pages, document declares {page_total}, "
                f"markers seen {sorted(pages_declared)[:10]}...",
            ))


def _context_from(m: re.Match, line: list[dict], pno: int) -> dict[str, Cell]:
    bbox = [min(w["x0"] for w in line), min(w["top"] for w in line),
            max(w["x1"] for w in line), max(w["bottom"] for w in line)]
    return {
        k: Cell(raw=v, loc={"page": pno, "bbox": [round(b, 2) for b in bbox], "section_line": True,
                            "source_text": " ".join(w["text"] for w in line)})
        for k, v in m.groupdict().items() if v is not None
    }


def _cells_for_line(line, labels, bounds, pno) -> dict[str, Cell]:
    buckets: dict[int, list[dict]] = {i: [] for i in range(len(labels))}
    for w in line:
        cx = (w["x0"] + w["x1"]) / 2
        for i, (lo, hi) in enumerate(bounds):
            if lo <= cx < hi:
                buckets[i].append(w)
                break
    out = {}
    for i, label in enumerate(labels):
        ws = buckets[i]
        if ws:
            bbox = [round(min(w["x0"] for w in ws), 2), round(min(w["top"] for w in ws), 2),
                    round(max(w["x1"] for w in ws), 2), round(max(w["bottom"] for w in ws), 2)]
            out[label] = Cell(raw=" ".join(w["text"] for w in ws), loc={"page": pno, "bbox": bbox, "type": "text"})
        else:
            out[label] = Cell(raw="", loc={"page": pno, "empty_column": label, "type": "text"})
    return out
