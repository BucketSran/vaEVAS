"""Replay the twelve public Spec B requests with their original scientific settings."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from evas import Instance, compile_sources
from evas.protocol import validate_response
from evas.runtime import _invoke

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'evas/validation/event_acceptance'))
from checker import inspect


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--historical-requests', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases = []
    fixtures = ROOT / 'evas/validation/event_acceptance/cases'
    for folder in sorted(fixtures.iterdir()):
        if not folder.is_dir():
            continue
        manifest = json.loads((folder / 'evas-manifest.json').read_text())
        program = compile_sources(
            {name: (folder / name).read_text() for name in manifest['models']},
            [Instance(**instance) for instance in manifest['instances']],
        )
        config = manifest['transient']
        request = {'program': program.to_dict(), 'driven': list(config['sources']), 'samples': [],
                   'transient': {'pwl': list(config['sources'].values()),
                                 'output_times': config['output_times'],
                                 'stop': config['stop'], 'max_step': config['max_step']},
                   'tolerances': {'absolute': manifest['tolerances']['vabstol'],
                                  'relative': manifest['tolerances']['reltol']}}
        historical = {}
        if args.historical_requests:
            original_path = args.historical_requests / folder.name / 'request.json'
            original = json.loads(original_path.read_text())
            latest_program = json.loads(json.dumps(request['program']))
            assert {k: v for k, v in latest_program.items() if k != 'schema_version'} == {
                k: v for k, v in original['program'].items() if k != 'schema_version'}
            assert request['transient'] == original['transient']
            assert {k: v for k, v in request.items() if k != 'program'} == {
                k: v for k, v in original.items() if k != 'program'}
            historical = {'historical_request_sha256': sha(original_path),
                          'historical_schema_version': original['program']['schema_version'],
                          'scientific_request_equal_except_schema_version': True}
        request_path = args.output / (folder.name + '.request.json')
        request_path.write_text(json.dumps(request) + '\n')
        response = _invoke(request, str(args.kernel), 300)
        times = request['transient']['output_times']
        validate_response(response, program, len(times), times)
        rows = [dict(zip(response['nodes'], solution['voltages']), time=time)
                for time, solution in zip(response['transient']['times'], response['solutions'])]
        result = inspect(rows, folder.name.split('-')[0], request['transient']['stop'],
                         request['transient']['max_step'], response['transient']['events'],
                         'evas_binary64_native')
        assert result['numeric_status'] == result['event_status'] == 'P', result
        response_path = args.output / (folder.name + '.json')
        response_path.write_text(json.dumps(response, allow_nan=False) + '\n')
        cases.append({'case': folder.name, **historical,
                      'actual_request_sha256': sha(request_path),
                      'actual_response_sha256': sha(response_path),
                      'response_times_nodes_shape_finite_validated': True,
                      'numeric_status': result['numeric_status'],
                      'event_status': result['event_status']})
    result = {'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'kernel_sha256': sha(args.kernel), 'checker_sha256': sha(fixtures.parent / 'checker.py'),
              'new_spectre_calls': 0, 'cases': cases}
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
