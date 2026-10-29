"""Write targeted wrong and alternative-correct VA candidates for later calibration."""
from pathlib import Path

CROSS = """    @(cross(V(clk) - vth, +1)) begin
        t_capture = $abstime + taperture;
        pending = 1;
    end
"""
TIMER = """    @(timer(t_capture)) begin
        if (pending) begin
            held = V(vin);
            pending = 0;
        end
    end
"""
OUTPUT = "V(vout) <+ transition(held, 0, tedge, tedge);"
INITIAL = """        held = V(vin);
        t_capture = -1.0;"""
PENDING = "integer pending; // a trigger is waiting for its aperture instant"
# A capture that arrives while vout is still moving is dropped (fix-r1, F04).
DROP_TIMER = """    @(timer(t_capture)) begin
        if (pending) begin
            if ($abstime >= t_settled) begin
                held = V(vin);
                t_settled = $abstime + tedge;
            end
            pending = 0;
        end
    end
"""
# The running transition is completed first; the newest value read meanwhile follows (fix-r1, F03).
QUEUE_TIMERS = """    @(timer(t_capture)) begin
        if (pending) begin
            if ($abstime >= t_settled) begin
                held = V(vin);
                t_settled = $abstime + tedge;
            end else begin
                queued = V(vin);
                t_apply = t_settled;
                waiting = 1;
            end
            pending = 0;
        end
    end

    @(timer(t_apply)) begin
        if (waiting) begin
            held = queued;
            t_settled = $abstime + tedge;
            waiting = 0;
        end
    end
"""


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert all(part in gold for part in (CROSS, TIMER, OUTPUT, INITIAL, PENDING))
    clamp = "min(max(V(vin), V(VSS)), V(VDD))"
    wrong = {
        # Reads vin at the trigger and only delays the visible output by taperture.
        "edge_read_delayed_output": gold.replace(CROSS, CROSS.replace("t_capture = $abstime + taperture;\n        pending = 1;", "held = V(vin);"))
                                        .replace(TIMER, "").replace(OUTPUT, "V(vout) <+ transition(held, taperture, tedge, tedge);"),
        "edge_sample_immediate": gold.replace(CROSS, CROSS.replace("t_capture = $abstime + taperture;\n        pending = 1;", "held = V(vin);")).replace(TIMER, ""),
        "read_late_by_tedge": gold.replace("$abstime + taperture;", "$abstime + taperture + tedge;"),
        "fixed_aperture": gold.replace("$abstime + taperture;", "$abstime + 200p;"),
        "fixed_threshold": gold.replace("V(clk) - vth", "V(clk) - 0.45"),
        "fixed_tedge": gold.replace(OUTPUT, "V(vout) <+ transition(held, 0, 50p, 50p);"),
        "slow_output": gold.replace(OUTPUT, "V(vout) <+ transition(held, 0, 2*tedge, 2*tedge);"),
        "init_zero": gold.replace(INITIAL, INITIAL.replace("held = V(vin);", "held = 0.0;")),
        "clamp_rails": gold.replace("held = V(vin);", f"held = {clamp};"),
        "vss_referenced": gold.replace("held = V(vin);", "held = V(vin, VSS);").replace(OUTPUT, "V(vout, VSS) <+ transition(held, 0, tedge, tedge);"),
        "both_edges": gold.replace("cross(V(clk) - vth, +1)", "cross(V(clk) - vth, 0)"),
        "above_trigger": gold.replace("cross(V(clk) - vth, +1)", "above(V(clk) - vth)"),
        "requires_clk_high": gold.replace("if (pending) begin", "if (pending && V(clk) > vth) begin"),
        "periodic_timer": gold.replace("@(timer(t_capture))", "@(timer(t_capture, taperture))").replace("held = V(vin);\n            pending = 0;", "held = V(vin);"),
        "lockout": gold.replace(PENDING, PENDING + "\nreal t_last;    // last accepted trigger")
                       .replace("pending = 0;\n    end", "pending = 0;\n        t_last = -1.0;\n    end", 1)
                       .replace("t_capture = $abstime + taperture;\n        pending = 1;",
                                "if ($abstime - t_last >= 3*taperture) begin\n            t_capture = $abstime + taperture;\n            pending = 1;\n            t_last = $abstime;\n        end"),
        "continuous_track": gold.replace(OUTPUT, "V(vout) <+ V(vin);"),
        # fix-r1: captures during a transition (F04), the queueing reading of interruption (F03),
        # and an initial value precharged to mid-supply instead of vin(0) (F05).
        "drop_while_moving": gold.replace(PENDING, PENDING + "\nreal t_settled;  // time the latest accepted transition reaches its value")
                                 .replace(INITIAL, INITIAL + "\n        t_settled = 0.0;").replace(TIMER, DROP_TIMER),
        "finish_then_turn": gold.replace(PENDING, PENDING + "\nreal t_settled;  // time the running transition completes"
                                                            "\nreal t_apply;    // when the waiting value is applied"
                                                            "\nreal queued;     // value read while vout was still moving"
                                                            "\ninteger waiting; // a read value waits for the running transition")
                                .replace(INITIAL, INITIAL + "\n        t_settled = 0.0;\n        t_apply = -1.0;\n        queued = 0.0;"
                                                            "\n        waiting = 0;").replace(TIMER, QUEUE_TIMERS),
        "init_mid_supply": gold.replace(INITIAL, INITIAL.replace("held = V(vin);", "held = 0.5*(V(VDD) + V(VSS));")),
    }
    correct = {
        # Delay the clock instead of scheduling a timer; the capture instant is the same.
        "alt_delayed_clock": gold.replace(PENDING, "real clk_late;   // clk delayed by the aperture")
                                 .replace(INITIAL + "\n        pending = 0;\n", "        held = V(vin);\n")
                                 .replace("analog begin\n", "analog begin\n    clk_late = absdelay(V(clk), taperture);\n", 1)
                                 .replace(CROSS + "\n", "").replace(TIMER, "    @(cross(clk_late - vth, +1)) held = V(vin);\n")
                                 .replace("real t_capture;  // aperture instant of the pending capture\n", ""),
        "alt_fast_output": gold.replace(OUTPUT, "V(vout) <+ transition(held, 0, 0.2*tedge, 0.2*tedge);"),
    }
    for name, source in {**wrong, **correct}.items():
        assert source != gold, name
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
