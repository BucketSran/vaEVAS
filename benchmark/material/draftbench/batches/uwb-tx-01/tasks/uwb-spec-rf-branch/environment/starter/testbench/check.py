#!/usr/bin/env python3
"""Public checks for the RF branch oscillator.

  python3 /app/testbench/check.py plan
  python3 /app/testbench/check.py run [--case NAME] [--candidate /app/circuit.va] [--output DIR]

`run` launches the simulator once per case (see README.md). Public results are
diagnostics only; they do not produce a task score.
"""
import argparse
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import contract  # noqa: E402
import uwbtask as u  # noqa: E402


def run_cases(cases, candidate, out_dir, *, final=False):
    protocol = json.loads((HERE / 'protocol.json').read_text())
    os.environ.setdefault('UWB_BACKEND', protocol['backend'])
    rows, errors = [], []
    try:
        frozen = u.freeze(Path(candidate), out_dir)
    except u.RunError as exc:
        return u.finish([], [str(exc)], out_dir, final=final)
    banned = u.preflight(frozen)
    if banned:
        rows.append(dict(case='preflight', specification='model is self-contained (Deliverable)',
                         limit='no file or process access', value=', '.join(banned), passed=False))
        return u.finish(rows, [], out_dir, final=final, candidate_sha=u.digest(frozen))
    for case in cases:
        work = out_dir / case['name']
        try:
            res = u.simulate(contract.netlist(case, frozen, HERE, contract.stop_time(case)), work,
                             timeout=protocol['timeout_s_per_case'])
            waves = u.read_rows(res['rows'])
        except (u.RunError, OSError) as exc:
            errors.append(f"{case['name']}: {exc}")
            continue
        for rep in contract.check(case, waves):
            rows += rep.rows
    return u.finish(rows, errors, out_dir, final=final, candidate_sha=u.digest(frozen))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['plan', 'run'])
    ap.add_argument('--case', action='append')
    ap.add_argument('--candidate', default='/app/circuit.va')
    ap.add_argument('--output', default='/tmp/uwb-rf-branch-public')
    a = ap.parse_args()
    cases = [c for c in contract.public_cases() if not a.case or c['name'] in a.case]
    if a.command == 'plan':
        for c in cases:
            ivs = {i['name']: [(round(x * 1e9, 4), round(y * 1e9, 4)) for x, y in contract.releases(c, i['params'])[0]]
                   for i in c['instances']}
            print(f"{c['name']}: VIN {c['vin']} V, stop {c['stop'] * 1e9:g} ns, instances "
                  f"{[(i['name'], i['params']) for i in c['instances']]}, released intervals (ns) {ivs}")
        return 0
    return run_cases(cases, a.candidate, Path(a.output))


if __name__ == '__main__':
    sys.exit(main())
