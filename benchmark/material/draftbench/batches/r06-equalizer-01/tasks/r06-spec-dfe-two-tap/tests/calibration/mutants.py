#!/usr/bin/env python3
"""Write the calibration candidates of r06-spec-dfe-two-tap into an empty directory.

    python3 -B mutants.py <output-directory>

wrong/<name>.va must be rejected and correct/<name>.va must be accepted by the
checker in ../verify.py on ../cases.json. Each candidate is ../../solution/circuit.va
with checked text changes; alt_modules is a three-module organization of the same
behavior, and original_v4_354_gold is the four released v4:354 gold modules, read
from benchmark/material/historyref when this file runs inside the repository (its
top module name and ports are those of this task). expected.json holds the
rejection matrix.
"""
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
SOLUTION = (HERE.parent.parent / 'solution/circuit.va').read_text()
GOLD = None
for parent in HERE.parents:
    candidate = parent / 'benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/354-dfe-receiver-2tap'
    if (candidate / 'evaluator/solution').is_dir():
        GOLD = candidate / 'evaluator/solution'
        break

CLEAR = ('            h1 = 0;\n'
         '            h2 = 0;\n'
         '            fb = 0.0;\n'
         '            slicer = 0.0;\n'
         '            level = vss;\n')
RST = '        @(cross(V(rst) - vth, +1)) begin\n' + CLEAR + '        end\n'
TAPS = ('                k1 = (V(tap1_1) > vth ? 2 : 0) + (V(tap1_0) > vth ? 1 : 0);\n'
        '                k2 = (V(tap2_1) > vth ? 2 : 0) + (V(tap2_0) > vth ? 1 : 0);\n')
