"""Deterministic matching waterfall.

No probabilities, no tolerances, no "best guess". A record is MATCHED only if
it satisfies one of three named rules; every other situation becomes an
exception with exactly one primary code. Ambiguity is never resolved by the
engine – it is reported.

  T0  duplicates            same broker reference appears more than once
  T1  REF_EXACT             unique broker reference on both sides and every
                            compare field identical
      (ref pair, fields differ)  -> CONFLICTING_VALUES (not a match)
  T2  KEY_EXACT             internal record without a broker reference whose
                            full economic key equals broker records; group
                            sizes must be equal (fungible lots), otherwise
                            GROUP_COUNT_MISMATCH
  T3  APS_GROUP             one broker average-price line vs exactly one
                            internal fill group: identical trade key, quantity
                            sum equal, VWAP rounded half-even to the
                            instrument's declared APS decimals equal
  T4  break detection       unique pair differing in exactly one field ->
                            VALUE_BREAK naming that field (not a match)
  --  residue               UNMATCHED_INTERNAL / UNMATCHED_BROKER
"""

from __future__ import annotations

from collections import defaultdict
from decimal import ROUND_HALF_EVEN, Decimal

from .hashing import short_id
from .model import (
    AMBIGUOUS_CANDIDATES, APS_GROUP_BREAK, APS_KEY_FIELDS, COMPARE_FIELDS, CONFIRMATION_NOT_PROCESSED,
    CONFLICTING_VALUES, COUNTERPART_INCOMPLETE, DUPLICATE_RECORD, GROUP_COUNT_MISMATCH,
    NO_CONFIRMATION_RECEIVED, STATUS_BY_CODE, T1_REF_EXACT, T2_KEY_EXACT, T3_APS_GROUP, UNMATCHED_BROKER,
    UNMATCHED_INTERNAL, VALUE_BREAK, ExceptionItem, Record,
)
from .reference import Reference

MATCHING_RULES_VERSION = "rules-1"
T4_FIELD_ORDER = ("broker_ref", "account", "exchange", "root", "contract_month", "put_call", "strike",
                  "ccy_pair", "side", "quantity", "price", "trade_date", "value_date")


