"""Directed Decimal enclosures for finite legacy-chain observations.

Operands are the frozen binary64 inputs. Callback boxes are supplied evidence,
not fitted to outputs. This module does not qualify that evidence or a simulator.
"""
from decimal import Decimal, localcontext, ROUND_FLOOR, ROUND_CEILING
from fractions import Fraction
from copy import deepcopy
import itertools


PRECISION = 80


class BoundsPending(ValueError):
    """The supplied boxes do not establish one supported transition geometry."""


def exact(value):
    return Decimal.from_float(value) if type(value) is float else Decimal(value)


def rounded(operation, rounding):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        ctx.rounding = rounding
        return operation()


class I:
    def __init__(self, lo, hi=None):
        self.lo = exact(lo)
        self.hi = self.lo if hi is None else exact(hi)
        if not self.lo.is_finite() or not self.hi.is_finite() or self.lo > self.hi:
            raise BoundsPending('invalid finite interval')

    def __add__(self, other):
        other = interval(other)
        return I(rounded(lambda: self.lo + other.lo, ROUND_FLOOR),
                 rounded(lambda: self.hi + other.hi, ROUND_CEILING))

    __radd__ = __add__

    def __neg__(self):
        return I(self.hi.copy_negate(), self.lo.copy_negate())

    def __sub__(self, other):
        return self + -interval(other)

    def __rsub__(self, other):
        return interval(other) + -self

    def __mul__(self, other):
        other = interval(other)
        pairs = list(itertools.product((self.lo, self.hi), (other.lo, other.hi)))
        return I(min(rounded(lambda a=a, b=b: a*b, ROUND_FLOOR) for a, b in pairs),
                 max(rounded(lambda a=a, b=b: a*b, ROUND_CEILING) for a, b in pairs))

    __rmul__ = __mul__

    def __truediv__(self, other):
        other = interval(other)
        if other.lo <= 0 <= other.hi:
            raise BoundsPending('division interval includes zero')
        pairs = list(itertools.product((self.lo, self.hi), (other.lo, other.hi)))
        return I(min(rounded(lambda a=a, b=b: a/b, ROUND_FLOOR) for a, b in pairs),
                 max(rounded(lambda a=a, b=b: a/b, ROUND_CEILING) for a, b in pairs))

    def exp(self):
        # Decimal.exp is correctly rounded with ROUND_HALF_EVEN, regardless of
        # the context's rounding mode. Adjacent representables enclose it.
        with localcontext() as ctx:
            ctx.prec = PRECISION
            first = self.lo.exp()
            last = first if self.lo == self.hi else self.hi.exp()
            low = first.next_minus()
            high = last.next_plus()
        return I(low, high)

    def positive(self):
        return I(max(Decimal(0), self.lo), max(Decimal(0), self.hi))

    def pair(self):
        return self.lo, self.hi


def interval(value):
    if isinstance(value, I):
        return value
    if isinstance(value, (tuple, list)):
        return I(*value)
    return I(value)


def hull(values):
    values = list(values)
    if not values:
        raise BoundsPending('empty interval union')
    return I(min(v.lo for v in values), max(v.hi for v in values))


def box(callback):
    if isinstance(callback, dict):
        callback = callback.get('time_bounds_s')
    if callback is None:
        raise BoundsPending('callback time bounds missing')
    return interval(callback)


def pwl(points, time):
    """Range over every intersected affine segment, including interior knots."""
    time = interval(time)
    pieces = []
    if time.lo <= exact(points[0][0]):
        pieces.append(I(points[0][1]))
    for (a, u), (b, v) in zip(points, points[1:]):
        left, right = max(time.lo, exact(a)), min(time.hi, exact(b))
        if left <= right:
            pieces.append(I(u) + (I(v)-I(u)) * (I(left, right)-I(a))/(I(b)-I(a)))
    if time.hi >= exact(points[-1][0]):
        pieces.append(I(points[-1][1]))
    return hull(pieces)


def ramp_filter_response(time, tau):
    """K(h)=h-tau*(1-exp(-h/tau)); monotone for h >= 0."""
    time = interval(time).positive()
    tau = interval(tau)
    if tau.lo != tau.hi or tau.lo <= 0:
        raise BoundsPending('filter requires a fixed positive time constant')
    def scalar(h):
        if h == 0:
            return I(0)
        h = I(h)
        return h-tau*(1-(-h/tau).exp())
    low = scalar(time.lo)
    high = low if time.lo == time.hi else scalar(time.hi)
    return I(low.lo, high.hi)


