#!/usr/bin/env python3
"""Write the calibration candidates of r01-spec-droop-front-end into an empty directory.

    python3 -B mutants.py <output-directory>

wrong/<name>.va must be rejected and correct/<name>.va must be accepted by the
checker in ../verify.py on ../cases.json, as listed in expected.json. Each candidate
is ../../solution/circuit.va with checked text changes, except two that are read
byte for byte from benchmark/material/historyref when this file runs inside the
repository and only get this task's module name (the historical name is
sample_hold_droop_ref): original_v4_100_gold (the released v4:100 gold) and
historical_v4_1100_buggy (the released v4:1100 buggy bundle).
"""
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
SOLUTION = (HERE.parent.parent / 'solution/circuit.va').read_text()
HISTORY = None
for parent in HERE.parents:
    candidate = parent / 'benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks'
    if (candidate / '100-sample-hold-droop-front-end/evaluator/solution/sample_hold_droop_ref.va').is_file():
        HISTORY = candidate
        break

TRIGGER = ('        @(cross(V(clk, vss) - vth, +1)) begin\n'
           '            t_sample = $abstime + taperture;\n'
           '            pending = 1;\n'
           '        end\n')
CLAMP = ('                if (held < 0.0)\n                    held = 0.0;\n'
         '                if (held > span)\n                    held = span;\n')
DECIDE = '                coarse_level = (held > vth) ? span : 0.0;\n'
VALID_ON = '                valid_level = span;\n'
DROOP = ('        @(timer(0, dt)) begin\n'
         '            if (V(clk, vss) < vth)\n'
         '                held = held * alpha;\n'
         '        end\n')
OUT_V = '        V(vout, vss) <+ transition(held, 0, trf, trf);\n'
OUT_VALID = '        V(valid, vss) <+ transition(valid_level, 0, trf, trf);\n'
OUT_COARSE = '        V(coarse, vss) <+ transition(coarse_level, 0, trf, trf);\n'
OUTS = OUT_V + OUT_VALID + OUT_COARSE
DECL = '    integer valid_on;\n'
INIT_END = '            valid_on = 0;\n        end\n'
TRANS = ', 0, trf, trf);'


def sub(text, old, new, count=1):
    assert text.count(old) == count, (old[:60], text.count(old))
    return text.replace(old, new)


def body_param(text, name, value):
    """A parameter replaced by a literal inside the analog block (the declaration keeps it)."""
    a, b = text.split('    analog begin\n', 1)
    b, k = re.subn(rf'\b{name}\b', value, b)
    assert k > 0, name
    return a + '    analog begin\n' + b


