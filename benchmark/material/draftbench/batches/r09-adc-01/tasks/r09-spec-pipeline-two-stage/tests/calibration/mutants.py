#!/usr/bin/env python3
"""Write the calibration candidates of r09-spec-pipeline-two-stage into an empty directory.

    python3 -B mutants.py <output-directory>

wrong/<name>.va must be rejected and correct/<name>.va must be accepted by the
checker in ../verify.py on ../cases.json. Most candidates are derived from
../../solution/circuit.va by one checked text change; four are written out in
full (a gold-like live residue, a tracking stage 1, a three-module hierarchy and
a compute-then-delay pipeline), and original_v4_343_gold wraps the five released
v4:343 gold modules from benchmark/material/historyref when this file runs inside
the repository. expected.json holds the rejection matrix.
"""
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
SOLUTION = (HERE.parent.parent / 'solution/circuit.va').read_text()
GOLD = None
for parent in HERE.parents:
    candidate = parent / 'benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/343-pipeline-adc-two-stage'
    if (candidate / 'evaluator/solution').is_dir():
        GOLD = candidate / 'evaluator/solution'
        break

RES = 'res = 0.5*(vss + vref) + 4.0*(x - (vss + (k1 + 0.5)*0.25*span));'
K1 = ('                    k1 = 0;\n'
      '                    if (x >= vss + 0.25*span) k1 = 1;\n'
      '                    if (x >= vss + 0.50*span) k1 = 2;\n'
      '                    if (x >= vss + 0.75*span) k1 = 3;\n')
F2 = ('                    f2 = 0;\n'
      '                    if (res >= vss + 0.25*span) f2 = 1;\n'
      '                    if (res >= vss + 0.50*span) f2 = 2;\n'
      '                    if (res >= vss + 0.75*span) f2 = 3;\n')
CLAMP = ('                    if (x < vss) x = vss;\n'
         '                    if (x > vref) x = vref;\n')
PUB = ('                valid_q = s2_valid;\n'
       '                if (s2_valid)\n'
       '                    code = 4*k2 + f2;\n')
STAGE2 = ('                s2_valid = s1_new;\n'
          '                if (s1_new) begin\n'
          '                    k2 = k1;\n' + F2 +
          '                end\n')
TAKE = '                s1_new = V(valid_i) > vth;\n'
STAGE1 = (TAKE +
          '                if (s1_new) begin\n'
          '                    x = V(vin);\n' + CLAMP + K1 +
          '                    // Gain-of-four error from the bin center, referred to mid-scale.\n'
          '                    ' + RES + '\n'
          '                end\n')
CLK = '@(cross(V(clk) - vth, +1, 1p)) begin'
GATE = '            if (V(rst) < vth) begin\n'
CLIP = ' if (res < vss) res = vss; if (res > vref) res = vref;'
RST_BODY = ('            x = vss;\n'
            '            res = vss;\n'
            '            k1 = 0;\n'
            '            s1_new = 0;\n'
            '            s2_valid = 0;\n'
            '            code = 0;\n'
            '            valid_q = 0;\n'
            '        end\n\n'
            '        // Each clock edge')


