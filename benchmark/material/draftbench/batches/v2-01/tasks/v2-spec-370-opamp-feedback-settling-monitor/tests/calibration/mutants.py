"""Write the 370 calibration candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the cases in
../cases.json. The F01 pair changes only the output transition time. The two polling
candidates keep the update law and change only when an update happens: at the actual clk
crossing instead of the next global tick, or on ticks shifted by half a tick. The other
candidates change one rule each: the settled low level (settled_low_zero is byte for byte
the reference before fix-dec-r1, 2026-10-28), the gain decode, one side of the target clamp,
or where the previous clk level is tracked. Run `python3 -B mutants.py <new or empty directory>`
from any directory.
"""
import hashlib
from pathlib import Path

OUTPUT = ", 0, tr, tr)"
TIMER = "@(timer(0, tick)) begin"
EDGE = "else if (V(clk) > vth && prev_clk <= vth) begin"
DECODE = "code = 0; if (V(gain_0) > vth) code = code + 1; if (V(gain_1) > vth) code = code + 2; if (V(gain_2) > vth) code = code + 4;"
TARGET = "target = clip(vcm + (1.0 + gain_lsb * mapped_code) * (V(vin) - vcm));"
BODY = """                """ + DECODE + """
                mapped_code = code;
                """ + TARGET + """
                vout_v = clip(vout_v + alpha * (target - vout_v));
                err_v = target - vout_v;
                if (absval(err_v) < settle_tol) settle_count = settle_count + 1; else settle_count = 0;
                settled_v = (settle_count >= 3) ? vdd : vss;
"""
INIT_LOW = "err_v = 0.0; settled_v = vss; end"
RESET_LOW = "<= vth) begin settle_count = 0; vout_v = vcm; err_v = 0.0; settled_v = vss; end"
PREV = "            prev_clk = V(clk);\n"
PREFIX_REFERENCE_SHA256 = "7b4b354ff35d8c791ea26597ef556be745f5923ce65012816bcef0c8bca20bf6"
# Same update law at each rising clk crossing; reset and disable still act on the ticks.
CROSS = """        @(cross(V(clk) - vth, +1)) begin
            if (V(rst) <= vth && V(enable) > vth) begin
""" + BODY + """            end
        end
"""
RAW = "target = vcm + (1.0 + gain_lsb * mapped_code) * (V(vin) - vcm);"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert [gold.count(p) for p in (OUTPUT, TIMER, EDGE, BODY, INIT_LOW, RESET_LOW, PREV)] == [3, 1, 1, 1, 2, 1, 1]
    prefix = gold.replace("settled_v = vss; end", "settled_v = 0.0; end")
    assert hashlib.sha256(prefix.encode()).hexdigest() == PREFIX_REFERENCE_SHA256
    wrong = {
        # The three outputs arrive at 1.3*tr, after the 1.15*tr scoring start.
        "late_transition_1p3tr": gold.replace(OUTPUT, ", 0, 1.3*tr, 1.3*tr)"),
        "edge_triggered_update": gold.replace(EDGE, "else if (0) begin").replace("        @(timer(0, tick)) begin", CROSS + "        @(timer(0, tick)) begin"),
        # Polling on (k + 1/2)*tick instead of the global k*tick grid.
        "half_tick_phase": gold.replace(TIMER, "@(timer(0.5*tick, tick)) begin"),
        # settled low level 0 V instead of vss at power-up and in reset or disable.
        "settled_low_zero": prefix,
        "reset_settled_zero": gold.replace(RESET_LOW, RESET_LOW.replace("settled_v = vss;", "settled_v = (V(rst) > vth) ? 0.0 : vss;")),
        "disable_settled_zero": gold.replace(RESET_LOW, RESET_LOW.replace("settled_v = vss;", "settled_v = (V(rst) > vth) ? vss : 0.0;")),
        # Gain bits read with swapped weights: gain_0 counts 4 and gain_2 counts 1.
        "gain_bits_reversed": gold.replace(DECODE, DECODE.replace("code = code + 1; if (V(gain_1)", "code = code + 4; if (V(gain_1)")
                                                          .replace("if (V(gain_2) > vth) code = code + 4;", "if (V(gain_2) > vth) code = code + 1;")),
        # Only gain_0 is read; it selects the full code 7.
        "gain_code_from_bit0_only": gold.replace(DECODE, "code = 0; if (V(gain_0) > vth) code = 7;"),
        "target_no_upper_clamp": gold.replace(TARGET, RAW + " if (target < vss) target = vss;"),
        "target_no_lower_clamp": gold.replace(TARGET, RAW + " if (target > vdd) target = vdd;"),
        # The previous clk level is not taken at ticks in reset (or, in the second, in disable).
        "prev_clk_frozen_in_reset": gold.replace(PREV, "            if (V(rst) <= vth) prev_clk = V(clk);\n"),
        "prev_clk_frozen_in_disable": gold.replace(PREV, "            if (V(rst) > vth || V(enable) > vth) prev_clk = V(clk);\n"),
    }
    correct = {
        # Arrival at 1.1*tr lies between the tr deadline and the 1.15*tr scoring start: the accepted margin.
        "inwindow_transition_1p1tr": gold.replace(OUTPUT, ", 0, 1.1*tr, 1.1*tr)"),
    }
    assert wrong["edge_triggered_update"].count(BODY) == 2
    assert all(source != gold for source in wrong.values())
    return wrong, correct


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("output", type=Path, help="new or empty directory")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"{args.output}: output must be a new or empty directory")
    wrong, correct = candidates()
    for group, items in (("wrong", wrong), ("correct", correct)):
        (args.output / group).mkdir(parents=True, exist_ok=True)
        for name, source in items.items():
            (args.output / group / (name + ".va")).write_text(source)
