#!/usr/bin/env python3
"""N04 evidence-only observation helper (no pass/fail verdict).

This module is validation-side tooling.  It implements the minimum contract of
the independent N04 review (``review/astra-n04/REPORT.md``): strict structural
validation of already-archived observation artifacts, complete preservation of
native callback/display material, per-query per-side provenance
(``native_saved`` / ``interpolated`` / ``unavailable``), declared-source
coverage evidence, and separate requested/effective controls.  It deliberately
produces **no** behavioral pass verdict, no default tolerance, and no
native/certified/integration qualification: ``invalid``, ``incomplete`` and
``unqualified`` states stay distinguishable, and missing records stay missing.

Distinctions honored throughout
-------------------------------
* ``invalid``    -- structural failure: non-finite/non-numeric/bool value, wrong
                    type or shape, duplicate node, duplicate or decreasing
                    saved times, decreasing event times, lo>hi bounds.  Such
                    evidence never enters any numeric summary.
* ``incomplete`` -- a required record is partially absent (missing required
                    node column, missing expected rows, unbound display
                    record, absent requested controls); the denominator is
                    never silently shrunk.
* ``unqualified``-- a quantity exists but has no approved certificate (e.g.
                    reference-side native precision, declared-source interval
                    ranges).  It is reported, not promoted.
* ``missing``    -- an optional artifact was not supplied; absence is recorded
                    verbatim and never inferred from another field.

Declared PWL sources and simulator samples are distinct objects: declared
knots are coverage evidence against the save grid; saved values are compared
to the declared source only as reported deviations.  Point values derived from
a declared PWL carry ``origin: derived_from_declared_source`` and are exact
binary64-rational values; interval ranges are returned ``unqualified`` (an
auditable certification envelope is a coordinator decision, not invented here).

Only the Python standard library is used; no production module is imported.
"""
from fractions import Fraction
import bisect
import hashlib
import math

SCHEMA = 'evas-observation-evidence/1'

VALID = 'valid'
INVALID = 'invalid'
INCOMPLETE = 'incomplete'
UNQUALIFIED = 'unqualified'
MISSING = 'missing'

# Worst-first ordering used to combine component statuses.  A absent optional
# artifact (``missing``) never dominates a present-but-flawed one.
_STATUS_RANK = {VALID: 0, MISSING: 1, UNQUALIFIED: 1, INCOMPLETE: 2, INVALID: 3}

SAMPLE_ORIGIN_KINDS = frozenset({
    'stateless_working_point', 'accepted_controller_frame',
    'certified_causal_frame', 'implicit_history_evaluation', 'unknown'})

_PROVENANCE_NOTE = (
    'provenance only; native_saved does not certify query precision and '
    'interpolated values are linear resampling of saved rows, never native '
    'queries')


def worst_status(statuses):
    """Combine component statuses; a structural failure dominates."""
    return max(statuses, key=lambda s: _STATUS_RANK.get(s, _STATUS_RANK[INVALID]))


def _finite(value):
    try:
        return (not isinstance(value, bool) and isinstance(value, (int, float))
                and math.isfinite(value))
    except OverflowError:
        return False