def candidates():
    s = SOLUTION
    w, c = {}, {}
    # aperture and trigger
    w['no_aperture'] = sub(s, '            t_sample = $abstime + taperture;\n', '            t_sample = $abstime;\n')
    w['falling_trigger'] = sub(s, '@(cross(V(clk, vss) - vth, +1))', '@(cross(V(clk, vss) - vth, -1))')
    w['need_clk_high'] = sub(s, '            if (pending) begin\n', '            if (pending && V(clk, vss) > vth) begin\n')
    # clamp and rails
    w['no_clamp'] = sub(s, CLAMP, '')
    w['upper_clamp_only'] = sub(s, CLAMP, '                if (held > span)\n                    held = span;\n')
    w['lower_clamp_only'] = sub(s, CLAMP, '                if (held < 0.0)\n                    held = 0.0;\n')
    w['span_fixed_0p9'] = sub(s, '                span = V(vdd, vss);\n', '                span = 0.9;\n')
    w['rails_at_t0'] = sub(sub(s, '                span = V(vdd, vss);\n', ''), '            pending = 0;\n            valid_on = 0;\n',
                           '            pending = 0;\n            valid_on = 0;\n            span = V(vdd, vss);\n')
    w['rails_at_trigger'] = sub(sub(s, '                span = V(vdd, vss);\n', ''), '            t_sample = $abstime + taperture;\n',
                                '            t_sample = $abstime + taperture;\n            span = V(vdd, vss);\n')
    # reference frame
    w['ground_threshold'] = sub(sub(s, '@(cross(V(clk, vss) - vth, +1))', '@(cross(V(clk) - vth, +1))'),
                                '            if (V(clk, vss) < vth)\n', '            if (V(clk) < vth)\n')
    w['decision_from_ground'] = sub(s, DECIDE, '                coarse_level = (held + V(vss) > vth) ? span : 0.0;\n')
    w['droop_toward_ground'] = sub(s, '                held = held * alpha;\n',
                                   '                held = (held + V(vss)) * alpha - V(vss);\n')
    w['levels_fixed_0p9'] = sub(sub(s, DECIDE, '                coarse_level = (held > vth) ? 0.9 : 0.0;\n'),
                                VALID_ON, '                valid_level = 0.9;\n')
    w['low_level_zero'] = low_level_zero(s)
    # decision and valid
    w['coarse_follows_vout'] = sub(s, '                held = held * alpha;\n',
                                   '                begin\n                    held = held * alpha;\n'
                                   '                    coarse_level = (held > vth) ? V(vdd, vss) : 0.0;\n'
                                   '                end\n')
    w['valid_from_trigger'] = valid_from_trigger(s)
    w['valid_on_droop_grid'] = valid_on_grid(s)
    # droop law, phase, gating and target
    w['no_droop'] = sub(s, DROOP, '')
    w['droop_always'] = sub(s, '            if (V(clk, vss) < vth)\n                held = held * alpha;\n',
                            '            held = held * alpha;\n')
    w['droop_fall_anchored'] = fall_anchored(s)
    w['continuous_droop'] = continuous_droop(s)
    w['euler_factor'] = sub(s, '            alpha = exp(-dt / tau);\n', '            alpha = 1.0 - dt / tau;\n')
    # parameters
    w['vth_fixed_0p45'] = body_param(s, 'vth', '0.45')
    w['vth_default_0p57'] = sub(s, '    parameter real vth = 0.45 from [0.2:0.7];\n', '    parameter real vth = 0.57 from [0.2:0.7];\n')
    w['trf_fixed_40p'] = sub(s, OUTS, OUTS.replace(TRANS, ', 0, 40p, 40p);'))
    w['trf_floor_20p'] = sub(sub(s, '    parameter real valid_width = 2n from [0.5n:10n];\n',
                                 '    parameter real valid_width = 2n from [0.5n:10n];\n    parameter real trx = max(trf, 20p);\n'),
                             OUTS, OUTS.replace(TRANS, ', 0, trx, trx);'))
    w['tau_fixed_90n'] = sub(s, '            alpha = exp(-dt / tau);\n', '            alpha = exp(-dt / 90n);\n')
    w['dt_fixed_0p5n'] = sub(sub(s, '            alpha = exp(-dt / tau);\n', '            alpha = exp(-0.5n / tau);\n'),
                             '        @(timer(0, dt)) begin\n', '        @(timer(0, 0.5n)) begin\n')
    w['taperture_fixed_200p'] = sub(s, '            t_sample = $abstime + taperture;\n', '            t_sample = $abstime + 200p;\n')
    w['valid_width_fixed_2n'] = sub(s, '                t_valid_off = $abstime + valid_width;\n',
                                    '                t_valid_off = $abstime + 2n;\n')
    # output timing, scale, initial state and historical stubs
    w['late_arrival_1p3trf'] = sub(s, OUTS, OUTS.replace(TRANS, ', 0, 1.3 * trf, 1.3 * trf);'))
    w['output_scale_0p42'] = sub(sub(s, OUT_V, '        V(vout, vss) <+ 0.42 * transition(held, 0, trf, trf);\n'),
                                 OUT_VALID, '        V(valid, vss) <+ 0.42 * transition(valid_level, 0, trf, trf);\n')
    w['zero_outputs'] = sub(s, OUTS, '        V(vout) <+ transition(0.0, 0, trf, trf);\n'
                                     '        V(valid) <+ transition(0.0, 0, trf, trf);\n'
                                     '        V(coarse) <+ transition(0.0, 0, trf, trf);\n')
    w['initial_vin'] = sub(s, '            held = 0.0;\n            valid_level = 0.0;\n',
                           '            held = V(vin, vss);\n            valid_level = 0.0;\n')
    w['trigger_initial_high'] = sub(s, INIT_END, '            valid_on = 0;\n'
                                                 '            if (V(clk, vss) > vth) begin\n'
                                                 '                t_sample = taperture;\n'
                                                 '                pending = 1;\n'
                                                 '            end\n        end\n')
    w['droop_after_ramp'] = droop_after_ramp(s)
    if HISTORY is not None:
        for name, rel in (('original_v4_100_gold', '100-sample-hold-droop-front-end/evaluator/solution'),
                          ('historical_v4_1100_buggy', '1100-sample-hold-droop-front-end-bugfix/public/buggy_bundle')):
            text = (HISTORY / rel / 'sample_hold_droop_ref.va').read_text()
            w[name] = sub(text, 'module sample_hold_droop_ref(', 'module sample_hold_droop(')
    c['alt_fast_output'] = sub(s, OUTS, OUTS.replace(TRANS, ', 0, 0.2 * trf, 0.2 * trf);'))
    c['alt_delayed_within_trf'] = sub(s, OUTS, OUTS.replace(TRANS, ', 0.2 * trf, 0.8 * trf, 0.8 * trf);'))
    c['margin_arrival_1p2trf'] = sub(s, OUTS, OUTS.replace(TRANS, ', 0, 1.2 * trf, 1.2 * trf);'))
    c['alt_following_levels'] = following_levels(s)
    c['alt_counter_grid'] = counter_grid(s)
    return w, c


