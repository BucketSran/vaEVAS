from __future__ import annotations

import csv
from pathlib import Path

from runners.checkers.v4.task_081 import CHECKER, STREAMING_CHECKER


def _ratio_at(time_s: float) -> tuple[float, float]:
    # Affine timing of the public 081 score/reference stimulus.
    schedule = (
        (0.0, 4.0),
        (2.74337e-6, 6.0),
        (7.12737e-6, 3.49),
        (8.25077e-6, 3.50),
        (9.37417e-6, 2.20),
        (10.49757e-6, 13.20),
    )
    start_s, value = schedule[0]
    for start, candidate in schedule:
        if time_s >= start:
            start_s = start
            value = candidate
    return value, start_s


def _logic_clock(time_s: float, period_s: float) -> float:
    return 0.9 if (time_s % period_s) < 0.5 * period_s else 0.0


def _affine_adpll_rows() -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    step_s = 0.274e-9
    dco_period_s = 1.0 / 240.0e6
    stop_s = 11.647e-6
    count = int(stop_s / step_s) + 1
    for index in range(count + 1):
        time_s = index * step_s
        ratio_raw, ratio_start_s = _ratio_at(time_s)
        ratio = max(3, min(12, int(ratio_raw + 0.5)))
        lock = 0.9
        if 2.74337e-6 <= time_s < 4.4e-6:
            lock = 0.0
        rows.append(
            {
                "time": time_s,
                "ref_clk": _logic_clock(time_s - ratio_start_s, dco_period_s * ratio),
                "ratio_ctrl": ratio_raw,
                "fb_clk": _logic_clock(time_s - ratio_start_s, dco_period_s * ratio),
                "vout": _logic_clock(time_s - ratio_start_s, dco_period_s),
                "lock": lock,
                "vctrl_mon": 0.0,
            }
        )
    return rows


def test_task081_conformance_windows_follow_observed_ratio_plateaus(tmp_path: Path) -> None:
    rows = _affine_adpll_rows()

    passed, note = CHECKER(rows)
    assert passed, note

    csv_path = tmp_path / "tran.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    score, notes = STREAMING_CHECKER(csv_path)
    assert score == 1.0, notes
