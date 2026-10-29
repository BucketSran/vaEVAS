"""Write targeted wrong and alternative-correct VA candidates for later calibration."""
from pathlib import Path

RESET = """    @(cross(V(rst) - vth, +1)) begin
        loaded = 0;
        in_pulse = 0;
        rise_pending = 0;
        fall_pending = 0;
        out_high = 0;
    end
"""
LOAD_HEAD = "    @(cross(V(load) - vth, +1)) begin\n        if (V(rst) < vth) begin\n"
WEIGHTS = """            if (V(code_0) > vth) code = code + 1;
            if (V(code_1) > vth) code = code + 2;
            if (V(code_2) > vth) code = code + 4;
            if (V(code_3) > vth) code = code + 8;
            if (V(code_4) > vth) code = code + 16;
            if (V(code_5) > vth) code = code + 32;
"""
RISE_SCHEDULE = """            pulse_delay = delay_min + delay_lsb * code;
            t_rise = $abstime + pulse_delay;
            rise_pending = 1;
"""
FALL_SCHEDULE = """            t_fall = $abstime + pulse_delay;
            fall_pending = 1;
"""
RISE_TIMER = "    @(timer(t_rise)) begin\n        if (rise_pending) begin\n"
FALL_TIMER = "    @(timer(t_fall)) begin\n        if (fall_pending) begin\n"
FALL_TIMER_BLOCK = FALL_TIMER + """            out_high = 0;
            fall_pending = 0;
        end
    end

"""
TIMERS = RISE_TIMER + """            out_high = 1;
            rise_pending = 0;
        end
    end

""" + FALL_TIMER_BLOCK
OUTPUT = "V(out_clk) <+ transition(out_high ? vdd : vss, 0, tr, tr);"
STATE = "real t_rise, t_fall;\n"
ACCEPT = "        if (V(rst) < vth && loaded) begin\n"


def swap(source, old, new, count=1):
    assert source.count(old) == count, (old, source.count(old))
    return source.replace(old, new)


def load_block(source):
    start = source.index("    // This block precedes the in_clk blocks")
    end = source.index("    @(cross(V(in_clk) - vth, +1))")
    return source[start:end]


def transport(gold, fall_delay):
    """Delay with transition(): the second argument is a transport delay (LRM 4.5.8)."""
    src = swap(gold, STATE, "real td_now;    // transport delay of the next target change\n")
    src = swap(src, "integer out_high;\n", "integer target;  // level the transition filter moves toward\n")
    src = swap(src, "        t_rise = -1.0;\n        t_fall = -1.0;\n        out_high = 0;\n",
               "        td_now = 0.0;\n        target = 0;\n")
    src = swap(src, "        rise_pending = 0;\n        fall_pending = 0;\n        out_high = 0;\n    end\n",
               "        target = 0;\n        td_now = 0.0;\n    end\n")
    src = swap(src, "integer rise_pending;  // a rising output edge is scheduled at t_rise\n"
                    "integer fall_pending;  // a falling output edge is scheduled at t_fall\n", "")
    src = swap(src, "        rise_pending = 0;\n        fall_pending = 0;\n", "")
    src = swap(src, RISE_SCHEDULE, "            pulse_delay = delay_min + delay_lsb * code;\n"
                                   "            td_now = pulse_delay;\n            target = 1;\n")
    src = swap(src, FALL_SCHEDULE, f"            td_now = {fall_delay};\n            target = 0;\n")
    src = swap(src, TIMERS, "")
    return swap(src, OUTPUT, "V(out_clk) <+ transition(target ? vdd : vss, td_now, tr, tr);")


def single_slot(gold):
    """One pending slot: the falling edge overwrites a rising edge that has not happened yet."""
    src = swap(gold, "integer out_high;\n", "integer out_high;\ninteger next_high;    // level of the one scheduled edge\n")
    src = swap(src, RISE_SCHEDULE, RISE_SCHEDULE + "            next_high = 1;\n")
    src = swap(src, FALL_SCHEDULE, "            t_rise = $abstime + pulse_delay;\n            rise_pending = 1;\n"
                                   "            next_high = 0;\n")
    src = swap(src, RISE_TIMER + "            out_high = 1;\n", RISE_TIMER + "            out_high = next_high;\n")
    return swap(src, FALL_TIMER_BLOCK, "")


