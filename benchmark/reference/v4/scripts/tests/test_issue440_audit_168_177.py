from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
RUNNERS = ROOT / "runners"
if str(RUNNERS) not in sys.path:
    sys.path.insert(0, str(RUNNERS))

from checkers.v4.task_170 import check_v3_comparator_delay_overdrive_meter
from checkers.v4.task_168 import check_v3_dac_ideal_4b_offset
from checkers.v4.task_171 import check_v3_comparator_offset_driver
from checkers.v4.task_172 import check_v3_pipe_2lane_edge_align
from checkers.v4.task_174 import check_v3_iterative_isar_dac
from checkers.v4.task_176 import check_v3_weighted_decoder_7b5
from checkers.v4.task_177 import check_v3_sync_8b_dffs_v2


RELEASE = ROOT / "benchmark-vabench-release-v4/provenance/dut-base-v3-exact-five-hash-bound-v2"


def _rows(stop_ns: float, step_ns: float = 0.025) -> list[dict[str, float]]:
    return [{"time": index * step_ns * 1e-9} for index in range(round(stop_ns / step_ns) + 1)]


def _semantic_deck_lines(path: Path) -> list[str]:
    return [
        line
        for line in path.read_text().splitlines()
        if line and not line.startswith("simulatorOptions options")
    ]


def _wrong_swapped_dac_rows(codes: list[int]) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for window, code in enumerate(codes):
        bits = [(code >> bit) & 1 for bit in range(4)]
        swapped = bits.copy()
        swapped[0], swapped[2] = swapped[2], swapped[0]
        wrong_code = sum(bit << index for index, bit in enumerate(swapped))
        for sample_index in range(101):
            row = {
                "time": (window * 10.0 + sample_index * 0.1) * 1e-9,
                "dout": 0.239 + wrong_code / (32.0 * 10.0 / 9.0),
            }
            row.update({f"din{bit}": float(bits[bit]) for bit in range(4)})
            rows.append(row)
    return rows


def _weighted_outputs(bits: list[int]) -> dict[str, float]:
    weights = [1.0, 2.0, 4.0, 8.0, 8.0, 16.0, 32.0, 64.0]
    denom = 2.0 * (sum(weights) + 1.0)
    bipolar = [1.0 if bit else -1.0 for bit in bits]
    paired_lsb = 1.0 if bits[0] and bits[1] else -1.0 if not bits[0] and not bits[1] else 0.0
    return {
        "aout7b": sum(weight * bipolar[index + 1] for index, weight in enumerate(weights)) / denom,
        "aout8b": (0.5 * bipolar[0] + sum(weight * bipolar[index + 1] for index, weight in enumerate(weights))) / denom,
        "aout7b5": (paired_lsb + sum(weight * bipolar[index + 2] for index, weight in enumerate(weights[1:]))) / denom,
    }


def _wrong_swapped_weighted_rows(states: list[list[int]]) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for state_index, bits in enumerate(states):
        wrong_bits = bits.copy()
        wrong_bits[4], wrong_bits[6] = wrong_bits[6], wrong_bits[4]
        outputs = _weighted_outputs(wrong_bits)
        for sample_index in range(31):
            row = {"time": (state_index * 1.0 + sample_index * 0.02) * 1e-9, **outputs}
            row.update({f"d{bit}": 0.9 * bits[bit] for bit in range(9)})
            rows.append(row)
    return rows


def test_score_stimuli_break_decoder_bit_aliases() -> None:
    dac_dir = RELEASE / "168-dac-ideal-4b-offset"
    dac = (dac_dir / "evaluator/score_tb.scs").read_text()
    assert _semantic_deck_lines(dac_dir / "public/task/feedback_tb.scs") == _semantic_deck_lines(
        dac_dir / "evaluator/score_tb.scs"
    )
    assert "Vdin0" in dac and "8n 1.0" in dac
    assert "Vdin1" in dac and "18n 1.0" in dac
    assert "Vdin2" in dac and "28n 1.0" in dac
    assert "Vdin3" in dac and "38n 1.0" in dac
    assert "tran tran stop=60n" in dac

    weighted_dir = RELEASE / "176-weighted-decoder-7b5"
    weighted = (weighted_dir / "evaluator/score_tb.scs").read_text()
    assert _semantic_deck_lines(
        weighted_dir / "public/task/feedback_tb.scs"
    ) == _semantic_deck_lines(weighted_dir / "evaluator/score_tb.scs")
    for bit, start_ns in enumerate(range(5, 50, 5)):
        line = next(line for line in weighted.splitlines() if line.startswith(f"Vd{bit} "))
        assert f"{start_ns}n 0.9" in line
    assert "tran tran stop=55n" in weighted

    old_dac_passed, _ = check_v3_dac_ideal_4b_offset(
        _wrong_swapped_dac_rows([0, 5, 10, 15])
    )
    new_dac_passed, _ = check_v3_dac_ideal_4b_offset(
        _wrong_swapped_dac_rows([0, 1, 2, 4, 8, 15])
    )
    assert old_dac_passed
    assert not new_dac_passed

    old_states = [
        [0] * 9,
        [1, 1, 0, 1, 0, 1, 0, 1, 0],
        [0, 0, 1, 0, 1, 0, 1, 0, 1],
        [1, 1, 0, 1, 0, 1, 0, 1, 1],
    ]
    new_states = [[0] * 9] + [
        [1 if bit == active else 0 for bit in range(9)]
        for active in range(9)
    ] + [[1] * 9]
    old_weighted_passed, _ = check_v3_weighted_decoder_7b5(
        _wrong_swapped_weighted_rows(old_states)
    )
    new_weighted_passed, _ = check_v3_weighted_decoder_7b5(
        _wrong_swapped_weighted_rows(new_states)
    )
    assert old_weighted_passed
    assert not new_weighted_passed


