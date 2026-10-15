from __future__ import annotations

from runners.checkers.v4.batch18_diagnostics import bind_properties
from runners.checkers.v4.task_176 import CHECKER as CHECK_WEIGHTED_DECODER
from runners.checkers.v4.task_179 import _trace_time_scale


def test_batch18_diagnostics_bind_all_properties_and_redact_failure() -> None:
    property_ids = ("P_FIRST", "P_SECOND")

    passing = bind_properties(lambda rows: (True, "raw pass"), property_ids)
    passed, pass_note = passing([{"time": 0.0}])
    assert passed
    assert all(property_id in pass_note for property_id in property_ids)

    failing = bind_properties(lambda rows: (False, "secret value=123"), property_ids)
    passed, failure_note = failing([{"time": 0.0}])
    assert not passed
    assert all(property_id in failure_note for property_id in property_ids)
    assert "123" not in failure_note


def test_weighted_decoder_rejects_static_prefix_as_insufficient() -> None:
    rows = []
    for index in range(30):
        row = {
            "time": index * 0.02e-9,
            "aout7b": -0.5,
            "aout7b5": -0.5,
            "aout8b": -0.5,
        }
        row.update({f"d{bit}": 0.0 for bit in range(9)})
        rows.append(row)

    passed, note = CHECK_WEIGHTED_DECODER(rows)
    assert not passed
    assert "P_SHARED_272_DENOMINATOR" in note


def test_tdc_checker_derives_affine_scale_from_output_transition() -> None:
    rows = [
        {"time": 0.0, "vout": 0.0},
        {"time": 1.0e-12, "vout": 0.0},
        {"time": 2.0e-12, "vout": 0.1},
        {"time": 14.7e-12, "vout": 0.9},
        {"time": 15.7e-12, "vout": 0.9},
    ]

    assert abs((_trace_time_scale(rows) or 0.0) - 1.37) < 1e-9
