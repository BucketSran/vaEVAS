"""Task-local semantic regressions for family 091."""
from __future__ import annotations

from copy import deepcopy

from checker import CHECKER, GAIN, LP_ALPHA, SETTLE_CYCLES, SETTLE_TOL, VCM, VDD, VOS_AMP


def _transform_time(
    rows: list[dict[str, float]], *, scale: float, shift_s: float
) -> list[dict[str, float]]:
    transformed = deepcopy(rows)
    for row in transformed:
        row["time"] = scale * row["time"] + shift_s
    return transformed


def _trace(fault: str = "gold") -> list[dict[str, float]]:
    step_ns = 0.05
    times = [index * step_ns for index in range(round(70 / step_ns) + 1)]
    edge_times = sorted(
        [(2.0 + 2.0 * index, 1) for index in range(35)]
        + [(2.9 + 2.0 * index, -1) for index in range(34)]
    )
    baseband = residual = settled = 0.0
    converged = 0
    rows: list[dict[str, float]] = []
    edge_index = 0
    previous_enable = 0.0
    for t in times:
        diff = 0.04 if t < 24.1 else (-0.03 if t < 42.1 else 0.02)
        vinp, vinn = VCM + 0.5 * diff, VCM - 0.5 * diff
        rst = VDD if t < 1.6 else 0.0
        enable = VDD if 3.1 <= t < 55.1 or t >= 58.1 else 0.0
        hold = VDD if 18.1 <= t < 22.1 or 48.1 <= t < 52.1 else 0.0
        if previous_enable > 0.45 and enable <= 0.45:
            baseband = residual = settled = 0.0
            converged = 0
        while edge_index < len(edge_times) and edge_times[edge_index][0] <= t + 1e-12:
            polarity = edge_times[edge_index][1]
            if rst > 0.45 or enable <= 0.45:
                baseband = residual = settled = 0.0
                converged = 0
            elif hold <= 0.45:
                demod = GAIN * diff + polarity * GAIN * VOS_AMP
                if fault == "no_demod":
                    demod = GAIN * (polarity * diff + VOS_AMP)
                elif fault == "no_offset":
                    demod = GAIN * diff
                if fault == "no_lowpass":
                    baseband = demod
                else:
                    baseband += LP_ALPHA * (demod - baseband)
                residual = baseband - GAIN * diff
                converged = converged + 1 if abs(residual) <= SETTLE_TOL else 0
                settled = VDD if converged >= SETTLE_CYCLES else 0.0
            edge_index += 1
        chop = VDD if any(2.0 + 2.0 * index <= t < 2.9 + 2.0 * index for index in range(35)) else 0.0
        rows.append({
            "time": t * 1e-9, "vinp": vinp, "vinn": vinn, "chop_clk": chop,
            "rst": rst, "enable": enable, "hold": hold,
            "voutp": VCM + 0.5 * baseband, "voutn": VCM - 0.5 * baseband,
            "settled": settled, "offset_residual": residual,
        })
        previous_enable = enable
    if fault == "ignores_hold":
        for row in rows:
            if 19e-9 < row["time"] < 21e-9:
                row["voutp"] += 0.08
    if fault == "wrong_gain":
        for row in rows:
            if row["time"] > 10e-9:
                delta = row["voutp"] - row["voutn"]
                row["voutp"] = VCM + delta / 3.0
                row["voutn"] = VCM - delta / 3.0
    return rows


def test_gold_oracle_trace_passes() -> None:
    rows = _trace()
    assert CHECKER(rows)[0], CHECKER(rows)[1]


def test_gold_oracle_is_time_affine_invariant() -> None:
    rows = _transform_time(_trace(), scale=1.37, shift_s=2e-9)
    assert CHECKER(rows)[0], CHECKER(rows)[1]


def test_five_behavior_classes_are_rejected() -> None:
    for fault in ("no_demod", "no_offset", "no_lowpass", "ignores_hold", "wrong_gain"):
        rows = _trace(fault)
        assert not CHECKER(rows)[0], fault


def test_reset_clear_is_not_inferred_from_candidate_outputs() -> None:
    rows = deepcopy(_trace())
    for row in rows:
        if 56e-9 < row["time"] < 57e-9:
            row["settled"] = VDD
    assert not CHECKER(rows)[0]
