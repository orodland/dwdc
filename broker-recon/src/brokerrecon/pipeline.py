"""End-to-end run: evidence intake -> extraction -> normalisation -> matching
-> exceptions -> standardised outputs, lineage, audit log and manifest.

The run identity is a hash of every input file, every approved config, the
reference data and the engine/rule versions. Same identity => same outputs.
"""

from __future__ import annotations

import datetime as dt
import getpass
import platform
import shutil
import time
from collections import Counter
from pathlib import Path

import yaml

from . import ENGINE_VERSION
from .audit import EventLog
from .config import BrokerConfig, load_broker_configs, load_internal_config
from .extract import extract, file_format, fingerprint
from .hashing import sha256_file, sha256_obj, short_id
from .match import MATCHING_RULES_VERSION, Reconciler, positions
from .model import (
    CONFIG_NOT_APPROVED, FORMAT_UNRECOGNISED, PROVENANCE_UNVERIFIED, DocIssue, DocumentExtraction,
    ExceptionItem, Record,
)
from .normalize import NORMALISATION_VERSION, normalize_row
from .outputs import (
    EXCEPTION_COLUMNS, TRADE_COLUMNS, exception_row, trade_row, write_csv, write_json, write_jsonl, write_jsonl_gz, write_xlsx,
)
from .reference import load_reference

XLSX_TRADE_LIMIT = 150_000  # above this the workbook lists only non-matched trades; trades.csv is always complete
DOC_COLUMNS = ["file", "sha256", "broker_id", "format", "config_id", "config_sha256", "status",
               "rows_extracted", "rows_declared", "quantity_extracted", "quantity_declared",
               "cells_verified", "cells_unverified", "issues"]


