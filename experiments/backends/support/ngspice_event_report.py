"""Reanalyze the bounded OpenVAF-R event diagnosis; never runs a simulator.

This reports diagnostic observations, not a new paper-suite pass count.
The raw directory is the verified local-only bundle described in README.md.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/backends/paper'))
from observations import read_native
from settings_readback import ngspice, ReadbackError

ROUNDS = ('baseline', 'minimize', 'lowering', 'settings', 'settings-readback', 'original-mir')
ANALYSIS_DEPENDENCIES = (
    'experiments/backends/paper/observations.py',
    'experiments/backends/paper/settings_readback.py',
    'experiments/archive/dvs2-starter-pilot/analyze.py',
    'experiments/archive/dvs2-starter-pilot/suite.py',
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def reference(path, base):
    return {'path': str(path.relative_to(base)), 'sha256': digest(path)}


def verify_round(folder):
    manifest = read(folder / 'FILE_MANIFEST.json')
    actual = {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file()}
    if actual != set(manifest) | {'FILE_MANIFEST.json'}:
        raise ValueError(f'raw inventory differs: {folder.name}')
    for relative, identity in manifest.items():
        path = folder / relative
        if not path.resolve().is_relative_to(folder.resolve()) or path.is_symlink():
            raise ValueError('unsafe raw path')
        if path.stat().st_size != identity['bytes'] or digest(path) != identity['sha256']:
            raise ValueError(f'raw bytes differ: {relative}')


def build(raw):
    records = []
    row_sets = {}
    identities = []
    for round_name in ROUNDS:
        folder = raw / round_name
        verify_round(folder)
        operator = read(raw / (round_name + '-operator.json'))
        if operator['status'] != 'complete' or not operator['cleanup_confirmed']:
            raise ValueError(f'incomplete operator: {round_name}')
        tool = read(folder / 'TOOL_IDENTITY.json')
        identity = {'compiler_sha256': tool['compiler_sha256'],
                    'images': {k: v['config_id'] for k, v in tool['images'].items()}}
        identities.append(identity)
        plan = read(raw / (round_name + '.json'))
        provenance = read(folder / 'PROVENANCE.json')
        if digest(raw / (round_name + '.json')) != provenance['plan_sha256']:
            raise ValueError('plan drift')
        if digest(raw / 'remote_probe.py') != provenance['driver_sha256']:
            raise ValueError('execution driver drift')
        cases = {c['id']: c for c in plan['cases']}
        results = read(folder / 'RESULTS.json')
        if {c['id'] for c in results} != set(cases) or len(results) != len(cases):
            raise ValueError('result denominator differs')
        for result in results:
            name = result['id']
            work = folder / 'runs' / name
            case = cases[name]
            for filename, key in [('dut.va', 'source'), ('tb.cir', 'deck')]:
                if (work / filename).read_text() != case[key]:
                    raise ValueError('executed input differs from plan')
            if digest(work / 'dut.va') != result['source_sha256'] or digest(work / 'tb.cir') != result['deck_sha256']:
                raise ValueError('input identity differs')
            if not result['compiled'] or digest(work / 'dut.osdi') != result['osdi_sha256']:
                raise ValueError('compiled model missing or changed')
            if any(s['returncode'] != 0 or s['timeout'] or not s['cleanup']['complete']
                   or not s['container_cleanup']['complete'] for s in result['stages']):
                raise ValueError('stage incomplete')
            entry = {'round': round_name, 'case': name, 'compiled': True,
                     'source_sha256': result['source_sha256'], 'deck_sha256': result['deck_sha256'],
                     'osdi_sha256': result['osdi_sha256'], 'waveform_available': result['waveform'],
                     'diagnostics': result['diagnostics'],
                     'result': reference(work / 'RESULT.json', raw),
                     'compile_log': reference(work / 'compile.log', raw),
                     'simulate_log': reference(work / 'simulate.log', raw)}
            if result['waveform']:
                rows = read_native(work / 'waveform.txt', 'openvaf_r_ngspice')
                entry.update(row_count=len(rows), first=rows[0], last=rows[-1],
                             waveform=reference(work / 'waveform.txt', raw))
                row_sets[(round_name, name)] = rows
            if round_name == 'settings-readback':
                text = (work / 'simulate.log').read_text()
                try:
                    entry['settings_readback'] = ngspice(text, case['deck'])
                except ReadbackError as error:
                    # UIC is deliberately outside the normal reader's command contract.
                    entry['settings_readback'] = {'status': 'not_qualified', 'reason': str(error)}
                final = text.rsplit('* Current simulation options *', 1)[-1]
                entry['iteration_readback_lines'] = [s.strip() for s in final.splitlines()
                                                     if re.match(r'\s*itl[14]\s', s)]
            if round_name in ('minimize', 'lowering', 'settings-readback'):
                entry['source'] = case['source']
                entry['deck'] = case['deck']
            if round_name == 'original-mir' or (round_name == 'settings-readback' and name == 'no-optimization'):
                text = (work / 'compile.log').read_text()
                entry['unoptimized_mir'] = text.split('Partially optimized MIR', 1)[0]
            records.append(entry)
    if any(x != identities[0] for x in identities):
        raise ValueError('tool identity differs between diagnostic rounds')
    lookup = {(r['round'], r['case']): r for r in records}
    original = [r for r in records if r['round'] == 'baseline']
    for r in original:
        other = lookup[('original-mir', r['case'])]
        if any(other[k] != r[k] for k in ('source_sha256', 'deck_sha256', 'osdi_sha256')):
            raise ValueError('MIR instrumentation changed original artifact')
    constant = row_sets[('lowering', 'timer-assignment')]
    cross = row_sets[('lowering', 'cross-assignment')]
    sample = row_sets[('lowering', 'timer-sampler')]
    witness = min(sample, key=lambda r: abs(r['time'] - 1e-7))
    baseline_artifact = lookup[('lowering', 'timer-assignment')]['osdi_sha256']
    same = all(lookup[('lowering', n)]['osdi_sha256'] == baseline_artifact
               for n in ('timer-different-time', 'timer-different-initial'))
    controls = {n: row_sets[('minimize' if n == 'remove-timer' else 'lowering', n)]
                for n in ('remove-timer', 'initial-only-five')}
    facts = {
        'original_cases': len(original),
        'original_timestep_failures': sum(not r['waveform_available'] and any('Timestep too small' in d for d in r['diagnostics']) for r in original),
        'settings_configurations': sum(r['round'] == 'settings-readback' for r in records),
        'settings_waveforms': sum(r['waveform_available'] for r in records if r['round'] == 'settings-readback'),
        'timer_expected_at_t0_V': 0, 'timer_observed_at_t0_V': constant[0]['count'],
        'cross_expected_at_t0_V': 0, 'cross_observed_at_t0_V': cross[0]['count'],
        'timer_time_and_initial_changes_produce_identical_artifact': same,
        'sampler_pre_first_event': {'row': witness, 'expected_count_V': 0, 'first_event_s': 2e-7},
        'sampler_max_output_minus_input_V': max(abs(r['count'] - r['inp']) for r in sample),
        'no_event_controls': {n: {'first': rows[0], 'last': rows[-1]} for n, rows in controls.items()},
    }
    return {'schema_version': 1, 'run_id': 'ngspice-openvaf-diagnosis-20261010',
            'claim': 'Actual compiled-event diagnosis, not a new capability-suite score or a general simulator ranking',
            'project_reference_revision': '6d23108d636514e7c8b296ad106b7652127f19ed',
            'simulator_source_changed': False,
            'configuration_count': len(records), 'compile_count': len(records), 'simulation_count': len(records),
            'original_suite_denominator_unchanged': True,
            'raw_availability': 'local-only; runs/ngspice-openvaf-diagnosis/raw.tar.gz',
            'raw_directory': raw.name,
            'round_manifests': [reference(raw / r / 'FILE_MANIFEST.json', raw) for r in ROUNDS],
            'execution_provenance': [reference(raw / r / 'PROVENANCE.json', raw) for r in ROUNDS],
            'execution_driver': reference(raw / 'remote_probe.py', raw),
            'operator_receipts': [reference(raw / (r + '-operator.json'), raw) for r in ROUNDS],
            'tool': identities[0],
            'compiler_source_commit': 'unknown; directory v24.0.2mob does not prove build provenance',
            'ngspice_self_report': '46',
            'analyzer': {'path': str(Path(__file__).resolve().relative_to(ROOT)), 'sha256': digest(Path(__file__))},
            'analysis_dependencies': [reference(ROOT / path, ROOT) for path in ANALYSIS_DEPENDENCIES],
            'facts': facts, 'records': records}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = build(args.raw)
    with args.output.open('x') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')
    print(json.dumps(report['facts'], ensure_ascii=False, indent=2))
