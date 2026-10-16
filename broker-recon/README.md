# broker-recon — prototype

A working proof-of-concept for **reconciling broker-confirmed open derivative trades
(commodity futures, options, FX forwards) to a client's internal trade list** as part of a
year-end audit. Built to the design in
[`reports/AI broker trade reconciliation.md`](../reports/AI%20broker%20trade%20reconciliation.md):

> **AI proposes, deterministic code decides.** AI is limited to onboarding new statement
> layouts (proposing a column mapping that a person approves). Every extracted value,
> every normalisation and every match status comes from versioned, rule-based code.

Everything runs on **synthetic data**: a generator creates a trade register, broker
statements in five deliberately different layouts, seeded breaks, and a ground-truth file.
No client or broker data is needed, and none is included.

> Status: prototype for discussion and proof-of-concept gates G1–G2 — not a certified audit
> tool. See *Limitations* below.

---

## Quick start

```bash
cd broker-recon
pip install -e ".[dev]"          # Python 3.11+
brokerrecon demo --out demo      # ~30 s: generate → reconcile → onboard new layout → re-run → score → verify
```

The demo ends with `DEMO RESULT: PASS` when every acceptance gate holds. Open
`demo/runs/run-<id>/review/review_pack.html` in a browser and `results/reconciliation.xlsx` in Excel.

Run the test suite with `pytest -q`.

## What the demo shows

| Step | What happens | What it demonstrates |
|---|---|---|
| 1 | Synthetic evidence for 6 brokers: Excel (2 layouts), native PDF without grid lines (multi-page, account sections, `442'2` eighths prices, `Z7` month codes), PDF with grid lines (European `1.250.000,00` numbers), CSV, and one broker that never replied | Format diversity; confirmation not received |
| 2 | First run | The CSV layout has no approved template → `FORMAT_UNRECOGNISED`; its broker's internal trades → `CONFIRMATION_NOT_PROCESSED`. Nothing is skipped silently |
| 3 | `onboard` proposes a template for the CSV, runs a self-test on it, and a reviewer approves it (approval stores a hash of the template) | AI/heuristic proposes, a person approves |
| 4 | Second run | All brokers reconciled |
| 5 | `score` against ground truth, `verify` | Zero false matches; every seeded break found with the right code; 100 % row completeness; byte-identical re-execution; intact audit chain |

## How the seven requirements are met

| Requirement | Mechanism in this prototype |
|---|---|
| **1. Accurate, complete extraction** | Template-driven parsers (openpyxl / pdfplumber / csv) copy text verbatim with its location. **Every cell is re-read by a second, independent parser** (PyMuPDF for PDF, raw XLSX XML for Excel); a disagreement makes the record `EXTRACTION_UNCERTAIN`. **Completeness controls:** row count and lot totals reconciled to the statement's own footer; `page n of m` sequence checked; *every* text line must be classified by the template, otherwise `UNCLASSIFIED_CONTENT` |
| **2. Deterministic matching, no invented data** | Waterfall of named rules (below). No tolerances, no fuzzy scores, no imputation; ambiguity is reported (`GROUP_COUNT_MISMATCH`, `AMBIGUOUS_CANDIDATES`), never resolved by the engine. Values are compared as exact decimals; nothing is rounded |
| **3. Complete audit trail** | Per record (`lineage/records.jsonl.gz` and the review pack): source file + SHA-256, page and bounding box or sheet!cell, raw text, independent re-read result, every transformation step (rule, input, output), match rule, counterpart record IDs, final status and exception ID. Run-level: hash-chained event log, manifest of input/config/output hashes |
| **4. Exceptions clearly identified** | Each record ends with exactly one status and one code; exceptions are grouped with their counterpart records (taxonomy below) and listed separately at document level |
| **5. Repeatable** | Run ID = hash of every input file, every approved template, reference data and engine/rule versions. Outputs contain no timestamps (those live in `execution.json`). `brokerrecon verify` re-executes and proves byte-identical outputs. The AI is never on the run path |
| **6. Standardised outputs** | Same CSV/XLSX/JSON structure for every broker and format (`results/`) |
| **7. Volume** | Exact-key hash grouping; see *Scale* below |

