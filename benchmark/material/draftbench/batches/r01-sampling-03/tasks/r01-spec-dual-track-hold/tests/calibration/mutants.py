#!/usr/bin/env python3
"""Write the calibration candidates of r01-spec-dual-track-hold into an empty directory.

    python3 -B mutants.py <output-directory>

wrong/<name>.va must be rejected and correct/<name>.va must be accepted by the
checker in ../verify.py on ../cases.json. Each candidate is ../../solution/circuit.va
with checked text changes, except alt_two_modules (the same behavior in two helper
modules) and original_v4_236_gold, the released v4:236 gold read from
benchmark/material/historyref when this file runs inside the repository (its module
name and ports are those of this task). expected.json holds the rejection matrix.
"""
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
SOLUTION = (HERE.parent.parent / 'solution/circuit.va').read_text()
GOLD = None
for parent in HERE.parents:
    candidate = parent / ('benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/'
                          '236-dual-track-sample-hold/evaluator/solution/dual_track_sample_hold.va')
    if candidate.is_file():
        GOLD = candidate
        break

DECL = '    real tracks;   // 1 while the clock is high and the output stage tracks\n'
INIT = ('            a = vinit;\n'
        '            b = vinit;\n'
        '            tracks = (V(clk, vss) > vth) ? 1.0 : 0.0;\n')
RISE = '        @(cross(V(clk, vss) - vth, +1))\n            tracks = 1.0;\n'
FALL = '        @(cross(V(clk, vss) - vth, -1))\n            tracks = 0.0;\n'
TIMER = '        @(timer(0, tick)) begin\n'
SPAN = '            s = V(vdd, vss);\n'
OUT_STEP = '                b = b + alpha_out * (a - b);\n'
IN_STEP = '                a = a + alpha_in * (V(vin, vss) - a);\n'
UPDATE = '            if (tracks > 0.5)\n' + OUT_STEP + '            else\n' + IN_STEP
LIMIT = '            a = min(max(a, 0.0), s);\n            b = min(max(b, 0.0), s);\n'
TIMER_BLOCK = TIMER + SPAN + UPDATE + LIMIT + '        end\n'
OUT = '        V(vout, vss) <+ transition(b, 0.0, tedge, tedge);\n'
PH = '        V(phase, vss) <+ V(vdd, vss) * transition(tracks, 0.0, tedge, tedge);\n'


def sub(text, old, new, count=1):
    assert text.count(old) == count, (old[:60], text.count(old))
    return text.replace(old, new)


def body_param(text, name, value):
    """A parameter replaced by a literal inside the analog block (the declaration keeps it)."""
    a, b = text.split('    analog begin\n', 1)
    b, k = re.subn(rf'\b{name}\b', value, b)
    assert k > 0, name
    return a + '    analog begin\n' + b


def declare(text, line):
    return sub(text, DECL, DECL + line)


def two_modules():
    return '''`include "constants.vams"
`include "disciplines.vams"

// Input stage: acquires vin on low-clock ticks and publishes its value on node aout.
module dth_input_stage(vdd, vss, clk, vin, aout);
    inout vdd, vss;
    input clk, vin;
    output aout;
    electrical vdd, vss, clk, vin, aout;
    parameter real vth = 0.45;
    parameter real tick = 0.5n;
    parameter real alpha = 0.45;
    parameter real vinit = 0.0;
    real a;
    real s;
    real low;

    analog begin
        @(initial_step) begin
            a = vinit;
            low = (V(clk, vss) > vth) ? 0.0 : 1.0;
        end
        @(cross(V(clk, vss) - vth, +1))
            low = 0.0;
        @(cross(V(clk, vss) - vth, -1))
            low = 1.0;
        @(timer(0, tick)) begin
            s = V(vdd, vss);
            if (low > 0.5)
                a = a + alpha * (V(vin, vss) - a);
            a = min(max(a, 0.0), s);
        end
        V(aout, vss) <+ transition(a, 0.0, 1p, 1p);
    end
endmodule

// Output stage: acquires the published input-stage value on high-clock ticks.
module dth_output_stage(vdd, vss, clk, ain, vout, phase);
    inout vdd, vss;
    input clk, ain;
    output vout, phase;
    electrical vdd, vss, clk, ain, vout, phase;
    parameter real vth = 0.45;
    parameter real tick = 0.5n;
    parameter real alpha = 0.55;
    parameter real tedge = 50p;
    parameter real vinit = 0.0;
    real b;
    real s;
    real tracks;

    analog begin
        @(initial_step) begin
            b = vinit;
            tracks = (V(clk, vss) > vth) ? 1.0 : 0.0;
        end
        @(cross(V(clk, vss) - vth, +1))
            tracks = 1.0;
        @(cross(V(clk, vss) - vth, -1))
            tracks = 0.0;
        @(timer(0, tick)) begin
            s = V(vdd, vss);
            if (tracks > 0.5)
                b = b + alpha * (V(ain, vss) - b);
            b = min(max(b, 0.0), s);
        end
        V(vout, vss) <+ transition(b, 0.0, tedge, tedge);
        V(phase, vss) <+ V(vdd, vss) * transition(tracks, 0.0, tedge, tedge);
    end
endmodule

module dual_track_sample_hold(vdd, vss, clk, vin, vout, phase);
    inout vdd, vss;
    input clk, vin;
    output vout, phase;
    electrical vdd, vss, clk, vin, vout, phase, held;

    parameter real vth = 0.45 from [0.1:0.8];
    parameter real tick = 0.5n from [0.25n:5n];
    parameter real alpha_in = 0.45 from (0:1];
    parameter real alpha_out = 0.55 from (0:1];
    parameter real tedge = 50p from [10p:1.25n];
    parameter real vinit = 0.0 from [0:1.5];

    dth_input_stage #(.vth(vth), .tick(tick), .alpha(alpha_in), .vinit(vinit)) xin(vdd, vss, clk, vin, held);
    dth_output_stage #(.vth(vth), .tick(tick), .alpha(alpha_out), .tedge(tedge), .vinit(vinit))
        xout(vdd, vss, clk, held, vout, phase);
endmodule
'''


