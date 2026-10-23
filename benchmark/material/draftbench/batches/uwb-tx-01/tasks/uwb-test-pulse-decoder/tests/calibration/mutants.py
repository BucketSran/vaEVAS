#!/usr/bin/env python3
"""Author calibration: the verifier must accept correct variants and reject
typical wrong ones. Each mutant changes one thing in the reference solution
(one or two text edits).

  python3 tests/calibration/mutants.py [--only NAME ...] [--output DIR]
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

TASK = Path(__file__).resolve().parents[2]
SOLUTION = TASK / 'solution/circuit.va'
ALT = Path(__file__).resolve().parent / 'alternative.va'
# author runs are kept in the repository's run record, not in the package
DEFAULT_OUT = TASK.parents[6] / 'runs/uwb-tx-vabench-20261022/tasks' / TASK.name / 'calibration'

RST = 'open = 0; hiv = 0; p_prev = 0; sym_out = 0; err_out = 0; sv = 0;\n            t_close = 1;'

# name, [(old text, new text, occurrences)], requirement it violates
MUTANTS = [
    ('absolute_position', [('d = ((p - p_prev) % 8 + 8) % 8;', 'd = p % 8;', 1)],
     'S4 differential decode D = (P - P_prev) mod 8'),
    ('no_gray', [('sym_next = 8 * (d ^ (d >> 1)) + (fi ^ (fi >> 1));', 'sym_next = 8 * d + fi;', 1)],
     'S4 Gray coding of D and F'),
    ('frequency_by_peaks', [('fest = (nw - 1) / (2 * (zl - zf));', 'fest = (nw - 1) / (zl - zf);', 1)],
     'S3 f = (N - 1)/(2 span): each crossing taken as a full period (2x)'),
    ('no_offgrid_err', [('bad = (abs(e) > tol_pos * delta) || (p > 7);', 'bad = (p > 7);', 1)],
     'S5 err for a start off the grid by more than tol_pos*delta'),
    ('nominal_delta', [('delta = t_clk / 16;', 'delta = 1 / (16 * 672e6);', 1)],
     'S2 delta from the measured clk period, not the nominal 672 MHz'),
    ('strobe_every_crossing', [('hiv = 0; t_last = $abstime; t_close = $abstime + t_gap;',
                                'hiv = 0; t_last = $abstime; t_close = $abstime + 1p;', 1)],
     'S1/S6 one strobe per pulse: gaps shorter than t_gap are bridged'),
    ('frame_before_ts', [('frame = ck + floor((ts + delta / 2 - ck) / t_clk) * t_clk;',
                          'frame = ck + floor((ts - ck) / t_clk) * t_clk;', 1)],
     'S2 frame edge at or before ts + delta/2 (an early P = 0 is not P = 16)'),
    ('hold_pprev_on_err', [('p_prev = p % 8;', 'if (!bad) p_prev = p % 8;', 1)],
     'S4 P_prev = P mod 8 after every pulse, erroneous or not'),
    ('reset_keeps_pprev', [(RST, RST.replace('p_prev = 0; ', ''), 1)],
     'S7 reset returns P_prev to 0'),
    ('strobe_at_decision', [('t_out = t_last + t_lat;', 't_out = t_last + t_gap;', 1)],
     'S6 outputs t_lat after the last exceedance'),
    ('whole_pulse_window', [('lo = tc - n_width * delta / 4;', 'lo = t_first;', 1),
                            ('hi = tc + n_width * delta / 4;', 'hi = t_last;', 1)],
     'S3 frequency window tc +- n_width*delta/4'),
    ('fixed_strobe_width', [('t_off = $abstime + t_pw;', 't_off = $abstime + 200p;', 2)],
     'S6 sym_valid high for t_pw'),
    ('positive_only', [('@(cross(v - v_det, +1) or cross(v + v_det, -1))', '@(cross(v - v_det, +1))', 1),
                       ('@(cross(v - v_det, -1) or cross(v + v_det, +1))', '@(cross(v - v_det, -1))', 1)],
     'S1 exceedance of |v|, both polarities'),
]


def run(candidate, out):
    start = time.monotonic()
    p = subprocess.run([sys.executable, '-B', str(TASK / 'tests/verify.py'), '--candidate', str(candidate),
                        '--output', str(out)], capture_output=True, text=True)
    wall = time.monotonic() - start
    res = json.loads((out / 'results.json').read_text()) if (out / 'results.json').is_file() else {}
    fails = [r for r in res.get('checks', []) if not r['passed']]
    return res, fails, wall, p


def summary_row(name, res, fails, wall):
    return dict(sample=name, score=res.get('score'), status=res.get('status'), errors=res.get('errors'),
                wall_s=round(wall, 1), candidate_sha256=res.get('candidate_sha256'),
                failed_checks=len(fails), failed_cases=sorted({r['case'] for r in fails}),
                first_failure=(fails[0]['case'] + ': ' + fails[0]['specification']) if fails else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append')
    ap.add_argument('--output', default=str(DEFAULT_OUT))
    a = ap.parse_args()
    root = Path(a.output)
    summary = []
    for name, cand in [('reference', SOLUTION), ('alternative', ALT)]:
        if a.only and name not in a.only:
            continue
        res, fails, wall, _ = run(cand, root / name)
        row = summary_row(name, res, fails, wall)
        summary.append(dict(row, expected=1, ok=row['score'] == 1))
    src = SOLUTION.read_text()
    for name, edits, req in MUTANTS:
        if a.only and name not in a.only:
            continue
        text = src
        for old, new, count in edits:
            assert text.count(old) == count, f'{name}: pattern occurs {text.count(old)} times, expected {count}'
            text = text.replace(old, new)
        work = root / name
        work.mkdir(parents=True, exist_ok=True)
        cand = work / 'circuit.va'
        cand.write_text(text)
        res, fails, wall, _ = run(cand, work / 'out')
        row = summary_row(name, res, fails, wall)
        summary.append(dict(row, violates=req, expected=0, ok=row['score'] == 0))
    for s in summary:
        print(f"{'OK ' if s['ok'] else 'BAD'} {s['sample']:24s} score={s['score']} {s['wall_s']:6.1f} s "
              f"{','.join(s['failed_cases'])}  {s.get('first_failure') or ''}")
    (root / 'calibration.json').write_text(json.dumps(summary, indent=1) + '\n')
    return 0 if all(s['ok'] for s in summary) else 1


if __name__ == '__main__':
    sys.exit(main())
