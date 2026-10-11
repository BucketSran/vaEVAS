"""Supplementary callback observations and separate numerical/evidence verdicts."""
import math
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'evas/validation/paper'))
sys.path.insert(0, str(ROOT / 'experiments/backends/paper'))
from precision_v2 import rows_digest
from inputs import sha
from precision_binding_run import TRACE


def callback_trace(card, source, log, rows):
    """Only the reviewed single-instance Spectre strobe instrumentation is allowed.

    Keep every trace line. Match it to the same run's accepted counter transition
    and sampled input, not a requested time or a predicted root. The v2 checker
    separately checks legal time windows and clock-root uncertainty.
    """
    expected = card['source'].replace('n=n+1; end', 'n=n+1; ' + TRACE + ' end')
    if source != expected or source.count(TRACE) != 1:
        raise ValueError('unreviewed instrumentation/model identity')
    lines = [s.strip() for s in log.splitlines() if 'EVAS_CALLBACK' in s]
    pattern = re.compile(r'EVAS_CALLBACK (\d+) ([+\-0-9.eE]+)')
    parsed = []
    for line in lines:
        match = pattern.fullmatch(line)
        if not match: raise ValueError('malformed or mixed callback trace')
        index, t = int(match[1]), float(match[2])
        if not math.isfinite(t): raise ValueError('nonfinite callback time')
        token = match[2]
        # VAMS 2.4 sections 3.2/9.10 specify binary64 real/$abstime;
        # Spectre 21.1's real-to-C-double interface confirms the representation.
        # Seventeen significant digits uniquely recover the machine argument.
        # This is not an exact mathematical root or a zero solver-error claim.
        if (format(t, '.17g') != token or
                any(format(math.nextafter(t, side), '.17g') == token for side in (-math.inf, math.inf))):
            raise ValueError('callback token is not canonical binary64 roundtrip output')
        parsed.append((index, t))
    if [i for i, t in parsed] != list(range(1, card['expected_events'] + 1)):
        raise ValueError('missing, repeated, reordered or extra callback index')
    if any(b[1] <= a[1] for a, b in zip(parsed, parsed[1:])):
        raise ValueError('callback time is not increasing')
    # Never deduplicate retries. Each logged state change must have its accepted
    # same-time output record, and no unlogged state change may remain.
    changes = [(a, b) for a, b in zip(rows, rows[1:]) if round(a['count']) != round(b['count'])]
    if len(changes) != len(parsed): raise ValueError('callback/native transition count differs')
    events = []
    for (index, t), (before, after) in zip(parsed, changes):
        if (round(before['count']) != index - 1 or round(after['count']) != index or
                after['time'] != t or before['time'] >= t):
            raise ValueError('callback has no same-time accepted counter transition')
        # These fixtures sample u directly. This checks the observation mapping;
        # the independent reference still checks the actual voltage accuracy.
        allowance = 16 * math.ulp(max(card['scale_V'], abs(after['u']), abs(after['y'])))
        if abs(after['y'] - after['u']) > allowance:
            raise ValueError('callback record does not contain sampled input')
        events.append({'index': index, 'time_bounds_s': [t, t]})
    return {'method': 'independent_callback_trace', 'events': events,
            'waveform_rows_sha256': rows_digest(rows),
            'scope': 'reviewed single-instance strobe at committed counter change; no trial deduplication',
            'representation': 'binary64-roundtrip-v1; actual machine timestamp, not exact mathematical root',
            'type_basis': 'VAMS 2.4 sections 3.2 and 9.10; Spectre 21.1 Verilog-A C interface real maps to double',
            'standard_url': 'https://accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2-4.pdf'}


def axes(assessment, qualification):
    """Numerical bounded error and completeness are deliberately independent."""
    output = {}
    for tier, result in assessment['tiers'].items():
        budget = result.get('voltage_budget_V')
        if (budget is None or 'error_upper_V' not in assessment or
                any(s in issue for issue in assessment.get('behavior', {}).get('issues', [])
                    for s in ('counter is not', 'initial/final count', 'missing holding stage'))):
            numerical = 'unavailable'
        elif max(assessment['error_lower_V'], assessment['hold_drift_lower_V']) > budget:
            numerical = 'numerical_error'
        elif max(assessment['error_upper_V'], assessment['hold_drift_upper_V']) <= budget:
            numerical = 'pass'
        else:
            numerical = 'indeterminate'
        evidence_reasons = list(assessment.get('observation_issues', [])) + qualification['issues']
        evidence_reasons += [r for r in result['reasons'] if any(s in r for s in
                            ('uncertainty', 'bracket', 'overlaps', 'input error'))]
        output[tier] = {'numerical': numerical,
                        'behavior': assessment.get('behavior', {}).get('status', 'unknown'),
                        'evidence': 'incomplete' if evidence_reasons else 'complete',
                        'evidence_reasons': list(dict.fromkeys(evidence_reasons)),
                        'status': 'pass' if result['status'] == 'pass' and not qualification['issues']
                                  else result['status'] if result['status'] != 'pass' else 'evidence_insufficient',
                        'voltage_budget_V': budget}
    return output


