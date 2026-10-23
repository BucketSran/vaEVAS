#!/usr/bin/env python3
"""Author calibration: the verifier must accept correct module sets and reject
typical wrong ones.

Each sample is a full module directory: the reference solution with
ro_scheduler8.va replaced by the alternative or by one edited version.
Partial fixes start from the faulty starter; over-fixes start from the
repaired scheduler and change one more thing.

  python3 tests/calibration/mutants.py [--only NAME ...] [--output DIR] [--case NAME ...]
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

TASK = Path(__file__).resolve().parents[2]
SOLUTION = TASK / 'solution/modules'
STARTER = TASK / 'environment/starter/modules'
ALT = Path(__file__).resolve().parent / 'alternative.va'
SCHED = 'ro_scheduler8.va'

WARM_A0 = 'la_slot = 0; s0_pend = s0_pend + 1;             // warm: already powered'
WARM_A1 = 'la_slot = 1; s1_pend = s1_pend + 1;\n'
WARM_B0 = 'lb_slot = 0; s0_pend = s0_pend + 1;             // warm: already powered'
WARM_B1 = 'lb_slot = 1; s1_pend = s1_pend + 1;\n'


def fault(line):
    """The starter's fault on one warm-grant line: the branch goes back to PRECHARGE."""
    slot = '0' if 's0_pend' in line else '1'
    head = line.split(';')[0] + f'; s{slot}_pend = s{slot}_pend + 1;'
    return head + f' s{slot}_st = 1;' + ('\n' if line.endswith('\n') else '')


# name, edits [(old, new, expected count)] on the reference scheduler, requirement violated
MUTANTS = [
    ('fix_lane_a_only', [(WARM_B0, fault(WARM_B0), 1), (WARM_B1, fault(WARM_B1), 1)],
     'C4 warm grant: lane-b requests still restart the precharge'),
    ('fix_slot0_only', [(WARM_A1, fault(WARM_A1), 1), (WARM_B1, fault(WARM_B1), 1)],
     'C4 warm grant: a branch held in supply slot 1 still restarts'),
    ('warm_path_removed', [('if (s0_st != 0 && s0_br == k) begin', 'if (0 && s0_st != 0 && s0_br == k) begin', 2),
                           ('end else if (s1_st != 0 && s1_br == k) begin',
                            'end else if (0 && s1_st != 0 && s1_br == k) begin', 2)],
     'C4 warm grant: a request for a powered branch takes another supply and precharges'),
    ('warm_no_pending', [(WARM_A0, 'la_slot = 0;', 1), (WARM_A1, 'la_slot = 1;\n', 1),
                         (WARM_B0, 'lb_slot = 0;', 1), (WARM_B1, 'lb_slot = 1;\n', 1)],
     'C4 HOLD: a branch with a warm-granted pulse waiting must not time out'),
    ('never_off', [('s0_due = $abstime + t_wait;             // idle hold, may end\n'
                    '                    if (t_wait <= 0) begin s0_st = 0; s0_br = -1; end', 's0_due = 1.0;', 1),
                   ('s1_due = $abstime + t_wait;             // idle hold, may end\n'
                    '                    if (t_wait <= 0) begin s1_st = 0; s1_br = -1; end', 's1_due = 1.0;', 1)],
     'C4 HOLD timeout: an idle branch turns off after max(0, t_hold - n_pre*delta)'),
    ('hold_ignores_tpre', [('t_wait = t_hold - n_pre * delta0;', 't_wait = t_hold;', 1)],
     'C4 HOLD timeout counts from the TAIL end and is shortened by T_pre'),
    ('always_take_slot', [('la_slot = -1; conf = 1; t_conf_off = $abstime + t_conf;   // drop the symbol',
                           's0_br = k; s0_st = 1; s0_pend = 1; la_slot = 0;', 1),
                          ('lb_slot = -1; conf = 1; t_conf_off = $abstime + t_conf;   // drop the symbol',
                           's0_br = k; s0_st = 1; s0_pend = 1; lb_slot = 0;', 1)],
     'C4 drop: with both supplies busy the request is dropped and conflict pulses'),
    ('warm_goes_active', [(WARM_A0, 'la_slot = 0; s0_pend = s0_pend + 1; s0_st = 3;', 1),
                          (WARM_A1, 'la_slot = 1; s1_pend = s1_pend + 1; s1_st = 3;\n', 1),
                          (WARM_B0, 'lb_slot = 0; s0_pend = s0_pend + 1; s0_st = 3;', 1),
                          (WARM_B1, 'lb_slot = 1; s1_pend = s1_pend + 1; s1_st = 3;\n', 1)],
     'C4 warm grant: the branch keeps its state; a precharging branch is not released early'),
    ('warm_excludes_precharge', [('if (s0_st != 0 && s0_br == k) begin', 'if (s0_st >= 3 && s0_br == k) begin', 2),
                                 ('end else if (s1_st != 0 && s1_br == k) begin',
                                  'end else if (s1_st >= 3 && s1_br == k) begin', 2)],
     'C4 warm grant applies to every powered state, PRECHARGE included'),
    ('no_preempt', [('end else if (s0_st == 5 && s0_pend == 0) begin',
                     'end else if (0 && s0_st == 5 && s0_pend == 0) begin', 2),
                    ('end else if (s1_st == 5 && s1_pend == 0) begin',
                     'end else if (0 && s1_st == 5 && s1_pend == 0) begin', 2)],
     'C4 preemption: an idle HOLD gives its supply to a new branch'),
]


