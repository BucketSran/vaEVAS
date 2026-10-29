#!/usr/bin/env python3
"""Write the calibration candidates of r01-spec-droop-leakage-hold into an empty directory.

    python3 -B mutants.py <output-directory>

wrong/<name>.va must be rejected and correct/<name>.va must be accepted by the
checker in ../verify.py on ../cases.json, as listed in expected.json. Each candidate
is ../../solution/circuit.va with checked text changes, except two that are read
byte for byte from benchmark/material/historyref when this file runs inside the
repository: original_v4_042_gold (the released v4:042 gold, same module name and
ports as this task) and historical_v4_1042_buggy (the released v4:1042 buggy bundle).
"""
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
SOLUTION = (HERE.parent.parent / 'solution/circuit.va').read_text()
HISTORY = None
for parent in HERE.parents:
    candidate = parent / 'benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks'
    if (candidate / '042-sample-and-hold-with-droop-leakage/evaluator/solution/leaky_hold.va').is_file():
        HISTORY = candidate
        break

LEAK = ('        // Leak updates at k*leak_period; captures and resets do not move this grid.\n'
        '        @(timer(0, leak_period))\n'
        '            held = held * decay;\n')
CLEAR = ('        // Asynchronous clear. Captures stay blocked while rst is high.\n'
         '        @(cross(V(rst) - vth, +1))\n'
         '            held = 0.0;\n')
CAPTURE = ('        @(cross(V(sample) - vth, +1))\n'
           '            if (V(rst) <= vth)\n'
           '                held = V(vin);\n')
OUT = '        V(vout) <+ transition(held, 0, tr, tr);\n'
DECL = '    real held;\n'
INIT = '        @(initial_step)\n            held = 0.0;\n'


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
    # the leak grid and law
    w['leak_from_capture'] = leak_from_capture(s)
    w['leak_grid_half_phase'] = sub(s, '@(timer(0, leak_period))', '@(timer(0.5 * leak_period, leak_period))')
    w['continuous_leak'] = continuous_leak(s)
    w['no_leak'] = sub(s, LEAK, '')
    w['leak_only_sample_low'] = sub(s, '            held = held * decay;\n',
                                    '            if (V(sample) <= vth)\n                held = held * decay;\n')
    w['negative_not_leaked'] = sub(s, '            held = held * decay;\n',
                                   '            if (held > 0.0)\n                held = held * decay;\n')
    w['capture_includes_leak'] = sub(s, '                held = V(vin);\n', '                held = V(vin) * decay;\n')
    # parameters written as literals
    w['decay_fixed_0p985'] = body_param(s, 'decay', '0.985')
    w['period_fixed_1n'] = body_param(s, 'leak_period', '1n')
    w['tr_fixed_500p'] = sub(s, OUT, '        V(vout) <+ transition(held, 0, 500p, 500p);\n')
    w['vth_fixed_0p45'] = body_param(s, 'vth', '0.45')
    w['tr_floor_100p'] = sub(s, OUT, '        V(vout) <+ transition(held, 0, max(tr, 100p), max(tr, 100p));\n')
    # reset
    w['sync_reset_events'] = sub(sub(sub(s, CLEAR, ''), '            held = held * decay;\n',
                                     '            if (V(rst) > vth)\n                held = 0.0;\n'
                                     '            else\n                held = held * decay;\n'),
                                 '            if (V(rst) <= vth)\n                held = V(vin);\n',
                                 '            if (V(rst) > vth)\n                held = 0.0;\n'
                                 '            else\n                held = V(vin);\n')
    w['capture_in_reset'] = sub(s, CAPTURE, '        @(cross(V(sample) - vth, +1))\n            held = V(vin);\n')
    w['capture_on_release'] = sub(s, CAPTURE, CAPTURE + '\n        @(cross(V(rst) - vth, -1))\n'
                                  '            if (V(sample) > vth)\n                held = V(vin);\n')
    w['reset_ignored'] = sub(sub(s, CLEAR, ''), CAPTURE,
                             '        @(cross(V(sample) - vth, +1))\n            held = V(vin);\n')
    # capture edge, tracking and initial state
    w['falling_edge_capture'] = sub(s, '@(cross(V(sample) - vth, +1))', '@(cross(V(sample) - vth, -1))')
    w['track_while_high'] = track_while_high(s)
    w['sample_deglitch_0p6n'] = deglitch(s)
    w['initial_vin'] = sub(s, INIT, '        @(initial_step)\n            held = V(vin);\n')
    w['capture_initial_high'] = sub(s, INIT, '        @(initial_step)\n'
                                             '            held = (V(sample) > vth && V(rst) <= vth) ? V(vin) : 0.0;\n')
    # output timing
    w['late_arrival_1p3tr'] = sub(s, OUT, '        V(vout) <+ transition(held, 0, 1.3 * tr, 1.3 * tr);\n')
    if HISTORY is not None:
        w['original_v4_042_gold'] = (HISTORY / '042-sample-and-hold-with-droop-leakage/evaluator/solution/'
                                     'leaky_hold.va').read_text()
        w['historical_v4_1042_buggy'] = (HISTORY / '1042-sample-and-hold-with-droop-leakage-bugfix/public/'
                                         'buggy_bundle/leaky_hold.va').read_text()
    c['alt_fast_output'] = sub(s, OUT, '        V(vout) <+ transition(held, 0, 0.2 * tr, 0.2 * tr);\n')
    c['alt_counter_grid'] = counter_grid(s)
    c['alt_delayed_within_tr'] = sub(s, OUT, '        V(vout) <+ transition(held, 0.2 * tr, 0.8 * tr, 0.8 * tr);\n')
    c['margin_arrival_1p2tr'] = sub(s, OUT, '        V(vout) <+ transition(held, 0, 1.2 * tr, 1.2 * tr);\n')
    return w, c


