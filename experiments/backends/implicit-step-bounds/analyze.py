"""Recheck the two frozen, finite implicit-DAE mesh comparisons."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from experiments.backends.evidence.psf import normalize

BASE = Path(__file__).resolve().parent
BUDGET = Fraction('1e-7')
TIMES = [Fraction(i, 32) for i in range(33)]


def compare(spectre, evas):
    if [Fraction(row['time']) for row in spectre] != TIMES:
        raise ValueError('Spectre must retain all 33 native times, including t=0')
    if [Fraction(row['time']) for row in evas] != TIMES:
        raise ValueError('EVAS must retain all 33 forced observations, including t=0')
    errors = {'spectre_vs_answer': Fraction(0), 'evas_vs_answer': Fraction(0),
              'paired': Fraction(0)}
    for expected, reference, dut in zip(TIMES, spectre, evas):
        a, b = Fraction(reference['y']), Fraction(float(dut['y']))
        errors['spectre_vs_answer'] = max(errors['spectre_vs_answer'], abs(a - expected))
        errors['evas_vs_answer'] = max(errors['evas_vs_answer'], abs(b - expected))
        errors['paired'] = max(errors['paired'], abs(a - b))
    return dict(rows=33, max_absolute_error_V={k: float(v) for k, v in errors.items()},
                budget_V=float(BUDGET), passed=all(v <= BUDGET for v in errors.values()))


def self_test():
    exact = [{'time': str(float(t)), 'y': str(float(t))} for t in TIMES]
    assert compare(exact, exact)['passed']
    wrong = [dict(row) for row in exact]
    wrong[7]['y'] = repr(float(Fraction(wrong[7]['y']) + Fraction('1e-4')))
    assert not compare(exact, wrong)['passed']
    for truncated in [exact[1:], exact[:-1]]:
        try:
            compare(truncated, exact)
        except ValueError:
            pass
        else:
            raise AssertionError('missing observation was accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
    receipt = json.loads((BASE / 'receipt.json').read_text())
    for relative, expected in receipt['retained_files_sha256'].items():
        actual = hashlib.sha256((BASE / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'retained evidence changed: {relative}')
    results = {}
    for name in ('voltage', 'conditional'):
        reference = normalize(BASE / name / 'spectre.psf', {'voltage_nodes': ['u', 'y']})
        spectre = [{'time': r['time'], 'y': r['voltages']['y']}
                   for r in reference['decimal_tokens']]
        evas = json.loads((BASE / name / 'evas-observations.json').read_text())['rows']
        results[name] = compare(spectre, evas)
    print(json.dumps(dict(analysis='implicit-step-bounds-finite-v1', results=results), indent=2))
    return 0 if all(r['passed'] for r in results.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
