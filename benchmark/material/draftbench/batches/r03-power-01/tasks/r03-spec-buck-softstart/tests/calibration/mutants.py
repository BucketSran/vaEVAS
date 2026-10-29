"""Write targeted wrong and alternative-correct VA candidates for later calibration."""
from pathlib import Path

DUTY_UP = "                duty_up = (fb_now < soft);\n"
SOFT = """                if (abs(ref_now - soft) <= soft_step)
                    soft = ref_now;
                else if (ref_now > soft)
                    soft = soft + soft_step;
                else
                    soft = soft - soft_step;
"""
DUTY = """                duty = duty_up ? duty + 0.05 : duty - 0.05;
                if (duty < duty_min)
                    duty = duty_min;
                if (duty > duty_max)
                    duty = duty_max;
"""
CARRIER = "                carrier = (carrier + 1) % 20;\n"
PWM = "                pwm_level = (carrier + 0.5 < 20.0 * duty) ? vdd : vss;\n"
GOOD = """                if (abs(fb_now - ref_now) <= pgood_tol) begin
                    if (good_count < 3)
                        good_count = good_count + 1;
                end else
                    good_count = 0;
                pgood_level = (good_count >= 3) ? vdd : vss;
"""
CLEAR = """                soft = vss;
                duty = 0.0;
                carrier = 0;
                good_count = 0;
                pwm_level = vss;
                pgood_level = vss;
"""
INIT_HEAD = "        @(initial_step) begin\n            soft = vss;\n            duty = 0.0;\n"
CROSS = "@(cross(V(clk) - vth, +1)) begin"
CONDITION = "if (V(rst) > vth || V(enable) <= vth) begin"
STATE = "    integer duty_up;\n"
OUTPUTS = """        V(soft_ref) <+ transition(soft, 0.0, tr, tr);
        V(duty_metric) <+ transition(duty, 0.0, tr, tr);
        V(pwm) <+ transition(pwm_level, 0.0, tr, tr);
        V(pgood) <+ transition(pgood_level, 0.0, tr, tr);
"""
ASYNC = """        // Clears at once on a rising rst or falling enable crossing, not only at sample events.
        @(cross(V(rst) - vth, +1)) begin
""" + CLEAR.replace("                ", "            ") + """        end
        @(cross(V(enable) - vth, -1)) begin
""" + CLEAR.replace("                ", "            ") + """        end

"""


