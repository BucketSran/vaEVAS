#!/usr/bin/env python3
"""Trusted final entry. Without --execute it only prepares frozen inputs."""
import argparse
import os
import sys
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]
PUBLIC = TASK / 'environment/starter/testbench'
if not PUBLIC.is_dir():
    PUBLIC = Path('/app/testbench')  # Fresh separate-verifier baseline.
sys.path.insert(0, str(PUBLIC))
from contract import observations, render
from runtime import dump, read_json, run_suite, suite_result
from final_cases import final_cases

task_result = suite_result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--author-plan', action='store_true')
    parser.add_argument('--render', type=Path)
    parser.add_argument('--step-ns', type=float, default=1.)
    parser.add_argument('--guard-ns', type=float, default=.01)
    parser.add_argument('--candidate', type=Path, default=Path('/app/circuit.va'))
    parser.add_argument('--output', type=Path, default=Path('/logs/verifier'))
    parser.add_argument('--execute', action='store_true', help='launch licensed Spectre; otherwise prepare only')
    parser.add_argument('--spectre', default=os.environ.get('SPECTRE', 'spectre'))
    args = parser.parse_args()
    if args.author_plan or args.render:
        import json
        cases = final_cases()
        plan = observations(cases, args.step_ns * 1e-9, args.guard_ns * 1e-9)
        if args.render:
            for case in cases:
                render(case, plan, args.render / case['name'])
        print(json.dumps(dict(status='specified_unvalidated', score=None, cases=cases, observations=plan), indent=2))
        return 0
    settings = read_json(PUBLIC / 'protocol.json')
    result = run_suite(args.candidate, args.output, final_cases(), settings,
                       launch=args.execute, binary=args.spectre)
    import json
    print(json.dumps(dict(status=result['status'], score=result['score'], reason=result.get('reason'))))
    return 2 if result['score'] is None else 0

if __name__ == '__main__':
    raise SystemExit(main())
