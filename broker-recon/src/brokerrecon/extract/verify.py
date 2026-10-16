"""Independent second reads of every extracted cell ("grounding").

Each extracted value is re-read from its recorded source location by a
*different* parser than the one that extracted it:

* PDF  – primary extraction uses pdfplumber; verification uses PyMuPDF's word
  layer and the recorded bounding box.
* XLSX – primary extraction uses openpyxl; verification parses the workbook
  XML directly (sharedStrings + sheet XML) and reads the recorded cell address.

A disagreement marks the cell ``verified=False`` and the record becomes an
extraction uncertainty for human review; it is never silently corrected.
"""

from __future__ import annotations

import bisect
import datetime as dt
import re
import zipfile
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from ..model import DocumentExtraction

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_EXCEL_EPOCH = dt.date(1899, 12, 30)


def _norm_ws(s: str) -> str:
    return " ".join(s.split())


# --------------------------------------------------------------------------- PDF

def verify_pdf(path: Path, doc: DocumentExtraction) -> None:
    import pymupdf

    pad = 1.0
    with pymupdf.open(path) as pdf:
        page_words: dict[int, tuple[list[float], list[tuple]]] = {}

        def words_for(pno: int):
            if pno not in page_words:
                ws = []
                for x0, y0, x1, y1, text, *_ in pdf[pno - 1].get_text("words"):
                    ws.append(((y0 + y1) / 2, (x0 + x1) / 2, x0, text))
                ws.sort()
                page_words[pno] = ([w[0] for w in ws], ws)
            return page_words[pno]

        for row in doc.rows:
            for cell in row.cells.values():
                loc = cell.loc
                if "bbox" not in loc:
                    continue
                x0, top, x1, bottom = loc["bbox"]
                ys, ws = words_for(loc["page"])
                lo = bisect.bisect_left(ys, top - pad)
                hi = bisect.bisect_right(ys, bottom + pad)
                found = sorted((w for w in ws[lo:hi] if x0 - pad <= w[1] <= x1 + pad), key=lambda w: w[2])
                reread = _norm_ws(" ".join(w[3] for w in found))
                source_text = loc.get("source_text", cell.raw)
                cell.verified = reread == _norm_ws(source_text)
                if not cell.verified:
                    cell.loc["reread"] = reread


# -------------------------------------------------------------------------- XLSX

def _sheet_paths(zf: zipfile.ZipFile) -> dict[str, str]:
    wb = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    targets = {r.get("Id"): r.get("Target") for r in rels.iter(f"{_REL_NS}Relationship")}
    out = {}
    for s in wb.iter(f"{{{_NS['m']}}}sheet"):
        rid = s.get(f"{{{_NS['r']}}}id")
        target = targets[rid].lstrip("/")
        out[s.get("name")] = target if target.startswith("xl/") else f"xl/{target}"
    return out


def _shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    out = []
    for si in root.iter(f"{{{_NS['m']}}}si"):
        out.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
    return out


def _read_sheet_cells(zf: zipfile.ZipFile, part: str, wanted: set[str], sst: list[str]) -> dict[str, tuple[str, str]]:
    """Return {address: (cell type attr, raw text)} for wanted addresses."""
    found: dict[str, tuple[str, str]] = {}
    m = _NS["m"]
    with zf.open(part) as fh:
        for _event, el in ET.iterparse(fh):
            if el.tag != f"{{{m}}}c":
                continue
            addr = el.get("r")
            if addr in wanted:
                t = el.get("t", "n")
                if t == "inlineStr":
                    text = "".join(x.text or "" for x in el.iter(f"{{{m}}}t"))
                else:
                    v = el.find(f"{{{m}}}v")
                    text = v.text if v is not None and v.text is not None else ""
                    if t == "s" and text:
                        text = sst[int(text)]
                found[addr] = (t, text)
            el.clear()
    return found


def _xml_value_as_text(t: str, text: str, expected_type: str) -> str:
    if t in ("s", "inlineStr", "str"):
        return text.strip()
    if t == "b":
        return "TRUE" if text == "1" else "FALSE"
    if text == "":
        return ""
    if expected_type == "date":
        serial = Decimal(text)
        return (_EXCEL_EPOCH + dt.timedelta(days=int(serial))).isoformat()
    num = Decimal(text)
    return format(num, "f") if "." in text or "E" in text.upper() else str(int(num))


def verify_xlsx(path: Path, doc: DocumentExtraction) -> None:
    with zipfile.ZipFile(path) as zf:
        sheets = _sheet_paths(zf)
        sst = _shared_strings(zf)
        wanted: dict[str, set[str]] = {}
        for row in doc.rows:
            for cell in row.cells.values():
                if "cell" in cell.loc:
                    wanted.setdefault(cell.loc["sheet"], set()).add(cell.loc["cell"])
        values = {s: _read_sheet_cells(zf, sheets[s], addrs, sst) for s, addrs in wanted.items() if s in sheets}
    for row in doc.rows:
        for cell in row.cells.values():
            loc = cell.loc
            if "cell" not in loc:
                continue
            t, text = values.get(loc["sheet"], {}).get(loc["cell"], ("n", ""))
            source_text = loc.get("source_text", cell.raw)
            reread = _xml_value_as_text(t, text, loc.get("type", "text"))
            if loc.get("type") == "number" and reread:
                # Spreadsheet numbers are IEEE doubles; the XML may spell the same double
                # with more digits than the shortest round-trip form, so compare as doubles.
                cell.verified = float(reread) == float(source_text)
            else:
                cell.verified = reread == source_text
            if not cell.verified:
                cell.loc["reread"] = reread


def verify_csv(path: Path, doc: DocumentExtraction) -> None:
    """Re-read each recorded line from the raw bytes and check the value is present."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    for row in doc.rows:
        for cell in row.cells.values():
            loc = cell.loc
            if "line" not in loc:
                continue
            source_text = loc.get("source_text", cell.raw)
            text = lines[loc["line"] - 1] if loc["line"] - 1 < len(lines) else ""
            fields = [f.strip().strip('"') for f in re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', text)]
            cell.verified = loc["col_index"] < len(fields) and fields[loc["col_index"]] == source_text