class Reconciler:
    def __init__(self, ref: Reference):
        self.ref = ref
        self.exceptions: list[ExceptionItem] = []

    # ------------------------------------------------------------------ helpers
    def _assign(self, recs: list[Record], code: str, counterparts_of=None, detail: str = "",
                diff: list[str] | None = None, raise_exception: bool = True) -> None:
        ids = sorted(r.record_id for r in recs)
        status = STATUS_BY_CODE[code]
        ex_id = None
        if status == "MATCHED":
            group = short_id("MG", code, ids)
        else:
            group = None
            if raise_exception:
                ex_id = short_id("EX", code, ids)
                self.exceptions.append(ExceptionItem(
                    exception_id=ex_id, level="RECORD", code=code, status=status,
                    broker_id=recs[0].broker_id, record_ids=ids, diff_fields=list(diff or []), detail=detail,
                    source_file=next((r.source_file for r in recs if r.origin == "BROKER"), ""),
                ))
        for r in recs:
            r.status, r.code, r.rule_detail = status, code, detail
            r.match_group, r.exception_id = group, ex_id
            r.diff_fields = list(diff or [])
            other = counterparts_of(r) if counterparts_of else [x for x in recs if x.origin != r.origin]
            r.counterparts = sorted(x.record_id for x in other)

    @staticmethod
    def _diff(a: Record, b: Record) -> list[str]:
        if a.product_type != b.product_type:
            return ["product_type"]
        return [f for f in COMPARE_FIELDS[a.product_type] if getattr(a, f) != getattr(b, f)]

    # --------------------------------------------------------------------- main
    def run(self, internal: list[Record], broker: list[Record], processed: set[str], received_unprocessed: set[str]) -> None:
        internal = sorted(internal, key=lambda r: r.record_id)
        broker = sorted(broker, key=lambda r: r.record_id)

        # Duplicate internal identifiers are a data-integrity exception on the client list.
        by_iid = defaultdict(list)
        for r in internal:
            if r.internal_id:
                by_iid[r.internal_id].append(r)
        for iid, recs in by_iid.items():
            if len(recs) > 1:
                self._assign(recs, DUPLICATE_RECORD, counterparts_of=lambda r, recs=recs: [x for x in recs if x is not r],
                             detail=f"internal trade id {iid} appears {len(recs)} times in the internal list")

        int_by_broker = defaultdict(list)
        for r in internal:
            if r.status is None:
                int_by_broker[r.broker_id].append(r)
        brk_by_broker = defaultdict(list)
        for r in broker:
            brk_by_broker[r.broker_id].append(r)

        for b_id in sorted(set(int_by_broker) | set(brk_by_broker)):
            if b_id not in processed:
                for r in int_by_broker.get(b_id, []):
                    if not r.comparable:
                        self._issue_exception(r)
                    elif b_id in received_unprocessed:
                        self._assign([r], CONFIRMATION_NOT_PROCESSED, counterparts_of=lambda r: [],
                                     detail=f"a confirmation from {b_id} was received but could not be processed")
                    else:
                        self._assign([r], NO_CONFIRMATION_RECEIVED, counterparts_of=lambda r: [],
                                     detail=f"no confirmation received from broker {b_id}")
                continue
            self._reconcile_broker(int_by_broker.get(b_id, []), brk_by_broker.get(b_id, []))

        self.exceptions.sort(key=lambda e: (e.broker_id, e.code, e.exception_id))

    def _issue_exception(self, r: Record) -> None:
        first = r.issues[0]
        detail = "; ".join(f"{i['field']}: {i['detail']}" for i in r.issues)
        self._assign([r], first["code"], counterparts_of=lambda x: [], detail=detail,
                     diff=sorted({i["field"] for i in r.issues}))

    def _reconcile_broker(self, I: list[Record], B: list[Record]) -> None:
        # ---- T0 duplicates on broker reference (either side)
        refs_b = defaultdict(list)
        for r in B:
            if r.broker_ref:
                refs_b[r.broker_ref].append(r)
        refs_i = defaultdict(list)
        for r in I:
            if r.broker_ref:
                refs_i[r.broker_ref].append(r)
        for ref in sorted(set(refs_b) | set(refs_i)):
            bs, is_ = refs_b.get(ref, []), refs_i.get(ref, [])
            if len(bs) > 1 or len(is_) > 1:
                self._assign(bs + is_, DUPLICATE_RECORD,
                             counterparts_of=lambda r, grp=bs + is_: [x for x in grp if x is not r],
                             detail=f"broker reference {ref} appears {len(bs)}x on the statement and {len(is_)}x internally")

        # ---- T1 reference pairing
        for ref in sorted(set(refs_b) & set(refs_i)):
            bs, is_ = refs_b[ref], refs_i[ref]
            if len(bs) != 1 or len(is_) != 1:
                continue
            b, i = bs[0], is_[0]
            if not b.comparable or not i.comparable:
                # One exception covering both records: the reviewer sees the unreadable
                # broker row next to the internal trade it carries the reference of.
                bad, good = (b, i) if not b.comparable else (i, b)
                self._issue_exception(bad)
                ex = self.exceptions[-1]
                if good.comparable:
                    good.status, good.code = STATUS_BY_CODE[COUNTERPART_INCOMPLETE], COUNTERPART_INCOMPLETE
                    good.rule_detail = f"counterpart {bad.record_id} (same broker reference {ref}) could not be compared: {bad.code}"
                    good.exception_id = ex.exception_id
                else:
                    self._issue_exception(good)
                    self.exceptions.pop()
                    good.exception_id = ex.exception_id
                ex.record_ids = sorted([bad.record_id, good.record_id])
                bad.counterparts, good.counterparts = [good.record_id], [bad.record_id]
                continue
            diff = self._diff(i, b)
            if not diff:
                self._assign([i, b], T1_REF_EXACT, detail=f"broker reference {ref}; all compare fields equal")
            else:
                self._assign([i, b], CONFLICTING_VALUES, diff=diff,
                             detail=f"broker reference {ref} matches but {', '.join(diff)} differ")

        # Non-comparable leftovers each get their own exception.
        for r in I + B:
            if r.status is None and not r.comparable:
                self._issue_exception(r)

        I_r = [r for r in I if r.status is None]
        B_r = [r for r in B if r.status is None]

        # ---- T2 exact economic key (internal records without a broker reference)
        gi, gb = defaultdict(list), defaultdict(list)
        for r in I_r:
            if not r.broker_ref:
                gi[r.key()].append(r)
        for r in B_r:
            gb[r.key()].append(r)
        for k in sorted(set(gi) & set(gb), key=repr):
            ii, bb = gi[k], gb[k]
            if len(ii) == len(bb):
                self._assign(ii + bb, T2_KEY_EXACT,
                             detail=f"all compare fields equal; {len(ii)} internal vs {len(bb)} broker (fungible lots)" if len(ii) > 1 else "all compare fields equal")
            else:
                self._assign(ii + bb, GROUP_COUNT_MISMATCH,
                             detail=f"{len(ii)} internal vs {len(bb)} broker records with identical economics; engine will not choose")

        # ---- T3 average-price (APS) groups
        I_r = [r for r in I_r if r.status is None]
        B_r = [r for r in B_r if r.status is None]
        groups = defaultdict(list)
        for r in I_r:
            if r.aps_group_id:
                groups[r.aps_group_id].append(r)
        aps_index = defaultdict(list)
        for gid in sorted(groups):
            recs = groups[gid]
            keys = {(r.product_type,) + tuple(getattr(r, f) for f in APS_KEY_FIELDS) for r in recs}
            if len(keys) == 1:
                aps_index[keys.pop()].append(gid)
        aps_lines = [r for r in B_r if r.aps_flag]
        cands = {b.record_id: aps_index.get((b.product_type,) + tuple(getattr(b, f) for f in APS_KEY_FIELDS), []) for b in aps_lines}
        claims = defaultdict(list)
        for b in aps_lines:
            for gid in cands[b.record_id]:
                claims[gid].append(b)
        for b in aps_lines:
            c = cands[b.record_id]
            if not c:
                continue
            if len(c) > 1 or any(len(claims[g]) > 1 for g in c):
                involved = {b.record_id: b}
                for g in c:
                    for x in claims[g]:
                        involved[x.record_id] = x
                    for x in groups[g]:
                        involved[x.record_id] = x
                recs = [x for x in involved.values() if x.status is None]
                if recs:
                    self._assign(recs, AMBIGUOUS_CANDIDATES,
                                 detail=f"average-price line has {len(c)} candidate fill groups / groups claimed by several lines")
                continue
            fills = groups[c[0]]
            qty = sum(Decimal(f.quantity) for f in fills)
            vwap = sum(Decimal(f.quantity) * Decimal(f.price) for f in fills) / qty
            dp = self.ref.instruments[b.root].aps_price_decimals if b.root else 6
            vwap_r = vwap.quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_EVEN)
            diff = []
            if qty != Decimal(b.quantity):
                diff.append("quantity")
            if vwap_r != Decimal(b.price):
                diff.append("price")
            detail = (f"APS group {c[0]}: {len(fills)} fills, quantity {qty}, VWAP {vwap_r} "
                      f"(rounded half-even to {dp} dp) vs broker {b.quantity} @ {b.price}")
            self._assign([b] + fills, APS_GROUP_BREAK if diff else T3_APS_GROUP, diff=diff, detail=detail)

        # ---- T4 single-field break detection (never a match)
        for f in T4_FIELD_ORDER:
            I_r = [r for r in I_r if r.status is None]
            B_r = [r for r in B_r if r.status is None]
            mi, mb = defaultdict(list), defaultdict(list)

            def kf(r: Record):
                fields = COMPARE_FIELDS[r.product_type]
                if f != "broker_ref" and f not in fields:
                    return None
                return (r.product_type,) + tuple(getattr(r, g) for g in fields if g != f)
            for r in I_r:
                if (k := kf(r)) is not None:
                    mi[k].append(r)
            for r in B_r:
                if (k := kf(r)) is not None:
                    mb[k].append(r)
            for k in sorted(set(mi) & set(mb), key=repr):
                if len(mi[k]) != 1 or len(mb[k]) != 1:
                    continue
                i, b = mi[k][0], mb[k][0]
                diff = self._diff(i, b)
                refs_conflict = bool(i.broker_ref and b.broker_ref and i.broker_ref != b.broker_ref)
                if f == "broker_ref":
                    ok = not diff and (refs_conflict or bool(i.broker_ref))
                    diff = ["broker_ref"]
                else:
                    ok = diff == [f] and not refs_conflict
                if ok:
                    self._assign([i, b], VALUE_BREAK, diff=diff,
                                 detail=f"unique counterpart differs only in {diff[0]}: internal {getattr(i, diff[0])!r} vs broker {getattr(b, diff[0])!r}")

        # ---- residue
        for r in I:
            if r.status is None:
                d = f"broker reference {r.broker_ref} not found on the statement" if r.broker_ref else "no counterpart on the broker statement"
                self._assign([r], UNMATCHED_INTERNAL, counterparts_of=lambda x: [], detail=d)
        for r in B:
            if r.status is None:
                self._assign([r], UNMATCHED_BROKER, counterparts_of=lambda x: [], detail="no counterpart in the internal trade list")


def positions(internal: list[Record], broker: list[Record], processed: set[str]) -> list[dict]:
    """Net open position per broker/account/instrument from comparable records (BUY +, SELL -)."""
    def pkey(r: Record):
        if r.product_type == "FXFWD":
            return (r.broker_id, r.account, r.product_type, r.ccy_pair, r.value_date, "", "")
        return (r.broker_id, r.account, r.product_type, r.root, r.contract_month, r.put_call or "", r.strike or "")
    agg = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for side, recs in ((0, internal), (1, broker)):
        for r in recs:
            if r.broker_id in processed and r.comparable and r.quantity and r.side:
                q = Decimal(r.quantity) * (1 if r.side == "BUY" else -1)
                agg[pkey(r)][side] += q
    out = []
    for k in sorted(agg, key=repr):
        i, b = agg[k]
        out.append({
            "broker_id": k[0], "account": k[1], "product_type": k[2], "instrument": k[3], "period": k[4],
            "put_call": k[5], "strike": k[6], "internal_net": format(i.normalize(), "f"),
            "broker_net": format(b.normalize(), "f"), "difference": format((i - b).normalize(), "f"),
            "status": "AGREED" if i == b else "POSITION_BREAK",
        })
    return out