def candidates():
    s = SOLUTION
    for part in (DECL, INIT, RISE, FALL, TIMER_BLOCK, OUT, PH):
        assert s.count(part) == 1, part[:50]
    w = {}
    w['late_arrival_1p3tedge'] = sub(s, 'tedge, tedge)', '1.3 * tedge, 1.3 * tedge)', 2)
    w['transparent_output'] = sub(s, UPDATE, '            b = V(vin, vss);\n')
    w['single_edge_sampler'] = sub(sub(s, TIMER_BLOCK, ''), RISE,
                                   '        @(cross(V(clk, vss) - vth, +1)) begin\n            tracks = 1.0;\n'
                                   '            b = min(max(V(vin, vss), 0.0), V(vdd, vss));\n        end\n')
    w['wrong_track_phase'] = sub(s, '            if (tracks > 0.5)\n', '            if (tracks < 0.5)\n')
    w['no_output_hold'] = sub(s, UPDATE, '            if (tracks < 0.5)\n' + IN_STEP +
                              '            b = b + alpha_out * (a - b);\n')
    w['phase_inverted'] = sub(s, 'transition(tracks, 0.0', 'transition(1.0 - tracks, 0.0')
    w['input_stage_ideal'] = sub(s, IN_STEP, '                a = V(vin, vss);\n')
    w['output_stage_ideal'] = sub(s, OUT_STEP, '                b = a;\n')
    w['output_copy_at_rising_edge'] = sub(sub(s, RISE, '        @(cross(V(clk, vss) - vth, +1)) begin\n'
                                              '            tracks = 1.0;\n            b = a;\n        end\n'),
                                          UPDATE, '            if (tracks < 0.5)\n' + IN_STEP)
    w['input_sample_at_rising_edge'] = sub(sub(s, RISE, '        @(cross(V(clk, vss) - vth, +1)) begin\n'
                                               '            tracks = 1.0;\n'
                                               '            a = min(max(V(vin, vss), 0.0), V(vdd, vss));\n        end\n'),
                                           UPDATE, '            if (tracks > 0.5)\n' + OUT_STEP)
    w['output_reads_vin'] = sub(s, OUT_STEP, '                b = b + alpha_out * (V(vin, vss) - b);\n')
    w['input_tracks_both_phases'] = sub(declare(s, '    real na;\n'), UPDATE,
                                        '            na = a + alpha_in * (V(vin, vss) - a);\n'
                                        '            if (tracks > 0.5)\n' + OUT_STEP + '            a = na;\n')
    w['edge_extra_update'] = sub(sub(s, RISE, '        @(cross(V(clk, vss) - vth, +1)) begin\n            tracks = 1.0;\n'
                                     '            b = min(max(b + alpha_out * (a - b), 0.0), V(vdd, vss));\n        end\n'),
                                 FALL, '        @(cross(V(clk, vss) - vth, -1)) begin\n            tracks = 0.0;\n'
                                 '            a = min(max(a + alpha_in * (V(vin, vss) - a), 0.0), V(vdd, vss));\n        end\n')
    r = declare(s, '    real tnext;\n')
    r = sub(r, INIT, INIT + '            tnext = 0.0;\n')
    r = sub(r, RISE, '        @(cross(V(clk, vss) - vth, +1)) begin\n            tracks = 1.0;\n'
            '            tnext = $abstime + tick;\n        end\n')
    r = sub(r, FALL, '        @(cross(V(clk, vss) - vth, -1)) begin\n            tracks = 0.0;\n'
            '            tnext = $abstime + tick;\n        end\n')
    w['grid_restart_at_edges'] = sub(r, TIMER, '        @(timer(tnext)) begin\n            tnext = tnext + tick;\n')
    w['no_tick_at_zero'] = sub(s, '@(timer(0, tick))', '@(timer(tick, tick))')
    w['grid_half_offset'] = sub(s, '@(timer(0, tick))', '@(timer(0.5 * tick, tick))')
    w['alphas_swapped'] = sub(sub(s, OUT_STEP, OUT_STEP.replace('alpha_out', 'alpha_in')),
                              IN_STEP, IN_STEP.replace('alpha_in', 'alpha_out'))
    for name, value in (('alpha_in', '0.45'), ('alpha_out', '0.55'), ('tick', '0.5n'), ('vth', '0.45'),
                        ('tedge', '50p'), ('vinit', '0.0')):
        w['fixed_' + name] = body_param(s, name, value)
    w['no_clamp'] = sub(s, LIMIT, '')
    w['clamp_upper_only'] = sub(s, LIMIT, '            a = min(a, s);\n            b = min(b, s);\n')
    w['clamp_lower_only'] = sub(s, LIMIT, '            a = max(a, 0.0);\n            b = max(b, 0.0);\n')
    w['clamp_fixed_0p9'] = sub(s, SPAN, '            s = 0.9;\n')
    w['clamp_rails_at_start'] = sub(sub(s, SPAN, ''), INIT, INIT + '            s = V(vdd, vss);\n')
    w['clamp_input_first'] = sub(sub(s, IN_STEP, '                a = a + alpha_in * (min(max(V(vin, vss), 0.0), s) - a);\n'),
                                 LIMIT, '            b = min(max(b, 0.0), s);\n')
    w['clamp_updated_stage_only'] = sub(sub(s, UPDATE, '            if (tracks > 0.5)\n'
                                            '                b = min(max(b + alpha_out * (a - b), 0.0), s);\n'
                                            '            else\n'
                                            '                a = min(max(a + alpha_in * (V(vin, vss) - a), 0.0), s);\n'),
                                        LIMIT, '')
    w['clamp_output_only'] = sub(sub(s, LIMIT, ''), OUT,
                                 '        V(vout, vss) <+ min(max(transition(b, 0.0, tedge, tedge), 0.0), V(vdd, vss));\n')
    g = s
    for old, new in (('V(clk, vss)', 'V(clk)'), ('V(vdd, vss)', 'V(vdd)'), ('V(vin, vss)', 'V(vin)'),
                     ('V(vout, vss) <+', 'V(vout) <+'), ('V(phase, vss) <+', 'V(phase) <+')):
        g = g.replace(old, new)
    w['ground_referenced'] = g
    v = declare(s, '    real v0;\n')
    v = sub(v, INIT, '            v0 = V(vss);\n' + INIT)
    for old, new in (('V(clk, vss)', '(V(clk) - v0)'), ('V(vin, vss)', '(V(vin) - v0)'),
                     ('V(vout, vss) <+ transition', 'V(vout) <+ v0 + transition'),
                     ('V(phase, vss) <+ V(vdd, vss) *', 'V(phase) <+ v0 + (V(vdd) - v0) *'),
                     ('V(vdd, vss)', '(V(vdd) - v0)')):
        v = v.replace(old, new)
    w['vss_at_start'] = v
    w['phase_fixed_levels'] = sub(s, PH, '        V(phase) <+ 0.9 * transition(tracks, 0.0, tedge, tedge);\n')
    p = declare(s, '    real ph;\n')
    p = sub(p, INIT, INIT + '            ph = tracks;\n')
    p = sub(p, TIMER + SPAN, TIMER + '            ph = tracks;\n' + SPAN)
    w['phase_from_ticks'] = sub(p, 'transition(tracks, 0.0', 'transition(ph, 0.0')
    w['initial_from_vin'] = sub(s, INIT, '            a = V(vin, vss);\n            b = V(vin, vss);\n'
                                '            tracks = (V(clk, vss) > vth) ? 1.0 : 0.0;\n')
    w['initial_output_zero'] = sub(s, '            b = vinit;\n', '            b = 0.0;\n')
    w['initial_input_vin'] = sub(s, '            a = vinit;\n', '            a = V(vin, vss);\n')

    c = {}
    c['alt_level_at_tick'] = sub(s, '            if (tracks > 0.5)\n', '            if (V(clk, vss) > vth)\n')
    c['alt_latched_span_phase'] = sub(sub(s, INIT, INIT + '            s = V(vdd, vss);\n'), PH,
                                      '        V(phase, vss) <+ transition(tracks > 0.5 ? s : 0.0, 0.0, tedge, tedge);\n')
    c['alt_limit_then_update'] = sub(s, SPAN + UPDATE, SPAN + LIMIT + UPDATE)
    c['alt_two_modules'] = two_modules()
    c['alt_fast_transition'] = sub(s, 'tedge, tedge)', '0.5 * tedge, 0.5 * tedge)', 2)
    c['margin_arrival_1p2tedge'] = sub(s, 'tedge, tedge)', '1.2 * tedge, 1.2 * tedge)', 2)
    if GOLD is not None:
        c['original_v4_236_gold'] = GOLD.read_text()
    return w, c


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