def test_comparator_meter_rejects_valid_that_never_clears_on_arm() -> None:
    rows = _rows(8.0)
    clk_rises = (1.0, 3.0, 5.0, 7.0)
    decisions = tuple(value + 0.5 for value in clk_rises)
    for row in rows:
        t_ns = row["time"] * 1e9
        cycle = min(int(t_ns // 2.0), 3)
        positive = cycle % 2 == 0
        row.update(
            clk=0.9 if any(rise <= t_ns < rise + 0.4 for rise in clk_rises) else 0.0,
            vinp=0.55 if positive else 0.45,
            vinn=0.45 if positive else 0.55,
            outp=0.9 if positive and decisions[cycle] <= t_ns < clk_rises[cycle] + 1.5 else 0.0,
            outn=0.9 if (not positive) and decisions[cycle] <= t_ns < clk_rises[cycle] + 1.5 else 0.0,
            delay_ps=0.5e-9,
            overdrive_mv=0.1,
            polarity=0.9 if positive else 0.0,
            valid=0.9,
        )
    passed, note = check_v3_comparator_delay_overdrive_meter(rows)
    assert not passed
    assert "valid" in note


def test_offset_driver_rejects_update_before_falling_edge() -> None:
    rows = _rows(6.0)
    for row in rows:
        t_ns = row["time"] * 1e9
        update_count = sum(t_ns >= rise for rise in (1.0, 3.0, 5.0))
        diff = (0.0, -0.05, -0.075, -0.0875)[update_count]
        row.update(
            clk=0.9 if any(rise <= t_ns < rise + 0.5 for rise in (1.0, 3.0, 5.0)) else 0.0,
            dcmpp=0.9,
            vinp=0.45 + 0.5 * diff,
            vinn=0.45 - 0.5 * diff,
        )
    passed, note = check_v3_comparator_offset_driver(rows)
    for edge_ns, expected_diff in ((1.5, -0.05), (3.5, -0.075), (5.5, -0.0875)):
        post = min(rows, key=lambda row: abs(row["time"] - (edge_ns + 0.25) * 1e-9))
        assert abs((post["vinp"] - post["vinn"]) - expected_diff) < 1e-12
    assert not passed
    assert "pre_falling_diff" in note


def test_edge_align_rejects_wrong_initial_lane() -> None:
    rows = _rows(5.0)
    for row in rows:
        t_ns = row["time"] * 1e9
        row.update(
            din1=0.9,
            din2=0.0,
            clk_align=0.9 if 1.0 <= t_ns < 2.0 or 3.0 <= t_ns < 4.0 else 0.0,
            dout=0.0 if t_ns < 1.0 else (0.9 if t_ns < 2.0 or 3.0 <= t_ns < 4.0 else 0.0),
        )
    passed, note = check_v3_pipe_2lane_edge_align(rows)
    assert not passed
    assert "initial_dout" in note


def test_iterative_isar_rejects_nonzero_pre_reset_state() -> None:
    rows = _rows(6.0)
    for row in rows:
        t_ns = row["time"] * 1e9
        updates = sum(t_ns >= rise for rise in (2.0, 3.0, 4.0, 5.0))
        vdac = 0.05 if t_ns < 1.0 else sum(0.05 / (2**index) for index in range(updates))
        row.update(
            dcmp=0.0,
            rst=0.9 if 1.0 <= t_ns < 1.5 else 0.0,
            clk=0.9 if any(rise <= t_ns < rise + 0.2 for rise in (2.0, 3.0, 4.0, 5.0)) else 0.0,
            vdac=vdac,
        )
    passed, note = check_v3_iterative_isar_dac(rows)
    assert not passed
    assert "initial_vdac" in note


def test_sync_pipeline_rejects_direct_final_clock_capture() -> None:
    sync_dir = RELEASE / "177-sync-8b-dffs-v2"
    deck = (sync_dir / "evaluator/score_tb.scs").read_text()
    assert _semantic_deck_lines(sync_dir / "public/task/feedback_tb.scs") == _semantic_deck_lines(
        sync_dir / "evaluator/score_tb.scs"
    )
    assert "Vdl8" in deck and "1.3n 0" in deck
    assert "Vdl0" in deck and "9.3n 0" in deck
    assert "tran tran stop=20.5n" in deck

    legacy_rows = _rows(10.5)
    first_pattern = (1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    for row in legacy_rows:
        t_ns = row["time"] * 1e9
        for clock in range(1, 10):
            first_rise = 10.0 - clock
            row[f"ck{clock}"] = 0.9 if first_rise <= t_ns < first_rise + 0.5 else 0.0
        for bit, value in enumerate(first_pattern):
            row[f"do{bit}"] = value if t_ns >= 9.05 else 0.0
    legacy_passed, legacy_note = check_v3_sync_8b_dffs_v2(legacy_rows)
    assert legacy_passed, legacy_note

    rows = _rows(20.5)
    second_pattern = (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0)
    for row in rows:
        t_ns = row["time"] * 1e9
        for clock in range(1, 10):
            first_rise = 10.0 - clock
            row[f"ck{clock}"] = 0.9 if (
                first_rise <= t_ns < first_rise + 0.5
                or first_rise + 10.0 <= t_ns < first_rise + 10.5
            ) else 0.0
        for bit, value in enumerate(second_pattern):
            row[f"do{bit}"] = value if t_ns >= 9.05 else 0.0
    passed, note = check_v3_sync_8b_dffs_v2(rows)
    assert not passed
    assert "do0@9.7ns" in note
