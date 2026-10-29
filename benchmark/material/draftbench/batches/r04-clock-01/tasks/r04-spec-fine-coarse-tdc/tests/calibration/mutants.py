"""Write targeted wrong and alternative-correct VA candidates for later calibration."""
from pathlib import Path

FINE_START = "q_start = floor(16.0*($abstime - t_last)/(t_last - t_prev));"
RESULT = "code = 16*count + floor(16.0*($abstime - t_last)/(t_last - t_prev)) - q_start;"
OVERFLOW = """                    if (count == 16) begin
                        armed = 0;
                        code = 255;
                        valid_q = 1;
                        overflow_q = 1;
                    end
"""
START_IF = "if (V(rst) < vth && seen >= 2) begin"
START_CLEAR = """                armed = 1;
                count = 0;
                code = 0;
                valid_q = 0;
                overflow_q = 0;
"""
STOP_DISARM = """                armed = 0;
                valid_q = 1;
                overflow_q = 0;
"""
RST_RISE = """        @(cross(V(rst) - vth, +1, 1p)) begin
            armed = 0;
            code = 0;
            valid_q = 0;
            overflow_q = 0;
            seen = 0;
        end
        @(cross(V(rst) - vth, -1, 1p))
            seen = 0;
"""
REF_GATE = "            if (V(rst) < vth) begin\n                t_prev = t_last;"
DECL = "    real t_prev;        // the one before it; t_last - t_prev is the reference period\n"
BITS = [f"V(code_{k}) <+ transition(((code >> {k}) & 1) ? vdd : 0.0, 0.0, tr, tr);" for k in range(7, 0, -1)] \
    + ["V(code_0) <+ transition((code & 1) ? vdd : 0.0, 0.0, tr, tr);"]
OUTPUTS = BITS + ["V(valid) <+ transition(valid_q ? vdd : 0.0, 0.0, tr, tr);",
                  "V(overflow) <+ transition(overflow_q ? vdd : 0.0, 0.0, tr, tr);"]
