"""Post-run metadata audit. Does not change the frozen scorer or any evidence."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/archive/dvs2-starter-pilot'))
from analyze import number


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def last(pattern, log):
    matches = re.findall(pattern, log, re.M)
    if not matches:
        raise ValueError('missing setting readback: ' + pattern)
    return matches[-1].strip()


def setting_readback(backend, log):
    if backend == 'gnucap':
        actual = {key: number(last(r'\b' + key + r'=\s*(\S+)', log))
                  for key in ['reltol', 'vntol', 'abstol', 'short', 'numdgt']}
        actual['method'] = last(r'\bmethod=\s*(\S+)', log)
        assert actual['short'] == 1e-9 and actual['numdgt'] == 16
        assert actual['method'] == 'trap'
        return actual, {'reltol': 'reltol', 'vntol': 'vabstol', 'abstol': 'iabstol'}
    if backend == 'openvaf_ngspice':
        # option before tran can show defaults; the last block is after tran.
        actual = {key: float(last(r'^' + key + r'\s+\([^)]+\)\s*=\s*(\S+)', log))
                  for key in ['reltol', 'vntol', 'abstol']}
        actual['method'] = last(r'^Integration Method = (\S+)', log)
        actual['maxorder'] = int(last(r'^MaxOrder = (\S+)', log))
        assert actual['method'] == 'TRAPEZOIDAL' and actual['maxorder'] == 2
        return actual, {'reltol': 'reltol', 'vntol': 'vabstol', 'abstol': 'iabstol'}
    units = {'s': 1., 'ms': 1e-3, 'us': 1e-6, 'ns': 1e-9, 'ps': 1e-12}
    actual = {}
    for key in ['reltol', 'vabstol', 'iabstol', 'step', 'stop']:
        tokens = last(r'^\s*' + key + r'\s*=\s*([^\n]+)', log).split()
        actual[key] = float(tokens[0]) * (units[tokens[1]] if len(tokens) > 1 else 1.)
    return actual, {key: key for key in actual}


def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('archive', type=Path)
    parser.add_argument('results', type=Path)
    args = parser.parse_args()
    root = args.root
    matrix = read(args.results / 'matrix.json')
    assert matrix['evidence_manifests'][root.name] == sha(root / 'FILE_MANIFEST.json')
    manifest = read(root / 'FILE_MANIFEST.json')
    for name, identity in manifest.items():
        path = root / name
        assert path.resolve().is_relative_to(root.resolve())
        assert sha(path) == identity['sha256'] and path.stat().st_size == identity['bytes']
    execution = read(root / 'EXECUTION.json')
    stages = read(root / 'STAGE_COUNTS.json')
    assert len(execution) == 130 and stages['simulate'] == 112
    assert sum(stages.get(k, 0) for k in ['compile', 'modelgen', 'cpp_compile']) == 34
    settings = []
    for record in execution:
        work = root / 'runs' / record['backend'] / record['condition'] / record['profile']
        item = {key: record[key] for key in ['backend', 'condition', 'profile', 'status']}
        if record['status'] == 'waveform_available':
            log = (work / 'simulate.log').read_text()
            actual, mapping = setting_readback(record['backend'], log)
            requested = read(work / 'requested_settings.json')
            assert all(math.isclose(actual[k], requested[v], rel_tol=1e-12, abs_tol=0)
                       for k, v in mapping.items()), item
            item.update(readback=actual, requested_values_match=True,
                        readback_log_sha256=sha(work / 'simulate.log'),
                        interpretation='EVAS request echo; not a SPICE error-control certification'
                        if record['backend'] == 'evas' else 'logged settings after netlist setup')
        else:
            item['readback_unavailable_reason'] = record['status']
        settings.append(item)
    save(args.results / 'settings-audit.json', settings)
    actual_stages = [read(p) for p in root.rglob('*.json')
                     if p.name in ['simulate.json', 'compile.json', 'modelgen.json', 'cpp_compile.json']]
    assert len(actual_stages) == 146
    assert not any(s['timed_out'] for s in actual_stages)
    receipt = dict(
        run_id=root.name, date='2026-09-28', host_alias='thu-sui',
        input_manifest_sha256=sha(root / 'INPUT_MANIFEST.json'),
        file_manifest_sha256=sha(root / 'FILE_MANIFEST.json'),
        raw_archive_sha256=sha(args.archive), raw_archive_bytes=args.archive.stat().st_size,
        verified_archived_files=len(manifest),
        matrix_sha256=sha(args.results / 'matrix.json'),
        csv_sha256=sha(args.results / 'matrix.csv'),
        table_sha256=sha(args.results / 'MATRIX.md'),
        settings_audit_sha256=sha(args.results / 'settings-audit.json'),
        auditor_sha256=sha(Path(__file__)),
        frozen_sources=read(root / 'SOURCE_IDENTITY.json'),
        images=read(root / 'expected_images.json'),
        version_readbacks={p.stem: p.read_text().strip() for p in sorted((root / 'versions').glob('*.log'))},
        new_execution_counts={b: dict(Counter(r['status'] for r in execution if r['backend'] == b))
                              for b in ['evas', 'openvaf_ngspice', 'gnucap']},
        stage_counts=stages, timeout_count=0,
        settings_readbacks_checked=dict(Counter(r['backend'] for r in settings if r.get('requested_values_match'))),
        settings_limitations='Logged tolerances and selected algorithms only. Backend semantics are not equivalent; EVAS echoes requests. Waveform gap/input checks are in matrix.json. No qualified observation-error bound.',
        execution_and_compile_elapsed_sum_s=sum(s['elapsed_s'] for s in actual_stages),
        merged_summary=matrix['summary'], evidence_use=matrix['evidence_use'],
        verified_source_file_counts=matrix['verified_file_counts'], formal_dvs_qualification='I')
    save(args.results / 'RECEIPT.json', receipt)
    print(json.dumps({k: receipt[k] for k in ['new_execution_counts', 'settings_readbacks_checked',
                     'raw_archive_sha256', 'file_manifest_sha256', 'merged_summary']}, indent=2))


if __name__ == '__main__':
    main()
