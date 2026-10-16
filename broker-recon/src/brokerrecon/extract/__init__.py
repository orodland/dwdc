"""Format routing (fingerprinting) and extraction dispatch."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from ..config import BrokerConfig
from ..model import COMPLETENESS_FAIL, DocIssue, DocumentExtraction
from .csvx import extract_csv
from .pdf import extract_pdf
from .verify import verify_csv, verify_pdf, verify_xlsx
from .xlsx import extract_xlsx

_FORMAT_BY_SUFFIX = {".xlsx": "xlsx", ".pdf": "pdf", ".csv": "csv"}


def file_format(path: Path) -> str | None:
    return _FORMAT_BY_SUFFIX.get(path.suffix.lower())


def sample_text(path: Path, max_chars: int = 20000) -> str:
    """Text used for fingerprinting: first page / first rows only."""
    fmt = file_format(path)
    if fmt == "pdf":
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return (pdf.pages[0].extract_text() or "")[:max_chars] if pdf.pages else ""
    if fmt == "xlsx":
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            parts = []
            for ws in wb.worksheets:
                parts.append(ws.title)
                for row in ws.iter_rows(max_row=15, values_only=True):
                    parts.extend(str(v) for v in row if v is not None)
            return " | ".join(parts)[:max_chars]
        finally:
            wb.close()
    if fmt == "csv":
        return path.read_text(encoding="utf-8-sig")[:max_chars]
    return ""


def fingerprint(path: Path, configs: list[BrokerConfig]) -> list[BrokerConfig]:
    """All configs whose fingerprint matches this file (0, 1 or ambiguous many)."""
    fmt = file_format(path)
    text = None
    hits = []
    for cfg in configs:
        if cfg.format != fmt:
            continue
        fp = cfg.fingerprint
        if fp.filename_regex and not re.search(fp.filename_regex, path.name):
            continue
        if fp.must_contain:
            text = text if text is not None else sample_text(path)
            if not all(s in text for s in fp.must_contain):
                continue
        hits.append(cfg)
    return hits


def extract(path: Path, cfg: BrokerConfig, doc: DocumentExtraction) -> None:
    if cfg.format == "xlsx":
        extract_xlsx(path, cfg, doc)
        verify_xlsx(path, doc)
    elif cfg.format == "pdf":
        extract_pdf(path, cfg, doc)
        verify_pdf(path, doc)
    elif cfg.format == "csv":
        extract_csv(path, cfg, doc)
        verify_csv(path, doc)
    check_control_totals(doc)


def check_control_totals(doc: DocumentExtraction) -> None:
    """Reconcile extracted row counts / quantities to the document's own totals."""
    results = {}
    for name, ctl in doc.controls.get("tables", {}).items():
        footer = ctl.get("footer")
        res = {"rows_extracted": ctl["rows"], "quantity_extracted": str(ctl["quantity_sum"])}
        if not footer:
            res["status"] = "NO_CONTROL_TOTAL"
            doc.issues.append(DocIssue(COMPLETENESS_FAIL, f"[{name}] no control total found in document"))
        else:
            ok = True
            if footer.get("count") is not None:
                declared = int(footer["count"].replace(",", "").replace(".", "").replace("'", ""))
                res["rows_declared"] = declared
                if declared != ctl["rows"]:
                    ok = False
                    doc.issues.append(DocIssue(
                        COMPLETENESS_FAIL,
                        f"[{name}] document declares {declared} trades but {ctl['rows']} were extracted",
                        ctl.get("footer_loc", {}),
                    ))
            if footer.get("quantity") is not None:
                q_raw = footer["quantity"]
                # Control quantities are whole lots: strip grouping separators of any locale.
                declared_q = Decimal(re.sub(r"[^\d]", "", q_raw) or "0")
                res["quantity_declared"] = str(declared_q)
                if ctl["quantity_unparsed"]:
                    res["quantity_check"] = f"INCONCLUSIVE ({ctl['quantity_unparsed']} row quantities unparseable)"
                elif declared_q != ctl["quantity_sum"]:
                    ok = False
                    doc.issues.append(DocIssue(
                        COMPLETENESS_FAIL,
                        f"[{name}] document total quantity {declared_q} != extracted {ctl['quantity_sum']}",
                        ctl.get("footer_loc", {}),
                    ))
            res["status"] = "PASS" if ok else "FAIL"
        results[name] = res
    doc.controls["completeness"] = results