def low_level_zero(s):
    """valid and coarse are driven from ground: V(vdd) when high, 0 V when low."""
    s = sub(s, VALID_ON, '                valid_level = V(vdd);\n')
    s = sub(s, DECIDE, '                coarse_level = (held > vth) ? V(vdd) : 0.0;\n')
    return sub(sub(s, OUT_VALID, '        V(valid) <+ transition(valid_level, 0, trf, trf);\n'),
               OUT_COARSE, '        V(coarse) <+ transition(coarse_level, 0, trf, trf);\n')


def valid_from_trigger(s):
    """valid rises at the trigger and lasts valid_width from there."""
    s = sub(s, VALID_ON, '')
    s = sub(s, '                valid_on = 1;\n                t_valid_off = $abstime + valid_width;\n', '')
    return sub(s, TRIGGER, '        @(cross(V(clk, vss) - vth, +1)) begin\n'
                           '            t_sample = $abstime + taperture;\n            pending = 1;\n'
                           '            valid_level = V(vdd, vss);\n            valid_on = 1;\n'
                           '            t_valid_off = $abstime + valid_width;\n        end\n')


def valid_on_grid(s):
    """valid falls at the first droop update instant after c_k + valid_width (the v4:100 gold)."""
    s = sub(s, '        @(timer(t_valid_off)) begin\n            if (valid_on) begin\n                valid_level = 0.0;\n'
               '                valid_on = 0;\n            end\n        end\n\n', '')
    return sub(s, DROOP, '        @(timer(0, dt)) begin\n            if (V(clk, vss) < vth)\n                held = held * alpha;\n'
                         '            if (valid_on && $abstime > t_valid_off) begin\n                valid_level = 0.0;\n'
                         '                valid_on = 0;\n            end\n        end\n')


def fall_anchored(s):
    """Droop updates every dt counted from each falling clk crossing, while clk stays low."""
    s = sub(s, DECL, DECL + '    real t_droop;\n')
    s = sub(s, INIT_END, '            valid_on = 0;\n            t_droop = -1.0;\n        end\n')
    return sub(s, DROOP, '        @(cross(V(clk, vss) - vth, -1))\n            t_droop = $abstime + dt;\n\n'
                         '        @(timer(t_droop)) begin\n            if (V(clk, vss) < vth) begin\n'
                         '                held = held * alpha;\n                t_droop = t_droop + dt;\n'
                         '            end\n        end\n')