def fifo(gold):
    """One timer on the head of a queue of scheduled edges instead of one slot per direction."""
    src = swap(gold, "integer rise_pending;  // a rising output edge is scheduled at t_rise\n"
                     "integer fall_pending;  // a falling output edge is scheduled at t_fall\n"
                     "real t_rise, t_fall;\n",
               "integer count;        // scheduled output edges, oldest first\n"
               "integer head;\nreal edge_time[0:3];\ninteger edge_level[0:3];\nreal t_next;\n")
    src = swap(src, "        rise_pending = 0;\n        fall_pending = 0;\n        t_rise = -1.0;\n        t_fall = -1.0;\n",
               "        count = 0;\n        head = 0;\n        t_next = -1.0;\n")
    src = swap(src, "        rise_pending = 0;\n        fall_pending = 0;\n", "        count = 0;\n")
    push = ("            edge_time[(head + count) % 4] = $abstime + pulse_delay;\n"
            "            edge_level[(head + count) % 4] = {level};\n"
            "            count = count + 1;\n            t_next = edge_time[head];\n")
    src = swap(src, RISE_SCHEDULE, "            pulse_delay = delay_min + delay_lsb * code;\n" + push.format(level=1))
    src = swap(src, FALL_SCHEDULE, push.format(level=0))
    return swap(src, TIMERS, """    @(timer(t_next)) begin
        if (count > 0) begin
            out_high = edge_level[head];
            head = (head + 1) % 4;
            count = count - 1;
            if (count > 0) t_next = edge_time[head];
        end
    end

""")


