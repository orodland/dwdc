import json

from brokerrecon.audit import EventLog, verify_chain
from brokerrecon.config import approve, load_config


def test_config_edit_after_approval_is_refused(config_dir, tmp_path):
    cfg = load_config(config_dir / "brokers" / "BRK_A.yaml")
    assert cfg.approval_problem() is None
    cfg.symbology["XX"] = "ZC"  # someone edits the template after sign-off
    assert "hash mismatch" in cfg.approval_problem()
    assert approve(cfg, "Second Reviewer").approval_problem() is None


def test_event_log_detects_tampering(tmp_path):
    p = tmp_path / "events.jsonl"
    log = EventLog(p)
    for k in range(5):
        log.emit("E", k=k)
    head = log.close()
    ok, h, n = verify_chain(p)
    assert ok and h == head and n == 5
    lines = p.read_text().splitlines()
    ev = json.loads(lines[2])
    ev["data"]["k"] = 99
    lines[2] = json.dumps(ev, sort_keys=True, separators=(",", ":"))
    p.write_text("\n".join(lines) + "\n")
    ok, msg, _ = verify_chain(p)
    assert not ok and "altered" in msg
