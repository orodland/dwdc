"""Core data structures shared by every pipeline stage."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# --- Reconciliation statuses and exception codes --------------------------------
# Every record ends with exactly one status and one primary code.

MATCHED = "MATCHED"
BREAK = "BREAK"
AMBIGUOUS = "AMBIGUOUS"
DUPLICATE = "DUPLICATE"
NOT_COMPARABLE = "NOT_COMPARABLE"
UNMATCHED = "UNMATCHED"

# Match rules (status MATCHED)
T1_REF_EXACT = "T1_REF_EXACT"
T2_KEY_EXACT = "T2_KEY_EXACT"
T3_APS_GROUP = "T3_APS_GROUP"

# Record-level exception codes
CONFLICTING_VALUES = "CONFLICTING_VALUES"  # same broker reference, economic fields differ
VALUE_BREAK = "VALUE_BREAK"  # unique counterpart that differs in exactly one field
APS_GROUP_BREAK = "APS_GROUP_BREAK"  # average-price line vs fill group totals differ
GROUP_COUNT_MISMATCH = "GROUP_COUNT_MISMATCH"  # identical economics, different counts
AMBIGUOUS_CANDIDATES = "AMBIGUOUS_CANDIDATES"
DUPLICATE_RECORD = "DUPLICATE_RECORD"
MISSING_FIELD = "MISSING_FIELD"
EXTRACTION_UNCERTAIN = "EXTRACTION_UNCERTAIN"
UNMAPPED_INSTRUMENT = "UNMAPPED_INSTRUMENT"
VALIDATION_FAILED = "VALIDATION_FAILED"
COUNTERPART_INCOMPLETE = "COUNTERPART_INCOMPLETE"
UNMATCHED_INTERNAL = "UNMATCHED_INTERNAL"
UNMATCHED_BROKER = "UNMATCHED_BROKER"
NO_CONFIRMATION_RECEIVED = "NO_CONFIRMATION_RECEIVED"
CONFIRMATION_NOT_PROCESSED = "CONFIRMATION_NOT_PROCESSED"

# Document-level exception codes
FORMAT_UNRECOGNISED = "FORMAT_UNRECOGNISED"
CONFIG_NOT_APPROVED = "CONFIG_NOT_APPROVED"
COMPLETENESS_FAIL = "COMPLETENESS_FAIL"
GROUNDING_FAIL = "GROUNDING_FAIL"
UNCLASSIFIED_CONTENT = "UNCLASSIFIED_CONTENT"
PROVENANCE_UNVERIFIED = "PROVENANCE_UNVERIFIED"

STATUS_BY_CODE = {
    T1_REF_EXACT: MATCHED,
    T2_KEY_EXACT: MATCHED,
    T3_APS_GROUP: MATCHED,
    CONFLICTING_VALUES: BREAK,
    VALUE_BREAK: BREAK,
    APS_GROUP_BREAK: BREAK,
    GROUP_COUNT_MISMATCH: AMBIGUOUS,
    AMBIGUOUS_CANDIDATES: AMBIGUOUS,
    DUPLICATE_RECORD: DUPLICATE,
    MISSING_FIELD: NOT_COMPARABLE,
    EXTRACTION_UNCERTAIN: NOT_COMPARABLE,
    UNMAPPED_INSTRUMENT: NOT_COMPARABLE,
    VALIDATION_FAILED: NOT_COMPARABLE,
    COUNTERPART_INCOMPLETE: NOT_COMPARABLE,
    UNMATCHED_INTERNAL: UNMATCHED,
    UNMATCHED_BROKER: UNMATCHED,
    NO_CONFIRMATION_RECEIVED: UNMATCHED,
    CONFIRMATION_NOT_PROCESSED: UNMATCHED,
}

# Validation issue precedence when a record has several problems.
ISSUE_PRECEDENCE = (EXTRACTION_UNCERTAIN, MISSING_FIELD, UNMAPPED_INSTRUMENT, VALIDATION_FAILED)

COMPARE_FIELDS = {
    "FUT": ("account", "exchange", "root", "contract_month", "side", "quantity", "price", "trade_date"),
    "OPT": ("account", "exchange", "root", "contract_month", "put_call", "strike", "side", "quantity", "price", "trade_date"),
    "FXFWD": ("account", "ccy_pair", "side", "quantity", "price", "trade_date", "value_date"),
}
# Fields that identify *what* was traded and when (used to find APS fill groups).
APS_KEY_FIELDS = ("account", "exchange", "root", "contract_month", "put_call", "strike", "side", "trade_date")


@dataclass
class Cell:
    raw: str
    loc: dict[str, Any]
    verified: bool | None = None  # independent re-read of the source location agreed


@dataclass
class ExtractedRow:
    row_id: str
    table: str
    cells: dict[str, Cell]
    row_loc: dict[str, Any]


@dataclass
class DocIssue:
    code: str
    detail: str
    loc: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentExtraction:
    file: str
    sha256: str
    broker_id: str
    config_id: str | None
    config_sha256: str | None
    fmt: str
    rows: list[ExtractedRow] = field(default_factory=list)
    controls: dict[str, Any] = field(default_factory=dict)
    issues: list[DocIssue] = field(default_factory=list)


@dataclass
class Step:
    field: str
    rule: str
    input: str
    output: str


@dataclass
class Record:
    """Canonical trade record (internal or broker side)."""

    record_id: str
    origin: str  # BROKER | INTERNAL
    broker_id: str
    source_file: str
    source_row: str
    product_type: str | None = None
    account: str | None = None
    exchange: str | None = None
    root: str | None = None
    contract_month: str | None = None
    put_call: str | None = None
    strike: str | None = None
    ccy_pair: str | None = None
    value_date: str | None = None
    side: str | None = None
    quantity: str | None = None
    price: str | None = None
    trade_date: str | None = None
    broker_ref: str | None = None
    aps_flag: bool = False
    aps_group_id: str | None = None
    internal_id: str | None = None
    # lineage
    raw: dict[str, Any] = field(default_factory=dict)
    steps: list[Step] = field(default_factory=list)
    issues: list[dict[str, str]] = field(default_factory=list)
    # reconciliation outcome
    status: str | None = None
    code: str | None = None
    rule_detail: str | None = None
    counterparts: list[str] = field(default_factory=list)
    match_group: str | None = None
    diff_fields: list[str] = field(default_factory=list)
    exception_id: str | None = None

    @property
    def comparable(self) -> bool:
        return not self.issues

    def compare_fields(self) -> tuple[str, ...]:
        return COMPARE_FIELDS.get(self.product_type or "", ())

    def key(self, fields: tuple[str, ...] | None = None) -> tuple:
        fields = fields if fields is not None else self.compare_fields()
        return (self.product_type,) + tuple(getattr(self, f) for f in fields)

    def canonical(self) -> dict[str, Any]:
        keys = (
            "product_type", "account", "exchange", "root", "contract_month", "put_call", "strike",
            "ccy_pair", "value_date", "side", "quantity", "price", "trade_date", "broker_ref",
            "aps_flag", "aps_group_id", "internal_id",
        )
        return {k: getattr(self, k) for k in keys}

    def to_lineage(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class ExceptionItem:
    exception_id: str
    level: str  # DOCUMENT | RECORD
    code: str
    status: str
    broker_id: str
    record_ids: list[str]
    diff_fields: list[str]
    detail: str
    source_file: str = ""
