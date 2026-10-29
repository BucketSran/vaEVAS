"""Write targeted wrong and alternative-correct VA candidates for later calibration."""
from pathlib import Path

FILTER_BLOCK = """        // H(z) = 0.25/(1 - 0.75 z^-1): numerator 0.25 and a real pole at 0.75, unity DC
        // gain, sampled every tupdate from t = 0. Zero transition time keeps the value
        // constant between update instants. The operator runs outside any event, so
        // clock and reset never touch its updates. It starts from the DC operating
        // point, H(1)*V(vin) = V(vin).
        filtered = zi_np(V(vin), {0.25}, {0.75, 0.0}, tupdate, 0.0);
"""
ZI = "zi_np(V(vin), {0.25}, {0.75, 0.0}, tupdate, 0.0)"
CROSS = "@(cross(V(clk) - vth, +1)) begin"
RESET = "if (V(rst) > vth)\n                held = 0.0;"
SAMPLE = "held = filtered;"
OUTPUT = "V(out) <+ transition(held, 0.0, tr, tr);"
INIT = "        @(initial_step)\n            held = 0.0;\n"
# Scalar-state recursion on an internal timer, equilibrium start (no zi operator).
TIMER_BLOCK = """        // y_k = 0.25*x_k + 0.75*y_(k-1) every tupdate from t = 0; equilibrium start.
        @(initial_step)
            filtered = V(vin);
        @(timer(0, tupdate))
            filtered = 0.25*V(vin) + 0.75*filtered;
"""
TIMER_UPDATE = "@(timer(0, tupdate))\n            filtered = 0.25*V(vin) + 0.75*filtered;"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert all(gold.count(part) == 1 for part in (FILTER_BLOCK, ZI, CROSS, RESET, SAMPLE, OUTPUT, INIT))
    timer = gold.replace(FILTER_BLOCK, TIMER_BLOCK)
    wrong = {
        # Continuous-time filters: the same pole (step-invariant mapping) and the Euler time constant.
        "continuous_same_pole": gold.replace(ZI, "laplace_nd(V(vin), {1.0}, {1.0, tupdate/ln(4.0/3.0)})"),
        "continuous_euler_tau": gold.replace(ZI, "laplace_nd(V(vin), {1.0}, {1.0, 4.0*tupdate})"),
        # The recursion moved onto the external clock edge.
        "update_on_clock": gold.replace(FILTER_BLOCK, "        @(initial_step)\n            filtered = V(vin);\n")
                               .replace(CROSS, CROSS + "\n            filtered = 0.25*V(vin) + 0.75*filtered;"),
        "one_period_delay": gold.replace(ZI, "zi_np(V(vin), {0.0, 0.25}, {0.75, 0.0}, tupdate, 0.0)"),
        "half_period_phase": gold.replace(ZI, "zi_np(V(vin), {0.25}, {0.75, 0.0}, tupdate, 0.0, 0.5*tupdate)"),
        "interpolated_between_updates": gold.replace(ZI, "zi_np(V(vin), {0.25}, {0.75, 0.0}, tupdate, tupdate)"),
        "swapped_coefficients": gold.replace(ZI, "zi_np(V(vin), {0.75}, {0.25, 0.0}, tupdate, 0.0)"),
        "fixed_tupdate_100n": gold.replace(ZI, "zi_np(V(vin), {0.25}, {0.75, 0.0}, 100n, 0.0)"),
        "zero_initial_state": timer.replace("filtered = V(vin);", "filtered = 0.0;"),
        "reset_clears_filter": timer.replace(RESET, "if (V(rst) > vth) begin\n                held = 0.0;\n"
                                                    "                filtered = 0.0;\n            end"),
        "filter_frozen_in_reset": timer.replace(TIMER_UPDATE, "@(timer(0, tupdate))\n            if (V(rst) <= vth)\n"
                                                              "                filtered = 0.25*V(vin) + 0.75*filtered;"),
        "asynchronous_reset": gold.replace(INIT, INIT + "\n        @(cross(V(rst) - vth, +1))\n            held = 0.0;\n"),
        "sample_input_directly": gold.replace(SAMPLE, "held = V(vin);"),
        "transparent_output": gold.replace(OUTPUT, "V(out) <+ transition(filtered, 0.0, tr, tr);"),
        "falling_edge_sample": gold.replace(CROSS, "@(cross(V(clk) - vth, -1)) begin"),
        "clamp_at_zero": gold.replace(SAMPLE, "held = max(filtered, 0.0);"),
        "slow_output": gold.replace(OUTPUT, "V(out) <+ transition(held, 0.0, 2*tr, 2*tr);"),
        # Arrives after the 1.25*tr scoring start (p0-fix-a).
        "late_arrival_1p3tr": gold.replace(OUTPUT, "V(out) <+ transition(held, 0.0, 1.3*tr, 1.3*tr);"),
        # Ignore the vth and tr parameters (p0-fix-a).
        "fixed_vth": gold.replace(CROSS, "@(cross(V(clk) - 0.45, +1)) begin")
                         .replace(RESET, RESET.replace("V(rst) > vth", "V(rst) > 0.45")),
        "fixed_tr": gold.replace(OUTPUT, "V(out) <+ transition(held, 0.0, 200p, 200p);"),
    }
    correct = {
        "alt_timer_recursion": timer,
        # Numerator-denominator form of the same H(z); correct when zi_nd starts from its DC point.
        "alt_zi_nd": gold.replace(ZI, "zi_nd(V(vin), {0.25}, {1.0, -0.75}, tupdate, 0.0)"),
        "alt_fast_output": gold.replace(OUTPUT, "V(out) <+ transition(held, 0.0, 0.2*tr, 0.2*tr);"),
        # Not a correct model: arrives after the tr deadline but before the 1.25*tr scoring
        # start, the margin the user accepted (p0-fix-a).
        "margin_arrival_1p2tr": gold.replace(OUTPUT, "V(out) <+ transition(held, 0.0, 1.2*tr, 1.2*tr);"),
    }
    assert TIMER_UPDATE in timer
    assert "vth" not in wrong["fixed_vth"].split("analog begin")[1]
    for name, source in {**wrong, **correct}.items():
        assert source != gold and source != timer or name == "alt_timer_recursion", name
    return wrong, correct


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    wrong, correct = candidates()
    for group, items in (("wrong", wrong), ("correct", correct)):
        (args.output / group).mkdir(parents=True, exist_ok=True)
        for name, source in items.items():
            (args.output / group / (name + ".va")).write_text(source)
