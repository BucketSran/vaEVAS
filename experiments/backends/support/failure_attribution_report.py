"""Replay diagnostic facts without changing a checker, binding or historical score.

Cause assignments are reviewed judgments in README.md. This script verifies
their archived inputs and extracts the observations; it does not infer a bug
from a failed grade or turn diagnostic variants into qualified configurations.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'evas/validation/paper'))
sys.path.insert(0, str(ROOT / 'experiments/backends/paper'))
from precision_binding import load_registry
from precision_v2_report import verify_case_inputs
from observations import read_native
from inputs import sha

RECEIPT = ROOT / 'experiments/backends/support/20261011-precision-binding.json'


def load(path):
    return json.loads(path.read_text())


def identity(path, base):
    return {'path': str(path.relative_to(base)), 'sha256': sha(path)}


def verify_manifest(base):
    manifest = load(base / 'FILE_MANIFEST.json')
    for name, entry in manifest.items():
        path = (base / name).resolve()
        if not path.is_relative_to(base.resolve()) or path.is_symlink():
            raise ValueError('unsafe evidence path: ' + name)
        if sha(path) != entry['sha256'] or path.stat().st_size != entry['bytes']:
            raise ValueError('evidence changed: ' + name)
    return len(manifest)


def count_changes(rows):
    changes = []
    previous = None
    for row in rows:
        current = round(row['count'])
        if abs(row['count'] - current) > 1e-6:
            raise ValueError('noninteger counter cannot be interpreted')
        if current != previous:
            changes.append({k: row[k] for k in ('time', 'clk', 'y', 'count')})
            previous = current
    return changes


def tool_identity(tool):
    # Probe process IDs, elapsed time and output-directory paths are execution
    # metadata. Keep all actual version/binary/image fields for comparison.
    value = dict(tool)
    value['versions'] = {k: {n: v for n, v in entry.items() if n != 'probe'}
                         for k, entry in tool.get('versions', {}).items()}
    return value


def diagnostic_deck(original, variant):
    if variant in ('mir', 'repeat'):
        return original
    if variant == 'explicit-op':
        if original.count('.tran ') != 1:
            raise ValueError('unexpected transient command')
        return original.replace('.tran ', '.print op v(u) v(y)\n.op\n.tran ')
    if variant == 'no-observer':
        if original.count('Vpaper_observer ') != 1:
            raise ValueError('unexpected observer source')
        result = []
        skipping = False
        for line in original.splitlines():
            if line.startswith('Vpaper_observer '):
                skipping = True
                continue
            if skipping and line.startswith('+'):
                continue
            skipping = False
            result.append(line)
        return '\n'.join(result) + '\n'
    raise ValueError('unreviewed diagnostic variant')


def build(old, supplement, diagnostic):
    analyzer_hash = sha(Path(__file__))
    registry = load_registry()  # Includes the immutable receipt dependency.
    receipt = load(RECEIPT)
    bases = {'v2-original': old, 'binding-supplement': supplement}
    verified = []
    for origin, base in bases.items():
        # Historical execution sources are verified against their snapshots,
        # not today's analysis code. The registry verifies the latter separately.
        for folder, manifest_name in ((base / 'inputs', 'MANIFEST.json'),
                                      (base / 'repo', '../inputs/SOURCE_IDENTITY.json')):
            for name, digest in load(folder / manifest_name).items():
                path = (folder / name).resolve()
                if not path.is_relative_to(folder.resolve()) or sha(path) != digest:
                    raise ValueError('historical input/source changed: ' + name)
        if sha(base / 'inputs/MANIFEST.json') != receipt['manifests'][origin]:
            raise ValueError('frozen input identity changed')
        for lane, evidence in receipt['lanes'][origin].items():
            collected = base / 'collected' / lane
            out = collected / 'outputs' / lane
            if sha(collected / 'raw.tar.gz') != evidence['archive_sha256']:
                raise ValueError('archive identity changed')
            if sha(out / 'FILE_MANIFEST.json') != evidence['manifest_sha256']:
                raise ValueError('manifest identity changed')
            operator = load(collected / 'operator-receipts' / (lane + '.json'))
            if not operator['cleanup_confirmed'] or operator['exit_code'] != 0:
                raise ValueError('incomplete original execution')
            verified.append({'origin': origin, 'lane': lane, 'files': verify_manifest(out)})

    attempts = []
    for row in receipt['results']:
        relevant = (
            row['backend'] == 'openvaf_r_ngspice' and row['family'] == 'sample_hold'
            or row['backend'] == 'gnucap_modelgen' and row['condition'] in ('SH-X-RAMP', 'LP-NONZERO')
            or row['backend'] == 'evas' and (row['condition'] == 'SH-X-RAMP'
                or row['condition'] in ('LP-RAMP', 'LP-NONZERO', 'LP-IDT'))
            or row['condition'] == 'LP-RAMP'
        )
        if not relevant:
            continue
        base = bases[row['origin']]
        lane = row['family'] + '-' + row['backend']
        out = base / 'collected' / lane / 'outputs' / lane
        work = out / 'runs' / row['label']
        plan = next(p for p in load(base / 'inputs/PLAN.json')
                    if p['backend'] == row['backend'] and p['label'] == row['label'])
        verify_case_inputs(work, base / 'inputs' / plan['work'], plan)
        record = load(work / 'RESULT.json')
        fact = {k: row[k] for k in ('id', 'condition', 'backend', 'profile', 'execution_status', 'axes')}
        fact.update(source=identity(work / 'dut.va', base),
                    execution=identity(work / 'RESULT.json', base),
                    settings=load(work / 'requested_settings.json'))
        if row['execution_status'] == 'waveform_available':
            if sha(work / record['waveform']) != row['waveform_sha256'] or sha(work / 'RESULT.json') != row['receipt_sha256']:
                raise ValueError('receipt and waveform identities differ')
            rows = read_native(work / record['waveform'], row['backend'])
            fact.update(first=rows[0], last=rows[-1], row_count=len(rows),
                        waveform=identity(work / record['waveform'], base),
                        error_upper_V=row['assessment']['error_upper_V'],
                        effective_settings=row['qualification']['actual'],
                        setting_issues=row['qualification']['issues'])
            if row['condition'] == 'SH-X-RAMP':
                fact['count_changes'] = count_changes(rows)
            if row['backend'] == 'evas' and row['condition'] == 'SH-X-RAMP':
                evidence = load(work / 'ASSESSMENT-v2.json')
                fact['first_event'] = evidence['event_records'][0]
                raw_response = load(work / 'raw-response.json')
                fact['reported_events'] = raw_response['transient']['events']
                fact['raw_response'] = identity(work / 'raw-response.json', base)
        else:
            fact['reason'] = record.get('reason')
            if (work / 'simulate.log').exists():
                log = (work / 'simulate.log').read_text()
                fact['diagnostics'] = [s.strip() for s in log.splitlines()
                                       if any(word in s.lower() for word in ('timestep too small', 'aborted', 'error:'))]
            if (work / 'worker-result.json').exists():
                fact['worker_result'] = load(work / 'worker-result.json')
        attempts.append(fact)

    raw = diagnostic / 'raw'
    collection = load(diagnostic / 'COLLECTION.json')
    if sha(diagnostic / 'raw.tar.gz') != collection['archive_sha256']:
        raise ValueError('diagnostic archive changed')
    if sha(raw / 'outputs/FILE_MANIFEST.json') != collection['manifest_sha256']:
        raise ValueError('diagnostic manifest changed')
    verify_manifest(raw / 'outputs')
    operator = load(raw / 'operator.json')
    if not operator['cleanup_confirmed'] or operator['exit_code'] != 0:
        raise ValueError('diagnostic cleanup incomplete')
    provenance = load(raw / 'outputs/PROVENANCE.json')
    if sha(raw / 'remote_diagnose.py') != provenance['driver_sha256'] or sha(raw / 'PLAN.json') != provenance['plan_sha256']:
        raise ValueError('diagnostic driver or plan changed')
    plan = load(raw / 'PLAN.json')
    diagnostics = []
    for case in plan:
        backend, condition = case['backend'], case['condition']
        work = raw / 'outputs/runs' / (backend + '--' + condition + '--' + case['variant'])
        original = old / 'collected' / (case['family'] + '-' + backend) / 'outputs' / (case['family'] + '-' + backend) / 'runs' / (condition + '--base')
        tool = load(raw / 'outputs' / backend / 'TOOL_IDENTITY.json')
        prior_tool = load(original.parents[1] / 'TOOL_IDENTITY.json')
        if tool_identity(tool) != tool_identity(prior_tool):
            raise ValueError('diagnostic tool differs from original scan')
        if sha(work / 'dut.va') != sha(original / 'dut.va'):
            raise ValueError('diagnostic changed DUT source')
        deck = 'tb.cir' if backend == 'openvaf_r_ngspice' else 'tb.gc'
        if (work / deck).read_text() != diagnostic_deck((original / deck).read_text(), case['variant']):
            raise ValueError('diagnostic changed more than its named factor')
        record = load(work / 'RESULT.json')
        if any(s['returncode'] != 0 or s['timeout'] or not s['cleanup']['complete'] or not s['container_cleanup']['complete'] for s in record['stages']):
            raise ValueError('diagnostic stage incomplete')
        item = {'case': case, 'source': identity(work / 'dut.va', raw),
                'deck': identity(work / ('tb.cir' if backend == 'openvaf_r_ngspice' else 'tb.gc'), raw),
                'result': identity(work / 'RESULT.json', raw), 'tool': tool_identity(tool)}
        if backend == 'openvaf_r_ngspice':
            if sha(work / 'dut.osdi') != sha(original / 'dut.osdi'):
                raise ValueError('MIR export changed compiled model')
            item.update(same_compiled_model=True, osdi_sha256=sha(work / 'dut.osdi'),
                        unoptimized_mir=(work / 'compile.log').read_text().split('Partially optimized MIR', 1)[0],
                        log=identity(work / 'compile.log', raw))
        else:
            rows = read_native(work / record['waveform'], backend)
            item.update(first=rows[0], last=rows[-1], waveform=identity(work / record['waveform'], raw),
                        simulation_log=identity(work / 'simulate.log', raw))
            if condition == 'SH-X-RAMP':
                item['count_changes'] = count_changes(rows)
            if case['variant'] == 'explicit-op':
                item['dc_log_tail'] = (work / 'simulate.log').read_text().split('@@#')[-3:]
        diagnostics.append(item)
    if sha(Path(__file__)) != analyzer_hash:
        raise ValueError('analyzer changed during replay')
    return {'schema_version': 1, 'id': 'precision-failure-attribution-20261011',
            'scope': 'diagnostic observations; no new grading or binding; unchanged eight-condition denominator',
            'previous_receipt': identity(RECEIPT, ROOT), 'verified_original_lanes': verified,
            'frozen_registry_id': registry['id'], 'attempts': attempts,
            'diagnostic_collection': collection, 'diagnostic_provenance': provenance,
            'diagnostics': diagnostics,
            'analysis_dependencies': {str(p.relative_to(ROOT)): sha(p) for p in
                [Path(__file__), ROOT / 'experiments/backends/paper/observations.py',
                 ROOT / 'experiments/backends/evidence/legacy_waveforms.py',
                 ROOT / 'experiments/backends/support/precision_v2_report.py',
                 ROOT / 'experiments/backends/support/precision_run.py',
                 ROOT / 'evas/validation/paper/precision_binding.py']},
            'availability': 'raw waveforms, logs and execution driver are local-only; compact receipt and replay script repository-contained'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('old', 'supplement', 'diagnostic', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('preserve previous analyses; choose a new output')
    result = build(args.old, args.supplement, args.diagnostic)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'verified_lanes': len(result['verified_original_lanes']),
                      'archived_attempts': len(result['attempts']), 'diagnostics': len(result['diagnostics'])}))