def run(cand_dir, out, cases):
    cmd = [sys.executable, '-B', str(TASK / 'tests/verify.py'), '--candidate', str(cand_dir), '--output', str(out)]
    for c in cases or []:
        cmd += ['--case', c]
    start = time.monotonic()
    p = subprocess.run(cmd, capture_output=True, text=True)
    wall = time.monotonic() - start
    (out / 'verify.log').write_text(p.stdout + '\n---STDERR---\n' + p.stderr)
    res = json.loads((out / 'results.json').read_text()) if (out / 'results.json').is_file() else {}
    fails = [r for r in res.get('checks', []) if not r['passed']]
    timing = {}
    if (out / 'timing.json').is_file():
        timing = json.loads((out / 'timing.json').read_text())['wall_s_per_case']
    return dict(score=res.get('score'), status=res.get('status'), errors=res.get('errors'),
                candidate_sha256=res.get('candidate_sha256'), wall_s=round(wall, 1), wall_s_per_case=timing,
                failed_cases=sorted({r['case'] for r in fails}),
                first_failure=(fails[0]['case'] + ': ' + fails[0]['specification'] + ' -> ' + fails[0]['value'][:160])
                if fails else None)


def module_dir(root, name, scheduler_text=None, scheduler_file=None, base=SOLUTION):
    d = root / name / 'modules'
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(base, d)
    if scheduler_file is not None:
        shutil.copyfile(scheduler_file, d / SCHED)
    if scheduler_text is not None:
        (d / SCHED).write_text(scheduler_text)
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append')
    ap.add_argument('--case', action='append')
    ap.add_argument('--output', default='/tmp/uwb-chain-calibration')
    a = ap.parse_args()
    root = Path(a.output)
    root.mkdir(parents=True, exist_ok=True)
    summary = []
    samples = [('reference', 1, 'reference solution', dict(base=SOLUTION)),
               ('alternative', 1, 'different organization of the repaired scheduler', dict(scheduler_file=ALT)),
               ('faulty_starter', 0, 'C4 warm grant: the supplied fault', dict(base=STARTER))]
    for name, want, note, kw in samples:
        if a.only and name not in a.only:
            continue
        d = module_dir(root, name, **kw)
        r = run(d, root / name / 'out', a.case)
        summary.append(dict(sample=name, expected=want, ok=r['score'] == want, note=note, **r))
    src = (SOLUTION / SCHED).read_text()
    for name, edits, req in MUTANTS:
        if a.only and name not in a.only:
            continue
        text = src
        for old, new, count in edits:
            assert text.count(old) == count, f'{name}: pattern occurs {text.count(old)} times, expected {count}'
            text = text.replace(old, new)
        d = module_dir(root, name, scheduler_text=text)
        r = run(d, root / name / 'out', a.case)
        summary.append(dict(sample=name, expected=0, ok=r['score'] == 0, violates=req, **r))
    for s in summary:
        print(f"{'OK ' if s['ok'] else 'BAD'} {s['sample']:20s} score={s['score']} wall={s['wall_s']} s "
              f"failed={s['failed_cases']} {s.get('first_failure') or ''}"[:300])
    (root / 'calibration.json').write_text(json.dumps(summary, indent=1) + '\n')
    return 0 if all(s['ok'] for s in summary) else 1


if __name__ == '__main__':
    sys.exit(main())
