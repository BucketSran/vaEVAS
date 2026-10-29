"""Write targeted wrong and alternative-correct VA candidates for later calibration."""
from pathlib import Path

FALL_SIG = """        @(cross(V(sig) - vth, -1)) begin
            level = 0;
            running = 0;
        end
"""
FALL_RST = """        @(cross(V(rst_n) - vth, -1)) begin
            level = 0;
            running = 0;
        end
"""
RISE = """        @(cross(V(sig) - vth, +1)) begin
            if (V(rst_n) > vth) begin
                running = 1;
                t_done = $abstime + stable;
            end
        end
"""
TIMER = """        @(timer(t_done)) begin
            if (running && V(sig) > vth && V(rst_n) > vth)
                level = 1;
            running = 0;
        end
"""
OUTPUT = "V(out) <+ transition(level ? vdd : 0.0, 0.0, tr, tr);"
INIT = """        @(initial_step) begin
            level = 0;
            running = 0;
            t_done = -1.0;
        end
"""
DECL = "    real t_done;        // completion instant of the latest qualification\n"
START = "t_done = $abstime + stable;"

# A transport-delayed copy of the armed state: out = armed(t) and armed(t - stable)
# when every pending change of transition() is kept (LRM 4.5.8).
TRANSPORT = """        @(initial_step)
            armed = 0;
        @(cross(V(sig) - vth, -1))
            armed = 0;
        @(cross(V(rst_n) - vth, -1))
            armed = 0;
        @(cross(V(sig) - vth, +1))
            if (V(rst_n) > vth)
                armed = 1;
        seen = transition(armed, stable, 10p);
        V(out) <+ transition((armed && seen > 0.5) ? vdd : 0.0, 0.0, tr, tr);
"""
# The rising change of the armed state is scheduled stable later; a falling change is
# scheduled at once and deletes any pending rise that would follow it (LRM 4.5.8).
DELAYED = """        @(initial_step)
            armed = 0;
        @(cross(V(sig) - vth, -1))
            armed = 0;
        @(cross(V(rst_n) - vth, -1))
            armed = 0;
        @(cross(V(sig) - vth, +1))
            if (V(rst_n) > vth)
                armed = 1;
        V(out) <+ transition(armed ? vdd : 0.0, armed ? stable : 0.0, tr, tr);
"""
# Input levels kept as event-updated flags; a cancel moves the timer instant into the past.
FLAGS = """        @(initial_step) begin
            s_hi = V(sig) > vth;
            r_hi = V(rst_n) > vth;
            q = 0;
            t_end = -1.0;
        end
        @(cross(V(rst_n) - vth, +1))
            r_hi = 1;
        @(cross(V(rst_n) - vth, -1)) begin
            r_hi = 0;
            q = 0;
            t_end = -1.0;
        end
        @(cross(V(sig) - vth, -1)) begin
            s_hi = 0;
            q = 0;
            t_end = -1.0;
        end
        @(cross(V(sig) - vth, +1)) begin
            s_hi = 1;
            if (r_hi)
                t_end = $abstime + stable;
        end
        @(timer(t_end))
            if (s_hi && r_hi && t_end > 0.0)
                q = 1;
        V(out) <+ transition(q ? vdd : 0.0, 0.0, tr, tr);
"""


