"""Write targeted wrong and alternative-correct VA candidates for later calibration."""
from pathlib import Path

INIT = "@(initial_step)\n            env = 0.0;"
CLEAR = """        // A rising rst crossing clears the envelope at once.
        @(cross(V(rst) - vth, +1))
            env = 0.0;
"""
CROSS = "@(cross(V(clk) - vth, +1)) begin"
RESET_CHECK = "            if (V(rst) > vth)\n                env = 0.0;\n            else begin"
MODE_RULE = """                if (V(mode) > vth)
                    env = V(vin);
                else if (V(vin) > env)
                    env = V(vin);
"""
LOW_CLAMP = "                if (env < 0.0)\n                    env = 0.0;\n"
HIGH_CLAMP = "                if (env > 0.8)\n                    env = 0.8;\n"
OUT = "V(out) <+ slew(env, rise_rate, -fall_rate);"
METRIC = "V(metric) <+ slew(env / 0.8, rise_rate, -fall_rate);"
DECL = "    real env;  // envelope: changes only at reset and sample events\n"

# Explicit ramps from the last event, no slew(): origin, start time and target per output.
RAMP_DECL = DECL + """    real out_org, out_t0, out_tgt, met_org, met_t0, met_tgt;
    real out_now, met_now;
"""
RAMP_INIT = """@(initial_step) begin
            env = 0.0;
            out_org = 0.0;
            out_t0 = 0.0;
            out_tgt = 0.0;
            met_org = 0.0;
            met_t0 = 0.0;
            met_tgt = 0.0;
        end

        // Each trajectory now: a ramp from its origin toward its target, stopping on it.
        if (out_tgt >= out_org)
            out_now = min(out_tgt, out_org + rise_rate * ($abstime - out_t0));
        else
            out_now = max(out_tgt, out_org - fall_rate * ($abstime - out_t0));
        if (met_tgt >= met_org)
            met_now = min(met_tgt, met_org + rise_rate * ($abstime - met_t0));
        else
            met_now = max(met_tgt, met_org - fall_rate * ($abstime - met_t0));"""
RESTART = """
            out_org = out_now;
            out_t0 = $abstime;
            out_tgt = env;
            met_org = met_now;
            met_t0 = $abstime;
            met_tgt = env / 0.8;"""
