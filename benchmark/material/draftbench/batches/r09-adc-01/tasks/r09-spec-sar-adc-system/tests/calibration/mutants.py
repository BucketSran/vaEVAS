#!/usr/bin/env python3
"""Write the calibration candidates of r09-spec-sar-adc-system into an empty directory.

    python3 -B mutants.py <output-directory>

wrong/<name>.va must be rejected and correct/<name>.va must be accepted by the
checker in ../verify.py on ../cases.json. Each candidate is ../../solution/circuit.va
with checked text changes in one or more modules; original_v4_342_gold is the five
released v4:342 gold modules, read from benchmark/material/historyref when this file
runs inside the repository (their module names and ports are those of this task).
comparator_cross_latch is the comparator of the reference before p0-fix-e: its state
follows cross() events only, so a difference that leaves an exact 0 does not update it.
expected.json holds the rejection matrix.
"""
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
SOLUTION = (HERE.parent.parent / 'solution/circuit.va').read_text()
GOLD = None
for parent in HERE.parents:
    candidate = parent / 'benchmark/material/historyref/v4/release/benchmarkv4-r53/tasks/342-sar-adc-system-4b'
    if (candidate / 'evaluator/solution').is_dir():
        GOLD = candidate / 'evaluator/solution'
        break

LEVEL = 'level = vss + (vref - vss)*(8*b3 + 4*b2 + 2*b1 + b0)/16.0;'
CDAC_INIT = ('        @(initial_step) begin\n'
             '            b3 = V(bit_3) > vth;\n'
             '            b2 = V(bit_2) > vth;\n'
             '            b1 = V(bit_1) > vth;\n'
             '            b0 = V(bit_0) > vth;\n'
             '        end\n')
CMP = ('        @(cross(V(sample_i) - V(dac_i), 0, 1p));\n'
       '        high = V(sample_i) >= V(dac_i);\n')
CMP_LATCH = ('        @(initial_step) high = V(sample_i) >= V(dac_i);\n'
             '        @(cross(V(sample_i) - V(dac_i), +1, 1p)) high = 1;\n'
             '        @(cross(V(sample_i) - V(dac_i), -1, 1p)) high = 0;\n')
SH_RST = '        @(cross(V(rst) - vth, +1, 1p)) held = vss;\n'
SH_IF = '            if (V(rst) < vth && V(sample_en) > vth)\n                held = V(vin);\n'
SH_CLK = '        @(cross(V(clk) - vth, +1, 1p)) begin\n' + SH_IF + '        end\n'
CT_RST = ('        @(cross(V(rst) - vth, +1, 1p)) begin\n'
          '            phase = 0;\n'
          '            trial = 0;\n'
          '            result = 0;\n'
          '            en = 0;\n'
          '            fin = 0;\n'
          '        end\n')
SAMPLE_EDGE = ('                if (phase == 1) begin\n'
               '                    en = 0;\n'
               '                    trial = 8;\n'
               '                    bitpos = 3;\n'
               '                    phase = 2;\n'
               '                end else if (phase == 2) begin\n')
DECIDE = '                    if (V(cmp_i) > vth)\n'
NEXT = '                        trial = result + (1 << bitpos);\n'
LAST = ('                        trial = result;\n'
        '                        fin = 1;\n'
        '                        phase = 0;\n'
        '                    end\n'
        '                end\n')
START = ('        @(cross(V(start) - vth, +1, 1p)) begin\n'
         '            if (V(rst) < vth) begin\n'
         '                phase = 1;\n'
         '                trial = 0;\n'
         '                result = 0;\n'
         '                en = 1;\n'
         '                fin = 0;\n'
         '            end\n'
         '        end\n')
CT_CLK_HEAD = '        @(cross(V(clk) - vth, +1, 1p)) begin\n            if (V(rst) < vth) begin\n                if (phase == 1)'
CT_DECL = '    integer fin;\n'
TRANS = ', 0.0, tr, tr);'


def sub(text, old, new, count=1):
    assert text.count(old) == count, (old[:60], text.count(old))
    return text.replace(old, new)


def modules(text):
    """Split into module chunks (the include lines stay with the first)."""
    parts = re.split(r'(?m)^(?=module )', text)
    return parts[0], parts[1:]


