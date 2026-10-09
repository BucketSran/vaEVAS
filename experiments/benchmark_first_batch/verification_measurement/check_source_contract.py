"""Apply the canonical submission policy to this group's VA, without executing it."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def check(runtime):
    spec = importlib.util.spec_from_file_location('first_batch_submission_policy', runtime)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    registry = json.loads((ROOT / 'benchmark/first_batch/verification_measurement.json').read_text())
    sources = []
    for task in registry['tasks']:
        if task['id'] == 'va08-adc-linearity':
            continue
        directory = ROOT / task['path']
        contract = json.loads((directory / 'tests/contract.json').read_text())
        paths = [directory / 'solution/dut.va', *sorted((directory / 'tests/mutants').glob('*.va')),
                 directory / 'environment/public/starter.va', directory / 'environment/public/device.va']
        for path in paths:
            source = path.read_bytes()
            executed, receipt = module.prepare_source(source, contract['candidate_files'],
                                                      contract['output_files'], ROOT / 'runs/policy-only-output')
            if executed != source or not receipt['inverse_verified']:
                raise AssertionError('unexpected source translation in no-I/O task')
            sources.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(source).hexdigest()})
    return {'policy_sha256': hashlib.sha256(runtime.read_bytes()).hexdigest(),
            'lexer_sha256': hashlib.sha256(runtime.with_name('adc_linearity.py').read_bytes()).hexdigest(),
            'source_count': len(sources), 'passed': True, 'scope': 'static_policy_only_no_candidate_execution',
            'sources': sources}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, default=ROOT / 'benchmark/checkers/circuit_task.py')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = check(args.runtime)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(f"{report['source_count']} VA sources: static submission policy PASS")


if __name__ == '__main__':
    main()
