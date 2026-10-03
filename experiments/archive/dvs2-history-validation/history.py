"""Exact-rational, finite-observation history compatibility for isolated linear edges.

P is a verified common witness in K_in, F is a covering exclusion of K_out,
and I is invalid input, a remaining uncertainty band, or exhausted search.
This limited model does not implement interrupted transitions or certify a backend.
"""
from dataclasses import dataclass
from fractions import Fraction as Q


def rational(value):
    return value if isinstance(value, Q) else Q(str(value))


@dataclass(frozen=True)
class Event:
    start: Q
    target: Q
    duration: Q
    offset_min: Q
    offset_max: Q
    sample_slope: Q = Q(0)

    def __post_init__(self):
        for key in self.__dataclass_fields__:
            object.__setattr__(self, key, rational(getattr(self, key)))


def _target(event, offset):
    return event.target + event.sample_slope * offset


def value_at(t, events, offsets, initial):
    """One exact event history, including sampled levels on subsequent plateaus."""
    old = initial
    for event, offset in zip(events, offsets):
        start = event.start + offset
        target = _target(event, offset)
        if t <= start:
            return old
        if t < start + event.duration:
            return old + (target - old) * (t - start) / event.duration
        old = target
    return old


def _level_bounds(event, domain):
    return tuple(sorted(_target(event, offset) for offset in domain))


def value_bounds(t, events, box, initial):
    """Conservative enclosure; dependencies are retained by the point witness.

On a possible edge, old level, new level and interpolation fraction form a
multi-affine expression. Its extrema over their enclosing box occur at corners.
Overestimation can produce I, but cannot prove a spurious empty outer domain.
"""
    old = (initial, initial)
    for event, domain in zip(events, box):
        target = _level_bounds(event, domain)
        earliest, latest = (event.start + offset for offset in domain)
        if t <= earliest:
            return old
        if t < latest + event.duration:
            alpha = (max(Q(0), min(Q(1), (t - latest) / event.duration)),
                     max(Q(0), min(Q(1), (t - earliest) / event.duration)))
            corners = [a + (b - a) * c for a in old for b in target for c in alpha]
            return min(corners), max(corners)
        old = target
    return old


@dataclass
class Constraint:
    # A plateau uses only the previous event's held target; -1 is initialization.
    time: Q | None
    event_index: int
    inner_low: Q
    inner_high: Q
    outer_low: Q
    outer_high: Q


def _constraints(rows, events, epsilon, uncertainty):
    constraints = []
    plateaus = {}
    previous_time = None
    for raw in rows:
        if len(raw) != 2:
            raise ValueError('observations must be (time, voltage) pairs')
        t, y = map(rational, raw)
        if previous_time is not None and t <= previous_time:
            raise ValueError('unknown duplicate-time ordering or nonincreasing time')
        previous_time = t
        active = None
        previous = -1
        for i, event in enumerate(events):
            if t <= event.start + event.offset_min:
                break
            if t < event.start + event.offset_max + event.duration:
                active = i
                break
            previous = i
        inner_radius, outer_radius = epsilon - uncertainty, epsilon + uncertainty
        c = Constraint(t if active is not None else None,
                       active if active is not None else previous,
                       y - inner_radius, y + inner_radius,
                       y - outer_radius, y + outer_radius)
        if active is not None:
            constraints.append(c)
        elif previous not in plateaus:
            plateaus[previous] = c
        else:
            old = plateaus[previous]
            old.inner_low = max(old.inner_low, c.inner_low)
            old.inner_high = min(old.inner_high, c.inner_high)
            old.outer_low = max(old.outer_low, c.outer_low)
            old.outer_high = min(old.outer_high, c.outer_high)
    # Intersecting identical plateau expressions is lossless and checks every row.
    return list(plateaus.values()) + constraints


def _bounds(constraint, events, box, initial):
    if constraint.time is not None:
        return value_bounds(constraint.time, events, box, initial)
    if constraint.event_index < 0:
        return initial, initial
    return _level_bounds(events[constraint.event_index], box[constraint.event_index])


def _at(constraint, events, offsets, initial):
    if constraint.time is not None:
        return value_at(constraint.time, events, offsets, initial)
    if constraint.event_index < 0:
        return initial
    return _target(events[constraint.event_index], offsets[constraint.event_index])


