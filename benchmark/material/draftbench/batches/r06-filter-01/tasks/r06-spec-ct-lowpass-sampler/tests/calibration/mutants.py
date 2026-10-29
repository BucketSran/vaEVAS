"""Write targeted wrong and alternative-correct VA candidates for later calibration.

probe/ holds a numerical probe that is not a calibration candidate (see the README).
"""
from pathlib import Path

FILTER_BLOCK = """        // H(s) = 1/(1 + s*tau), unity DC gain. The operator is evaluated on every
        // time step, outside any event, so clock and reset never restart or freeze
        // it. Its state starts at the DC operating point: filtered = V(vin) at t = 0.
        filtered = laplace_nd(V(vin), {1.0}, {1.0, tau});
"""
LAPLACE = "laplace_nd(V(vin), {1.0}, {1.0, tau})"
STATE = "    real filtered;\n    real held;\n"
CROSS = "@(cross(V(clk) - vth, +1)) begin"
RESET = "if (V(rst) > vth)\n                held = 0.0;"
SAMPLE = "held = filtered;"
OUTPUT = "V(out) <+ transition(held, 0.0, tr, tr);"
INIT = "        @(initial_step)\n            held = 0.0;\n"
# Scalar state, no analog operator: the exact response of tau*dy/dt = vin - y over each 25 ps step,
# vin taken as linear across the step, equilibrium start. A sample uses the same step from the last tick.
# It reads vin only at the ticks and at sample events, so it is exact only while vin is linear between
# those reads, as on the fixed cases (every vin corner lies on the 25 ps grid). The contract lets vin change
# anywhere, so this is a numerical probe for the fixed benches, not a correct candidate; the three
# filter-state wrong candidates are built on it.
STEP_STATE = "    real filtered;\n    real held;\n    real y_last, x_last, t_last, h, slope;\n"
STEP_BLOCK = """        // Exact first-order response over each 25 ps step with vin linear across it; equilibrium start.
        @(initial_step) begin
            y_last = V(vin);
            x_last = V(vin);
            t_last = 0.0;
        end
        @(timer(0, 25p)) begin
            h = $abstime - t_last;
            if (h > 0) begin
                slope = (V(vin) - x_last) / h;
                y_last = V(vin) - slope*tau + (y_last - x_last + slope*tau)*exp(-h/tau);
                x_last = V(vin);
                t_last = $abstime;
            end
        end
"""
STEP_VALUE = """            h = $abstime - t_last;
            filtered = y_last;
            if ($abstime > t_last) begin
                slope = (V(vin) - x_last) / h;
                filtered = V(vin) - slope*tau + (y_last - x_last + slope*tau)*exp(-h/tau);
            end
"""
STEP_RESTART = """                y_last = 0.0;
                x_last = V(vin);
                t_last = $abstime;
"""
STEP_UPDATE = "            if (h > 0) begin\n"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert all(gold.count(part) == 1 for part in (FILTER_BLOCK, LAPLACE, STATE, CROSS, RESET, SAMPLE, OUTPUT, INIT))
    step = gold.replace(STATE, STEP_STATE).replace(FILTER_BLOCK, STEP_BLOCK).replace(CROSS, CROSS + "\n" + STEP_VALUE)
    wrong = {
        # Filter law
        "sample_input_directly": gold.replace(SAMPLE, "held = V(vin);"),
        "discrete_update_at_clock": gold.replace(STATE, STATE + "    real t_prev;\n").replace(FILTER_BLOCK, "")
                                        .replace(INIT, "        @(initial_step) begin\n            held = 0.0;\n"
                                                       "            filtered = V(vin);\n            t_prev = 0.0;\n        end\n")
                                        .replace(CROSS, CROSS + "\n            // first-order update only at the clock edge\n"
                                                 "            filtered = filtered + (V(vin) - filtered)*(1 - exp(-($abstime - t_prev)/tau));\n"
                                                 "            t_prev = $abstime;"),
        "tau_from_cutoff": gold.replace(LAPLACE, "laplace_nd(V(vin), {1.0}, {1.0, tau/(2*`M_PI)})"),
        "fixed_tau_100n": gold.replace(LAPLACE, "laplace_nd(V(vin), {1.0}, {1.0, 100n})"),
        # Filter state across start-up and reset (scalar step version, so no operator state is needed)
        "zero_initial_state": step.replace("            y_last = V(vin);\n", "            y_last = 0.0;\n"),
        "reset_restarts_filter": step.replace(RESET, "if (V(rst) > vth) begin\n                held = 0.0;\n" + STEP_RESTART
                                              + "            end"),
        "filter_frozen_in_reset": step.replace(STEP_UPDATE, "            if (h > 0 && V(rst) > vth) begin\n"
                                                            "                x_last = V(vin);\n                t_last = $abstime;\n"
                                                            "            end else if (h > 0) begin\n"),
        # Sampler and output
        "asynchronous_reset": gold.replace(INIT, INIT + "\n        @(cross(V(rst) - vth, +1))\n            held = 0.0;\n"),
        "transparent_output": gold.replace(OUTPUT, "V(out) <+ transition(filtered, 0.0, tr, tr);"),
        "one_sample_latency": gold.replace(STATE, STATE + "    real pending;\n")
                                  .replace(INIT, "        @(initial_step) begin\n            held = 0.0;\n            pending = 0.0;\n        end\n")
                                  .replace(RESET + "\n            else\n                " + SAMPLE,
                                           "held = pending;\n            if (V(rst) > vth)\n                pending = 0.0;\n"
                                           "            else\n                pending = filtered;"),
        "falling_edge_sample": gold.replace(CROSS, "@(cross(V(clk) - vth, -1)) begin"),
        "clamp_at_zero": gold.replace(SAMPLE, "held = max(filtered, 0.0);"),
        "slow_output": gold.replace(OUTPUT, "V(out) <+ transition(held, 0.0, 2*tr, 2*tr);"),
        # fix-r1: arrival after the scoring start (F01), a fixed threshold and a fixed transition (F08)
        "late_arrival_1p3tr": gold.replace(OUTPUT, "V(out) <+ transition(held, 0.0, 1.3*tr, 1.3*tr);"),
        "fixed_vth": gold.replace(CROSS, "@(cross(V(clk) - 0.45, +1)) begin").replace("V(rst) > vth", "V(rst) > 0.45"),
        "fixed_tr": gold.replace(OUTPUT, "V(out) <+ transition(held, 0.0, 200p, 200p);"),
    }
    correct = {
        "alt_ddt_node": gold.replace(STATE, STATE + "    electrical ynode;  // filter state as an internal node\n")
                            .replace(FILTER_BLOCK, "        // tau*dV(ynode)/dt = V(vin) - V(ynode); the DC point gives V(ynode) = V(vin).\n"
                                                   "        I(ynode) <+ V(ynode) - V(vin);\n        I(ynode) <+ ddt(tau*V(ynode));\n"
                                                   "        filtered = V(ynode);\n"),
        "alt_laplace_np": gold.replace(LAPLACE, "laplace_np(V(vin), {1.0}, {-1.0/tau, 0.0})"),
        "alt_fast_output": gold.replace(OUTPUT, "V(out) <+ transition(held, 0.0, 0.2*tr, 0.2*tr);"),
    }
    probe = {"probe_step_recursion_25p": step}
    for name, source in {**wrong, **correct}.items():
        assert source != gold and source != step, name
    return wrong, correct, probe


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    wrong, correct, probe = candidates()
    for group, items in (("wrong", wrong), ("correct", correct), ("probe", probe)):
        (args.output / group).mkdir(parents=True, exist_ok=True)
        for name, source in items.items():
            (args.output / group / (name + ".va")).write_text(source)
