from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "run_batch34_metamorphic.py"
REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "benchmark-vabench-release-v4" / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"


def load_script():
    spec = importlib.util.spec_from_file_location("batch34_metamorphic", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_affine_transform_changes_times_not_voltage_values() -> None:
    script = load_script()
    deck = """Vx (x 0) vsource type=pwl wave=[0 0.20 10n 0.80 20n 0.30]\ntran tran stop=20n maxstep=100p\nVclk (clk 0) vsource type=pulse period=5n delay=1n width=2n\n"""
    transformed = script.transform_deck(deck)
    assert "wave=[2n 0.20 15.7n 0.80 29.4n 0.30]" in transformed
    assert "stop=29.4n maxstep=137p" in transformed
    assert "period=6.85n delay=3.37n width=2.74n" in transformed


def test_batch34_checker_sources_have_no_absolute_secret_windows() -> None:
    forbidden = (
        r"t\s*[<>]=?\s*\d+(?:\.\d+)?e-9",
        r"(?:start|stop)\s*=\s*\d+(?:\.\d+)?e-9",
    )
    for family in range(331, 341):
        source = (REPO / "runners" / "checkers" / "v4" / f"task_{family}.py").read_text()
        assert not any(re.search(pattern, source) for pattern in forbidden), family


def test_batch34_checker_profiles_publish_diagnostic_contract() -> None:
    for family_dir in sorted(SOURCE.iterdir()):
        if not family_dir.is_dir() or not family_dir.name[:3].isdigit():
            continue
        family = int(family_dir.name[:3])
        if not 331 <= family <= 340:
            continue
        evaluator = family_dir / "evaluator"
        profile = json.loads((evaluator / "checker_profile.json").read_text())
        contract = profile["diagnostic_contract"]
        assert contract["schema_version"] == "v4-checker-diagnostic-v1"
        assert contract["event_context"] == "stimulus_relative"
        assert profile["property_ids"]