def complete_boundary_search(card, rows, assessment, contract):
    """Supplement v2's nearest-two-point search without altering its criteria.

    Retain every native value for numerical scoring. Clear a missing-side claim
    only when the full original permitted interval contains both required sides.
    The original assessment is not mutated; caller records each new witness.
    """
    import copy
    from bisect import bisect_left, bisect_right
    from precision_v2 import critical_points
    result = copy.deepcopy(assessment)
    times = [r['time'] for r in rows]
    ut = result.get('time_serialization_bound_s')
    if ut is None: return result, []
    distance = contract['budgets']['boundary_distance_s']
    witnesses = []
    for point in critical_points(card):
        t = point['time_s']; reason = 'missing boundary sides: ' + point['id']
        if reason not in result.get('observation_issues', []): continue
        left = bisect_left(times, t - ut) - 1
        right = bisect_right(times, t + ut)
        if (left >= 0 and right < len(times) and
                t - distance - ut <= times[left] < t - ut and
                t + ut < times[right] <= t + distance + ut):
            witnesses.append({'boundary': point['id'], 'time_s': t,
                              'left_s': times[left], 'right_s': times[right],
                              'distance_s': distance, 'serialization_bound_s': ut})
            result['observation_issues'].remove(reason)
            for tier in result['tiers'].values():
                tier['reasons'] = [r for r in tier['reasons'] if r != reason]
                if (tier['status'] == 'evidence_insufficient' and not tier['reasons'] and
                        max(result['error_upper_V'], result['hold_drift_upper_V']) <= tier['voltage_budget_V']):
                    tier['status'] = 'pass'
    return result, witnesses


def qualify_ngspice_step(qualification, requested, tool, evidence):
    """Apply a reviewed installed-binary parameter-path proof, never a deck echo."""
    import copy
    import json
    q = copy.deepcopy(qualification)
    try:
        image = tool['images']['ngspice']['config_id']
        for key in ('artifact', 'review'):
            ref = evidence[key]; path = (ROOT / ref['path']).resolve()
            if not path.is_relative_to(ROOT) or sha(path) != ref['sha256']:
                raise ValueError('audit attachment changed')
        audit = json.loads((ROOT / evidence['artifact']['path']).read_text())
        if (audit['method'] != 'installed_binary_parameter_path' or
                audit['mapping'] != 'ngspice-explicit-tmax-v1' or audit['image_id'] != image or
                audit['binary_sha256'] != 'e9b0e776ac656de5e470f6b339c4a7254c961d77714b4b94f4b71be2422e7b46' or
                set(audit['controls']) != {'maxstep', 'stop'} or not evidence['review']['reviewer']):
            raise ValueError('unreviewed parameter mapping/identity')
        for name, expected in audit['attachments'].items():
            path = (ROOT / name).resolve()
            if not path.is_relative_to(ROOT) or sha(path) != expected:
                raise ValueError('binary audit input changed')
        if not audit['attachments'] or requested['maxstep_s'] <= 0 or requested['stop_s'] <= 0:
            raise ValueError('only explicit positive TMAX/stop supported')
    except (OSError, ValueError, KeyError, TypeError):
        return q
    removable = {'maxstep/stop have no runtime echo or verified installed-version parameter path',
                 'audited maxstep/stop mapping is not implemented for this backend'}
    q['issues'] = [s for s in q['issues'] if s not in removable]
    q['step_setting_evidence'] = evidence
    q['mapped_controls'] = {'maxstep_s': requested['maxstep_s'], 'stop_s': requested['stop_s'],
        'basis': 'reviewed exact installed-binary parser/job/transient path; not a runtime echo',
        'scope': 'positive explicit TMAX with frozen unmodified deck; not a proof of every floating time difference'}
    q['status'] = 'qualified' if not q['issues'] else 'evidence_insufficient'
    return q
