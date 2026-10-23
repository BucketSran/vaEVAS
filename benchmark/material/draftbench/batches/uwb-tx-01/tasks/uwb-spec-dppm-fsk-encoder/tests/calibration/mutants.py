#!/usr/bin/env python3
"""Author calibration: the verifier must accept correct variants and reject
typical wrong ones. Each mutant changes one thing in the reference solution.

  python3 tests/calibration/mutants.py [--only NAME ...] [--output DIR]
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

TASK = Path(__file__).resolve().parents[2]
SOLUTION = TASK / 'solution/circuit.va'
ALT = Path(__file__).resolve().parent / 'alternative.va'

# name, old text, new text, requirement it violates
MUTANTS = [
    ('no_gray_decode', 'd = 4 * g5 + 2 * (g5 ^ g4) + (g5 ^ g4 ^ g3);', 'd = 4 * g5 + 2 * g4 + g3;', 'S2 Gray decode'),
    ('absolute_position', 'p = (p + d) % 8;', 'p = d;', 'S2 position recursion'),
    ('capture_on_rising_edge', '@(cross(V(sym_valid) - vth, -1))', '@(cross(V(sym_valid) - vth, +1))', 'S1 capture edge'),
    ('reset_keeps_position', 'd = 0; f = 0; p = 0; d_out = 0; f_out = 0; p_out = 0; has_word = 0; ev = 0;\n            t_data = 1.0; t_ev_on = 1.0; t_ev_off = 1.0;\n        end\n        @(cross(V(sym_valid)',
     'd = 0; f = 0; d_out = 0; f_out = 0; p_out = 0; has_word = 0; ev = 0;\n            t_data = 1.0; t_ev_on = 1.0; t_ev_off = 1.0;\n        end\n        @(cross(V(sym_valid)', 'S5 reset restarts P'),
    ('reset_does_not_cancel', 'd = 0; f = 0; p = 0; d_out = 0; f_out = 0; p_out = 0; has_word = 0; ev = 0;\n            t_data = 1.0; t_ev_on = 1.0; t_ev_off = 1.0;\n        end\n        @(cross(V(sym_valid)',
     'd = 0; f = 0; p = 0; d_out = 0; f_out = 0; p_out = 0; has_word = 0; ev = 0;\n        end\n        @(cross(V(sym_valid)', 'S5 reset cancels pending updates'),
    ('one_hot_before_first_word', 'transition((has_word && f_out == i) * vdd, 0, tr)', 'transition((f_out == i) * vdd, 0, tr)', 'S2 no request before a word'),
    ('fixed_pulse_width', 't_ev_off = $abstime + t_ev + t_pw;', 't_ev_off = $abstime + t_ev + 400p;', 'S4 enc_valid width parameter'),
    ('data_without_delay', 't_data = $abstime + t_enc;', 't_data = $abstime + 1p;', 'S3 data delay t_enc'),
    # a repeated word must still give a new strobe (original SPEC 6.3)
    ('no_strobe_for_repeat', 't_ev_on = $abstime + t_ev;', 'if (d != d_out || f != f_out) t_ev_on = $abstime + t_ev;',
     'S4 strobe for every word, including repeats'),
]


def run(candidate, out):
    p = subprocess.run([sys.executable, str(TASK / 'tests/verify.py'), '--candidate', str(candidate),
                        '--output', str(out)], capture_output=True, text=True)
    res = json.loads((out / 'results.json').read_text()) if (out / 'results.json').is_file() else {}
    fails = [r for r in res.get('checks', []) if not r['passed']]
    return res.get('score'), fails, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append')
    ap.add_argument('--output', default='/tmp/uwb-encoder-calibration')
    a = ap.parse_args()
    root = Path(a.output)
    summary = []
    for name, cand in [('reference', SOLUTION), ('alternative', ALT)]:
        if a.only and name not in a.only:
            continue
        score, fails, _ = run(cand, root / name)
        summary.append(dict(sample=name, expected=1, score=score, ok=score == 1,
                            first_failure=fails[0]['specification'] if fails else None))
    src = SOLUTION.read_text()
    for name, old, new, req in MUTANTS:
        if a.only and name not in a.only:
            continue
        assert src.count(old) == 1, f'{name}: pattern must occur once'
        work = root / name
        work.mkdir(parents=True, exist_ok=True)
        cand = work / 'circuit.va'
        cand.write_text(src.replace(old, new))
        score, fails, _ = run(cand, work / 'out')
        summary.append(dict(sample=name, violates=req, expected=0, score=score, ok=score == 0,
                            first_failure=(fails[0]['case'] + ': ' + fails[0]['specification']) if fails else None))
    for s in summary:
        print(f"{'OK ' if s['ok'] else 'BAD'} {s['sample']:28s} score={s['score']} {s.get('first_failure') or ''}")
    (root / 'calibration.json').write_text(json.dumps(summary, indent=1) + '\n')
    return 0 if all(s['ok'] for s in summary) else 1


if __name__ == '__main__':
    sys.exit(main())