def _suggest_witness(constraints, events, box, initial):
    """A proposal only. Acceptance always rechecks all constraints exactly."""
    offsets = [(lo + hi) / 2 for lo, hi in box]
    for i, event in enumerate(events):
        old = initial if i == 0 else _target(events[i - 1], offsets[i - 1])
        if event.sample_slope or (i and events[i - 1].sample_slope):
            continue
        delta = event.target - old
        if not delta:
            continue
        possible = []
        for c in constraints:
            if c.time is None or c.event_index != i:
                continue
            y = (c.outer_low + c.outer_high) / 2
            fraction = (y - old) / delta
            if Q(1, 4) <= fraction <= Q(3, 4):
                possible.append(c.time - event.start - event.duration * fraction)
        if possible:
            possible.sort()
            offsets[i] = max(box[i][0], min(box[i][1], possible[len(possible) // 2]))
    return offsets


def check_history(rows, events, *, initial, epsilon, uncertainty=0, max_boxes=256):
    result = {'status': 'I', 'reason': None, 'witness_offsets': None,
              'boxes_examined': 0, 'boxes_excluded': 0,
              'formal_dvs_qualification': 'I', 'continuous_time_qualified': False,
              'arithmetic': 'exact rational over supplied numeric values'}
    try:
        initial, epsilon, uncertainty = map(rational, (initial, epsilon, uncertainty))
        if epsilon < 0 or uncertainty < 0 or not isinstance(max_boxes, int) or max_boxes < 0:
            raise ValueError('invalid error or search budget')
        if not rows or not events:
            raise ValueError('empty observations or event contract')
        for i, event in enumerate(events):
            if event.duration <= 0 or event.offset_min > event.offset_max:
                raise ValueError('invalid duration or event domain')
            if i and events[i - 1].start + events[i - 1].offset_max + events[i - 1].duration >= event.start + event.offset_min:
                raise ValueError('overlapping/interrupted edge domains are not implemented')
        constraints = _constraints(rows, events, epsilon, uncertainty)
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        return {**result, 'reason': 'invalid_observation_or_contract', 'detail': str(exc)}
    result.update(sample_count=len(rows), constraint_count=len(constraints),
                  epsilon=str(epsilon), uncertainty=str(uncertainty))
    domain = [(e.offset_min, e.offset_max) for e in events]
    queue = [domain]
    unresolved = False
    while queue and result['boxes_examined'] < max_boxes:
        box = queue.pop()
        result['boxes_examined'] += 1
        for c in constraints:
            lo, hi = _bounds(c, events, box, initial)
            if lo > c.outer_high or hi < c.outer_low or c.outer_low > c.outer_high:
                result['boxes_excluded'] += 1
                break
        else:
            candidates = [_suggest_witness(constraints, events, box, initial),
                          [(lo + hi) / 2 for lo, hi in box]]
            for offsets in candidates:
                if all(c.inner_low <= _at(c, events, offsets, initial) <= c.inner_high for c in constraints):
                    return {**result, 'status': 'P', 'reason': 'verified_common_inner_witness',
                            'witness_offsets': [str(x) for x in offsets]}
            # If no inner witness can exist in this box, retain it as unresolved
            # rather than mistakenly counting it toward an empty K_out proof.
            if any(c.inner_low > c.inner_high or
                   (lambda bounds: bounds[0] > c.inner_high or bounds[1] < c.inner_low)(_bounds(c, events, box, initial))
                   for c in constraints):
                unresolved = True
                continue
            widths = [hi - lo for lo, hi in box]
            widest = max(widths)
            if not widest:
                unresolved = True
                continue
            i = widths.index(widest)
            lo, hi = box[i]
            mid = (lo + hi) / 2
            left, right = box.copy(), box.copy()
            left[i], right[i] = (lo, mid), (mid, hi)
            queue.extend([right, left])
    if queue:
        return {**result, 'reason': 'search_budget_exhausted'}
    if unresolved:
        return {**result, 'reason': 'uncertainty_band_unresolved'}
    return {**result, 'status': 'F', 'reason': 'outer_domain_proved_empty'}
