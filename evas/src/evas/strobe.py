"""Expand explicit solve controls without changing the requested output grid."""
from fractions import Fraction
import math

FIELDS = {'strobetimes', 'strobeperiod', 'strobedelay', 'skipstart', 'skipstop'}
MAX_POINTS = 100_000


def _number(value, name):
    try:
        valid = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{name} must be a finite number')
    return float(value)


def expand(stop, *, strobetimes=None, strobeperiod=None, strobedelay=0.0,
           skipstart=0.0, skipstop=None):
    """Use exact arithmetic on binary64 controls, then round each grid point once.

    This defines EVAS's generation order; it does not claim Spectre's private
    arithmetic order. Explicit and periodic points form a sorted union.
    """
    stop = _number(stop, 'stop')
    if stop <= 0:
        raise ValueError('stop must be positive')
    explicit = [] if strobetimes is None else strobetimes
    if not isinstance(explicit, list) or len(explicit) > MAX_POINTS:
        raise ValueError(f'strobetimes must be an array of at most {MAX_POINTS} points')
    explicit = [_number(t, 'strobetimes entry') for t in explicit]
    if any(t < 0 or t > stop for t in explicit) or any(a >= b for a,b in zip(explicit, explicit[1:])):
        raise ValueError('strobetimes must strictly increase within [0,stop]')
    start = _number(skipstart, 'skipstart')
    end = stop if skipstop is None else _number(skipstop, 'skipstop')
    delay = _number(strobedelay, 'strobedelay')
    if not 0 <= start <= end <= stop or delay < 0:
        raise ValueError('strobe window must be within [0,stop] and strobedelay nonnegative')
    periodic = []
    if strobeperiod is None:
        if start != 0 or skipstop is not None or delay != 0:
            raise ValueError('strobe window and delay require strobeperiod')
    else:
        period = _number(strobeperiod, 'strobeperiod')
        if period <= 0 or delay >= period:
            raise ValueError('strobeperiod must be positive and strobedelay smaller than it')
        first = Fraction(start) + Fraction(delay)
        count = max(0, int((Fraction(end)-first)//Fraction(period))+1)
        if count > MAX_POINTS:
            raise ValueError(f'periodic strobe exceeds {MAX_POINTS} points')
        periodic = [float(first+k*Fraction(period)) for k in range(count)]
        if any(a >= b for a,b in zip(periodic,periodic[1:])):
            raise ValueError('periodic strobe points collapse at binary64 resolution')
    points = sorted(set(explicit).union(periodic))
    if len(points) > MAX_POINTS:
        raise ValueError(f'combined strobe exceeds {MAX_POINTS} points')
    return points


def controls(config):
    """Normalize only the optional controls; an old request stays unchanged."""
    if not FIELDS.intersection(config):
        return {}
    return {'strobetimes': expand(config['stop'], **{k:config[k] for k in FIELDS if k in config})}