def filtered_pwl(points, time, tau):
    """DC-initialized one-pole response as a sum of slope changes."""
    time = interval(time)
    out = I(points[0][1])
    previous = I(0)
    for (a, u), (b, v) in zip(points, points[1:]):
        slope = (I(v)-I(u))/(I(b)-I(a))
        out += (slope-previous)*ramp_filter_response(time-I(a), tau)
        previous = slope
    out -= previous*ramp_filter_response(time-I(points[-1][0]), tau)
    return out


def sample_envelope(card, label, callbackbox, index):
    time = box(callbackbox)
    kind = card['kind']
    if kind == 'sef':
        config = next(p for p in card['instances'] if p['name'] == label)
        if config['cross']:
            reset = pwl(card['inputs']['rst'], time)
            threshold = exact(.25)
            if reset.lo > threshold:
                return I(.25).pair()
            if reset.hi > threshold:
                raise BoundsPending('reset predicate changes within callback box')
        return (I(config['gain'])*pwl(card['inputs']['u'], time)+I(config['bias'])).pair()
    if kind == 'integral':
        return pwl(card['inputs']['u'], time).pair()
    if kind == 'c2':
        return filtered_pwl(card['inputs']['vin'], time, .5e-6).pair()
    if kind == 'nt':
        return I(1 if label == 'a' else index).pair()
    raise BoundsPending('unknown legacy card kind')


class Polygon:
    """Interval slope-change replay; unresolved branch geometry stays pending."""
    def __init__(self, initial, callbacks, delay, rise, fall):
        initial = interval(initial)
        self.initial = initial
        value = origin = target = initial
        slope = I(0)
        start = I(0)
        self.knots = [(start, slope)]
        for event, new in callbacks:
            activation = interval(event)+I(delay)
            new = interval(new)
            if new.lo == new.hi == target.lo == target.hi:
                continue
            if slope.lo == slope.hi == 0:
                current = target
            else:
                end = start+(target-value)/slope
                if end.hi <= activation.lo:
                    self.knots.append((end, I(0)))
                    value = current = target
                    slope = I(0)
                    start = end
                elif end.lo < activation.hi:
                    raise BoundsPending('completed/interrupted branch changes within callback boxes')
                else:
                    current = value+slope*(activation-start).positive()
            if new.lo > current.hi:
                direction = 1
            elif new.hi < current.lo:
                direction = -1
            elif new.lo == new.hi == current.lo == current.hi:
                direction = 0
            else:
                raise BoundsPending('transition direction changes within callback boxes')
            if slope.lo == slope.hi == 0:
                new_origin = current
            elif slope.lo > 0:
                new_origin = origin if direction > 0 else target
            elif slope.hi < 0:
                new_origin = origin if direction < 0 else target
            else:
                raise BoundsPending('old transition slope direction is unresolved')
            new_slope = (new-new_origin)/I(rise if direction > 0 else fall) if direction else I(0)
            value, start, origin, target, slope = current, activation, new_origin, new, new_slope
            self.knots.append((start, slope))
        if not slope.lo == slope.hi == 0:
            self.knots.append((start+(target-value)/slope, I(0)))

    def value(self, time):
        out, previous = self.initial, I(0)
        for start, slope in self.knots:
            out += (slope-previous)*(interval(time)-start).positive()
            previous = slope
        return out

    def filtered(self, time, tau):
        out, previous = self.initial, I(0)
        for start, slope in self.knots:
            change = slope-previous
            if not change.lo == change.hi == 0:
                out += change*ramp_filter_response(interval(time)-start, tau)
            previous = slope
        return out


def rectangles(time, initial, callbacks, scale=1, offset=0):
    time = interval(time)
    previous = I(initial)
    out = I(offset)+previous*time/I(scale)
    for event, target in callbacks:
        target = interval(target)
        out += (target-previous)*(time-interval(event)).positive()/I(scale)
        previous = target
    return out


def nt_orders(callbacks):
    """All box-compatible orders; exact same-time traces retain their order."""
    if len(callbacks) > 8:
        raise BoundsPending('near-timer permutation cap exceeded')
    pairs = []
    for i, first in enumerate(callbacks):
        for j, second in enumerate(callbacks):
            if i == j:
                continue
            a, b = box(first), box(second)
            if (a.hi < b.lo or (i < j and first['time_s'] == second['time_s'])
                    or first['label'] == second['label'] and first['index'] < second['index']):
                pairs.append((i, j))
    for order in itertools.permutations(range(len(callbacks))):
        positions = {v: i for i, v in enumerate(order)}
        if all(positions[a] < positions[b] for a, b in pairs):
            yield [callbacks[i] for i in order]


