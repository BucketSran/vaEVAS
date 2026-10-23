#!/usr/bin/env python3
"""Author calibration: the verifier must accept correct variants and reject
typical wrong ones. Each mutant changes one thing in the reference solution
(one or two text edits; both lanes where the mistake concerns both).

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

EN_CANCEL = ('@(timer(t_ovr_off)) ovr = 0;\n'
             '        @(cross(V(en) - vth, -1)) begin\n'
             '            act_a = 0; pre_a_q = 0; rf_a_q = 0; act_b = 0; pre_b_q = 0; rf_b_q = 0;\n'
             '        end')
F_NOW = '4 * (V(fcode[2]) > vth) + 2 * (V(fcode[1]) > vth) + (V(fcode[0]) > vth)'
RST_HEAD = '            lane = 0; pend = 0;\n            act_a = 0; pre_a_q = 0; rf_a_q = 0; act_b = 0; pre_b_q = 0; rf_b_q = 0;\n'

# name, [(old text, new text, occurrences)], requirement it violates
MUTANTS = [
    ('no_frame_delay', [('a + 16 + pend_p', 'a + pend_p', 2)],
     'S5 window starts at tap edge 16 + P (next frame)'),
    ('width_ignores_parameter', [('+ n_width;', '+ 9;', 2)], 'S5 window length n_width'),
    ('precharge_ignores_parameter', [('- n_pre;', '- 2;', 2)], 'S5 precharge length n_pre'),
    ('lane_per_latch', [('                lane = 1 - lane;\n', '', 1), ('pend = 1;', 'pend = 1; lane = 1 - lane;', 1)],
     'S4 overwritten descriptors take no lane'),
    ('lane_by_frame_parity', [('if (lane == 0) begin', 'if (fc % 2 == 0) begin', 1)],
     'S4 lanes alternate over scheduled descriptors'),
    ('no_overrun', [('ovr = 1; t_ovr_off', 't_ovr_off', 1)], 'S3 overrun pulse'),
    ('en_blocks_latch', [('            if (V(rst) < vth) begin\n                if (pend)',
                          '            if (V(rst) < vth && V(en) > vth) begin\n                if (pend)', 1)],
     'S4 en low keeps latching into the pending register'),
    ('en_low_cancels_windows', [('@(timer(t_ovr_off)) ovr = 0;', EN_CANCEL, 1)],
     'S4 en acts only at frame edges'),
    ('descriptor_read_at_frame_edge', [('f_a = pend_f;', f'f_a = {F_NOW};', 1), ('f_b = pend_f;', f'f_b = {F_NOW};', 1)],
     'S3 descriptor read at the enc_valid edge'),
    ('reset_keeps_pending', [(RST_HEAD, RST_HEAD.replace(' pend = 0;', ''), 1)], 'S7 reset discards the pending descriptor'),
    ('reset_keeps_lane', [(RST_HEAD, RST_HEAD.replace('lane = 0; ', ''), 1)], 'S7 first descriptor after reset on lane a'),
    ('reset_keeps_windows', [(RST_HEAD, '            lane = 0; pend = 0;\n', 1)], 'S7 reset clears both lanes'),
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
                failed_cases=sorted({r['case'] for r in fails}),
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
        print(f"{'OK ' if s['ok'] else 'BAD'} {s['sample']:30s} score={s['score']} {s['wall_s']:6.1f} s "
              f"{','.join(s['failed_cases'])}  {s.get('first_failure') or ''}")
    (root / 'calibration.json').write_text(json.dumps(summary, indent=1) + '\n')
    return 0 if all(s['ok'] for s in summary) else 1


if __name__ == '__main__':
    sys.exit(main())
