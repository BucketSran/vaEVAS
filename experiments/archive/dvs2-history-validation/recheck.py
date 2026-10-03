"""Read-only reanalysis of v1 event waveforms under a new conditional method.

Only the output file is written. No simulator, network or model is invoked.
Raw values are checked under B=0 and candidate B=.25 mV sensitivity scenarios;
neither scenario asserts a qualified measurement bound for the historical data.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import sys

from history import Event, check_history, rational

ROOT = Path(__file__).resolve().parents[3]
PILOT = ROOT / 'experiments/archive/dvs2-starter-pilot'
sys.path.insert(0, str(PILOT))
from analyze import read_waveform  # Existing format reader only, not its oracle/checker.

CONDITION_IDS = ('v3-main', 'v4-c0', 'v4-c1', 'v5-main')
BACKENDS = ('spectre', 'evas', 'openvaf_ngspice', 'gnucap')
PROFILES = ('base', 'fine')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event_contract(condition_id):
    """Normalized x=t/(1 us), y in volts; exact constants from the v1 cards.

Independent of suite.events/reference. Start denotes output-edge start; for V5
it includes the fixed .1 T delay, so offsets still refer to the timer shift.
"""
    if condition_id == 'v3-main':
        return [Event(x, y, '1/20', 0, '1/2000')
                for x, y in [('11/8', '9/10'), ('27/8', '1/10')]]
    if condition_id in ('v4-c0', 'v4-c1'):
        result = [Event('23/20', '1/10', '1/40', 0, '1/50000')]
        for x in map(Q, ['1/2', '3/2', '5/2', '7/2']):
            if condition_id == 'v4-c1' and x == Q(3, 2):
                continue
            result.append(Event(x, Q(1, 5) + Q(3, 20) * x, '1/40', 0, '1/25000', '3/20'))
        return sorted(result, key=lambda event: event.start)
    if condition_id == 'v5-main':
        return [Event(Q(19, 40) + Q(3, 4) * n, '9/10' if n % 2 == 0 else '1/10',
                      '1/5' if n % 2 == 0 else '1/10', '-1/10000', '1/10000')
                for n in range(5)]
    raise ValueError('condition has no implemented history contract')


def exact_pwl(points, x):
    points = [(rational(t), rational(v)) for t, v in points]
    if any(a[0] >= b[0] for a, b in zip(points, points[1:])):
        raise ValueError('invalid stimulus knot ordering')
    if x <= points[0][0]:
        return points[0][1]
    for (left, a), (right, b) in zip(points, points[1:]):
        if x <= right:
            return a + (b - a) * (x - left) / (right - left)
    return points[-1][1]


def prepare_observations(rows, condition):
    """Validate the existing export contract without interpolating/deleting rows."""
    if not rows:
        raise ValueError('empty waveform')
    required = {'time', 'vout', *condition['inputs']}
    observations = []
    worst = {name: Q(0) for name in condition['inputs']}
    max_gap = Q(0)
    for row in rows:
        if not required.issubset(row):
            raise ValueError('missing required signal')
        values = {name: rational(row[name]) for name in required}
        x = values['time'] / Q(1, 1000000)
        if observations:
            gap = x - observations[-1][0]
            if gap <= 0:
                raise ValueError('unknown duplicate-time ordering or nonincreasing time')
            max_gap = max(max_gap, gap)
        for name, points in condition['inputs'].items():
            worst[name] = max(worst[name], abs(values[name] - exact_pwl(points, x)))
        observations.append((x, values['vout']))
    if len(observations) < 2 or abs(observations[0][0]) > Q(1, 10**9) or abs(observations[-1][0] - 4) > Q(1, 10**6):
        raise ValueError('incomplete extent or incorrect time units')
    if max_gap > Q(1001, 10**6):
        raise ValueError('export gap exceeds v1 1 ns allowance')
    if any(error > Q(1, 10**7) for error in worst.values()):
        raise ValueError('input mismatch; do not attribute it to the DUT')
    return observations, {'sample_count': len(rows), 'max_export_gap_s': float(max_gap / 10**6),
                          'input_max_error_v': {k: float(v) for k, v in worst.items()},
                          'input_between_exports_qualified': False,
                          'time_semantics_qualified': False}


def recheck(evidence):
    receipt_path = PILOT / 'results/ARCHIVE_RECEIPT.json'
    receipt = json.loads(receipt_path.read_text())
    manifest_path = evidence / 'FILE_MANIFEST.json'
    if digest(manifest_path) != receipt['file_manifest_sha256']:
        raise ValueError('historical file manifest does not match archive receipt')
    manifest = json.loads(manifest_path.read_text())
    bindings = {}

    def checked(relative):
        path = (evidence / relative).resolve()
        if not path.is_relative_to(evidence.resolve()):
            raise ValueError('evidence path escapes archive')
        expected = manifest.get(relative)
        actual = digest(path)
        if expected is None or actual != expected['sha256'] or path.stat().st_size != expected['bytes']:
            raise ValueError('historical artifact identity mismatch: ' + relative)
        bindings[relative] = actual
        return path

    frozen = json.loads((ROOT / 'evas/validation/versions/v1/conditions.json').read_text())
    conditions = {c['id']: c for c in frozen['conditions']}
    snapshot = json.loads((ROOT / 'evas/validation/versions/v1/manifest.json').read_text())
    for relative, sha in snapshot['snapshot_files'].items():
        if digest(ROOT / relative) != sha:
            raise ValueError('v1 snapshot artifact drift: ' + relative)
    for name in ('analyze.py', 'suite.py'):
        # The frozen identity names the path at the original run. Only the
        # maintained reader location moved; the original hash stays unchanged.
        original = 'experiments/dvs2-starter-pilot/' + name
        if digest(PILOT / name) != snapshot['git_files'][original]:
            raise ValueError('v1 reader dependency drift: ' + original)
    records = []
    for backend in BACKENDS:
        for condition_id in CONDITION_IDS:
            for profile in PROFILES:
                prefix = f'runs/{backend}/{condition_id}/{profile}/'
                run = json.loads(checked(prefix + 'result.json').read_text())
                if (run['backend'], run['condition'], run['profile']) != (backend, condition_id, profile):
                    raise ValueError('run identity disagrees with directory')
                condition = json.loads(checked(prefix + 'condition.json').read_text())
                if condition != conditions[condition_id]:
                    raise ValueError('condition differs from frozen v1')
                model = checked(prefix + 'dut.va')
                if digest(model) != run['source_sha256']:
                    raise ValueError('DUT does not match recorded execution')
                for name in ('requested_settings.json', 'tb.scs', 'tb.cir', 'tb.gc'):
                    checked(prefix + name)
                record = {'backend': backend, 'condition': condition_id, 'profile': profile,
                          'execution_status': run['status'], 'formal_dvs_qualification': 'I',
                          'reuse': 'not_reexecuted', 'history': None}
                if run['status'] == 'waveform_available':
                    waveform = checked(prefix + run['waveform'])
                    if digest(waveform) != run['waveform_sha256']:
                        raise ValueError('waveform does not match recorded execution')
                    try:
                        rows = read_waveform(waveform, backend)
                        observed, quality = prepare_observations(rows, condition)
                        record['observation_screen'] = quality
                        record['history'] = {
                            scenario: check_history(observed, event_contract(condition_id), initial='1/10',
                                                    epsilon='1/1000', uncertainty=bound)
                            for scenario, bound in [('exact_export_assumption', 0), ('candidate_budget_sensitivity', '1/4000')]
                        }
                        record['reuse'] = 'reanalyzed'
                    except (ValueError, KeyError, TypeError, IndexError) as exc:
                        record['observation_error'] = str(exc)
                records.append(record)
                if record['history']:
                    states = '/'.join(r['status'] for r in record['history'].values())
                    print(backend, condition_id, profile, states, flush=True)
    counts = {}
    for backend in BACKENDS:
        selected = [r for r in records if r['backend'] == backend]
        counts[backend] = {
            'configuration_count': len(selected),
            'waveforms_reanalyzed': sum(r['history'] is not None for r in selected),
            'execution_statuses': dict(Counter(r['execution_status'] for r in selected)),
            'scenarios': {scenario: dict(Counter(r['history'][scenario]['status'] for r in selected if r['history']))
                          for scenario in ('exact_export_assumption', 'candidate_budget_sensitivity')},
        }
    tracked_dependencies = [Path(__file__), Path(__file__).with_name('history.py'),
                            Path(__file__).with_name('test_history.py'), Path(__file__).with_name('test_recheck.py'),
                            PILOT / 'analyze.py', PILOT / 'suite.py',
                            ROOT / 'evas/validation/versions/v1/conditions.json']
    return {'analysis_id': 'dvs2-history-reanalysis-20260928', 'source_run_id': receipt['run_id'],
            'archive_receipt_sha256': digest(receipt_path), 'file_manifest_sha256': digest(manifest_path),
            'analyzer_sha256': {str(p.relative_to(ROOT)): digest(p) for p in tracked_dependencies},
            'scenario_scope': 'Conditional finite-observation compatibility only. Neither B is an established physical uncertainty bound.',
            'event_domain_scope': 'Nominal roots and v1 declared event windows; input/root/export uncertainty not qualified.',
            'new_simulator_runs': 0, 'formal_dvs_qualification': 'I',
            'counts': counts, 'records': records, 'verified_input_sha256': bindings,
            'limitations': ['No internal event count or continuous-time certification.',
                            'P is a rational witness for the chosen scenario, not proof of simulator correctness.',
                            'F excludes the specified scenario, not every possible physical uncertainty model.',
                            'V5 separate 1% timing measurements and interrupted transitions remain outside this implementation.',
                            'Missing waveforms retain their original execution failure; no fabricated trace.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    # Refuse to mutate the evidence archive, including through a symlink.
    if args.output.resolve().is_relative_to(args.evidence.resolve()):
        parser.error('output must be outside the evidence directory')
    if args.output.exists():
        parser.error('output already exists; choose a new analysis artifact')
    try:
        report = recheck(args.evidence)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print('Reanalysis failed: ' + str(exc), file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        stream.write(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report['counts'], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
