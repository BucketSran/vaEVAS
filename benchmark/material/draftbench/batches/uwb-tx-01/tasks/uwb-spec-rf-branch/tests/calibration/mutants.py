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
import time

TASK = Path(__file__).resolve().parents[2]
SOLUTION = TASK / 'solution/circuit.va'
ALT = Path(__file__).resolve().parent / 'alternative.va'
sys.path[:0] = [str(TASK / 'environment/starter/testbench'), str(TASK / 'tests')]
import contract  # noqa: E402
from final_cases import final_cases  # noqa: E402

# name, old text, new text, requirement it violates
MUTANTS = [
    ('amp_tau_is_t99', 'tau_a = t99_amp / ln(100);', 'tau_a = t99_amp;', 'S2 amplitude time constant t99/ln 100'),
    ('freq_settles_with_t99_amp', 'tau_f = t99_freq / ln(100);', 'tau_f = t99_amp / ln(100);',
     'S2 frequency settles with t99_freq'),
    ('phase_not_integrated',
     'phase = phi0 + 2 * `M_PI * f_rf * (u + df_start * tau_f * (1 - exp(-u / tau_f)));',
     'phase = phi0 + 2 * `M_PI * f_rf * (1 + df_start * exp(-u / tau_f)) * u;',
     'S2 phase is the integral of the frequency'),
    ('phi0_dropped_while_settling',
     'phase = phi0 + 2 * `M_PI * f_rf * (u + df_start',
     'phase = 2 * `M_PI * f_rf * (u + df_start', 'S2 phase starts at phi0'),
    ('a_ro_ignored', 'amp = a_ro * (1 - exp(-u / tau_a));', 'amp = 1.0 * (1 - exp(-u / tau_a));',
     'S2 amplitude a_ro'),
    ('global_phase', 'phase = phi0 + 2 * `M_PI * f_rf * (u + df_start',
     'phase = phi0 + 2 * `M_PI * f_rf * ($abstime + df_start', 'S3 phase local to the release'),
    ('no_cold_restart', 'osc = 1; t_rel = $abstime;', 'osc = 1; if (t_rel == 0) t_rel = $abstime;',
     'S3 every release restarts at phi0'),
    ('oscillates_in_precharge', '@(cross(V(rel) - vth, +1)) begin', '@(cross(V(pwr) - vth, +1)) begin',
     'S1 no oscillation before the release'),
    ('release_ignores_pwr', 'if (V(pwr) > vth) begin', 'if (1) begin', 'S1 release only while pwr is high'),
    ('rel_fall_does_not_stop', '@(cross(V(rel) - vth, -1) or cross(V(pwr) - vth, -1))',
     '@(cross(V(pwr) - vth, -1))', 'S4 rel falling stops the branch'),
    ('pwr_fall_does_not_stop', '@(cross(V(rel) - vth, -1) or cross(V(pwr) - vth, -1))',
     '@(cross(V(rel) - vth, -1))', 'S4 pwr falling stops the branch'),
]


def run(candidate, out):
    start = time.monotonic()
    p = subprocess.run([sys.executable, '-B', str(TASK / 'tests/verify.py'), '--candidate', str(candidate),
                        '--output', str(out)], capture_output=True, text=True)
    wall = time.monotonic() - start
    res = json.loads((out / 'results.json').read_text()) if (out / 'results.json').is_file() else {}
    fails = [r for r in res.get('checks', []) if not r['passed']]
    return res, fails, wall, p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', action='append')
    ap.add_argument('--output', default='/tmp/uwb-rf-branch-calibration')
    a = ap.parse_args()
    root = Path(a.output)
    cases = contract.public_cases() + final_cases()
    bad = [f"{c['name']}: {x}" for c in cases for x in contract.domain_problems(c)]
    assert not bad, f'cases outside the S5 domain: {bad}'
    summary = []
    for name, cand in [('reference', SOLUTION), ('alternative', ALT)]:
        if a.only and name not in a.only:
            continue
        res, fails, wall, _ = run(cand, root / name)
        score = res.get('score')
        summary.append(dict(sample=name, expected=1, score=score, ok=score == 1, wall_s=round(wall, 2),
                            candidate_sha256=res.get('candidate_sha256'),
                            checks=len(res.get('checks', [])), errors=res.get('errors'),
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
        res, fails, wall, _ = run(cand, work / 'out')
        score = res.get('score')
        failed_cases = sorted({f['case'] for f in fails})
        summary.append(dict(sample=name, violates=req, expected=0, score=score, ok=score == 0,
                            wall_s=round(wall, 2), candidate_sha256=res.get('candidate_sha256'),
                            failed_checks=len(fails), failed_case_instances=failed_cases,
                            errors=res.get('errors'),
                            first_failure=(fails[0]['case'] + ': ' + fails[0]['specification']) if fails else None))
    for s in summary:
        print(f"{'OK ' if s['ok'] else 'BAD'} {s['sample']:28s} score={s['score']} {s['wall_s']:6.1f} s "
              f"{s.get('first_failure') or ''}")
    (root / 'calibration.json').write_text(json.dumps(summary, indent=1) + '\n')
    return 0 if all(s['ok'] for s in summary) else 1


if __name__ == '__main__':
    sys.exit(main())