PERIOD = "(t_last - t_prev)"


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    for part in (FINE_START, RESULT, OVERFLOW, START_IF, START_CLEAR, STOP_DISARM, RST_RISE, REF_GATE, DECL, *OUTPUTS):
        assert gold.count(part) == 1, part
    assert gold.count(PERIOD) == 2

    def outputs(transform):
        source = gold
        for line in OUTPUTS:
            source = source.replace(line, transform(line))
        return source

    q_e = "floor(16.0*($abstime - t_last)/(t_last - t_prev))"
    reversed_bits = gold
    for k in range(8):
        old = BITS[7 - k]
        new = old.replace(f"V(code_{k})", f"V(code_{7 - k})")
        reversed_bits = reversed_bits.replace(old, "@@" + new)
    reversed_bits = reversed_bits.replace("@@", "")
    wrong = {
        # The v4 proxy: only the stop phase enters the result.
        "stop_phase_only": gold.replace(RESULT, f"code = 16*count + {q_e};"),
        "concatenated_no_borrow": gold.replace(RESULT, f"code = 16*count + (({q_e} - q_start + 16) % 16);"),
        "clamped_fine_difference": gold.replace(RESULT, f"code = 16*count + max({q_e} - q_start, 0);"),
        # Coarse part from the elapsed time instead of counted crossings.
        "time_based_coarse_count": gold.replace(DECL, DECL + "    real t_start;\n")
                                       .replace(FINE_START, FINE_START + "\n                t_start = $abstime;")
                                       .replace(RESULT, f"code = 16*floor(($abstime - t_start)/(t_last - t_prev)) + {q_e} - q_start;"),
        "rounded_fine_codes": gold.replace("floor(16.0*", "floor(0.5 + 16.0*"),
        # Time to the next crossing, combined with the sign of the time since the last crossing.
        "next_edge_sign_error": gold.replace("floor(16.0*($abstime - t_last)/(t_last - t_prev))",
                                             "floor(16.0*(t_last + (t_last - t_prev) - $abstime)/(t_last - t_prev))"),
        "extra_coarse_edge": gold.replace(RESULT, f"code = 16*(count + 1) + {q_e} - q_start;"),
        "fixed_period_4ns": gold.replace(PERIOD, "4n"),
        "no_warm_up": gold.replace(START_IF, "if (V(rst) < vth && seen >= 1) begin"),
        "warm_up_survives_reset": gold.replace(RST_RISE, RST_RISE.replace("            seen = 0;\n        end", "        end")
                                               .replace("        @(cross(V(rst) - vth, -1, 1p))\n            seen = 0;\n", ""))
                                      .replace(REF_GATE, "            if (1) begin\n                t_prev = t_last;"),
        # No overflow event; a stop after 16 crossings publishes the saturated code.
        "overflow_only_at_stop": gold.replace(OVERFLOW, "").replace(
            RESULT, "if (count >= 16)\n                    code = 255;\n                else\n                    " + RESULT)
            .replace(STOP_DISARM, STOP_DISARM.replace("overflow_q = 0;", "overflow_q = (count >= 16);")),
        "overflow_code_zero": gold.replace(OVERFLOW, OVERFLOW.replace("code = 255;", "code = 0;")),
        "overflow_flag_missing": gold.replace(OVERFLOW, OVERFLOW.replace("overflow_q = 1;", "overflow_q = 0;")),
        "restart_ignored": gold.replace(START_IF, "if (V(rst) < vth && seen >= 2 && !armed) begin"),
        "stop_keeps_measurement": gold.replace(STOP_DISARM, STOP_DISARM.replace("                armed = 0;\n", "")),
        "start_keeps_result": gold.replace(START_CLEAR, "                armed = 1;\n                count = 0;\n"),
        "reset_keeps_measurement": gold.replace(RST_RISE, RST_RISE.replace("            armed = 0;\n", "")),
        "ref_falling_edges": gold.replace("@(cross(V(ref_clk) - vth, +1, 1p))", "@(cross(V(ref_clk) - vth, -1, 1p))"),
        "bit_order_reversed": reversed_bits,
        "hardcoded_vth_045": gold.replace("- vth,", "- 0.45,").replace("< vth", "< 0.45"),
        "hardcoded_vdd_09": outputs(lambda line: line.replace("? vdd :", "? 0.9 :")),
        "hardcoded_tr_200p": outputs(lambda line: line.replace("tr, tr);", "200p, 200p);")),
        # Arrives 1.3*tr after each change: after the scoring start 1.25*tr.
        "slow_output_1p3tr": outputs(lambda line: line.replace("tr, tr);", "1.3*tr, 1.3*tr);")),
    }
    correct = {
        # Nutt form: D = 16*N + t1 - t2 with fine times t1, t2 to the next crossing.
        "alt_nutt_complement": gold.replace(FINE_START, "q_start = floor(16.0*(t_last + (t_last - t_prev) - $abstime)"
                                                        "/(t_last - t_prev));")
                                   .replace(RESULT, "code = 16*count + q_start - floor(16.0*(t_last + (t_last - t_prev)"
                                                    " - $abstime)/(t_last - t_prev));"),
        # Coarse count from timestamps of the bracketing crossings; overflow on a timer.
        "alt_timestamp_overflow_timer": gold.replace(DECL, DECL + "    real r_start;\n    real t_overflow;\n")
            .replace(OVERFLOW, "")
            .replace(FINE_START, FINE_START + "\n                r_start = t_last;\n"
                                              "                t_overflow = t_last + 16*(t_last - t_prev);")
            .replace(RESULT, "code = 16*floor(0.5 + (t_last - r_start)/(t_last - t_prev)) + "
                             "floor(16.0*($abstime - t_last)/(t_last - t_prev)) - q_start;")
            .replace("        V(code_7) <+", "        @(timer(t_overflow)) begin\n"
                                             "            if (armed) begin\n                armed = 0;\n                code = 255;\n"
                                             "                valid_q = 1;\n                overflow_q = 1;\n            end\n"
                                             "        end\n\n        V(code_7) <+"),
        "alt_fast_output": outputs(lambda line: line.replace("tr, tr);", "0.2*tr, 0.2*tr);")),
        # Starts 0.2*tr late and arrives exactly at tr.
        "alt_delayed_within_tr": outputs(lambda line: line.replace("0.0, tr, tr);", "0.2*tr, 0.8*tr, 0.8*tr);")),
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