RAMP_CLEAR = """        // A rising rst crossing clears the envelope at once.
        @(cross(V(rst) - vth, +1)) begin
            env = 0.0;""" + RESTART + """
        end
"""


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    parts = (INIT, CLEAR, CROSS, RESET_CHECK, MODE_RULE, LOW_CLAMP, HIGH_CLAMP, OUT, METRIC, DECL)
    assert all(gold.count(part) == 1 for part in parts)
    end_sample = HIGH_CLAMP + "            end\n        end\n"
    assert gold.count(end_sample) == 1
    ramp = (gold.replace(DECL, RAMP_DECL).replace(INIT, RAMP_INIT).replace(CLEAR, RAMP_CLEAR)
                .replace(end_sample, HIGH_CLAMP + "            end" + RESTART.replace("\n            ", "\n            ") + "\n        end\n")
                .replace(OUT, "V(out) <+ out_now;").replace(METRIC, "V(metric) <+ met_now;")
                .replace("        // Each output follows its own target with the limited rising and falling\n"
                         "        // slopes. slew() takes the falling limit as a negative rate.\n",
                         "        // Each output follows its own trajectory.\n"))
    step = (gold.replace(DECL, DECL + "    real out_s, met_s, t_last, dt;\n")
                .replace(INIT, "@(initial_step) begin\n            env = 0.0;\n            out_s = 0.0;\n"
                               "            met_s = 0.0;\n            t_last = 0.0;\n        end")
                .replace(end_sample, HIGH_CLAMP + "            end\n"
                         "            // Output moves only here, by at most one slope times the time since the last sample.\n"
                         "            dt = $abstime - t_last;\n"
                         "            out_s = out_s + max(-fall_rate * dt, min(rise_rate * dt, env - out_s));\n"
                         "            met_s = met_s + max(-fall_rate * dt, min(rise_rate * dt, env / 0.8 - met_s));\n"
                         "            t_last = $abstime;\n        end\n")
                .replace(OUT, "V(out) <+ transition(out_s, 0.0, 10p, 10p);")
                .replace(METRIC, "V(metric) <+ transition(met_s, 0.0, 10p, 10p);"))
    wrong = {
        "no_slew": gold.replace(OUT, "V(out) <+ transition(env, 0.0, 10p, 10p);")
                       .replace(METRIC, "V(metric) <+ transition(env / 0.8, 0.0, 10p, 10p);"),
        "rates_swapped": gold.replace(OUT, "V(out) <+ slew(env, fall_rate, -rise_rate);")
                             .replace(METRIC, "V(metric) <+ slew(env / 0.8, fall_rate, -rise_rate);"),
        "symmetric_rate": gold.replace(OUT, "V(out) <+ slew(env, rise_rate, -rise_rate);")
                              .replace(METRIC, "V(metric) <+ slew(env / 0.8, rise_rate, -rise_rate);"),
        # transition() with the full-scale ramp time: right slope only for full-scale steps.
        "fixed_duration_transition": gold.replace(OUT, "V(out) <+ transition(env, 0.0, 0.8 / rise_rate, 0.8 / fall_rate);")
                                         .replace(METRIC, "V(metric) <+ transition(env / 0.8, 0.0, 1.0 / rise_rate, 1.0 / fall_rate);"),
        "step_per_sample": step,
        "metric_from_out": gold.replace(METRIC, "V(metric) <+ slew(env, rise_rate, -fall_rate) / 0.8;"),
        "metric_same_target": gold.replace(METRIC, "V(metric) <+ slew(env, rise_rate, -fall_rate);"),
        "fixed_rates": gold.replace(OUT, "V(out) <+ slew(env, 8.0e8, -3.0e8);")
                           .replace(METRIC, "V(metric) <+ slew(env / 0.8, 8.0e8, -3.0e8);"),
        "no_upper_clamp": gold.replace(HIGH_CLAMP, ""),
        "no_lower_clamp": gold.replace(LOW_CLAMP, ""),
        "mode_inverted": gold.replace("if (V(mode) > vth)", "if (V(mode) < vth)"),
        "always_release": gold.replace(MODE_RULE, "                env = V(vin);\n"),
        "always_hold": gold.replace(MODE_RULE, "                if (V(vin) > env)\n                    env = V(vin);\n"),
        # Peak hold against the actual output instead of the held envelope.
        "peak_on_output": gold.replace(MODE_RULE, "                if (V(mode) > vth)\n                    env = V(vin);\n"
                                                  "                else if (V(vin) > V(out))\n                    env = V(vin);\n"
                                                  "                else\n                    env = V(out);\n"),
        "sync_reset_only": gold.replace(CLEAR + "\n", ""),
        "reset_ignored_while_high": gold.replace(RESET_CHECK, "            begin"),
        # Hand-written ramps whose clear also restarts the trajectories at 0 V.
        "reset_jumps_outputs": ramp.replace("            env = 0.0;" + RESTART,
                                            "            env = 0.0;" + RESTART.replace("out_org = out_now;", "out_org = 0.0;")
                                                                          .replace("met_org = met_now;", "met_org = 0.0;"), 1),
        "falling_clk_sample": gold.replace(CROSS, "@(cross(V(clk) - vth, -1)) begin"),
        "init_env_from_vin": gold.replace(INIT, "@(initial_step) begin\n            env = V(vin);\n"
                                                "            if (env < 0.0)\n                env = 0.0;\n"
                                                "            if (env > 0.8)\n                env = 0.8;\n        end"),
        # Ignores the vth parameter: clk, rst and mode all switch at 0.45 V (p0-fix-a).
        "fixed_vth": gold.replace("V(rst) - vth", "V(rst) - 0.45").replace("V(clk) - vth", "V(clk) - 0.45")
                         .replace("V(rst) > vth", "V(rst) > 0.45").replace("V(mode) > vth", "V(mode) > 0.45"),
    }
    correct = {
        "alt_explicit_ramp": ramp,
        "alt_clamp_then_compare": gold.replace(MODE_RULE + LOW_CLAMP + HIGH_CLAMP,
                                               "                vin_c = V(vin);\n"
                                               "                if (vin_c < 0.0)\n                    vin_c = 0.0;\n"
                                               "                if (vin_c > 0.8)\n                    vin_c = 0.8;\n"
                                               "                if (V(mode) > vth || vin_c > env)\n                    env = vin_c;\n")
                                      .replace(DECL, DECL + "    real vin_c;\n"),
        "alt_above_reset": gold.replace("@(cross(V(rst) - vth, +1))\n            env = 0.0;",
                                        "@(above(V(rst) - vth))\n            env = 0.0;"),
    }
    assert "out_org = 0.0;\n            out_t0 = $abstime;" in wrong["reset_jumps_outputs"]
    assert "vth" not in wrong["fixed_vth"].split("analog begin")[1]
    for name, source in {**wrong, **correct}.items():
        assert source != gold and (name == "alt_explicit_ramp" or source != ramp), name
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
