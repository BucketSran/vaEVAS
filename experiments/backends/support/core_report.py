"""Replay core execution evidence with the existing adapter and checker.

This report does not run simulators, sign Spectre qualification, alter native
timestamps, or replace the original core results. Raw bundles stay local-only.
"""
import argparse
import collections
import json
from pathlib import Path
import re
import sys

from summarize import ROOT, load, sha, verify

sys.path.insert(0, str(ROOT/'experiments/backends/paper'))
sys.path.insert(0, str(ROOT/'evas/validation/paper'))
from actual_observation import adapt
from criteria import assess_observation
from inputs import verify as verify_inputs
from observations import read_native, normalize_observation


def reference(path):
    return {'path': str(path.resolve().relative_to(ROOT)), 'sha256': sha(path),
            'availability': 'local-only'}


def lane_records(run, backend, selected):
    verify_inputs(run/'inputs')
    lane = run/'collected'/backend/'outputs'/backend
    records = verify(lane)
    active = [r for r in records if r['status'] != 'not_run']
    assert len(active) == len(selected) and {r['condition'] for r in active} == set(selected)
    assert all(r['status'] == 'waveform_available' for r in active)
    receipt = run/'collected'/backend/'operator-receipts'/(backend+'.json')
    operator = load(receipt)
    assert operator['cleanup_confirmed'] and operator['exit_code'] == 0
    for record in active:
        work = lane/'runs'/record['condition']
        assert load(work/'simulate.json')['cleanup']['complete']
        for filename in ('dut.va', 'condition.json', 'requested_times.json',
                         'breakpoint_requests.json', 'requested_settings.json',
                         'request.json' if backend == 'evas' else 'tb.scs'):
            assert (work/filename).read_bytes() == (run/'inputs/runs'/backend/record['condition']/filename).read_bytes()
    return lane, active, reference(receipt)


def native_facts(lane, card, data):
    """Report measured grid/source facts, without granting native-role certificates."""
    work = lane/'runs'/card['id']
    raw = work/'psf/tran.tran.tran'
    rows = read_native(raw, 'spectre')
    old = load(work/'observation.json')
    assert rows == old['rows']
    assert (work/'dut.va').read_text() == card['source']
    observation = normalize_observation(card, 'spectre', rows, ['unknown']*len(rows),
                                        contract=data['shared_contract'])
    metadata = observation['metadata']
    log = (work/'spectre.log').read_text()
    counts = re.findall(r'Number of accepted tran steps\s*=\s*(\d+)', log)
    assert len(counts) == 1
    accepted = int(counts[0])
    assert len(rows) == accepted+1
    stop = card['stop_T']*data['units']['T_s']
    return {'condition': card['id'], 'raw': reference(raw),
            'log': reference(work/'spectre.log'), 'deck': reference(work/'tb.scs'),
            'rows': len(rows), 'logged_accepted_steps': accepted,
            'rows_equal_accepted_steps_plus_initial': True,
            'first_time_s': rows[0]['time'], 'last_time_s': rows[-1]['time'],
            'requested_stop_s': stop, 'last_minus_stop_s': rows[-1]['time']-stop,
            'coverage': metadata['coverage'], 'max_gap_s': metadata['actual_max_gap_s'],
            'local_windows': metadata['local_windows'],
            'missing_exact_centers': sum(not w['exact_center_rows'] for w in metadata['local_windows']),
            'local_gap_limits_met': all(w['max_gap_s'] is not None and
                w['max_gap_s'] <= w['required_max_gap_s']*(1+1e-10) for w in metadata['local_windows']),
            'precision_17g_readback': bool(re.search(r'^\s*precision\s*=\s*%\.17g\s*$', log, re.M)),
            'assessment': assess_observation(observation)['status'],
            'limit': 'Native row-count and time facts only; no new source/input/uncertainty or boundary qualification. No interpolation or nearest-row substitution.'}


