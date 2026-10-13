"""EC04 reanalysis at the represented-input root, preserving historical grades.

The caller supplies externally reviewed producer identity. This wrapper does
not qualify a binary, manifest or export. Complete observed boxes reach the
unchanged composition reference, including sampling and later integral area.
"""
from copy import deepcopy
import math

import precision_breadth as science
from root_windows import reference_roots, reference_card, timing


ANALYSIS_ID = 'precision-composition-root-v3'


def _boxes(card, backend, response, log):
    """Extract observations for timing; extraction alone grants no evidence."""
    event = card['events'][0]
    if backend == 'evas':
        records = response['transient']['events']
        if len(records) != 1:
            raise ValueError('missing or extra committed callback')
        record = records[0]
        point = record['time']
        box = record.get('observation_time_bounds', [point, point])
    else:
        from breadth_callback_trace import parse
        records = parse(log)
        if len(records) != 1:
            raise ValueError('missing or repeated actual callback')
        point = float(records[0]['time_token'])
        box = [point, point]
    if (not isinstance(box, (list, tuple)) or len(box) != 2
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in [point, *box])
            or not 0 <= box[0] <= point <= box[1] <= card['stop_s']):
        raise ValueError('invalid complete callback box')
    return {event['id']: list(box)}


def _compose(assessment, resolved, timing_status, qualified):
    """Remove only replaced timing findings; preserve every other obligation."""
    behavior = assessment['behavior']
    behavior.setdefault('errors', [])
    behavior.setdefault('issues', [])
    keep = lambda values: [v for v in values if v not in resolved]
    if qualified and timing_status == 'pass':
        behavior['errors'] = keep(behavior['errors'])
        behavior['issues'] = keep(behavior['issues'])
        assessment['observation_issues'] = keep(assessment['observation_issues'])
    if timing_status == 'behavior_error':
        behavior['errors'].append('complete callback violates represented-input root window')
    elif timing_status != 'pass':
        behavior['issues'].append('complete callback root timing is unresolved')
    if not qualified:
        behavior['issues'].append('actual callback evidence is unqualified')
    behavior['status'] = ('behavior_error' if behavior['errors'] else
                          'unknown' if behavior['issues'] else 'pass')
    added = [v for v in behavior['issues'] if v not in assessment['observation_issues']]
    assessment['observation_issues'].extend(added)
    assessment['evidence'] = {'status': 'evidence_insufficient' if assessment['observation_issues'] else 'complete',
                              'issues': list(assessment['observation_issues'])}
    for tier in assessment['tiers'].values():
        issues = tier['evidence']['issues']
        if qualified and timing_status == 'pass':
            issues = keep(issues)
        issues = list(issues) + [v for v in added if v not in issues]
        tier['evidence'] = {'status': 'evidence_insufficient' if issues else 'complete', 'issues': issues}
        tier['behavior'] = deepcopy(behavior)
        tier['status'] = ('behavior_error' if behavior['errors'] else
                          'numerical_error' if tier['numerical']['status'] == 'numerical_error' else
                          'evidence_insufficient' if issues else tier['numerical']['status'])


def reanalyze(card, rows, contract, *, backend, producer_qualified=False,
              program=None, response=None, executed_source=None, log=None,
              format_version=2):
    """Return both assessments, full-box timing and separate strict semantics.

    Only canonical EC04-v1 is supported. The finite 16-ULP(stop) export budget
    is unchanged; a finite-resolution pass does not imply strict no-early.
    EVAS needs the original compiled program and response. Spectre needs the
    exact read-only instrumented source and complete callback log.
    """
    if backend not in ('evas', 'spectre'):
        raise ValueError('backend must be evas or spectre')
    roots = reference_roots(card)  # Reject source/physical-contract substitution.
    if card['id'] != 'EC04-v1':
        raise ValueError('only canonical EC04-v1 is supported')
    frozen = science.load_contract(cards=[card])
    for key in ('budgets', 'tiers', 'observation'):
        if contract[key] != frozen[key]:
            raise ValueError('frozen precision budgets differ: ' + key)
    ulps = contract['budgets']['time_serialization_ulps']
    old = science.assess(card, rows, contract)
    result = {'analysis_id': ANALYSIS_ID, 'original_assessment': old,
              'timing': {}, 'strict_semantic_timing': 'unresolved',
              'serialized_resolution_timing': 'evidence_insufficient'}
    try:
        boxes = _boxes(card, backend, response, log)
        checks = {e['id']: timing(root, boxes[e['id']], card['stop_s'], ulps)
                  for e, root in zip(card['events'], roots, strict=True)}
        result['timing'] = checks
        check = next(iter(checks.values()))
        result['strict_semantic_timing'] = check['strict_semantic_timing']
        result['serialized_resolution_timing'] = check['serialized_resolution_timing']
    except (ValueError, KeyError, TypeError, IndexError, ArithmeticError) as exc:
        boxes = None
        result['timing_reason'] = str(exc)
    # Adapter metadata is independent of observations and grants no acceptance.
    adapted = reference_card(card, ulps)
    if backend == 'evas':
        from callback_evidence import callbacks
        proof = callbacks(adapted, program, response, rows,
                          producer_qualified=producer_qualified)
    else:
        from spectre_callback_evidence import qualify
        proof = qualify(adapted, executed_source, log, rows,
                        producer_qualified=producer_qualified, format_version=format_version)
    result['callback_evidence'] = proof
    qualified = proof['status'] == 'qualified'
    status = result['serialized_resolution_timing']
    if qualified and status == 'pass' and proof['event_bounds_s'] == boxes:
        def actual_reference(c, t, unused):
            metadata = deepcopy(adapted)
            for key in ('reference_counter_stages', 'reference_event_stages', 'reference_time_uncertainty_s'):
                if key in c:
                    metadata[key] = deepcopy(c[key])
            return science._reference(card)(metadata, t, deepcopy(boxes))
        new = science.assess(card, rows, contract, reference=actual_reference)
        new['event_bounds_s'] = deepcopy(boxes)
    else:
        new = deepcopy(old)
        if qualified and proof['event_bounds_s'] != boxes:
            qualified = False
            result['callback_evidence'] = {'status': 'unknown', 'reason': 'qualified boxes differ from timing observations'}
    resolved = {prefix + e['id'] for e in card['events'] for prefix in
                ('full callback bracket does not fit legal window: ', 'callback outside legal window: ')}
    _compose(new, resolved, status, qualified)
    new['analysis_id'] = ANALYSIS_ID
    new['strict_semantic_timing'] = result['strict_semantic_timing']
    new['serialized_resolution_timing'] = status
    result['new_assessment'] = new
    return result


def reanalyze_evas(card, program, response, rows, contract, *, producer_qualified=False):
    return reanalyze(card, rows, contract, backend='evas', program=program,
                     response=response, producer_qualified=producer_qualified)


def reanalyze_spectre(card, executed_source, log, rows, contract, *, producer_qualified=False,
                      format_version=2):
    return reanalyze(card, rows, contract, backend='spectre', executed_source=executed_source,
                     log=log, producer_qualified=producer_qualified, format_version=format_version)
