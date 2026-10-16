"""Human review: a self-contained HTML review pack, and reviewer dispositions.

The review pack is source-first: for every exception it shows the source
location (with a highlighted image of the PDF row where available), the raw
values, every transformation applied, and the counterpart record side by side
with differing fields highlighted.

Dispositions are recorded as new, hash-chained events anchored to the run's
event log. They never modify machine results.
"""

from __future__ import annotations

import base64
import csv
import datetime as dt
import html
import io
import json
from pathlib import Path

from .audit import append_events
from .hashing import canonical_json
from .model import ExceptionItem, Record

DISPOSITIONS = {
    "RESOLVED_TIMING_DIFFERENCE": "Explained timing difference, corroborated",
    "RESOLVED_CLIENT_BOOKING_ERROR": "Client booking error confirmed - evaluate for misstatement",
    "RESOLVED_BROKER_ERROR": "Broker statement error confirmed with broker",
    "RESOLVED_SOURCE_VALUE_CONFIRMED": "Reviewer read the value from the source document",
    "RESOLVED_NO_ISSUE": "No issue after investigation",
    "ESCALATED_FURTHER_WORK": "Further audit work required",
    "POTENTIAL_MISSTATEMENT": "Potential misstatement - escalate to engagement leadership",
}
NEEDS_EVIDENCE = {k for k in DISPOSITIONS if k.startswith("RESOLVED")}
MAX_IMAGES = 400
MAX_TRADES_LISTED = 3000

DISPLAY_FIELDS = ("product_type", "account", "exchange", "root", "contract_month", "put_call", "strike", "ccy_pair",
                  "value_date", "side", "quantity", "price", "trade_date", "broker_ref", "aps_group_id", "internal_id")


def _snippet(evidence_dir: Path, rec: Record, cache: dict) -> str | None:
    """PNG (base64) of the PDF row band with the record's cells outlined."""
    boxes = [(v["loc"]["page"], v["loc"]["bbox"], k) for k, v in rec.raw.items()
             if "bbox" in v["loc"] and not v["loc"].get("section_line")]
    if not boxes:
        return None
    import pymupdf
    from PIL import Image, ImageDraw

    page_no = boxes[0][0]
    path = evidence_dir / rec.source_file
    if path not in cache:
        cache[path] = pymupdf.open(path)
    page = cache[path][page_no - 1]
    top = min(b[1][1] for b in boxes) - 16
    bottom = max(b[1][3] for b in boxes) + 6
    clip = pymupdf.Rect(20, top, page.rect.width - 20, bottom)
    zoom = 2.0
    pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    draw = ImageDraw.Draw(img)
    for _p, (x0, y0, x1, y1), fld in boxes:
        hot = fld in rec.diff_fields or any(i["field"] == fld for i in rec.issues)
        draw.rectangle([(x0 - 20 - 1.5) * zoom, (y0 - top - 1.5) * zoom, (x1 - 20 + 1.5) * zoom, (y1 - top + 1.5) * zoom],
                       outline=(208, 52, 44) if hot else (37, 99, 235), width=3 if hot else 1)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def build_review_pack(run_dir: Path, evidence_dir: Path, records: list[Record], exceptions: list[ExceptionItem],
                      doc_rows: list[dict], summary: dict) -> Path:
    by_id = {r.record_id: r for r in records}
    involved = sorted({rid for e in exceptions for rid in e.record_ids})
    cache: dict = {}
    images = {}
    for rid in involved:
        r = by_id[rid]
        if r.origin == "BROKER" and r.source_file.endswith(".pdf") and len(images) < MAX_IMAGES:
            img = _snippet(evidence_dir, r, cache)
            if img:
                images[rid] = img
    for d in cache.values():
        d.close()

    def rec_json(r: Record) -> dict:
        return {
            "id": r.record_id, "origin": r.origin, "broker": r.broker_id, "status": r.status, "code": r.code,
            "detail": r.rule_detail, "counterparts": r.counterparts, "diff": r.diff_fields, "file": r.source_file,
            "row": r.source_row, "fields": {f: getattr(r, f) for f in DISPLAY_FIELDS},
            "raw": r.raw, "steps": [s.__dict__ for s in r.steps], "issues": r.issues, "img": images.get(r.record_id),
        }

    detail_ids = set(involved)
    for rid in involved:
        detail_ids.update(by_id[rid].counterparts)
    data = {
        "summary": summary,
        "documents": doc_rows,
        "exceptions": [e.__dict__ for e in exceptions],
        "records": {rid: rec_json(by_id[rid]) for rid in sorted(detail_ids)},
        "trades": [[r.record_id, r.origin, r.broker_id, r.status, r.code, r.product_type or "", r.root or r.ccy_pair or "",
                    r.side or "", r.quantity or "", r.price or "", r.trade_date or ""] for r in records[:MAX_TRADES_LISTED]],
        "trades_total": len(records),
        "dispositions": DISPOSITIONS,
    }
    payload = canonical_json(data).replace("</", "<\\/")
    page = _TEMPLATE.replace("__DATA__", payload).replace("__RUN__", html.escape(summary["run_id"]))
    out = run_dir / "review" / "review_pack.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


