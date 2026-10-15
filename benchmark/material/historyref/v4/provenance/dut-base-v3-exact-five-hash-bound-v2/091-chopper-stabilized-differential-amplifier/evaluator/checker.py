"""Independent waveform oracle for canonical v4 family 091."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median


VDD = 0.9
VSS = 0.0
VCM = 0.45
VTH = 0.45
GAIN = 3.0
VOS_AMP = 0.020
LP_ALPHA = 0.25
SETTLE_TOL = 0.020
SETTLE_CYCLES = 3


def _sample(rows: list[dict[str, float]], signal: str, time_s: float) -> float:
    for left, right in zip(rows, rows[1:]):
        if left["time"] <= time_s <= right["time"]:
            span = right["time"] - left["time"]
            if span == 0.0:
                return right[signal]
            alpha = (time_s - left["time"]) / span
            return left[signal] + alpha * (right[signal] - left[signal])
    return rows[-1][signal]


def _crossings(rows: list[dict[str, float]], signal: str, direction: int) -> list[float]:
    result: list[float] = []
    for left, right in zip(rows, rows[1:]):
        v0, v1 = left[signal], right[signal]
        hit = v0 <= VTH < v1 if direction > 0 else v0 >= VTH > v1
        if hit:
            fraction = (VTH - v0) / (v1 - v0) if v1 != v0 else 1.0
            result.append(left["time"] + fraction * (right["time"] - left["time"]))
    return result


@dataclass
class _State:
    baseband: float = 0.0
    residual: float = 0.0
    settled: float = VSS
    converged: int = 0

    def clear(self) -> None:
        self.baseband = 0.0
        self.residual = 0.0
        self.settled = VSS
        self.converged = 0

    def update(self, input_diff: float, polarity: int) -> None:
        chopped = polarity * input_diff
        amplified = GAIN * (chopped + VOS_AMP)
        demodulated = polarity * amplified
        self.baseband += LP_ALPHA * (demodulated - self.baseband)
        self.residual = self.baseband - GAIN * input_diff
        self.converged = self.converged + 1 if abs(self.residual) <= SETTLE_TOL else 0
        self.settled = VDD if self.converged >= SETTLE_CYCLES else VSS

    def outputs(self) -> dict[str, float]:
        return {
            "voutp": min(VDD, max(VSS, VCM + 0.5 * self.baseband)),
            "voutn": min(VDD, max(VSS, VCM - 0.5 * self.baseband)),
            "settled": self.settled,
            "offset_residual": self.residual,
        }


def check_chopper_stabilized_differential_amplifier(
    rows: list[dict[str, float]],
) -> tuple[bool, str]:
    required = {
        "time", "vinp", "vinn", "chop_clk", "rst", "enable", "hold",
        "voutp", "voutn", "settled", "offset_residual",
    }
    if not rows or not required.issubset(rows[0]):
        missing = sorted(required - (set(rows[0]) if rows else set()))
        return False, "missing_columns=" + ",".join(missing)
    if len(rows) < 20:
        return False, "insufficient_excitation trace_rows"

    steps = [b["time"] - a["time"] for a, b in zip(rows, rows[1:]) if b["time"] > a["time"]]
    step = median(steps)
    chop_rising = _crossings(rows, "chop_clk", +1)
    chop_periods = [right - left for left, right in zip(chop_rising, chop_rising[1:])]
    if not chop_periods:
        return False, "insufficient_excitation chop_periods"
    chop_period = median(chop_periods)
    guard = max(0.225 * chop_period, 8.0 * step)
    probe_offset = max(5e-4 * chop_period, 0.05 * step)
    events: list[tuple[float, int, str, int]] = []
    events += [(time_s, 1, "chop", +1) for time_s in chop_rising]
    events += [(time_s, 1, "chop", -1) for time_s in _crossings(rows, "chop_clk", -1)]
    events += [(time_s, 0, "clear", 0) for time_s in _crossings(rows, "rst", +1)]
    events += [(time_s, 0, "clear", 0) for time_s in _crossings(rows, "enable", -1)]
    events.sort()
    if len([event for event in events if event[2] == "chop"]) < 16:
        return False, "insufficient_excitation chop_edges"

    state = _State()
    checked = active_updates = hold_edges = clear_events = 0
    positive_updates = negative_updates = settled_rows = 0
    errors: list[str] = []

    for index, (event_time, _priority, kind, polarity) in enumerate(events):
        probe = min(rows[-1]["time"], event_time + probe_offset)
        rst = _sample(rows, "rst", probe)
        enable = _sample(rows, "enable", probe)
        hold = _sample(rows, "hold", probe)
        if kind == "clear" or rst > VTH or enable <= VTH:
            state.clear()
            clear_events += 1
        elif hold > VTH:
            hold_edges += 1
        else:
            input_diff = _sample(rows, "vinp", probe) - _sample(rows, "vinn", probe)
            state.update(input_diff, polarity)
            active_updates += 1
            positive_updates += polarity > 0
            negative_updates += polarity < 0

        next_time = events[index + 1][0] if index + 1 < len(events) else rows[-1]["time"]
        for row in rows:
            if not (event_time + guard <= row["time"] < next_time - 0.5 * step):
                continue
            for signal, expected in state.outputs().items():
                tolerance = 0.015 if signal != "settled" else 0.08
                checked += 1
                if abs(row[signal] - expected) > tolerance:
                    errors.append(
                        f"{signal}@{row['time'] * 1e9:.3f}ns={row[signal]:.5f} expected={expected:.5f}"
                    )
                    if len(errors) >= 5:
                        break
            settled_rows += row["settled"] > VTH
            if len(errors) >= 5:
                break
        if len(errors) >= 5:
            break

    coverage_ok = (
        active_updates >= 12 and hold_edges >= 2 and clear_events >= 2
        and positive_updates >= 5 and negative_updates >= 5 and settled_rows >= 2
        and checked >= 100
    )
    ok = not errors and coverage_ok
    note = (
        f"checked={checked} active={active_updates} hold_edges={hold_edges} clears={clear_events} "
        f"polarity=+{positive_updates}/-{negative_updates} settled_rows={settled_rows} "
        f"errors={len(errors)}"
    )
    if errors:
        note += " first=" + errors[0]
    elif not coverage_ok:
        note = "insufficient_excitation " + note
    return ok, note


CHECKER_ID = "v4_091_chopper_stabilized_differential_amplifier"
CHECKER = check_chopper_stabilized_differential_amplifier
