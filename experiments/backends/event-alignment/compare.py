"""Compare native observations without interpolation or an analytical oracle.

Finite agreement does not qualify source/export identities or continuous time.
Event windows classify differences; they never remove a failing observation.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def compare(contract, evas, spectre):
    budgets = contract['budgets_v']
    stop = contract['stop']
    required = contract['required_times']
    phases = contract.get('phase_nodes', [])
    windows = contract.get('event_windows_s', [])
    if (not budgets or any(not finite(v) or v < 0 for v in budgets.values())
            or not finite(stop) or stop <= 0
            or not required or any(not finite(t) or not 0 <= t <= stop for t in required)
            or required != sorted(set(required))
            or not set(phases) <= set(budgets)
            or any(len(w) != 2 or not all(finite(t) for t in w)
                   or not 0 <= w[0] <= w[1] <= stop for w in windows)):
        raise ValueError('invalid direct-comparison contract')
    result = dict(finite_pair_status='I', phase_status='I', formal_qualification='I',
                  native_rows=len(spectre.get('rows', [])), paired_rows=0,
                  paired_values=0, unpaired_native_rows=0, failed_values=0,
                  failed_inside_windows=0, failed_outside_windows=0,
                  phase_failed_values=0, worst={}, coverage_gaps=[],
                  missing_required_times={}, duplicate_times={},
                  scope='All native rows at identical parsed binary64 times; no interpolation. '
                        'Formal source/export/continuous-time qualification is not established.')
    gaps = result['coverage_gaps']

    def inspect(trace, name):
        rows = trace.get('rows', [])
        if not rows:
            gaps.append(name + ': no successful observations')
        valid = []
        for i, row in enumerate(rows):
            try:
                t, values = row['time'], row['voltages']
                if not finite(t) or not 0 <= t <= stop or not isinstance(values, dict):
                    raise ValueError('nonfinite/time outside domain or invalid voltage object')
            except (KeyError, TypeError, ValueError) as error:
                gaps.append(f'{name}: row {i}: {error}')
                continue
            observed = {n: values[n] for n in budgets if n in values and finite(values[n])}
            if len(observed) != len(budgets):
                gaps.append(f'{name}: row {i}: missing/nonfinite signals')
            # A bad column cannot erase another column's known mismatch.
            valid.append(dict(time=t, voltages=observed))
        times = [r['time'] for r in valid]
        if times != sorted(times):
            gaps.append(name + ': unordered observations')
        duplicates = sorted(t for t, count in Counter(times).items() if count > 1)
        result['duplicate_times'][name] = duplicates
        if duplicates:
            gaps.append(name + ': duplicate parsed time; observation phase is ambiguous')
        missing = sorted(set(required) - set(times))
        result['missing_required_times'][name] = missing
        if missing:
            gaps.append(name + ': missing required observation times')
        if not times or min(times) != 0 or max(times) != stop:
            gaps.append(name + ': missing exact parsed start/stop')
        return valid, set(duplicates)

    ev, duplicates = inspect(evas, 'evas')
    sp, _ = inspect(spectre, 'spectre')
    # Never choose one of several EVAS phases merely because it agrees better.
    by_time = {r['time']: r['voltages'] for r in ev if r['time'] not in duplicates}
    result['worst'] = {n: dict(error_v=0.0, time_s=None, evas_v=None, spectre_v=None)
                       for n in budgets}
    for row in sp:
        t = row['time']
        if t not in by_time:
            continue
        if len(by_time[t]) == len(budgets) and len(row['voltages']) == len(budgets):
            result['paired_rows'] += 1
        inside = any(a <= t <= b for a, b in windows)
        for n, budget in budgets.items():
            if n not in by_time[t] or n not in row['voltages']:
                continue
            ev_value, sp_value = by_time[t][n], row['voltages'][n]
            error = abs(ev_value - sp_value)
            result['paired_values'] += 1
            if error > result['worst'][n]['error_v']:
                result['worst'][n] = dict(error_v=error, time_s=t,
                                          evas_v=ev_value, spectre_v=sp_value)
            if error > budget:
                result['failed_values'] += 1
                result['failed_inside_windows' if inside else 'failed_outside_windows'] += 1
                result['phase_failed_values'] += int(n in phases)
    result['unpaired_native_rows'] = result['native_rows'] - result['paired_rows']
    result['unpaired_native_values'] = result['native_rows'] * len(budgets) - result['paired_values']
    if result['unpaired_native_rows']:
        gaps.append('unpaired native rows remain in the comparison denominator')
    # A known mismatch remains F even when other observations are unavailable.
    result['finite_pair_status'] = 'F' if result['failed_values'] else 'I' if gaps else 'P'
    result['phase_status'] = ('F' if result['phase_failed_values'] else
                              'I' if gaps or not phases else 'P')
    return result


def main():
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            self.exit(3, json.dumps(dict(status='ERROR', reason=message)) + '\n')

    parser = Parser(description=__doc__)
    for name in ['contract', 'evas', 'spectre', 'output']:
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    paths = [args.contract, args.evas, args.spectre]
    try:
        report = compare(*(json.loads(p.read_text()) for p in paths))
        report['identities'] = {name: dict(path=str(p.resolve()),
                                         sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                                for name, p in zip(['contract', 'evas', 'spectre', 'comparator'],
                                                   paths + [Path(__file__)])}
        encoded = json.dumps(report, indent=2, allow_nan=False) + '\n'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=args.output.parent,
                                             prefix='.compare-', delete=False) as file:
                temporary = Path(file.name)
                file.write(encoded)
            # Publish only a complete file. Hard-link creation is atomic and
            # refuses an existing result, unlike replace/rename overwrites.
            os.link(temporary, args.output)
        finally:
            if temporary is not None:
                temporary.unlink()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError) as error:
        print(json.dumps(dict(status='ERROR', kind=type(error).__name__, reason=str(error))),
              file=sys.stderr)
        return 3
    print(report['finite_pair_status'])
    return {'P': 0, 'F': 1, 'I': 2}[report['finite_pair_status']]


if __name__ == '__main__':
    raise SystemExit(main())