def candidates():
    gold = (Path(__file__).resolve().parents[2] / "solution/circuit.va").read_text()
    for part in (DUTY_UP, SOFT, DUTY, CARRIER, PWM, GOOD, CLEAR, INIT_HEAD, CROSS, CONDITION, STATE, OUTPUTS):
        assert gold.count(part) == 1, part
    shown = OUTPUTS.replace("transition(soft,", "transition(soft_shown,").replace("transition(duty,", "transition(duty_shown,") \
                   .replace("transition(pwm_level,", "transition(pwm_shown,").replace("transition(pgood_level,", "transition(pgood_shown,")
    wrong = {
        # Order and comparison of the soft reference
        "duty_up_new_soft": gold.replace(DUTY_UP + "\n" + SOFT, SOFT + DUTY_UP),
        "duty_up_vs_vref": gold.replace(DUTY_UP, "                duty_up = (fb_now < ref_now);\n"),
        "soft_overshoot": gold.replace(SOFT, "                if (ref_now > soft)\n                    soft = soft + soft_step;\n"
                                             "                else if (ref_now < soft)\n                    soft = soft - soft_step;\n"),
        "soft_jumps_down": gold.replace("                else\n                    soft = soft - soft_step;\n",
                                        "                else\n                    soft = ref_now;\n"),
        # Duty integrator
        "duty_step_25m": gold.replace("duty_up ? duty + 0.05 : duty - 0.05", "duty_up ? duty + 0.025 : duty - 0.025"),
        "clamp_before_update": gold.replace(DUTY, DUTY.split("\n", 1)[1] + DUTY.split("\n", 1)[0] + "\n"),
        "duty_clear_to_min": gold.replace(INIT_HEAD, INIT_HEAD.replace("duty = 0.0;", "duty = duty_min;"))
                                 .replace(CLEAR, CLEAR.replace("duty = 0.0;", "duty = duty_min;")),
        "duty_metric_cleared_to_vss": gold.replace("transition(duty, 0.0, tr, tr)", "transition(duty == 0.0 ? vss : duty, 0.0, tr, tr)"),
        # PWM comparison
        "pwm_old_carrier": gold.replace(CARRIER + PWM, PWM + CARRIER),
        "pwm_old_duty": gold.replace(STATE, STATE + "    real duty_prev;\n").replace(DUTY, "                duty_prev = duty;\n" + DUTY)
                            .replace(PWM, PWM.replace("20.0 * duty)", "20.0 * duty_prev)")),
        "pwm_less_or_equal": gold.replace(PWM, "                pwm_level = (carrier <= floor(20.0 * duty + 0.5)) ? vdd : vss;\n"),
        "pwm_duty_latched_per_cycle": gold.replace(STATE, STATE + "    real duty_latch;  // duty compared during one carrier cycle\n")
                                          .replace(INIT_HEAD, INIT_HEAD + "            duty_latch = 0.0;\n")
                                          .replace(CLEAR, CLEAR + "                duty_latch = 0.0;\n")
                                          .replace(CARRIER + PWM, CARRIER + "                if (carrier == 0)\n"
                                                   "                    duty_latch = duty;\n"
                                                   + PWM.replace("20.0 * duty)", "20.0 * duty_latch)")),
        # Clear
        "carrier_kept_across_clear": gold.replace(CLEAR, CLEAR.replace("                carrier = 0;\n", "")),
        "pgood_count_kept_across_clear": gold.replace(CLEAR, CLEAR.replace("                good_count = 0;\n", "")),
        "enable_ignored": gold.replace(CONDITION, "if (V(rst) > vth) begin"),
        "asynchronous_clear": gold.replace(OUTPUTS, ASYNC + OUTPUTS),
        # Power good
        "pgood_sticky": gold.replace("                end else\n                    good_count = 0;\n", "                end\n"),
        "pgood_after_2": gold.replace("(good_count >= 3) ? vdd : vss", "(good_count >= 2) ? vdd : vss"),
        "pgood_after_4": gold.replace(GOOD, GOOD.replace("good_count < 3", "good_count < 4").replace("good_count >= 3", "good_count >= 4")),
        "pgood_from_soft_done": gold.replace("abs(fb_now - ref_now) <= pgood_tol", "abs(soft - ref_now) <= pgood_tol"),
        "pgood_vfb_vs_soft": gold.replace("abs(fb_now - ref_now) <= pgood_tol", "abs(fb_now - soft) <= pgood_tol"),
        # Event and output timing
        "falling_edge_sample": gold.replace(CROSS, "@(cross(V(clk) - vth, -1)) begin"),
        "one_edge_latency": gold.replace(STATE, STATE + "    real soft_shown, duty_shown, pwm_shown, pgood_shown;  // states of the previous edge\n")
                                .replace(INIT_HEAD, INIT_HEAD + "            soft_shown = vss;\n            duty_shown = 0.0;\n"
                                                    "            pwm_shown = vss;\n            pgood_shown = vss;\n")
                                .replace(CROSS, CROSS + "\n            soft_shown = soft;\n            duty_shown = duty;\n"
                                                "            pwm_shown = pwm_level;\n            pgood_shown = pgood_level;")
                                .replace(OUTPUTS, shown),
        # fix-r1: arrival after the scoring start (F02), fixed threshold and transition (F08), duty end points (F07)
        "late_arrival_1p3tr": gold.replace(OUTPUTS, OUTPUTS.replace("0.0, tr, tr)", "0.0, 1.3*tr, 1.3*tr)")),
        "fixed_vth": gold.replace(CROSS, "@(cross(V(clk) - 0.45, +1)) begin")
                         .replace(CONDITION, "if (V(rst) > 0.45 || V(enable) <= 0.45) begin"),
        "fixed_tr": gold.replace(OUTPUTS, OUTPUTS.replace("0.0, tr, tr)", "0.0, 200p, 200p)")),
        "endpoint_limits": gold.replace(DUTY, DUTY + "                // never 0 % or 100 %, whatever duty_min and duty_max say\n"
                                                     "                if (duty < 0.05)\n                    duty = 0.05;\n"
                                                     "                if (duty > 0.95)\n                    duty = 0.95;\n"),
        "min_on_time_at_wrap": gold.replace(PWM, "                pwm_level = (carrier + 0.5 < 20.0 * duty || carrier == 0) ? vdd : vss;\n"),
        "forced_off_state": gold.replace(PWM, "                pwm_level = (carrier + 0.5 < 20.0 * duty && carrier != 19) ? vdd : vss;\n"),
    }
    integer = gold.replace("    real duty;       // dimensionless duty, cleared to 0 (not to vss)\n",
                           "    integer duty_n;  // duty in 0.05 steps, cleared to 0 (not to vss)\n    integer n_min, n_max;\n") \
                  .replace(INIT_HEAD, INIT_HEAD.replace("            duty = 0.0;\n", "            duty_n = 0;\n"
                                      "            n_min = floor(duty_min/0.05 + 0.5);\n            n_max = floor(duty_max/0.05 + 0.5);\n")) \
                  .replace(CLEAR, CLEAR.replace("duty = 0.0;", "duty_n = 0;")) \
                  .replace(DUTY, "                duty_n = duty_up ? duty_n + 1 : duty_n - 1;\n                if (duty_n < n_min)\n"
                                 "                    duty_n = n_min;\n                if (duty_n > n_max)\n                    duty_n = n_max;\n") \
                  .replace(PWM, "                pwm_level = (carrier < duty_n) ? vdd : vss;\n") \
                  .replace("transition(duty, 0.0, tr, tr)", "transition(0.05*duty_n, 0.0, tr, tr)")
    correct = {
        "alt_integer_duty": integer,
        "alt_fast_output": gold.replace(OUTPUTS, OUTPUTS.replace("0.0, tr, tr)", "0.0, 0.2*tr, 0.2*tr)")),
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
