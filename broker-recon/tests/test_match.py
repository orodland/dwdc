import random

from brokerrecon.match import Reconciler
from brokerrecon.model import Record

BASE = dict(product_type="FUT", account="A1", exchange="XCBT", root="ZC", contract_month="2027-12",
            side="BUY", quantity="10", price="442.25", trade_date="2026-11-02")


def rec(rid, origin, ref=None, aps=False, group=None, **over):
    d = dict(BASE, **over)
    return Record(record_id=rid, origin=origin, broker_id="B1", source_file="f", source_row=rid,
                  broker_ref=ref, aps_flag=aps, aps_group_id=group, internal_id=rid if origin == "INTERNAL" else None, **d)


def run(internal, broker, ref):
    r = Reconciler(ref)
    r.run(internal, broker, {"B1"}, set())
    return {x.record_id: (x.status, x.code) for x in internal + broker}, r


def test_ref_exact_and_conflict(config_dir):
    from brokerrecon.reference import load_reference
    ref = load_reference(config_dir)
    out, _ = run([rec("i1", "INTERNAL", "R1"), rec("i2", "INTERNAL", "R2")],
                 [rec("b1", "BROKER", "R1"), rec("b2", "BROKER", "R2", quantity="11")], ref)
    assert out["i1"] == out["b1"] == ("MATCHED", "T1_REF_EXACT")
    assert out["i2"] == out["b2"] == ("BREAK", "CONFLICTING_VALUES")


def test_fungible_groups_and_count_mismatch(config_dir):
    from brokerrecon.reference import load_reference
    ref = load_reference(config_dir)
    ints = [rec(f"i{k}", "INTERNAL") for k in range(2)] + [rec(f"j{k}", "INTERNAL", price="450") for k in range(3)]
    brks = [rec(f"b{k}", "BROKER", f"R{k}") for k in range(2)] + [rec(f"c{k}", "BROKER", f"S{k}", price="450") for k in range(2)]
    out, _ = run(ints, brks, ref)
    assert all(out[f"i{k}"] == ("MATCHED", "T2_KEY_EXACT") for k in range(2))
    assert all(out[f"j{k}"] == ("AMBIGUOUS", "GROUP_COUNT_MISMATCH") for k in range(3))
    assert all(out[f"c{k}"] == ("AMBIGUOUS", "GROUP_COUNT_MISMATCH") for k in range(2))


def test_internal_ref_never_key_matched_to_a_different_ref(config_dir):
    """Same economics but conflicting references must not be accepted as a match."""
    from brokerrecon.reference import load_reference
    ref = load_reference(config_dir)
    out, _ = run([rec("i1", "INTERNAL", "R1")], [rec("b1", "BROKER", "R9")], ref)
    assert out["i1"] == ("BREAK", "VALUE_BREAK")  # reported as a reference break, not matched


def test_single_field_break_and_residue(config_dir):
    from brokerrecon.reference import load_reference
    ref = load_reference(config_dir)
    out, r = run([rec("i1", "INTERNAL"), rec("i2", "INTERNAL", root="CL", exchange="XNYM", price="70")],
                 [rec("b1", "BROKER", "R1", price="442.5"), rec("b2", "BROKER", "R2", root="GC", exchange="XCEC", price="1")], ref)
    assert out["i1"] == out["b1"] == ("BREAK", "VALUE_BREAK")
    ex = next(e for e in r.exceptions if "i1" in e.record_ids)
    assert ex.diff_fields == ["price"]
    assert out["i2"] == ("UNMATCHED", "UNMATCHED_INTERNAL")
    assert out["b2"] == ("UNMATCHED", "UNMATCHED_BROKER")


def test_aps_group_exact_vwap(config_dir):
    from brokerrecon.reference import load_reference
    ref = load_reference(config_dir)
    fills = [rec("f1", "INTERNAL", group="G", quantity="10", price="442"),
             rec("f2", "INTERNAL", group="G", quantity="30", price="443")]
    line = rec("b1", "BROKER", "R1", aps=True, quantity="40", price="442.75")
    out, _ = run(fills, [line], ref)
    assert out["b1"] == out["f1"] == out["f2"] == ("MATCHED", "T3_APS_GROUP")
    bad = rec("b1", "BROKER", "R1", aps=True, quantity="40", price="442.7")
    out, _ = run([rec("f1", "INTERNAL", group="G", quantity="10", price="442"),
                  rec("f2", "INTERNAL", group="G", quantity="30", price="443")], [bad], ref)
    assert out["b1"] == ("BREAK", "APS_GROUP_BREAK")


def test_duplicates_and_not_comparable(config_dir):
    from brokerrecon.reference import load_reference
    ref = load_reference(config_dir)
    b_bad = rec("b3", "BROKER", "R3")
    b_bad.issues = [{"code": "MISSING_FIELD", "field": "price", "detail": "empty"}]
    out, r = run([rec("i1", "INTERNAL", "R1"), rec("i3", "INTERNAL", "R3")],
                 [rec("b1", "BROKER", "R1"), rec("b1x", "BROKER", "R1"), b_bad], ref)
    assert out["b1"] == out["b1x"] == out["i1"] == ("DUPLICATE", "DUPLICATE_RECORD")
    assert out["b3"] == ("NOT_COMPARABLE", "MISSING_FIELD")
    assert out["i3"] == ("NOT_COMPARABLE", "COUNTERPART_INCOMPLETE")
    ex = next(e for e in r.exceptions if e.code == "MISSING_FIELD")
    assert ex.record_ids == ["b3", "i3"]


def test_result_independent_of_input_order(config_dir):
    from brokerrecon.reference import load_reference
    ref = load_reference(config_dir)

    def build():
        ints = [rec(f"i{k}", "INTERNAL", f"R{k}" if k % 2 else None, quantity=str(k + 1)) for k in range(40)]
        brks = [rec(f"b{k}", "BROKER", f"R{k}", quantity=str(k + 1 + (k % 7 == 0))) for k in range(40)]
        return ints, brks
    a_i, a_b = build()
    out_a, _ = run(a_i, a_b, ref)
    b_i, b_b = build()
    random.Random(1).shuffle(b_i)
    random.Random(2).shuffle(b_b)
    out_b, _ = run(b_i, b_b, ref)
    assert out_a == out_b
