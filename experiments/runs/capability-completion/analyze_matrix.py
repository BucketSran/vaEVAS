"""Reanalyze an EVAS matrix with the existing, unchanged original checker.

The frozen source, full raw manifest and copied requests must match before
counting results. Failures remain in the input-defined denominator.
"""
import argparse
from collections import Counter
import csv
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]


def analyze(source, raw, output):
    path = ROOT / 'experiments/archive/pr14-pr15-validation/matrix.py'
    spec = importlib.util.spec_from_file_location('original_matrix', path)
    matrix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matrix)
    matrix.verify(source)
    matrix.verify(raw, 'FILE_MANIFEST.json')
    if (source/'conditions.json').read_bytes() != (raw/'conditions.json').read_bytes():
        raise ValueError('condition denominator changed')
    started = json.loads((raw/'STARTED.json').read_text())
    if started['source_input_manifest_sha256'] != matrix.sha(source/'INPUT_MANIFEST.json'):
        raise ValueError('execution input identity changed')
    cases = json.loads((source/'conditions.json').read_text())
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('duplicate condition ID')
    executions = json.loads((raw/'EXECUTION.json').read_text())
    expected = {(case['id'], profile) for case in cases for profile in matrix.PROFILES}
    actual = [(record['condition'], record['profile']) for record in executions]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError('execution denominator changed')
    records = []
    for case in cases:
        for profile in matrix.PROFILES:
            work = raw/'runs'/case['id']/profile
            frozen = source/'runs'/case['id']/profile
            for name in ('dut.va', 'condition.json', 'requested_settings.json'):
                if (work/name).read_bytes() != (frozen/name).read_bytes():
                    raise ValueError('frozen asset changed: '+str(work/name))
            result = json.loads((work/'result.json').read_text())
            analysis = {'status':result['status'], 'reason':result.get('reason'),
                        'formal_dvs_qualification':'I'}
            if result['status'] == 'waveform_available':
                wave = (work/result['waveform']).resolve()
                if not wave.is_relative_to(work.resolve()) or matrix.sha(wave) != result['waveform_sha256']:
                    raise ValueError('waveform identity changed')
                with wave.open() as stream:
                    rows = [{key:float(value) for key,value in row.items()} for row in csv.DictReader(stream)]
                analysis = matrix.check(rows, case)
            effective = json.loads((work/'effective.json').read_text()) if (work/'effective.json').exists() else {}
            records.append({'condition':case['id'], 'profile':profile,
                            'execution_status':result['status'],
                            'requested_settings':json.loads((work/'requested_settings.json').read_text()),
                            'effective_settings':{key:effective[key] for key in (
                                'vabstol','reltol','max_step','output_points','stop','engine','unsupported_spice_controls')
                                if key in effective},
                            'waveform_sha256':result.get('waveform_sha256'), 'analysis':analysis})
    # Includes transitive repository imports used by the historical checker.
    checker = {str(path.relative_to(ROOT)):matrix.sha(path)}
    for module in tuple(sys.modules.values()):
        file = getattr(module, '__file__', None)
        if file is not None:
            file = Path(file).resolve()
            if file.is_relative_to(ROOT/'experiments') and file.suffix == '.py':
                checker[str(file.relative_to(ROOT))] = matrix.sha(file)
    checker[str(Path(__file__).resolve().relative_to(ROOT))] = matrix.sha(Path(__file__))
    receipt = {'evidence_use':'reanalysis of this named raw execution; original checker unchanged',
               'source_input_manifest_sha256':matrix.sha(source/'INPUT_MANIFEST.json'),
               'raw_manifest_sha256':matrix.sha(raw/'FILE_MANIFEST.json'),
               'execution_started':started, 'checker_sha256':dict(sorted(checker.items())),
               'conditions':len(cases), 'configurations':len(records), 'records':records,
               'summary':{profile:dict(Counter(record['analysis']['status'] for record in records
                            if record['profile']==profile)) for profile in matrix.PROFILES},
               'continuous_time_qualified':False, 'formal_dvs_qualification':'I',
               'raw_artifacts':'local-only; manifests do not make raw artifacts publicly retrievable'}
    with output.open('x') as stream:
        json.dump(receipt,stream,indent=2,ensure_ascii=False,allow_nan=False)
        stream.write('\n')
    print(json.dumps(receipt['summary'],ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    analyze(args.source.resolve(),args.run.resolve(),args.out.resolve())