def continuous_droop(s):
    """dh/dt = -h/tau while clk is low: the sampled value times exp(-(low time since the sample)/tau)."""
    s = sub(s, DECL, DECL + '    integer low;\n    real acc;\n    real t_low;\n    real smooth;\n')
    s = sub(s, INIT_END, '            valid_on = 0;\n            low = 1;\n            acc = 0.0;\n            t_low = 0.0;\n'
                         '        end\n')
    s = sub(s, TRIGGER, '        @(cross(V(clk, vss) - vth, +1)) begin\n'
                        '            t_sample = $abstime + taperture;\n            pending = 1;\n'
                        '            if (low)\n                acc = acc + $abstime - t_low;\n            low = 0;\n'
                        '        end\n\n'
                        '        @(cross(V(clk, vss) - vth, -1)) begin\n            low = 1;\n'
                        '            t_low = $abstime;\n        end\n')
    s = sub(s, '                pending = 0;\n', '                pending = 0;\n                acc = 0.0;\n'
               '                t_low = $abstime;\n')
    s = sub(s, DROOP, '')
    return sub(s, OUT_V, '        smooth = transition(held, 0, trf, trf);\n'
                         '        V(vout, vss) <+ smooth * exp(-(acc + (low ? $abstime - t_low : 0.0)) / tau);\n')


def droop_after_ramp(s):
    """vout starts a new ramp only after the running one has ended (1 ps later), not at the change itself."""
    retarget = ('                if (held != out_level) begin\n'
                '                    if ($abstime < t_ramp_end) begin\n'
                '                        t_apply = t_ramp_end + 1p;\n'
                '                        apply_pending = 1;\n'
                '                    end else begin\n'
                '                        out_level = held;\n'
                '                        t_ramp_end = $abstime + trf;\n'
                '                    end\n'
                '                end\n')
    s = sub(s, DECL, DECL + '    integer apply_pending;\n    real out_level;\n    real t_ramp_end;\n    real t_apply;\n')
    s = sub(s, INIT_END, '            valid_on = 0;\n            apply_pending = 0;\n            out_level = 0.0;\n'
                         '            t_ramp_end = -1.0;\n            t_apply = -1.0;\n        end\n')
    s = sub(s, '                pending = 0;\n            end\n', '                pending = 0;\n' + retarget + '            end\n')
    s = sub(s, DROOP, '        @(timer(0, dt)) begin\n            if (V(clk, vss) < vth) begin\n'
                      '                held = held * alpha;\n' + retarget + '            end\n        end\n\n'
                      '        @(timer(t_apply)) begin\n            if (apply_pending) begin\n'
                      '                out_level = held;\n                t_ramp_end = $abstime + trf;\n'
                      '                apply_pending = 0;\n            end\n        end\n')
    return sub(s, OUT_V, '        V(vout, vss) <+ transition(out_level, 0, trf, trf);\n')


def following_levels(s):
    """valid and coarse follow V(vdd) while high (equal to the latched levels when vdd is constant there)."""
    s = sub(s, VALID_ON, '                valid_level = 1.0;\n')
    s = sub(s, DECIDE, '                coarse_level = (held > vth) ? 1.0 : 0.0;\n')
    return sub(sub(s, OUT_VALID, '        V(valid, vss) <+ V(vdd, vss) * transition(valid_level, 0, trf, trf);\n'),
               OUT_COARSE, '        V(coarse, vss) <+ V(vdd, vss) * transition(coarse_level, 0, trf, trf);\n')


def counter_grid(s):
    """The droop grid from an absolute timer and an update counter instead of a periodic timer."""
    s = sub(s, DECL, DECL + '    integer updates;\n    real next_update;\n')
    s = sub(s, INIT_END, '            valid_on = 0;\n            updates = 1;\n            next_update = dt;\n        end\n')
    return sub(s, DROOP, '        @(timer(next_update)) begin\n            if (V(clk, vss) < vth)\n'
                         '                held = held * alpha;\n            updates = updates + 1;\n'
                         '            next_update = updates * dt;\n        end\n')


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    out = Path(sys.argv[1])
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f'{out} is not empty')
    wrong, correct = candidates()
    for group, items in (('wrong', wrong), ('correct', correct)):
        (out / group).mkdir(parents=True)
        for name, text in items.items():
            assert text != SOLUTION, name
            (out / group / f'{name}.va').write_text(text)
    print(f'{len(wrong)} wrong, {len(correct)} correct candidates in {out}')


if __name__ == '__main__':
    main()