def body_param(text, name, value):
    """A parameter replaced by a literal inside every analog block (declarations and instance overrides keep it)."""
    head, mods = modules(text)
    out = [head]
    n = 0
    for mod in mods:
        if '    analog begin\n' in mod:
            a, b = mod.split('    analog begin\n', 1)
            b, k = re.subn(rf'\b{name}\b', value, b)
            n += k
            mod = a + '    analog begin\n' + b
        out.append(mod)
    assert n > 0, name
    return ''.join(out)


def candidates():
    s = SOLUTION
    w, c = {}, {}
    # DAC
    w['dac_span_reading'] = sub(s, LEVEL, 'level = vss + vref*(8*b3 + 4*b2 + 2*b1 + b0)/16.0;')
    w['dac_old_public_formula'] = sub(s, LEVEL, 'level = vref*(8*b3 + 4*b2 + 2*b1 + b0)/16.0;')
    w['dac_divisor_15'] = sub(s, LEVEL, 'level = vss + (vref - vss)*(8*b3 + 4*b2 + 2*b1 + b0)/15.0;')
    w['cdac_bit_order_reversed'] = sub(s, LEVEL, 'level = vss + (vref - vss)*(8*b0 + 4*b1 + 2*b2 + b3)/16.0;')
    w['cdac_initial_bits_zero'] = sub(s, CDAC_INIT, '        @(initial_step) begin\n            b3 = 0;\n            b2 = 0;\n'
                                                    '            b1 = 0;\n            b0 = 0;\n        end\n')
    # comparator
    w['comparator_polarity'] = sub(s, CMP, '        @(cross(V(sample_i) - V(dac_i), 0, 1p));\n'
                                           '        high = V(sample_i) < V(dac_i);\n')
    w['comparator_reads_live_vin'] = sub(s, '        XCMP(held, dac, cmp);', '        XCMP(vin, dac, cmp);')
    w['comparator_initial_high'] = sub(s, CMP, CMP_LATCH.replace('@(initial_step) high = V(sample_i) >= V(dac_i);',
                                                                 '@(initial_step) high = 1;'))
    w['comparator_cross_latch'] = sub(s, CMP, CMP_LATCH)
    # sample-and-hold
    w['sh_ignores_sample_en'] = sub(s, SH_IF, '            if (V(rst) < vth)\n                held = V(vin);\n')
    w['sh_samples_in_reset'] = sub(s, SH_IF, '            if (V(sample_en) > vth)\n                held = V(vin);\n')
    w['sh_samples_at_sample_en_rise'] = sub(s, SH_CLK, '        @(cross(V(sample_en) - vth, +1, 1p)) begin\n'
                                                       '            if (V(rst) < vth)\n'
                                                       '                held = V(vin);\n'
                                                       '        end\n')
    w['sample_clamped_at_vss'] = sub(s, SH_IF, SH_IF + '            if (held < vss) held = vss;\n')
    w['sh_reset_does_not_clear'] = sub(s, SH_RST, '')
    # controller: sequence
    w['sample_one_edge_late'] = sub(s, SAMPLE_EDGE, '                if (phase == 1) begin\n'
                                                    '                    phase = 4;\n'
                                                    '                end else if (phase == 4) begin\n'
                                                    + SAMPLE_EDGE[SAMPLE_EDGE.index('                    en = 0;'):])
    w['first_decision_at_sample_edge'] = sub(s, SAMPLE_EDGE, SAMPLE_EDGE.replace(
        '                end else if (phase == 2) begin\n', '                end\n                if (phase == 2) begin\n'))
    w['idle_edge_before_decisions'] = sub(s, SAMPLE_EDGE, SAMPLE_EDGE.replace(
        '                    phase = 2;\n                end else if (phase == 2) begin\n',
        '                    phase = 5;\n                end else if (phase == 5) begin\n'
        '                    phase = 2;\n                end else if (phase == 2) begin\n'))
    w['keep_every_trial_bit'] = sub(s, DECIDE, '                    if (1)\n')
    w['next_trial_from_trial'] = sub(s, NEXT, '                        trial = trial + (1 << bitpos);\n')
    w['decided_bits_lost'] = sub(s, NEXT, '                        trial = (1 << bitpos);\n')
    # controller: outputs and monitors
    w['code_only_at_done'] = code_only_at_done(s)
    w['done_kept_at_start'] = sub(s, START, START.replace('                fin = 0;\n', ''))
    w['done_one_clock'] = sub(s, LAST, LAST + '                else if (phase == 0)\n                    fin = 0;\n')
    w['dac_keeps_final_at_start'] = sub(s, START, START.replace('                trial = 0;\n', ''))
    w['dac_shows_last_trial_after_done'] = sub(s, LAST, LAST.replace('                        trial = result;\n', ''))
    w['trial_lags_one_edge'] = trial_lags(s)
    # controller: start and clock
    w['busy_start_ignored'] = sub(s, START, START.replace('            if (V(rst) < vth) begin\n',
                                                          '            if (V(rst) < vth && phase == 0) begin\n'))
    w['level_sensitive_start'] = sub(s, LAST, LAST + '                else if (phase == 0 && V(start) > vth) begin\n'
                                                     '                    phase = 1;\n'
                                                     '                    en = 1;\n'
                                                     '                    trial = 0;\n'
                                                     '                    result = 0;\n'
                                                     '                    fin = 0;\n'
                                                     '                end\n')
    w['falling_edge_clock'] = sub(s, '@(cross(V(clk) - vth, +1, 1p))', '@(cross(V(clk) - vth, -1, 1p))', count=2)
    # reset
    w['synchronous_reset'] = synchronous_reset(s)
    w['reset_keeps_conversion'] = sub(s, CT_RST, '        @(cross(V(rst) - vth, +1, 1p)) begin\n'
                                                 '            result = 0;\n'
                                                 '            fin = 0;\n'
                                                 '        end\n')
    w['start_latched_in_reset'] = start_latched(s)
    w['sample_en_cleared_at_next_edge'] = sample_en_cleared_at_next_edge(s)
    # output timing and parameters
    w['slow_output_1p3tr'] = sub(s, TRANS, ', 0.0, 1.3*tr, 1.3*tr);', count=15)
    w['hardcoded_vss_0'] = body_param(s, 'vss', '0.0')
    w['hardcoded_vref_0p9'] = body_param(s, 'vref', '0.9')
    w['hardcoded_vdd_0p9'] = body_param(s, 'vdd', '0.9')
    w['hardcoded_vth_0p45'] = body_param(s, 'vth', '0.45')
    w['hardcoded_tr_200p'] = sub(s, TRANS, ', 0.0, 200p, 200p);', count=15)
    if GOLD is not None:
        w['original_v4_342_gold'] = original_gold()
    c['alt_gold_style_continuous'] = gold_style(s)
    c['alt_mask_pointer_controller'] = mask_pointer(s)
    c['alt_fast_output'] = sub(s, TRANS, ', 0.0, 0.2*tr, 0.2*tr);', count=15)
    c['alt_delayed_within_tr'] = sub(s, TRANS, ', 0.2*tr, 0.8*tr, 0.8*tr);', count=15)
    c['margin_arrival_1p2tr'] = sub(s, TRANS, ', 0.0, 1.2*tr, 1.2*tr);', count=15)
    c['alt_fast_sample_en'] = sub(s, '        V(sample_en) <+ transition(en ? vdd : vss, 0.0, tr, tr);\n',
                                  '        V(sample_en) <+ transition(en ? vdd : vss, 0.0, 0.1*tr, 0.1*tr);\n')
    return w, c


