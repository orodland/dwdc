"""Quality assurance: scoring against ground truth, and reproducibility checks."""

from __future__ import annotations

import csv
import datetime as dt
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from .audit import verify_chain
from .hashing import sha256_file

COMPARED = ("product_type", "account", "exchange", "root", "contract_month", "put_call", "strike", "ccy_pair",
            "value_date", "side", "quantity", "price", "trade_date", "broker_ref")


def _read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def score(run_dir: Path, truth_path: Path) -> dict:
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    trades = _read_csv(run_dir / "results" / "trades.csv")
    docs = {d["file"]: d for d in _read_csv(run_dir / "results" / "documents.csv")}
    exceptions = _read_csv(run_dir / "results" / "exceptions.csv")

    processed_brokers = {d["broker_id"] for d in docs.values() if d["status"] != "NOT_PROCESSED"}
    rec_by_id = {t["record_id"]: t for t in trades}
    bkey = lambda t: f"{t['broker_id']}|{t['broker_ref']}"  # noqa: E731

    # Expected counterparts, by internal id, derived from truth broker entries.
    expected_brokers_for_internal = defaultdict(set)
    for k, e in truth["broker"].items():
        for iid in e["internal_ids"]:
            expected_brokers_for_internal[iid].add(k)

    results = {"internal": Counter(), "broker": Counter()}
    mismatches = []
    false_matches = []

    for t in trades:
        actual = (t["status"], t["code"])
        if t["origin"] == "INTERNAL":
            iid = t["internal_id"]
            b = t["broker_id"]
            if b == "BRK_E" and "BRK_E" not in processed_brokers:
                exp = tuple(truth["internal_before_onboarding"].get(iid, truth["internal"].get(iid)))
            else:
                exp = tuple(truth["internal"].get(iid, ("?", "?")))
            ok = actual == exp
            results["internal"]["correct" if ok else "incorrect"] += 1
            if not ok:
                mismatches.append({"record": t["record_id"], "internal_id": iid, "expected": exp, "actual": actual})
            if t["status"] == "MATCHED":
                got = {bkey(rec_by_id[c]) for c in t["counterparts"].split(";") if c}
                if exp[0] != "MATCHED" or got != expected_brokers_for_internal[iid]:
                    false_matches.append({"record": t["record_id"], "internal_id": iid, "matched_to": sorted(got),
                                          "expected": sorted(expected_brokers_for_internal[iid]), "expected_code": exp})
        else:
            e = truth["broker"].get(bkey(t))
            exp = tuple(e["expect"]) if e else ("?", "?")
            ok = actual == exp
            results["broker"]["correct" if ok else "incorrect"] += 1
            if not ok:
                mismatches.append({"record": t["record_id"], "broker_key": bkey(t), "expected": exp, "actual": actual})
            if t["status"] == "MATCHED":
                got = {rec_by_id[c]["internal_id"] for c in t["counterparts"].split(";") if c}
                if not e or exp[0] != "MATCHED" or got != set(e["internal_ids"]):
                    false_matches.append({"record": t["record_id"], "broker_key": bkey(t), "matched_to": sorted(got),
                                          "expected": sorted(e["internal_ids"]) if e else [], "expected_code": exp})

    # Seeded breaks: every non-match scenario must be surfaced with the expected code.
    seeded = [s for s in truth["seeded"] if (s.get("expect_internal") or s.get("expect_broker") or [""])[0] != "MATCHED"]
    detected = correct_code = 0
    seeded_fail = []
    by_iid = {t["internal_id"]: t for t in trades if t["origin"] == "INTERNAL"}
    by_bkey = defaultdict(list)
    for t in trades:
        if t["origin"] == "BROKER":
            by_bkey[bkey(t)].append(t)
    for s in seeded:
        if s["broker_id"] == "BRK_E" and "BRK_E" not in processed_brokers:
            continue
        recs, exps = [], []
        for iid in s.get("internal_ids", []):
            if s.get("expect_internal") and iid in by_iid:
                recs.append(by_iid[iid])
                exps.append(tuple(s["expect_internal"]))
        refs = s.get("broker_refs") or ([s["broker_ref"]] if s.get("broker_ref") else [])
        for ref in refs:
            for t in by_bkey.get(f"{s['broker_id']}|{ref}", []):
                recs.append(t)
                exps.append(tuple(s["expect_broker"]))
        surfaced = recs and all(t["status"] != "MATCHED" for t in recs)
        right = recs and all((t["status"], t["code"]) == e for t, e in zip(recs, exps))
        detected += bool(surfaced)
        correct_code += bool(right)
        if not right:
            seeded_fail.append({"scenario": s["scenario"], "broker_id": s["broker_id"],
                                "records": [(t["record_id"], t["status"], t["code"]) for t in recs], "expected": exps})
    n_seeded = len([s for s in seeded if not (s["broker_id"] == "BRK_E" and "BRK_E" not in processed_brokers)])

    # Field-level extraction accuracy on rows with a clean ground truth.
    field_total = field_ok = 0
    field_errors = []
    doc_exact = Counter()
    for t in trades:
        if t["origin"] != "BROKER":
            continue
        e = truth["broker"].get(bkey(t))
        if not e or not e["canonical"]:
            continue
        row_ok = True
        for f in COMPARED:
            want = e["canonical"].get(f)
            if want is None:
                continue
            field_total += 1
            if t[f] == want:
                field_ok += 1
            else:
                row_ok = False
                field_errors.append({"record": t["record_id"], "field": f, "expected": want, "actual": t[f]})
        doc_exact["rows_all_fields_correct" if row_ok else "rows_with_field_error"] += 1

    # Completeness per document and expected document-level exceptions.
    completeness = []
    for f, d in truth["documents"].items():
        got = docs.get(f)
        processed = got and got["status"] != "NOT_PROCESSED"
        codes = {x["code"] for x in exceptions if x["level"] == "DOCUMENT" and x["source_file"] == f}
        exp_codes = set(d["doc_codes"] if processed or "doc_codes_before_onboarding" not in d else d["doc_codes_before_onboarding"])
        completeness.append({
            "file": f, "processed": bool(processed), "rows_expected": d["rows"],
            "rows_extracted": int(got["rows_extracted"]) if got else 0,
            "complete": bool(processed) and int(got["rows_extracted"]) == d["rows"],
            "expected_doc_exceptions": sorted(exp_codes), "doc_exceptions": sorted(codes),
            "doc_exceptions_ok": exp_codes == codes,
        })

    out = {
        "run_dir": str(run_dir),
        "false_matches": len(false_matches),
        "classification": {k: dict(v) for k, v in results.items()},
        "seeded_breaks": {"total": n_seeded, "surfaced": detected, "correct_code": correct_code},
        "field_accuracy": {"fields": field_total, "correct": field_ok,
                           "rate": round(field_ok / field_total, 6) if field_total else None},
        "row_level": dict(doc_exact),
        "documents": completeness,
        "details": {"false_matches": false_matches[:50], "misclassified": mismatches[:50],
                    "seeded_failures": seeded_fail[:50], "field_errors": field_errors[:50]},
    }
    processed_docs = [c for c in completeness if c["processed"]]
    out["gates"] = {
        "zero_false_matches": out["false_matches"] == 0,
        "all_records_classified_as_expected": all(v.get("incorrect", 0) == 0 for v in out["classification"].values()),
        "seeded_break_recall_100pct": detected == n_seeded,
        "seeded_break_codes_100pct": correct_code == n_seeded,
        "row_completeness_100pct": all(c["complete"] for c in processed_docs),
        "document_exceptions_as_expected": all(c["doc_exceptions_ok"] for c in completeness),
        "field_accuracy_100pct": field_total > 0 and field_ok == field_total,
    }
    out["passed"] = all(out["gates"].values())
    qa_dir = run_dir / "qa"
    qa_dir.mkdir(exist_ok=True)
    (qa_dir / "score.json").write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    return out