## Architecture

```
evidence/intake.yaml ─┐  (auditor-controlled register of confirmations received)
evidence/brokers/*  ──┼─► [A] evidence register: SHA-256, provenance check
evidence/internal/*  ─┘
                         [B] format routing: fingerprint → exactly one APPROVED template, else exception
                         [C] extraction (extract/): raw text + location for every cell
                         [D] independent re-read (extract/verify.py) + control totals + page sequence
                         [E] validation & normalisation (normalize.py): pure functions, every step logged
                         [F] deterministic matching (match.py): T0–T4 waterfall
                         [G] exceptions: one code per record, grouped with counterparts
                         [H] human review (review.py): HTML review pack + hash-chained dispositions
                         [I] audit trail (audit.py, pipeline.py): event log, lineage, manifest
                         [J] QA (qa.py): ground-truth scoring, tamper check, byte-identical re-run
```

### Where AI is used — and where it is not

| Component | Approach | Why |
|---|---|---|
| Onboarding a new statement layout | **AI (optional) or heuristic proposes** a template: column mapping, date/number conventions, side codes; ambiguous points are listed, not guessed. The proposal is self-tested on the file and must be **approved by a person** before use | Saves set-up effort; the output is configuration a reviewer can read, not a decision |
| Extraction of known layouts | Deterministic template parser | Repeatable and inspectable; no model in the run path |
| Validation / normalisation | Deterministic, versioned functions | Every transformation is explainable |
| Matching and status | Deterministic rules only | Requirement 2 |
| Exception disposition | Human reviewer | Professional judgement stays with the auditor |

`brokerrecon onboard FILE --broker-id X --ai` calls Claude (`claude-opus-5-5`) through the
Anthropic SDK with structured outputs. Only the header row and up to 8 sample rows are sent,
with reference and account values pseudonymised by default (`EB-0001234` → `XX-9999999`). The
proposal records the requested and served model, response ID, and prompt and response hashes.
Server-side model fallback is deliberately **not** enabled, so the model named in the
provenance is the one that answered. Without `--ai`, a local synonym-based heuristic does the
same job offline (that is what the demo uses).

### Matching rules (`match.py`)

| Tier | Rule | Outcome |
|---|---|---|
| T0 | Same broker reference more than once (on either side) | `DUPLICATE_RECORD` |
| T1 | Unique broker reference on both sides, **all** compare fields equal | **MATCHED** `T1_REF_EXACT` |
| — | Same reference, some fields differ | `CONFLICTING_VALUES` (fields named) |
| — | Same reference, one side unreadable | `MISSING_FIELD` / `EXTRACTION_UNCERTAIN` / `UNMAPPED_INSTRUMENT` + counterpart `COUNTERPART_INCOMPLETE` (one exception) |
| T2 | Internal trade without a broker reference; full economic key equal; equal group sizes (fungible lots) | **MATCHED** `T2_KEY_EXACT` — unequal sizes → `GROUP_COUNT_MISMATCH` |
| T3 | Broker average-price line vs exactly one internal fill group: same trade key, quantity sum equal, VWAP rounded half-even to the instrument's declared APS decimals equal | **MATCHED** `T3_APS_GROUP` — otherwise `APS_GROUP_BREAK` / `AMBIGUOUS_CANDIDATES` |
| T4 | Unique pair differing in exactly one field (incl. broker reference) | `VALUE_BREAK` (**not** a match) |
| — | Residue | `UNMATCHED_INTERNAL`, `UNMATCHED_BROKER` |

The compare fields are account, exchange (MIC), product root, contract month, put/call,
strike, side, quantity, price and trade date, or for FX: pair, side, notional, rate, trade
date and value date. A net-position check per account and instrument is reported alongside
in `positions.csv`.