def code_only_at_done(s):
    s = sub(s, CT_DECL, CT_DECL + '    integer shown;      // result shown on the code outputs\n')
    s = sub(s, '            fin = 0;\n        end\n\n        // Reset has priority',
            '            fin = 0;\n            shown = 0;\n        end\n\n        // Reset has priority')
    s = sub(s, CT_RST, CT_RST.replace('            fin = 0;\n', '            fin = 0;\n            shown = 0;\n'))
    s = sub(s, LAST, LAST.replace('                        fin = 1;\n', '                        fin = 1;\n'
                                                                       '                        shown = result;\n'))
    for k in (3, 2, 1):
        s = sub(s, f'V(code_{k}) <+ transition(((result >> {k}) & 1)', f'V(code_{k}) <+ transition(((shown >> {k}) & 1)')
    return sub(s, 'V(code_0) <+ transition((result & 1)', 'V(code_0) <+ transition((shown & 1)')


def trial_lags(s):
    s = sub(s, CT_DECL, CT_DECL + '    integer shown;      // trial code of the previous clock edge\n')
    s = sub(s, '            fin = 0;\n        end\n\n        // Reset has priority',
            '            fin = 0;\n            shown = 0;\n        end\n\n        // Reset has priority')
    s = sub(s, CT_CLK_HEAD, '        @(cross(V(clk) - vth, +1, 1p)) begin\n            if (V(rst) < vth) begin\n'
                            '                shown = trial;\n                if (phase == 1)')
    for k in (3, 2, 1):
        s = sub(s, f'V(trial_{k}) <+ transition(((trial >> {k}) & 1)', f'V(trial_{k}) <+ transition(((shown >> {k}) & 1)')
    return sub(s, 'V(trial_0) <+ transition((trial & 1)', 'V(trial_0) <+ transition((shown & 1)')