def write_template(run_dir: Path) -> Path:
    src = run_dir / "results" / "exceptions.csv"
    out = run_dir / "review" / "dispositions_template.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(src, encoding="utf-8", newline="") as fi, open(out, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, lineterminator="\n")
        w.writerow(["exception_id", "code", "broker_id", "detail", "disposition", "comment", "evidence_reference"])
        for row in csv.DictReader(fi):
            w.writerow([row["exception_id"], row["code"], row["broker_id"], row["detail"], "", "", ""])
    return out


def apply_dispositions(run_dir: Path, file: Path, reviewer: str) -> dict:
    if not reviewer:
        raise SystemExit("--reviewer is required")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    known = {}
    with open(run_dir / "results" / "exceptions.csv", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            known[row["exception_id"]] = row
    events, errors = [], []
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    with open(file, encoding="utf-8", newline="") as fh:
        for n, row in enumerate(csv.DictReader(fh), start=2):
            disp = (row.get("disposition") or "").strip()
            if not disp:
                continue
            eid = row["exception_id"].strip()
            if eid not in known:
                errors.append(f"line {n}: unknown exception id {eid}")
                continue
            if disp not in DISPOSITIONS:
                errors.append(f"line {n}: unknown disposition {disp!r}")
                continue
            if not (row.get("comment") or "").strip():
                errors.append(f"line {n}: a comment is required")
                continue
            if disp in NEEDS_EVIDENCE and not (row.get("evidence_reference") or "").strip():
                errors.append(f"line {n}: {disp} requires an evidence_reference")
                continue
            events.append(("REVIEW_DISPOSITION", {
                "exception_id": eid, "exception_code": known[eid]["code"], "disposition": disp,
                "comment": row["comment"].strip(), "evidence_reference": (row.get("evidence_reference") or "").strip(),
                "reviewer": reviewer, "recorded_utc": now,
            }))
    if errors:
        return {"applied": 0, "errors": errors}
    log = run_dir / "review" / "review_log.jsonl"
    head = append_events(log, events, anchor=manifest["event_log"]["head_sha256"])
    latest = {}
    for line in log.read_text(encoding="utf-8").splitlines():
        ev = json.loads(line)
        latest[ev["data"]["exception_id"]] = ev["data"]
    with open(run_dir / "review" / "exception_status.csv", "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo, lineterminator="\n")
        w.writerow(["exception_id", "code", "broker_id", "review_status", "disposition", "reviewer", "recorded_utc", "comment", "evidence_reference"])
        for eid, row in known.items():
            d = latest.get(eid)
            w.writerow([eid, row["code"], row["broker_id"], "OPEN" if not d else ("CLOSED" if d["disposition"].startswith("RESOLVED") else "ESCALATED"),
                        d["disposition"] if d else "", d["reviewer"] if d else "", d["recorded_utc"] if d else "",
                        d["comment"] if d else "", d["evidence_reference"] if d else ""])
    open_n = sum(1 for e in known if e not in latest or not latest[e]["disposition"].startswith("RESOLVED"))
    return {"applied": len(events), "review_log_head": head, "exceptions_total": len(known), "not_closed": open_n, "errors": []}


_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Reconciliation review pack</title>
<style>
:root{--bg:#f7f7f5;--panel:#fff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e3e2dd;--accent:#2563eb;--bad:#c2410c;--bad-bg:#fff1e8;--ok:#15803d;--ok-bg:#ecfdf3;--warn:#a16207;--warn-bg:#fef9e7;--chip:#efefea;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#141413;--panel:#1d1d1b;--ink:#ecebe6;--muted:#a3a29c;--line:#34332f;--accent:#7aa2ff;--bad:#ff8a5c;--bad-bg:#3a2016;--ok:#5ad08a;--ok-bg:#15301f;--warn:#e6c25a;--warn-bg:#352c12;--chip:#2a2926}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:20px 24px 8px}h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 8px}.sub{color:var(--muted);font-size:13px}
main{padding:0 24px 40px;max-width:1500px}.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:12px 0}
.tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px}.tile b{display:block;font-size:22px;font-variant-numeric:tabular-nums}.tile span{color:var(--muted);font-size:12px}
.tabs{display:flex;gap:6px;margin:16px 0 10px;flex-wrap:wrap}.tabs button{border:1px solid var(--line);background:var(--panel);color:var(--ink);padding:6px 12px;border-radius:999px;cursor:pointer}.tabs button.on{background:var(--ink);color:var(--bg)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:auto}
table{border-collapse:collapse;width:100%}th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:13px}th{position:sticky;top:0;background:var(--panel);color:var(--muted);font-weight:600}
td.num{font-variant-numeric:tabular-nums;font-family:var(--mono);font-size:12px}tr.click{cursor:pointer}tr.click:hover{background:var(--chip)}tr.sel{background:var(--chip)}
.chip{display:inline-block;padding:1px 8px;border-radius:999px;background:var(--chip);font-size:12px;white-space:nowrap}.chip.bad{background:var(--bad-bg);color:var(--bad)}.chip.ok{background:var(--ok-bg);color:var(--ok)}.chip.warn{background:var(--warn-bg);color:var(--warn)}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}select,input{background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:6px 8px}
.split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.25fr);gap:12px}@media(max-width:1000px){.split{grid-template-columns:1fr}}
.detail{padding:14px 16px}.detail h3{margin:0 0 6px;font-size:15px}.cmp td.diff{background:var(--bad-bg);color:var(--bad);font-weight:600}
.snip{max-width:100%;border:1px solid var(--line);border-radius:6px;margin:6px 0;background:#fff}.kv{font-family:var(--mono);font-size:12px;color:var(--muted)}
details{margin:6px 0}summary{cursor:pointer;color:var(--accent)}.muted{color:var(--muted)}.list{max-height:70vh;overflow:auto}
</style></head><body>
<header><h1>Broker confirmation reconciliation &mdash; review pack</h1>
<div class="sub">Run <code>__RUN__</code> &middot; synthetic prototype &middot; deterministic outputs: every status below comes from a named rule; AI never decides a match.</div></header>
<main>
<div class="tiles" id="tiles"></div>
<div class="tabs" id="tabs"></div>
<section id="view"></section>
</main>
<script type="application/json" id="data">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const $=s=>document.querySelector(s);const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const chipFor=c=>{if(!c)return'';if(/^T[123]_/.test(c))return`<span class="chip ok">${c}</span>`;if(/UNMATCHED|BREAK|CONFLICT|MISMATCH|DUPLICATE|AMBIG|FAIL|UNRECOG|NOT_APPROVED|UNVERIFIED|NO_CONFIRMATION/.test(c))return`<span class="chip bad">${c}</span>`;return`<span class="chip warn">${c}</span>`};
const S=D.summary;const I=S.records.INTERNAL,B=S.records.BROKER;
const tile=(v,l)=>`<div class="tile"><b>${v}</b><span>${l}</span></div>`;
$('#tiles').innerHTML=tile(I.records.toLocaleString(),'internal open trades')+tile(B.records.toLocaleString(),'broker-confirmed rows')+
 tile(((I.by_status.MATCHED||0)/I.records*100).toFixed(1)+'%','internal trades matched by rule')+tile(S.exceptions.total.toLocaleString(),'exceptions to review')+
 tile(Object.values(S.exceptions.document_level).reduce((a,b)=>a+b,0),'document-level exceptions')+tile(D.documents.length,'documents registered');
const tabs=[['ex','Exceptions'],['docs','Documents & controls'],['trades','All trades'],['codes','Summary by code']];let cur='ex';
function drawTabs(){$('#tabs').innerHTML=tabs.map(([k,l])=>`<button class="${k==cur?'on':''}" data-k="${k}">${l}</button>`).join('');document.querySelectorAll('#tabs button').forEach(b=>b.onclick=()=>{cur=b.dataset.k;drawTabs();draw()})}
function draw(){({ex:drawEx,docs:drawDocs,trades:drawTrades,codes:drawCodes})[cur]()}
let fCode='',fBroker='',fText='',selected=null;
function drawEx(){const codes=[...new Set(D.exceptions.map(e=>e.code))].sort(),brokers=[...new Set(D.exceptions.map(e=>e.broker_id))].sort();
 const rows=D.exceptions.filter(e=>(!fCode||e.code==fCode)&&(!fBroker||e.broker_id==fBroker)&&(!fText||(e.detail+e.record_ids.join(' ')+e.exception_id).toLowerCase().includes(fText)));
 $('#view').innerHTML=`<div class="filters"><select id="fc"><option value="">All codes (${D.exceptions.length})</option>${codes.map(c=>`<option ${c==fCode?'selected':''}>${c}</option>`).join('')}</select>
 <select id="fb"><option value="">All brokers</option>${brokers.map(c=>`<option ${c==fBroker?'selected':''}>${c}</option>`).join('')}</select><input id="ft" placeholder="search id / detail" value="${esc(fText)}"><span class="muted" style="align-self:center">${rows.length} shown</span></div>
 <div class="split"><div class="panel list"><table><thead><tr><th>Exception</th><th>Code</th><th>Broker</th><th>Detail</th></tr></thead><tbody>${rows.map(e=>`<tr class="click ${e.exception_id==selected?'sel':''}" data-id="${e.exception_id}"><td class="num">${e.exception_id}</td><td>${chipFor(e.code)}</td><td>${esc(e.broker_id)}</td><td>${esc(e.detail).slice(0,140)}</td></tr>`).join('')}</tbody></table></div>
 <div class="panel detail" id="det"><p class="muted">Select an exception to see source evidence, transformations and the counterpart record.</p></div></div>`;
 $('#fc').onchange=e=>{fCode=e.target.value;drawEx()};$('#fb').onchange=e=>{fBroker=e.target.value;drawEx()};$('#ft').oninput=e=>{fText=e.target.value.toLowerCase();clearTimeout(window._t);window._t=setTimeout(drawEx,250)};
 document.querySelectorAll('tr.click').forEach(tr=>tr.onclick=()=>{selected=tr.dataset.id;document.querySelectorAll('tr.sel').forEach(x=>x.classList.remove('sel'));tr.classList.add('sel');showEx(selected)});if(selected)showEx(selected)}
function locText(l){if(l.cell)return`${l.sheet}!${l.cell}`;if(l.bbox)return`page ${l.page}, bbox [${l.bbox.map(v=>v.toFixed(0)).join(', ')}]`;if(l.line)return`line ${l.line}`;return l.rule?`(${l.rule})`:'(none)'}
function recBlock(r){const raw=Object.entries(r.raw).map(([k,v])=>`<tr><td>${k}</td><td class="num">${esc(v.raw)}</td><td class="kv">${esc(locText(v.loc))}</td><td>${v.verified===true?'<span class="chip ok">re-read ✓</span>':v.verified===false?'<span class="chip bad">re-read ✗ '+esc(v.loc.reread)+'</span>':'<span class="muted">n/a</span>'}</td></tr>`).join('');
 const steps=r.steps.map(s=>`<tr><td>${s.field}</td><td class="kv">${esc(s.rule)}</td><td class="num">${esc(s.input)}</td><td class="num">${esc(s.output)}</td></tr>`).join('');
 return`<details ${r.origin=='BROKER'?'open':''}><summary>${r.origin} record <code>${esc(r.id)}</code> &middot; ${esc(r.file)} :: ${esc(r.row)} ${chipFor(r.code)}</summary>
 ${r.img?`<img class="snip" alt="source row" src="data:image/png;base64,${r.img}">`:''}
 ${r.issues.length?`<p>${r.issues.map(i=>`<span class="chip bad">${i.code}</span> <b>${i.field}</b>: ${esc(i.detail)}`).join('<br>')}</p>`:''}
 <table><thead><tr><th>Field</th><th>Raw value</th><th>Source location</th><th>Independent re-read</th></tr></thead><tbody>${raw}</tbody></table>
 <h3 style="margin-top:10px">Transformations</h3><table><thead><tr><th>Field</th><th>Rule</th><th>Input</th><th>Output</th></tr></thead><tbody>${steps||'<tr><td colspan=4 class="muted">none</td></tr>'}</tbody></table></details>`}
function showEx(id){const e=D.exceptions.find(x=>x.exception_id==id);const recs=e.record_ids.map(r=>D.records[r]).filter(Boolean);
 const ints=recs.filter(r=>r.origin=='INTERNAL'),brks=recs.filter(r=>r.origin=='BROKER');let cmp='';
 if(recs.length){const cols=[...ints,...brks];const fields=Object.keys(cols[0].fields).filter(f=>cols.some(c=>c.fields[f]!=null&&c.fields[f]!==''));
  cmp=`<table class="cmp"><thead><tr><th>Field</th>${cols.map(c=>`<th>${c.origin}<br><span class="kv">${esc(c.id)}</span></th>`).join('')}</tr></thead><tbody>${fields.map(f=>{const vals=cols.map(c=>c.fields[f]);const d=e.diff_fields.includes(f);return`<tr><td>${f}</td>${vals.map(v=>`<td class="num ${d?'diff':''}">${esc(v)}</td>`).join('')}</tr>`}).join('')}</tbody></table>`}
 $('#det').innerHTML=`<h3>${chipFor(e.code)} <code>${e.exception_id}</code></h3><p>${esc(e.detail)}</p>
 <p class="kv">level ${e.level} &middot; status ${e.status} &middot; broker ${esc(e.broker_id)} ${e.source_file?'&middot; '+esc(e.source_file):''}</p>${cmp}${recs.map(recBlock).join('')}
 <h3 style="margin-top:14px">Record a disposition</h3><p class="muted">Use <code>brokerrecon review template</code>, fill a disposition for <code>${e.exception_id}</code> with a comment (and evidence reference when resolving), then <code>brokerrecon review apply</code>. Allowed: ${Object.keys(D.dispositions).map(k=>`<code>${k}</code>`).join(', ')}.</p>`}
function drawDocs(){$('#view').innerHTML=`<div class="panel"><table><thead><tr><th>File</th><th>Broker</th><th>Status</th><th>Template</th><th>Rows extracted / declared</th><th>Qty extracted / declared</th><th>Cells re-read ✓ / ✗</th><th>Issues</th></tr></thead><tbody>${D.documents.map(d=>`<tr><td>${esc(d.file)}<div class="kv">${d.sha256.slice(0,16)}…</div></td><td>${esc(d.broker_id)}</td><td>${chipFor(d.status=='PROCESSED'?'T1_OK':d.status)}</td><td class="kv">${esc(d.config_id)}</td><td class="num">${d.rows_extracted} / ${esc(d.rows_declared)}</td><td class="num">${esc(d.quantity_extracted)} / ${esc(d.quantity_declared)}</td><td class="num">${d.cells_verified} / ${d.cells_unverified}</td><td>${esc(d.issues)}</td></tr>`).join('')}</tbody></table></div>`.replace('T1_OK','PROCESSED')}
let tText='';function drawTrades(){const rows=D.trades.filter(t=>!tText||t.join(' ').toLowerCase().includes(tText)).slice(0,1500);
 $('#view').innerHTML=`<div class="filters"><input id="tt" placeholder="filter trades" value="${esc(tText)}"><span class="muted" style="align-self:center">${D.trades_total.toLocaleString()} records in run${D.trades.length<D.trades_total?' (first '+D.trades.length+' embedded; see results/trades.csv)':''}; showing ${rows.length}</span></div>
 <div class="panel list"><table><thead><tr><th>Record</th><th>Origin</th><th>Broker</th><th>Status</th><th>Code</th><th>Type</th><th>Instrument</th><th>Side</th><th>Qty</th><th>Price</th><th>Trade date</th></tr></thead><tbody>${rows.map(t=>`<tr><td class="num">${esc(t[0])}</td><td>${t[1]}</td><td>${t[2]}</td><td>${t[3]}</td><td>${chipFor(t[4])}</td><td>${t[5]}</td><td>${t[6]}</td><td>${t[7]}</td><td class="num">${t[8]}</td><td class="num">${t[9]}</td><td class="num">${t[10]}</td></tr>`).join('')}</tbody></table></div>`;
 $('#tt').oninput=e=>{tText=e.target.value.toLowerCase();clearTimeout(window._t);window._t=setTimeout(drawTrades,250)}}
function drawCodes(){const block=(t,o)=>`<h2>${t}</h2><div class="panel"><table><thead><tr><th>Code</th><th>Count</th></tr></thead><tbody>${Object.entries(o).map(([k,v])=>`<tr><td>${chipFor(k)}</td><td class="num">${v}</td></tr>`).join('')}</tbody></table></div>`;
 $('#view').innerHTML=block('Internal records by code',I.by_code)+block('Broker records by code',B.by_code)+block('Document-level exceptions',S.exceptions.document_level)+block('Net positions',S.positions)}
drawTabs();draw();
</script></body></html>
"""
