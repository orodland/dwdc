"""Onboarding an unrecognised broker layout: AI (or a heuristic) *proposes* a
template; a person reviews and approves it; only then does the deterministic
engine use it.

The proposal is self-tested before it is written: the engine dry-runs the
proposed template over the very file it was built from and records how many
rows were extracted, whether control totals agree and which issues arose, so
the approver sees evidence rather than a bare mapping.

Data minimisation for the AI path: only the header row and a handful of
sample rows are sent, and values in reference/account columns are
pseudonymised (shape preserved) unless --no-mask is given.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
from collections import Counter
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .config import BrokerConfig, Fingerprint, Formats, ProductTypeRule, TableConfig, TotalsRule, save_config
from .hashing import canonical_json, sha256_file, sha256_text
from .model import DocumentExtraction
from .reference import load_reference

AI_MODEL = "claude-opus-5-5"

SYNONYMS = {
    "broker_ref": ["trade ref", "ticket", "deal no", "execid", "exec id", "reference", "ref", "trade id", "confirmation no"],
    "account": ["account", "acct", "client account", "account no", "a/c"],
    "exchange": ["exch", "exchange", "venue", "mic"],
    "instrument_code": ["contract", "product code", "symbol", "product", "instrument", "commodity", "ticker"],
    "contract_month": ["mth", "month", "contract month", "expiry", "delivery month", "prompt"],
    "put_call": ["p/c", "call/put", "put/call", "option type", "cp"],
    "strike": ["strike", "strike px", "strike price"],
    "side": ["b/s", "side", "buy/sell", "direction"],
    "quantity": ["lots", "qty", "quantity", "size", "contracts", "notional", "base amount"],
    "price": ["price", "trade price", "px", "fwd rate", "forward rate", "rate", "exec price"],
    "trade_date": ["trade date", "trade dt", "exec date", "execution date"],
    "value_date": ["value date", "value dt", "settlement date"],
    "ccy_pair": ["pair", "currency pair", "ccy pair"],
}
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%d-%b-%Y", "%Y%m%d"]
SIDE_WORDS = {"B": "BUY", "BUY": "BUY", "BOUGHT": "BUY", "LONG": "BUY", "S": "SELL", "SELL": "SELL", "SOLD": "SELL", "SHORT": "SELL"}


# ------------------------------------------------------------------ reading
def _read_table(path: Path) -> tuple[str | None, list[list[str]]]:
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return None, [[c.strip() for c in row] for row in csv.reader(fh)]
    if path.suffix.lower() == ".xlsx":
        import openpyxl
        from .extract.xlsx import cell_text

        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            ws = wb.worksheets[0]
            return ws.title, [[cell_text(v)[0] for v in row] for row in ws.iter_rows(values_only=True)]
        finally:
            wb.close()
    raise SystemExit("heuristic onboarding supports CSV and XLSX; use --ai for PDF layouts or author the template by hand")


def _match_field(label: str) -> str | None:
    lab = label.strip().lower()
    for fld, words in SYNONYMS.items():
        if lab in words:
            return fld
    return None


def _ref_pattern(samples: list[str]) -> str | None:
    pats = {re.sub(r"\d+", lambda m: rf"\d{{{len(m.group())}}}", re.escape(s)) for s in samples if s}
    return pats.pop() if len(pats) == 1 else None


# ------------------------------------------------------------- heuristic
def heuristic_proposal(path: Path, broker_id: str, ref_roots: set[str]) -> tuple[BrokerConfig, dict]:
    sheet, rows = _read_table(path)
    header_idx, header = None, None
    for i, row in enumerate(rows[:30]):
        if sum(1 for c in row if _match_field(c)) >= 3:
            header_idx, header = i, row
            break
    if header is None:
        raise SystemExit("could not find a header row with at least three recognisable column names")
    columns = {}
    for c in header:
        f = _match_field(c)
        if f and f not in columns:
            columns[f] = c
    body = [r for r in rows[header_idx + 1:] if any(r)]
    col = {lbl: header.index(lbl) for lbl in header if lbl}
    ref_lbl = columns.get("broker_ref")
    data = [r for r in body if ref_lbl and len(r) > col[ref_lbl] and r[col[ref_lbl]]
            and re.match(r"^[A-Z0-9][A-Z0-9\-_/]+$", r[col[ref_lbl]]) and len(r) >= len(header) - 1]
    trailer = [r for r in body if r not in data]
    vals = lambda f: [r[col[columns[f]]] for r in data if f in columns and len(r) > col[columns[f]]]  # noqa: E731
    notes = []

    # Dates: keep only formats that parse every sample; ambiguity is flagged, never resolved silently.
    date_fmt = None
    if "trade_date" in columns:
        ok = [f for f in DATE_FORMATS if all(_parses(v, f) for v in vals("trade_date")[:200])]
        if len(ok) == 1:
            date_fmt = ok[0]
        else:
            notes.append(f"trade date format ambiguous or unknown (candidates {ok}); reviewer must set formats.date")
            date_fmt = ok[0] if ok else "%Y-%m-%d"
    cm_style = "YYYY-MM"
    if "contract_month" in columns:
        s = vals("contract_month")[:50]
        for style, rx in (("YYYY-MM", r"^\d{4}-\d{2}$"), ("MONYY", r"^[A-Z]{3}\d{2}$"), ("MON-YYYY", r"^[A-Za-z]{3}-\d{4}$"),
                          ("CODE_Y1", r"^[FGHJKMNQUVXZ]\d$"), ("CODE_Y2", r"^[FGHJKMNQUVXZ]\d{2}$")):
            if s and all(re.match(rx, v) for v in s):
                cm_style = style
                break
        else:
            notes.append("contract month style not recognised; reviewer must set formats.contract_month")
    side_map, signed = {}, False
    if "side" in columns:
        for v in sorted(set(vals("side"))):
            if v.upper() in SIDE_WORDS:
                side_map[v] = SIDE_WORDS[v.upper()]
            else:
                notes.append(f"side value {v!r} not understood; add it to formats.side_map")
    elif any(v.startswith("-") for v in vals("quantity")):
        signed = True
        notes.append("no side column; quantities are signed - proposed signed_quantity: true")
    pt = ProductTypeRule(opt_if_present="put_call") if "put_call" in columns else (
        ProductTypeRule(constant="FXFWD") if "ccy_pair" in columns else ProductTypeRule(constant="FUT"))
    if pt.constant == "FUT":
        notes.append("no option or FX columns found; proposed constant product type FUT - confirm")
    symbology, unmapped = {}, []
    if "instrument_code" in columns:
        for code in sorted(set(v.upper() for v in vals("instrument_code"))):
            if code in ref_roots:
                symbology[code] = code
            else:
                unmapped.append(code)
        if unmapped:
            notes.append(f"instrument codes with no proposed mapping (left unmapped; rows will be exceptions until mapped): {unmapped}")
    totals = []
    for r in trailer[-3:]:
        text = " ".join(c for c in r if c)
        m = re.match(r"^(.*?)(\d[\d,]*)\s*$", text)
        if m and re.search(r"(?i)record|total|count|trades", m.group(1)):
            totals.append(TotalsRule(regex="^" + re.escape(m.group(1)) + r"(?P<count>[\d,]+)$"))
    if not totals:
        notes.append("no control-total line detected: completeness will rest on reconciling to the internal list only")
    stem = re.split(r"[_\-\s.]", path.stem)[0]
    table = TableConfig(
        name="open_trades", sheet=sheet, header=[h for h in header if h], columns=columns, product_type=pt,
        totals=totals, end_patterns=[t.regex.split("(?P<count>")[0] for t in totals],
        row_ref_pattern=_ref_pattern(vals("broker_ref")[:500]),
    )
    cfg = BrokerConfig(
        config_id=f"{broker_id}.v1", broker_id=broker_id, broker_name=f"{broker_id} (proposed)", version=1,
        status="proposed", format="csv" if path.suffix.lower() == ".csv" else "xlsx",
        fingerprint=Fingerprint(filename_regex=f"^{re.escape(stem)}[_\\-].*\\{path.suffix.lower()}$", must_contain=table.header[:4]),
        tables=[table], formats=Formats(date=date_fmt or "%Y-%m-%d", contract_month=cm_style, side_map=side_map, signed_quantity=signed),
        symbology=symbology,
    )
    return cfg, {"method": "heuristic-synonyms-v1", "notes": notes, "unmapped_instrument_codes": unmapped}


def _parses(v: str, f: str) -> bool:
    try:
        dt.datetime.strptime(v, f)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------- AI
class AIColumn(BaseModel):
    canonical_field: Literal["broker_ref", "account", "exchange", "instrument_code", "contract_month", "put_call", "strike",
                             "ccy_pair", "value_date", "side", "quantity", "price", "trade_date", "aps_flag"]
    header_label: str


class AISideValue(BaseModel):
    raw: str
    side: Literal["BUY", "SELL"]


class AIProposal(BaseModel):
    columns: list[AIColumn]
    product_type_rule: Literal["CONSTANT_FUT", "CONSTANT_FXFWD", "OPT_IF_PUT_CALL_PRESENT"]
    date_format: str
    contract_month_style: Literal["MONYY", "MON-YYYY", "MONYYYY", "YYYY-MM", "CODE_Y1", "CODE_Y2", "NOT_APPLICABLE"]
    side_values: list[AISideValue]
    signed_quantity: bool
    decimal_separator: Literal[".", ","]
    thousands_separator: Literal["", ",", ".", " ", "'"]
    uncertainties: list[str]


def _mask(value: str) -> str:
    """Pseudonymise while keeping shape: letters->X, digits->9."""
    return re.sub(r"[A-Za-z]", "X", re.sub(r"\d", "9", value))


def ai_proposal(path: Path, broker_id: str, ref_roots: set[str], mask: bool = True, client=None) -> tuple[BrokerConfig, dict]:
    base, meta = heuristic_proposal(path, broker_id, ref_roots)
    _sheet, rows = _read_table(path)
    header = base.tables[0].header
    h_idx = next(i for i, r in enumerate(rows) if [c for c in r if c] == header)
    sample = [r for r in rows[h_idx + 1:h_idx + 9] if any(r)]
    sensitive = {base.tables[0].columns.get("broker_ref"), base.tables[0].columns.get("account")}
    if mask:
        sample = [[_mask(v) if header[i] in sensitive else v for i, v in enumerate(r[:len(header)])] for r in sample]
    prompt = (
        "You are helping an auditor configure a deterministic parser for a broker statement of open derivative trades. "
        "Map each column header to the canonical field it contains (omit columns that match none), and infer the value "
        "conventions from the sample rows. Do not guess when the samples are ambiguous (for example a date that could be "
        "day-first or month-first): list the ambiguity in `uncertainties` instead. The output is a proposal that a "
        "person will review before anything uses it.\n\n"
        f"File type: {path.suffix.lower()}\nHeader: {header}\nSample rows (some values pseudonymised):\n"
        + "\n".join(str(r) for r in sample)
    )
    if client is None:
        import anthropic

        client = anthropic.Anthropic()
    resp = client.messages.parse(
        model=AI_MODEL,
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}],
        output_format=AIProposal,
    )
    if resp.stop_reason == "refusal" or resp.parsed_output is None:
        raise SystemExit(f"model did not return a proposal (stop_reason={resp.stop_reason}); use the heuristic path")
    p: AIProposal = resp.parsed_output
    t = base.tables[0]
    t.columns = {c.canonical_field: c.header_label for c in p.columns if c.header_label in header}
    t.product_type = {"CONSTANT_FUT": ProductTypeRule(constant="FUT"), "CONSTANT_FXFWD": ProductTypeRule(constant="FXFWD"),
                      "OPT_IF_PUT_CALL_PRESENT": ProductTypeRule(opt_if_present="put_call")}[p.product_type_rule]
    base.formats = Formats(
        date=p.date_format, contract_month=p.contract_month_style if p.contract_month_style != "NOT_APPLICABLE" else "YYYY-MM",
        side_map={s.raw: s.side for s in p.side_values}, signed_quantity=p.signed_quantity,
        decimal_separator=p.decimal_separator, thousands_separator=p.thousands_separator,
    )
    meta = {
        "method": "ai-structured-output", "model_requested": AI_MODEL, "model_served": getattr(resp, "model", None),
        "response_id": getattr(resp, "id", None), "prompt_sha256": sha256_text(prompt),
        "response_sha256": sha256_text(canonical_json(p.model_dump())), "values_masked": mask,
        "notes": list(p.uncertainties) + [n for n in meta["notes"] if "instrument codes" in n or "control-total" in n],
        "unmapped_instrument_codes": meta["unmapped_instrument_codes"],
    }
    return base, meta


# ------------------------------------------------------------------ driver
def self_test(path: Path, cfg: BrokerConfig, config_dir: Path, as_of: dt.date) -> dict:
    from .extract import extract
    from .normalize import normalize_row

    ref = load_reference(config_dir)
    doc = DocumentExtraction(file=path.name, sha256=sha256_file(path), broker_id=cfg.broker_id, config_id=cfg.config_id,
                             config_sha256=cfg.body_sha256(), fmt=cfg.format)
    extract(path, cfg, doc)
    recs = [normalize_row(r, cfg, ref, as_of, "BROKER", path.name, r.row_id) for r in doc.rows]
    return {
        "rows_extracted": len(doc.rows),
        "completeness": doc.controls.get("completeness"),
        "document_issues": [f"{i.code}: {i.detail}" for i in doc.issues][:20],
        "records_comparable": sum(1 for r in recs if r.comparable),
        "record_issues_by_code": dict(sorted(Counter(r.issues[0]["code"] for r in recs if r.issues).items())),
    }


def onboard(path: Path, broker_id: str, config_dir: Path, use_ai: bool = False, mask: bool = True,
            as_of: dt.date = dt.date(2026, 12, 31), client=None) -> Path:
    roots = set(load_reference(config_dir).instruments)
    cfg, meta = (ai_proposal(path, broker_id, roots, mask=mask, client=client) if use_ai
                 else heuristic_proposal(path, broker_id, roots))
    meta["generated_from"] = {"file": path.name, "sha256": sha256_file(path)}
    meta["self_test"] = self_test(path, cfg, config_dir, as_of)
    cfg.proposal = meta
    out = config_dir / "brokers" / "proposed" / f"{broker_id}.yaml"
    save_config(cfg, out)
    return out