FB = '                fb = tap_lsb * (k1 * h1 + k2 * h2);\n'
SLICE = '                slicer = V(vin) - fb;\n'
DECIDE = '                d = (slicer >= vcm) ? 1 : -1;\n'
SHIFT = '                h2 = h1;\n                h1 = d;\n'
CLK = '        @(cross(V(clk) - vth, +1)) begin\n            if (V(rst) <= vth) begin\n'
DECL = '    real level;          // decision output level\n'
OUT_FB = '        V(fb_metric) <+ transition(fb, 0.0, tr, tr);\n'
OUT_DBG = '        V(slicer_in_dbg) <+ transition(slicer, 0.0, tr, tr);\n'
TRANS = ', 0.0, tr, tr);'


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
    # history encoding and empty slots (user decision A, 2026-10-28)
    w['empty_history_low'] = sub(s, '            h1 = 0;\n            h2 = 0;\n',
                                 '            h1 = -1;\n            h2 = -1;\n', count=2)
    w['empty_history_high'] = sub(s, '            h1 = 0;\n            h2 = 0;\n',
                                  '            h1 = 1;\n            h2 = 1;\n', count=2)
    w['unipolar_history'] = sub(s, FB, '                fb = tap_lsb * (k1 * (h1 > 0) + k2 * (h2 > 0));\n')
    w['empty_second_slot_low'] = sub(s, FB, '                fb = tap_lsb * (k1 * h1 + k2 * (h2 == 0 ? -1 : h2));\n')
    # feedback sign, tap order and code bits
    w['feedback_added'] = sub(s, SLICE, '                slicer = V(vin) + fb;\n')
    w['tap_order_swapped'] = sub(s, FB, '                fb = tap_lsb * (k2 * h1 + k1 * h2);\n')
    w['second_tap_ignored'] = sub(s, FB, '                fb = tap_lsb * (k1 * h1);\n')
    w['tap_bits_swapped'] = sub(s, TAPS, TAPS.replace('? 2 : 0) + (V(tap1_0) > vth ? 1', '? 1 : 0) + (V(tap1_0) > vth ? 2')
                                .replace('? 2 : 0) + (V(tap2_0) > vth ? 1', '? 1 : 0) + (V(tap2_0) > vth ? 2'))
    w['no_feedback'] = sub(s, FB, '                fb = 0.0;\n')
    # what the history holds and when it shifts
    w['input_sign_as_history'] = sub(s, SHIFT, '                h2 = h1;\n                h1 = (V(vin) >= vcm) ? 1 : -1;\n')
    w['shift_before_feedback'] = sub(sub(s, SHIFT, '                h1 = d;\n'), FB, '                h2 = h1;\n' + FB)
    w['history_one_decision_late'] = history_late(s)
    w['raw_current_decision_in_feedback'] = sub(
        s, FB, '                fb = tap_lsb * (k1 * ((V(vin) >= vcm) ? 1 : -1) + k2 * h1);\n')
    # the decision itself
    w['decision_on_raw_input'] = sub(s, DECIDE, '                d = (V(vin) >= vcm) ? 1 : -1;\n')
    w['slicer_compares_with_vth'] = sub(s, DECIDE, '                d = (slicer >= vth) ? 1 : -1;\n')
    w['decision_polarity'] = sub(s, DECIDE, '                d = (slicer >= vcm) ? -1 : 1;\n')
    # what the metrics report
    w['fb_metric_reports_next_feedback'] = report_next(s)
    w['live_metrics'] = live_metrics(s)
    w['slicer_dbg_follows_vin'] = dbg_follows_vin(s)
    # when the taps are read
    w['taps_one_decision_old'] = taps_old(s)
    w['taps_read_only_at_reset'] = taps_at_reset(s)
    # reset
    w['synchronous_reset'] = sub(sub(s, '        // Asynchronous clear: both history slots become empty.\n' + RST, ''),
                                 CLK, '        @(cross(V(clk) - vth, +1)) begin\n            if (V(rst) > vth) begin\n'
                                 + CLEAR.replace('            ', '                ')
                                 + '            end else begin\n')
    w['reset_keeps_history'] = sub(s, RST, RST.replace('            h1 = 0;\n            h2 = 0;\n', ''))
    w['reset_clears_h1_only'] = sub(s, RST, RST.replace('            h2 = 0;\n', ''))
    w['decisions_during_reset'] = sub(s, CLK, '        @(cross(V(clk) - vth, +1)) begin\n            begin\n')
    w['cleared_dbg_at_vss'] = sub(s, '            slicer = 0.0;\n', '            slicer = vss;\n', count=2)
    w['first_decision_after_reset_skipped'] = first_skipped(s)
    w['initial_decision_high'] = sub(s, '            level = vss;\n        end\n\n        // Asynchronous',
                                     '            level = vdd;\n        end\n\n        // Asynchronous')
    w['falling_edge_clock'] = sub(s, '@(cross(V(clk) - vth, +1))', '@(cross(V(clk) - vth, -1))')
    w['clk_deglitch_0p6n'] = clk_deglitch(s)
    # output timing and parameters
    w['slow_output_1p3tr'] = sub(s, TRANS, ', 0.0, 1.3*tr, 1.3*tr);', count=3)
    w['hardcoded_vdd_0p9'] = body_param(s, 'vdd', '0.9')
    w['hardcoded_vss_0'] = body_param(s, 'vss', '0.0')
    w['hardcoded_vcm_0p45'] = body_param(s, 'vcm', '0.45')
    w['hardcoded_vth_0p45'] = body_param(s, 'vth', '0.45')
    w['hardcoded_tap_lsb_20m'] = body_param(s, 'tap_lsb', '20e-3')
    w['hardcoded_tr_200p'] = sub(s, TRANS, ', 0.0, 200p, 200p);', count=3)
    w['tr_floor_100p'] = sub(s, TRANS, ', 0.0, max(tr, 100p), max(tr, 100p));', count=3)
    w['decision_floor_0v'] = sub(s, '        V(decision) <+ transition(level, 0.0, tr, tr);\n',
                                 '        V(decision) <+ transition(max(level, 0.0), 0.0, tr, tr);\n')
    if GOLD is not None:
        w['original_v4_354_gold'] = original_gold()
    c['alt_valid_count'] = valid_count(s)
    c['alt_modules'] = MODULES
    c['alt_fast_output'] = sub(s, TRANS, ', 0.0, 0.2*tr, 0.2*tr);', count=3)
    c['alt_delayed_within_tr'] = sub(s, TRANS, ', 0.2*tr, 0.8*tr, 0.8*tr);', count=3)
    c['margin_arrival_1p2tr'] = sub(s, TRANS, ', 0.0, 1.2*tr, 1.2*tr);', count=3)
    return w, c


def history_late(s):
    """An extra register stage: the feedback uses decisions n-2 and n-3."""
    s = sub(s, '    integer h1, h2;', '    integer h1, h2, h3;')
    s = sub(s, '            h2 = 0;\n', '            h2 = 0;\n            h3 = 0;\n', count=2)
    s = sub(s, FB, '                fb = tap_lsb * (k1 * h2 + k2 * h3);\n')
    return sub(s, SHIFT, '                h3 = h2;\n' + SHIFT)


def report_next(s):
    """fb_metric shows the feedback of the next decision, from the shifted history."""
    s = sub(s, DECL, DECL + '    real shown;          // value on fb_metric\n')
    s = sub(s, '            fb = 0.0;\n', '            fb = 0.0;\n            shown = 0.0;\n', count=2)
    s = sub(s, SHIFT, SHIFT + '                shown = tap_lsb * (k1 * h1 + k2 * h2);\n')
    return sub(s, OUT_FB, '        V(fb_metric) <+ transition(shown, 0.0, tr, tr);\n')


