#!/usr/bin/env python3
"""Author calibration: the verifier must accept correct variants and reject
typical wrong ones. Each mutant makes one change to the reference solution;
where the reference repeats a statement for both lanes or both slots, the
change is applied to the stated number of identical occurrences.

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
OUT = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs/uwb-tx-vabench-20261022'
           '/tasks/uwb-spec-branch-scheduler/calibration')

# name, old text, new text, occurrences, requirement it violates
MUTANTS = [
    ('steal_busy_slot',
     'la_slot = -1; conf = 1; t_conf_off = $abstime + t_conf;   // drop the symbol',
     's0_br = k; s0_st = 1; s0_pend = 1; la_slot = 0;', 1,
     'S3 (d) drop instead of powering a third branch'),
    ('warm_restarts_precharge',
     'la_slot = 0; s0_pend = s0_pend + 1;             // warm: already powered',
     'la_slot = 0; s0_pend = s0_pend + 1; s0_st = 1;', 1,
     'S3 (a) a warm grant keeps the branch state'),
    ('no_take_over',
     'end else if (s0_st == 5 && s0_pend == 0) begin', 'end else if (0) begin', 2,
     'S3 (c) take over an idle HOLD'),
    ('no_hold',
     's0_st = 5;                                  // tail done', 's0_st = 0; s0_br = -1;', 1,
     'S5 HOLD after TAIL'),
    ('hold_ignores_tpre',
     't_wait = t_hold - n_pre * delta0;', 't_wait = t_hold;', 1,
     'S5 idle HOLD lasts max(0, t_hold - n_pre*delta0)'),
    ('fixed_tail',
     '$abstime + t_tail;', '$abstime + 150p;', 4,
     'S5 TAIL lasts t_tail'),
    ('fixed_conflict_width',
     't_conf_off = $abstime + t_conf;', 't_conf_off = $abstime + 200p;', 2,
     'S6 conflict pulse width t_conf'),
    ('drop_without_conflict',
     'conf = 1; t_conf_off', 'conf = 0; t_conf_off', 2,
     'S6 conflict pulse at a dropped request'),
    ('reset_keeps_branches',
     's0_br = -1; s0_st = 0; s0_pend = 0; s0_nact = 0;\n            s1_br = -1; s1_st = 0; s1_pend = 0; s1_nact = 0;\n'
     '            la_slot = -1;',
     'la_slot = -1;', 1,
     'S7 reset turns every branch off'),
    ('requests_during_reset',
     'if (V(rst) < vth) begin\n                k = 4', 'if (1) begin\n                k = 4', 2,
     'S7 requests are ignored while rst is high'),
    ('nsup_scaled_by_vdd',
     'V(nsup) <+ transition(1.0 * (', 'V(nsup) <+ transition(vdd * (', 1,
     'S2 nsup is 1 V per powered branch'),
    ('rel_during_precharge',
     'V(rel[i]) <+ transition(((s0_st >= 2 && s0_br == i) || (s1_st >= 2 && s1_br == i)) * vdd, 0, tr);',
     'V(rel[i]) <+ transition(((s0_st >= 1 && s0_br == i) || (s1_st >= 1 && s1_br == i)) * vdd, 0, tr);', 1,
     'S2 rel is low in PRECHARGE (release at the window start)'),
]


def run(candidate, out):
    start = time.monotonic()
    p = subprocess.run([sys.executable, '-B', str(TASK / 'tests/verify.py'), '--candidate', str(candidate),
                        '--output', str(out)], capture_output=True, text=True)
    wall = time.monotonic() - start
    res = json.loads((out / 'results.json').read_text()) if (out / 'results.json').is_file() else {}
    fails = [r for r in res.get('checks', []) if not r['passed']]
    failed_cases = sorted({r['case'].split('/')[0] for r in fails})
    return res, fails, failed_cases, wall, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append')
    ap.add_argument('--output', default=str(OUT))
    a = ap.parse_args()
    root = Path(a.output)
    summary = []
    for name, cand in [('reference', SOLUTION), ('alternative', ALT)]:
        if a.only and name not in a.only:
            continue
        res, fails, cases, wall, _ = run(cand, root / name)
        summary.append(dict(sample=name, expected=1, score=res.get('score'), ok=res.get('score') == 1,
                            candidate_sha256=res.get('candidate_sha256'), wall_s=round(wall, 1),
                            checks=len(res.get('checks', [])), failed_checks=len(fails), errors=res.get('errors'),
                            first_failure=(fails[0]['case'] + ': ' + fails[0]['specification']) if fails else None))
    src = SOLUTION.read_text()
    for name, old, new, count, req in MUTANTS:
        if a.only and name not in a.only:
            continue
        assert src.count(old) == count, f'{name}: pattern occurs {src.count(old)} times, expected {count}'
        work = root / name
        work.mkdir(parents=True, exist_ok=True)
        cand = work / 'circuit.va'
        cand.write_text(src.replace(old, new))
        res, fails, cases, wall, _ = run(cand, work / 'out')
        summary.append(dict(sample=name, violates=req, expected=0, score=res.get('score'), ok=res.get('score') == 0,
                            candidate_sha256=res.get('candidate_sha256'), wall_s=round(wall, 1),
                            checks=len(res.get('checks', [])), failed_checks=len(fails), failed_cases=cases,
                            errors=res.get('errors'),
                            first_failure=(fails[0]['case'] + ': ' + fails[0]['specification']) if fails else None))
    for s in summary:
        print(f"{'OK ' if s['ok'] else 'BAD'} {s['sample']:26s} score={s['score']} {s['wall_s']:6.1f}s "
              f"{s.get('failed_cases') or ''} {s.get('first_failure') or ''}")
    root.mkdir(parents=True, exist_ok=True)
    (root / 'calibration.json').write_text(json.dumps(summary, indent=1) + '\n')
    return 0 if all(s['ok'] for s in summary) else 1


if __name__ == '__main__':
    sys.exit(main())
