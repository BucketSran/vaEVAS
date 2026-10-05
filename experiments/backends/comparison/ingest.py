"""Add freshly executed CMP8 observations to a new immutable evidence snapshot."""
from __future__ import annotations
import argparse
import copy
from pathlib import Path

from records import ROOT, BACKENDS, identity, load, sha, validate
from freeze import SELECTED, save
from runner import verify

STATUS = {'observations_within_targets': 'P', 'observed_violation': 'F', 'unresolved': 'I',
          'observation_invalid': 'I', 'compile_failed': 'X', 'execution_failed': 'X', 'timeout': 'X',
          'missing_waveform': 'I', 'missing_compile_artifact': 'X'}


def verify_output(output):
    for rel, entry in load(output / 'FILE_MANIFEST.json').items():
        path = (output / rel).resolve()
        if not path.is_relative_to(output.resolve()) or sha(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
            raise ValueError('execution artifact drift: ' + rel)


def ingest(snapshot, inputs, executions, compact):
    compact = compact.resolve()
    data = copy.deepcopy(load(snapshot))
    verify(inputs)
    if not compact.resolve().is_relative_to(ROOT):
        raise ValueError('retrievable compact evidence belongs inside owning repository')
    compact.mkdir(parents=True, exist_ok=False)
    batch = next(d for d in data['datasets'] if d['id'] == 'cmp8-base')
    case_ids = {c['id']: c['input_identity'] for c in batch['cases']}
    seen = set()
    for output in executions:
        verify_output(output)
        started = load(output / 'STARTED.json')
        if started['input_manifest_sha256'] != sha(inputs / 'INPUT_MANIFEST.json'):
            raise ValueError('execution used another frozen input manifest')
        results = load(output / 'EXECUTION.json')
        backend = started['backend']
        if backend not in BACKENDS or len(results) != 8 or {r['condition'] for r in results} != set(SELECTED):
            raise ValueError('incomplete or unexpected backend execution')
        if backend in seen:
            raise ValueError('duplicate backend execution; retries need a distinct dataset')
        seen.add(backend)
        for result in results:
            condition = result['condition']
            if result['backend'] != backend or result['profile'] != 'base' or result['input_identity'] != case_ids[condition]:
                raise ValueError('execution configuration identity mismatch')
            directory = compact / backend / condition
            directory.mkdir(parents=True)
            analysis = result['analysis']
            save(directory / 'observation.json', analysis)
            tool = result['tool']
            effective = copy.deepcopy(result.get('effective_settings', result.get('settings_audit')))
            if effective and 'transient' in effective:
                transient = effective.pop('transient')
                effective['transient_summary'] = {'accepted_steps': transient.get('accepted_steps'),
                    'discarded_trials': transient.get('discarded_trials'), 'state_names': transient.get('state_names'),
                    'event_count': len(transient.get('events', []))}
            receipt = {'schema_version': 1, 'run_id': output.name, 'backend': backend, 'condition': condition,
                'profile': 'base', 'source_revision': tool['revision'], 'runtime_identity': tool['runtime_identity'],
                'kernel_sha256': tool.get('kernel_sha256'), 'tool': tool,
                'input_identity': result['input_identity'], 'input_manifest_sha256': started['input_manifest_sha256'],
                'source_sha256': result['source_sha256'], 'checker_identity': load(inputs / 'provenance.json')['checker_identity'],
                'runner_sha256': started['runner_sha256'], 'allocation': started['allocation'],
                'requested_settings': load(output / 'runs' / condition / 'base' / 'requested_settings.json'),
                'effective_settings': effective,
                'commands': result['commands'], 'execution_status': result['status'],
                'waveform_sha256': result.get('waveform_sha256'),
                'raw_file_manifest_sha256': sha(output / 'FILE_MANIFEST.json'),
                'raw_availability': 'task-local; original waveforms/logs not committed',
                'observation': {'path': str((directory / 'observation.json').relative_to(ROOT)), 'sha256': sha(directory / 'observation.json')}}
            save(directory / 'receipt.json', receipt)
            verdict = STATUS[analysis['status']]
            measured = {'revision': tool['revision'], 'runtime_identity': tool['runtime_identity'],
                        'run_id': output.name, 'kernel_sha256': tool.get('kernel_sha256'),
                        'output_sha256': result.get('waveform_sha256'), 'version': tool.get('version', tool.get('kernel_version', 'unknown'))}
            record = next(r for r in data['records'] if r['dataset'] == 'cmp8-base' and r['backend'] == backend and r['case'] == condition)
            if record['accounting'] != 'unrun':
                raise ValueError('attempt to relabel prior measured configuration')
            record.update(verdict=verdict, qualification='I', stage='analysis' if result['status'] == 'waveform_available'
                          else result.get('failure_stage', 'execute'), reason=analysis['status'], accounting='executed',
                          measurement=measured, checker_identity=receipt['checker_identity'],
                          reuse_justification='Input and runtime identity match the target; comparison tooling/receipt commits do not alter EVAS parser/kernel sources.'
                          if backend == 'evas' and tool['runtime_identity'] == data['targets']['evas']['runtime_identity'] else '',
                          evidence=[{'path': receipt['observation']['path'], 'sha256': receipt['observation']['sha256'], 'kind': 'analysis'},
                                    {'path': str((directory / 'receipt.json').relative_to(ROOT)), 'sha256': sha(directory / 'receipt.json'), 'kind': 'receipt'}],
                          execution_receipt={'path': str((directory / 'receipt.json').relative_to(ROOT)), 'sha256': sha(directory / 'receipt.json')},
                          availability={'compact': 'repository-contained', 'raw': receipt['raw_availability']})
            screen = analysis.get('v1_screen', {})
            if condition in ('v1-main', 'v2-main') and screen.get('max_observed_error'):
                record['metrics'] = {'voltage': {'property': 'maximum absolute exported output voltage error',
                    'unit': 'V', 'observed': max(v['error_v'] for v in screen['max_observed_error'].values()), 'budget': .001}}
    validate(data)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--execution', type=Path, action='append', required=True)
    parser.add_argument('--compact', type=Path, required=True)
    args = parser.parse_args()
    save(args.output, ingest(args.snapshot, args.inputs, args.execution, args.compact))