### Document-level exceptions
`FORMAT_UNRECOGNISED`, `CONFIG_NOT_APPROVED` (including a template edited after approval:
hash mismatch), `PROVENANCE_UNVERIFIED` (file not in the intake register, or a layout and
sender mismatch), `COMPLETENESS_FAIL`, `UNCLASSIFIED_CONTENT`, plus `NO_CONFIRMATION_RECEIVED`
for brokers that did not reply.

## Outputs of a run (`runs/run-<id>/`)

```
results/  trades.csv  exceptions.csv  documents.csv  positions.csv  summary.json  reconciliation.xlsx
lineage/  records.jsonl.gz (full per-record lineage)  documents.jsonl (controls per document)
audit/    events.jsonl (hash-chained, no wall-clock time)
review/   review_pack.html, dispositions_template.csv, review_log.jsonl, exception_status.csv
manifest.json   run identity (all input/config/reference hashes), output hashes, event-log head
execution.json  wall-clock, host, user (deliberately excluded from output hashes)
qa/score.json   written by `brokerrecon score`
```

## Commands

```bash
brokerrecon generate --out demo --trades 3000 [--seed 7]              # synthetic evidence + truth
brokerrecon approve config/brokers/BRK_A.yaml --by "Name"             # sign off a template
brokerrecon run --evidence demo/evidence --config config --out runs   # reconcile
brokerrecon score runs/run-<id> --truth demo/truth/ground_truth.json   # acceptance gates
brokerrecon verify runs/run-<id>                                      # chain + hashes + byte-identical re-run
brokerrecon onboard demo/evidence/brokers/new.csv --broker-id BRK_X [--ai]
brokerrecon review template runs/run-<id>
brokerrecon review apply runs/run-<id> --file dispositions.csv --reviewer "Name"
```

Templates in `config/brokers/` ship as `status: proposed`; approve them before a run
(the `demo` command does this on a copy, as a synthetic reviewer).

## Results so far (synthetic)

| Check | Result |
|---|---|
| Unit and end-to-end tests | 31 passing |
| `demo` across seeds 7, 11, 23, 101 (2,500 trades each) | All gates pass: 0 false matches, 100 % seeded breaks with the correct code, 100 % row completeness, 100 % field accuracy, byte-identical re-run |
| Scale run | SCALE_RESULT |

Bugs the controls caught while this was being built, which is the point of having them:

- A synthetic PDF footer overlapped the page footer. The missing control total surfaced as `COMPLETENESS_FAIL`.
- `"12,5"` under a US number format was being read as 125. It is now `EXTRACTION_UNCERTAIN`.
- Excel stores numbers as binary doubles, and the raw XML can spell `64.46` as `64.45999999999999`. The independent re-read flagged this, so values are now compared as doubles and stored in the shortest round-trip decimal form.
- Two generator bugs: a mistyped reference that collided with a real reference, and a seeded FX price break hidden by display rounding. The ground-truth scorer caught both.

## Limitations and next steps

- **Scanned PDFs / images are not handled.** They need OCR or a vision model, run as a
  second independent extraction path with mandatory review. The interface for this (cells
  with location plus a verification flag) is in place.
- **Layouts:** one trade per text line; no wrapped rows; no position-only statements; no
  LME prompt dates; no give-up or allocation reports; no options on FX.
- **Reference data** is a small illustrative set. Production needs a maintained,
  versioned symbology and contract-specification source.
- **Synthetic truth is not real-world evidence.** Gate G3 (a parallel run on real
  confirmations next to the manual procedure) is still needed, as is firm methodology and
  tool certification (ISQM 1) before any reliance.
- **Data handling:** nothing leaves the machine unless `--ai` is used. Before using client
  data with any hosted model, resolve confidentiality, secrecy and cross-border transfer
  questions; the report has a Swiss-specific section.
- **Licences:** PyMuPDF is AGPL-3.0. Review it before any distribution, or replace it with
  another independent parser (for example pypdfium2).
