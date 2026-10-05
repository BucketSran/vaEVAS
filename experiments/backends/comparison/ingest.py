"""Add freshly executed CMP8 observations to a new immutable evidence snapshot."""
from __future__ import annotations
import argparse
import copy
import subprocess
from pathlib import Path

from records import ROOT, BACKENDS, STATUS, identity, load, sha, validate, voltage_metrics
from freeze import SELECTED, save
from runner import verify


def verify_output(output):
    for rel, entry in load(output / 'FILE_MANIFEST.json').items():
        path = (output / rel).resolve()
        if not path.is_relative_to(output.resolve()) or sha(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
            raise ValueError('execution artifact drift: ' + rel)


def runner_sources(hashes):
    refs = []
    for digest in sorted(set(hashes)):
        paths = list((ROOT / 'experiments/backends/comparison/evidence/sources').glob('*-' + digest + '.py.txt'))
        if len(paths) != 1 or sha(paths[0]) != digest:
            raise ValueError('actual runner source is not retrievable: ' + digest)
        refs.append({'path': str(paths[0].relative_to(ROOT)), 'sha256': digest, 'kind': 'actual runner source'})
    return refs


def ingest(snapshot, inputs, executions, compact, blocked=()):
    compact = compact.resolve()
    data = copy.deepcopy(load(snapshot))
    if data['schema_version'] != 2:
        raise ValueError('derive legacy snapshot to schema2 before new ingestion')
    if 'derivation' in data:
        data['prior_static_derivation'] = data.pop('derivation')
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
                'initial_runner_sha256': started['runner_sha256'],
                'analysis_runner_sha256': result.get('runner_sha256', started['runner_sha256']),
                'runner_sources': runner_sources([started['runner_sha256'], result.get('runner_sha256', started['runner_sha256'])]),
                'continuation': load(output / 'CONTINUATION.json') if (output / 'CONTINUATION.json').is_file() else None,
                'allocation': started['allocation'],
                'requested_settings': load(output / 'runs' / condition / 'base' / 'requested_settings.json'),
                'effective_settings': effective,
                'commands': result['commands'], 'execution_status': result['status'],
                'waveform_sha256': result.get('waveform_sha256'),
                'raw_file_manifest_sha256': sha(output / 'FILE_MANIFEST.json'),
                'raw_availability': 'local-only',
                'raw_availability_note': 'task-local; original waveforms/logs not committed',
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
                          availability={'compact': 'repository-contained', 'raw': receipt['raw_availability'],
                                        'raw_note': receipt['raw_availability_note']})
            record['metrics'] = voltage_metrics(condition, analysis, data['schema_version'])
    for output in blocked:
        started = load(output / 'STARTED.json')
        backend = started['backend']
        if backend in seen or backend not in BACKENDS or started['input_manifest_sha256'] != sha(inputs / 'INPUT_MANIFEST.json'):
            raise ValueError('duplicate or mismatched blocked backend')
        seen.add(backend)
        probes = list(output.glob('version-*.json'))
        if len(probes) != 1:
            raise ValueError('blocked evidence must identify one failed tool preflight')
        probe = load(probes[0])
        log = probes[0].with_suffix('.log')
        if probe['exit_code'] == 0 and not probe['timed_out'] or sha(log) != probe['log_sha256']:
            raise ValueError('failed preflight/log identity mismatch')
        receipt = {'backend': backend, 'input_manifest_sha256': started['input_manifest_sha256'],
                   'allocation': started['allocation'], 'tool': started['tool'], 'probe': probe,
                   'runner_sources': runner_sources([started['runner_sha256']]),
                   'failure_log': log.read_text(), 'case_compilation_launches': 0, 'case_simulation_launches': 0,
                   'reason': 'Existing pinned container layer is missing; no backend case was launched. No restore or retry.'}
        path = compact / (backend + '-preflight.json')
        save(path, receipt)
        for record in data['records']:
            if record['dataset'] == 'cmp8-base' and record['backend'] == backend:
                if record['accounting'] != 'unrun':
                    raise ValueError('cannot replace an actual observation with unrun')
                record.update(stage='infrastructure', reason=receipt['reason'],
                              evidence=[{'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'kind': 'failed preflight'}])
    application = next(d for d in data['datasets'] if d['id'] == 'application-reference')
    task = ROOT / 'benchmark/tasks/va07-triangle-repair'
    case = next(c for c in load(task / 'tests/cases.json') if c['name'] == 'constant-tighter')
    application['scope'] = '正确参考候选已固定，四后端公共回放合同尚未冻结；原本地EVAS结果仅为单后端历史开发回放。'
    application['candidates'] = [{'id': 'va07-correct-reference', 'case_name': 'constant-tighter',
        'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'source_sha256': sha(task / 'solution/dut.va'),
        'case_sha256': identity(case), 'checker_sha256': sha(ROOT / 'benchmark/checkers/triangle_oscillator.py'),
        'adapter_checker_sha256': sha(ROOT / 'benchmark/checkers/triangle_evas.py'),
        'history_path': 'benchmark/tasks/va07-triangle-repair/SOURCE.md#通过-harness-调用本地-evas',
        'pending_contract': '同源后端外壳、精度设置映射、601/607查询的公平观察与独立时间区间资格',
        'sources': [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p), 'kind': 'application source'} for p in
                    (task / 'solution/dut.va', task / 'tests/cases.json', ROOT / 'benchmark/checkers/triangle_oscillator.py',
                     ROOT / 'benchmark/checkers/triangle_evas.py')]}]
    from derive import freeze_candidates
    freeze_candidates(data, ROOT)
    validate(data)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('inputs', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--execution', type=Path, action='append', required=True)
    parser.add_argument('--compact', type=Path, required=True)
    parser.add_argument('--blocked', type=Path, action='append', default=[])
    args = parser.parse_args()
    save(args.output, ingest(args.snapshot, args.inputs, args.execution, args.compact, args.blocked))