def body(gold):
    """The analog block contents of the reference, from initial_step to the output."""
    start, end = gold.index(INIT), gold.index(OUTPUT) + len(OUTPUT) + 1
    return gold[start:end]


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    assert all(gold.count(part) == 1 for part in (FALL_SIG, FALL_RST, RISE, TIMER, OUTPUT, INIT, DECL, START))
    analog = body(gold)

    def replace_body(new, decls):
        return gold.replace(analog, new).replace(DECL, DECL + decls)
    wrong = {
        # The repair task's starter fault: the output is set at the rising crossing.
        "immediate_set_on_rise": gold.replace("running = 1;\n", "running = 1;\n                level = 1;\n"),
        # A falling decision keeps the reservation and a new rise does not restart it.
        "stale_first_reservation": gold.replace(FALL_SIG, FALL_SIG.replace("            running = 0;\n", ""))
                                       .replace("if (V(rst_n) > vth) begin", "if (V(rst_n) > vth && !running) begin"),
        "reset_keeps_reservation": gold.replace(FALL_RST, FALL_RST.replace("            running = 0;\n", "")),
        # A falling decision keeps the reservation and completion rechecks only rst_n.
        "no_recheck_fall_keeps_reservation": gold.replace(FALL_SIG, FALL_SIG.replace("            running = 0;\n", ""))
                                                 .replace("running && V(sig) > vth && V(rst_n) > vth",
                                                          "running && V(rst_n) > vth"),
        "arms_while_reset": gold.replace("""            if (V(rst_n) > vth) begin
                running = 1;
                t_done = $abstime + stable;
            end
""", """            running = 1;
            t_done = $abstime + stable;
"""),
        # Reset release with sig high, and sig high at t = 0, also start a qualification.
        "level_sensitive_start": gold.replace(INIT, INIT.replace("            t_done = -1.0;\n",
                                                                 "            t_done = -1.0;\n"
                                                                 "            if (V(sig) > vth && V(rst_n) > vth) begin\n"
                                                                 "                running = 1;\n"
                                                                 "                t_done = stable;\n"
                                                                 "            end\n")
                                              + "        @(cross(V(rst_n) - vth, +1)) begin\n"
                                                "            if (V(sig) > vth) begin\n"
                                                "                running = 1;\n"
                                                "                t_done = $abstime + stable;\n"
                                                "            end\n"
                                                "        end\n"),
        # above() also fires at initialization when sig is already high (LRM 5.10.3.2).
        "power_up_above": gold.replace("@(cross(V(sig) - vth, +1))", "@(above(V(sig) - vth))"),
        "accumulated_high_time": replace_body("""        @(initial_step) begin
            level = 0;
            running = 0;
            t_done = -1.0;
            acc = 0.0;
            t_mark = 0.0;
        end
        @(cross(V(sig) - vth, -1)) begin
            if (running)
                acc = acc + ($abstime - t_mark);
            level = 0;
            running = 0;
        end
        @(cross(V(rst_n) - vth, -1)) begin
            acc = 0.0;
            level = 0;
            running = 0;
        end
        @(cross(V(sig) - vth, +1)) begin
            if (V(rst_n) > vth) begin
                running = 1;
                t_mark = $abstime;
                t_done = $abstime + stable - acc;
            end
        end
        @(timer(t_done)) begin
            if (running && V(sig) > vth && V(rst_n) > vth) begin
                level = 1;
                acc = 0.0;
            end
            running = 0;
        end
        V(out) <+ transition(level ? vdd : 0.0, 0.0, tr, tr);
""", "    real acc, t_mark;\n"),
        "transport_delay_and": replace_body(TRANSPORT, "    integer armed;\n    real seen;\n"),
        # A falling decision also has to persist for stable before the output clears.
        "symmetric_debounce": gold.replace(FALL_SIG, """        @(cross(V(sig) - vth, -1)) begin
            running = 0;
            if (level) begin
                releasing = 1;
                t_release = $abstime + stable;
            end
        end
        @(timer(t_release)) begin
            if (releasing && V(sig) < vth)
                level = 0;
            releasing = 0;
        end
""").replace(FALL_RST, FALL_RST.replace("            running = 0;\n", "            running = 0;\n            releasing = 0;\n"))
            .replace("            if (V(rst_n) > vth) begin\n                running = 1;",
                     "            releasing = 0;\n            if (V(rst_n) > vth) begin\n                running = 1;")
            .replace(INIT, INIT.replace("            t_done = -1.0;\n", "            t_done = -1.0;\n"
                                        "            releasing = 0;\n            t_release = -1.0;\n"))
            .replace(DECL, DECL + "    integer releasing;\n    real t_release;\n"),
        "fall_keeps_output": gold.replace(FALL_SIG, FALL_SIG.replace("            level = 0;\n", "")),
        # Reset only masks the output; the latched level returns at release.
        "output_gated_by_reset": gold.replace(FALL_RST, """        @(cross(V(rst_n) - vth, -1)) begin
            released = 0;
            running = 0;
        end
        @(cross(V(rst_n) - vth, +1))
            released = 1;
""").replace(INIT, INIT.replace("            t_done = -1.0;\n", "            t_done = -1.0;\n"
                                "            released = V(rst_n) > vth;\n"))
            .replace(OUTPUT, "V(out) <+ transition((level && released) ? vdd : 0.0, 0.0, tr, tr);")
            .replace(DECL, DECL + "    integer released;\n"),
        "rst_active_high": gold.replace("@(cross(V(rst_n) - vth, -1))", "@(cross(V(rst_n) - vth, +1))")
                               .replace("V(rst_n) > vth", "V(rst_n) < vth"),
        "hardcoded_stable_12n": gold.replace(START, "t_done = $abstime + 12n;"),
        "hardcoded_vth_045": gold.replace("- vth,", "- 0.45,").replace("> vth", "> 0.45"),
        "hardcoded_vdd_09": gold.replace(OUTPUT, "V(out) <+ transition(level ? 0.9 : 0.0, 0.0, tr, tr);"),
        "hardcoded_tr_500p": gold.replace(OUTPUT, "V(out) <+ transition(level ? vdd : 0.0, 0.0, 500p, 500p);"),
        # Arrives 1.3*tr after each change: after the scoring start 1.25*tr.
        "slow_output_1p3tr": gold.replace(OUTPUT, "V(out) <+ transition(level ? vdd : 0.0, 0.0, 1.3*tr, 1.3*tr);"),
        "late_by_0p3tr": gold.replace(START, "t_done = $abstime + stable + 0.3*tr;"),
        "late_by_tr": gold.replace(START, "t_done = $abstime + stable + tr;"),
        "early_by_tr": gold.replace(START, "t_done = $abstime + stable - tr;"),
    }
    correct = {
        "alt_transition_delay": replace_body(DELAYED, "    integer armed;\n"),
        "alt_event_flags": replace_body(FLAGS, "    integer s_hi, r_hi, q;\n    real t_end;\n"),
        "alt_fast_output": gold.replace(OUTPUT, "V(out) <+ transition(level ? vdd : 0.0, 0.0, 0.2*tr, 0.2*tr);"),
        # Starts 0.2*tr late and arrives exactly at tr.
        "alt_delayed_within_tr": gold.replace(OUTPUT, "V(out) <+ transition(level ? vdd : 0.0, 0.2*tr, 0.8*tr, 0.8*tr);"),
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
