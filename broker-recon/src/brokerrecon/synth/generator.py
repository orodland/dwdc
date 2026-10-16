"""Generate a synthetic internal trade register, broker statements in several
layouts (Excel, native PDF with and without grid lines, CSV), seeded breaks,
and a ground-truth file describing the expected outcome of every record.

Ground truth is written outside the evidence folder; the engine never reads it.
"""

from __future__ import annotations

import datetime as dt
import json
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

import yaml

from ..model import COMPARE_FIELDS

AS_OF = dt.date(2026, 12, 31)

PRICE_LEVEL = {"ZC": "450", "ZW": "560", "ZS": "1050", "CL": "70", "NG": "3.2", "B": "75", "KC": "250",
               "SB": "20", "GC": "2400", "HG": "4.5"}
TICK = {"ZC": "0.25", "ZW": "0.25", "ZS": "0.25", "CL": "0.01", "NG": "0.001", "B": "0.01", "KC": "0.05",
        "SB": "0.01", "GC": "0.1", "HG": "0.0005"}
STRIKE_STEP = {"ZC": "10", "CL": "1", "B": "1", "GC": "10"}
APS_DP = {"ZC": 4, "ZW": 4, "ZS": 4, "CL": 4, "NG": 5, "B": 4, "KC": 4, "SB": 4, "GC": 3, "HG": 5}
FX_LEVEL = {"EURUSD": ("1.085", 5), "USDCHF": ("0.885", 5), "GBPUSD": ("1.265", 5), "USDJPY": ("151.2", 3),
            "AUDUSD": ("0.655", 5)}
FUT_ROOTS = ["ZC", "ZW", "ZS", "CL", "NG", "B", "KC", "SB", "GC", "HG"]
OPT_ROOTS = ["ZC", "CL", "B", "GC"]


@dataclass(frozen=True)
class BrokerSpec:
    broker_id: str
    share: float
    products: tuple[str, ...]
    accounts: tuple[str, ...]
    ref_prefix: str
    internal_ref_rate: float = 0.85
    statement: bool = True


BROKERS = (
    BrokerSpec("BRK_A", 0.30, ("FUT", "OPT"), ("A-10021", "A-10022"), "AF"),
    BrokerSpec("BRK_B", 0.25, ("FUT", "OPT", "FXFWD"), ("BRV-501", "BRV-502", "BRV-503"), "BC"),
    BrokerSpec("BRK_C", 0.20, ("FUT", "OPT"), ("7781-AX", "7781-BX"), "CM"),
    BrokerSpec("BRK_D", 0.10, ("FXFWD",), ("DFX-01", "DFX-02"), "DX"),
    BrokerSpec("BRK_E", 0.10, ("FUT",), ("E-9001",), "EB"),
    BrokerSpec("BRK_F", 0.05, ("FUT",), ("F-77",), "FF", statement=False),
)


@dataclass
class Trade:
    internal_id: str
    broker_id: str
    account: str
    product_type: str
    side: str
    quantity: Decimal
    price: Decimal
    trade_date: dt.date
    broker_ref: str
    internal_has_ref: bool
    root: str | None = None
    contract_month: str | None = None
    put_call: str | None = None
    strike: Decimal | None = None
    ccy_pair: str | None = None
    value_date: dt.date | None = None
    aps_group_id: str | None = None

    def canon(self) -> dict:
        def d(x):
            if x is None:
                return None
            if isinstance(x, Decimal):
                s = format(x.normalize(), "f")
                return "0" if s == "-0" else s
            if isinstance(x, dt.date):
                return x.isoformat()
            return x
        exch = {"ZC": "XCBT", "ZW": "XCBT", "ZS": "XCBT", "CL": "XNYM", "NG": "XNYM", "B": "IFEU", "KC": "IFUS",
                "SB": "IFUS", "GC": "XCEC", "HG": "XCEC"}
        out = {
            "product_type": self.product_type, "account": self.account, "side": self.side,
            "quantity": d(self.quantity), "price": d(self.price), "trade_date": d(self.trade_date),
            "root": self.root, "exchange": exch.get(self.root) if self.root else None,
            "contract_month": self.contract_month, "put_call": self.put_call, "strike": d(self.strike),
            "ccy_pair": self.ccy_pair, "value_date": d(self.value_date),
        }
        return out

    def key(self, drop: str | None = None) -> tuple:
        c = self.canon()
        return (self.product_type,) + tuple(c[f] for f in COMPARE_FIELDS[self.product_type] if f != drop)


