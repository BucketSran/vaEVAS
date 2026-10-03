from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runners"))

from testbench_security import validate_testbench  # noqa: E402


def _contract() -> dict:
    return {
        "artifact_contract": {
            "files": [
                {
                    "path": "entry.va",
                    "modules": [
                        {
                            "name": "entry",
                            "role": "entry",
                            "ports": [
                                {"name": "vin", "direction": "input"},
                                {"name": "vout", "direction": "output"},
                            ],
                            "parameters": [],
                        }
                    ],
                }
            ]
        },
        "supplied_support_artifacts": ["supplied_dut/support/helper.va"],
        "testbench_binding": {
            "source_path_template": "./dut/{artifact_path}",
            "instances": [
                {
                    "name": "XDUT",
                    "module_ref": "entry",
                    "connections": [
                        {"position": 0, "port_ref": "vin", "net": "vin"},
                        {"position": 1, "port_ref": "vout", "net": "vout"},
                    ],
                }
            ],
        },
        "trace_contract": {"required_signals": ["vin", "vout"]},
    }


def _policy() -> dict:
    return {
        "allowed_include_paths": ["./dut/entry.va", "./dut/support/helper.va"],
        "limits": {"max_candidate_bytes": 100_000, "max_tran_stop_seconds": 1.0},
    }


def _deck(*includes: str) -> str:
    include_lines = "\n".join(f'ahdl_include "{path}"' for path in includes)
    return f"""simulator lang=spectre
{include_lines}
VIN (vin 0) vsource dc=0
XDUT (vin vout) entry
tran tran stop=1n
save vin vout
"""


def test_optional_support_include_is_not_required(tmp_path: Path) -> None:
    candidate = tmp_path / "testbench.scs"
    candidate.write_text(_deck("./dut/entry.va"), encoding="utf-8")

    result = validate_testbench(candidate, _contract(), _policy())

    assert result.valid, result.diagnostics


def test_optional_support_include_remains_allowed(tmp_path: Path) -> None:
    candidate = tmp_path / "testbench.scs"
    candidate.write_text(
        _deck("./dut/entry.va", "./dut/support/helper.va"), encoding="utf-8"
    )

    result = validate_testbench(candidate, _contract(), _policy())

    assert result.valid, result.diagnostics


def test_declared_dut_include_remains_required(tmp_path: Path) -> None:
    candidate = tmp_path / "testbench.scs"
    candidate.write_text(_deck("./dut/support/helper.va"), encoding="utf-8")

    result = validate_testbench(candidate, _contract(), _policy())

    assert not result.valid
    assert any("missing declared DUT include" in item for item in result.diagnostics)
