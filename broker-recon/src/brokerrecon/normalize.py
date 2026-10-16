"""Validation and normalisation: pure, versioned, deterministic functions.

Every transformation applied to a raw value is recorded as a ``Step`` so a
reviewer can see exactly how ``"442'2"`` became ``442.25``. Nothing is ever
guessed: a value that cannot be interpreted under the broker's declared
conventions raises an issue and the record is excluded from matching.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation

from .config import BrokerConfig, Formats, TableConfig
from .model import (
    EXTRACTION_UNCERTAIN, ISSUE_PRECEDENCE, MISSING_FIELD, UNMAPPED_INSTRUMENT, VALIDATION_FAILED,
    Cell, ExtractedRow, Record, Step,
)
from .reference import Reference

NORMALISATION_VERSION = "norm-1"

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}
MONTH_CODES = {c: i for i, c in enumerate("FGHJKMNQUVXZ", start=1)}

REQUIRED = {
    "FUT": ("account", "instrument_code", "contract_month", "side", "quantity", "price", "trade_date"),
    "OPT": ("account", "instrument_code", "contract_month", "put_call", "strike", "side", "quantity", "price", "trade_date"),
    "FXFWD": ("account", "ccy_pair", "side", "quantity", "price", "trade_date", "value_date"),
}


class NormError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def dec_str(d: Decimal) -> str:
    """Exact, trailing-zero-free decimal string (no rounding ever applied)."""
    s = format(d.normalize(), "f")
    return "0" if s in ("-0", "") else s


_NUM_RE = re.compile(r"^\d+(\.\d+)?$")


def parse_number(raw: str, fmt: Formats, typed_number: bool = False) -> Decimal:
    s = raw.strip()
    if not s:
        raise NormError(MISSING_FIELD, "empty")
    if typed_number:  # a numeric spreadsheet cell: always '.' decimal, no grouping
        try:
            return Decimal(s)
        except InvalidOperation as e:
            raise NormError(EXTRACTION_UNCERTAIN, f"not a number: {raw!r}") from e
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1].strip()
    if s.startswith("-"):
        neg, s = True, s[1:].strip()
    elif s.endswith("-"):
        neg, s = True, s[:-1].strip()
    int_part, sep, frac = s.partition(fmt.decimal_separator)
    if sep and not frac.isdigit():
        raise NormError(EXTRACTION_UNCERTAIN, f"not a number under declared format: {raw!r}")
    ts = fmt.thousands_separator
    if ts and ts in int_part:
        # Grouping must be well-formed (1-3 digits, then groups of exactly 3): "12,5" under a
        # US format is a locale mismatch to flag, not the number 125.
        groups = int_part.split(ts)
        if not (groups[0].isdigit() and len(groups[0]) <= 3 and all(len(g) == 3 and g.isdigit() for g in groups[1:])):
            raise NormError(EXTRACTION_UNCERTAIN, f"malformed digit grouping under declared format: {raw!r}")
        int_part = "".join(groups)
    s = int_part + ("." + frac if sep else "")
    if not _NUM_RE.match(s):
        raise NormError(EXTRACTION_UNCERTAIN, f"not a number under declared format: {raw!r}")
    v = Decimal(s)
    return -v if neg else v


def parse_date(cell: Cell, fmt: Formats) -> dt.date:
    s = cell.raw.strip()
    if not s:
        raise NormError(MISSING_FIELD, "empty")
    if cell.loc.get("type") == "date":
        return dt.date.fromisoformat(s)
    try:
        return dt.datetime.strptime(s, fmt.date).date()
    except ValueError as e:
        raise NormError(EXTRACTION_UNCERTAIN, f"date {s!r} does not match declared format {fmt.date}") from e


def parse_contract_month(raw: str, style: str, as_of: dt.date) -> tuple[str, str]:
    s = raw.strip().upper()
    if not s:
        raise NormError(MISSING_FIELD, "empty")
    try:
        if style == "YYYY-MM":
            y, m = s.split("-")
            year, month = int(y), int(m)
        elif style == "MONYY":
            month, year = MONTHS[s[:3]], 2000 + int(s[3:])
            if len(s) != 5:
                raise ValueError
        elif style == "MONYYYY":
            month, year = MONTHS[s[:3]], int(s[3:])
            if len(s) != 7:
                raise ValueError
        elif style == "MON-YYYY":
            mon, y = s.split("-")
            month, year = MONTHS[mon], int(y)
        elif style == "CODE_Y2":
            month, year = MONTH_CODES[s[0]], 2000 + int(s[1:])
            if len(s) != 3:
                raise ValueError
        elif style == "CODE_Y1":
            if len(s) != 2:
                raise ValueError
            month, digit = MONTH_CODES[s[0]], int(s[1])
            # Open positions cannot be in contract years before the confirmation year.
            window = range(as_of.year, as_of.year + 10)
            year = next(y for y in window if y % 10 == digit)
            out = f"{year:04d}-{month:02d}"
            return out, f"month code + single-digit year resolved in window {window.start}-{window.stop - 1}"
        else:
            raise ValueError
    except (KeyError, ValueError, StopIteration) as e:
        raise NormError(EXTRACTION_UNCERTAIN, f"contract month {raw!r} not in declared style {style}") from e
    if not 1 <= month <= 12:
        raise NormError(EXTRACTION_UNCERTAIN, f"invalid month in {raw!r}")
    return f"{year:04d}-{month:02d}", f"parsed as {style}"


def parse_price(raw: str, root: str | None, cell: Cell, fmt: Formats, ref: Reference, steps: list[Step], fld: str) -> Decimal:
    style = fmt.price_format.get(root or "", "decimal") if fld == "price" else "decimal"
    s = raw.strip()
    if not s:
        raise NormError(MISSING_FIELD, "empty")
    if style == "eighths_apostrophe" and cell.loc.get("type") != "number":
        m = re.fullmatch(r"(\d+)'([0-7])", s)
        if not m:
            raise NormError(EXTRACTION_UNCERTAIN, f"{raw!r} is not a valid eighths price (e.g. 442'2)")
        value = Decimal(m.group(1)) + Decimal(int(m.group(2))) / Decimal(8)
        steps.append(Step(fld, "fraction_eighths", raw, dec_str(value)))
    else:
        value = parse_number(s, fmt, typed_number=cell.loc.get("type") == "number")
    unit = fmt.price_unit.get(root or "")
    inst = ref.instruments.get(root or "")
    if unit and inst and unit != inst.quote_unit:
        if unit == "dollars" and inst.quote_unit == "cents":
            new = value * 100
        elif unit == "cents" and inst.quote_unit == "units":
            new = value / 100
        else:
            raise NormError(VALIDATION_FAILED, f"no conversion from {unit} to {inst.quote_unit}")
        steps.append(Step(fld, f"unit_{unit}_to_{inst.quote_unit}", dec_str(value), dec_str(new)))
        value = new
    return value


def _cell(row: ExtractedRow, name: str) -> Cell | None:
    return row.cells.get(name)


def normalize_row(
    row: ExtractedRow,
    cfg: BrokerConfig,
    ref: Reference,
    as_of: dt.date,
    origin: str,
    source_file: str,
    record_id: str,
) -> Record:
    table: TableConfig = next(t for t in cfg.tables if t.name == row.table)
    fmt = cfg.formats.model_copy(update=table.format_overrides) if table.format_overrides else cfg.formats
    rec = Record(record_id=record_id, origin=origin, broker_id=cfg.broker_id if origin == "BROKER" else "",
                 source_file=source_file, source_row=row.row_id)
    rec.raw = {k: {"raw": c.raw, "loc": c.loc, "verified": c.verified} for k, c in sorted(row.cells.items())}
    steps = rec.steps
    issues: list[dict[str, str]] = []

    def issue(code: str, fld: str, detail: str):
        issues.append({"code": code, "field": fld, "detail": detail})

    def text(name: str) -> str:
        c = _cell(row, name)
        return c.raw.strip() if c else ""

    # Grounding: an independent re-read that disagrees is an extraction uncertainty.
    for name, c in sorted(row.cells.items()):
        if c.verified is False:
            issue(EXTRACTION_UNCERTAIN, name, f"independent re-read of source gave {c.loc.get('reread')!r}, extracted {c.raw!r}")
        if c.loc.get("split_failed"):
            issue(EXTRACTION_UNCERTAIN, name, f"value {c.loc.get('source_text')!r} did not match split rule")

    # Product type
    pt_rule = table.product_type
    if pt_rule.constant:
        pt = pt_rule.constant
    elif pt_rule.column:
        raw_pt = text("product_type")
        pt = pt_rule.map.get(raw_pt, raw_pt if raw_pt in REQUIRED else None)
        if raw_pt and pt != raw_pt:
            steps.append(Step("product_type", "map", raw_pt, pt or ""))
        if pt is None:
            issue(EXTRACTION_UNCERTAIN if raw_pt else MISSING_FIELD, "product_type", f"unknown product type {raw_pt!r}")
    elif pt_rule.opt_if_present:
        pt = "OPT" if text(pt_rule.opt_if_present) else "FUT"
        steps.append(Step("product_type", f"OPT if {pt_rule.opt_if_present} present else FUT", text(pt_rule.opt_if_present), pt))
    else:
        pt = None
        issue(VALIDATION_FAILED, "product_type", "config defines no product type rule")
    rec.product_type = pt

    if origin == "INTERNAL":
        rec.internal_id = text("internal_id") or None
        rec.broker_id = text("broker_id").upper()
        rec.aps_group_id = text("aps_group_id") or None
        if not rec.broker_id:
            issue(MISSING_FIELD, "broker_id", "internal record has no broker")

    rec.broker_ref = text("broker_ref") or None

    if pt in REQUIRED:
        for fld in REQUIRED[pt]:
            if fld == "side" and fmt.signed_quantity:
                continue
            if not text(fld) and not any(i["field"] == fld for i in issues):
                issue(MISSING_FIELD, fld, "required field is empty")

    def guarded(fld: str, fn):
        if any(i["field"] == fld for i in issues) or not text(fld):
            return None
        try:
            return fn()
        except NormError as e:
            issue(e.code, fld, e.detail)
            return None

    # Account
    acct = guarded("account", lambda: text("account").upper())
    if acct is not None:
        if acct != _cell(row, "account").raw:
            steps.append(Step("account", "strip_upper", _cell(row, "account").raw, acct))
        rec.account = acct

    if pt in ("FUT", "OPT"):
        def _root():
            code = text("instrument_code").upper()
            root = cfg.symbology.get(code)
            if root is None:
                raise NormError(UNMAPPED_INSTRUMENT, f"broker instrument code {code!r} not in approved symbology")
            if root not in ref.instruments:
                raise NormError(UNMAPPED_INSTRUMENT, f"root {root!r} not in reference data")
            if pt not in ref.instruments[root].product_types:
                raise NormError(VALIDATION_FAILED, f"{pt} not a valid product type for {root}")
            steps.append(Step("root", "symbology", code, root))
            return root
        rec.root = guarded("instrument_code", _root)
        if rec.root:
            inst = ref.instruments[rec.root]
            ex_raw = text("exchange")
            if ex_raw:
                if ex_raw.upper() not in inst.exchange_aliases:
                    issue(VALIDATION_FAILED, "exchange", f"exchange {ex_raw!r} inconsistent with {rec.root} ({inst.exchange})")
                else:
                    rec.exchange = inst.exchange
                    steps.append(Step("exchange", "alias_to_MIC", ex_raw, inst.exchange))
            else:
                rec.exchange = inst.exchange
                steps.append(Step("exchange", "derived_from_reference", "", inst.exchange))

        def _cm():
            out, how = parse_contract_month(text("contract_month"), fmt.contract_month, as_of)
            steps.append(Step("contract_month", how, text("contract_month"), out))
            return out
        rec.contract_month = guarded("contract_month", _cm)

        if pt == "OPT":
            def _pc():
                raw = text("put_call")
                pc = fmt.put_call_map.get(raw, fmt.put_call_map.get(raw.upper()))
                if pc not in ("C", "P"):
                    raise NormError(EXTRACTION_UNCERTAIN, f"put/call value {raw!r} not in declared map")
                if pc != raw:
                    steps.append(Step("put_call", "map", raw, pc))
                return pc
            rec.put_call = guarded("put_call", _pc)
            rec.strike = None if rec.root is None else guarded("strike", lambda: dec_str(parse_price(text("strike"), rec.root, _cell(row, "strike"), fmt, ref, steps, "strike")))
            if rec.strike is not None and Decimal(rec.strike) <= 0:
                issue(VALIDATION_FAILED, "strike", "strike must be positive")

        # Price/strike conventions depend on the instrument: not interpreted if it is unknown.
        rec.price = None if rec.root is None else guarded("price", lambda: dec_str(parse_price(text("price"), rec.root, _cell(row, "price"), fmt, ref, steps, "price")))
    elif pt == "FXFWD":
        def _pair():
            raw = text("ccy_pair").upper()
            letters = re.sub(r"[^A-Z]", "", raw)
            if len(letters) != 6 or letters[:3] not in ref.currencies or letters[3:] not in ref.currencies:
                raise NormError(EXTRACTION_UNCERTAIN, f"currency pair {raw!r} not recognised")
            if letters != raw:
                steps.append(Step("ccy_pair", "strip_separators", raw, letters))
            return letters
        rec.ccy_pair = guarded("ccy_pair", _pair)
        rec.price = guarded("price", lambda: dec_str(parse_number(text("price"), fmt, typed_number=_cell(row, "price").loc.get("type") == "number")))
        def _vd():
            d = parse_date(_cell(row, "value_date"), fmt)
            steps.append(Step("value_date", f"date {fmt.date}" if _cell(row, "value_date").loc.get("type") != "date" else "excel_date", text("value_date"), d.isoformat()))
            return d.isoformat()
        rec.value_date = guarded("value_date", _vd)

    # Quantity and side
    def _qty():
        q = parse_number(text("quantity"), fmt, typed_number=_cell(row, "quantity").loc.get("type") == "number")
        if fmt.signed_quantity:
            side = "BUY" if q > 0 else "SELL"
            steps.append(Step("side", "sign_of_quantity", text("quantity"), side))
            rec.side = side
            if q < 0:
                steps.append(Step("quantity", "absolute_value", dec_str(q), dec_str(-q)))
            q = abs(q)
        if q <= 0:
            raise NormError(VALIDATION_FAILED, f"quantity must be positive, got {text('quantity')!r}")
        return dec_str(q)
    rec.quantity = guarded("quantity", _qty)
    if not fmt.signed_quantity:
        def _side():
            raw = text("side")
            s = fmt.side_map.get(raw, fmt.side_map.get(raw.upper()))
            if s not in ("BUY", "SELL"):
                raise NormError(EXTRACTION_UNCERTAIN, f"side {raw!r} not in declared map")
            if s != raw:
                steps.append(Step("side", "map", raw, s))
            return s
        rec.side = guarded("side", _side)

    def _td():
        d = parse_date(_cell(row, "trade_date"), fmt)
        if d > as_of:
            raise NormError(VALIDATION_FAILED, f"trade date {d} is after the confirmation date {as_of}")
        steps.append(Step("trade_date", f"date {fmt.date}" if _cell(row, "trade_date").loc.get("type") != "date" else "excel_date", text("trade_date"), d.isoformat()))
        return d.isoformat()
    rec.trade_date = guarded("trade_date", _td)
    if pt == "FXFWD" and rec.value_date and rec.trade_date and rec.value_date <= rec.trade_date:
        issue(VALIDATION_FAILED, "value_date", "value date must be after trade date")

    if fmt.aps_true_values:
        rec.aps_flag = text("aps_flag") in fmt.aps_true_values

    issues.sort(key=lambda i: (ISSUE_PRECEDENCE.index(i["code"]) if i["code"] in ISSUE_PRECEDENCE else 99, i["field"]))
    rec.issues = issues
    return rec
