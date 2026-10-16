import json
import shutil
from types import SimpleNamespace

from brokerrecon.config import approve, load_config, save_config
from brokerrecon.onboard import AIProposal, onboard
from brokerrecon.pipeline import run
from brokerrecon.qa import score, verify

from conftest import AS_OF


def test_pipeline_meets_all_gates_and_is_reproducible(small_demo, config_dir, tmp_path):
    run_dir = run(small_demo / "evidence", config_dir, tmp_path / "runs", AS_OF)
    s = score(run_dir, small_demo / "truth" / "ground_truth.json")
    assert s["false_matches"] == 0
    assert s["passed"], s["gates"]
    # The unrecognised CSV layout is reported, never silently skipped.
    docs = {d["file"]: d for d in s["documents"]}
    assert docs["brokers/echo_positions_export.csv"]["doc_exceptions"] == ["FORMAT_UNRECOGNISED"]

    v = verify(run_dir)
    assert v["passed"] and v["rerun"]["byte_identical_outputs"] and v["rerun"]["same_run_id"]

    # Tampering with an output is detected.
    trades = run_dir / "results" / "trades.csv"
    trades.write_text(trades.read_text().replace("MATCHED", "MATCHEd", 1))
    v2 = verify(run_dir, rerun=False)
    assert not v2["passed"] and "results/trades.csv" in v2["tampered_or_missing"]


def test_onboarding_heuristic_then_approval(small_demo, config_dir, tmp_path):
    cfg_dir = tmp_path / "config"
    shutil.copytree(config_dir, cfg_dir)
    prop = onboard(small_demo / "evidence" / "brokers" / "echo_positions_export.csv", "BRK_E", cfg_dir)
    cfg = load_config(prop)
    assert cfg.status == "proposed" and cfg.approval_problem()
    assert cfg.proposal["self_test"]["completeness"]["open_trades"]["status"] == "PASS"
    # Proposed templates are not used until approved.
    run_dir = run(small_demo / "evidence", cfg_dir, tmp_path / "r1", AS_OF, review_pack=False)
    assert json.loads((run_dir / "results" / "summary.json").read_text())["exceptions"]["document_level"].get("FORMAT_UNRECOGNISED") == 1
    save_config(approve(cfg, "Test Reviewer"), cfg_dir / "brokers" / "BRK_E.yaml")
    prop.unlink()
    run_dir = run(small_demo / "evidence", cfg_dir, tmp_path / "r2", AS_OF, review_pack=False)
    s = score(run_dir, small_demo / "truth" / "ground_truth.json")
    assert s["passed"], s["gates"]


class _FakeMessages:
    def __init__(self, proposal):
        self.proposal = proposal
        self.calls = []

    def parse(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(parsed_output=self.proposal, stop_reason="end_turn", model=kw["model"], id="msg_test")


def test_ai_onboarding_masks_data_and_records_provenance(small_demo, config_dir, tmp_path):
    cfg_dir = tmp_path / "config"
    shutil.copytree(config_dir, cfg_dir)
    proposal = AIProposal.model_validate({
        "columns": [{"canonical_field": f, "header_label": h} for f, h in [
            ("broker_ref", "ExecID"), ("account", "Client Account"), ("instrument_code", "Symbol"),
            ("contract_month", "Expiry"), ("side", "Side"), ("quantity", "Size"), ("price", "Px"), ("trade_date", "Exec Date")]],
        "product_type_rule": "CONSTANT_FUT", "date_format": "%Y-%m-%d", "contract_month_style": "YYYY-MM",
        "side_values": [{"raw": "BUY", "side": "BUY"}, {"raw": "SELL", "side": "SELL"}], "signed_quantity": False,
        "decimal_separator": ".", "thousands_separator": ",", "uncertainties": [],
    })
    fake = SimpleNamespace(messages=_FakeMessages(proposal))
    prop = onboard(small_demo / "evidence" / "brokers" / "echo_positions_export.csv", "BRK_E", cfg_dir, use_ai=True, client=fake)
    sent = fake.messages.calls[0]["messages"][0]["content"]
    assert "EB-" not in sent and "XX-9999999" in sent  # references pseudonymised before leaving the machine
    cfg = load_config(prop)
    assert cfg.status == "proposed"
    assert cfg.proposal["method"] == "ai-structured-output" and len(cfg.proposal["prompt_sha256"]) == 64
    assert cfg.proposal["self_test"]["records_comparable"] > 0