def level_state(gold):
    """One cross() for both directions; the input level is tracked from its crossings."""
    src = swap(gold, "integer out_high;\n", "integer out_high;\ninteger in_high;     // in_clk level after its last crossing\n")
    src = swap(src, "        out_high = 0;\n    end\n\n    // Reset",
               "        out_high = 0;\n        in_high = V(in_clk) > vth;\n    end\n\n    // Reset")
    rise = src[src.index("    @(cross(V(in_clk) - vth, +1)) begin\n"):src.index("    @(cross(V(in_clk) - vth, -1)) begin\n")]
    fall = src[src.index("    @(cross(V(in_clk) - vth, -1)) begin\n"):src.index(RISE_TIMER)]
    rise_body = rise.split("begin\n", 1)[1].rsplit("    end\n", 1)[0]
    fall_body = fall.split("begin\n", 1)[1].rsplit("    end\n", 1)[0]
    merged = ("    @(cross(V(in_clk) - vth, 0)) begin\n        in_high = !in_high;\n        if (in_high) begin\n"
              + "".join("    " + line + "\n" for line in rise_body.rstrip("\n").split("\n"))
              + "        end else begin\n"
              + "".join("    " + line + "\n" for line in fall_body.rstrip("\n").split("\n"))
              + "        end\n    end\n\n")
    return swap(src, rise + fall, merged)


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    for part in (RESET, LOAD_HEAD, WEIGHTS, RISE_SCHEDULE, FALL_SCHEDULE, TIMERS, OUTPUT, STATE, ACCEPT):
        assert gold.count(part) == 1, part
    block = load_block(gold)
    reversed_weights = WEIGHTS
    for bit in range(6):
        reversed_weights = reversed_weights.replace(f"V(code_{bit}) > vth) code = code + {1 << bit};",
                                                    f"V(code_{bit}) > vth) code = code + @{1 << (5 - bit)};")
    reversed_weights = reversed_weights.replace("@", "")
    bits = " + ".join(f"{1 << (5 - i)} * (V(code_{5 - i}) > vth)" for i in range(6))
    wrong = {
        # The falling edge takes the delay of the code loaded when it arrives (the historical rule).
        "per_edge_latch": swap(gold, FALL_SCHEDULE, FALL_SCHEDULE.replace("pulse_delay;", "delay_min + delay_lsb * code;")),
        "single_slot": single_slot(gold),
        "rise_clears_pending_fall": swap(gold, RISE_SCHEDULE, RISE_SCHEDULE + "            fall_pending = 0;\n"),
        # The falling edge is timed from the delay variable, which the next accepted pulse overwrites.
        "fall_time_from_current_delay": swap(swap(gold, "            t_fall = $abstime + pulse_delay;\n",
                                                  "            t_fall = $abstime;\n"),
                                             "@(timer(t_fall))", "@(timer(t_fall + pulse_delay))"),
        # Pending edges are timed from the input crossing with the code loaded now.
        "retime_on_load": swap(swap(swap(swap(gold, "            t_rise = $abstime + pulse_delay;\n", "            t_rise = $abstime;\n"),
                                         "            t_fall = $abstime + pulse_delay;\n", "            t_fall = $abstime;\n"),
                                    "@(timer(t_rise))", "@(timer(t_rise + delay_min + delay_lsb * code))"),
                               "@(timer(t_fall))", "@(timer(t_fall + delay_min + delay_lsb * code))"),
        # Reset only masks edges that come due while rst is high; pending edges survive the release.
        "reset_gate_only": swap(swap(swap(gold, RESET, RESET.replace("        in_pulse = 0;\n        rise_pending = 0;\n"
                                                                     "        fall_pending = 0;\n", "")),
                                     "if (rise_pending)", "if (rise_pending && V(rst) < vth)"),
                                "if (fall_pending)", "if (fall_pending && V(rst) < vth)"),
        "reset_no_force_low": swap(gold, RESET, RESET.replace("        out_high = 0;\n", "")),
        "reset_keeps_code": swap(gold, RESET, RESET.replace("        loaded = 0;\n", "")),
        "unloaded_code0": swap(swap(gold, ACCEPT, "        if (V(rst) < vth) begin\n"),
                               RESET, RESET.replace("        loaded = 0;\n", "        loaded = 0;\n        code = 0;\n")),
        "load_during_reset": swap(gold, LOAD_HEAD, LOAD_HEAD.replace("if (V(rst) < vth) begin", "if (1) begin")),
        # The in_clk blocks run first, so a load at the same instant applies only from the next pulse.
        "edge_first": swap(swap(gold, block, ""), RISE_TIMER, block.split("\n", 2)[2] + RISE_TIMER),
        "load_on_falling_edge": swap(gold, LOAD_HEAD, LOAD_HEAD.replace("vth, +1", "vth, -1")),
        "code_at_input_edge": swap(gold, "pulse_delay = delay_min + delay_lsb * code;",
                                   f"pulse_delay = delay_min + delay_lsb * ({bits});"),
        "bit_order_reversed": swap(gold, WEIGHTS, reversed_weights),
        "no_delay_min": swap(gold, "pulse_delay = delay_min + delay_lsb * code;", "pulse_delay = delay_lsb * code;"),
        "fixed_vth": gold.replace(" - vth", " - 0.45").replace("> vth", "> 0.45").replace("< vth", "< 0.45"),
        "fixed_levels": swap(gold, OUTPUT, "V(out_clk) <+ transition(out_high ? 0.9 : 0.0, 0, tr, tr);"),
        "fixed_delay_params": swap(gold, "pulse_delay = delay_min + delay_lsb * code;", "pulse_delay = 20p + 3p * code;"),
        "slow_output": swap(gold, OUTPUT, "V(out_clk) <+ transition(out_high ? vdd : vss, 0, 2*tr, 2*tr);"),
        "fixed_tr": swap(gold, OUTPUT, "V(out_clk) <+ transition(out_high ? vdd : vss, 0, 10p, 10p);"),
        # Centres the ramp on the edge time (50 % delay reading) instead of starting it there.
        "centered_transition": swap(swap(gold, "@(timer(t_rise))", "@(timer(t_rise - tr/2))"),
                                    "@(timer(t_fall))", "@(timer(t_fall - tr/2))"),
        # Transport delay through transition(); a reset that leaves the target low cancels nothing.
        "transport_reset_unchanged": transport(gold, "pulse_delay"),
        # The historical structure: transport transition and a per-edge delay.
        "historical_per_edge_transport": transport(gold, "delay_min + delay_lsb * code"),
    }
    correct = {
        "alt_fifo_queue": fifo(gold),
        "alt_fast_output": swap(gold, OUTPUT, "V(out_clk) <+ transition(out_high ? vdd : vss, 0, 0.2*tr, 0.2*tr);"),
        "alt_level_state": level_state(gold),
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