def _load_intake(evidence_dir: Path) -> dict:
    path = evidence_dir / "intake.yaml"
    if not path.exists():
        return {"internal": None, "confirmations": []}
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def run(evidence_dir: Path, config_dir: Path, out_root: Path, as_of: dt.date, review_pack: bool = True) -> Path:
    t0 = time.time()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    evidence_dir, config_dir = evidence_dir.resolve(), config_dir.resolve()
    ref = load_reference(config_dir)
    all_cfgs = load_broker_configs(config_dir)
    internal_cfg = load_internal_config(config_dir)
    intake = _load_intake(evidence_dir)

    # ---------------------------------------------------------------- evidence register
    listed = {c["file"]: c for c in intake.get("confirmations", [])}
    broker_files = sorted(p for p in (evidence_dir / "brokers").rglob("*") if p.is_file())
    evidence = []
    for p in broker_files:
        rel = p.relative_to(evidence_dir).as_posix()
        evidence.append({"file": rel, "sha256": sha256_file(p), "intake": listed.get(rel)})
    internal_meta = intake.get("internal") or {}
    internal_path = evidence_dir / internal_meta.get("file", "internal/internal_open_trades.xlsx")
    internal_rel = internal_path.relative_to(evidence_dir).as_posix()
    internal_sha = sha256_file(internal_path)

    cfg_fingerprints = [
        {"config_id": c.config_id, "file": p.name, "body_sha256": c.body_sha256(), "status": c.status,
         "approval": c.approval.model_dump() if c.approval else None}
        for p, c in sorted(all_cfgs, key=lambda pc: pc[1].config_id)
    ]
    identity = {
        "engine_version": ENGINE_VERSION,
        "normalisation_version": NORMALISATION_VERSION,
        "matching_rules_version": MATCHING_RULES_VERSION,
        "reference": {"version": ref.version, "sha256": ref.sha256},
        "configs": cfg_fingerprints,
        "internal_config_sha256": internal_cfg.body_sha256(),
        "evidence": evidence,
        "internal": {"file": internal_rel, "sha256": internal_sha, "intake": internal_meta},
        "as_of": as_of.isoformat(),
    }
    run_id = sha256_obj(identity)[:16]
    run_dir = out_root / f"run-{run_id}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)

    log = EventLog(run_dir / "audit" / "events.jsonl")
    log.emit("RUN_STARTED", run_id=run_id, as_of=as_of.isoformat(), engine_version=ENGINE_VERSION,
             normalisation_version=NORMALISATION_VERSION, matching_rules_version=MATCHING_RULES_VERSION,
             reference=identity["reference"])
    for c in cfg_fingerprints:
        log.emit("CONFIG_REGISTERED", **c)
    log.emit("EVIDENCE_REGISTERED", file=internal_rel, sha256=internal_sha, role="internal_trade_list", intake=internal_meta)
    for e in evidence:
        log.emit("EVIDENCE_REGISTERED", file=e["file"], sha256=e["sha256"], role="broker_confirmation", intake=e["intake"])

    # ------------------------------------------------------------- broker documents
    docs: list[DocumentExtraction] = []
    broker_records: list[Record] = []
    processed: set[str] = set()
    received_unprocessed: set[str] = set()
    approved_or_not = [c for _, c in all_cfgs]
    for e in evidence:
        path = evidence_dir / e["file"]
        meta = e["intake"] or {}
        intake_broker = meta.get("broker_id", "")
        doc = DocumentExtraction(file=e["file"], sha256=e["sha256"], broker_id=intake_broker, config_id=None,
                                 config_sha256=None, fmt=file_format(path) or path.suffix)
        docs.append(doc)
        if not e["intake"]:
            doc.issues.append(DocIssue(PROVENANCE_UNVERIFIED, "file is not recorded in the confirmation intake register; not processed"))
            log.emit("DOCUMENT_REJECTED", file=e["file"], reason=PROVENANCE_UNVERIFIED)
            continue
        hits = fingerprint(path, approved_or_not)
        if len(hits) != 1:
            why = "no approved template matches this layout" if not hits else f"ambiguous: {len(hits)} templates match"
            doc.issues.append(DocIssue(FORMAT_UNRECOGNISED, f"{why}; run `brokerrecon onboard` to propose a template"))
            received_unprocessed.add(intake_broker)
            log.emit("DOCUMENT_ROUTED", file=e["file"], result=FORMAT_UNRECOGNISED, candidates=[h.config_id for h in hits])
            continue
        cfg: BrokerConfig = hits[0]
        doc.config_id, doc.config_sha256 = cfg.config_id, cfg.body_sha256()
        problem = cfg.approval_problem()
        if problem:
            doc.issues.append(DocIssue(CONFIG_NOT_APPROVED, f"{cfg.config_id}: {problem}"))
            received_unprocessed.add(intake_broker)
            log.emit("DOCUMENT_ROUTED", file=e["file"], result=CONFIG_NOT_APPROVED, config_id=cfg.config_id)
            continue
        if cfg.broker_id != intake_broker:
            doc.issues.append(DocIssue(PROVENANCE_UNVERIFIED, f"layout is {cfg.broker_id} but intake register says {intake_broker}"))
            received_unprocessed.add(intake_broker)
            log.emit("DOCUMENT_ROUTED", file=e["file"], result=PROVENANCE_UNVERIFIED, config_id=cfg.config_id)
            continue
        log.emit("DOCUMENT_ROUTED", file=e["file"], result="ROUTED", config_id=cfg.config_id, config_sha256=doc.config_sha256)
        extract(path, cfg, doc)
        processed.add(cfg.broker_id)
        for row in doc.rows:
            rid = f"{cfg.broker_id}:{e['sha256'][:8]}:{row.row_id}"
            broker_records.append(normalize_row(row, cfg, ref, as_of, "BROKER", e["file"], rid))
        n_ver = sum(1 for r in doc.rows for c in r.cells.values() if c.verified is True)
        n_unv = sum(1 for r in doc.rows for c in r.cells.values() if c.verified is False)
        doc.controls["cells_verified"], doc.controls["cells_unverified"] = n_ver, n_unv
        log.emit("DOCUMENT_EXTRACTED", file=e["file"], config_id=cfg.config_id, rows=len(doc.rows),
                 completeness=doc.controls.get("completeness"), cells_verified=n_ver, cells_unverified=n_unv,
                 issues=[{"code": i.code, "detail": i.detail} for i in doc.issues])

    # ------------------------------------------------------------------ internal list
    idoc = DocumentExtraction(file=internal_rel, sha256=internal_sha, broker_id="INTERNAL",
                              config_id=internal_cfg.config_id, config_sha256=internal_cfg.body_sha256(), fmt="xlsx")
    problem = internal_cfg.approval_problem()
    if problem:
        raise SystemExit(f"internal list config not usable: {problem}")
    extract(internal_path, internal_cfg, idoc)
    internal_records = [
        normalize_row(row, internal_cfg, ref, as_of, "INTERNAL", internal_rel, f"INT:{row.row_id}") for row in idoc.rows
    ]
    log.emit("DOCUMENT_EXTRACTED", file=internal_rel, config_id=internal_cfg.config_id, rows=len(idoc.rows),
             completeness=idoc.controls.get("completeness"),
             issues=[{"code": i.code, "detail": i.detail} for i in idoc.issues])
    log.emit("NORMALISATION_COMPLETED",
             internal_not_comparable=dict(sorted(Counter(r.issues[0]["code"] for r in internal_records if r.issues).items())),
             broker_not_comparable=dict(sorted(Counter(r.issues[0]["code"] for r in broker_records if r.issues).items())),
             internal_records=len(internal_records), broker_records=len(broker_records))

    # ------------------------------------------------------------------------ matching
    rec = Reconciler(ref)
    rec.run(internal_records, broker_records, processed, received_unprocessed)
    all_records = sorted(internal_records + broker_records, key=lambda r: (r.origin != "INTERNAL", r.record_id))
    log.emit("MATCHING_COMPLETED", rules_version=MATCHING_RULES_VERSION,
             by_code=dict(sorted(Counter(r.code for r in all_records).items())))

    # ---------------------------------------------------- document-level exceptions
    doc_exceptions = []
    for d in docs + [idoc]:
        for issue in d.issues:
            doc_exceptions.append(ExceptionItem(
                exception_id=short_id("EX", "DOC", d.sha256, issue.code, issue.detail), level="DOCUMENT",
                code=issue.code, status="OPEN", broker_id=d.broker_id, record_ids=[], diff_fields=[],
                detail=issue.detail + (f" @ {issue.loc}" if issue.loc else ""), source_file=d.file,
            ))
    doc_exceptions.sort(key=lambda e: (e.broker_id, e.code, e.exception_id))
    exceptions = doc_exceptions + rec.exceptions
    for ex in doc_exceptions:
        log.emit("DOCUMENT_EXCEPTION", exception_id=ex.exception_id, code=ex.code, file=ex.source_file, detail=ex.detail)

    # ------------------------------------------------------------------------ outputs
    pos = positions(internal_records, broker_records, processed)
    doc_rows = [_doc_row(d) for d in docs + [idoc]]
    trades = [trade_row(r) for r in all_records]
    ex_rows = [exception_row(e) for e in exceptions]
    res = run_dir / "results"
    write_csv(res / "trades.csv", TRADE_COLUMNS, trades)
    write_csv(res / "exceptions.csv", EXCEPTION_COLUMNS, ex_rows)
    write_csv(res / "documents.csv", DOC_COLUMNS, doc_rows)
    pos_cols = list(pos[0].keys()) if pos else ["broker_id"]
    write_csv(res / "positions.csv", pos_cols, pos)
    summary = _summary(run_id, as_of, all_records, exceptions, docs, idoc, pos)
    write_json(res / "summary.json", summary)
    write_xlsx(res / "reconciliation.xlsx", [
        ("Summary", ["metric", "value"], [{"metric": k, "value": str(v)} for k, v in _flatten(summary)]),
        ("Exceptions", EXCEPTION_COLUMNS, ex_rows),
        ("Trades", TRADE_COLUMNS, trades if len(trades) <= XLSX_TRADE_LIMIT
         else [t for t in trades if t["status"] != "MATCHED"]),
        ("Documents", DOC_COLUMNS, doc_rows),
        ("Positions", pos_cols, pos),
    ])
    write_jsonl_gz(run_dir / "lineage" / "records.jsonl.gz", (r.to_lineage() for r in all_records))
    write_jsonl(run_dir / "lineage" / "documents.jsonl", (
        {"file": d.file, "sha256": d.sha256, "broker_id": d.broker_id, "config_id": d.config_id,
         "config_sha256": d.config_sha256, "controls": d.controls,
         "issues": [{"code": i.code, "detail": i.detail, "loc": i.loc} for i in d.issues]}
        for d in docs + [idoc]))
    if review_pack:
        from .review import build_review_pack
        build_review_pack(run_dir, evidence_dir, all_records, exceptions, doc_rows, summary)

    outputs = {p.relative_to(run_dir).as_posix(): sha256_file(p)
               for p in sorted(run_dir.rglob("*")) if p.is_file() and p.parts[-2] != "audit"}
    log.emit("OUTPUTS_WRITTEN", files=outputs)
    log.emit("RUN_COMPLETED", run_id=run_id, records=len(all_records), exceptions=len(exceptions))
    head = log.close()
    write_json(run_dir / "manifest.json", {
        "run_id": run_id, "identity": identity, "outputs": outputs,
        "event_log": {"file": "audit/events.jsonl", "head_sha256": head},
        "evidence_dir": str(evidence_dir), "config_dir": str(config_dir),
    })
    write_json(run_dir / "execution.json", {
        "note": "Non-deterministic execution facts; excluded from output hashes.",
        "started_utc": started, "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "elapsed_seconds": round(time.time() - t0, 2), "python": platform.python_version(),
        "platform": platform.platform(), "user": getpass.getuser(),
    })
    return run_dir