def _json_safe(value):
    """Keep invalid numbers explicit without emitting non-standard JSON.

    Valid data remain verbatim. The original artifact, identified by its hash,
    remains the authoritative byte record for malformed data.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return {'invalid_numeric_token': repr(value)}
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _valid_pwl(points):
    return (isinstance(points, list) and bool(points)
            and all(isinstance(p, (list, tuple)) and len(p) == 2
                    and all(_finite(x) for x in p) for p in points)
            and all(a[0] < b[0] for a, b in zip(points, points[1:])))


def _finite_approx(exact):
    """Diagnostic approximation; retain the exact rational separately."""
    try:
        value = float(exact)
        return value if math.isfinite(value) else None
    except OverflowError:
        return None


def _issue(kind, detail, **where):
    record = {'kind': kind, 'detail': detail}
    record.update(where)
    return record


def sha256_file(path):
    """Digest of an input artifact, for identity preservation in reports."""
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


# ---------------------------------------------------------------------------
# Saved waveform adapter (per side)
# ---------------------------------------------------------------------------

class SavedWaveform:
    """Strict validated view of one side's saved waveform block.

    ``saved`` follows the public response schema ``{'nodes', 'times',
    'values'}``.  Validation happens once, up front: finiteness, types, shape,
    node uniqueness and strictly increasing times.  ``classify`` never
    re-derives validity and never extends the end value for out-of-range
    queries (those are ``unavailable``, not extrapolations).
    """

    def __init__(self, saved, *, side, required_nodes=(), expected_row_count=None,
                 require_full_coverage=False):
        if not isinstance(saved, dict):
            saved = {}
        self.side = side
        self.required_nodes = list(required_nodes)
        self.expected_row_count = expected_row_count
        self.require_full_coverage = require_full_coverage
        self.issues = []
        self.nodes = saved.get('nodes')
        self.times = saved.get('times')
        self.values = saved.get('values')
        status = self._validate(saved)
        self.status = worst_status([status, self._completeness()])
        self.saved = saved
        if status == INVALID:
            self.times = None
            self.values = None

    def _validate(self, saved):
        nodes, times, values = self.nodes, self.times, self.values
        if (not isinstance(nodes, list) or not nodes
                or any(not isinstance(n, str) or not n for n in nodes)):
            self.issues.append(_issue('invalid_nodes',
                                      'nodes must be a non-empty list of names'))
            return INVALID
        if len(set(nodes)) != len(nodes):
            self.issues.append(_issue('duplicate_node',
                                      'saved nodes contain duplicates',
                                      nodes=nodes))
            return INVALID
        if (not isinstance(times, list) or not times
                or any(not _finite(t) for t in times)):
            self.issues.append(_issue('invalid_times',
                                      'saved times must be finite numbers'))
            return INVALID
        for a, b in zip(times, times[1:]):
            if b == a:
                self.issues.append(_issue('duplicate_time',
                                          'saved time is not strictly increasing',
                                          time=a))
                return INVALID
            if b < a:
                self.issues.append(_issue('non_monotonic_times',
                                          'saved times must be strictly increasing',
                                          first_decrease=[a, b]))
                return INVALID
        if not isinstance(values, list) or len(values) != len(times):
            self.issues.append(_issue('row_count_mismatch',
                                      'values rows must match times exactly',
                                      times=len(times), values=len(values)
                                      if isinstance(values, list) else None))
            return INVALID
        width = len(nodes)
        for i, row in enumerate(values):
            if (not isinstance(row, list) or len(row) != width
                    or any(not _finite(v) for v in row)):
                bad = None
                if isinstance(row, list) and len(row) == width:
                    bad = nodes[next(j for j, v in enumerate(row) if not _finite(v))]
                self.issues.append(_issue(
                    'invalid_row',
                    'saved row must be a finite numeric vector of width %d' % width,
                    row_index=i, node=bad))
                return INVALID
        return VALID

    def _completeness(self):
        if self.nodes is None or not isinstance(self.nodes, list):
            return INCOMPLETE
        incomplete = False
        missing = [n for n in self.required_nodes if n not in self.nodes]
        if missing:
            self.issues.append(_issue('missing_required_nodes',
                                      'required nodes absent from saved waveform',
                                      missing=missing))
            incomplete = True
        if (self.expected_row_count is not None and isinstance(self.times, list)
                and len(self.times) != self.expected_row_count):
            self.issues.append(_issue('unexpected_row_count',
                                      'saved row count differs from the contract',
                                      expected=self.expected_row_count,
                                      actual=len(self.times)))
            incomplete = True
        return INCOMPLETE if incomplete else VALID

    # -- queries ----------------------------------------------------------
    def classify(self, time, node, declared_points=None, observation=None):
        """Provenance of one (time, node) query on this side's save grid.

        ``observation`` is the validated observation-evidence block of the same
        response (or ``None``); sample origin and voltage bounds are attached
        to ``native_saved`` rows only where they are genuinely present.
        """
        if self.status == INVALID or not isinstance(self.nodes, list) or node not in self.nodes:
            return {'status': MISSING, 'note': 'no validated saved grid'}
        i = bisect.bisect_left(self.times, time)
        if i < len(self.times) and self.times[i] == time:
            out = {'status': 'native_saved', 'row_index': i, 'side': self.side,
                   'value_v': self.values[i][self.nodes.index(node)],
                   'note': _PROVENANCE_NOTE}
            if observation is None:
                out['sample_origin'] = MISSING
                out['voltage_bounds_V'] = MISSING
            else:
                source_row = observation.saved_rows.get(i)
                out['sample_origin'] = (observation.sample_origin(source_row)
                                        if source_row is not None else MISSING)
                out['voltage_bounds_V'] = (observation.voltage_bound(source_row, node)
                                           if source_row is not None else MISSING)
            return out
        if i == 0:
            return {'status': 'unavailable', 'side': self.side,
                    'reason': 'before_first_saved_row', 'first_time_s': self.times[0]}
        if i == len(self.times):
            return {'status': 'unavailable', 'side': self.side,
                    'reason': 'after_last_saved_row', 'last_time_s': self.times[-1]}
        a, b = i - 1, i
        out = {'status': 'interpolated', 'side': self.side,
               'row_indices': [a, b], 'endpoint_times_s': [self.times[a], self.times[b]],
               'method': 'linear_interpolation_of_saved_rows',
               'value_v': self._interpolate(a, b, time, node),
               'note': _PROVENANCE_NOTE}
        if declared_points is not None:
            straddled = [k for k, _ in declared_points
                         if self.times[a] < k < self.times[b]]
            if straddled:
                out['straddled_declared_knots_s'] = straddled
        return out

    def _interpolate(self, a, b, time, node):
        j = self.nodes.index(node)
        ta, tb = self.times[a], self.times[b]
        va, vb = self.values[a][j], self.values[b][j]
        weight = (Fraction(time) - Fraction(ta)) / (Fraction(tb) - Fraction(ta))
        return float((1 - weight) * Fraction(va) + weight * Fraction(vb))


# ---------------------------------------------------------------------------
# Observation-evidence block (response schema, validated standalone)
# ---------------------------------------------------------------------------

class ObservationEvidence:
    """Schema-aware view of ``response['observation_evidence']``.

    Mirrors the transport checks of ``evas.src.evas.protocol`` (schema 1)
    without importing production code and without granting qualification:
    finite transport bounds stay transport facts, never certified precision.
    """

    def __init__(self, evidence, *, nodes, solutions=None, output_times=None):
        self.status = VALID
        self.issues = []
        self.evidence = evidence
        self.saved_rows = {}
        self.nodes = nodes
        self.solutions = solutions
        self.output_times = output_times
        self.present = isinstance(evidence, dict)
        if not self.present:
            self.issues.append(_issue('observation_evidence_missing',
                                      'response carries no observation evidence; '
                                      'absence is preserved, not inferred'))
            self.status = MISSING
            return
        if (not isinstance(nodes, list) or not nodes
                or any(not isinstance(n, str) or not n for n in nodes)
                or len(set(nodes)) != len(nodes)
                or not isinstance(output_times, list) or not output_times
                or any(not _finite(t) for t in output_times)
                or any(a >= b for a, b in zip(output_times, output_times[1:]))
                or not isinstance(solutions, list) or len(solutions) != len(output_times)
                or any(not isinstance(row, dict)
                       or not isinstance(row.get('voltages'), list)
                       or len(row['voltages']) != len(nodes)
                       or any(not _finite(v) for v in row['voltages'])
                       for row in solutions)):
            self.issues.append(_issue('invalid_output_solutions',
                                      'output times, nodes and finite solution rows must correspond'))
            self.status = INVALID
            return
        if (type(evidence.get('schema_version')) is not int
                or evidence['schema_version'] != 1
                or evidence.get('nodes') != list(nodes)):
            self.issues.append(_issue('invalid_observation_identity',
                                      'observation evidence identity mismatch'))
            self.status = INVALID
            return
        controls = evidence.get('effective_controls')
        if not isinstance(controls, dict):
            self.issues.append(_issue('invalid_effective_controls',
                                      'effective controls must be an object'))
            self.status = INVALID
            return
        for key in ('absolute_V', 'stop_s', 'max_step_s'):
            if not _finite(controls.get(key)) or controls[key] <= 0:
                self.issues.append(_issue('invalid_effective_controls',
                                          'effective control must be finite and positive',
                                          control=key))
                self.status = INVALID
        if not _finite(controls.get('relative')) or controls['relative'] < 0:
            self.issues.append(_issue('invalid_effective_controls',
                                      'effective relative tolerance must be finite '
                                      'and nonnegative'))
            self.status = INVALID
        if type(controls.get('max_step_applied')) is not bool:
            self.issues.append(_issue('invalid_effective_controls',
                                      'max_step_applied must be a boolean'))
            self.status = INVALID
        origins = evidence.get('sample_origins')
        if (not isinstance(origins, list) or not origins
                or any(not isinstance(o, str) or o not in SAMPLE_ORIGIN_KINDS
                       for o in origins)):
            self.issues.append(_issue('invalid_sample_origins',
                                      'sample origins must be known kinds'))
            self.status = INVALID
        elif solutions is not None and len(origins) != len(solutions):
            self.issues.append(_issue('sample_origin_count',
                                      'sample origins must match solution rows'))
            self.status = INVALID
        if 'initial_settled' in evidence and evidence['initial_settled'] is not None:
            if (evidence['initial_settled'] is not True or not output_times
                    or output_times[0] != 0):
                self.issues.append(_issue('invalid_initial_settlement',
                                          'initial_settled must be True with a '
                                          'zero-leading output grid'))
                self.status = INVALID
        bounds = evidence.get('voltage_bounds_V')
        if not isinstance(bounds, list):
            self.issues.append(_issue('invalid_voltage_bounds',
                                      'voltage bounds must be an array'))
            self.status = INVALID
        else:
            if solutions is not None and len(bounds) != len(solutions):
                self.issues.append(_issue('voltage_bounds_count',
                                          'voltage bounds must match solution rows'))
                self.status = INVALID
            names = list(nodes)
            for i, row in enumerate(bounds):
                if row is None:
                    continue
                if not isinstance(row, list) or len(row) != len(names):
                    self.issues.append(_issue('invalid_voltage_bounds',
                                              'voltage bounds row has wrong width',
                                              row_index=i))
                    self.status = INVALID
                    continue
                for name, interval in zip(names, row):
                    if (not isinstance(interval, list) or len(interval) != 2
                            or not _finite(interval[0]) or not _finite(interval[1])
                            or interval[0] > interval[1]):
                        self.issues.append(_issue(
                            'invalid_voltage_bounds',
                            'voltage bounds must be finite with lo<=hi '
                            '(exact point intervals lo==hi are legal)',
                            row_index=i, node=name))
                        self.status = INVALID
                if self.status != INVALID and i < len(solutions):
                    for name, interval, value in zip(names, row, solutions[i]['voltages']):
                        if not interval[0] <= value <= interval[1]:
                            self.issues.append(_issue(
                                'uncontained_representative',
                                'solution voltage outside its own bounds row',
                                row_index=i, node=name))
                            self.status = INVALID

    def bind_saved(self, saved):
        """Bind evidence by exact time, node and representative, never row index."""
        if self.status != VALID or saved.status == INVALID:
            return
        index = {t: i for i, t in enumerate(self.output_times)}
        mapping = {}
        for i, (time, values) in enumerate(zip(saved.times, saved.values)):
            row = index.get(time)
            if row is None or any(n not in self.nodes for n in saved.nodes):
                self.issues.append(_issue('saved_evidence_mismatch',
                                          'saved row lacks an exact output time/node match', row_index=i))
                self.status = INVALID
                return
            actual = self.solutions[row]['voltages']
            if any(v != actual[self.nodes.index(n)] for n, v in zip(saved.nodes, values)):
                self.issues.append(_issue('saved_evidence_mismatch',
                                          'saved representative differs from its output solution', row_index=i))
                self.status = INVALID
                return
            mapping[i] = row
        self.saved_rows = mapping

    def sample_origin(self, row_index):
        if not self.present or self.status == INVALID:
            return MISSING
        origins = self.evidence.get('sample_origins')
        if not isinstance(origins, list) or row_index >= len(origins):
            return MISSING
        return origins[row_index]

    def voltage_bound(self, row_index, node):
        if not self.present or self.status == INVALID:
            return MISSING
        bounds = self.evidence.get('voltage_bounds_V')
        if (not isinstance(bounds, list) or row_index >= len(bounds)
                or bounds[row_index] is None or node not in self.evidence['nodes']):
            return MISSING
        return bounds[row_index][list(self.evidence['nodes']).index(node)]

    def effective_controls(self):
        if not self.present or self.status == INVALID:
            return {'state': MISSING}
        return dict(self.evidence['effective_controls'])


# ---------------------------------------------------------------------------
# Callback / display preservation
# ---------------------------------------------------------------------------

def preserve_events(transient_block):
    """Verbatim preservation of event records with schema-aware validation.

    Keeps original order, event/leaf identity, times, top-level and leaf time
    bounds, guard values, before/after states and origins.  Validates finite
    values, types, bound shapes (``lo<=hi``; exact point intervals are legal)
    and non-decreasing chronology -- same-time events are legal and keep their
    order.  Completeness against the request/IR cannot be verified from the
    response alone and is reported as such, never assumed.
    """
    issues = []
    if not isinstance(transient_block, dict):
        return (MISSING if transient_block is None else INVALID), issues, {'records': MISSING}
    state_names = transient_block.get('state_names')
    names_valid = (isinstance(state_names, list)
                   and all(isinstance(n, str) and bool(n) for n in state_names)
                   and len(set(state_names)) == len(state_names))
    width = len(state_names) if names_valid else None
    if width is None:
        issues.append(_issue('state_width_unknown',
                             'state_names absent; state vector widths not verified'))
    events = transient_block.get('events')
    if not isinstance(events, list):
        issues.append(_issue('invalid_events', 'events must be an array'))
        return INVALID, issues, {'records': MISSING}
    status = INCOMPLETE if width is None else VALID
    if 'state_names' in transient_block and not names_valid:
        issues.append(_issue('invalid_state_names', 'state names must be unique nonempty strings'))
        status = INVALID
    records = []
    previous = None
    for index, event in enumerate(events):
        record = {'record_index': index, 'verbatim': event}
        records.append(record)
        if not isinstance(event, dict):
            issues.append(_issue('invalid_event', 'event must be an object',
                                 record_index=index))
            status = INVALID
            continue
        if not _finite(event.get('time')):
            issues.append(_issue('invalid_event_time',
                                 'event time must be a finite number',
                                 record_index=index))
            status = INVALID
        elif previous is not None and event['time'] < previous:
            issues.append(_issue('event_chronology',
                                 'event times must be non-decreasing '
                                 '(same-time events are legal)',
                                 record_index=index))
            status = INVALID
        else:
            previous = event['time']
        if (type(event.get('event')) is not int or event['event'] < 0
                or not isinstance(event.get('origin'), str)
                or not isinstance(event.get('kind'), str)):
            issues.append(_issue('invalid_event_identity',
                                 'event index/origin/kind have wrong types',
                                 record_index=index))
            status = INVALID
        for key in ('before', 'after'):
            vector = event.get(key)
            if (not isinstance(vector, list)
                    or any(not _finite(v) for v in vector)
                    or width is not None and len(vector) != width):
                issues.append(_issue('invalid_event_states',
                                     'event %s must be a finite state vector' % key,
                                     record_index=index))
                status = INVALID
        if 'guard_value' in event and not _finite(event['guard_value']):
            issues.append(_issue('invalid_guard_value',
                                 'guard value must be finite', record_index=index))
            status = INVALID
        bounds = event.get('observation_time_bounds')
        if 'observation_time_bounds' in event and (not isinstance(bounds, list) or len(bounds) != 2
                                   or not _finite(bounds[0]) or not _finite(bounds[1])
                                   or bounds[0] > bounds[1]):
            issues.append(_issue('invalid_time_bounds',
                                 'observation_time_bounds must be finite lo<=hi',
                                 record_index=index))
            status = INVALID
        fired = event.get('fired_triggers', [])
        if not isinstance(fired, list):
            issues.append(_issue('invalid_fired_triggers',
                                 'fired_triggers must be an array',
                                 record_index=index))
            status = INVALID
            continue
        for leaf in fired:
            if (not isinstance(leaf, dict) or type(leaf.get('trigger')) is not int
                    or leaf['trigger'] < 0
                    or not isinstance(leaf.get('kind'), str)):
                issues.append(_issue('invalid_fired_trigger',
                                     'fired trigger identity has wrong types',
                                     record_index=index))
                status = INVALID
                continue
            if 'guard_value' in leaf and not _finite(leaf['guard_value']):
                issues.append(_issue('invalid_guard_value',
                                     'fired trigger guard value must be finite',
                                     record_index=index))
                status = INVALID
            leaf_bounds = leaf.get('time_bounds')
            if 'time_bounds' in leaf and (not isinstance(leaf_bounds, list)
                                            or len(leaf_bounds) != 2
                                            or not _finite(leaf_bounds[0])
                                            or not _finite(leaf_bounds[1])
                                            or leaf_bounds[0] > leaf_bounds[1]):
                issues.append(_issue('invalid_time_bounds',
                                     'fired trigger time_bounds must be finite lo<=hi',
                                     record_index=index))
                status = INVALID
    return status, issues, {
        'records': records,
        'count': len(events),
        'completeness': 'not_verified_without_request_or_ir',
        'preservation': 'verbatim (order, event/leaf identity, times, top-level '
                        'and leaf time bounds, guards, before/after, origin)',
    }


def preserve_displays(transient_block, events_payload):
    """Verbatim display-record preservation with in-response linkage checks."""
    issues = []
    if not isinstance(transient_block, dict):
        return INVALID, issues, {'records': MISSING}
    if 'display_records' not in transient_block:
        return MISSING, issues, {'records': MISSING, 'state': MISSING}
    displays = transient_block['display_records']
    if not isinstance(displays, list):
        issues.append(_issue('invalid_displays', 'display records must be an array'))
        return INVALID, issues, {'records': displays}
    status = VALID
    committed = None
    records = []
    for index, record in enumerate(displays):
        records.append({'record_index': index, 'verbatim': record})
        if not isinstance(record, dict):
            issues.append(_issue('invalid_display', 'display record must be an object',
                                 record_index=index))
            status = INVALID
            continue
        if (not _finite(record.get('time')) or type(record.get('event')) is not int
                or record['event'] < 0
                or not isinstance(record.get('origin'), str) or not record['origin']
                or not isinstance(record.get('text'), str)):
            issues.append(_issue('invalid_display',
                                 'display time/event/origin/text have wrong types',
                                 record_index=index))
            status = INVALID
            continue
        if committed is None and isinstance(events_payload.get('records'), list):
            committed = [(e['verbatim'].get('event'), e['verbatim'].get('time'))
                         for e in events_payload['records']
                         if isinstance(e.get('verbatim'), dict)]
        if committed is not None and (record['event'], record['time']) not in committed:
            issues.append(_issue('unbound_display_record',
                                 'display record has no committed event with the '
                                 'same index and time', record_index=index))
            status = INCOMPLETE if status == VALID else status
    return status, issues, {'records': records, 'count': len(displays),
                            'preservation': 'verbatim (order, text, linkage)'}


# ---------------------------------------------------------------------------
# Declared PWL sources (distinct from simulator samples)
# ---------------------------------------------------------------------------

def declared_point(points, time):
    """Exact evaluation of a declared PWL at one explicit point.

    Returns an exact binary64-rational value labeled ``derived_from_declared_
    source``; it is a property of the declaration, never of a saved sample.
    """
    if not _valid_pwl(points) or not _finite(time):
        raise ValueError('declared PWL requires finite values and increasing knots')
    i = bisect.bisect_right([p[0] for p in points], time) - 1
    if i < 0:
        return Fraction(points[0][1])
    if i == len(points) - 1:
        return Fraction(points[i][1])
    (ta, va), (tb, vb) = points[i], points[i + 1]
    t = Fraction(time)
    return Fraction(va) + (Fraction(vb) - Fraction(va)) * (t - Fraction(ta)) / (Fraction(tb) - Fraction(ta))


def declared_interval(points, t0, t1):
    """Range of a declared PWL over [t0, t1], reported unqualified.

    The vertex envelope (both endpoints plus every knot strictly inside) is
    computed with exact rational arithmetic, but no certified rounding
    envelope exists yet, so the result is explicitly ``unqualified``.
    """
    if not _finite(t0) or not _finite(t1) or t1 < t0:
        raise ValueError('interval endpoints must satisfy t0<=t1')
    vertices = [declared_point(points, t0), declared_point(points, t1)]
    vertices.extend(Fraction(v) for t, v in points if t0 < t < t1)
    lo, hi = min(vertices), max(vertices)
    return {
        'low_v': float(lo), 'high_v': float(hi),
        'exact_low_rational': str(lo), 'exact_high_rational': str(hi),
        'origin': 'derived_from_declared_source',
        'method': 'exact rational vertex envelope over endpoints and interior knots',
        'qualification': UNQUALIFIED,
        'note': 'an auditable certification envelope is a separate coordinator '
                'decision; this range is evidence, not a certificate',
    }


def declared_coverage(points, saved, node):
    """Coverage evidence: which declared knots the save grid preserves."""
    knots = sorted({Fraction(t) for t, _ in points})
    present, missing = [], []
    if isinstance(saved.times, list):
        grid = {Fraction(t) for t in saved.times}
        for knot in knots:
            (present if knot in grid else missing).append(float(knot))
    return {
        'knots_declared': [float(k) for k in knots],
        'knots_preserved_in_save_grid': present,
        'knots_missing_from_save_grid': missing,
        'note': 'coverage evidence only; it does not change the historical save '
                'grid and a missing knot is not repaired by interpolation',
    }


def saved_vs_declared(points, saved, node):
    """Reported (never judged) deviation of saved samples from the declaration."""
    if saved.status == INVALID or node not in saved.nodes:
        return {'state': MISSING}
    j = saved.nodes.index(node)
    worst = None
    for i, time in enumerate(saved.times):
        deviation = abs(Fraction(saved.values[i][j]) - declared_point(points, time))
        if worst is None or deviation > worst[0]:
            worst = (deviation, time, saved.values[i][j])
    return {'checks': len(saved.times),
            'max_abs_deviation_v': {
                'time_s': worst[1], 'saved_v': worst[2],
                'exact_abs_deviation_rational': str(worst[0]),
                'abs_deviation_v': _finite_approx(worst[0])},
            'note': 'reported deviation only; no tolerance and no pass state'}


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------

def build_evidence_report(response, *, identity, declared_sources=None,
                          query_plan=(), query_meaning=None, required_nodes=(),
                          expected_row_count=None, require_full_coverage=False,
                          query_nodes=None, reference_saved=None,
                          reference_identity=None, reference_qualification=None,
                          requested_controls=None):
    """Assemble the evidence-only report.  No pass/fail field is produced.

    ``identity`` is a list of ``{'side', 'role', 'path', 'sha256'}`` artifact
    descriptors; original artifact hashes are preserved verbatim.  ``response``
    is the archived kernel response (validated, never regenerated).
    ``reference_saved`` is an optional second ``SavedWaveform`` (e.g. an
    archived Spectre trace) provenance-classified independently; its native
    query precision stays ``unqualified`` unless the caller supplies an
    approved ``reference_qualification`` record.
    """
    if not isinstance(response, dict):
        raise TypeError('response must be a dict')
    declared_sources = {} if declared_sources is None else declared_sources
    nodes = response.get('nodes')
    solutions = response.get('solutions') if isinstance(response.get('solutions'), list) else None
    output_times = (response.get('transient', {}).get('times')
                    if isinstance(response.get('transient'), dict) else None)

    observation = ObservationEvidence(
        response.get('observation_evidence'), nodes=nodes if isinstance(nodes, list) else [],
        solutions=solutions, output_times=output_times if isinstance(output_times, list) else None)
    if 'observation_evidence' in response and not isinstance(response['observation_evidence'], dict):
        observation.status = INVALID
        observation.issues.append(_issue('invalid_observation_evidence',
                                          'present observation evidence must be an object'))
    candidate = SavedWaveform(response.get('saved', {}), side='candidate',
                              required_nodes=required_nodes,
                              expected_row_count=expected_row_count,
                              require_full_coverage=require_full_coverage)
    observation.bind_saved(candidate)

    validity = {'candidate_saved_waveform': candidate.status,
                'observation_evidence': observation.status}
    issues = list(candidate.issues) + list(observation.issues)
    if isinstance(reference_saved, SavedWaveform):
        validity['reference_saved_waveform'] = reference_saved.status
        issues.extend(reference_saved.issues)
    valid_sources = {}
    if not isinstance(declared_sources, dict):
        validity['declared_sources'] = INVALID
        issues.append(_issue('invalid_declared_sources', 'declared sources must be an object'))
    else:
        for node, points in declared_sources.items():
            if not isinstance(node, str) or not _valid_pwl(points):
                validity['declared_sources'] = INVALID
                issues.append(_issue('invalid_declared_pwl',
                                      'declared PWL must be nonempty, finite and strictly increasing', node=node))
            else:
                valid_sources[node] = points
    declared_sources = valid_sources

    provenance = []
    query_nodes = (list(query_nodes) if query_nodes is not None
                   else list(candidate.nodes) if isinstance(candidate.nodes, list) else [])
    if (any(not isinstance(n, str) or not n for n in query_nodes)
            or len(set(query_nodes)) != len(query_nodes)):
        validity['query_plan'] = INVALID
        issues.append(_issue('invalid_query_nodes', 'query columns must be unique nonempty names',
                              requested=query_nodes))
        query_nodes = []
    for query in query_plan:
        time = query.get('time') if isinstance(query, dict) else query
        if not _finite(time):
            issues.append(_issue('invalid_query_time',
                                 'query plan contains a non-finite time', query=query))
            validity['query_plan'] = INVALID
            continue
        entry = {'time_s': time, 'candidate': {
            node: candidate.classify(time, node, declared_sources.get(node), observation)
            for node in query_nodes}}
        if isinstance(query, dict):  # preserve caller design metadata verbatim
            entry['metadata'] = {k: v for k, v in query.items() if k != 'time'}
        if isinstance(reference_saved, SavedWaveform):
            entry['reference'] = {
                node: reference_saved.classify(time, node) for node in query_nodes}
            validity['reference_saved_waveform'] = reference_saved.status
        provenance.append(entry)
        out_of_range = [pr.get('status') for side in ('candidate', 'reference')
                        for pr in entry.get(side, {}).values()
                        if pr.get('status') in ('unavailable', MISSING)]
        if out_of_range and require_full_coverage:
            issues.append(_issue('query_outside_saved_range',
                                 'query plan requires full coverage but a query '
                                 'falls outside a saved range', time_s=time))
            validity['query_plan'] = worst_status([validity.get('query_plan', VALID), INCOMPLETE])
    validity['query_plan'] = validity.get('query_plan', VALID)

    events_status, event_issues, events_payload = preserve_events(response.get('transient'))
    displays_status, display_issues, displays_payload = preserve_displays(
        response.get('transient'), events_payload)
    validity['callback_events'] = events_status
    validity['display_records'] = displays_status
    issues.extend(event_issues)
    issues.extend(display_issues)

    controls = {
        'effective_controls': observation.effective_controls(),
        'effective_source': 'response observation_evidence' if observation.present else MISSING,
        'requested_controls': (dict(requested_controls) if requested_controls is not None
                               else {'state': MISSING,
                                     'note': 'requested controls not supplied; they are '
                                             'not inferred from effective controls'}),
    }

    coverage = {}
    deviations = {}
    interpolation = []
    if declared_sources:
        for node, points in declared_sources.items():
            if candidate.status != INVALID and node in candidate.nodes:
                coverage[node] = declared_coverage(points, candidate, node)
                deviations[node] = saved_vs_declared(points, candidate, node)
        for entry in provenance:
            if candidate.status == INVALID:
                break
            record = {'time_s': entry['time_s']}
            for node, points in declared_sources.items():
                if candidate.status == INVALID or node not in candidate.nodes:
                    continue
                pr = candidate.classify(entry['time_s'], node, points)
                if pr['status'] == 'interpolated':
                    exact = declared_point(points, entry['time_s'])
                    record[node] = {
                        'resampled_v': pr['value_v'],
                        'declared_exact_v': float(exact),
                        'declared_exact_rational': str(exact),
                        'abs_resampling_deviation_v': _finite_approx(abs(Fraction(pr['value_v']) - exact)),
                        'straddled_declared_knots_s': pr.get('straddled_declared_knots_s', []),
                    }
            interpolation.append(record)

    reference = None
    if isinstance(reference_saved, SavedWaveform):
        qualification = (dict(reference_qualification) if reference_qualification
                         else {'native_query_precision': UNQUALIFIED,
                               'note': 'no approved reference precision evidence '
                                       'supplied; provenance is reported, never '
                                       'promoted to certified'})
        reference = {'identity': reference_identity or {'state': MISSING},
                     'qualification': qualification}

    status = worst_status([validity[k] for k in validity]
                          + [observation.status])
    if status == INVALID:
        coverage, deviations, interpolation = {}, {}, []
    return _json_safe({
        'schema': SCHEMA,
        'status': status,
        'status_meaning': {'valid': 'all structural checks passed (no verdict implied)',
                           'invalid': 'structural failure; aggregate numeric summaries withheld; '
                                      'per-side valid saved values remain provenance only',
                           'incomplete': 'required records partially absent',
                           'unqualified': 'present but without an approved certificate',
                           'missing': 'optional artifact absent; absence preserved'},
        'identity': {'artifacts': identity, 'engine_recorded_verbatim': response.get('engine'),
                     'response_schema_version': response.get('schema_version'),
                     'note': 'engine strings are recorded, never used to infer '
                             'capability or qualification. Nonfinite malformed raw numbers '
                             'use explicit invalid_numeric_token objects; original bytes stay in artifacts.'},
        'evidence_validity': validity,
        'issues': issues,
        'coverage': coverage,
        'query_provenance': {'per_query': provenance,
                             'meaning': query_meaning or {'state': MISSING}},
        'source_deviations': deviations,
        'interpolation_diagnostics': {
            'note': 'saved-waveform interpolation diagnostic only; never an '
                    'integration error, a native query or a precision certificate',
            'per_query': interpolation},
        'callbacks': {'events': events_payload, 'display_records': displays_payload},
        'controls': controls,
        'reference_side': reference,
        'verdicts': {'produced': 'none', 'note': 'evidence only; any behavioral '
                                                 'verdict needs a separately '
                                                 'approved checker'},
    })