def summarize(evas, spectre, original, source_review, output):
    output.mkdir(parents=True, exist_ok=False)
    data = load(evas/'inputs/core.json')
    ids = [c['id'] for c in data['cards']]
    assert len(ids) == 12 and len(set(ids)) == 12
    for run in (spectre, original):
        assert (run/'inputs/core.json').read_bytes() == (evas/'inputs/core.json').read_bytes()
    assert (ROOT/'evas/validation/paper/core-v1.json').read_bytes() == (evas/'inputs/core.json').read_bytes()
    lane, records, operator = lane_records(evas, 'evas', ids)
    build_path = evas/'collected/evas/build/BUILD.json'
    build = load(build_path)
    result = []
    for card in data['cards']:
        cid = card['id']; work = lane/'runs'/cid
        report, observation = adapt(evas/'inputs/core.json', cid, work, source_review,
            output/cid, lane=lane, build_record=build_path,
            source_manifest=evas/'SOURCE_MANIFEST.json',
            tool_profile=evas/'collected/evas/evas-profile.json', producer_repo=evas/'repo')
        assessment = assess_observation(observation)
        (output/cid/'assessment.json').write_text(json.dumps(assessment, indent=2)+'\n')
        previous = original/'collected/evas/outputs/evas/runs'/cid/'observation.json'
        result.append({'condition': cid, 'execution': 'waveform_available',
            # Keep the scorer's separate boundary I and claim limits visible.
            **{k: v for k, v in assessment.items() if k not in
               ('condition_id', 'execution_state', 'qualification_evidence')},
            'execution_identity_verified': report['execution_identity']['verified'],
            'missing_roles': report['missing_roles'],
            'uncertainty': {k: report[k] for k in ('time_error_s', 'voltage_error_V', 'input_error_V')},
            'same_numeric_rows_as_original': observation['rows'] == load(previous)['rows'],
            'previous_observation': reference(previous), 'evidence': reference(output/cid/'evidence.json'),
            'assessment': reference(output/cid/'assessment.json'),
            'effective_controls': report['effective_controls']})
    original_lane, _, original_operator = lane_records(original, 'spectre', ids)
    preflight_lane, _, preflight_operator = lane_records(spectre, 'spectre', ['EV-SH-01', 'CP-02'])
    old_tool = load(original_lane/'TOOL_IDENTITY.json')
    new_tool = load(preflight_lane/'TOOL_IDENTITY.json')
    assert old_tool['binary_sha256'] == new_tool['binary_sha256']
    assert old_tool['setup_sha256'] == new_tool['setup_sha256']
    for cid in ('EV-SH-01', 'CP-02'):
        before = original_lane/'runs'/cid/'tb.scs'
        expected = '\n'.join(line+' precision="%.17g"' if line.startswith('simulatorOptions ')
            else line+' skipcount=1 compression=no annotate=steps annotatedigits=16' if line.startswith('tran tran ')
            else line for line in before.read_text().splitlines())+'\n'
        assert (preflight_lane/'runs'/cid/'tb.scs').read_text() == expected
    spectre_rows = [native_facts(original_lane, c, data) for c in data['cards']]
    preflight = [native_facts(preflight_lane, c, data) for c in data['cards'] if c['id'] in ('EV-SH-01', 'CP-02')]
    assert all(r['precision_17g_readback'] for r in preflight)
    prior = ROOT/'experiments/backends/support/20261009-timegrid.json'
    return {'schema_version': 1,
        'claim': 'New EVAS execution assessed by unchanged finite core-v1 criteria; Spectre format preflight is separate and remains I. No full-domain or cross-backend equivalence claim.',
        'previous_receipt': {'path': str(prior.relative_to(ROOT)), 'sha256': sha(prior)},
        'source_revision': build['source_revision'], 'source_manifest': reference(evas/'SOURCE_MANIFEST.json'),
        'source_review': {'path': str(source_review.relative_to(ROOT)), 'sha256': sha(source_review), 'availability': 'repository-contained'},
        'build_record': reference(build_path), 'kernel_sha256': build['kernel_sha256'],
        'cargo_lock_sha256': build['cargo_lock_sha256'],
        'compiler_identity': {k: {n: v[n] for n in ('actual_binary_sha256', 'version')} for k, v in build['compiler_identity'].items()},
        'build_flags': ['--offline', '--locked', '--release', '-j', '1'],
        'counts': dict(collections.Counter(r['status'] for r in result)), 'evas': result,
        'spectre_original': spectre_rows, 'spectre_preflight': preflight,
        'operator_receipts': {'evas': operator, 'spectre_original': original_operator, 'spectre_preflight': preflight_operator},
        'tool_identities': {'evas': reference(lane/'TOOL_IDENTITY.json'), 'spectre': reference(preflight_lane/'TOOL_IDENTITY.json')},
        'new_configurations': 14, 'total_configurations_including_original': load(prior)['total_configurations_including_original']+14,
        'primary_conditions': 27, 'primary_slots': 108,
        'selection': 'Replace 12 EVAS core slots with this new execution; reuse other 36 original core slots and all 60 selected supplemental slots. Spectre 2-format preflights are diagnostics. Original I/X and all attempts remain retained.',
        'checked_in_analysis': {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__),
            ROOT/'experiments/backends/paper/actual_observation.py', ROOT/'experiments/backends/paper/observations.py',
            ROOT/'evas/validation/paper/criteria.py', ROOT/'evas/validation/paper/oracle.py', ROOT/'evas/validation/paper/core-v1.json']},
        'raw_availability': 'local-only; paths relative to repository root; raw archives retained locally and on the execution server'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('evas_run', 'spectre_run', 'original_run', 'source_review', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = summarize(*(getattr(args, n).resolve() for n in
        ('evas_run', 'spectre_run', 'original_run', 'source_review', 'output')))
    (args.output/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    print(json.dumps({'counts': report['counts'], 'new_configurations': report['new_configurations']}))