def leak_from_capture(s):
    """The leak grid restarts at each capture: the first update comes one leak_period after it."""
    s = sub(s, DECL, DECL + '    real t_next;\n    integer leaking;\n')
    s = sub(s, INIT, '        @(initial_step) begin\n            held = 0.0;\n            t_next = -1.0;\n'
                     '            leaking = 0;\n        end\n')
    s = sub(s, LEAK, '        @(timer(t_next))\n            if (leaking) begin\n                held = held * decay;\n'
                     '                t_next = t_next + leak_period;\n            end\n')
    return sub(s, '                held = V(vin);\n', '                begin\n                    held = V(vin);\n'
               '                    t_next = $abstime + leak_period;\n                    leaking = 1;\n'
               '                end\n')


def continuous_leak(s):
    """The captured value decays continuously, decay^((t - t_capture)/leak_period); captures jump."""
    s = sub(s, DECL, DECL + '    real t_cap;\n')
    s = sub(s, INIT, '        @(initial_step) begin\n            held = 0.0;\n            t_cap = 0.0;\n        end\n')
    s = sub(s, LEAK, '')
    s = sub(s, '                held = V(vin);\n', '                begin\n                    held = V(vin);\n'
               '                    t_cap = $abstime;\n                end\n')
    return sub(s, OUT, '        V(vout) <+ held * exp(ln(decay) * ($abstime - t_cap) / leak_period);\n')


def track_while_high(s):
    """vout follows vin from a capture until the falling sample crossing, which then holds vin."""
    s = sub(s, DECL, DECL + '    real tracking;\n    real smooth;\n')
    s = sub(s, INIT, '        @(initial_step) begin\n            held = 0.0;\n            tracking = 0.0;\n        end\n')
    s = sub(s, CLEAR, '        // Asynchronous clear. Captures stay blocked while rst is high.\n'
                      '        @(cross(V(rst) - vth, +1)) begin\n            held = 0.0;\n            tracking = 0.0;\n'
                      '        end\n')
    s = sub(s, '                held = V(vin);\n', '                begin\n                    held = V(vin);\n'
               '                    tracking = 1.0;\n                end\n\n'
               '        @(cross(V(sample) - vth, -1))\n            if (tracking > 0.5) begin\n'
               '                held = V(vin);\n                tracking = 0.0;\n            end\n')
    return sub(s, OUT, '        smooth = transition(held, 0, tr, tr);\n'
                       '        V(vout) <+ tracking * V(vin) + (1.0 - tracking) * smooth;\n')


def deglitch(s):
    """A rising sample crossing after less than 0.6 ns low is ignored (stricter than the 0.5 ns minimum)."""
    s = sub(s, DECL, DECL + '    real t_fall;\n')
    s = sub(s, INIT, '        @(initial_step) begin\n            held = 0.0;\n            t_fall = 0.0;\n        end\n')
    s = sub(s, CAPTURE, '        @(cross(V(sample) - vth, -1))\n            t_fall = $abstime;\n\n'
            '        @(cross(V(sample) - vth, +1))\n            if (V(rst) <= vth && $abstime - t_fall >= 0.6n)\n'
            '                held = V(vin);\n')
    return s


def counter_grid(s):
    """The same leak grid from an absolute timer and an update counter instead of a periodic timer."""
    s = sub(s, DECL, DECL + '    real next_leak;\n    integer updates;\n')
    s = sub(s, INIT, '        @(initial_step) begin\n            held = 0.0;\n            updates = 1;\n'
                     '            next_leak = leak_period;\n        end\n')
    return sub(s, LEAK, '        // Leak update k at k*leak_period, k = 1, 2, ...\n        @(timer(next_leak)) begin\n'
                        '            held = held * decay;\n            updates = updates + 1;\n'
                        '            next_leak = updates * leak_period;\n        end\n')


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