def compile_history(card, callbacks):
    """Build query-independent polygons once from a private frozen history."""
    # The fixed cards have distinct successive events within each channel.
    # Cross-channel NT boxes may overlap and are handled by nt_orders below.
    previous = {}
    for callback in callbacks:
        label = callback['label']
        current = box(callback)
        if label in previous:
            prior = previous[label]
            if callback['index'] <= prior['index'] or box(prior).hi >= current.lo:
                raise BoundsPending('same-channel callback order or separation unproved')
        previous[label] = callback
    kind = card['kind']
    if kind == 'sef':
        polygons = []
        for config in card['instances']:
            name = config['name']
            history = [(box(c), interval(sample_envelope(card, name, c, c['index'])))
                       for c in callbacks if c['label'] == name]
            # The frozen SEF source emits float(gain*.25+bias) from its exact
            # decimal-intent Fraction initial, rather than runtime arithmetic.
            initial = float(Fraction(str(config['gain']))*Fraction(1, 4)+Fraction(str(config['bias'])))
            poly = Polygon(initial, history, config['delay']*1e-6, config['rise']*1e-6, config['fall']*1e-6)
            polygons.append((name, poly, config['tau']*1e-6))
        def evaluate(time):
            out = {}
            for name, poly, tau in polygons:
                out[name+'e'] = poly.value(time)
                out[name+'f'] = poly.filtered(time, tau)
            return out
        return evaluate
    if kind == 'integral':
        history = [(box(c), interval(sample_envelope(card, 'sample', c, c['index']))) for c in callbacks]
        return lambda time: {'i': rectangles(time, .25, history, 1e-6, .05)}
    if kind == 'c2':
        history = [(box(c), interval(sample_envelope(card, 'sample', c, c['index']))) for c in callbacks]
        poly = Polygon(.1, history, 0, 25e-9, 25e-9)
        return lambda time: {'z': filtered_pwl(card['inputs']['vin'], time, .5e-6), 'vout': poly.value(time)}
    if kind == 'nt':
        if not card['chain']:
            return lambda time: {}
        possibilities = []
        for order in nt_orders(callbacks):
            a = b = 0
            history = []
            for callback in order:
                if callback['label'] == 'a':
                    a = 1
                else:
                    b = callback['index']
                history.append((box(callback), I(.01)*a+I(.1)*b))
            poly = Polygon(0, history, 0, .05, .05)
            possibilities.append((poly, history))
        if not possibilities:
            raise BoundsPending('no callback-box-compatible order')
        def evaluate(time):
            values = [{'e': poly.value(time), 'f': poly.filtered(time, .05),
                       'i': rectangles(time, 0, history)} for poly, history in possibilities]
            return {name: hull(p[name] for p in values) for name in ('e', 'f', 'i')}
        return evaluate
    raise BoundsPending('unknown legacy card kind')


def prepare(card, callbacks):
    """Return an envelope(time) callable owning a private frozen history.

    reference_error_V measures directed arithmetic width at the supplied central
    callback/time points. Full output intervals additionally include history,
    observation-time and possible cross-channel order uncertainty.
    """
    card, callbacks = deepcopy(card), deepcopy(callbacks)
    try:
        full = compile_history(card, callbacks)
        point_callbacks = [{**c, 'time_bounds_s': [c['time_s'], c['time_s']]} for c in callbacks]
        point_history = all(box(c).lo == box(c).hi == exact(c['time_s']) for c in callbacks)
        central = full if point_history else compile_history(card, point_callbacks)
    except (BoundsPending, KeyError, IndexError, StopIteration, TypeError, ValueError, ArithmeticError) as exc:
        reason = str(exc)
        return lambda time: {'status': 'pending', 'outputs': {}, 'reference_error_V': Decimal(0), 'reason': reason}
    def evaluate(time):
        try:
            query = interval(time)
            outputs = full(query)
            center = rounded(lambda: (query.lo+query.hi)/2, ROUND_FLOOR)
            point = outputs if point_history and query.lo == query.hi else central(I(center))
            arithmetic = max((rounded(lambda v=v: v.hi-v.lo, ROUND_CEILING) for v in point.values()), default=Decimal(0))
            return {'status': 'proved', 'outputs': {name: value.pair() for name, value in outputs.items()},
                    'reference_error_V': arithmetic,
                    'method': 'directed Decimal80 interval replay; finite observations only'}
        except (BoundsPending, KeyError, IndexError, StopIteration, TypeError, ValueError, ArithmeticError) as exc:
            return {'status': 'pending', 'outputs': {}, 'reference_error_V': Decimal(0), 'reason': str(exc)}
    return evaluate


def envelope(card, callbacks, time):
    """Convenience entry point for a single finite query."""
    return prepare(card, callbacks)(time)