def _doc_row(d: DocumentExtraction) -> dict:
    comp = d.controls.get("completeness", {})
    rows_declared = ";".join(str(v.get("rows_declared", "")) for v in comp.values())
    q_ext = ";".join(str(v.get("quantity_extracted", "")) for v in comp.values())
    q_dec = ";".join(str(v.get("quantity_declared", "")) for v in comp.values())
    blocking = {FORMAT_UNRECOGNISED, CONFIG_NOT_APPROVED, PROVENANCE_UNVERIFIED}
    if any(i.code in blocking for i in d.issues):
        status = "NOT_PROCESSED"
    elif d.issues:
        status = "PROCESSED_WITH_EXCEPTIONS"
    else:
        status = "PROCESSED"
    return {
        "file": d.file, "sha256": d.sha256, "broker_id": d.broker_id, "format": d.fmt, "config_id": d.config_id or "",
        "config_sha256": d.config_sha256 or "", "status": status, "rows_extracted": len(d.rows),
        "rows_declared": rows_declared, "quantity_extracted": q_ext, "quantity_declared": q_dec,
        "cells_verified": d.controls.get("cells_verified", ""), "cells_unverified": d.controls.get("cells_unverified", ""),
        "issues": " | ".join(f"{i.code}: {i.detail}" for i in d.issues),
    }


def _summary(run_id, as_of, records, exceptions, docs, idoc, pos) -> dict:
    by_origin = {}
    for origin in ("INTERNAL", "BROKER"):
        rs = [r for r in records if r.origin == origin]
        by_origin[origin] = {
            "records": len(rs),
            "by_status": dict(sorted(Counter(r.status for r in rs).items())),
            "by_code": dict(sorted(Counter(r.code for r in rs).items())),
        }
    return {
        "run_id": run_id,
        "as_of": as_of.isoformat(),
        "records": by_origin,
        "exceptions": {
            "total": len(exceptions),
            "document_level": dict(sorted(Counter(e.code for e in exceptions if e.level == "DOCUMENT").items())),
            "record_level": dict(sorted(Counter(e.code for e in exceptions if e.level == "RECORD").items())),
        },
        "documents": {"broker_documents": len(docs), "internal_rows": len(idoc.rows)},
        "positions": dict(sorted(Counter(p["status"] for p in pos).items())),
    }


def _flatten(d: dict, prefix: str = ""):
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            yield from _flatten(v, key + ".")
        else:
            yield key, v