def live_metrics(s):
    """Both metrics follow the live tap inputs and the shifted history; slicer_in_dbg follows vin."""
    s = sub(s, OUT_FB, '        V(fb_metric) <+ transition(tap_lsb * (((V(tap1_1) > vth ? 2 : 0) + (V(tap1_0) > vth ? 1 : 0)) * h1\n'
                       '            + ((V(tap2_1) > vth ? 2 : 0) + (V(tap2_0) > vth ? 1 : 0)) * h2), 0.0, tr, tr);\n')
    return sub(s, OUT_DBG, '        V(slicer_in_dbg) <+ V(vin) - V(fb_metric);\n')


def dbg_follows_vin(s):
    """slicer_in_dbg shows V(vin) minus the latched feedback, live in vin after a decision."""
    s = sub(s, DECL, DECL + '    real live;           // 1 after a decision, 0 after a clear\n')
    s = sub(s, '            level = vss;\n', '            level = vss;\n            live = 0.0;\n', count=2)
    s = sub(s, SHIFT, SHIFT + '                live = 1.0;\n')
    return sub(s, OUT_DBG, '        V(slicer_in_dbg) <+ live * (V(vin) - fb) + (1.0 - live) * transition(slicer, 0.0, tr, tr);\n')


def taps_old(s):
    """Codes registered at one decision are used at the next one."""
    s = sub(s, '    integer k1, k2;', '    integer k1, k2, n1, n2;')
    s = sub(s, '            h2 = 0;\n            fb = 0.0;\n            slicer = 0.0;\n            level = vss;\n        end\n\n'
               '        // Asynchronous',
            '            h2 = 0;\n            fb = 0.0;\n            slicer = 0.0;\n            level = vss;\n'
            '            n1 = 0;\n            n2 = 0;\n        end\n\n        // Asynchronous')
    return sub(s, TAPS, '                k1 = n1;\n                k2 = n2;\n'
               + TAPS.replace('k1 =', 'n1 =').replace('k2 =', 'n2 ='))


def taps_at_reset(s):
    """Codes read at t = 0 and at a rising rst crossing only."""
    s = sub(s, CLEAR, CLEAR + TAPS.replace('                ', '            '), count=2)
    return sub(s, TAPS, '')


def first_skipped(s):
    """After a reset the first rising clk crossing with rst low only re-arms the receiver."""
    s = sub(s, DECL, DECL + '    integer armed;       // 0 until one clock edge has passed after a reset\n')
    s = sub(s, '            level = vss;\n        end\n\n        // Asynchronous',
            '            level = vss;\n            armed = (V(rst) > vth) ? 0 : 1;\n        end\n\n        // Asynchronous')
    s = sub(s, RST, RST.replace('            level = vss;\n', '            level = vss;\n            armed = 0;\n'))
    return sub(s, CLK, CLK + '              if (armed == 0)\n                armed = 1;\n              else begin\n',
               ) .replace(SHIFT + '            end\n        end\n', SHIFT + '              end\n            end\n        end\n')


def clk_deglitch(s):
    """A rising clk crossing decides only after clk has been low for 0.6 ns; the contract allows 0.5 ns."""
    s = sub(s, DECL, DECL + '    real t_fall;         // time of the latest falling clk crossing\n')
    s = sub(s, '            level = vss;\n        end\n\n        // Asynchronous',
            '            level = vss;\n            t_fall = -1.0;\n        end\n\n        // Asynchronous')
    s = sub(s, '        // Decision edge:', '        @(cross(V(clk) - vth, -1))\n            t_fall = $abstime;\n\n'
            '        // Decision edge:')
    return sub(s, CLK, '        @(cross(V(clk) - vth, +1)) begin\n'
               '            if (V(rst) <= vth && $abstime - t_fall >= 600p) begin\n')


def valid_count(s):
    """Decision bits as 0/1 plus a count of the decisions since the latest reset."""
    s = sub(s, '    integer h1, h2;      // history: +1 high, -1 low, 0 no decision since the latest reset\n',
            '    integer b1, b2;      // decision bits, 1 for high\n'
            '    integer nvalid;      // decisions since the latest reset, at most 2\n')
    s = sub(s, '            h1 = 0;\n            h2 = 0;\n', '            b1 = 0;\n            b2 = 0;\n            nvalid = 0;\n',
            count=2)
    s = sub(s, FB, '                fb = tap_lsb * (k1 * (nvalid >= 1 ? 2 * b1 - 1 : 0) + k2 * (nvalid >= 2 ? 2 * b2 - 1 : 0));\n')
    return sub(s, SHIFT, '                b2 = b1;\n                b1 = (d > 0) ? 1 : 0;\n'
               '                nvalid = (nvalid < 2) ? nvalid + 1 : 2;\n')