@dataclass
class BrokerRow:
    trade: Trade  # economic values as the broker shows them
    broker_ref: str
    aps_flag: bool = False
    overrides: dict[str, str] = field(default_factory=dict)  # field -> raw text to render instead
    truth_internal: list[str] = field(default_factory=list)
    expect: tuple[str, str] = ("MATCHED", "T1_REF_EXACT")
    scenario: str = "normal"


class Generator:
    def __init__(self, n_trades: int, seed: int = 7, break_rate: float = 0.004):
        self.rng = random.Random(seed)
        self.n = n_trades
        self.break_rate = break_rate
        self.trades: list[Trade] = []
        self.rows: dict[str, list[BrokerRow]] = defaultdict(list)
        self.internal_expect: dict[str, tuple[str, str]] = {}
        self.internal_expect_pre: dict[str, tuple[str, str]] = {}
        self.seeded: list[dict] = []
        self._keys: set[tuple] = set()
        self._near: dict[str, set[tuple]] = defaultdict(set)
        self._near_count: dict[str, Counter] = {}
        self._ref_seq = 0
        self._iid_seq = 0

    # ----------------------------------------------------------------- primitives
    def _ref(self, spec: BrokerSpec) -> str:
        self._ref_seq += 1
        return f"{spec.ref_prefix}-{self._ref_seq:07d}"

    def _iid(self) -> str:
        self._iid_seq += 1
        return f"T{self._iid_seq:08d}"

    def _date(self) -> dt.date:
        while True:
            d = dt.date(2026, 1, 5) + dt.timedelta(days=self.rng.randrange(0, 360))
            if d.weekday() < 5 and d <= AS_OF:
                return d

    def _on_tick(self, level: str, tick: str, spread: float = 0.15) -> Decimal:
        lv, tk = Decimal(level), Decimal(tick)
        steps = int((lv * Decimal(str(spread))) / tk)
        return (lv / tk).to_integral_value() * tk + tk * self.rng.randint(-steps, steps)

    def _random_trade(self, spec: BrokerSpec, product: str | None = None) -> Trade:
        product = product or self.rng.choice(spec.products)
        side = self.rng.choice(["BUY", "SELL"])
        acct = self.rng.choice(spec.accounts)
        td = self._date()
        has_ref = self.rng.random() < spec.internal_ref_rate
        base = dict(internal_id=self._iid(), broker_id=spec.broker_id, account=acct, product_type=product,
                    side=side, trade_date=td, broker_ref=self._ref(spec), internal_has_ref=has_ref)
        if product == "FXFWD":
            pair = self.rng.choice(sorted(FX_LEVEL))
            lvl, dp = FX_LEVEL[pair]
            rate = self._on_tick(lvl, str(Decimal(1).scaleb(-dp)), 0.05)
            vd = td + dt.timedelta(days=self.rng.randrange(30, 380))
            while vd.weekday() >= 5 or vd <= AS_OF:
                vd += dt.timedelta(days=1)
            notional = Decimal(50000) * self.rng.randint(2, 500)
            return Trade(**base, quantity=notional, price=rate, ccy_pair=pair, value_date=vd)
        roots = OPT_ROOTS if product == "OPT" else FUT_ROOTS
        root = self.rng.choice(roots)
        y, m = divmod(self.rng.randrange(0, 24), 12)
        cm = f"{2027 + y}-{m + 1:02d}"
        qty = Decimal(self.rng.randint(1, 250))
        if product == "OPT":
            step = Decimal(STRIKE_STEP[root])
            lvl = Decimal(PRICE_LEVEL[root])
            strike = (lvl / step).to_integral_value() * step + step * self.rng.randint(-5, 5)
            prem = Decimal(TICK[root]) * self.rng.randint(4, 400)
            return Trade(**base, quantity=qty, price=prem, root=root, contract_month=cm,
                         put_call=self.rng.choice(["C", "P"]), strike=strike)
        price = self._on_tick(PRICE_LEVEL[root], TICK[root])
        return Trade(**base, quantity=qty, price=price, root=root, contract_month=cm)

    def _register(self, t: Trade) -> bool:
        k = t.key()
        if k in self._keys:
            return False
        self._keys.add(k)
        for f in COMPARE_FIELDS[t.product_type]:
            self._near[t.broker_id].add((f,) + t.key(drop=f))
        return True

    def _near_unique(self, t: Trade, f: str) -> bool:
        if f not in self._near_count:
            self._near_count[f] = Counter((x.broker_id, x.key(drop=f)) for x in self.trades)
        return self._near_count[f][(t.broker_id, t.key(drop=f))] == 1

    def _isolated(self, t: Trade) -> bool:
        """True if t differs from every registered trade in at least two compare fields."""
        if t.key() in self._keys:
            return False
        return not any((f,) + t.key(drop=f) in self._near[t.broker_id] for f in COMPARE_FIELDS[t.product_type])

    # ---------------------------------------------------------------------- build
    def build(self) -> None:
        for spec in BROKERS:
            n = max(40, int(self.n * spec.share))
            made = 0
            while made < n:
                t = self._random_trade(spec)
                if self._register(t):
                    self.trades.append(t)
                    made += 1
        for t in self.trades:
            spec = next(s for s in BROKERS if s.broker_id == t.broker_id)
            if spec.statement:
                code = "T1_REF_EXACT" if t.internal_has_ref else "T2_KEY_EXACT"
                self.rows[t.broker_id].append(BrokerRow(trade=t, broker_ref=t.broker_ref, truth_internal=[t.internal_id],
                                                        expect=("MATCHED", code)))
                self.internal_expect[t.internal_id] = ("MATCHED", code)
            else:
                self.internal_expect[t.internal_id] = ("UNMATCHED", "NO_CONFIRMATION_RECEIVED")
        for spec in BROKERS:
            if spec.statement:
                self._seed(spec)
        for t in self.trades:
            if t.broker_id == "BRK_E":
                self.internal_expect_pre[t.internal_id] = ("UNMATCHED", "CONFIRMATION_NOT_PROCESSED")

    def _victim(self, spec: BrokerSpec, used: set, has_ref: bool | None, products=None, pred=None) -> BrokerRow | None:
        def ok(r: BrokerRow) -> bool:
            return (r.scenario == "normal" and r.trade.internal_id not in used
                    and (has_ref is None or r.trade.internal_has_ref == has_ref)
                    and (products is None or r.trade.product_type in products)
                    and (pred is None or pred(r)))
        rows = self.rows[spec.broker_id]
        # Rejection sampling keeps seeding O(1) per victim at large volumes.
        for _ in range(200):
            r = rows[self.rng.randrange(len(rows))]
            if ok(r):
                used.add(r.trade.internal_id)
                return r
        for r in rows:
            if ok(r):
                used.add(r.trade.internal_id)
                return r
        return None

    def _mark(self, row: BrokerRow, scenario: str, b_expect, i_expect=None):
        row.scenario = scenario
        row.expect = b_expect
        if i_expect is not None:
            for iid in row.truth_internal:
                self.internal_expect[iid] = i_expect
        self.seeded.append({"broker_id": row.trade.broker_id, "scenario": scenario, "broker_ref": row.broker_ref,
                            "internal_ids": list(row.truth_internal), "expect_broker": list(b_expect),
                            "expect_internal": list(i_expect) if i_expect else None})

    def _seed(self, spec: BrokerSpec) -> None:
        rows = self.rows[spec.broker_id]
        k = max(1, round(len(rows) * self.break_rate))
        used: set = set()
        fut_opt = ("FUT", "OPT")
        econ = tuple(p for p in spec.products)

        for _ in range(k):
            # Missing at broker: internal trade open, broker does not show it.
            r = self._victim(spec, used, None)
            if r:
                rows.remove(r)
                self.internal_expect[r.trade.internal_id] = ("UNMATCHED", "UNMATCHED_INTERNAL")
                self.seeded.append({"broker_id": spec.broker_id, "scenario": "missing_at_broker",
                                    "internal_ids": [r.trade.internal_id], "expect_internal": ["UNMATCHED", "UNMATCHED_INTERNAL"]})
            # Extra at broker: broker shows a trade the client did not book.
            for _attempt in range(50):
                t = self._random_trade(spec)
                if self._isolated(t):
                    self._keys.add(t.key())
                    for f in COMPARE_FIELDS[t.product_type]:
                        self._near[spec.broker_id].add((f,) + t.key(drop=f))
                    row = BrokerRow(trade=t, broker_ref=t.broker_ref, truth_internal=[])
                    rows.append(row)
                    self._mark(row, "extra_at_broker", ("UNMATCHED", "UNMATCHED_BROKER"))
                    break
            # Quantity conflict on a shared reference.
            r = self._victim(spec, used, True)
            if r:
                r.trade = replace(r.trade, quantity=r.trade.quantity + (Decimal(50000) if r.trade.product_type == "FXFWD" else 1))
                self._mark(r, "quantity_conflict", ("BREAK", "CONFLICTING_VALUES"), ("BREAK", "CONFLICTING_VALUES"))
            # Trade date conflict on a shared reference.
            r = self._victim(spec, used, True, pred=lambda r: r.trade.trade_date.weekday() > 0)
            if r:
                r.trade = replace(r.trade, trade_date=r.trade.trade_date - dt.timedelta(days=1))
                self._mark(r, "trade_date_conflict", ("BREAK", "CONFLICTING_VALUES"), ("BREAK", "CONFLICTING_VALUES"))
            # Price break without a shared reference (found by T4).
            r = self._victim(spec, used, False, pred=lambda r: self._near_unique(r.trade, "price"))
            if r:
                if r.trade.product_type == "FXFWD":
                    tick = Decimal(1).scaleb(-FX_LEVEL[r.trade.ccy_pair][1])
                else:
                    tick = Decimal(TICK[r.trade.root])
                r.trade = replace(r.trade, price=r.trade.price + tick * 2)
                self._mark(r, "price_break", ("BREAK", "VALUE_BREAK"), ("BREAK", "VALUE_BREAK"))
            # Side break without a shared reference.
            r = self._victim(spec, used, False, pred=lambda r: self._near_unique(r.trade, "side"))
            if r:
                r.trade = replace(r.trade, side="SELL" if r.trade.side == "BUY" else "BUY")
                self._mark(r, "side_break", ("BREAK", "VALUE_BREAK"), ("BREAK", "VALUE_BREAK"))
            # Reference typo at the broker.
            r = self._victim(spec, used, True)
            if r:
                # Mistyped leading digit; sequence numbers never reach 9xxxxxx so it cannot collide.
                pre, digits = r.broker_ref.split("-")
                r.broker_ref = f"{pre}-9{digits[1:]}"
                self._mark(r, "reference_typo", ("BREAK", "VALUE_BREAK"), ("BREAK", "VALUE_BREAK"))
            # Duplicate row on the statement.
            r = self._victim(spec, used, True)
            if r:
                dup = BrokerRow(trade=r.trade, broker_ref=r.broker_ref, truth_internal=list(r.truth_internal))
                rows.insert(rows.index(r) + 1, dup)
                self._mark(r, "duplicate_row", ("DUPLICATE", "DUPLICATE_RECORD"), ("DUPLICATE", "DUPLICATE_RECORD"))
                dup.scenario, dup.expect = "duplicate_row", ("DUPLICATE", "DUPLICATE_RECORD")
            # Missing price on the statement.
            r = self._victim(spec, used, True)
            if r:
                r.overrides["price"] = ""
                self._mark(r, "missing_price", ("NOT_COMPARABLE", "MISSING_FIELD"), ("NOT_COMPARABLE", "COUNTERPART_INCOMPLETE"))
            # Unmapped broker instrument code.
            r = self._victim(spec, used, True, products=fut_opt)
            if r:
                r.overrides["instrument_code"] = "ZZQ"
                self._mark(r, "unmapped_instrument", ("NOT_COMPARABLE", "UNMAPPED_INSTRUMENT"), ("NOT_COMPARABLE", "COUNTERPART_INCOMPLETE"))
            # Homoglyph in quantity (letter O for zero / l for one): extraction uncertainty.
            r = self._victim(spec, used, True, pred=lambda r: ("0" in str(r.trade.quantity) or "1" in str(r.trade.quantity)))
            if r:
                q = format(r.trade.quantity.normalize(), "f")
                r.overrides["quantity"] = q.replace("0", "O", 1) if "0" in q else q.replace("1", "l", 1)
                self._mark(r, "homoglyph_quantity", ("NOT_COMPARABLE", "EXTRACTION_UNCERTAIN"), ("NOT_COMPARABLE", "COUNTERPART_INCOMPLETE"))

        # Fungible lots (identical economics, no internal references): one equal group, one count mismatch.
        for n_int, n_brk, scen, exp in ((2, 2, "fungible_equal", ("MATCHED", "T2_KEY_EXACT")),
                                        (3, 2, "fungible_count_mismatch", ("AMBIGUOUS", "GROUP_COUNT_MISMATCH"))):
            for _attempt in range(50):
                t = self._random_trade(spec, product=econ[0])
                if self._isolated(t):
                    break
            self._register(t)
            copies = []
            for j in range(n_int):
                c = replace(t, internal_id=self._iid(), internal_has_ref=False, broker_ref=self._ref(spec))
                self.trades.append(c)
                copies.append(c)
                self.internal_expect[c.internal_id] = exp
            for j in range(n_brk):
                row = BrokerRow(trade=copies[j], broker_ref=copies[j].broker_ref, truth_internal=[c.internal_id for c in copies])
                rows.append(row)
                row.scenario, row.expect = scen, exp
            self.seeded.append({"broker_id": spec.broker_id, "scenario": scen, "internal_ids": [c.internal_id for c in copies],
                                "broker_refs": [c.broker_ref for c in copies[:n_brk]], "expect_broker": list(exp), "expect_internal": list(exp)})

        # Average-price (APS) lines: only BRK_A reports them.
        if spec.broker_id == "BRK_A":
            for scen, exp, qty_delta in (("aps_group", ("MATCHED", "T3_APS_GROUP"), 0),
                                         ("aps_group_break", ("BREAK", "APS_GROUP_BREAK"), 1)):
                for _attempt in range(50):
                    base = self._random_trade(spec, product="FUT")
                    if self._isolated(base):
                        break
                gid = f"APS-{self._iid_seq + 1:06d}"
                fills = []
                for j in range(3):
                    f = replace(base, internal_id=self._iid(), internal_has_ref=False, broker_ref=self._ref(spec),
                                quantity=Decimal(self.rng.randint(5, 60)),
                                price=base.price + Decimal(TICK[base.root]) * self.rng.randint(-6, 6), aps_group_id=gid)
                    self._register(f)
                    self.trades.append(f)
                    fills.append(f)
                    self.internal_expect[f.internal_id] = exp
                q = sum(f.quantity for f in fills)
                vwap = (sum(f.quantity * f.price for f in fills) / q).quantize(Decimal(1).scaleb(-APS_DP[base.root]), rounding=ROUND_HALF_EVEN)
                line = replace(base, internal_id="", quantity=q + qty_delta, price=vwap, broker_ref=self._ref(spec))
                row = BrokerRow(trade=line, broker_ref=line.broker_ref, aps_flag=True, truth_internal=[f.internal_id for f in fills])
                rows.append(row)
                row.scenario, row.expect = scen, exp
                self.seeded.append({"broker_id": spec.broker_id, "scenario": scen, "broker_ref": line.broker_ref,
                                    "internal_ids": [f.internal_id for f in fills], "expect_broker": list(exp), "expect_internal": list(exp)})

        # Keep statement order realistic: by account, then trade date, then reference.
        rows.sort(key=lambda r: (r.trade.product_type == "FXFWD", r.trade.account, r.trade.trade_date, r.broker_ref))

    # -------------------------------------------------------------------- outputs
    def truth(self, documents: dict) -> dict:
        broker = {}
        for b_id, rows in self.rows.items():
            for r in rows:
                key = f"{b_id}|{r.broker_ref}"
                entry = broker.setdefault(key, {"expect": list(r.expect), "scenario": r.scenario,
                                                "internal_ids": sorted(r.truth_internal), "occurrences": 0,
                                                "canonical": None})
                entry["occurrences"] += 1
                if not r.overrides:
                    c = r.trade.canon()
                    c["broker_ref"] = r.broker_ref
                    entry["canonical"] = c
        return {
            "as_of": AS_OF.isoformat(),
            "internal": {iid: list(v) for iid, v in sorted(self.internal_expect.items())},
            "internal_before_onboarding": {iid: list(v) for iid, v in sorted(self.internal_expect_pre.items())},
            "broker": dict(sorted(broker.items())),
            "documents": documents,
            "seeded": self.seeded,
        }


def generate(out_dir: Path, n_trades: int = 3000, seed: int = 7, break_rate: float = 0.004) -> dict:
    from .render import render_all

    g = Generator(n_trades, seed=seed, break_rate=break_rate)
    g.build()
    evidence = out_dir / "evidence"
    (evidence / "brokers").mkdir(parents=True, exist_ok=True)
    (evidence / "internal").mkdir(parents=True, exist_ok=True)
    documents, intake = render_all(g, evidence)
    with open(evidence / "intake.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(intake, fh, sort_keys=False)
    truth_dir = out_dir / "truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    truth = g.truth(documents)
    with open(truth_dir / "ground_truth.json", "w", encoding="utf-8") as fh:
        json.dump(truth, fh, indent=1, sort_keys=True)
    return {"internal_trades": len(g.trades), "broker_rows": sum(len(v) for v in g.rows.values()),
            "seeded_scenarios": len(g.seeded), "documents": len(documents)}