def sub(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


def body_param(text, name, value):
    """Replace a parameter by a literal inside the analog block (the declaration keeps its default)."""
    head, body = text.split('    analog begin\n', 1)
    body, n = re.subn(rf'\b{name}\b', value, body)
    assert n > 0, name
    return head + '    analog begin\n' + body


def declare(text, line):
    return sub(text, '    integer valid_q;\n', '    integer valid_q;\n' + line)


def candidates():
    s = SOLUTION
    wrong, correct = {}, {}
    wrong['center_residue_no_midscale'] = sub(s, RES, 'res = vss + 4.0*(x - (vss + (k1 + 0.5)*0.25*span));' + CLIP)
    wrong['edge_residue_midscale_offset'] = sub(s, RES, 'res = 0.5*(vss + vref) + 4.0*(x - (vss + k1*0.25*span));' + CLIP)
    wrong['residue_gain_2'] = sub(s, RES, 'res = 0.5*(vss + vref) + 2.0*(x - (vss + (k1 + 0.5)*0.25*span));')
    wrong['rounded_coarse_thresholds'] = sub(sub(s, K1, K1.replace('0.25*span) k1 = 1', '0.125*span) k1 = 1')
                                                 .replace('0.50*span) k1 = 2', '0.375*span) k1 = 2')
                                                 .replace('0.75*span) k1 = 3', '0.625*span) k1 = 3')), RES, RES + CLIP)
    wrong['rounded_fine_thresholds'] = sub(s, F2, F2.replace('0.25*span) f2 = 1', '0.125*span) f2 = 1')
                                           .replace('0.50*span) f2 = 2', '0.375*span) f2 = 2')
                                           .replace('0.75*span) f2 = 3', '0.625*span) f2 = 3'))
    wrong['stage_order_swapped'] = sub(s, 'code = 4*k2 + f2;', 'code = 4*f2 + k2;')
    wrong['low_bits_swapped'] = sub(sub(s, 'V(code_1) <+ transition(((code >> 1) & 1)', 'V(code_1) <+ transition((code & 1)'),
                                    'V(code_0) <+ transition((code & 1)', 'V(code_0) <+ transition(((code >> 1) & 1)')
    wrong['no_input_limit_wraps'] = sub(sub(sub(s, CLAMP, ''), K1, '                    k1 = floor(4.0*(x - vss)/span);\n'),
                                        'code = 4*k2 + f2;', 'code = (4*k2 + f2) & 15;')
    wrong['residue_from_unlimited_input'] = sub(s, RES, 'res = 0.5*(vss + vref) + 4.0*(V(vin) - (vss + (k1 + 0.5)*0.25*span));')
    wrong['top_bin_floor_at_vref'] = sub(s, K1, '                    k1 = floor(4.0*(x - vss)/span);\n')
    wrong['live_input_residue'] = live_input_residue(s)
    wrong['track_while_clock_high'] = track_while_clock_high(s)
    wrong['residue_one_cycle_then_vss'] = sub(s, STAGE1, STAGE1[:-len('                end\n')] +
                                              '                end else\n                    res = vss;\n')
    wrong['stage2_takes_new_sample'] = sub(s, STAGE2 + '\n' + STAGE1,
                                           '                s2_valid = s1_new;\n'
                                           '                if (s2_valid)\n'
                                           '                    k2 = k1;\n' + STAGE1 +
                                           '                if (s2_valid) begin\n' + F2 + '                end\n')
    wrong['aligner_takes_new_coarse'] = sub(s, 'code = 4*k2 + f2;', 'code = 4*k1 + f2;')
    wrong['latency_one_edge'] = sub(s, PUB + '\n' + STAGE2,
                                    '                valid_q = s1_new;\n'
                                    '                if (s1_new) begin\n' + F2 +
                                    '                    code = 4*k1 + f2;\n'
                                    '                end\n')
    wrong['latency_three_edges'] = sub(sub(declare(s, '    integer k3, f3, s3_valid;\n'), PUB,
                                           '                valid_q = s3_valid;\n'
                                           '                if (s3_valid)\n'
                                           '                    code = 4*k3 + f3;\n'
                                           '                s3_valid = s2_valid;\n'
                                           '                k3 = k2;\n'
                                           '                f3 = f2;\n'),
                                       '            s2_valid = 0;\n            code = 0;\n',
                                       '            s2_valid = 0;\n            s3_valid = 0;\n            code = 0;\n', count=2)
    wrong['sticky_valid'] = sub(s, PUB, '                if (s2_valid) begin\n'
                                        '                    valid_q = 1;\n'
                                        '                    code = 4*k2 + f2;\n'
                                        '                end\n')
    wrong['valid_5ns_pulse'] = valid_pulse(s)
    wrong['advance_only_on_valid'] = sub(s, GATE, '            if (V(rst) < vth && V(valid_i) <= vth)\n'
                                                  '                valid_q = 0;\n'
                                                  '            if (V(rst) < vth && V(valid_i) > vth) begin\n')
    wrong['ignores_valid_i'] = sub(s, TAKE, '                s1_new = 1;\n')
    wrong['valid_not_pipelined'] = sub(s, PUB, PUB + '                valid_q = V(valid_i) > vth;\n')
    wrong['code_zero_between_results'] = sub(s, PUB, '                valid_q = s2_valid;\n'
                                                     '                if (s2_valid)\n'
                                                     '                    code = 4*k2 + f2;\n'
                                                     '                else\n'
                                                     '                    code = 0;\n')
    wrong['falling_edge_clock'] = sub(s, CLK, '@(cross(V(clk) - vth, -1, 1p)) begin')
    wrong['synchronous_reset'] = synchronous_reset(s)
    wrong['reset_keeps_pipeline'] = sub(s, '            s1_new = 0;\n            s2_valid = 0;\n            code = 0;\n'
                                           '            valid_q = 0;\n        end\n\n        // Each',
                                        '            code = 0;\n            valid_q = 0;\n        end\n\n        // Each')
    wrong['reset_keeps_residue'] = sub(s, RST_BODY, RST_BODY.replace('            x = vss;\n            res = vss;\n'
                                                                     '            k1 = 0;\n', ''))
    wrong['reset_keeps_code'] = sub(s, RST_BODY, RST_BODY.replace('            code = 0;\n', ''))
    wrong['samples_while_rst_high'] = sub(s, GATE, '            begin\n')
    wrong['slow_output_1p3tr'] = sub(s, ', 0.0, tr, tr);', ', 0.0, 1.3*tr, 1.3*tr);', count=6)
    wrong['hardcoded_vss_0'] = body_param(s, 'vss', '0.0')
    wrong['hardcoded_vref_0p9'] = body_param(s, 'vref', '0.9')
    wrong['hardcoded_vdd_0p9'] = body_param(s, 'vdd', '0.9')
    wrong['hardcoded_vth_0p45'] = body_param(s, 'vth', '0.45')
    wrong['hardcoded_tr_200p'] = sub(s, ', 0.0, tr, tr);', ', 0.0, 200p, 200p);', count=6)
    if GOLD is not None:
        wrong['original_v4_343_gold'] = original_gold()
    correct['alt_compute_then_delay'] = compute_then_delay(s)
    correct['alt_three_module_hierarchy'] = HIERARCHY
    correct['alt_fast_output'] = sub(s, ', 0.0, tr, tr);', ', 0.0, 0.2*tr, 0.2*tr);', count=6)
    correct['alt_delayed_within_tr'] = sub(s, ', 0.0, tr, tr);', ', 0.2*tr, 0.8*tr, 0.8*tr);', count=6)
    return wrong, correct


def valid_pulse(s):
    s = declare(s, '    real t_off;      // end of the fixed-width valid pulse\n')
    s = sub(s, '            valid_q = 0;\n        end\n\n        // Asynchronous',
            '            valid_q = 0;\n            t_off = 1.0;\n        end\n\n'
            '        // Fixed-width valid pulse.\n        @(timer(t_off))\n            valid_q = 0;\n\n        // Asynchronous')
    s = sub(s, PUB, '                valid_q = s2_valid;\n'
                    '                if (s2_valid) begin\n'
                    '                    code = 4*k2 + f2;\n'
                    '                    t_off = $abstime + 5n;\n'
                    '                end\n')
    return s


def live_input_residue(s):
    """The v4:343 gold behavior: residue from the live input and the held coarse code."""
    s = declare(s, '    real live;       // residue of the live input with the held coarse code\n')
    s = sub(s, '        span = vref - vss;\n',
            '        span = vref - vss;\n'
            '        live = V(vin);\n'
            '        if (live < vss) live = vss;\n'
            '        if (live > vref) live = vref;\n'
            '        live = 0.5*(vss + vref) + 4.0*(live - (vss + (k1 + 0.5)*0.25*span));\n'
            '        if (live < vss) live = vss;\n'
            '        if (live > vref) live = vref;\n'
            '        if (V(rst) > vth) live = vss;\n')
    s = sub(s, F2, F2.replace('(res >=', '(live >='))
    return sub(s, 'V(residue_dbg) <+ transition(res, 0.0, tr, tr);', 'V(residue_dbg) <+ live;')


def track_while_clock_high(s):
    """Stage 1 tracks vin while clk is high after a sample edge and holds at the falling edge."""
    s = declare(s, '    integer tracking;  // 1 while stage 1 tracks vin\n')
    s = sub(s, '            valid_q = 0;\n        end\n\n        // Asynchronous', '            valid_q = 0;\n'
            '            tracking = 0;\n        end\n\n        // Asynchronous')
    s = sub(s, '            valid_q = 0;\n        end\n\n        // Each', '            valid_q = 0;\n'
            '            tracking = 0;\n        end\n\n        // Each')
    s = sub(s, '        @(initial_step) begin\n', '        if (tracking) begin\n'
            '            x = V(vin);\n' + CLAMP.replace(' ' * 20, ' ' * 12) +
            K1.replace(' ' * 20, ' ' * 12) +
            '            ' + RES + '\n        end\n\n        @(initial_step) begin\n')
    s = sub(s, STAGE1, TAKE + '                if (s1_new)\n                    tracking = 1;\n')
    s = sub(s, '        V(code_3)', '        @(cross(V(clk) - vth, -1, 1p))\n            tracking = 0;\n\n        V(code_3)')
    return sub(s, 'V(residue_dbg) <+ transition(res, 0.0, tr, tr);', 'V(residue_dbg) <+ res;')


def synchronous_reset(s):
    s = sub(s, s[s.index('        // Asynchronous clear'):s.index('        // Each clock edge')], '')
    return sub(s, GATE, '            if (V(rst) > vth) begin\n'
                        '                x = vss;\n                res = vss;\n                k1 = 0;\n'
                        '                s1_new = 0;\n                s2_valid = 0;\n                code = 0;\n'
                        '                valid_q = 0;\n'
                        '            end else begin\n')


def compute_then_delay(s):
    """Bin-edge form: the whole code at the sample edge, then two registers; residue vss + 4*(x - vss) - k*span."""
    s = declare(s, '    integer c0, c1, v0, v1;   // code and tag of the newest and the older sample\n')
    s = sub(s, '            valid_q = 0;\n        end\n\n        // Asynchronous', '            valid_q = 0;\n'
            '            v0 = 0;\n            v1 = 0;\n            c0 = 0;\n            c1 = 0;\n        end\n\n        // Asynchronous')
    s = sub(s, '            valid_q = 0;\n        end\n\n        // Each', '            valid_q = 0;\n'
            '            v0 = 0;\n            v1 = 0;\n        end\n\n        // Each')
    start = s.index(PUB)
    end = s.index(STAGE1) + len(STAGE1)
    s = s[:start] + ('                valid_q = v1;\n'
                     '                if (v1)\n'
                     '                    code = c1;\n'
                     '                v1 = v0;\n'
                     '                c1 = c0;\n'
                     '                v0 = V(valid_i) > vth;\n'
                     '                if (v0) begin\n'
                     '                    x = V(vin);\n' + CLAMP +
                     '                    c0 = floor(16.0*(x - vss)/span);\n'
                     '                    if (c0 > 15) c0 = 15;\n'
                     '                    k1 = c0/4;\n'
                     '                    res = vss + 4.0*(x - vss) - k1*span;\n'
                     '                end\n') + s[end:]
    return s


def original_gold():
    """The five released v4:343 gold modules under a wrapper with the new module name."""
    parts = ['`include "constants.vams"\n`include "disciplines.vams"\n']
    for name in ('stage1_quantizer', 'residue_amp', 'stage2_quantizer', 'code_aligner', 'pipeline_adc_top'):
        text = (GOLD / f'{name}.va').read_text()
        parts.append('\n'.join(line for line in text.splitlines() if not line.startswith('`include')) + '\n')
    parts.append('''
module pipeline_adc_two_stage(vin, clk, rst, valid_i, code_3, code_2, code_1, code_0, valid_o, residue_dbg);
    input vin, clk, rst, valid_i;
    output code_3, code_2, code_1, code_0, valid_o, residue_dbg;
    electrical vin, clk, rst, valid_i, code_3, code_2, code_1, code_0, valid_o, residue_dbg;
    parameter real vdd = 0.9;
    parameter real vss = 0.0;
    parameter real vref = 0.9;
    parameter real vth = 0.45;
    parameter real tr = 200p;
    pipeline_adc_top #(.vdd(vdd), .vss(vss), .vref(vref), .vth(vth), .tr(tr))
        XTOP(vin, clk, rst, valid_i, code_3, code_2, code_1, code_0, valid_o, residue_dbg);
endmodule
''')
    return ''.join(parts)


HIERARCHY = '''`include "constants.vams"
`include "disciplines.vams"

// Stage 1: holds the sample, its coarse code and its residue until the next sample or reset.
module r09_stage1(vin, clk, rst, valid_i, b1, b0, s1v, res_o);
    input vin, clk, rst, valid_i;
    output b1, b0, s1v, res_o;
    electrical vin, clk, rst, valid_i, b1, b0, s1v, res_o;
    parameter real vdd = 0.9;
    parameter real vss = 0.0;
    parameter real vref = 0.9;
    parameter real vth = 0.45;
    parameter real tr = 200p;
    real span, x, res;
    integer k, fresh;

    analog begin
        span = vref - vss;
        @(initial_step) begin
            x = vss;
            res = vss;
            k = 0;
            fresh = 0;
        end
        @(cross(V(rst) - vth, +1, 1p)) begin
            x = vss;
            res = vss;
            k = 0;
            fresh = 0;
        end
        @(cross(V(clk) - vth, +1, 1p)) begin
            if (V(rst) < vth) begin
                fresh = V(valid_i) > vth;
                if (fresh) begin
                    x = V(vin);
                    if (x < vss) x = vss;
                    if (x > vref) x = vref;
                    k = 0;
                    if (x >= vss + 0.25*span) k = 1;
                    if (x >= vss + 0.50*span) k = 2;
                    if (x >= vss + 0.75*span) k = 3;
                    res = 0.5*(vss + vref) + 4.0*(x - (vss + (k + 0.5)*0.25*span));
                end
            end
        end
        V(b1) <+ transition((k >= 2) ? vdd : vss, 0.0, tr, tr);
        V(b0) <+ transition((k == 1 || k == 3) ? vdd : vss, 0.0, tr, tr);
        V(s1v) <+ transition(fresh ? vdd : vss, 0.0, tr, tr);
        V(res_o) <+ transition(res, 0.0, tr, tr);
    end
endmodule

// Stage 2: decides the fine code from the residue node at the clock edge after a sample.
module r09_stage2(res_i, clk, rst, s1v, f1, f0, s2v);
    input res_i, clk, rst, s1v;
    output f1, f0, s2v;
    electrical res_i, clk, rst, s1v, f1, f0, s2v;
    parameter real vdd = 0.9;
    parameter real vss = 0.0;
    parameter real vref = 0.9;
    parameter real vth = 0.45;
    parameter real tr = 200p;
    real span, vmid;
    integer f, fresh;

    analog begin
        span = vref - vss;
        vmid = 0.5*(vdd + vss);
        @(initial_step) begin
            f = 0;
            fresh = 0;
        end
        @(cross(V(rst) - vth, +1, 1p)) begin
            f = 0;
            fresh = 0;
        end
        @(cross(V(clk) - vth, +1, 1p)) begin
            if (V(rst) < vth) begin
                fresh = V(s1v) > vmid;
                if (fresh) begin
                    f = 0;
                    if (V(res_i) >= vss + 0.25*span) f = 1;
                    if (V(res_i) >= vss + 0.50*span) f = 2;
                    if (V(res_i) >= vss + 0.75*span) f = 3;
                end
            end
        end
        V(f1) <+ transition((f >= 2) ? vdd : vss, 0.0, tr, tr);
        V(f0) <+ transition((f == 1 || f == 3) ? vdd : vss, 0.0, tr, tr);
        V(s2v) <+ transition(fresh ? vdd : vss, 0.0, tr, tr);
    end
endmodule

// Aligner: keeps the coarse code of the sample in stage 2 and publishes it with the fine code.
module r09_align(clk, rst, b1, b0, s1v, f1, f0, s2v, code_3, code_2, code_1, code_0, valid_o);
    input clk, rst, b1, b0, s1v, f1, f0, s2v;
    output code_3, code_2, code_1, code_0, valid_o;
    electrical clk, rst, b1, b0, s1v, f1, f0, s2v, code_3, code_2, code_1, code_0, valid_o;
    parameter real vdd = 0.9;
    parameter real vss = 0.0;
    parameter real vth = 0.45;
    parameter real tr = 200p;
    real vmid;
    integer k_hold, code, valid_q;

    analog begin
        vmid = 0.5*(vdd + vss);
        @(initial_step) begin
            k_hold = 0;
            code = 0;
            valid_q = 0;
        end
        @(cross(V(rst) - vth, +1, 1p)) begin
            k_hold = 0;
            code = 0;
            valid_q = 0;
        end
        @(cross(V(clk) - vth, +1, 1p)) begin
            if (V(rst) < vth) begin
                valid_q = V(s2v) > vmid;
                if (valid_q)
                    code = 4*k_hold + 2*(V(f1) > vmid) + (V(f0) > vmid);
                if (V(s1v) > vmid)
                    k_hold = 2*(V(b1) > vmid) + (V(b0) > vmid);
            end
        end
        V(code_3) <+ transition(((code >> 3) & 1) ? vdd : vss, 0.0, tr, tr);
        V(code_2) <+ transition(((code >> 2) & 1) ? vdd : vss, 0.0, tr, tr);
        V(code_1) <+ transition(((code >> 1) & 1) ? vdd : vss, 0.0, tr, tr);
        V(code_0) <+ transition((code & 1) ? vdd : vss, 0.0, tr, tr);
        V(valid_o) <+ transition(valid_q ? vdd : vss, 0.0, tr, tr);
    end
endmodule

module pipeline_adc_two_stage(vin, clk, rst, valid_i, code_3, code_2, code_1, code_0, valid_o, residue_dbg);
    input vin, clk, rst, valid_i;
    output code_3, code_2, code_1, code_0, valid_o, residue_dbg;
    electrical vin, clk, rst, valid_i, code_3, code_2, code_1, code_0, valid_o, residue_dbg;
    electrical b1, b0, s1v, f1, f0, s2v;
    parameter real vdd = 0.9;
    parameter real vss = 0.0 from [-0.5:0.5];
    parameter real vref = 0.9;
    parameter real vth = 0.45 from [0.2:0.7];
    parameter real tr = 200p from [10p:1n];

    r09_stage1 #(.vdd(vdd), .vss(vss), .vref(vref), .vth(vth), .tr(tr))
        XS1(vin, clk, rst, valid_i, b1, b0, s1v, residue_dbg);
    r09_stage2 #(.vdd(vdd), .vss(vss), .vref(vref), .vth(vth), .tr(tr))
        XS2(residue_dbg, clk, rst, s1v, f1, f0, s2v);
    r09_align #(.vdd(vdd), .vss(vss), .vth(vth), .tr(tr))
        XAL(clk, rst, b1, b0, s1v, f1, f0, s2v, code_3, code_2, code_1, code_0, valid_o);
endmodule
'''


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
            assert text != SOLUTION or group == 'correct', name
            (out / group / f'{name}.va').write_text(text)
    print(f'{len(wrong)} wrong, {len(correct)} correct candidates in {out}')


if __name__ == '__main__':
    main()
