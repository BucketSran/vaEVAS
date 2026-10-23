#!/usr/bin/env python3
"""Author calibration: the verifier must accept correct variants and reject
typical wrong top-level wirings. Each mutant changes one thing in the
reference solution.

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

PG = 'Xpg (ph, pos, fcode, pol, enc_valid, done, rst,'
SCH = 'Xsch (pre_a, rf_a, sel_a, pre_b, rf_b, sel_b, rst, pwr, pre, rel, gate_a, gate_b, conflict, nsup, st);'
NETS = 'electrical gate_a, gate_b, env_a, env_b;'
COPY = 'V(clk672) <+ V(ph[0]);'

# name, [(old text, new text), ...], requirement it violates
MUTANTS = [
    ('pg_enable_tied_high', [(NETS, NETS[:-1] + ', en_hi;'), (PG, PG.replace('done', 'en_hi')),
                             (COPY, COPY + '\n        V(en_hi) <+ 1.0;')],
     'S2/S4 the PG enable is done; no RF before calibration ends'),
    ('envelope_clocked_by_bclk', [('Xenva (gate_a, ph[0], env_a);', 'Xenva (gate_a, bclk, env_a);'),
                                  ('Xenvb (gate_b, ph[0], env_b);', 'Xenvb (gate_b, bclk, env_b);')],
     'S2/S4 the envelope lanes run on the frame clock ph[0] (window 9/16 of the RO period)'),
    ('lane_gates_swapped', [(SCH, SCH.replace('gate_a, gate_b, conflict', 'gate_b, gate_a, conflict'))],
     'S2 lane a/b of the scheduler drive lane a/b of the envelope and output stage'),
    ('scheduler_without_n_pre', [('uwb_ro_scheduler8 #(.n_pre(n_pre))\n        Xsch', 'uwb_ro_scheduler8\n        Xsch')],
     'S2/S5 n_pre reaches the scheduler (hold window)'),
    ('carriers_swapped', [('#(.f_rf(f0)) Xbr0', '#(.f_rf(f1)) Xbr0'), ('#(.f_rf(f1)) Xbr1', '#(.f_rf(f0)) Xbr1')],
     'S2/S4 branch k runs at f_k'),
    ('pol_not_connected', [(NETS, NETS[:-1] + ', pol_lo;'), (PG, PG.replace(' pol,', ' pol_lo,')),
                           (COPY, COPY + '\n        V(pol_lo) <+ 0.0;')],
     'S2/S4 pol is the PG polarity input'),
    ('conflict_from_overrun', [(NETS, NETS[:-1] + ', sch_conflict;'),
                               (SCH, SCH.replace('conflict, nsup', 'sch_conflict, nsup')),
                               ('sel_b, pol_b, overrun);', 'sel_b, pol_b, conflict);')],
     'S2/S5 conflict comes from the scheduler'),
    ('g_pa_not_passed', [('#(.g_pa(g_pa), .vcm(vcm))', '#(.vcm(vcm))')], 'S1/S4 pulse amplitude scales with g_pa'),
    ('done_fail_swapped', [('code, done, fail, busy);', 'code, fail, done, busy);')],
     'S2/S3 done and fail pins come from the matching calibration outputs'),
    ('clk672_from_tap8', [(COPY, 'V(clk672) <+ V(ph[8]);')], 'S2/S3 clk672 copies ph[0]'),
    ('code_init_not_passed', [('#(.n_win(n_win), .code_init(code_init))', '#(.n_win(n_win))')],
     'S1/S3 clk672 runs at code_init before calibration'),
    ('n_win_not_passed', [('#(.n_win(n_win), .code_init(code_init))', '#(.code_init(code_init))')],
     'S1/S3 the search counts over n_win reference periods'),
]


def run(candidate, out):
    start = time.monotonic()
    p = subprocess.run([sys.executable, '-B', str(TASK / 'tests/verify.py'), '--candidate', str(candidate),
                        '--output', str(out)], capture_output=True, text=True)
    wall = time.monotonic() - start
    res = json.loads((out / 'results.json').read_text()) if (out / 'results.json').is_file() else {}
    fails = [r for r in res.get('checks', []) if not r['passed']]
    cases = sorted({r['case'] for r in res.get('checks', [])})
    per_case = {c: [sum(r['passed'] for r in res['checks'] if r['case'] == c),
                    sum(1 for r in res['checks'] if r['case'] == c)] for c in cases}
    return res, fails, per_case, wall, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append')
    ap.add_argument('--output', default='/tmp/uwb-integrate-calibration')
    a = ap.parse_args()
    root = Path(a.output).resolve()
    summary = []
    for name, cand in [('reference', SOLUTION), ('alternative', ALT)]:
        if a.only and name not in a.only:
            continue
        res, fails, per_case, wall, _ = run(cand, root / name)
        summary.append(dict(sample=name, expected=1, score=res.get('score'), ok=res.get('score') == 1,
                            candidate_sha256=res.get('candidate_sha256'), wall_s=round(wall, 1),
                            passed_checks=per_case, errors=res.get('errors'),
                            first_failure=fails[0]['specification'] if fails else None))
    src = SOLUTION.read_text()
    for name, edits, req in MUTANTS:
        if a.only and name not in a.only:
            continue
        text = src
        for old, new in edits:
            assert text.count(old) == 1, f'{name}: pattern must occur once: {old!r}'
            text = text.replace(old, new)
        work = root / name
        work.mkdir(parents=True, exist_ok=True)
        cand = work / 'circuit.va'
        cand.write_text(text)
        res, fails, per_case, wall, _ = run(cand, work / 'out')
        failed_cases = sorted({r['case'] for r in fails})
        summary.append(dict(sample=name, violates=req, expected=0, score=res.get('score'), ok=res.get('score') == 0,
                            candidate_sha256=res.get('candidate_sha256'), wall_s=round(wall, 1),
                            failed_cases=failed_cases, failed_checks=len(fails), errors=res.get('errors'),
                            first_failure=(fails[0]['case'] + ': ' + fails[0]['specification']) if fails else None))
        (root / 'calibration.json').write_text(json.dumps(summary, indent=1) + '\n')
    for s in summary:
        print(f"{'OK ' if s['ok'] else 'BAD'} {s['sample']:26s} score={s['score']} {s['wall_s']:7.1f} s "
              f"{s.get('first_failure') or ''}")
    root.mkdir(parents=True, exist_ok=True)
    (root / 'calibration.json').write_text(json.dumps(summary, indent=1) + '\n')
    return 0 if all(s['ok'] for s in summary) else 1


if __name__ == '__main__':
    sys.exit(main())
