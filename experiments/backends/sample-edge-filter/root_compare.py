"""Reproduce the lost root-window certificate using frozen two-backend inputs.

The five fixed observations test continuous output accuracy, not exact event
phase. The original all-native-time phase check remains boundary_replay.py.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'evas/src'), str(ROOT/'experiments/backends/paper')]
from evas import Instance, KernelError, compile_sources, transient
from inputs import save, sha

TIMES = [0., 1., 1.75, 2.5, 3.]
CASES = {f'delay-{delay}-{name}': (delay, tolerance)
         for delay in (0.0, 0.125)
         for name, tolerance in (('loose', 1e-3), ('tight', 1e-12))}
BUDGETS = [1e-10, 1e-3]


def oracle(t, delay):
    h = max(0., t-math.sqrt(2.)-delay)
    a = min(h, .5)
    y = (a + .25*math.expm1(-a/.25))/.5
    return y if h <= .5 else 1+(y-1)*math.exp(-(h-.5)/.25)


def acceptance_observed(record, case, budget, policy):
    if policy not in ('retained-window', 'adaptive-root'):
        raise ValueError('Unknown acceptance policy: '+policy)
    should_reject = policy == 'retained-window' and case['root_tolerance'] == 1e-3 and budget == 1e-10
    if should_reject:
        return record['status'] == 'REJECTED' and 'waveform_accuracy' in record['reason']
    return record['status'] == 'ACCEPTED' and record['within_requested_voltage_budget']


def filter_error(rows, delay):
    if [r['time'] for r in rows] != TIMES:
        raise ValueError('Missing or reordered fixed observations')
    if any(not math.isfinite(v) for r in rows for v in r.values()):
        raise ValueError('Nonfinite observation')
    return max(abs(r['y']-oracle(r['time'],delay)) for r in rows)


def validate_reference(reference):
    """Require the complete frozen four-case, two-budget experiment."""
    manifest = json.loads((reference/'MANIFEST.json').read_text())
    found = {p.parent.name for p in reference.glob('*/case.json')}
    if found != set(CASES):
        raise ValueError('Incomplete or unexpected reference cases')
    required = {f'{name}/{file}' for name in CASES
                for file in ('case.json', 'dut.va', 'rows.json')}
    if not isinstance(manifest, dict) or not required <= manifest.keys():
        raise ValueError('Incomplete reference manifest coverage')
    for name, digest in manifest.items():
        if sha(reference/name) != digest:
            raise ValueError('Changed reference: '+name)
    cases = {}
    for name, (delay, tolerance) in CASES.items():
        case = json.loads((reference/name/'case.json').read_text())
        expected = dict(delay=delay, root_tolerance=tolerance,
                        eva_voltage_budgets=BUDGETS, stop=3.,
                        inputs={'u': [[0., 0.], [3., 3.]]})
        if case != expected:
            raise ValueError('Changed reference case or voltage budgets: '+name)
        cases[name] = case
    return cases


def compare(reference, output, kernel, policy='retained-window'):
    cases = validate_reference(reference)
    output.mkdir(parents=True, exist_ok=False)
    save(output/'IDENTITY.json', dict(kernel_sha256=sha(kernel), acceptance_policy=policy,
         checker_sha256=sha(Path(__file__)),
         kernel_identity=json.loads(subprocess.check_output([str(kernel.resolve()), '--version', '--json'])),
         reference_manifest_sha256=sha(reference/'MANIFEST.json')))
    results = []
    for name, case in sorted(cases.items()):
        work = reference/name
        refs = {r['time']:r for r in json.loads((work/'rows.json').read_text())}
        if any(t not in refs for t in TIMES):
            raise ValueError('Missing exact native observation: '+work.name)
        program = compile_sources({'dut.va':(work/'dut.va').read_text()},
                  [Instance('dut','dut',{n:n for n in ('u','e','y','n')})])
        for budget in case['eva_voltage_budgets']:
            dest = output/work.name/str(budget)
            dest.mkdir(parents=True)
            record = dict(case=work.name, voltage_budget_V=budget,
                          source_sha256=sha(work/'dut.va'),
                          spectre_maximum_filter_error_V=max(abs(refs[t]['y']-oracle(t,case['delay'])) for t in TIMES))
            try:
                response = transient(program,case['inputs'],TIMES,stop=3.,max_step=1.,
                                     vabstol=budget,reltol=0.,kernel=kernel,timeout=90)
                save(dest/'response.json',response)
                rows = [dict(time=t,**dict(zip(response['nodes'],r['voltages'])))
                        for t,r in zip(TIMES,response['solutions'],strict=True)]
                error = filter_error(rows, case['delay'])
                record.update(status='ACCEPTED', filter_error_V=error,
                              within_requested_voltage_budget=error<=budget,
                              maximum_same_time_filter_difference_V=max(abs(r['y']-refs[r['time']]['y']) for r in rows))
            except KernelError as error:
                record.update(status='REJECTED',reason=str(error))
            record['expected_acceptance_observed'] = acceptance_observed(record, case, budget, policy)
            save(dest/'RESULT.json', record)
            results.append(record)
    save(output/'RESULTS.json', results)
    print(json.dumps(results,indent=2))
    if any(r.get('within_requested_voltage_budget') is False or
           not r['expected_acceptance_observed'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('reference',type=Path)
    p.add_argument('output',type=Path)
    p.add_argument('kernel',type=Path)
    p.add_argument('--policy', choices=['retained-window', 'adaptive-root'], default='retained-window',
                   help='Historical safe rejection, or the new automatic refinement requirement')
    a=p.parse_args()
    compare(a.reference,a.output,a.kernel,a.policy)
