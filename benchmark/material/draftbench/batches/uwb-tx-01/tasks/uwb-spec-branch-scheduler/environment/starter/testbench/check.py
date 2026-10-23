#!/usr/bin/env python3
"""Public checks for the 8-branch RO scheduler.

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
        except u.RunError as exc:
            errors.append(f"{case['name']}: {exc}")
            continue
        (work / 'wall_s.txt').write_text(f"{res['wall_s']:.1f}\n")
        for rep in contract.check(case, u.Edges(res['records'])):
            rows += rep.rows
    return u.finish(rows, errors, out_dir, final=final, candidate_sha=u.digest(frozen))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['plan', 'run'])
    ap.add_argument('--case', action='append')
    ap.add_argument('--candidate', default='/app/circuit.va')
    ap.add_argument('--output', default='/tmp/uwb-scheduler-public')
    a = ap.parse_args()
    cases = [c for c in contract.public_cases() if not a.case or c['name'] in a.case]
    if a.command == 'plan':
        for c in cases:
            n_sym = sum(1 for f in c['frames'] if f is not None)
            print(f"{c['name']}: {n_sym} symbols in {len(c['frames'])} frames, n_pre={c['n_pre']}, "
                  f"instances {[(i['name'], i['params']) for i in c['instances']]}, reset intervals {len(c['rst'])}")
        return 0
    return run_cases(cases, a.candidate, Path(a.output))


if __name__ == '__main__':
    sys.exit(main())
