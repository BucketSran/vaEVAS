from __future__ import annotations

import pytest

from runners.checkers.v4.stimulus_relative import normalize_affine_time


def test_normalize_affine_time_uses_public_input_edges() -> None:
    scale = 1.37
    shift = 2e-9
    canonical = [
        {"time": 0.0, "stim": 0.0},
        {"time": 1e-9, "stim": 1.0},
        {"time": 2e-9, "stim": 0.0},
        {"time": 3e-9, "stim": 1.0},
    ]
    transformed = [{**row, "time": scale * row["time"] + shift} for row in canonical]

    normalized = normalize_affine_time(
        transformed,
        [
            ("stim", 0.5, "rising", 0.5, 0),
            ("stim", 0.5, "rising", 2.5, 1),
        ],
    )

    assert normalized is not None
    assert [row["time"] for row in normalized] == pytest.approx(
        [row["time"] for row in canonical]
    )


def test_normalize_affine_time_rejects_missing_excitation() -> None:
    rows = [{"time": index * 1e-9, "stim": 0.0} for index in range(4)]
    assert normalize_affine_time(
        rows,
        [
            ("stim", 0.5, "rising", 0.5, 0),
            ("stim", 0.5, "rising", 2.5, 1),
        ],
    ) is None