MODULES = '''`include "constants.vams"
`include "disciplines.vams"

// Feedback summer: tap weights times the history nodes (+0.5 V high, -0.5 V low, 0 V empty).
module dfe_feedback(tap1_1, tap1_0, tap2_1, tap2_0, h1n, h2n, fbn);
    input tap1_1, tap1_0, tap2_1, tap2_0, h1n, h2n;
    output fbn;
    electrical tap1_1, tap1_0, tap2_1, tap2_0, h1n, h2n, fbn;
    parameter real vth = 0.45;
    parameter real tap_lsb = 20e-3;
    integer k1, k2, s1, s2;

    analog begin
        k1 = (V(tap1_1) > vth ? 2 : 0) + (V(tap1_0) > vth ? 1 : 0);
        k2 = (V(tap2_1) > vth ? 2 : 0) + (V(tap2_0) > vth ? 1 : 0);
        s1 = V(h1n) > 0.25 ? 1 : (V(h1n) < -0.25 ? -1 : 0);
        s2 = V(h2n) > 0.25 ? 1 : (V(h2n) < -0.25 ? -1 : 0);
        V(fbn) <+ tap_lsb * (k1 * s1 + k2 * s2);
    end
endmodule

// Slicer and decision register: the only events are clk and rst crossings.
module dfe_slice_latch(vin, clk, rst, fbn, h1n, h2n, decision, fb_metric, slicer_in_dbg);
    input vin, clk, rst, fbn;
    output h1n, h2n, decision, fb_metric, slicer_in_dbg;
    electrical vin, clk, rst, fbn, h1n, h2n, decision, fb_metric, slicer_in_dbg;
    parameter real vdd = 0.9;
    parameter real vss = 0.0;
    parameter real vcm = 0.45;
    parameter real vth = 0.45;
    parameter real tr = 200p;
    integer h1, h2, d;
    real fb, slicer, level;

    analog begin
        @(initial_step) begin
            h1 = 0;
            h2 = 0;
            fb = 0.0;
            slicer = 0.0;
            level = vss;
        end
        @(cross(V(rst) - vth, +1)) begin
            h1 = 0;
            h2 = 0;
            fb = 0.0;
            slicer = 0.0;
            level = vss;
        end
        // The history nodes still hold the old decisions at this event.
        @(cross(V(clk) - vth, +1)) begin
            if (V(rst) <= vth) begin
                fb = V(fbn);
                slicer = V(vin) - fb;
                d = (slicer >= vcm) ? 1 : -1;
                level = (d > 0) ? vdd : vss;
                h2 = h1;
                h1 = d;
            end
        end
        V(h1n) <+ transition(0.5 * h1, 0.0, tr, tr);
        V(h2n) <+ transition(0.5 * h2, 0.0, tr, tr);
        V(decision) <+ transition(level, 0.0, tr, tr);
        V(fb_metric) <+ transition(fb, 0.0, tr, tr);
        V(slicer_in_dbg) <+ transition(slicer, 0.0, tr, tr);
    end
endmodule

module dfe_rx_top(vin, clk, rst, tap1_1, tap1_0, tap2_1, tap2_0, decision, fb_metric, slicer_in_dbg);
    input vin, clk, rst, tap1_1, tap1_0, tap2_1, tap2_0;
    output decision, fb_metric, slicer_in_dbg;
    electrical vin, clk, rst, tap1_1, tap1_0, tap2_1, tap2_0, decision, fb_metric, slicer_in_dbg;
    electrical fbn, h1n, h2n;
    parameter real vdd = 0.9 from [0.5:1.5];
    parameter real vss = 0.0 from [-0.5:0.5];
    parameter real vcm = 0.45 from [0.2:0.7];
    parameter real vth = 0.45 from [0.2:0.7];
    parameter real tap_lsb = 20e-3 from [5e-3:50e-3];
    parameter real tr = 200p from [10p:1n];

    dfe_feedback #(.vth(vth), .tap_lsb(tap_lsb)) xfb(tap1_1, tap1_0, tap2_1, tap2_0, h1n, h2n, fbn);
    dfe_slice_latch #(.vdd(vdd), .vss(vss), .vcm(vcm), .vth(vth), .tr(tr))
        xsl(vin, clk, rst, fbn, h1n, h2n, decision, fb_metric, slicer_in_dbg);
endmodule
'''


def original_gold():
    parts = ['`include "constants.vams"\n`include "disciplines.vams"\n']
    for name in ('slicer', 'feedback_filter', 'decision_latch', 'dfe_rx_top'):
        text = (GOLD / f'{name}.va').read_text()
        parts.append('\n' + '\n'.join(line for line in text.splitlines() if not line.startswith('`include')) + '\n')
    return ''.join(parts)


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
