#!/usr/bin/env python3
"""Author calibration: the verifier must accept correct variants and reject
typical wrong ones. Each mutant changes one thing in the reference solution.

  python3 tests/calibration/mutants.py [--only NAME ...] [--output DIR] [--results DIR]

Every sample runs the full final verifier (public and final cases). With
--results, results/reference.json and results/calibration.json are written.
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
BACKEND_NOTE = 'legacy EVAS 0.8.7, interim; declared backend evas pending (issue 229)'

# name, old text, new text, requirement it violates
MUTANTS = [
    ('inverted_decision', 'if (cnt <= target)', 'if (cnt >= target)',
     'S3 a count above the target clears the trial bit'),
    ('equal_count_clears_bit', 'if (cnt <= target)', 'if (cnt < target)',
     'S3 a count equal to the target keeps the trial bit'),
    ('window_one_period_short', 'if (nref >= n_win) begin', 'if (nref >= n_win - 1) begin',
     'S2 the window lasts n_win reference periods'),
    ('settle_ignores_n_settle', 'if (nref >= n_settle) begin', 'if (nref >= 1) begin',
     'S2 the window opens at the n_settle-th reference edge'),
    ('target_ignores_ratio', 'target = n_win * ratio;', 'target = n_win * 14;',
     'S3 target = n_win * ratio'),
    ('verify_ignores_tol', 'if (cnt - target <= tol && target - cnt <= tol)', 'if (cnt == target)',
     'S4 done when |count - target| <= tol'),
    ('no_lost_watchdog', 'if (lost > n_lost) begin', 'if (0 && lost > n_lost) begin',
     'S6 lost-reference watchdog'),
    ('lost_shows_trial_code', '                    trial = code_q;\n', '                    code_q = trial;\n',
     'S6 a watchdog fail shows the last kept code, not the untested trial code'),
    ('watchdog_not_cleared_by_ref', '            lost = 0;\n            if (phase == 1) begin',
     '            if (phase == 1) begin', 'S6 roclk edges are counted since the last reference edge'),
    ('reset_keeps_code', 'phase = 0; verify = 0; code_q = code_init; trial = code_init;',
     'phase = 0; verify = 0;', 'S7 reset shows code_init'),
    ('cal_start_during_reset', 'if (V(rst) < vth) begin', 'if (1) begin',
     'S7 cal_start is ignored while rst is high'),
    ('no_restart_while_busy', 'if (V(rst) < vth) begin', 'if (V(rst) < vth && !busy_q) begin',
     'S5 a cal_start during a search restarts it'),
    ('done_kept_on_restart', 'busy_q = 1; done_q = 0; fail_q = 0; verify = 0;', 'busy_q = 1; fail_q = 0; verify = 0;',
     'S5 a new cal_start clears done'),
    ('fixed_output_delay', '@(timer(t_out)) begin', '@(timer(t_out - t_cq + 10p)) begin',
     'S8 outputs change t_cq after the deciding edge'),
    ('no_code_init_at_start', 'out_code = code_init; out_done = 0;', 'out_code = 0; out_done = 0;',
     'S7 code_init is shown before calibration'),
]


def run(candidate, out):
    start = time.monotonic()
    subprocess.run([sys.executable, '-B', str(TASK / 'tests/verify.py'), '--candidate', str(candidate),
                    '--output', str(out)], capture_output=True, text=True)
    wall = time.monotonic() - start
    res = json.loads((out / 'results.json').read_text()) if (out / 'results.json').is_file() else {}
    checks = res.get('checks', [])
    cases = {}
    for r in checks:
        name = r['case'].split('/')[0]
        cases.setdefault(name, dict(checks=0, passed=0))
        cases[name]['checks'] += 1
        cases[name]['passed'] += bool(r['passed'])
    for name in cases:
        f = out / name / 'wall_s.txt'
        cases[name]['wall_s'] = float(f.read_text()) if f.is_file() else None
    fails = [r for r in checks if not r['passed']]
    return dict(score=res.get('score'), status=res.get('status'), errors=res.get('errors', []),
                candidate_sha256=res.get('candidate_sha256'), checks=len(checks),
                passed=len(checks) - len(fails), wall_s=round(wall, 1), cases=cases,
                failing_cases=sorted({r['case'].split('/')[0] for r in fails}),
                first_failure=(fails[0]['case'] + ': ' + fails[0]['specification']) if fails else None)


def identity(out):
    for f in sorted(out.glob('*/sim/evas_identity.json')):
        return json.loads(f.read_text())
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append')
    ap.add_argument('--output', default='/tmp/uwb-ro-cal-calibration')
    ap.add_argument('--results', help='write reference.json and calibration.json here')
    a = ap.parse_args()
    root = Path(a.output).resolve()
    summary = []
    for name, cand in [('reference', SOLUTION), ('alternative', ALT)]:
        if a.only and name not in a.only:
            continue
        r = run(cand, root / name)
        summary.append(dict(sample=name, expected=1, ok=r['score'] == 1, **r))
    src = SOLUTION.read_text()
    for name, old, new, req in MUTANTS:
        if a.only and name not in a.only:
            continue
        assert src.count(old) == 1, f'{name}: pattern must occur once'
        work = root / name
        work.mkdir(parents=True, exist_ok=True)
        cand = work / 'circuit.va'
        cand.write_text(src.replace(old, new))
        r = run(cand, work / 'out')
        summary.append(dict(sample=name, violates=req, change=[old, new], expected=0, ok=r['score'] == 0, **r))
    for s in summary:
        print(f"{'OK ' if s['ok'] else 'BAD'} {s['sample']:28s} score={s['score']} {s['wall_s']:6.1f} s "
              f"{s['passed']}/{s['checks']} {s.get('first_failure') or ''}")
    (root / 'calibration.json').write_text(json.dumps(summary, indent=1) + '\n')
    if a.results:
        sys.path[:0] = [str(TASK / 'environment/starter/testbench'), str(TASK / 'tests')]
        import contract  # noqa: E402
        from final_cases import final_cases  # noqa: E402
        protocol = json.loads((TASK / 'environment/starter/testbench/protocol.json').read_text())
        cases = dict(public=[c['name'] for c in contract.public_cases()],
                     final=[c['name'] for c in final_cases()])
        common = dict(task='uwb-spec-ro-frequency-cal', backend=BACKEND_NOTE,
                      backend_identity=identity(root / 'reference') or identity(root / 'alternative'),
                      maxstep_s=protocol['maxstep_s'], crossing_time_tolerance_s=protocol['crossing_time_tolerance_s'],
                      date=time.strftime('%Y-%m-%d'), cases=cases)
        res = Path(a.results)
        ref = next((s for s in summary if s['sample'] == 'reference'), None)
        if ref:
            (res / 'reference.json').write_text(json.dumps(dict(common, sample='solution/circuit.va', **{
                k: ref[k] for k in ('score', 'status', 'errors', 'candidate_sha256', 'checks', 'passed',
                                    'wall_s', 'cases')}), indent=1) + '\n')
        (res / 'calibration.json').write_text(json.dumps(dict(common, samples=[
            {k: s.get(k) for k in ('sample', 'violates', 'change', 'expected', 'score', 'ok', 'candidate_sha256',
                                   'checks', 'passed', 'wall_s', 'failing_cases', 'first_failure', 'errors')}
            for s in summary]), indent=1) + '\n')
    return 0 if all(s['ok'] for s in summary) else 1


if __name__ == '__main__':
    sys.exit(main())
