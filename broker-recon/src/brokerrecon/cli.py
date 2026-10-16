"""Command-line interface."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config"


def _p(s: str) -> Path:
    return Path(s).expanduser()


def cmd_generate(a):
    from .synth.generator import generate

    stats = generate(a.out, n_trades=a.trades, seed=a.seed, break_rate=a.break_rate)
    print(json.dumps(stats, indent=2))
    print(f"evidence: {a.out / 'evidence'}\nground truth (never read by the engine): {a.out / 'truth' / 'ground_truth.json'}")


def cmd_run(a):
    from .pipeline import run

    run_dir = run(a.evidence, a.config, a.out, dt.date.fromisoformat(a.as_of), review_pack=not a.no_review_pack)
    summary = json.loads((run_dir / "results" / "summary.json").read_text())
    print(json.dumps(summary, indent=2))
    print(f"\nrun directory: {run_dir}")


def cmd_approve(a):
    from .config import approve, load_config, save_config

    cfg = load_config(a.config_file)
    approved = approve(cfg, a.by, a.on)
    target = a.config_file
    if a.config_file.parent.name == "proposed":
        target = a.config_file.parent.parent / a.config_file.name
        a.config_file.unlink()
    save_config(approved, target)
    print(f"approved {approved.config_id} by {a.by}; body sha256 {approved.approval.body_sha256}\nwritten to {target}")


def cmd_verify(a):
    from .qa import verify

    rep = verify(a.run_dir, rerun=not a.no_rerun)
    print(json.dumps(rep, indent=2))
    sys.exit(0 if rep["passed"] else 1)


def cmd_score(a):
    from .qa import score

    out = score(a.run_dir, a.truth)
    brief = {k: out[k] for k in ("false_matches", "classification", "seeded_breaks", "field_accuracy", "row_level", "gates", "passed")}
    print(json.dumps(brief, indent=2))
    sys.exit(0 if out["passed"] else 1)


def cmd_onboard(a):
    from .onboard import onboard

    path = onboard(a.file, a.broker_id, a.config, use_ai=a.ai, mask=not a.no_mask)
    print(f"proposed template written to {path}\nReview it, then: brokerrecon approve {path} --by \"<name>\"")


def cmd_review(a):
    from .review import apply_dispositions, write_template

    if a.action == "template":
        p = write_template(a.run_dir)
        print(f"disposition template: {p}")
    else:
        res = apply_dispositions(a.run_dir, a.file, a.reviewer)
        print(json.dumps(res, indent=2))


def cmd_demo(a):
    """Full walk-through on synthetic data."""
    from .config import approve, load_config, save_config
    from .onboard import onboard
    from .pipeline import run
    from .qa import score, verify
    from .synth.generator import generate

    work = a.out
    if work.exists():
        shutil.rmtree(work)
    cfg_dir = work / "config"
    shutil.copytree(a.config, cfg_dir)
    for p in sorted((cfg_dir / "brokers").glob("*.yaml")) + [cfg_dir / "internal.yaml"]:
        c = load_config(p)
        if c.approval_problem():
            save_config(approve(c, "Demo Reviewer (synthetic)", "2027-01-10"), p)
    print("1) generating synthetic evidence ...")
    print(json.dumps(generate(work, n_trades=a.trades, seed=a.seed), indent=2))
    as_of = dt.date(2026, 12, 31)
    print("2) first run (BRK_E's CSV layout has no approved template yet) ...")
    r1 = run(work / "evidence", cfg_dir, work / "runs", as_of)
    s1 = score(r1, work / "truth" / "ground_truth.json")
    print(f"   run {r1.name}: gates {s1['gates']}")
    print(f"3) onboarding the unknown layout ({'AI' if a.ai else 'heuristic'} proposes, a person approves) ...")
    prop = onboard(work / "evidence" / "brokers" / "echo_positions_export.csv", "BRK_E", cfg_dir, use_ai=a.ai)
    c = load_config(prop)
    final = cfg_dir / "brokers" / prop.name
    save_config(approve(c, "Demo Reviewer (synthetic)", "2027-01-11"), final)
    prop.unlink()
    print(f"   proposal {prop.name} reviewed and approved -> {final}")
    print("4) second run ...")
    r2 = run(work / "evidence", cfg_dir, work / "runs", as_of)
    s2 = score(r2, work / "truth" / "ground_truth.json")
    print(f"   run {r2.name}: gates {s2['gates']}")
    print("5) verifying audit chain and byte-identical re-execution ...")
    v = verify(r2)
    print(json.dumps({k: v[k] for k in ("event_log_intact", "outputs_match_manifest", "rerun", "passed")}, indent=2))
    print(f"\nreview pack: {r2 / 'review' / 'review_pack.html'}\nworkbook:    {r2 / 'results' / 'reconciliation.xlsx'}")
    ok = s2["passed"] and v["passed"]
    print("\nDEMO RESULT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="brokerrecon", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate synthetic evidence + ground truth")
    g.add_argument("--out", type=_p, default=Path("demo"))
    g.add_argument("--trades", type=int, default=3000)
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--break-rate", type=float, default=0.004)
    g.set_defaults(fn=cmd_generate)

    r = sub.add_parser("run", help="run a reconciliation")
    r.add_argument("--evidence", type=_p, required=True)
    r.add_argument("--config", type=_p, default=DEFAULT_CONFIG)
    r.add_argument("--out", type=_p, default=Path("runs"))
    r.add_argument("--as-of", default="2026-12-31")
    r.add_argument("--no-review-pack", action="store_true")
    r.set_defaults(fn=cmd_run)

    p = sub.add_parser("approve", help="approve a broker template (records approver and body hash)")
    p.add_argument("config_file", type=_p)
    p.add_argument("--by", required=True)
    p.add_argument("--on", default=None)
    p.set_defaults(fn=cmd_approve)

    v = sub.add_parser("verify", help="verify audit chain, output hashes and byte-identical re-execution")
    v.add_argument("run_dir", type=_p)
    v.add_argument("--no-rerun", action="store_true")
    v.set_defaults(fn=cmd_verify)

    s = sub.add_parser("score", help="score a run against synthetic ground truth")
    s.add_argument("run_dir", type=_p)
    s.add_argument("--truth", type=_p, required=True)
    s.set_defaults(fn=cmd_score)

    o = sub.add_parser("onboard", help="propose a template for an unrecognised broker layout")
    o.add_argument("file", type=_p)
    o.add_argument("--broker-id", required=True)
    o.add_argument("--config", type=_p, default=DEFAULT_CONFIG)
    o.add_argument("--ai", action="store_true", help="use Claude to propose the mapping (needs ANTHROPIC_API_KEY)")
    o.add_argument("--no-mask", action="store_true", help="do not pseudonymise sample values sent to the model")
    o.set_defaults(fn=cmd_onboard)

    rv = sub.add_parser("review", help="human review dispositions")
    rv.add_argument("action", choices=["template", "apply"])
    rv.add_argument("run_dir", type=_p)
    rv.add_argument("--file", type=_p)
    rv.add_argument("--reviewer")
    rv.set_defaults(fn=cmd_review)

    d = sub.add_parser("demo", help="end-to-end demonstration on synthetic data")
    d.add_argument("--out", type=_p, default=Path("demo"))
    d.add_argument("--config", type=_p, default=DEFAULT_CONFIG)
    d.add_argument("--trades", type=int, default=3000)
    d.add_argument("--seed", type=int, default=7)
    d.add_argument("--ai", action="store_true")
    d.set_defaults(fn=cmd_demo)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
