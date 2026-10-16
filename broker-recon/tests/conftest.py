import datetime as dt
import shutil
from pathlib import Path

import pytest

from brokerrecon.config import approve, load_config, save_config

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config"
AS_OF = dt.date(2026, 12, 31)


@pytest.fixture(scope="session")
def config_dir(tmp_path_factory) -> Path:
    """A copy of the repository templates, approved by a test reviewer."""
    d = tmp_path_factory.mktemp("cfg") / "config"
    shutil.copytree(REPO_CONFIG, d)
    for p in sorted((d / "brokers").glob("*.yaml")) + [d / "internal.yaml"]:
        save_config(approve(load_config(p), "Test Reviewer", "2027-01-10"), p)
    return d


@pytest.fixture(scope="session")
def small_demo(tmp_path_factory, config_dir) -> Path:
    from brokerrecon.synth.generator import generate

    out = tmp_path_factory.mktemp("demo")
    generate(out, n_trades=600, seed=3)
    return out