def verify(run_dir: Path, rerun: bool = True) -> dict:
    """Check the audit chain and output hashes; optionally re-execute and compare byte-for-byte."""
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    ok_chain, head, n = verify_chain(run_dir / "audit" / "events.jsonl")
    report = {"run_id": manifest["run_id"], "event_log_intact": ok_chain and head == manifest["event_log"]["head_sha256"],
              "events": n}
    tampered = [f for f, h in manifest["outputs"].items()
                if not (run_dir / f).exists() or sha256_file(run_dir / f) != h]
    report["outputs_match_manifest"] = not tampered
    review_log = run_dir / "review" / "review_log.jsonl"
    if review_log.exists():
        ok_r, _h, n_r = verify_chain(review_log, anchor=manifest["event_log"]["head_sha256"])
        report["review_log_intact"] = ok_r
        report["review_events"] = n_r
    report["tampered_or_missing"] = tampered
    if rerun:
        from .pipeline import run

        with tempfile.TemporaryDirectory() as tmp:
            as_of = dt.date.fromisoformat(manifest["identity"]["as_of"])
            new_dir = run(Path(manifest["evidence_dir"]), Path(manifest["config_dir"]), Path(tmp), as_of)
            new_manifest = json.loads((new_dir / "manifest.json").read_text(encoding="utf-8"))
            same_id = new_manifest["run_id"] == manifest["run_id"]
            diff = sorted(f for f in set(manifest["outputs"]) | set(new_manifest["outputs"])
                          if manifest["outputs"].get(f) != new_manifest["outputs"].get(f))
            report["rerun"] = {"same_run_id": same_id, "byte_identical_outputs": not diff, "differing_files": diff,
                               "same_event_log_head": new_manifest["event_log"]["head_sha256"] == manifest["event_log"]["head_sha256"]}
    report["passed"] = report["event_log_intact"] and report["outputs_match_manifest"] and report.get("review_log_intact", True) and (
        not rerun or (report["rerun"]["byte_identical_outputs"] and report["rerun"]["same_event_log_head"]))
    return report
