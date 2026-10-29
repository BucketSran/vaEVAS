"""Write the 071 calibration candidates derived from solution/circuit.va.

wrong/ must be rejected and correct/ accepted by the unchanged checker on the cases in
../cases.json. The F01 pair changes only the output transition time. v1_bugfix_buggy is
byte for byte the v1 bugfix starting model (src-9276ce9b6eb2, gold/dut_buggy.va), kept here
because C055-R1 is not built as its own task. prefix_reference_sample_edge_reset is byte for
byte the reference before fix-dec-r1 (2026-10-28), which returned the held value to vinit at a
rising sample crossing while rst was high. The other candidates change one rule of the
contract each. Run `python3 -B mutants.py <new or empty directory>` from any directory.
"""
import hashlib
from pathlib import Path

OUTPUT = ", 0, tr, tr)"
ALPHA = "    parameter real alpha = 0.42 from (0:1];\n"
RISE = """        @(cross(V(sample) - vth, +1)) begin
            if (V(rst) > vth) begin
                tracking = 0.0;
            end else begin
                tracking = 1.0;
            end
        end
"""
FALL = """        @(cross(V(sample) - vth, -1)) begin
            tracking = 0.0;
        end
"""
TIMER = """        @(timer(0, tick)) begin
            if (V(rst) > vth) begin
                held = vinit;
                tracking = 0.0;
            end else if (tracking > 0.5) begin
                held = held + alpha * (V(vin) - held);
            end
        end
"""
UPDATE = "held = held + alpha * (V(vin) - held);"
INIT = "            held = vinit;\n            tracking = 0.0;\n        end\n"
STATE = "    real tracking;\n"
# v1 bugfix starting model: copies vin at the opening edge and never updates on ticks.
V1_RISE = """        @(cross(V(sample) - vth, +1)) begin
            if (V(rst) > vth)
                held = vinit;
            else
                held = V(vin);
            tracking = 1.0;
        end
"""
V1_TIMER = """        @(timer(0, tick)) begin
            if (V(rst) > vth)
                held = vinit;
        end
"""
V1_BUGGY_SHA256 = "082b0724576bb4cef3fa37c234c5aa36ce7e527e4f88eefef55ff0e7f7cfd918"
# Reference before fix-dec-r1: a rising sample crossing while rst is high also returns the held value to vinit.
PREFIX_RISE = RISE.replace("                tracking = 0.0;\n            end else", "                held = vinit;\n                tracking = 0.0;\n            end else")
PREFIX_REFERENCE_SHA256 = "4482266e8bef4f54761e3b0e547efe28e37460aea448eba731d208f9eba9fa30"
# Updates on a grid that restarts at each opening crossing instead of the global k*tick grid.
LOCAL_RISE = RISE.replace("                tracking = 1.0;\n",
                          "                tracking = 1.0;\n                next_update = $abstime + tick;\n")
LOCAL_TIMER = """        @(timer(0, tick)) begin
            if (V(rst) > vth) begin
                held = vinit;
                tracking = 0.0;
            end
        end

        @(timer(next_update)) begin
            if (tracking > 0.5 && V(rst) <= vth)
                held = held + alpha * (V(vin) - held);
            next_update = next_update + tick;
        end
"""
# Reset at the rst rising crossing itself instead of the next tick.
ASYNC_RESET = """        @(cross(V(rst) - vth, +1)) begin
            held = vinit;
            tracking = 0.0;
        end
"""
# Releasing rst while sample is high reopens the window.
REOPEN = """        @(cross(V(rst) - vth, -1)) begin
            if (V(sample) > vth)
                tracking = 1.0;
        end
"""


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert [gold.count(p) for p in (OUTPUT, ALPHA, RISE, FALL, TIMER, UPDATE, INIT, STATE)] == [2, 1, 1, 1, 1, 1, 1, 1]
    v1_buggy = gold.replace(ALPHA, "").replace(RISE, V1_RISE).replace(TIMER, V1_TIMER)
    assert hashlib.sha256(v1_buggy.encode()).hexdigest() == V1_BUGGY_SHA256
    prefix = gold.replace(RISE, PREFIX_RISE)
    assert hashlib.sha256(prefix.encode()).hexdigest() == PREFIX_REFERENCE_SHA256
    local = (gold.replace(STATE, STATE + "    real next_update;\n")
                 .replace(INIT, "            held = vinit;\n            tracking = 0.0;\n            next_update = 1.0;\n        end\n")
                 .replace(RISE, LOCAL_RISE).replace(TIMER, LOCAL_TIMER))
    wrong = {
        # Both outputs arrive at 1.3*tr, after the 1.15*tr scoring start.
        "late_transition_1p3tr": gold.replace(OUTPUT, ", 0, 1.3*tr, 1.3*tr)"),
        "v1_bugfix_buggy": v1_buggy,
        # Ideal sampler: each tick copies vin (alpha taken as 1).
        "ideal_sampler_alpha_one": gold.replace(UPDATE, "held = V(vin);"),
        "local_tick_grid": local,
        "prefix_reference_sample_edge_reset": prefix,
        "async_reset_on_rst_edge": gold.replace(FALL, FALL + "\n" + ASYNC_RESET),
        "reopen_on_rst_release": gold.replace(FALL, FALL + "\n" + REOPEN),
        # A reset tick returns the held value to vinit but leaves the window open.
        "reset_keeps_window": gold.replace(TIMER, TIMER.replace("                held = vinit;\n                tracking = 0.0;\n",
                                                                "                held = vinit;\n")),
    }
    correct = {
        # Arrival at 1.1*tr lies between the tr deadline and the 1.15*tr scoring start: the accepted margin.
        "inwindow_transition_1p1tr": gold.replace(OUTPUT, ", 0, 1.1*tr, 1.1*tr)"),
        # Same law with the tick block before the crossing blocks; differs from the reference
        # only when a sample crossing falls exactly on a tick, which no case does.
        "alt_timer_before_cross": gold.replace(RISE + "\n" + FALL + "\n" + TIMER, TIMER + "\n" + RISE + "\n" + FALL),
    }
    assert correct["alt_timer_before_cross"] != gold
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
