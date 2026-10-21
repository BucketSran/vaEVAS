#!/usr/bin/env python3
"""Public analytical diagnostics and explicit native Spectre execution."""
import argparse
import json
import os
from pathlib import Path
from cases import public_cases
from contract import diagnose, load_csv, observations, render
from runtime import read_json, run_suite


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['plan', 'render', 'check', 'prepare', 'run'])
    p.add_argument('--step-ns', type=float, default=1., help='offline diagnostic grid in ns')
    p.add_argument('--guard-ns', type=float, default=.01, help='offline diagnostic event exclusion in ns')
    p.add_argument('--output', type=Path)
    p.add_argument('--csv', type=Path)
    p.add_argument('--voltage-atol', type=float)
    p.add_argument('--time-atol', type=float)
    p.add_argument('--candidate', type=Path, default=Path('/app/circuit.va'))
    p.add_argument('--spectre', default=os.environ.get('SPECTRE', 'spectre'))
    args = p.parse_args()
    try:
        cases = public_cases()
        if args.action in ('prepare', 'run'):
            if args.output is None:
                p.error('prepare/run requires a new --output directory')
            settings = read_json(Path(__file__).with_name('protocol.json'))
            result = run_suite(args.candidate, args.output, cases, settings,
                               launch=args.action == 'run', binary=args.spectre, grading=False)
            # Public execution diagnostics never produce a final task score.
            result['diagnostic_only'] = True
        else:
            plan = observations(cases, args.step_ns * 1e-9, args.guard_ns * 1e-9)
            if args.action == 'plan':
                result = dict(status='specified_unvalidated', score=None, cases=cases, observations=plan)
            elif args.action == 'render':
                if args.output is None:
                    p.error('render requires --output')
                for case in cases:
                    render(case, plan, args.output / case['name'])
                result = dict(status='specified_unvalidated', score=None, rendered=[c['name'] for c in cases])
            else:
                if args.csv is None or args.voltage_atol is None or args.time_atol is None:
                    p.error('check requires --csv, --voltage-atol and --time-atol')
                result = diagnose(plan, load_csv(args.csv), args.voltage_atol, args.time_atol)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 1 if result['status'] == 'fail' else 2 if result['status'] == 'not_run' else 0
    except (ValueError, KeyError, OSError, TypeError) as exc:
        print(json.dumps(dict(status='error', diagnostic_only=True, reason=str(exc))))
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