def synchronous_reset(s):
    s = sub(s, SH_RST, '')
    s = sub(s, SH_IF, '            if (V(rst) > vth)\n                held = vss;\n'
                      '            else if (V(sample_en) > vth)\n                held = V(vin);\n')
    s = sub(s, CT_RST, '')
    return sub(s, CT_CLK_HEAD, '        @(cross(V(clk) - vth, +1, 1p)) begin\n'
                               '            if (V(rst) > vth) begin\n'
                               '                phase = 0;\n                trial = 0;\n                result = 0;\n'
                               '                en = 0;\n                fin = 0;\n'
                               '            end else begin\n                if (phase == 1)')


def start_latched(s):
    s = sub(s, CT_DECL, CT_DECL + '    integer pend;       // start request seen while rst was high\n')
    s = sub(s, '            fin = 0;\n        end\n\n        // Reset has priority',
            '            fin = 0;\n            pend = 0;\n        end\n\n        // Reset has priority')
    s = sub(s, START, START.replace('                fin = 0;\n            end\n        end\n',
                                    '                fin = 0;\n            end else\n                pend = 1;\n        end\n'
                                    '        @(cross(V(rst) - vth, -1, 1p)) begin\n'
                                    '            if (pend) begin\n'
                                    '                pend = 0;\n                phase = 1;\n                trial = 0;\n'
                                    '                result = 0;\n                en = 1;\n                fin = 0;\n'
                                    '            end\n        end\n'))
    return s


def sample_en_cleared_at_next_edge(s):
    """A reset leaves sample_en as it is; the next clock edge, with rst high or low, clears it."""
    s = sub(s, CT_RST, CT_RST.replace('            en = 0;\n', ''))
    return sub(s, CT_CLK_HEAD, '        @(cross(V(clk) - vth, +1, 1p)) begin\n            if (phase == 0)\n'
                               '                en = 0;\n            if (V(rst) < vth) begin\n                if (phase == 1)')


def gold_style(s):
    """Comparator and DAC evaluated continuously, as in the v4:342 gold, with the task's endpoint formula."""
    s = sub(s, CMP, '')
    s = sub(s, '        V(cmp_o) <+ transition(high ? vdd : vss, 0.0, tr, tr);',
            '        V(cmp_o) <+ transition((V(sample_i) >= V(dac_i)) ? vdd : vss, 0.0, tr, tr);')
    head = s[s.index('        @(initial_step) begin\n            b3 = V(bit_3) > vth;'):s.index('        level = vss')]
    s = sub(s, head, '        b3 = V(bit_3) > vth;\n        b2 = V(bit_2) > vth;\n        b1 = V(bit_1) > vth;\n'
                     '        b0 = V(bit_0) > vth;\n')
    return s


def mask_pointer(s):
    """The bit position kept as a one-hot mask instead of an index."""
    s = sub(s, SAMPLE_EDGE, SAMPLE_EDGE.replace('                    bitpos = 3;\n', '                    bitpos = 8;\n'))
    s = sub(s, '                        result = trial - (1 << bitpos);\n', '                        result = trial - bitpos;\n')
    s = sub(s, '                    if (bitpos > 0) begin\n                        bitpos = bitpos - 1;\n' + NEXT,
            '                    if (bitpos > 1) begin\n                        bitpos = bitpos/2;\n'
            '                        trial = result + bitpos;\n')
    return sub(s, '    integer bitpos;     // bit decided at the next clock edge while converting\n',
               '    integer bitpos;     // one-hot mask of the bit decided at the next clock edge\n')


def original_gold():
    parts = ['`include "constants.vams"\n`include "disciplines.vams"\n']
    for name in ('binary_weighted_cdac', 'sar_comparator', 'sample_hold', 'sar_controller', 'sar_adc_top'):
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
